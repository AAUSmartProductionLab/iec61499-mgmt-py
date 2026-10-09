"""The AAS as the desired state of a module: what it describes, how the running program differs
from that, and the program brought to it online.

A module is delivered with its program and its AAS (the module's own and one per component).
What the AAS describes is read here without the module spec the program may have been generated
from:

- the components (Hierarchical Structures) are the equipment;
- a component's skills are the skill primitives, each with its parameters, limits and results;
- a skill of the module of the kind Composite is a module level skill: its parameters, the
  primitives it runs in order, what each step is handed (a constant, or a parameter of the skill)
  and which step gives a result;
- the steps of the module's own Reset and Stop (skills of the kind ModuleControl) are the procedures;
- the Control Configuration records what was built: instance, block type and type hash.

``described`` gives that as a module spec without wiring, ``differences`` compares it with the
program FORTE reports (read by the module rules, ``structure``), and ``reconfigure`` applies what
the rules allow online: a constant, a parameter's default or limits, and a module level skill
that is described but not in the program. A reconfiguration is therefore a change to the AAS;
this module carries it into the program. ``record`` writes what was built back into the Control
Configuration.

The AASs are read as plain JSON (an environment: shells and submodels), as an AAS server gives
them.
"""
from __future__ import annotations

import base64
import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import urllib.request
import xml.etree.ElementTree as ET

from iec61499_mgmt.protocol import Client, Command
from iec61499_mgmt.sysfile import FlatApplication, flatten
from modgen.fbxml import connections as wire, fb
from modgen.module import module_skill
from modgen.spec import Composite, Equipment, Input, ModuleSpec, Parameter, Skill, Step

from .compare import Drift
from .device import Snapshot, literal, read_structure, read_values
from .structure import driven_by, stated, structure
from .sync import Refused, guard, lacking, online, summary

BASE = "https://smartproductionlab.aau.dk"
PRIMITIVE, COMPOSITE, CONTROL = (f"{BASE}/skill/{kind}" for kind in ("Primitive", "Composite", "ModuleControl"))
# The kinds of step a module built by the module rules can run (ARSO knows more: parallel, decision, conditional).
RUNS = ("step",)
IEC = {"xs:double": "LREAL", "xs:boolean": "BOOL", "xs:short": "INT", "xs:int": "DINT", "xs:unsignedShort": "UINT"}
MODULE_TYPE = f"{BASE}/Resource/Module"
# The variables every command has; a command's other variables are its parameters and results.
OWN = ("Session", "Accepted", "ErrorID")
# What a module's program says about itself (rule 1): its name and where its OPC UA nodes are.
MODULE_NAME, MODULE_ROOT = "Occupation.Module", "Occupation.UaRoot"


class NotDescribed(ValueError):
    """The AAS does not describe a module in the way the module rules need."""


# Reading an AAS as JSON ------------------------------------------------------------------------

def children(element: dict | None) -> list[dict]:
    if not element:
        return []
    kids = element.get("submodelElements") or element.get("statements") or element.get("value") or []
    return [k for k in kids if isinstance(k, dict)] if isinstance(kids, list) else []


def at(element: dict | None, *path: str) -> dict | None:
    for step in path:
        element = next((c for c in children(element) if c.get("idShort") == step), None)
    return element


def submodel(env: dict, id_short: str) -> dict | None:
    return next((s for s in env.get("submodels", []) if s.get("idShort") == id_short), None)


def meaning(element: dict) -> str:
    keys = (element.get("semanticId") or {}).get("keys") or []
    return keys[0]["value"] if keys else ""


def also(element: dict) -> list[str]:
    """The supplemental semanticIds of an element: the kind of a skill, what a step is called."""
    return [k["value"] for ref in element.get("supplementalSemanticIds") or [] for k in ref.get("keys", [])[:1]]


def target(reference: dict | None) -> list[str]:
    """The key values of a ReferenceElement's reference."""
    return [k["value"] for k in ((reference or {}).get("value") or {}).get("keys", [])]


def variables(operation: dict | None, kind: str) -> list[dict]:
    return [v["value"] for v in (operation or {}).get(kind) or [] if v["value"]["idShort"] not in OWN]


def qualifier(element: dict, name: str) -> str | None:
    return next((q.get("value") for q in element.get("qualifiers") or [] if q.get("type") == name), None)


def value_of(text, typ: str):
    """A value as the AAS writes it, as a Python value of the IEC type ``typ``."""
    if text is None:
        return None
    if typ == "BOOL":
        return str(text).strip().lower() == "true"
    return float(text) if typ == "LREAL" else int(float(text))


def parameter(variable: dict) -> Parameter:
    """A skill's parameter from the input variable of its Start operation."""
    typ = IEC[variable["valueType"]]
    default = qualifier(variable, "Default")
    return Parameter(type=typ, unit=qualifier(variable, "Unit"), minimum=value_of(qualifier(variable, "Minimum"), typ),
                     maximum=value_of(qualifier(variable, "Maximum"), typ),
                     default=value_of(variable.get("value") if default is None else default, typ))


def inside(inner: Parameter, outer: Parameter) -> bool:
    """Every value ``inner`` allows is one ``outer`` allows: a skill may not offer more than the
    component it hands the value to can do."""
    return ((outer.minimum is None or (inner.minimum is not None and inner.minimum >= outer.minimum))
            and (outer.maximum is None or (inner.maximum is not None and inner.maximum <= outer.maximum)))


# Where the AASs are ------------------------------------------------------------------------------

def b64(identifier: str) -> str:
    """An identifier as the AAS HTTP API expects it in a path (base64url, no padding)."""
    return base64.urlsafe_b64encode(identifier.encode()).decode().rstrip("=")


def is_server(source: str) -> bool:
    return source.startswith(("http://", "https://"))


def fetch(url: str):
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.loads(response.read())


def load(source: str, shell: str | None = None) -> tuple[dict, list[dict]]:
    """The AAS of a module and those of its components, each as an environment (shell and
    submodels), from ``source``: a folder of AAS files (one environment per ``.json``) or the
    address of an AAS server. ``shell``: the module's idShort, when the source holds several."""
    if is_server(source):
        base, shells, cursor = source.rstrip("/"), [], None
        while True:
            page = fetch(f"{base}/shells?limit=100" + (f"&cursor={cursor}" if cursor else ""))
            shells += page["result"]
            cursor = (page.get("paging_metadata") or {}).get("cursor")
            if not cursor or not page["result"]:
                break

        def environment(found: dict) -> dict:
            return {"assetAdministrationShells": [found],
                    "submodels": [fetch(f"{base}/submodels/{b64(r['keys'][0]['value'])}") for r in found.get("submodels", [])]}
    else:
        files = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(Path(source).glob("*.json"))]
        whole = {env["assetAdministrationShells"][0]["id"]: env for env in files if env.get("assetAdministrationShells")}
        shells = [env["assetAdministrationShells"][0] for env in whole.values()]

        def environment(found: dict) -> dict:
            return whole[found["id"]]

    modules = [s for s in shells if s["assetInformation"].get("assetType") == MODULE_TYPE
               and shell in (None, s["idShort"], s["id"])]
    if len(modules) != 1:
        raise NotDescribed(f"{source} holds {len(modules)} module AASs" + (f" named {shell}" if shell else "")
                           + (": name one of " + ", ".join(s["idShort"] for s in modules) if modules else ""))
    module = environment(modules[0])
    parts = {node.get("globalAssetId") for node in children(at(submodel(module, "HierarchicalStructures"), "EntryNode"))}
    return module, [environment(s) for s in shells if s["assetInformation"].get("globalAssetId") in parts]


def store(source: str, module: dict) -> str:
    """Put the module's Control Configuration (the record of what was built) back where its AAS
    came from; returns where it went."""
    config, shell = submodel(module, "ControlConfiguration"), module["assetAdministrationShells"][0]
    if is_server(source):
        url = f"{source.rstrip('/')}/submodels/{b64(config['id'])}"
        request = urllib.request.Request(url, json.dumps(config).encode(), method="PUT",
                                         headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=30):
            return url
    path = Path(source) / f"{shell['idShort']}.json"
    path.write_text(json.dumps(module, indent=1), encoding="utf-8")
    return str(path)


def endpoint(module: dict) -> tuple[str | None, int | None]:
    """Where the Control Configuration says the module's FORTE is managed: (host, port)."""
    stated_ = (at(submodel(module, "ControlConfiguration"), "Runtime", "ManagementEndpoint") or {}).get("value") or ""
    host, _, port = stated_.rpartition(":")
    return (host or None, int(port)) if port.isdigit() else (stated_ or None, None)


# What the AAS describes ------------------------------------------------------------------------

def described(module: dict, components: list[dict], name: str = "Module", package: str = "module",
              opcua_root: str = "/Objects/Module") -> ModuleSpec:
    """The module its AAS (``module``) and the AASs of its ``components`` describe, as a module spec
    without wiring: equipment by name, skill primitives, module level skills and procedures.

    ``name``, ``package`` and ``opcua_root`` are what the program says about itself; the AAS is not
    asked for them.
    """
    structure_, skills_ = (submodel(module, n) for n in ("HierarchicalStructures", "Skills"))
    if skills_ is None:
        raise NotDescribed("the module's AAS has no Skills submodel")
    items = {node.get("globalAssetId"): node["idShort"] for node in children(at(structure_, "EntryNode"))}
    equipment = {item: Equipment.model_construct(inputs={}) for item in items.values()}

    skills: dict[str, Skill] = {}
    for env in components:
        shell = env["assetAdministrationShells"][0]
        item = items.get(shell["assetInformation"].get("globalAssetId"))
        if item is None:
            raise NotDescribed(f"{shell['idShort']} is no component the module's Hierarchical Structures name")
        for skill in children(at(submodel(env, "Skills"), "Skills")):
            start = at(skill, "Start", "Start")
            results = {v["idShort"]: IEC[v["valueType"]] for v in variables(start, "outputVariables")}
            equipment[item].inputs.update({r: Input.model_construct(type=t) for r, t in results.items()})
            contract = at(skill, "Contract")
            skills[skill["idShort"]] = Skill.model_construct(
                equipment=item, parameters={v["idShort"]: parameter(v) for v in variables(start, "inputVariables")},
                results={r: r for r in results}, offered=at(skill, "Start", "InterfaceReference") is not None,
                ensures=(at(contract, "Ensures") or {}).get("value"),
                timeout=(at(contract, "Timeout") or {}).get("value") or "10s")

    def sequence(steps_: dict | None, operation: dict | None, results: dict[str, str] | None = None) -> list[Step]:
        """The steps below ``steps_`` in their Order. A step's Bindings hand each input of its skill
        a constant (Value) or a parameter of the skill it is a step of (SourceElement: an input
        variable of ``operation``); its Outputs say which results of the command it gives."""
        inputs = {v["idShort"]: parameter(v) for v in variables(operation, "inputVariables")}
        get = lambda element, name_: (at(element, name_) or {}).get("value")  # noqa: E731
        found = []
        for step in sorted(children(steps_), key=lambda s: int(get(s, "Order") or 0)):
            name_, kind = get(step, "NodeId") or step["idShort"], get(step, "Kind") or "step"
            if kind not in RUNS:
                raise NotDescribed(f"step {name_} is of the kind {kind}: the control of this module runs steps one after "
                                   "the other only")
            skill = (target(at(step, "Skill")) or [None])[-1]
            if skill not in skills:
                raise NotDescribed(f"step {name_} runs {skill}, which no component of the module has")
            bind = {}
            for given in children(at(step, "Bindings")):
                key = get(given, "Name")
                if key not in skills[skill].parameters:
                    raise NotDescribed(f"step {name_}: {skill} has no parameter {key}")
                declared_ = skills[skill].parameters[key]
                handed = (target(at(given, "SourceElement")) or [None])[-1]
                if handed is not None and handed not in inputs:
                    raise NotDescribed(f"step {name_}: {key} is handed {handed}, which the skill does not take")
                if handed is None and str(get(given, "Value") or "").strip() == "":
                    raise NotDescribed(f"step {name_}: {key} is handed nothing (neither a value nor a parameter of the skill)")
                constant = None if handed is not None else value_of(get(given, "Value"), declared_.type)
                if constant is not None and not isinstance(constant, bool) and (
                        (declared_.minimum is not None and constant < declared_.minimum)
                        or (declared_.maximum is not None and constant > declared_.maximum)):
                    raise NotDescribed(f"step {name_}: {key} = {constant} is outside what {skill} takes "
                                       f"({declared_.minimum} to {declared_.maximum})")
                if handed is not None and not inside(inputs[handed], declared_):
                    raise NotDescribed(f"step {name_}: {key} is handed {handed} ({inputs[handed].minimum} to "
                                       f"{inputs[handed].maximum}), more than {skill} takes ({declared_.minimum} "
                                       f"to {declared_.maximum})")
                bind[key] = handed if handed is not None else constant
            for given in children(at(step, "Outputs")):
                inner = (target(at(given, "ResultReference")) or [None])[-1]
                if inner not in skills[skill].results:
                    raise NotDescribed(f"step {name_}: {skill} has no result {inner}")
                if results is not None:
                    results[get(given, "OutputId")] = f"{name_}.{inner}"
            found.append(Step(skill=skill, name=name_, bind=bind))
        return found

    composites, procedures = {}, {}
    # A skill that is described and not built yet has no action that calls it; it gets one when it
    # is built. One that is built is offered if a command of it names its action.
    built = {path.split(".")[0] for path, _, _ in instances(module) if path}
    for skill in children(at(skills_, "Skills")):
        kinds, steps_ = also(skill), at(skill, "Start", "Steps")
        if CONTROL in kinds:
            # What the module runs itself while resetting or stopping; a step is called <procedure>/<step>.
            if children(steps_):
                procedures[next(a for a in also(children(steps_)[0]) if "/procedures/" in a).split("/")[-2]] = sequence(steps_, None)
            continue
        if steps_ is None and COMPOSITE not in kinds:
            continue
        start, results = at(skill, "Start", "Start"), {}
        execute = sequence(steps_, start, results)
        declared_ = [v["idShort"] for v in variables(start, "outputVariables")]
        composites[skill["idShort"]] = Composite(
            description=next((d["text"] for d in skill.get("description") or []), ""),
            parameters={v["idShort"]: parameter(v) for v in variables(start, "inputVariables")},
            execute=execute, stop=sequence(at(skill, "Stop", "Steps"), None),
            results={r: results[r] for r in declared_ if r in results},
            offered=at(skill, "Start", "InterfaceReference") is not None or skill["idShort"] not in built)
    return ModuleSpec.model_construct(module=name, package=package, opcua_root=opcua_root, equipment=equipment,
                                      skills=skills, composites=composites, procedures=procedures)


def instances(module: dict) -> list[tuple[str, str, str | None]]:
    """What the Control Configuration records as built: (instance, block type, type hash or None)."""
    found = []
    for instance in children(at(submodel(module, "ControlConfiguration"), "Instances")):
        get = lambda n: (at(instance, n) or {}).get("value")  # noqa: E731
        found.append((get("InstancePath"), get("FBType"), get("TypeHash")))
    return found


# The program against the description -------------------------------------------------------------

@dataclass
class Differences:
    """How a running program differs from what its AAS describes; empty: the AAS holds."""
    create: list[str] = field(default_factory=list)                         # described skills the program lacks
    values: dict[str, tuple[str, str | None]] = field(default_factory=dict)  # port -> (described, running)
    restart: list[str] = field(default_factory=list)                        # differences no online change removes
    built: list[str] = field(default_factory=list)                          # the record of what was built is wrong

    @property
    def empty(self) -> bool:
        return not (self.create or self.values or self.restart or self.built)

    @property
    def online(self) -> bool:
        """Something differs, and all of it can be brought in line without a restart."""
        return bool(self.create or self.values) and not self.restart

    def lines(self) -> list[str]:
        return ([f"described, not in the program: {n}" for n in self.create]
                + [f"{p} = {r}, the AAS describes {w}" for p, (w, r) in self.values.items()]
                + self.restart + self.built)


@dataclass
class Reading:
    """A module read against its AAS."""
    spec: ModuleSpec                 # what the AAS describes (``described``)
    snapshot: Snapshot
    running: dict                    # the structure of the program (``structure``)
    differences: Differences


def read(client: Client, host: str, port: int, module: dict, components: list[dict], resource: str = "RES") -> Reading:
    """Read the running program and compare it with what the AASs describe."""
    snap = read_structure(client, host, port, resource)
    if snap.empty:
        raise NotDescribed(f"{host}:{port} runs no program")

    def value(port_: str) -> str | None:
        if port_ not in snap.values:
            read_values(client, snap, [port_])
        return snap.values.get(port_)

    package = next((t.partition("::")[0] for t in snap.fbs.values() if "::EQ_" in t or "::SK_" in t), None)
    if package is None or value(MODULE_NAME) is None:
        raise NotDescribed(f"{host}:{port} does not run a module built by the module rules")
    spec = described(module, components, literal(value(MODULE_NAME)), package, literal(value(MODULE_ROOT)))
    wanted = stated(spec)
    primitives = {n: {"package": package, **{k: v for k, v in s.items() if k != "offered"}}
                  for n, s in wanted["skills"].items()}
    running = structure(snap.fbs, snap.connections, value, primitives)
    found = differences(wanted, running, spec)
    for path, typ, digest in instances(module):
        if path.split(".")[0] in found.create:
            continue                                      # of a skill that is still to be built
        if path not in snap.fbs:
            found.built.append(f"{path}: recorded as built, not in the program")
        elif snap.fbs[path] != typ:
            found.built.append(f"{path} is {snap.fbs[path]}, recorded as {typ}")
        elif digest and snap.hashes.get(typ) != digest:
            found.built.append(f"{path}: {typ} has another hash than the one recorded")
    return Reading(spec, snap, running, found)


def differences(wanted: dict, running: dict, spec: ModuleSpec) -> Differences:
    """What of ``wanted`` (the AAS, ``stated``) the ``running`` program (``structure``) does not show."""
    found = Differences()
    if wanted["equipment"] != running["equipment"]:
        found.restart.append(f"equipment: the AAS describes {wanted['equipment']}, the program has {running['equipment']}")
    for name, skill in wanted["skills"].items():
        if skill["offered"] != running["skills"].get(name, {}).get("offered"):
            found.restart.append(f"{name}: {'offered' if skill['offered'] else 'not offered'} in the AAS, the program differs")

    def text(value, typ: str) -> str:
        return Parameter(type=typ, default=value).literal()

    def sequence(prefix: str, described_: list[dict], have: list[dict]):
        if [(s["skill"], s["name"]) for s in described_] != [(s["skill"], s["name"]) for s in have]:
            found.restart.append(f"{prefix}: the AAS describes the steps {[s['name'] for s in described_]}, "
                                 f"the program runs {[s['name'] for s in have]}")
            return
        for a, b in zip(described_, have):
            for p, v in a["bind"].items():
                r = b["bind"].get(p)
                if v == r:
                    continue
                if isinstance(v, str) or isinstance(r, str):
                    found.restart.append(f"{prefix}.{a['name']}.{p}: handed {v} in the AAS, {r} in the program")
                else:
                    typ = spec.skills[a["skill"]].parameters[p].type
                    found.values[f"{prefix}.{a['name']}.{p}"] = (text(v, typ), text(r, typ))

    for name, comp in wanted["composites"].items():
        have = running["composites"].get(name)
        if have is None:
            found.create.append(name)
            continue
        sequence(f"{name}.Execute", comp["execute"], have["execute"])
        sequence(f"{name}.Stop", comp["stop"], have["stop"])
        if (list(comp["parameters"]), comp["results"], comp["offered"]) != (list(have["parameters"]), have["results"], have["offered"]):
            found.restart.append(f"{name}: parameters, results or whether it is offered differ from the AAS")
            continue
        for p, decl in comp["parameters"].items():
            if decl["type"] != have["parameters"][p]["type"]:
                found.restart.append(f"{name}.{p}: {decl['type']} in the AAS, {have['parameters'][p]['type']} in the program")
                continue
            for key, pin in (("default", "Default"), ("minimum", "Lower"), ("maximum", "Upper")):
                if decl[key] != have["parameters"][p][key]:
                    if decl[key] is None:
                        found.restart.append(f"{name}.{p}: the AAS states no {key}, the program has {have['parameters'][p][key]}")
                    else:
                        r = have["parameters"][p][key]
                        found.values[f"{name}.{p}.{pin}"] = (text(decl[key], decl["type"]),
                                                             None if r is None else text(r, decl["type"]))
    for name in running["composites"]:
        if name not in wanted["composites"]:
            found.restart.append(f"{name}: a skill of the program the AAS does not describe")
    for name in sorted(set(wanted["procedures"]) | set(running["procedures"])):
        sequence(name, wanted["procedures"].get(name, []), running["procedures"].get(name, []))
    return found


# Bringing the program to the description -----------------------------------------------------------

def init_tail(connections) -> str:
    """Where the INIT chain of the running program ends (rule 1.5): a new skill is added there."""
    at_, last = driven_by(connections, "Boot.COLD"), None
    while at_:
        last, at_ = at_, driven_by(connections, at_[:-len(".INIT")] + ".INITO", ".INIT")
    if last is None:
        raise NotDescribed("the program has no INIT chain from Boot.COLD")
    return last[:-len(".INIT")] + ".INITO"


def fragment(spec: ModuleSpec, names: list[str], tail: str) -> tuple[FlatApplication, list[tuple[str, str]]]:
    """The instances, values and connections of the module level skills ``names`` as the module
    rules build them (the generator's own pattern), and their connections, the first being the
    link from ``tail``, the end of the program's INIT chain."""
    net = ET.Element("SubAppNetwork")
    fb(net, "Tail__", "", 0, 0)
    for i, name in enumerate(names):
        module_skill(net, spec, name, 2000 + i * 5000, 9000)
    chain = ["Tail__", *names]
    wire(net, [(a + ".INITO", z + ".INIT") for a, z in zip(chain, chain[1:])], [])
    flat = flatten(net)
    del flat.fbs["Tail__"]
    links = [(tail if s == "Tail__.INITO" else s, d) for s, d in flat.event_connections + flat.data_connections]
    return flat, links


def amended(boot: str, commands: list[Command]) -> str:
    """The boot file ``boot`` with an online change added, so a restart brings up the changed
    program: what was created, written and connected goes in before the resource is started.
    Starting single instances and firing INIT are left out (a boot does both for everything)."""
    lines = boot.splitlines()
    if not lines or 'Action="START"' not in lines[-1]:
        raise ValueError("not a boot file that ends by starting its resource")
    kept = [c for c in commands if c.op in ("create_fb", "write", "connect") and c.value != "$e"]
    added = [f"{c.resource};{c.xml(i)}" for i, c in enumerate(kept, len(lines))]
    last = lines[-1].replace(f'ID="{len(lines)}"', f'ID="{len(lines) + len(kept)}"')
    return "\n".join([*lines[:-1], *added, last]) + "\n"


def reconfigure(client: Client, host: str, port: int, module: dict, components: list[dict], deployer=None,
                force: bool = False, dry_run: bool = False, resource: str = "RES") -> tuple[list[str], Reading]:
    """Bring the running module to what its AAS describes, online; returns what was done (or would
    be, with ``dry_run``) and the module as read afterwards.

    Refused when a difference needs a restart, when FORTE lacks a block type, or (unless ``force``)
    when values are to be written while the module runs or is occupied. A new skill touches
    nothing that runs and is created in any state. The change is verified by reading the program
    back against the AAS, then added to the module's boot file (``deployer``: where that file is).
    """
    before = read(client, host, port, module, components, resource)
    found = before.differences
    if found.empty:
        return ["the program is what the AAS describes, nothing to do"], before
    if found.restart or found.built:
        raise Refused("not possible online: " + "; ".join((found.restart + found.built)[:10]))
    app, links = fragment(before.spec, found.create, init_tail(before.snapshot.connections)) if found.create \
        else (FlatApplication(), [])
    if missing := lacking(client, app.fbs.values(), before.snapshot.hashes):
        raise Refused(f"FORTE lacks the block types {missing}")
    drift = Drift(missing=list(app.fbs), missing_connections=links, values=found.values)
    commands = online(app, drift, resource)
    done = summary(drift, commands)
    if dry_run:
        return done, before
    if found.values and not force:
        guard(client, before.snapshot)
    for command in commands:
        client.execute(command)
    after = read(client, host, port, module, components, resource)
    lacks = [n for n in app.fbs if n not in after.snapshot.fbs]
    if not after.differences.empty or lacks:
        raise RuntimeError("The module differs from its AAS after the change: "
                           + "; ".join([*after.differences.lines(), *lacks][:10]))
    done.append("verified by reading the program back against the AAS")
    if deployer is not None:
        deployer.save(amended(deployer.load(), commands))
        done.append("added to the boot file")
    else:
        done.append("not in the boot file (no deployer): a FORTE restart loses the change")
    return done, after


# The record of what was built ----------------------------------------------------------------------

def prop(id_short: str, value: str) -> dict:
    return {"idShort": id_short, "modelType": "Property", "valueType": "xs:string", "value": value}


def record(module: dict, reading: Reading, done: list[str] | None = None, trigger: str = "") -> dict:
    """The module's AAS with its Control Configuration saying what runs: every described skill and
    step with its instance, block type and the hash FORTE reports, when it was read, and (with
    ``done``, what a reconfiguration did) one more entry in the change log."""
    module = copy.deepcopy(module)
    config, skills_ = submodel(module, "ControlConfiguration"), submodel(module, "Skills")
    if config is None:
        raise NotDescribed("the module's AAS has no Control Configuration")
    snap, spec = reading.snapshot, reading.spec
    listed = at(config, "Instances")
    if listed is None:
        listed = {"idShort": "Instances", "modelType": "SubmodelElementCollection", "value": []}
        config["submodelElements"].append(listed)
    known = {(at(i, "InstancePath") or {}).get("value"): i for i in children(listed)}

    def note(path: str, keys: list[str]):
        """A skill or step that is built and not recorded yet."""
        if path in known or path not in snap.fbs:
            return
        known[path] = {"idShort": path.replace(".", "_"), "modelType": "SubmodelElementCollection", "value": [
            prop("InstancePath", path),
            {"idShort": "Skill", "modelType": "ReferenceElement", "value": {"type": "ModelReference", "keys": [
                {"type": "Submodel", "value": skills_["id"]},
                *[{"type": "SubmodelElementCollection", "value": k} for k in keys]]}}]}
        listed["value"].append(known[path])

    for name, comp in spec.composites.items():
        note(f"{name}.Control", ["Skills", name])
        for command, branch, steps_ in (("Start", "Execute", comp.execute), ("Stop", "Stop", comp.stop)):
            for k, step in enumerate(steps_):
                note(f"{name}.{branch}.{step.name}", ["Skills", name, command, "Steps", f"Step_{k:04d}"])
    for path, entry in known.items():                     # every recorded instance: what runs there now
        if (typ := snap.fbs.get(path)) is not None:
            entry["value"] = [e for e in entry["value"] if e["idShort"] not in ("FBType", "TypeHash")]
            entry["value"][1:1] = [prop("FBType", typ), *([prop("TypeHash", snap.hashes[typ])] if snap.hashes.get(typ) else [])]
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for id_short, value in (("ReadAt", snap.read_at or now), ("SyncState", "InSync" if reading.differences.empty else "Drift")):
        if (element := at(config, id_short)) is not None:
            element["value"] = value
    if done:
        log = at(config, "ChangeLog")
        if log is None:
            log = {"idShort": "ChangeLog", "modelType": "SubmodelElementList", "orderRelevant": True,
                   "typeValueListElement": "SubmodelElementCollection", "value": []}
            config["submodelElements"].append(log)
        log["value"].append({"modelType": "SubmodelElementCollection", "value": [
            prop("Time", now), prop("Trigger", trigger or "the AAS describes what the program did not have"),
            prop("Result", "; ".join(done))]})
    return module
