"""A module's AAS in the structure of the resource ontology (ARSO), from its module spec and, when
read, what runs on it.

``describe`` fills a ``ModuleTypeAAS``; ``model.profile`` turns it into the profile the module carries
and registers with (its manifest), ``model.environment`` into the AAS.

- **Asset Interfaces Description**: the OPC UA server; every method as an action (browse path,
  arguments in call order) and every published variable as a property.
- **Skills**: Occupy, Release and every skill the module offers, each with its SemanticId, its
  Operation (the parameters as inputs) and the reference to its Start action; and its kind,
  parameters, contract or sequences, occupied equipment, state reference and implementing function
  block. A primitive that is not offered only runs as a step of a module level skill: it is not
  listed, the steps name it. Every step refers to the State it publishes (with its ErrorID,
  parameters and results beside it). The procedures the module runs while Resetting and Stopping
  are sequences of steps as well.
- **Operational Data** with the mapping that feeds it (Asset Interfaces Mapping Configuration):
  module state, occupation, skill and step states and results, equipment inputs, as decimal data
  points.
- **Parameters**: the value of every skill parameter as deployed (none: no submodel).
- **Hierarchical Structures**: the equipment as parts of the module.
- **Control Configuration**: spec, target and program digest; from a module that was read also the
  synchronisation state, the differences and the type hashes.
"""
from __future__ import annotations

import hashlib
import json

from aas_model.constants import AID_SYNCHRONOUS, BASE_URL
from aas_model.json_schema_aid import datapoint_from_schema
from aas_model.resource_template import nameplate, skill_operation
from aas_model.resource_template._helpers import put
from aas_model.resource_template.asset_interfaces_mapping_configuration import mapping_configuration, sink, source
from aas_model.submodel_templates import (
    Aimc, AimcMappingConfigurations, DmpActionInput, DmpActionOutput, OpcuaAction, OpcuaProperty, OperationVariableProp,
)
from aas_pydantic import (
    Capability, ExternalReference, Key, ModelReference, Property, Qualifier, ReferenceElement, RelationshipElement,
)
from aas_pydantic.submodel_templates import asset_interfaces_description as wot
from aas_pydantic.submodel_templates import capability_description as cd
from aas_pydantic.submodel_templates.hierarchical_structures import ArcheType, EntryNode, HierarchicalStructures, Node
from aas_pydantic.submodel_templates.nameplate import ManufacturerProductDesignation, SerialNumber

from modgen.module import parameter_port
from modgen.spec import ModuleSpec, Parameter
from modsync.aas import MODULE_METHODS, SKILL_METHODS, browse_path, current, identity
from modsync.compare import Drift, expected, expected_values
from modsync.device import Snapshot

from . import model
from .generated import control_configuration as cc, skills as arso
from .generated.operational_data import OperationalData
from .generated.parameters import ParameterEntry, Parameters
from .model import ModuleSkill, ModuleTypeAAS

AID = "{aas_id}/submodels/AssetInterfacesDescription"
SKILLS = "{aas_id}/submodels/Skills"
STRUCTURE = "{aas_id}/submodels/HierarchicalStructures"
DATA = "{aas_id}/submodels/OperationalData"
CAPABILITIES = "{aas_id}/submodels/CapabilityDescription"
# IDTA 02020: the Capability element and its role qualifier.
CAPABILITY = "https://admin-shell.io/idta/CapabilityDescription/Capability/1/0"
OFFERED = "https://admin-shell.io/idta/CapabilityDescription/CapabilityRoleQualifier/Offered/1/0"
OFFERED_SET = "OfferedCapabilities"
SMC = "SubmodelElementCollection"
XSD = {"BOOL": "xs:boolean", "LREAL": "xs:double", "INT": "xs:short", "DINT": "xs:int", "UINT": "xs:unsignedShort",
       "UDINT": "xs:unsignedInt", "USINT": "xs:unsignedByte", "WSTRING": "xs:string"}
JSON = {"BOOL": "boolean", "LREAL": "number", "WSTRING": "string"}       # everything else is an integer
SKILL_STATES = "0 Idle, 1 Running, 2 Stopping, 3 Succeeded, 4 Failed, 5 Aborted"
MODULE_STATES = "1 Clearing, 2 Stopped, 3 Starting, 4 Idle, 6 Execute, 7 Stopping, 8 Aborting, 9 Aborted, 15 Resetting"
ERROR_CODES = {"PreconditionViolated": 1, "InvariantViolated": 2, "Timeout": 3, "NotReady": 4, "NotPermitted": 5,
               "Busy": 6, "Interrupted": 7, "OutOfRange": 8}
ERRORS = "0 none, " + ", ".join(f"{code} {name}" for name, code in ERROR_CODES.items())
ANSWER = {"type": "object", "properties": {"Accepted": {"type": "boolean"},
                                            "ErrorID": {"type": "integer", "minimum": 0, "maximum": 65535}}}
# The concepts of the two values every resource of the lab has.
MODULE_STATE = "https://w3id.org/2026/apex/semantic/state/operational"
OCCUPIED = "https://w3id.org/2026/apex/semantic/state/occupied"


def text(value) -> str:
    """A value as the AAS writes it."""
    return str(value).lower() if isinstance(value, bool) else str(value)


def prop(value, value_type: str = "xs:string", description: str = "") -> Property:
    return Property(value=text(value), value_type=value_type, description=description)


def path(submodel: str, *steps: tuple[str, str]) -> ModelReference:
    return ModelReference(key=(Key(type_="Submodel", value=submodel), *(Key(type_=t, value=v) for t, v in steps)))


def affordance(kind: str, key: str) -> ModelReference:
    """An action or a property of the OPC UA interface."""
    return path(AID, (SMC, "interface_opcua"), (SMC, "InteractionMetadata"), (SMC, kind), (SMC, key))


def skill_id(name: str) -> str:
    return f"{model.SKILL}/{name}"


def meaning(name: str, given: str | None = None) -> str:
    """What a capability or capability property means: the spec's IRI, else the lab's."""
    return given or f"{BASE_URL}/semantics/{name}"


def capability_path(name: str) -> ModelReference:
    return path(CAPABILITIES, (SMC, OFFERED_SET), (SMC, name), ("Capability", "Capability"))


def schema(parameters: dict[str, Parameter]) -> dict:
    """The arguments of a method as a JSON Schema object, in call order (the session first)."""
    fields = {"Session": {"type": "string", "title": "Occupation session of the caller"}}
    for name, pr in parameters.items():
        field = {"type": "number", "title": pr.description or name, "default": pr.default}
        field.update({k: v for k, v in (("minimum", pr.minimum), ("maximum", pr.maximum)) if v is not None})
        fields[name] = field
    return {"type": "object", "properties": fields}


def result_input(spec: ModuleSpec, skill: str, result: str):
    """The equipment input behind a skill's result (its type and unit); a composite's result is
    the result of one of its execute steps."""
    if skill in spec.composites:
        step_name, _, inner = spec.composites[skill].results[result].partition(".")
        step = next(s for s in spec.composites[skill].execute if s.name == step_name)
        return result_input(spec, step.skill, inner)
    decl = spec.skills[skill]
    return spec.equipment[decl.equipment].inputs[decl.results[result]]


def program_digest(spec: ModuleSpec, target: str) -> str:
    """SHA-256 of the program the spec generates for the target: instances with their types,
    connections and input values."""
    app = expected(spec, target)
    program = {"instances": sorted(app.fbs.items()),
               "connections": sorted([*app.event_connections, *app.data_connections]),
               "values": sorted(expected_values(spec, app).items())}
    return hashlib.sha256(json.dumps(program, separators=(",", ":")).encode()).hexdigest()


class Describer:
    """Collects the interface while the skills and data points are described, then builds the model."""

    def __init__(self, spec: ModuleSpec, target: str, snap: Snapshot | None, drift: Drift | None,
                 spec_path: str | None, opcua: str | None):
        self.spec, self.target, self.snap, self.drift, self.spec_path = spec, target, snap, drift, spec_path
        self.opcua = opcua or f"opc.tcp://{spec.targets[target].host}:4840"
        self.actions: dict[str, OpcuaAction] = {}
        self.properties: dict[str, OpcuaProperty] = {}
        self.datapoints: dict[str, tuple[str, str, str]] = {}    # data point -> (interface property, concept, title)
        self.operations: dict[str, tuple[str, list[str]]] = {}    # skill -> (interface action, arguments)
        # The skills the AAS lists: those with an interface of their own.
        self.listed = [n for n, s in [*spec.skills.items(), *spec.composites.items()] if s.offered]

    # Interface -------------------------------------------------------------------------------

    def action(self, key: str, node: str, title: str, parameters: dict[str, Parameter] | None = None) -> str:
        href = browse_path(self.spec, node)
        action = OpcuaAction()
        action.title = wot.Title(value=title)
        # The call answers at once with Accepted and ErrorID; the skill's progress is its State.
        action.synchronous = Property(semantic_id=AID_SYNCHRONOUS, value="true")
        action.input = datapoint_from_schema(schema(parameters or {}), cls=DmpActionInput)
        action.output = datapoint_from_schema(ANSWER, cls=DmpActionOutput)
        action.forms.href.value = href
        action.forms.op.value = "invokeaction"
        action.forms.uav_browsePath = wot.UavBrowsePath(value=href)
        # FORTE gives its nodes new numeric ids at every start, so the owning object is named by
        # its browse path as well.
        action.forms.uav_componentOf.value = href.rpartition("/")[0]
        self.actions[key] = action
        return key

    def property(self, key: str, node: str, iec: str, title: str, unit: str | None = None) -> str:
        href = browse_path(self.spec, node)
        p = OpcuaProperty()
        p.key = wot.Key(value=key)
        p.title = wot.Title(value=title)
        p.type = wot.Type(value=JSON.get(iec, "integer"))
        p.observable = wot.Observable(value="true")
        if unit:
            p.unit = wot.Unit(value=unit)
        p.forms.href.value = href
        p.forms.op.value = "observeproperty"
        p.forms.uav_browsePath = wot.UavBrowsePath(value=href)
        self.properties[key] = p
        return key

    def observe(self, name: str, key: str, concept: str, title: str):
        """A data point of the AAS fed from a property of the interface."""
        self.datapoints[name] = (key, concept, title)

    # Skills ----------------------------------------------------------------------------------

    def skill_reference(self, name: str, id_short: str = "Skill") -> ReferenceElement:
        """A skill of this submodel; one that only runs as a step is named, not listed."""
        if name in self.listed:
            return ReferenceElement(id_short=id_short, value=path(SKILLS, (SMC, "Skills"), (SMC, name)))
        named = ExternalReference(key=(Key(type_="GlobalReference", value=skill_id(name)),))
        return ReferenceElement(id_short=id_short, value=named)

    def entry(self, name: str, action: str, parameters: dict[str, Parameter], description: str) -> ModuleSkill:
        """What ARSO asks of every skill: SemanticId, Operation and the reference to its action."""
        def var(id_short, value_type, about):
            return OperationVariableProp(id_short=id_short, value_type=value_type, description=about)

        op = skill_operation(name, synchronous=True)
        op.semantic_id = skill_id(name)
        op.description = f"Start {name}; the answer says whether it was accepted, its State how it went."
        op.in_output_variable = []
        op.input_variable = [var("Session", "xs:string", "Occupation session of the caller"),
                             *[var(p, XSD[pr.type], pr.description or p) for p, pr in parameters.items()]]
        op.output_variable = [var("Accepted", "xs:boolean", "The command was accepted"),
                              var("ErrorID", "xs:unsignedShort", f"Why it was refused: {ERRORS}")]
        self.operations[name] = (action, ["Session", *parameters])
        return ModuleSkill(description=description, SemanticId=prop(skill_id(name)), SkillOperation={name: op},
                           InterfaceReference=ReferenceElement(value=affordance("actions", action)))

    def sequence(self, owner: str, steps, node: str, key: str, concept: str) -> model.ModuleSkillSequence:
        """A sequence with each step's bindings (constants as they run on the module) and the
        variables each step publishes below ``node``."""
        items = []
        for i, step in enumerate(steps, 1):
            declared = self.spec.skills[step.skill].parameters
            # A constant as the module runs it, else as bound (not the skill's default).
            bindings = {p: prop(v if isinstance(v, str) else current(f"{owner}.{step.name}.{p}",
                                                                     declared[p].model_copy(update={"default": v}),
                                                                     self.snap),
                                "xs:string" if isinstance(v, str) else XSD[declared[p].type])
                        for p, v in step.bind.items()}
            state = self.step_variables(step, f"{node}/{step.name}", f"{key}_{step.name}", f"{concept}/{step.name}")
            items.append(model.ModuleSkillStep(
                id_short=f"Step{i:02d}", Skill=self.skill_reference(step.skill), InstancePath=prop(f"{owner}.{step.name}"),
                Bindings=model.StepBindings(Binding=bindings) if bindings else None,
                StateReference=ReferenceElement(value=affordance("properties", state))))
        return model.ModuleSkillSequence(value=items)

    def step_variables(self, step, node: str, key: str, concept: str) -> str:
        """What a step publishes, as for a skill: State and ErrorID (both data points), and the
        parameters and results of the skill it runs. Gives the key of its State."""
        decl, title = self.spec.skills[step.skill], key.replace("_", " ")
        state = self.property(f"{key}_State", f"{node}/State", "USINT", f"{title} state: {SKILL_STATES}")
        self.observe(f"{key}_State", state, f"{concept}/State", f"State of {title}: {SKILL_STATES}")
        error = self.property(f"{key}_ErrorID", f"{node}/ErrorID", "UINT", f"{title} error: {ERRORS}")
        self.observe(f"{key}_ErrorID", error, f"{concept}/ErrorID", f"Why {title} last failed: {ERRORS}")
        for p, pr in decl.parameters.items():
            self.property(f"{key}_Parameter_{p}", f"{node}/Parameters/{p}", pr.type,
                          f"{title} {p} of the current or last run", pr.unit)
        for r in decl.results:
            source = result_input(self.spec, step.skill, r)
            self.property(f"{key}_Result_{r}", f"{node}/Results/{r}", source.type, f"{title} result {r}", source.unit)
        return state

    def implementation(self, instance: str) -> model.SkillImplementation:
        typ = self.snap.fbs.get(instance) if self.snap else None
        if typ is None:
            return model.SkillImplementation(InstancePath=prop(instance))
        return model.SkillImplementation(InstancePath=prop(instance), FBType=prop(typ),
                                         TypeHash=prop(self.snap.hashes.get(typ, "")))

    def skill(self, name: str) -> ModuleSkill:
        spec = self.spec
        composite = name in spec.composites
        decl = spec.composites[name] if composite else spec.skills[name]
        node = f"/Skills/{name}"
        start = self.action(f"{name}_Start", f"{node}/Start", f"Start {name}", decl.parameters)
        for method in SKILL_METHODS[1:]:
            self.action(f"{name}_{method}", f"{node}/{method}", f"{method} {name}")
        skill = self.entry(name, start, decl.parameters, decl.description or f"Skill {name}")
        skill.Kind = prop("Composite" if composite else "Primitive")
        if decl.parameters:
            skill.Parameters = arso.Parameters()
            for p, pr in decl.parameters.items():
                value = current(parameter_port(spec, name, p), pr, self.snap)
                declared = (("Unit", pr.unit), ("Minimum", pr.minimum), ("Maximum", pr.maximum), ("Default", pr.default))
                put(skill.Parameters.SkillParameter, p, Property(
                    value=text(value), value_type=XSD[pr.type], description=pr.description or f"Parameter {p}",
                    qualifiers=[Qualifier(type_=k, value=text(v), kind="ConceptQualifier") for k, v in declared if v is not None]))
                self.property(f"{name}_Parameter_{p}", f"{node}/Parameters/{p}", pr.type,
                              f"{name} {p} of the current or last run", pr.unit)
        if composite:
            put(skill.SkillSequence, "Execute", self.sequence(f"{name}.Execute", decl.execute, f"{node}/Execute",
                                                              f"{name}_Execute", f"{skill_id(name)}/Execute"))
            if decl.stop:
                # Published below .../Stopping: a "Stop" object would collide with the Stop method.
                put(skill.SkillSequence, "Stop", self.sequence(f"{name}.Stop", decl.stop, f"{node}/Stopping",
                                                               f"{name}_Stopping", f"{skill_id(name)}/Stopping"))
            used = dict.fromkeys(s.skill for s in [*decl.execute, *decl.stop])
            skill.Uses = model.SkillUses(value=[self.skill_reference(u, u) for u in used])
        else:
            ends = {"Ensures": decl.ensures} if decl.ensures is not None else {"After": decl.after}
            terms = {"Requires": decl.requires, **ends, "Invariant": decl.invariant, "Timeout": decl.timeout}
            skill.Contract = model.SkillContract(**{k: prop(v) for k, v in terms.items() if v is not None})
        occupied = [ReferenceElement(id_short=item, value=path(STRUCTURE, ("Entity", "EntryNode"), ("Entity", item)))
                    for item in spec.uses(name)]
        skill.Occupies = model.SkillOccupies(value=occupied) if occupied else None
        skill.Implementation = self.implementation(f"{name}.Control" if composite else name)
        state = self.property(f"{name}_State", f"{node}/State", "USINT", f"{name} state: {SKILL_STATES}")
        self.observe(f"{name}_State", state, f"{skill_id(name)}/State", f"State of {name}: {SKILL_STATES}")
        skill.StateReference = ReferenceElement(value=affordance("properties", state))
        error = self.property(f"{name}_ErrorID", f"{node}/ErrorID", "UINT", f"{name} error: {ERRORS}")
        self.observe(f"{name}_ErrorID", error, f"{skill_id(name)}/ErrorID", f"Why {name} last failed: {ERRORS}")
        for r in decl.results:
            source = result_input(spec, name, r)
            key = self.property(f"{name}_Result_{r}", f"{node}/Results/{r}", source.type, f"{name} result {r}",
                                source.unit)
            self.observe(f"{name}_Result_{r}", key, f"{skill_id(name)}/Results/{r}", f"Result {r} of {name}")
        return skill

    def occupation(self, name: str) -> ModuleSkill:
        """Occupy and Release, the two skills every resource of the lab has."""
        key = self.action(f"Occupation_{name}", f"/Occupation/{name}", f"{name} the module")
        return self.entry(name, key, {}, f"{name} the module for one client (its session)")

    # Submodels -------------------------------------------------------------------------------

    def parameters(self) -> Parameters | None:
        """The value of each skill parameter as deployed (the default a start without one uses)."""
        spec, entries = self.spec, {}
        for name in self.listed:
            decl = spec.composites.get(name) or spec.skills[name]
            for p, pr in decl.parameters.items():
                value = current(parameter_port(spec, name, p), pr, self.snap)
                shown = ReferenceElement(value=affordance("properties", f"{name}_Parameter_{p}"))
                entries[f"{name}_{p}"] = ParameterEntry(
                    description=pr.description or f"Parameter {p} of {name}", semantic_id=f"{skill_id(name)}/Parameters/{p}",
                    InterfaceReference=shown, Value=prop(value, XSD[pr.type]), Unit=prop(pr.unit) if pr.unit else None)
        return Parameters(id_short="Parameters", ParameterEntry=entries) if entries else None

    def mappings(self) -> Aimc:
        """What feeds the data points, and how each Operation reaches its method."""
        lines = "\n".join(f"        {v} = sources.{key}," for v, (key, _, _) in self.datapoints.items())
        mappings = [mapping_configuration(
            id_short="OPCUA",
            sources=[source(key, affordance("properties", key)) for key, _, _ in self.datapoints.values()],
            sinks=[sink(v, path(DATA, ("Property", v))) for v in self.datapoints],
            transformation=f"function aimc_main(sources)\n    return {{\n{lines}\n    }}\nend\n")]
        for name, (action, arguments) in self.operations.items():
            fields = "\n".join(f"            {a} = op.{a}," for a in arguments)
            operation = path(SKILLS, (SMC, "Skills"), (SMC, name), ("Operation", name))
            mappings.append(mapping_configuration(
                id_short=name, sources=[source(name, operation)], sinks=[sink(name, affordance("actions", action))],
                transformation=(f"-- {name}: the invocation's inputs become the arguments of the OPC UA method, in this order\n"
                                f"function aimc_main(sources)\n    local op = sources.{name}\n    return {{\n"
                                f"        {action} = {{\n{fields}\n        }},\n    }}\nend\n")))
        return Aimc(id_short="AssetInterfacesMappingConfiguration",
                    MappingConfigurations=AimcMappingConfigurations(value=mappings))

    def capabilities(self) -> model.ModuleCapabilityDescription | None:
        """The capabilities the module offers (IDTA 02020): each with its meaning, its properties
        (a value or a range, with a unit) and the skill realizing it (CapabilityRealizedBy, a
        reference into the Skills submodel)."""
        containers = {}
        for name, cap in self.spec.capabilities.items():
            capability = Capability(
                id_short="Capability", semantic_id=CAPABILITY, supplemental_semantic_ids=[meaning(name, cap.semantic_id)],
                display_name={"en": name}, description=cap.description or f"{name}, realized by {cap.realized_by}",
                # xs:boolean in the AAS (model.typed_qualifiers): aas-model cannot convert it.
                qualifiers=[Qualifier(type_="CapabilityRoleQualifier/Offered", value="true",
                                      semantic_id=OFFERED, kind="ConceptQualifier")])
            properties = {}
            for prop, value in cap.properties.items():
                about = dict(id_short="Value", supplemental_semantic_ids=[meaning(prop, value.semantic_id)],
                             display_name={"en": prop}, description=value.description,
                             qualifiers=[Qualifier(type_="Unit", value=value.unit, kind="ConceptQualifier")] if value.unit else [])
                if value.value is None:
                    element = cd.PropertyContainer(PropertyRange={"Value": cd.PropertyRange(
                        min=text(value.minimum), max=text(value.maximum), value_type="xs:double", **about)})
                else:
                    kind = "xs:boolean" if isinstance(value.value, bool) else "xs:string" if isinstance(value.value, str) else "xs:double"
                    element = cd.PropertyContainer(PropertyProperty={"Value": cd.PropertyProperty(
                        value=text(value.value), value_type=kind, **about)})
                put(properties, prop, element)
            realized = model.RealizedBySkill(
                id_short="RealizedBy", first=capability_path(name), second=path(SKILLS, (SMC, "Skills"), (SMC, cap.realized_by)))
            containers[name] = model.ModuleCapabilityContainer(
                id_short=name, Capability=capability,
                PropertySet={"PropertySet": cd.PropertySet(id_short="PropertySet", PropertyContainer=properties)} if properties else {},
                CapabilityRelations=model.ModuleCapabilityRelations(id_short="CapabilityRelations",
                                                                    CapabilityRealizedBy={"RealizedBy": realized}))
        if not containers:
            return None
        return model.ModuleCapabilityDescription(id_short="CapabilityDescription", CapabilitySet={
            OFFERED_SET: model.ModuleCapabilitySet(id_short=OFFERED_SET, CapabilityContainer=containers)})

    def realizes(self, skills: dict[str, ModuleSkill]) -> None:
        """A capability property a skill parameter sets: the skill's RealizesProperty (ARSO)."""
        for name, cap in self.spec.capabilities.items():
            for prop, value in cap.properties.items():
                if value.parameter is None:
                    continue
                skill = skills[cap.realized_by]
                if skill.RealizesProperty is not None:
                    raise model.ProfileError(f"{cap.realized_by}: ARSO holds one RealizesProperty per skill")
                skill.RealizesProperty = RelationshipElement(
                    id_short="RealizesProperty",
                    first=path(SKILLS, (SMC, "Skills"), (SMC, cap.realized_by), (SMC, "Parameters"), ("Property", value.parameter)),
                    second=path(CAPABILITIES, (SMC, OFFERED_SET), (SMC, name), (SMC, "PropertySet"), (SMC, prop), ("Range" if value.value is None else "Property", "Value")))

    def control_configuration(self) -> model.ModuleControlConfiguration:
        snap, drift, t = self.snap, self.drift, self.spec.targets[self.target]
        if snap is None:
            sync = "NotRead"
        elif snap.empty:
            sync = "NoProgram"
        else:
            sync = "InSync" if drift is not None and drift.empty else "Drift"
        differences = {f"D{i:03d}": prop(line) for i, line in enumerate(drift.lines()[:100] if drift else [], 1)}
        types = {f"T{i:03d}": cc.CCfgType(Name=prop(typ), Hash=prop(snap.hashes.get(typ, "")))
                 for i, typ in enumerate(sorted(set(snap.fbs.values())) if snap else [], 1)}
        return model.ModuleControlConfiguration(
            id_short="ControlConfiguration",
            Runtime=cc.Runtime(Name=prop("Eclipse 4diac FORTE"), Resource=prop(snap.resource if snap else "RES"),
                               ManagementEndpoint=prop(f"{snap.host}:{snap.port}" if snap else f"{t.host}:{t.port}")),
            ModuleSpec=prop(self.spec_path or ""), Target=prop(self.target), Generator=prop("modgen"),
            ProgramDigest=prop(program_digest(self.spec, self.target),
                               description="SHA-256 of the program the module spec generates for the target."),
            SyncState=prop(sync, description="InSync: the running program is the one the module spec generates; Drift: "
                           "it differs (see Differences); NoProgram: the runtime has none; NotRead: from the spec only."),
            ReadAt=prop(snap.read_at if snap else ""), Differences=cc.Differences(CCfgDifference=differences),
            Types=cc.Types(CCfgType=types))

    def build(self) -> tuple[ModuleTypeAAS, str]:
        spec = self.spec
        id_short, aas_id, asset_id = identity(spec)
        asset = ModuleTypeAAS(id_short=id_short, id=aas_id, asset_type=spec.aas.asset_type or "",
                              derived_from=model.RESOURCE_TEMPLATE)
        asset.specific_asset_ids = {k: v for k, v in (("serialNumber", spec.aas.serial_number),
                                                      ("location", spec.aas.location)) if v}
        plate = nameplate()
        plate.ManufacturerProductDesignation = ManufacturerProductDesignation(
            value={"en": f"{spec.module} module (IEC 61499, Eclipse 4diac FORTE)"})
        if spec.aas.serial_number:
            plate.SerialNumber = SerialNumber(value=spec.aas.serial_number)
        asset.nameplate = plate

        # Module level first, so the interface lists it first.
        skills = asset.skills.Skills.Skill
        for name in ("Occupy", "Release"):
            put(skills, name, self.occupation(name))
        occupied = self.property("Occupation_Occupied", "/Occupation/Occupied", "BOOL", "Occupied by a session")
        self.observe("OccupationState", occupied, OCCUPIED, "Occupied by a session: 0 free, 1 occupied")
        for m in MODULE_METHODS:
            self.action(f"Module_{m}", f"/Module/{m}", f"Module {m}")
        state = self.property("Module_State", "/Module/State", "USINT", f"PackML state: {MODULE_STATES}")
        self.observe("PackMLState", state, MODULE_STATE, f"PackML state of the module: {MODULE_STATES}")
        for name in self.listed:
            put(skills, name, self.skill(name))
        if spec.procedures:
            procedures = model.ModuleProcedures()
            for proc, steps in spec.procedures.items():
                put(procedures.Procedure, proc, self.sequence(proc, steps, f"/Procedures/{proc}", f"Procedure_{proc}",
                                                              f"{BASE_URL}/procedures/{proc}"))
            asset.skills.Procedures = procedures
        for name, code in ERROR_CODES.items():
            put(asset.skills.Errors.Error, name, arso.Error(ErrorCode=prop(code, "xs:integer")))
        nodes = {}
        for item, eq in spec.equipment.items():
            nodes[item] = Node(entity_type="CoManagedEntity", global_asset_id="",
                               description=eq.description or f"Equipment {item}")
            for s, io in eq.inputs.items():
                key = self.property(f"Equipment_{item}_{s}", f"/Equipment/{item}/{s}", io.type, f"{item} {s}", io.unit)
                self.observe(f"{item}_{s}", key, f"{BASE_URL}/variables/{item}/{s}",
                             f"{item} {s}" + (f" ({io.unit})" if io.unit else ""))
        asset.hierarchical_structures = HierarchicalStructures(
            id_short="HierarchicalStructures", ArcheType=ArcheType(value="OneDown"),
            EntryNode=EntryNode(global_asset_id=asset_id, description=f"The {spec.module} module", Node=nodes))

        interface = asset.asset_interfaces_description.InterfaceTemplateForOPCUA["interface_opcua"]
        interface.title.value = f"{spec.module} module"
        interface.EndpointMetadata.base.value = self.opcua
        interface.EndpointMetadata.contentType.value = "application/octet-stream"
        interface.EndpointMetadata.securityDefinitions.nosec_sc = wot.nosec_sc(scheme=wot.Scheme(value="nosec"))
        for key, action in self.actions.items():
            put(interface.InteractionMetadata.actions.property_name, key, action)
        for key, p in self.properties.items():
            put(interface.InteractionMetadata.properties.property_name, key, p)
        # A data point is a decimal: states and counts as their number, a Boolean as 0 or 1.
        for name, (_, concept, title) in self.datapoints.items():
            put(asset.operational_data.Datapoint, name,
                Property(value="0", value_type="xs:decimal", semantic_id=concept, description=title))
        self.realizes(skills)
        asset.capability_description = self.capabilities()
        asset.parameters = self.parameters()
        asset.asset_interfaces_mapping_configuration = self.mappings()
        asset.control_configuration = self.control_configuration()
        return ModuleTypeAAS.model_validate(asset.model_dump()), asset_id


def describe(spec: ModuleSpec, target: str, snap: Snapshot | None = None, drift: Drift | None = None,
             spec_path: str | None = None, opcua: str | None = None) -> dict:
    """The module's profile; with a snapshot, values, hashes and the sync state are the running ones."""
    asset, asset_id = Describer(spec, target, snap, drift, spec_path, opcua).build()
    return model.profile(asset, global_asset_id=asset_id)
