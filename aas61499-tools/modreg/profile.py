"""A module's AAS in the structure of the resource ontology (ARSO), from its module spec and, when
read, what runs on it.

``describe`` fills a ``ModuleTypeAAS``, and ``describe_all`` also a ``ComponentTypeAAS`` for every
part of the module that has skills; ``model.profile`` turns each into the profile it is registered
with (its manifest), ``model.environment`` into the AAS.

- **Asset Interfaces Description**: the OPC UA server; every method as an action (browse path,
  arguments in call order) and every published variable as a property.
- **Skills**: what the module offers. A skill is its commands (Start, Stop, Abort, Reset): each
  holds the action that calls it, its Operation (the session and the parameters in; whether it was
  accepted, why not and the results out) and, for a module level skill, the steps it runs. A step
  refers to the skill it runs and says what is connected to that skill's variables: a constant, or
  a variable of the command's own Operation. The primitives are in the AAS of the component they
  move; one without a component is the module's own.
- **Module**: the module's own commands in the same shape: Occupy, Release and its state machine.
  What it runs while resetting and stopping are the steps of Reset and Stop.
- **Operational Data** with the mapping that feeds it (Asset Interfaces Mapping Configuration):
  module state, occupation, skill and step states, parameters and results, equipment inputs, as
  decimal data points. A data point means what the Operation variable it shows means (the same
  semantic id); nothing in Skills refers to it.
- **Hierarchical Structures**: the components, each with an AAS of its own, found by its asset id.
- **Control Configuration**: spec, target and program digest, and which block of the program each
  skill and each step is (Instances); from a module that was read also the synchronisation state,
  the differences and the type hashes.
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
from aas_pydantic import Capability, Key, ModelReference, Property, Qualifier, ReferenceElement
from aas_pydantic.submodel_templates import asset_interfaces_description as wot
from aas_pydantic.submodel_templates import capability_description as cd
from aas_pydantic.submodel_templates.hierarchical_structures import ArcheType, EntryNode, HierarchicalStructures, Node
from aas_pydantic.submodel_templates.nameplate import ManufacturerProductDesignation, SerialNumber

from modgen.library import q
from modgen.module import parameter_port
from modgen.spec import ModuleSpec, Parameter
from modsync.compare import Drift, expected, expected_values
from modsync.device import Snapshot, literal

from . import model
from .generated import control_configuration as cc, skills as arso
from .model import ComponentTypeAAS, ModuleTypeAAS

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
# The rules a generated module is built by (docs/module-rules.md).
RULES = f"{BASE_URL}/rules/module/1"
OCCUPIED = "https://w3id.org/2026/apex/semantic/state/occupied"
# What a skill can be told: a command means the same on every skill (ontology/Vocabulary/commands.ttl).
COMMAND = f"{BASE_URL}/skill"


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


def block_type(spec: ModuleSpec, skill: str) -> str:
    """The function block type of a skill primitive, as modgen names it."""
    return f"{spec.package}::SK_{skill}"


def declared_parameter(name: str, pr: Parameter, value) -> Property:
    """A skill parameter holding ``value``, with its declaration (unit, limits, default) as qualifiers."""
    declared = (("Unit", pr.unit), ("Minimum", pr.minimum), ("Maximum", pr.maximum), ("Default", pr.default))
    return Property(
        value=text(value), value_type=XSD[pr.type], description=pr.description or f"Parameter {name}",
        qualifiers=[Qualifier(type_=k, value=text(v), kind="ConceptQualifier") for k, v in declared if v is not None])


def contract(decl) -> arso.Contract:
    """What starts, ends and bounds a primitive, as the module spec states it. A condition that is
    plainly true is left out."""
    done = {"Ensures": decl.ensures} if decl.ensures is not None else {"After": decl.after}
    # A time ends it by itself: the longest it may run is said only where a sensor ends it.
    terms = {"Requires": decl.requires, **done, "Invariant": decl.invariant,
             "Timeout": decl.timeout if decl.ensures is not None else None}
    return arso.Contract(**{k: prop(v) for k, v in terms.items() if v is not None and v != "TRUE"})


MODULE_METHODS = ["Reset", "Start", "Stop", "Abort", "Clear"]


def identity(spec: ModuleSpec) -> tuple[str, str, str]:
    """(idShort, id, globalAssetId) of the module's shell."""
    id_short = spec.aas.id_short or f"{spec.module}ModuleAAS"
    return (id_short, spec.aas.id or f"{BASE_URL}/aas/{id_short}",
            spec.aas.global_asset_id or f"{BASE_URL}/assets/{spec.module}Module")


def browse_path(spec: ModuleSpec, path: str) -> str:
    """OPC UA RelativePath text of a node below the module's root (FORTE's nodes are in namespace 1)."""
    parts = [p for p in spec.opcua_root.split("/") if p][1:] + [p for p in path.split("/") if p]
    return "/0:Objects" + "".join(f"/1:{p}" for p in parts)


def current(port: str, pr: Parameter, snap: Snapshot | None):
    """The parameter's value on the module if it was read, else the spec's default."""
    read = snap.values.get(port) if snap else None
    value = pr.default if read is None else literal(read)
    return bool(value) if pr.type == "BOOL" else float(value) if pr.type == "LREAL" else int(value)


def component_identity(spec: ModuleSpec, item: str) -> tuple[str, str, str, str]:
    """(idShort, id, globalAssetId, assetType) of the AAS of a component: named after the module and
    the item, of the kind every component like it shares."""
    name = f"{spec.module}{item}"
    return (f"{name}AAS", f"{BASE_URL}/aas/{name}AAS", f"{BASE_URL}/assets/{name}",
            f"{model.RESOURCE}/Component/{spec.equipment[item].kind or item}")


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


# A module level skill has no type of its own: it is its Control block.
CONTROL_TYPE = q("SKILL_Core")


class Describer:
    """Collects the interface while the skills and data points are described, then builds the model."""

    def __init__(self, spec: ModuleSpec, target: str, snap: Snapshot | None, drift: Drift | None,
                 spec_path: str | None, opcua: str | None):
        self.spec, self.target, self.snap, self.drift, self.spec_path = spec, target, snap, drift, spec_path
        self.opcua = opcua or f"opc.tcp://{spec.targets[target].host}:4840"
        self.actions: dict[str, OpcuaAction] = {}
        self.properties: dict[str, OpcuaProperty] = {}
        self.datapoints: dict[str, tuple[str, str, str]] = {}    # data point -> (interface property, concept, title)
        # Action of the interface -> (the Operation that invokes it, its arguments in call order)
        self.operations: dict[str, tuple[ModelReference, list[str]]] = {}
        # Block of the program -> (its type as the module's rules name it, the skill or step it is)
        self.instances: dict[str, tuple[str, ModelReference]] = {}
        self.module_id = identity(spec)[1]
        # The components: every item of equipment that a skill moves.
        self.components = [item for item in spec.equipment if any(d.equipment == item for d in spec.skills.values())]
        # What a parameter of a skill means in a product's terms: the capability property it sets.
        self.means = {(cap.realized_by, value.parameter): meaning(prop_name, value.semantic_id)
                      for cap in spec.capabilities.values() for prop_name, value in cap.properties.items() if value.parameter}

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

    def home(self, name: str, inside: str | None = None) -> str:
        """The Skills submodel a skill is described in, as seen from the AAS of ``inside`` (a
        component; None: the module): the component's it moves, else the module's."""
        decl = self.spec.skills.get(name)
        item = decl.equipment if decl is not None and decl.equipment in self.components else None
        if item == inside:
            return SKILLS
        return f"{component_identity(self.spec, item)[1] if item else self.module_id}/submodels/Skills"

    def skill_reference(self, name: str) -> ReferenceElement:
        return ReferenceElement(value=path(self.home(name), (SMC, "Skills"), (SMC, name)))

    def variable(self, name: str, value_type: str, about: str, concept: str | None = None, pr: Parameter | None = None,
                 value=None, unit: str | None = None, means: str | None = None) -> OperationVariableProp:
        """A variable of an Operation. A parameter carries its value (the default, or what the module
        runs with), its unit and its limits; ``concept`` is what the data point showing it means too,
        ``means`` what it is in a product's terms."""
        declared = [("Unit", pr.unit if pr else unit), ("Minimum", pr.minimum if pr else None),
                    ("Maximum", pr.maximum if pr else None), ("Default", pr.default if pr else None)]
        made = OperationVariableProp(
            id_short=name, value_type=value_type, description=about,
            qualifiers=[Qualifier(type_=k, value=text(v), kind="ConceptQualifier") for k, v in declared if v is not None])
        if value is not None:
            made.value = text(value)
        if concept:
            made.semantic_id = concept
        if means:
            made.supplemental_semantic_ids = [means]
        return made

    def operation(self, key: str | None, at: ModelReference, about: str, meaning_id: str, inputs=(), outputs=()):
        """The Operation of a command: the session and ``inputs`` in; Accepted, ErrorID and
        ``outputs`` out. With ``key`` it invokes that action of the interface (the AIMC maps it
        there, and the lab's delegation service calls it)."""
        op = skill_operation(key or "local", synchronous=True)
        if not key:
            op.qualifiers = []                      # nothing calls it: it only declares the variables
        op.semantic_id = meaning_id
        op.description = about
        op.in_output_variable = []
        op.input_variable = [self.variable("Session", "xs:string", "Occupation session of the caller"), *inputs]
        op.output_variable = [self.variable("Accepted", "xs:boolean", "The command was accepted"),
                              self.variable("ErrorID", "xs:unsignedShort", f"Why it was refused or failed: {ERRORS}"),
                              *outputs]
        if key:
            self.operations[key] = (at, [v.id_short for v in op.input_variable])
        return op

    def command(self, made, name: str, where: str, at: tuple, meaning_id: str, about: str, key: str | None = None,
                node: str = "", parameters: dict[str, Parameter] | None = None, inputs=(), outputs=(),
                says: list[str] | None = None, interface: str = AID):
        """One command of a skill or of the module: ``made``, named ``name``, at ``at`` in the
        submodel ``where``. With ``key`` it is callable: an action of the interface (the method
        ``node``), the Operation that invokes it, and the reference to that action."""
        made.semantic_id = meaning_id
        made.description = about
        if key:
            self.action(key, node, about.partition(";")[0], parameters)
            # The action says which command it carries out, beside the id every action has.
            self.actions[key].supplemental_semantic_ids = says or [meaning_id]
            made.InterfaceReference = ReferenceElement(value=path(
                interface, (SMC, "interface_opcua"), (SMC, "InteractionMetadata"), (SMC, "actions"), (SMC, key)))
        put(made.SkillOperation, name, self.operation(key, path(where, *at, ("Operation", name)), about, meaning_id,
                                                      inputs, outputs))
        return made

    def steps(self, owner: str, sequence, node: str, key: str, concept: str, where: str, at: tuple, command: str,
              results: dict[str, str] | None = None):
        """What a command runs, as a flow in the planner's elements: steps Step_0000, ... with their
        NodeId (the name of the step's instance in the program), Kind, Name and Order. A step of
        the kind ``step`` refers to the skill it runs. Its Bindings say what each input of that
        skill is handed: a constant as it runs on the module (Value), or a variable of the
        command's Operation (SourceElement). Its Outputs say which results of the command it gives
        (``results``, output -> "<step>.<its result>"). A step means what its instance in the
        program is called (``concept``/<step>, a supplemental id): its state and what it publishes
        below ``node`` are data points named from there."""
        held = arso.Steps()
        own = lambda v: path(where, *at, ("Operation", command), ("Property", v))    # noqa: E731

        def of_skill(name: str, variable: str) -> ModelReference:
            return path(self.home(name), (SMC, "Skills"), (SMC, name), (SMC, "Start"), ("Operation", "Start"),
                        ("Property", variable))

        for order, step in enumerate(sequence):
            declared = self.spec.skills[step.skill].parameters
            made = arso.SkillStep(
                NodeId=arso.NodeId(value=step.name), Kind=arso.Kind(value="step"), Name=arso.Name(value=step.name),
                Order=arso.Order(value=str(order), value_type="xs:nonNegativeInteger"),
                Skill=arso.Skill_production_sequence(value=self.skill_reference(step.skill).value),
                description=f"{step.name}: runs {step.skill}")
            made.supplemental_semantic_ids = [f"{concept}/{step.name}"]
            bindings = arso.Bindings()
            for p, v in step.bind.items():
                bound = arso.StepBinding(Name=arso.Name(value=p), InputReference=arso.InputReference(value=of_skill(step.skill, p)))
                if isinstance(v, str):
                    bound.SourceElement = arso.SourceElement(value=own(v))
                else:
                    # As the module runs it, else as bound (not the skill's default).
                    bound.Value = arso.Value(
                        value=text(current(f"{owner}.{step.name}.{p}", declared[p].model_copy(update={"default": v}), self.snap)),
                        value_type=XSD[declared[p].type])
                put(bindings.StepBinding, f"Binding_{len(bindings.StepBinding):04d}", bound)
            if bindings.StepBinding:
                made.Bindings = bindings
            outputs = arso.Outputs()
            for output, source in (results or {}).items():
                of, _, inner = source.partition(".")
                if of == step.name:
                    io = result_input(self.spec, step.skill, inner)
                    put(outputs.StepOutput, f"Output_{len(outputs.StepOutput):04d}", arso.StepOutput(
                        OutputId=arso.OutputId(value=output), Name=arso.Name(value=output),
                        DataType=arso.DataType(value="boolean" if io.type == "BOOL" else "number"),
                        Unit=arso.Unit(value=io.unit or ""), ResultReference=arso.ResultReference(value=of_skill(step.skill, inner))))
            if outputs.StepOutput:
                made.Outputs = outputs
            self.step_variables(step, f"{node}/{step.name}", f"{key}_{step.name}", f"{concept}/{step.name}")
            id_short = f"Step_{order:04d}"
            self.instances[f"{owner}.{step.name}"] = (block_type(self.spec, step.skill),
                                                      path(where, *at, (SMC, "Steps"), (SMC, id_short)))
            put(held.SkillStep, id_short, made)
        return held if held.SkillStep else None

    def step_variables(self, step, node: str, key: str, concept: str) -> str:
        """What a step publishes, as for a skill: State and ErrorID (both data points), and the
        parameters and results of the skill it runs. Gives the key of its State."""
        decl, title = self.spec.skills[step.skill], key.replace("_", " ")
        state = self.property(f"{key}_State", f"{node}/State", "USINT", f"{title} state: {SKILL_STATES}")
        self.observe(f"{key}_State", state, f"{concept}/State", f"State of {title}: {SKILL_STATES}")
        error = self.property(f"{key}_ErrorID", f"{node}/ErrorID", "UINT", f"{title} error: {ERRORS}")
        self.observe(f"{key}_ErrorID", error, f"{concept}/ErrorID", f"Why {title} last failed: {ERRORS}")
        for p, pr in decl.parameters.items():
            found = self.property(f"{key}_Parameter_{p}", f"{node}/Parameters/{p}", pr.type,
                                  f"{title} {p} of the current or last run", pr.unit)
            self.observe(found, found, f"{concept}/Parameters/{p}", f"{title} {p} of the current or last run")
        for r in decl.results:
            source = result_input(self.spec, step.skill, r)
            found = self.property(f"{key}_Result_{r}", f"{node}/Results/{r}", source.type, f"{title} result {r}",
                                  source.unit)
            self.observe(found, found, f"{concept}/Results/{r}", f"Result {r} of {title}")
        return state

    def skill(self, name: str) -> model.ModuleSkill:
        """A skill with its commands. A module level skill (composite) runs steps on Start and on
        Stop; a primitive runs nothing and states what ends it (Contract). A skill the module offers
        has an action per command and publishes its state, why it last failed, its parameters and
        its results as data points; one that only runs as a step has a Start that nothing calls."""
        spec = self.spec
        composite = name in spec.composites
        decl = spec.composites[name] if composite else spec.skills[name]
        item = decl.equipment if not composite and decl.equipment in self.components else None
        offered, node, here = decl.offered, f"/Skills/{name}", ((SMC, "Skills"), (SMC, name))
        where = self.home(name)                         # as the module sees it (the mapping is the module's)
        interface = AID if item is None else f"{self.module_id}/submodels/AssetInterfacesDescription"
        # Every skill is the same kind of element; what kind of skill it is, is said beside it.
        skill = model.ModuleSkill(description=decl.description or f"Skill {name}", SemanticId=prop(skill_id(name)))
        skill.supplemental_semantic_ids = [f"{COMMAND}/{'Composite' if composite else 'Primitive'}"]

        def told(command: str, about: str, **more):
            says = [f"{COMMAND}/{command}", skill_id(name)]
            return self.command(getattr(arso, command)(), command, where, (*here, (SMC, command)), f"{COMMAND}/{command}",
                                about, f"{name}_{command}" if offered else None, f"{node}/{command}", says=says,
                                interface=interface, **more)

        inputs, outputs = [], []
        for p, pr in decl.parameters.items():
            # Of an offered skill the value as deployed; of one that only runs as a step the type's default.
            value = current(parameter_port(spec, name, p), pr, self.snap) if offered else pr.default
            inputs.append(self.variable(p, XSD[pr.type], pr.description or f"Parameter {p}", f"{skill_id(name)}/Parameters/{p}",
                                        pr, value, means=self.means.get((name, p))))
            if offered:
                key = self.property(f"{name}_Parameter_{p}", f"{node}/Parameters/{p}", pr.type,
                                    f"{name} {p} of the current or last run", pr.unit)
                self.observe(key, key, f"{skill_id(name)}/Parameters/{p}", f"{name} {p} of the current or last run")
        for r in decl.results:
            source = result_input(spec, name, r)
            outputs.append(self.variable(r, XSD[source.type], f"Result {r}", f"{skill_id(name)}/Results/{r}", unit=source.unit))
            if offered:
                key = self.property(f"{name}_Result_{r}", f"{node}/Results/{r}", source.type, f"{name} result {r}", source.unit)
                self.observe(f"{name}_Result_{r}", key, f"{skill_id(name)}/Results/{r}", f"Result {r} of {name}")
        start = told("Start", f"Start {name}; the answer says whether it was accepted, its state how it went.",
                     parameters=decl.parameters, inputs=inputs, outputs=outputs)
        skill.Start = start
        if composite:
            start.Steps = self.steps(f"{name}.Execute", decl.execute, f"{node}/Execute", f"{name}_Execute",
                                     f"{skill_id(name)}/Execute", where, (*here, (SMC, "Start")), "Start", decl.results)
            # A module level skill has no type of its own: it is its Control block, a SKILL_Core.
            self.instances[f"{name}.Control"] = (CONTROL_TYPE, path(where, *here))
        else:
            skill.Contract = contract(decl)
            if offered:
                self.instances[name] = (block_type(spec, name), path(where, *here))
        if offered or (composite and decl.stop):
            stop = told("Stop", f"Stop {name}; the answer says whether it was accepted.")
            if composite and decl.stop:
                # Published below .../Stopping: a "Stop" object would collide with the Stop method.
                stop.Steps = self.steps(f"{name}.Stop", decl.stop, f"{node}/Stopping", f"{name}_Stopping",
                                        f"{skill_id(name)}/Stopping", where, (*here, (SMC, "Stop")), "Stop")
            skill.Stop = stop
        if offered:
            skill.Abort = told("Abort", f"Abort {name}; the answer says whether it was accepted.")
            skill.Reset = told("Reset", f"Reset {name}; the answer says whether it was accepted.")
            state = self.property(f"{name}_State", f"{node}/State", "USINT", f"{name} state: {SKILL_STATES}")
            self.observe(f"{name}_State", state, f"{skill_id(name)}/State", f"State of {name}: {SKILL_STATES}")
            error = self.property(f"{name}_ErrorID", f"{node}/ErrorID", "UINT", f"{name} error: {ERRORS}")
            self.observe(f"{name}_ErrorID", error, f"{skill_id(name)}/ErrorID", f"Why {name} last failed: {ERRORS}")
        return skill

    def module_control(self) -> dict[str, model.ModuleSkill]:
        """The module's own commands, each a skill of the kind ModuleControl that is called by its
        Start: who may use the module (Occupy, Release) and its state machine. What the module runs
        itself while resetting and stopping are the steps of Reset and of Stop. Its state and its
        occupation are data points."""
        spec, made = self.spec, {}

        def control(name: str, meaning: str, about: str, key: str, node: str, procedure: str | None = None):
            here = ((SMC, "Skills"), (SMC, name))
            skill = model.ModuleSkill(description=about, SemanticId=prop(meaning))
            skill.supplemental_semantic_ids = [f"{COMMAND}/ModuleControl"]
            start = self.command(arso.Start(), "Start", SKILLS, (*here, (SMC, "Start")), f"{COMMAND}/Start", about, key,
                                 node, says=[meaning])
            if procedure in spec.procedures:
                start.Steps = self.steps(procedure, spec.procedures[procedure], f"/Procedures/{procedure}",
                                         f"Procedure_{procedure}", f"{BASE_URL}/procedures/{procedure}", SKILLS,
                                         (*here, (SMC, "Start")), "Start")
            skill.Start = start
            made[name] = skill

        for name in ("Occupy", "Release"):
            control(name, skill_id(name), f"{name} the module for one client (its session)", f"Occupation_{name}",
                    f"/Occupation/{name}")
        occupied = self.property("Occupation_Occupied", "/Occupation/Occupied", "BOOL", "Occupied by a session")
        self.observe("OccupationState", occupied, OCCUPIED, "Occupied by a session: 0 free, 1 occupied")
        procedures = {"Reset": "Resetting", "Stop": "Stopping"}
        for m in MODULE_METHODS:
            control(m, f"{MODULE_STATE}/{m}", f"{m} the module (PackML); the answer says whether it was accepted.",
                    f"Module_{m}", f"/Module/{m}", procedures.get(m))
        state = self.property("Module_State", "/Module/State", "USINT", f"PackML state: {MODULE_STATES}")
        self.observe("PackMLState", state, MODULE_STATE, f"PackML state of the module: {MODULE_STATES}")
        return made

    # Submodels -------------------------------------------------------------------------------

    def mappings(self) -> Aimc:
        """How the interface reaches the other submodels (AIMC): every property of the interface
        feeds its Operational Data point, and every action of the interface is invoked by one
        Operation (a command of a skill, in this AAS or in a component's; a command of the module)."""
        def identity(id_short: str, feeds: dict[str, ModelReference]) -> object:
            lines = "\n".join(f"        {key} = sources.{key}," for key in feeds)
            return mapping_configuration(
                id_short=id_short, sources=[source(key, affordance("properties", key)) for key in feeds],
                sinks=[sink(key, sinks) for key, sinks in feeds.items()],
                transformation=f"function aimc_main(sources)\n    return {{\n{lines}\n    }}\nend\n")

        data = {key: path(DATA, ("Property", point)) for point, (key, _, _) in self.datapoints.items()}
        mappings = [identity("OPCUA", data)]
        for action, (at, arguments) in self.operations.items():
            fields = "\n".join(f"            {a} = op.{a}," for a in arguments)
            mappings.append(mapping_configuration(
                id_short=action, sources=[source(action, at)], sinks=[sink(action, affordance("actions", action))],
                transformation=(f"-- {action}: the invocation's inputs become the arguments of the OPC UA method, in this order\n"
                                f"function aimc_main(sources)\n    local op = sources.{action}\n    return {{\n"
                                f"        {action} = {{\n{fields}\n        }},\n    }}\nend\n")))
        return Aimc(id_short="AssetInterfacesMappingConfiguration",
                    MappingConfigurations=AimcMappingConfigurations(value=mappings))

    def capabilities(self) -> model.ModuleCapabilityDescription | None:
        """The capabilities the module offers (IDTA 02020): each with its meaning, its properties
        (a value or a range, with a unit) and the skill realizing it (CapabilityRealizedBy, a
        reference into the Skills submodel). The skill does not refer back: a parameter of it that
        sets a property of the capability means what that property means (``variable``)."""
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
                id_short="RealizedBy", first=capability_path(name), second=path(self.home(cap.realized_by), (SMC, "Skills"), (SMC, cap.realized_by)))
            containers[name] = model.ModuleCapabilityContainer(
                id_short=name, Capability=capability,
                PropertySet={"PropertySet": cd.PropertySet(id_short="PropertySet", PropertyContainer=properties)} if properties else {},
                CapabilityRelations=model.ModuleCapabilityRelations(id_short="CapabilityRelations",
                                                                    CapabilityRealizedBy={"RealizedBy": realized}))
        if not containers:
            return None
        return model.ModuleCapabilityDescription(id_short="CapabilityDescription", CapabilitySet={
            OFFERED_SET: model.ModuleCapabilitySet(id_short=OFFERED_SET, CapabilityContainer=containers)})

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
        instances = {}
        for instance, (typ, what) in self.instances.items():
            # The type its instance has on a module that was read, else as the module's rules name it.
            typ = (snap.fbs.get(instance) if snap else None) or typ
            known = snap.hashes.get(typ) if snap else None
            instances[instance.replace(".", "_")] = cc.CCfgInstance(
                InstancePath=prop(instance), FBType=prop(typ), TypeHash=prop(known) if known else None,
                Skill=ReferenceElement(value=what))
        return model.ModuleControlConfiguration(
            id_short="ControlConfiguration",
            Runtime=cc.Runtime(Name=prop("Eclipse 4diac FORTE"), Resource=prop(snap.resource if snap else "RES"),
                               ManagementEndpoint=prop(f"{snap.host}:{snap.port}" if snap else f"{t.host}:{t.port}")),
            Rules=prop(RULES, description="The rule set the program is built by: its shell, the interface of a "
                       "skill primitive and the pattern of a module level skill."),
            ModuleSpec=prop(self.spec_path or ""), Target=prop(self.target), Generator=prop("modgen"),
            ProgramDigest=prop(program_digest(self.spec, self.target),
                               description="SHA-256 of the program the module spec generates for the target."),
            SyncState=prop(sync, description="InSync: the running program is the one the module spec generates; Drift: "
                           "it differs (see Differences); NoProgram: the runtime has none; NotRead: from the spec only."),
            ReadAt=prop(snap.read_at if snap else ""), Differences=cc.Differences(CCfgDifference=differences),
            Types=cc.Types(CCfgType=types), Instances=cc.Instances(CCfgInstance=instances))

    def errors(self, held: arso.Errors) -> None:
        for name, code in ERROR_CODES.items():
            put(held.Error, name, arso.Error(ErrorCode=prop(code, "xs:integer")))

    def build(self) -> list[tuple[ModuleTypeAAS | ComponentTypeAAS, str]]:
        """The module and its components, each with the id of its asset."""
        spec = self.spec
        id_short, aas_id, asset_id = identity(spec)
        asset = ModuleTypeAAS(id_short=id_short, id=aas_id, asset_type=spec.aas.asset_type or f"{model.RESOURCE}/Module",
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
        control = self.module_control()
        parts = {item: ComponentTypeAAS(
            id_short=found[0], id=found[1], asset_type=found[3],
            description=f"{spec.equipment[item].description or item}: a component of the {spec.module} module, which carries out its skills")
            for item in self.components for found in [component_identity(spec, item)]}
        for name in [*spec.composites, *spec.skills]:
            decl = spec.skills.get(name)
            item = decl.equipment if decl is not None and decl.equipment in parts else None
            if name in control:
                raise ValueError(f"{name} is a command of the module itself: a skill cannot be called that")
            put((parts[item] if item else asset).skills.Skills.Skill, name, self.skill(name))
        for name, made in control.items():
            put(asset.skills.Skills.Skill, name, made)
        for held in (asset, *parts.values()):
            self.errors(held.skills.Errors)
        nodes = {}
        for item, eq in spec.equipment.items():
            # A component is found by its asset id; an item no skill moves is only a part.
            nodes[item] = Node(entity_type="SelfManagedEntity" if item in parts else "CoManagedEntity",
                               global_asset_id=component_identity(spec, item)[2] if item in parts else "",
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
        asset.capability_description = self.capabilities()
        asset.asset_interfaces_mapping_configuration = self.mappings()
        asset.control_configuration = self.control_configuration()
        return [(ModuleTypeAAS.model_validate(asset.model_dump()), asset_id),
                *[(ComponentTypeAAS.model_validate(part.model_dump()), component_identity(spec, item)[2])
                  for item, part in parts.items()]]


def describe_all(spec: ModuleSpec, target: str, snap: Snapshot | None = None, drift: Drift | None = None,
                 spec_path: str | None = None, opcua: str | None = None) -> list[dict]:
    """The profiles of the module (the first) and of its components; with a snapshot, values, hashes
    and the sync state are the running ones."""
    return [model.profile(asset, global_asset_id=asset_id)
            for asset, asset_id in Describer(spec, target, snap, drift, spec_path, opcua).build()]


def describe(spec: ModuleSpec, target: str, snap: Snapshot | None = None, drift: Drift | None = None,
             spec_path: str | None = None, opcua: str | None = None) -> dict:
    """The module's own profile (its components have theirs: ``describe_all``)."""
    return describe_all(spec, target, snap, drift, spec_path, opcua)[0]
