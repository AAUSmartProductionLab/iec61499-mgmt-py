"""The structure of a module, read from its program by the module rules (docs/module-rules.md).

A module's program says what the module is made of: its equipment, the skill primitives it has
and offers, its module level skills with their parameters and sequences, and its procedures. The
rules fix how each of these looks in a program, so the structure can be read back from one
without the module spec it may have been generated from:

- what runs (instances, connections and values, as FORTE reports them or a system file states
  them) gives the equipment, the offered primitives, the module level skills and the procedures;
- what a skill primitive is (its type file) gives its parameters, results and equipment. A
  primitive the module does not offer has no instance, so only its type tells of it.

``structure`` reads it, ``stated`` gives the same of a module spec. Both return the dictionary
below, with numbers as numbers and durations in milliseconds, so the two compare with ``==``::

    module, package, opcua_root
    equipment:  [item]
    skills:     {skill: offered, equipment, parameters {p: type, default, minimum, maximum},
                 results [r], timeout}
    composites: {skill: offered, parameters, execute [step], stop [step], results {r: step.result}}
    procedures: {name: [step]}
    step:       skill, name, bind {parameter: constant or the composite's parameter}

A step's ``bind`` holds every parameter of its skill: what a running program reports does not
tell a constant that was bound from a default that was left.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from defusedxml.ElementTree import parse

from modgen.library import PARAM_RANGE, q
from modgen.module import tlit
from modgen.spec import ModuleSpec, Parameter

from .device import literal

CORE = q("SKILL_Core")
LATCH = q("SKILL_Param_")
# The inputs every skill primitive has (rule 2.3); its other inputs are its parameters.
STANDARD = ("Module", "UaRoot", "UaPath", "UaEnable", "Methods", "Token", "LastUse", "Timeout")
PROCEDURES = ("Resetting", "Stopping")


def bound(value: str | None, typ: str, which: int):
    """A limit as declared; the limit of the type itself (what an undeclared one reads as) is none."""
    limits = PARAM_RANGE.get(typ)
    if value is None or (limits and literal(value) == literal(limits[which])):
        return None
    return literal(value)


def declared(typ: str, default: str | None, lower: str | None, upper: str | None) -> dict:
    """A parameter as the structure holds it."""
    return {"type": typ, "default": literal(default), "minimum": bound(lower, typ, 0), "maximum": bound(upper, typ, 1)}


def read_primitives(folder: str | Path) -> dict[str, dict]:
    """The skill primitive types (``SK_<Skill>.fbt``) below a type library folder, by skill: the
    package, and what rule 2 lets a type tell: equipment, parameters, results and timeout."""
    found = {}
    for path in sorted(Path(folder).rglob("SK_*.fbt")):
        root = parse(str(path)).getroot()
        info = root.find("CompilerInfo")
        written = {(fb.get("Name"), p.get("Name")): p.get("Value")
                   for fb in root.findall("FBNetwork/FB") for p in fb.findall("Parameter")}
        inputs = {v.get("Name"): v for v in root.findall("InterfaceList/InputVars/VarDeclaration")}
        outputs = [v.get("Name") for v in root.findall("InterfaceList/OutputVars/VarDeclaration")]
        timeout = inputs["Timeout"].get("InitialValue") if "Timeout" in inputs else None
        found[root.get("Name")[len("SK_"):]] = {
            "package": info.get("packageName") if info is not None else "",
            "equipment": literal(written.get(("Logic", "Equipment"))),
            "parameters": {n: declared(v.get("Type"), v.get("InitialValue"), written.get((f"Par_{n}", "Lower")),
                                       written.get((f"Par_{n}", "Upper")))
                           for n, v in inputs.items() if n not in STANDARD},
            "results": [n[len("R_"):] for n in outputs if n.startswith("R_")],
            "timeout": literal(timeout)[1] if timeout else None,
        }
    return found


def structure(fbs: dict[str, str], connections, value: Callable[[str], str | None],
              primitives: dict[str, dict]) -> dict:
    """The structure of the program with the instances ``fbs`` (name -> type), the ``connections``
    (source, destination) and the input values ``value(port)`` gives (None: not written).
    ``primitives`` are its skill primitive types (``read_primitives``)."""
    package = next(t.partition("::")[0] for t in fbs.values() if "::EQ_" in t or "::SK_" in t)
    primitive = f"{package}::SK_"
    driven = {d: s for s, d in connections}

    # Rule 1.5: one INIT chain from the boot event; it gives the order things were declared in.
    order, at = [], driven_by(connections, "Boot.COLD")
    while at:
        top = at.partition(".")[0]
        if top not in order:
            order.append(top)
        at = driven_by(connections, at[:-len(".INIT")] + ".INITO", ".INIT")

    def steps(prefix: str) -> list[dict]:
        """The steps of the sequence ``prefix``, in the order their SUCCESS starts the next."""
        depth = prefix.count(".") + 1
        names = [n for n, t in fbs.items() if n.startswith(prefix + ".") and n.count(".") == depth and t.startswith(primitive)]
        follows = {s[:-len(".SUCCESS")]: d[:-len(".START")] for s, d in connections
                   if s.endswith(".SUCCESS") and d.endswith(".START") and s in {n + ".SUCCESS" for n in names}}
        found = [n for n in names if n not in follows.values()][:1]
        while found and found[-1] in follows:
            found.append(follows[found[-1]])
        result = []
        for name in found:
            skill = fbs[name][len(primitive):]
            bind = {}
            for p, decl in primitives[skill]["parameters"].items():
                source = driven.get(f"{name}.{p}")
                # Rule 3: a parameter of the skill reaches a step from its latch's P.
                bind[p] = source.split(".")[-2] if source else (
                    decl["default"] if value(f"{name}.{p}") is None else literal(value(f"{name}.{p}")))
            result.append({"skill": skill, "name": name.rpartition(".")[2], "bind": bind})
        return result

    composites = {}
    for name in [n for n in order if fbs.get(f"{n}.Control") == CORE]:
        # Rule 3: the Start method hands argument k + 1 to the latch of parameter k.
        latches = sorted((int(s.rpartition("_")[2]), d.split(".")[-2]) for s, d in connections
                         if s.startswith(f"{name}.UaStart.RD_") and d.endswith(".S"))
        parameters = {p: declared(fbs[f"{name}.{p}"][len(LATCH):], value(f"{name}.{p}.Default"),
                                  value(f"{name}.{p}.Lower"), value(f"{name}.{p}.Upper")) for _, p in latches}
        # The results are published in the order the ID names them.
        published = [path.rpartition("/")[2] for path in (literal(value(f"{name}.PubResults.ID")) or "").strip("]").split(";")[1:]]
        results = {published[int(d.rpartition("_")[2]) - 1]: ".".join(s.split(".")[-2:]).replace(".R_", ".")
                   for s, d in connections if d.startswith(f"{name}.PubResults.SD_")}
        composites[name] = {"offered": literal(value(f"{name}.Control.Methods")) is True, "parameters": parameters,
                            "execute": steps(f"{name}.Execute"), "stop": steps(f"{name}.Stop"),
                            "results": {r: results[r] for r in published}}

    offered = [n for n in order if fbs.get(n) == f"{primitive}{n}"]
    return {
        "module": literal(value("Occupation.Module")), "package": package,
        "opcua_root": literal(value("Occupation.UaRoot")),
        "equipment": [n for n in order if fbs.get(n) == f"{package}::EQ_{n}"],
        "skills": {n: {"offered": n in offered, **{k: v for k, v in p.items() if k != "package"}}
                   for n, p in primitives.items() if p["package"] == package},
        "composites": composites,
        "procedures": {n: steps(n) for n in order if n in PROCEDURES and n not in composites},
    }


def driven_by(connections, source: str, ending: str = "") -> str | None:
    """The destination ``source`` is connected to (the one with ``ending``)."""
    return next((d for s, d in connections if s == source and d.endswith(ending)), None)


def stated(spec: ModuleSpec) -> dict:
    """The structure a module spec states, as ``structure`` reads it from the program it generates."""
    def parameters(declared_: dict[str, Parameter]) -> dict:
        return {n: declared(p.type, p.literal(), None if p.minimum is None else p.literal(p.minimum),
                            None if p.maximum is None else p.literal(p.maximum)) for n, p in declared_.items()}

    def steps(sequence) -> list[dict]:
        result = []
        for step in sequence:
            typ = spec.skills[step.skill].parameters
            result.append({"skill": step.skill, "name": step.name, "bind": {
                p: step.bind[p] if isinstance(step.bind.get(p), str) else literal(decl.literal(step.bind.get(p)))
                for p, decl in typ.items()}})
        return result

    return {
        "module": spec.module, "package": spec.package, "opcua_root": spec.opcua_root,
        "equipment": list(spec.equipment),
        "skills": {n: {"offered": s.offered, "equipment": s.equipment, "parameters": parameters(s.parameters),
                       "results": list(s.results),
                       "timeout": literal(tlit(s.timeout))[1] if s.ensures is not None else None}
                   for n, s in spec.skills.items()},
        "composites": {n: {"offered": c.offered, "parameters": parameters(c.parameters), "execute": steps(c.execute),
                           "stop": steps(c.stop), "results": dict(c.results)} for n, c in spec.composites.items()},
        "procedures": {n: steps(s) for n, s in spec.procedures.items()},
    }
