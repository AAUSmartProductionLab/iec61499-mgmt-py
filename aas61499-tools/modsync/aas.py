"""The asset administration shell of a module: from its module spec and, when read, what runs on it.

Follows the lab's conventions (AP2030-UNS Registration Service): ids below
https://smartproductionlab.aau.dk, submodel ids ``<base>/submodels/instances/<idShort>/<Submodel>``,
the same submodel idShorts and semantic ids. The Registration Service only knows MQTT interfaces
(``InterfaceMQTT``), so the shell is built here, with an ``InterfaceOPCUA`` in the Asset Interfaces
Description whose forms point at OPC UA browse paths.

Submodels:
- ``Skills``: one collection per skill the orchestrator can start (skill primitives and module
  level skills): an Operation (the OPC UA Start method), its parameters with their current values,
  contract or sequence, occupied equipment, and the implementing FB type with its hash.
- ``AssetInterfacesDescription``: the OPC UA endpoint, every method as an action and every
  published variable as a property.
- ``Variables``: PackML state, occupation and the equipment's sensors, referencing the interface.
- ``ControlSoftware``: which module spec and target the running program was generated from, whether
  it still matches (drift), and the type hashes the runtime reports.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path
import urllib.error
import urllib.request

from basyx.aas import model
from basyx.aas.adapter.json import AASToJsonEncoder, write_aas_json_file

from modgen.module import parameter_port, result_type
from modgen.spec import ModuleSpec, Parameter

from .compare import Drift
from .device import Snapshot, literal

BASE = "https://smartproductionlab.aau.dk"
SEM = {
    "Skills": "https://smartfactory.de/aas/submodel/Skills#1/0",
    "AssetInterfacesDescription": "https://admin-shell.io/idta/AssetInterfacesDescription/1/0/Submodel",
    "Interface": "https://admin-shell.io/idta/AssetInterfacesDescription/1/0/Interface",
    "InteractionMetadata": "https://admin-shell.io/idta/AssetInterfacesDescription/1/0/InteractionMetadata",
    "InterfaceReference": "https://admin-shell.io/idta/AssetInterfacesDescription/1/0/InterfaceReference",
    "Variables": "https://admin-shell.io/idta/Variables/1/0/Submodel",
    "ControlSoftware": f"{BASE}/submodels/ControlSoftware/1/0",
    "WoT": "https://www.w3.org/2019/wot/td",
    "Action": "https://www.w3.org/2019/wot/td#ActionAffordance",
    "Property": "https://www.w3.org/2019/wot/td#PropertyAffordance",
    "InteractionAffordance": "https://www.w3.org/2019/wot/td#InteractionAffordance",
    "OPCUA": "http://opcfoundation.org/UA/",
    "PackMLState": "https://www.omac.org/packml/state",
    "Occupation": f"{BASE}/stationOccupation",
}
XSD = {"BOOL": model.datatypes.Boolean, "LREAL": model.datatypes.Double, "INT": model.datatypes.Short,
       "DINT": model.datatypes.Int, "UINT": model.datatypes.UnsignedShort, "UDINT": model.datatypes.UnsignedInt,
       "USINT": model.datatypes.UnsignedByte}
# OPC UA data types of the published variables (as FORTE maps the IEC types).
UA_TYPE = {"BOOL": "Boolean", "LREAL": "Double", "USINT": "Byte", "UINT": "UInt16", "WSTRING": "String"}
SKILL_METHODS = ["Start", "Stop", "Abort", "Reset"]
MODULE_METHODS = ["Reset", "Start", "Stop", "Abort", "Clear"]


def ref(semantic: str) -> model.ExternalReference:
    return model.ExternalReference((model.Key(model.KeyTypes.GLOBAL_REFERENCE, semantic),))


def text(value: str) -> model.MultiLanguageTextType:
    return model.MultiLanguageTextType({"en": value})


def prop(id_short: str, value, value_type=model.datatypes.String, semantic: str | None = None,
         description: str | None = None, qualifiers=()) -> model.Property:
    return model.Property(id_short, value_type, value, semantic_id=ref(semantic) if semantic else None,
                          description=text(description) if description else None, qualifier=qualifiers)


def smc(id_short: str, elements, semantic: str | None = None, description: str | None = None,
        supplemental=()) -> model.SubmodelElementCollection:
    return model.SubmodelElementCollection(
        id_short, [e for e in elements if e is not None], semantic_id=ref(semantic) if semantic else None,
        description=text(description) if description else None,
        supplemental_semantic_id=[ref(s) for s in supplemental])


def identity(spec: ModuleSpec) -> tuple[str, str, str]:
    """(idShort, id, globalAssetId) of the module's shell."""
    id_short = spec.aas.id_short or f"{spec.module}ModuleAAS"
    return (id_short, spec.aas.id or f"{BASE}/aas/{id_short}",
            spec.aas.global_asset_id or f"{BASE}/assets/{spec.module}Module")


def submodel_id(id_short: str, name: str) -> str:
    return f"{BASE}/submodels/instances/{id_short}/{name}"


def browse_path(spec: ModuleSpec, path: str) -> str:
    """OPC UA RelativePath text of a node below the module's root (FORTE's nodes are in namespace 1)."""
    parts = [p for p in spec.opcua_root.split("/") if p][1:] + [p for p in path.split("/") if p]
    return "/0:Objects" + "".join(f"/1:{p}" for p in parts)


def current(port: str, pr: Parameter, snap: Snapshot | None):
    """The parameter's value on the module if it was read, else the spec's default."""
    read = snap.values.get(port) if snap else None
    value = pr.default if read is None else literal(read)
    return bool(value) if pr.type == "BOOL" else float(value) if pr.type == "LREAL" else int(value)


def parameter(name: str, pr: Parameter, value) -> model.Property:
    q = [model.Qualifier(k, model.datatypes.String, str(v)) for k, v in
         (("Unit", pr.unit), ("Minimum", pr.minimum), ("Maximum", pr.maximum), ("Default", pr.default)) if v is not None]
    return prop(name, value, XSD[pr.type], description=pr.description or None, qualifiers=q)


class Builder:
    """Collects the interface affordances while the skills are described, then builds the shell."""

    def __init__(self, spec: ModuleSpec, target: str, snap: Snapshot | None, drift: Drift | None,
                 spec_path: str | None, opcua: str | None):
        self.spec, self.target, self.snap, self.drift = spec, target, snap, drift
        self.spec_path = spec_path
        self.opcua = opcua or f"opc.tcp://{spec.targets[target].host}:4840"
        self.id_short, self.aas_id, self.asset_id = identity(spec)
        self.aid_id = submodel_id(self.id_short, "AssetInterfacesDescription")
        self.actions: list[model.SubmodelElementCollection] = []
        self.properties: list[model.SubmodelElementCollection] = []

    # Interface affordances -------------------------------------------------------------------

    def interface_ref(self, kind: str, key: str) -> model.ModelReference:
        """Reference to an action or property of the OPC UA interface."""
        keys = [model.Key(model.KeyTypes.SUBMODEL, self.aid_id)]
        keys += [model.Key(model.KeyTypes.SUBMODEL_ELEMENT_COLLECTION, k)
                 for k in ("InterfaceOPCUA", "InteractionMetadata", kind, key)]
        return model.ModelReference(tuple(keys), model.SubmodelElementCollection)

    def action(self, key: str, path: str, title: str, inputs: list[tuple[str, str]]) -> str:
        forms = smc("Forms", [prop("href", browse_path(self.spec, path)), prop("op", "invokeAction")])
        self.actions.append(smc(key, [
            prop("Key", key), prop("Title", title), prop("Synchronous", True, model.datatypes.Boolean),
            prop("input", "; ".join(f"{n}: {t}" for n, t in [("Session", "String"), *inputs])),
            prop("output", "Accepted: Boolean; ErrorID: UInt16"), forms]))
        return key

    def variable(self, key: str, path: str, iec: str, title: str) -> str:
        forms = smc("Forms", [prop("href", browse_path(self.spec, path)), prop("op", "readproperty observeproperty")])
        self.properties.append(smc(key, [prop("Key", key), prop("Title", title), prop("type", UA_TYPE[iec]), forms]))
        return key

    # Skills ----------------------------------------------------------------------------------

    def implementation(self, instance: str) -> model.SubmodelElementCollection:
        typ = self.snap.fbs.get(instance) if self.snap else None
        return smc("Implementation", [
            prop("InstancePath", instance),
            prop("FBType", typ or "(not read)"),
            prop("TypeHash", self.snap.hashes.get(typ, "")) if typ else None])

    def steps(self, name: str, owner: str, steps) -> model.SubmodelElementCollection:
        """A sequence with each step's constant bindings as running on the module."""
        items = []
        for i, step in enumerate(steps, 1):
            skill = self.spec.skills[step.skill]
            binds = []
            for pname, v in step.bind.items():
                if isinstance(v, str):
                    binds.append(f"{pname}={v}")
                else:
                    value = current(f"{owner}.{step.name}.{pname}", skill.parameters[pname], self.snap)
                    binds.append(f"{pname}={value}")
            items.append(prop(f"Step{i:02d}", f"{step.skill}({', '.join(binds)})" if binds else step.skill,
                              description=f"instance {owner}.{step.name}"))
        return smc(name, items)

    def skill(self, name: str) -> model.SubmodelElementCollection:
        spec = self.spec
        composite = name in spec.composites
        decl = spec.composites[name] if composite else spec.skills[name]
        instance = f"{name}.Control" if composite else name
        values = {p: current(parameter_port(spec, name, p), pr, self.snap) for p, pr in decl.parameters.items()}
        params = [parameter(p, pr, values[p]) for p, pr in decl.parameters.items()]
        start = self.action(f"{name}_Start", f"/Skills/{name}/Start", f"Start {name}",
                            [(p, "Double") for p in decl.parameters])
        for method in SKILL_METHODS[1:]:
            self.action(f"{name}_{method}", f"/Skills/{name}/{method}", f"{method} {name}", [])
        state = self.variable(f"{name}_State", f"/Skills/{name}/State", "USINT",
                              f"{name} state: 0 Idle, 1 Running, 2 Stopping, 3 Succeeded, 4 Failed, 5 Aborted")
        self.variable(f"{name}_ErrorID", f"/Skills/{name}/ErrorID", "UINT", f"{name} error: 0 none, 1 "
                      "PreconditionViolated, 2 InvariantViolated, 3 Timeout, 4 NotReady, 5 NotPermitted, 6 Busy, "
                      "7 Interrupted, 8 OutOfRange")
        results = []
        for r in decl.results:
            iec = self.result_type(name, r)
            key = self.variable(f"{name}_Result_{r}", f"/Skills/{name}/Results/{r}", iec, f"{name} result {r}")
            results.append(model.ReferenceElement(r, self.interface_ref("properties", key)))
        operation = model.Operation(
            name,
            input_variable=[prop("Session", "", description="Occupation session of the caller"),
                            *[parameter(p, pr, values[p]) for p, pr in decl.parameters.items()]],
            output_variable=[prop("Accepted", False, model.datatypes.Boolean),
                             prop("ErrorID", 0, model.datatypes.UnsignedShort)],
            semantic_id=ref(f"{BASE}/skills/{name}"),
            description=text(f"Start {name}; completion is reported by its State"))
        if composite:
            behaviour = [self.steps("Execute", f"{name}.Execute", decl.execute),
                         self.steps("Stop", f"{name}.Stop", decl.stop) if decl.stop else None]
        else:
            ends = {"Ensures": decl.ensures} if decl.ensures is not None else {"After": str(decl.after)}
            behaviour = [smc("Contract", [prop(k, v) for k, v in
                                          {"Requires": decl.requires, **ends, "Invariant": decl.invariant,
                                           "Timeout": decl.timeout}.items()])]
        return smc(name, [
            operation,
            model.ReferenceElement("InterfaceReference", self.interface_ref("actions", start),
                                   semantic_id=ref(SEM["InterfaceReference"])),
            model.ReferenceElement("StateReference", self.interface_ref("properties", state)),
            prop("Kind", "ModuleLevelSkill" if composite else "SkillPrimitive"),
            smc("Parameters", params) if params else None,
            smc("Results", results) if results else None,
            *behaviour,
            prop("Occupies", ", ".join(spec.uses(name))),
            self.implementation(instance)],
            description=decl.description or None)

    def result_type(self, name: str, result: str) -> str:
        spec = self.spec
        if name in spec.skills:
            skill = spec.skills[name]
            return spec.equipment[skill.equipment].inputs[skill.results[result]].type
        comp = spec.composites[name]
        return result_type(spec, comp.execute, comp.results[result])

    # Submodels -------------------------------------------------------------------------------

    def build(self) -> model.DictObjectStore:
        spec = self.spec
        # Module level first, so the interface lists it first.
        self.action("Occupation_Occupy", "/Occupation/Occupy", "Occupy the module", [])
        self.action("Occupation_Release", "/Occupation/Release", "Release the module", [])
        occupied = self.variable("Occupation_Occupied", "/Occupation/Occupied", "BOOL", "Occupied")
        for m in MODULE_METHODS:
            self.action(f"Module_{m}", f"/Module/{m}", f"Module {m}", [])
        state = self.variable("Module_State", "/Module/State", "USINT", "PackML state: 1 Clearing, 2 Stopped, "
                              "3 Starting, 4 Idle, 6 Execute, 7 Stopping, 8 Aborting, 9 Aborted, 15 Resetting")
        offered = [n for n, s in spec.skills.items() if s.offered] + [n for n, c in spec.composites.items() if c.offered]
        skills = [self.skill(n) for n in offered]
        variables = [smc("PackMLState", [model.ReferenceElement("InterfaceReference", self.interface_ref("properties", state))],
                         SEM["PackMLState"]),
                     smc("OccupationState", [model.ReferenceElement("InterfaceReference",
                                                                    self.interface_ref("properties", occupied))],
                         SEM["Occupation"])]
        for item, eq in spec.equipment.items():
            for s, io in eq.inputs.items():
                key = self.variable(f"Equipment_{item}_{s}", f"/Equipment/{item}/{s}", io.type, f"{item} {s}")
                variables.append(smc(f"{item}_{s}", [
                    prop("Unit", io.unit) if io.unit else None,
                    model.ReferenceElement("InterfaceReference", self.interface_ref("properties", key))],
                    f"{BASE}/variables/{item}/{s}", eq.description or None))
        interface = smc("InterfaceOPCUA", [
            prop("title", f"{spec.module} module"),
            smc("EndpointMetadata", [prop("base", self.opcua)]),
            smc("InteractionMetadata", [smc("actions", self.actions, SEM["Action"]),
                                        smc("properties", self.properties, SEM["Property"])],
                SEM["InteractionMetadata"], supplemental=[SEM["InteractionAffordance"]])],
            SEM["Interface"], supplemental=[SEM["OPCUA"], SEM["WoT"]])
        submodels = [
            self.submodel("Skills", skills),
            model.Submodel(self.aid_id, [interface], id_short="AssetInterfacesDescription",
                           semantic_id=ref(SEM["AssetInterfacesDescription"])),
            self.submodel("Variables", variables),
            self.submodel("ControlSoftware", self.control_software()),
        ]
        shell = model.AssetAdministrationShell(
            model.AssetInformation(model.AssetKind.INSTANCE, global_asset_id=self.asset_id,
                                   asset_type=spec.aas.asset_type,
                                   specific_asset_id=[model.SpecificAssetId(k, v) for k, v in
                                                      (("SerialNumber", spec.aas.serial_number),
                                                       ("Location", spec.aas.location)) if v]),
            self.aas_id, id_short=self.id_short,
            submodel={model.ModelReference.from_referable(s) for s in submodels})
        return model.DictObjectStore([shell, *submodels])

    def submodel(self, name: str, elements) -> model.Submodel:
        return model.Submodel(submodel_id(self.id_short, name), elements, id_short=name,
                              semantic_id=ref(SEM[name]))

    def control_software(self):
        snap, drift = self.snap, self.drift
        if snap is None:
            sync = "NotRead"
        elif snap.empty:
            sync = "NoProgram"
        else:
            sync = "InSync" if drift is not None and drift.empty else "Drift"
        lines = drift.lines() if drift else []
        t = self.spec.targets[self.target]
        types = sorted(set(snap.fbs.values())) if snap else []
        return [
            prop("Runtime", "Eclipse 4diac FORTE"),
            prop("ManagementEndpoint", f"{snap.host}:{snap.port}" if snap else f"{t.host}:{t.port}"),
            prop("Resource", snap.resource if snap else "RES"),
            prop("ModuleSpec", self.spec_path or ""),
            prop("Target", self.target),
            prop("Generator", "modgen"),
            prop("SyncState", sync, description="InSync: the running program is the one the module spec generates; "
                 "Drift: it differs (see Differences); NoProgram: FORTE runs without one; NotRead: from the spec only"),
            prop("ReadAt", snap.read_at if snap else ""),
            prop("InstanceCount", len(snap.fbs) if snap else 0, model.datatypes.Int),
            smc("Differences", [prop(f"D{i:03d}", line) for i, line in enumerate(lines[:100], 1)]),
            smc("Types", [smc(f"T{i:03d}", [prop("Name", typ), prop("Hash", snap.hashes.get(typ, ""))])
                          for i, typ in enumerate(types, 1)]),
        ]


def build(spec: ModuleSpec, target: str, snap: Snapshot | None = None, drift: Drift | None = None,
          spec_path: str | None = None, opcua: str | None = None) -> model.DictObjectStore:
    """The module's shell and submodels; with a snapshot, values and hashes are the running ones."""
    return Builder(spec, target, snap, drift, spec_path, opcua).build()


def write(store: model.DictObjectStore, path: Path) -> Path:
    """Write the shell and submodels as an AAS JSON environment."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        write_aas_json_file(f, store, indent=2)
    return path


def b64(identifier: str) -> str:
    """Identifier as the AAS HTTP API expects it in a path (base64url, no padding)."""
    return base64.urlsafe_b64encode(identifier.encode()).decode().rstrip("=")


def upload(store: model.DictObjectStore, url: str, timeout: float = 10) -> list[str]:
    """Create or replace the shell and submodels on an AAS server (BaSyx AAS environment, API v3)."""
    done = []
    for obj in store:
        kind = "shells" if isinstance(obj, model.AssetAdministrationShell) else "submodels"
        body = json.dumps(obj, cls=AASToJsonEncoder).encode()
        for method, target in (("PUT", f"{url.rstrip('/')}/{kind}/{b64(obj.id)}"), ("POST", f"{url.rstrip('/')}/{kind}")):
            request = urllib.request.Request(target, body, method=method, headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(request, timeout=timeout):
                    done.append(f"{method} {kind} {obj.id}")
                    break
            except urllib.error.HTTPError as e:
                if not (method == "PUT" and e.code == 404):
                    raise RuntimeError(f"{method} {target}: HTTP {e.code} {e.read()[:300]!r}") from e
    return done
