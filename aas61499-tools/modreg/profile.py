"""A module's AAS on the lab's shared model, from its module spec and, when read, what runs on it.

``describe`` fills a ``ModuleTypeAAS``; ``model.profile`` turns it into the profile the module carries
and registers with (its manifest), ``model.environment`` into the AAS.

- **Asset Interfaces Description**: the OPC UA server; every method as an action (browse path,
  arguments in call order) and every published variable as a property.
- **Control Component Instance**: Occupy, Release and every skill of the module spec. An offered
  skill has its native interface (the Start action) and an Operation with the parameters as inputs;
  each has its kind, contract or sequences, occupied equipment and implementing function block.
- **Variables** with the mapping that feeds them (Asset Interfaces Mapping Configuration): module
  state, occupation, skill states and results, equipment inputs.
- **Parameters**: the value of every skill parameter as deployed.
- **Hierarchical Structures**: the equipment as parts of the module.
- **Control Configuration**: spec, target and program digest; from a module that was read also the
  synchronisation state, the differences and the type hashes.
"""
from __future__ import annotations

import hashlib
import json

from aas_model.constants import AID_SYNCHRONOUS, BASE_URL
from aas_model.json_schema_aid import datapoint_from_schema
from aas_model.resource_template import nameplate, operation_ref, skill_operation
from aas_model.resource_template._helpers import put
from aas_model.resource_template.asset_interfaces_mapping_configuration import mapping_configuration, sink, source
from aas_model.resource_template.variables import variable
from aas_model.submodel_templates import (
    Aimc, AimcMappingConfigurations, DmpActionInput, DmpActionOutput, OpcuaAction, OpcuaProperty, OperationVariableProp,
    SkillInterfaceRelationship,
)
from aas_model.submodel_templates.parameters import ParameterItem, ParamProp, ParamReference
from aas_pydantic import Key, ModelReference, Property, ReferenceElement
from aas_pydantic.submodel_templates import asset_interfaces_description as wot
from aas_pydantic.submodel_templates.control_component_instance import Direction, SkillReference, Type as IecType, Uses
from aas_pydantic.submodel_templates.hierarchical_structures import ArcheType, EntryNode, HierarchicalStructures, Node
from aas_pydantic.submodel_templates.nameplate import ManufacturerProductDesignation, SerialNumber

from modgen.module import parameter_port, result_type
from modgen.spec import ModuleSpec, Parameter
from modsync.aas import MODULE_METHODS, SKILL_METHODS, browse_path, current, identity
from modsync.compare import Drift, expected, expected_values
from modsync.device import Snapshot

from . import model
from .model import ModuleSkill, ModuleTypeAAS

AID = "{aas_id}/submodels/AssetInterfacesDescription"
CCI = "{aas_id}/submodels/ControlComponentInstance"
STRUCTURE = "{aas_id}/submodels/HierarchicalStructures"
VARIABLES = "{aas_id}/submodels/Variables"
SMC = "SubmodelElementCollection"
XSD = {"BOOL": "xs:boolean", "LREAL": "xs:double", "INT": "xs:short", "DINT": "xs:int", "UINT": "xs:unsignedShort",
       "UDINT": "xs:unsignedInt", "USINT": "xs:unsignedByte", "WSTRING": "xs:string"}
JSON = {"BOOL": "boolean", "LREAL": "number", "WSTRING": "string"}       # everything else is an integer
SKILL_STATES = "0 Idle, 1 Running, 2 Stopping, 3 Succeeded, 4 Failed, 5 Aborted"
MODULE_STATES = "1 Clearing, 2 Stopped, 3 Starting, 4 Idle, 6 Execute, 7 Stopping, 8 Aborting, 9 Aborted, 15 Resetting"
ERRORS = ("0 none, 1 PreconditionViolated, 2 InvariantViolated, 3 Timeout, 4 NotReady, 5 NotPermitted, 6 Busy, "
          "7 Interrupted, 8 OutOfRange")
ANSWER = {"type": "object", "properties": {"Accepted": {"type": "boolean"},
                                            "ErrorID": {"type": "integer", "minimum": 0, "maximum": 65535}}}


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


def skill_reference(name: str) -> ModelReference:
    return path(CCI, (SMC, "Skills"), (SMC, name))


def schema(parameters: dict[str, Parameter]) -> dict:
    """The arguments of a method as a JSON Schema object, in call order (the session first)."""
    fields = {"Session": {"type": "string", "title": "Occupation session of the caller"}}
    for name, pr in parameters.items():
        field = {"type": "number", "title": pr.description or name, "default": pr.default}
        field.update({k: v for k, v in (("minimum", pr.minimum), ("maximum", pr.maximum)) if v is not None})
        fields[name] = field
    return {"type": "object", "properties": fields}


def program_digest(spec: ModuleSpec, target: str) -> str:
    """SHA-256 of the program the spec generates for the target: instances with their types,
    connections and input values."""
    app = expected(spec, target)
    program = {"instances": sorted(app.fbs.items()),
               "connections": sorted([*app.event_connections, *app.data_connections]),
               "values": sorted(expected_values(spec, app).items())}
    return hashlib.sha256(json.dumps(program, separators=(",", ":")).encode()).hexdigest()


class Describer:
    """Collects the interface while the skills and variables are described, then builds the model."""

    def __init__(self, spec: ModuleSpec, target: str, snap: Snapshot | None, drift: Drift | None,
                 spec_path: str | None, opcua: str | None):
        self.spec, self.target, self.snap, self.drift, self.spec_path = spec, target, snap, drift, spec_path
        self.opcua = opcua or f"opc.tcp://{spec.targets[target].host}:4840"
        self.actions: dict[str, OpcuaAction] = {}
        self.properties: dict[str, OpcuaProperty] = {}
        self.variables: dict[str, tuple[str, str]] = {}          # variable -> (interface property, concept)
        self.operations: dict[str, tuple[str, list[str]]] = {}    # skill -> (interface action, arguments)

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

    def observe(self, name: str, key: str, concept: str):
        """A variable of the AAS fed from a property of the interface."""
        self.variables[name] = (key, concept)

    # Skills ----------------------------------------------------------------------------------

    def operation(self, name: str, action: str, parameters: dict[str, Parameter]):
        """The Operation a client invokes: the session and the parameters in, the answer out."""
        def var(id_short, value_type, description):
            return OperationVariableProp(id_short=id_short, value_type=value_type, description=description)

        op = skill_operation(name, synchronous=True)
        op.in_output_variable = []
        op.input_variable = [var("Session", "xs:string", "Occupation session of the caller"),
                             *[var(p, XSD[pr.type], pr.description or p) for p, pr in parameters.items()]]
        op.output_variable = [var("Accepted", "xs:boolean", "The command was accepted"),
                              var("ErrorID", "xs:unsignedShort", f"Why it was refused: {ERRORS}")]
        self.operations[name] = (action, ["Session", *parameters])
        return op

    def sequence(self, owner: str, steps) -> model.SkillSequence:
        """A sequence with each step's bindings; constants as they run on the module."""
        sequence = model.SkillSequence()
        for i, step in enumerate(steps, 1):
            declared = self.spec.skills[step.skill].parameters
            bindings = {p: prop(v if isinstance(v, str) else current(f"{owner}.{step.name}.{p}", declared[p], self.snap),
                                "xs:string" if isinstance(v, str) else XSD[declared[p].type])
                        for p, v in step.bind.items()}
            item = model.SkillStep(InstancePath=prop(f"{owner}.{step.name}"),
                                   Bindings=model.StepBindings(Binding=bindings) if bindings else None)
            item.Skill.value = skill_reference(step.skill)
            put(sequence.Step, f"Step{i:02d}", item)
        return sequence

    def implementation(self, instance: str | None) -> model.SkillImplementation | None:
        typ = self.snap.fbs.get(instance) if self.snap and instance else None
        if typ is None:
            return model.SkillImplementation(InstancePath=prop(instance)) if instance else None
        return model.SkillImplementation(InstancePath=prop(instance), FBType=prop(typ),
                                         TypeHash=prop(self.snap.hashes.get(typ, "")))

    def skill(self, name: str) -> ModuleSkill:
        spec = self.spec
        composite = name in spec.composites
        decl = spec.composites[name] if composite else spec.skills[name]
        node = f"/Skills/{name}"
        skill = ModuleSkill(description=decl.description or f"Skill {name}")
        skill.Kind = prop("Composite" if composite else "Primitive")
        skill.Disabled.value = "false"
        for p, pr in decl.parameters.items():
            values = model.ParameterValues(
                Default=prop(pr.default, XSD[pr.type]),
                Minimum=prop(pr.minimum, XSD[pr.type]) if pr.minimum is not None else None,
                Maximum=prop(pr.maximum, XSD[pr.type]) if pr.maximum is not None else None,
                Unit=prop(pr.unit) if pr.unit else None)
            put(skill.Parameters.Parameter, p, model.ModuleSkillParameter(
                description=pr.description or f"Parameter {p}", Direction=Direction(value="In"),
                Type=IecType(value=pr.type), Values=values))
        if composite:
            skill.Execute = self.sequence(f"{name}.Execute", decl.execute)
            skill.Stop = self.sequence(f"{name}.Stop", decl.stop) if decl.stop else None
            used = dict.fromkeys(s.skill for s in [*decl.execute, *decl.stop])
            skill.Uses = Uses(SkillReference={u: SkillReference(value=skill_reference(u)) for u in used})
        else:
            ends = {"Ensures": decl.ensures} if decl.ensures is not None else {"After": decl.after}
            terms = {"Requires": decl.requires, **ends, "Invariant": decl.invariant, "Timeout": decl.timeout}
            skill.Contract = model.SkillContract(**{k: prop(v) for k, v in terms.items() if v is not None})
        occupied = {item: ReferenceElement(value=path(STRUCTURE, ("Entity", "EntryNode"), ("Entity", item)))
                    for item in spec.uses(name)}
        skill.Occupies = model.SkillOccupies(Node=occupied) if occupied else None
        # A primitive that is not offered runs only as a step of a module level skill.
        running = composite or decl.offered
        skill.Implementation = self.implementation((f"{name}.Control" if composite else name) if running else None)
        if not running:
            skill.Disabled.value = "true"
            return skill
        if decl.offered:
            start = self.action(f"{name}_Start", f"{node}/Start", f"Start {name}", decl.parameters)
            for method in SKILL_METHODS[1:]:
                self.action(f"{name}_{method}", f"{node}/{method}", f"{method} {name}")
            skill.interface_reference.value = affordance("actions", start)
            skill.operation = self.operation(name, start, decl.parameters)
        state = self.property(f"{name}_State", f"{node}/State", "USINT", f"{name} state: {SKILL_STATES}")
        self.observe(f"{name}_State", state, f"{BASE_URL}/skills/{name}/State")
        skill.StateReference = ReferenceElement(value=affordance("properties", state))
        error = self.property(f"{name}_ErrorID", f"{node}/ErrorID", "UINT", f"{name} error: {ERRORS}")
        self.observe(f"{name}_ErrorID", error, f"{BASE_URL}/skills/{name}/ErrorID")
        for p, pr in decl.parameters.items():
            self.property(f"{name}_Parameter_{p}", f"{node}/Parameters/{p}", pr.type,
                          f"{name} {p} of the current or last run", pr.unit)
        for r in decl.results:
            iec = (result_type(spec, decl.execute, decl.results[r]) if composite
                   else spec.equipment[decl.equipment].inputs[decl.results[r]].type)
            key = self.property(f"{name}_Result_{r}", f"{node}/Results/{r}", iec, f"{name} result {r}")
            self.observe(f"{name}_Result_{r}", key, f"{BASE_URL}/skills/{name}/Results/{r}")
        return skill

    def occupation(self, name: str) -> ModuleSkill:
        """Occupy and Release, the two skills every resource of the lab has."""
        key = self.action(f"Occupation_{name}", f"/Occupation/{name}", f"{name} the module")
        skill = ModuleSkill(description=f"{name} the module for one client (its session)")
        skill.Disabled.value = "false"
        skill.interface_reference.value = affordance("actions", key)
        skill.operation = self.operation(name, key, {})
        return skill

    # Submodels -------------------------------------------------------------------------------

    def parameters(self) -> model.Parameters:
        """The value of each skill parameter as deployed (the default a start without one uses)."""
        spec, groups = self.spec, {}
        for name, decl in [*spec.skills.items(), *spec.composites.items()]:
            running = name in spec.composites or decl.offered
            if not (decl.parameters and running):
                continue
            entries = {}
            for p, pr in decl.parameters.items():
                value = current(parameter_port(spec, name, p), pr, self.snap)
                entries[p] = ParameterItem(
                    description=pr.description or f"Parameter {p} of {name}",
                    parameter=ParamProp(value=text(value), value_type=XSD[pr.type]),
                    interface_reference=ParamReference(value=affordance("properties", f"{name}_Parameter_{p}")))
            groups[name] = ParameterItem(description=f"Parameters of the skill {name}", value=entries)
        return model.Parameters(id_short="Parameters", parameter=groups)

    def mappings(self) -> Aimc:
        """What feeds the variables, and how each Operation reaches its method."""
        lines = "\n".join(f"        {v} = sources.{key}," for v, (key, _) in self.variables.items())
        mappings = [mapping_configuration(
            id_short="OPCUA",
            sources=[source(key, affordance("properties", key)) for key, _ in self.variables.values()],
            sinks=[sink(v, path(VARIABLES, ("Property", v))) for v in self.variables],
            transformation=f"function aimc_main(sources)\n    return {{\n{lines}\n    }}\nend\n")]
        for name, (action, arguments) in self.operations.items():
            fields = "\n".join(f"            {a} = op.{a}," for a in arguments)
            mappings.append(mapping_configuration(
                id_short=name, sources=[source(name, operation_ref(name))],
                sinks=[sink(name, affordance("actions", action))],
                transformation=(f"-- {name}: the invocation's inputs become the arguments of the OPC UA method, in this order\n"
                                f"function aimc_main(sources)\n    local op = sources.{name}\n    return {{\n"
                                f"        {action} = {{\n{fields}\n        }},\n    }}\nend\n")))
        return Aimc(id_short="AssetInterfacesMappingConfiguration",
                    MappingConfigurations=AimcMappingConfigurations(value=mappings))

    def control_configuration(self) -> model.ControlConfiguration:
        snap, drift, t = self.snap, self.drift, self.spec.targets[self.target]
        if snap is None:
            sync = "NotRead"
        elif snap.empty:
            sync = "NoProgram"
        else:
            sync = "InSync" if drift is not None and drift.empty else "Drift"
        cc = model.ControlConfiguration(id_short="ControlConfiguration")
        cc.Runtime.ManagementEndpoint.value = f"{snap.host}:{snap.port}" if snap else f"{t.host}:{t.port}"
        cc.Runtime.Resource.value = snap.resource if snap else "RES"
        cc.ModuleSpec.value = self.spec_path or ""
        cc.Target.value = self.target
        cc.ProgramDigest.value = program_digest(self.spec, self.target)
        cc.SyncState.value = sync
        cc.ReadAt.value = snap.read_at if snap else ""
        for i, line in enumerate(drift.lines()[:100] if drift else [], 1):
            put(cc.Differences.Difference, f"D{i:03d}", prop(line))
        for i, typ in enumerate(sorted(set(snap.fbs.values())) if snap else [], 1):
            put(cc.Types.Type, f"T{i:03d}", model.ControlType(Name=prop(typ), Hash=prop(snap.hashes.get(typ, ""))))
        return cc

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
        skills = asset.control_component_instance.Skills.Skill
        endpoints = asset.control_component_instance.Endpoints.Endpoint
        for name in ("Occupy", "Release"):
            put(skills, name, self.occupation(name))
        occupied = self.property("Occupation_Occupied", "/Occupation/Occupied", "BOOL", "Occupied by a session")
        self.observe("OccupationState", occupied, "")
        for m in MODULE_METHODS:
            self.action(f"Module_{m}", f"/Module/{m}", f"Module {m}")
        state = self.property("Module_State", "/Module/State", "USINT", f"PackML state: {MODULE_STATES}")
        self.observe("PackMLState", state, "")
        for name in [*spec.skills, *spec.composites]:
            put(skills, name, self.skill(name))
        for name, (action, _) in self.operations.items():
            put(endpoints, name, SkillInterfaceRelationship(first=skill_reference(name),
                                                            second=affordance("actions", action)))
        nodes = {}
        for item, eq in spec.equipment.items():
            nodes[item] = Node(entity_type="CoManagedEntity", global_asset_id="",
                               description=eq.description or f"Equipment {item}")
            for s, io in eq.inputs.items():
                key = self.property(f"Equipment_{item}_{s}", f"/Equipment/{item}/{s}", io.type, f"{item} {s}", io.unit)
                self.observe(f"{item}_{s}", key, f"{BASE_URL}/variables/{item}/{s}")
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
        for name, (_, concept) in self.variables.items():
            if concept:                                    # PackMLState and OccupationState come with the type
                put(asset.variables.variable, name, variable(concept))
        asset.parameters = self.parameters()
        asset.asset_interfaces_mapping_configuration = self.mappings()
        asset.control_configuration = self.control_configuration()
        return ModuleTypeAAS.model_validate(asset.model_dump()), asset_id


def describe(spec: ModuleSpec, target: str, snap: Snapshot | None = None, drift: Drift | None = None,
             spec_path: str | None = None, opcua: str | None = None) -> dict:
    """The module's profile; with a snapshot, values, hashes and the sync state are the running ones."""
    asset, asset_id = Describer(spec, target, snap, drift, spec_path, opcua).build()
    return model.profile(asset, global_asset_id=asset_id)
