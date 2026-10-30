"""A module's AAS in the structure of the resource ontology (ARSO), from its module spec and, when
read, what runs on it.

``describe`` fills a ``Module``, and ``describe_all`` also a ``Component`` for every
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
- **Variables** (aas-model's) with the mapping that feeds them (Asset Interfaces Mapping
  Configuration): module state, occupation, skill and step states, parameters and results,
  equipment inputs, as decimal data points. A data point means what the Operation variable it shows
  means (that id is its supplemental semantic id); nothing in Skills refers to it. In
  ``Measurements/Coordinates``: where the module, its mounts, end effectors and points are.
- **Hierarchical Structures**: the components, each with an AAS of its own, found by its asset id.
- **Skills** also say which rule set the program is built by (RuleSet) and, per module level
  skill, that the program carries it out (Deployment Built).

What was built is not part of the AAS (ARSO 0.10): ``describe_with_record`` also gives the
integrator's record, a Control Configuration submodel kept outside the AAS: spec, target and
program digest, which block of the program each skill and each step is (Instances), and from a
module that was read the synchronisation state, the differences and the type hashes.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json

from aas_model.constants import AID_WOT_NAME, BASE_URL
from aas_model.json_schema_aid import datapoint_from_schema
from aas_model.resource_template import skill_operation
from aas_model.resource_template._helpers import put
from aas_model.resource_template.asset_interfaces_mapping_configuration import (
    mapping_configuration, response_sink, response_source, series_segment_ref, sink, source,
)
from aas_model.submodel_templates import (
    Aimc, AimcMappingConfigurations, DmpActionInput, DmpActionOutput, DmpProperty, OpcuaAction,
    DmpProperties, OpcuaActions, ReadOnly, Synchronous, UavComponentOf,
)
from aas_pydantic import Capability, Key, ModelReference, Property, Qualifier, ReferenceElement
from aas_pydantic.submodel_templates import asset_interfaces_description as wot
from aas_pydantic.submodel_templates import capability_description as cd
from aas_pydantic.submodel_templates.hierarchical_structures import ArcheType
from aas_pydantic.submodel_templates.nameplate import ManufacturerProductDesignation, SerialNumber

from modgen.library import q
from modgen.module import parameter_port
from modgen.spec import (AllOf, AnyOf, Capability as CapabilitySpec, CapabilityProperty, Decision, ModuleSpec, Parallel,
                         Parameter, Step, walk)
from modsync.compare import Drift, expected, expected_values
from modsync.device import Snapshot, literal

from . import model
from .derive import Offer, local, offers as derived_offers
from .projection import project
from aas_model.submodel_templates.arso import control_configuration as cc, skills as arso
from aas_model.submodel_templates.control_component_instance import OptionalVariable
from aas_model.submodel_templates.coordinates import (
    CoordinateRelativeTo, CoordinateSource, Coordinates, CoordinatePitch, CoordinateRoll, CoordinateX, CoordinateY,
    CoordinateYaw, CoordinateZ, RelativeCoordinate,
)
from aas_model.submodel_templates.time_series import operation_log, record_field, time_series
from aas_model.submodel_templates.variables import LogGroup, MeasurementsGroup, StateGroup
from .lab import nameplate
from .model import Component, Module

AID = "{aas_id}/submodels/AssetInterfacesDescription"
SKILLS = "{aas_id}/submodels/Skills"
STRUCTURE = "{aas_id}/submodels/HierarchicalStructures"
DATA = "{aas_id}/submodels/Variables"
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
# The concepts of the two values every resource of the lab has.
MODULE_STATE = "https://w3id.org/2026/apex/semantic/state/operational"
# The rules a generated module is built by (docs/module-rules.md); 2 adds parallel blocks and decisions to 1.
RULES = f"{BASE_URL}/rules/module/2"
OCCUPIED = "https://w3id.org/2026/apex/semantic/state/occupied"
# What a skill can be told: a command means the same on every skill (ontology/Vocabulary/commands.ttl).
COMMAND = f"{BASE_URL}/skill"
# The variables of the skill protocol (the session, the answer), not parameters of the skill: the
# planner, the skill editor and the projection tell them apart by this id. aas-model gave it to every
# Operation variable until its variables became plain Properties; here it is stated where it holds.
PROTOCOL_VARIABLE = f"{BASE_URL}/ControlComponent/Skill/OperationVariable/1/0"


def text(value) -> str:
    """A value as the AAS writes it."""
    return str(value).lower() if isinstance(value, bool) else str(value)


def prop(value, value_type: str = "xs:string", description: str = "") -> dict:
    """A Property as the content of the field it goes into: the class aas-model's generator made for
    that field adds its semantic id (its description is the one given here)."""
    return {"value": text(value), "value_type": value_type, "description": description}


def ref(value: ModelReference) -> dict:
    """A ReferenceElement as the content of the field it goes into (see ``prop``)."""
    return {"value": value}


def path(submodel: str, *steps: tuple[str, str]) -> ModelReference:
    return ModelReference(key=(Key(type_="Submodel", value=submodel), *(Key(type_=t, value=v) for t, v in steps)))


def affordance(kind: str, key: str, *inside: str) -> ModelReference:
    """An action or a property of the OPC UA interface, or a part of it (an action's ``input``)."""
    return path(AID, (SMC, "interface_opcua"), (SMC, "InteractionMetadata"), (SMC, kind), (SMC, key),
                *((SMC, part) for part in inside))


def skill_id(name: str) -> str:
    return f"{model.SKILL}/{name}"


def meaning(name: str, given: str | None = None) -> str:
    """What a capability or capability property means: the spec's IRI, else the lab's."""
    return given or f"{BASE_URL}/semantics/{name}"


COORDINATES = ((SMC, "Measurements"), (SMC, "Coordinates"))
# The module's own state, a series of its own.
MODULE_STATE_POINTS = ("PackMLState", "OccupationState")
# What a series holds, by its name, else by its group.
SERIES_ABOUT = {
    "Module": "The module's PackML state and its occupation, as they change",
    "Procedures": "The steps of the module's procedures (resetting, stopping): their state and error, as they run",
    "State": "A run of the skill {series}: its state, error, parameters and results, and those of its steps",
    "Measurements": "The inputs of {series}, as they change",
}


def series_of(spec: ModuleSpec, name: str) -> tuple[str, str]:
    """Where the value a module publishes as ``name`` is kept: the group of its Variables and the time
    series in it. A series holds what changes together: the module's state and occupation (State/Module),
    one skill's run with its steps (State/<Skill>), the procedures' (State/Procedures), and one item of
    equipment's inputs (Measurements/<Item>)."""
    if name in MODULE_STATE_POINTS:
        return "State", "Module"
    for item, eq in spec.equipment.items():
        if name.startswith(f"{item}_") and name[len(item) + 1:] in eq.inputs:
            return "Measurements", item
    if name.startswith("Procedure_"):
        return "State", "Procedures"
    return "State", name.split("_", 1)[0]


def record_field_ref(group: str, series: str, name: str, aas_id: str | None = None) -> ModelReference:
    """The field ``name`` of the series ``group/series`` of the Variables of this AAS (``aas_id`` None)
    or of the AAS ``aas_id``: where a value is found in the time series database."""
    return path(DATA if aas_id is None else f"{aas_id}/submodels/Variables", (SMC, group), (SMC, series),
                (SMC, "Metadata"), (SMC, "Record"), ("Property", name))


def field_ref(spec: ModuleSpec, name: str) -> ModelReference:
    """The record field of the value the module publishes as ``name``."""
    return record_field_ref(*series_of(spec, name), name)


def coordinate_ref(name: str, aas_id: str | None = None) -> ModelReference:
    """The coordinate ``name`` of this AAS (``aas_id`` None) or of the AAS ``aas_id``."""
    return path(DATA if aas_id is None else f"{aas_id}/submodels/Variables", *COORDINATES, (SMC, name))


def coordinate(name: str, meant: str | None = None, location=None, relative_to: ModelReference | None = None,
               sources: dict[str, ModelReference] | None = None, description: str = "") -> RelativeCoordinate:
    """A coordinate: ``location`` (x, y, z, rx, ry, rz; none: zero) relative to ``relative_to`` (none:
    a root, or not placed yet), in mm and degrees; ``meant`` a meaning of the vocabulary; ``sources``
    the record field each moving value is (``{"Z": <Measurements/LinearAxis/.../LinearAxis_ActualPosition>}``)."""
    given = [float(getattr(location, a, 0.0)) if location is not None else 0.0 for a in ("x", "y", "z", "rx", "ry", "rz")]
    made = RelativeCoordinate(
        id_short=name, description=description, supplemental_semantic_ids=[meaning(meant)] if meant else [],
        X=CoordinateX(value=text(given[0])), Y=CoordinateY(value=text(given[1])), Z=CoordinateZ(value=text(given[2])),
        Roll=CoordinateRoll(value=text(given[3])), Pitch=CoordinatePitch(value=text(given[4])),
        Yaw=CoordinateYaw(value=text(given[5])))
    if relative_to is not None:
        made.RelativeTo = CoordinateRelativeTo(value=relative_to)
    for value, field in (sources or {}).items():
        made.source[f"{value}Source"] = CoordinateSource(id_short=f"{value}Source", value=field)
    return made


def capability_path(name: str) -> ModelReference:
    return path(CAPABILITIES, (SMC, OFFERED_SET), (SMC, name), ("Capability", "Capability"))


def schema(parameters: dict[str, Parameter], argument=None) -> dict:
    """The arguments of a method as a JSON Schema object, in call order (the session first), named
    as the server names them (``argument``, by default as FORTE does); what each one is, is its title."""
    argument = argument or forte_argument
    fields = {argument(1, "Session"): {"type": "string", "title": "Session", "description": "Occupation session of the caller"}}
    for i, (name, pr) in enumerate(parameters.items(), 2):
        field = {"type": "number", "title": name, "description": pr.description or f"Parameter {name}", "default": pr.default}
        field.update({k: v for k, v in (("minimum", pr.minimum), ("maximum", pr.maximum)) if v is not None})
        fields[argument(i, name)] = field
    return {"type": "object", "properties": fields}


def answer(argument=None) -> dict:
    """What every method answers: whether the command was accepted, and why not."""
    argument = argument or forte_argument
    return {"type": "object", "properties": {
        argument(1, "Accepted", True): {"type": "boolean", "title": "Accepted"},
        argument(2, "ErrorID", True): {"type": "integer", "title": "ErrorID", "minimum": 0, "maximum": 65535}}}


def forte_argument(n: int, name: str, out: bool = False) -> str:
    """The name of a method's ``n``th input (or output) argument, ``name``. FORTE's OPC UA server
    names them after the data ports of the SERVER block that serves the method: an input after the
    block's output that receives it (RD_1, RD_2, ...), an output after the block's input that sends it
    (SD_1, SD_2, ...). The DMP calls a method with its arguments by name."""
    return f"{'SD' if out else 'RD'}_{n}"


def block_type(spec: ModuleSpec, skill: str) -> str:
    """The function block type of a skill primitive, as modgen names it."""
    return f"{spec.package}::SK_{skill}"


def declared_parameter(name: str, pr: Parameter, value) -> Property:
    """A skill parameter holding ``value``, with its declaration (unit, limits, default) as qualifiers."""
    declared = (("Unit", pr.unit), ("Minimum", pr.minimum), ("Maximum", pr.maximum), ("Default", pr.default))
    return Property(
        value=text(value), value_type=XSD[pr.type], description=pr.description or f"Parameter {name}",
        qualifiers=[Qualifier(type_=k, value=text(v), kind="ConceptQualifier") for k, v in declared if v is not None])


def stated(terms: dict) -> dict:
    """The terms as properties, without those not given or plainly true."""
    return {k: prop(v) for k, v in terms.items() if v is not None and v != "TRUE"}


def conditions(decl) -> arso.Conditions_2 | None:
    """What has to hold when a primitive starts, when it has succeeded and while it runs, as the
    module spec states it (``Conditions_2``: a decision's group of conditions is ``Conditions``)."""
    terms = stated({"Precondition": decl.precondition, "Postcondition": decl.postcondition, "Invariant": decl.invariant})
    return arso.Conditions_2(**terms) if terms else None


def completion(decl) -> arso.Completion | None:
    """How a primitive ends when no Postcondition ends it, and the longest it may run."""
    # A time ends it by itself: the longest it may run is said only where a sensor ends it.
    terms = stated({"After": decl.after if decl.postcondition is None else None,
                    "Timeout": decl.timeout if decl.postcondition is not None else None})
    return arso.Completion(**terms) if terms else None


MODULE_METHODS = ["Reset", "Start", "Stop", "Abort", "Clear"]


def identity(spec: ModuleSpec) -> tuple[str, str, str]:
    """(idShort, id, globalAssetId) of the module's shell."""
    id_short = spec.aas.id_short or f"{spec.module}ModuleAAS"
    return (id_short, spec.aas.id or f"{BASE_URL}/aas/{id_short}",
            spec.aas.global_asset_id or f"{BASE_URL}/assets/{spec.module}Module")


def browse_path(spec: ModuleSpec, path: str, namespace: int = 1) -> str:
    """OPC UA RelativePath text of a node below the module's root (FORTE's nodes are in namespace 1)."""
    parts = [p for p in spec.opcua_root.split("/") if p][1:] + [p for p in path.split("/") if p]
    return "/0:Objects" + "".join(f"/{namespace}:{p}" for p in parts)


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
        step = next(s for s in walk(spec.composites[skill].execute) if s.name == step_name)
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
        self.namespace = 1                                      # of the module's nodes on its OPC UA server
        self.actions: dict[str, OpcuaAction] = {}
        self.properties: dict[str, DmpProperty] = {}
        self.datapoints: dict[str, tuple[str, str, str]] = {}    # data point -> (interface property, concept, title)
        # Action of the interface -> (the Operation that invokes it, its arguments in call order)
        self.operations: dict[str, tuple[ModelReference, list[str]]] = {}
        # Block of the program -> (its type as the module's rules name it, the skill or step it is)
        self.instances: dict[str, tuple[str, ModelReference]] = {}
        self.module_id = identity(spec)[1]
        # The components: every item of equipment that a skill moves.
        self.components = [item for item in spec.equipment if any(d.equipment == item for d in spec.skills.values())]
        # The capabilities are derived from the AASs this writes; the pass that derives them writes none.
        self.derive = True

    def means_of(self, skill: str, p: str) -> str | None:
        """What a parameter of a skill means: as the spec says, else (a module level skill's) what
        the parameter of a step it is handed to means."""
        composite = self.spec.composites.get(skill)
        said = (composite or self.spec.skills[skill]).parameters[p].meaning
        if said:
            return said if "://" in said else meaning(said)
        for step in walk(composite.execute) if composite else ():
            handed = [q for q, v in step.bind.items() if v == p]
            if found := next((m for q in handed if (m := self.means_of(step.skill, q))), None):
                return found
        return None

    # Interface -------------------------------------------------------------------------------

    def argument(self, n: int, name: str, out: bool = False) -> str:
        """The name the module's OPC UA server gives a method's ``n``th argument, ``name``: FORTE's."""
        return forte_argument(n, name, out)

    def action(self, key: str, node: str, title: str, parameters: dict[str, Parameter] | None = None) -> str:
        href = browse_path(self.spec, node, self.namespace)
        # FORTE gives its nodes new numeric ids at every start, so the owning object is named by
        # its browse path, where OPC 10101 has its NodeId.
        action = OpcuaAction(uav_componentOf=UavComponentOf(value=href.rpartition("/")[0]))
        action.title = wot.Title(value=title)
        # The call answers at once with Accepted and ErrorID; the skill's progress is its State.
        action.synchronous = Synchronous(value="true")
        action.input = datapoint_from_schema(schema(parameters or {}, self.argument), cls=DmpActionInput)
        action.output = datapoint_from_schema(answer(self.argument), cls=DmpActionOutput)
        action.forms.href.value = href
        action.forms.uav_browsePath = wot.UavBrowsePath(value=href)
        self.actions[key] = action
        return key

    def property(self, key: str, node: str, iec: str, title: str, unit: str | None = None) -> str:
        href = browse_path(self.spec, node, self.namespace)
        p = DmpProperty()
        p.key = wot.Key(value=key)
        p.title = wot.Title(value=title)
        p.type = wot.Type(value=JSON.get(iec, "integer"))
        p.observable = wot.Observable(value="true")
        if unit:
            p.unit = wot.Unit(value=unit)
        # The module publishes it; a client reads and observes it, never writes it.
        p.readOnly = ReadOnly(value="true")
        p.forms.href.value = href
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
        return ReferenceElement(value=path(self.home(name), (SMC, name)))

    def variable(self, name: str, value_type: str, about: str, concept: str | None = None, pr: Parameter | None = None,
                 value=None, unit: str | None = None, means: str | None = None) -> Property:
        """A variable of an Operation. A parameter carries its value (the default, or what the module
        runs with), its unit and its limits; ``concept`` is what the data point showing it means too,
        ``means`` what it is in a product's terms."""
        declared = [("Unit", pr.unit if pr else unit), ("Minimum", pr.minimum if pr else None),
                    ("Maximum", pr.maximum if pr else None), ("Default", pr.default if pr else None)]
        made = Property(
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
        ``outputs`` out. With ``key`` it invokes that action of the interface: the AAS server
        delegates the call to the DMP, which calls the method as the AIMC maps it."""
        op = arso.SkillOperation(id_short="operation", qualifiers=skill_operation(key or "local", synchronous=True).qualifiers)
        if not key:
            op.qualifiers = []                      # nothing calls it: it only declares the variables
        op.semantic_id = meaning_id
        op.description = about
        op.in_output_variable = []
        op.input_variable = [self.variable("Session", "xs:string", "Occupation session of the caller", PROTOCOL_VARIABLE), *inputs]
        # The method answers at once; the results come when the skill is done, so the answer leaves
        # them out (the DMP requires every output not marked optional).
        for result in outputs:
            result.qualifiers = [*result.qualifiers, OptionalVariable()]
        op.output_variable = [self.variable("Accepted", "xs:boolean", "The command was accepted", PROTOCOL_VARIABLE),
                              self.variable("ErrorID", "xs:unsignedShort", f"Why it was refused or failed: {ERRORS}", PROTOCOL_VARIABLE),
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
            self.actions[key].supplemental_semantic_ids = [AID_WOT_NAME, *(says or [meaning_id])]
            made.InterfaceReference = arso.InterfaceReference(value=path(
                interface, (SMC, "interface_opcua"), (SMC, "InteractionMetadata"), (SMC, "actions"), (SMC, key)))
        put(made.SkillOperation, name, self.operation(key, path(where, *at, ("Operation", name)), about, meaning_id,
                                                      inputs, outputs))
        return made

    def steps(self, owner: str, sequence, node: str, key: str, concept: str, where: str, at: tuple, command: str,
              results: dict[str, str] | None = None, inside: tuple = ()):
        """What a command runs, as a flow in the planner's elements: steps Step_0000, ... with their
        NodeId (the name of the step's instance in the program), Kind, Name and Order. A step of
        the kind ``step`` refers to the skill it runs. Its Bindings say what each input of that
        skill is handed: a constant as it runs on the module (Value), or a variable of the
        command's Operation (SourceElement). Its Outputs say which results of the command it gives
        (``results``, output -> "<step>.<its result>"). A step means what its instance in the
        program is called (``concept``/<step>, a supplemental id): its state and what it publishes
        below ``node`` are data points named from there.

        A parallel block (rule set 2) is a step of the kind ``parallel`` with its Branches, a decision
        one of the kind ``decision`` with its Condition and two Branches (``conditional`` with its own
        Steps when the second is empty); ``inside`` is where these Steps are below the command."""
        held = arso.Steps()
        own = lambda v: path(where, *at, ("Operation", command), ("Property", v))    # noqa: E731
        here = lambda id_short: path(where, *at, *inside, (SMC, "Steps"), (SMC, id_short))  # noqa: E731
        below = lambda id_short, *more: (*inside, (SMC, "Steps"), (SMC, id_short), *more)    # noqa: E731
        everything = list(walk(self.spec.composites[owner.split(".")[0]].execute)) if owner.split(".")[0] in self.spec.composites else []
        parameters = self.spec.composites[owner.split(".")[0]].parameters if owner.split(".")[0] in self.spec.composites else {}

        def condition(c, order: int | None = None) -> arso.FlowCondition:
            """A comparison, or a group of them (all, any), in the planner's elements."""
            numbered = {"Order": arso.Order(value=str(order), value_type="xs:nonNegativeInteger")} if order is not None else {}
            if isinstance(c, (AllOf, AnyOf)):
                kind = "all" if isinstance(c, AllOf) else "any"
                group = arso.FlowConditions()
                for i, inner in enumerate(getattr(c, kind)):
                    put(group.Condition, f"Condition_{i:04d}", condition(inner, i))
                return arso.FlowCondition(ConditionType=arso.ConditionType(value=kind), Conditions=group, **numbered)
            step_name, _, result = c.operand.partition(".")
            if result:
                ran = next(s for s in everything if s.name == step_name)
                io = result_input(self.spec, ran.skill, result)
                operand = arso.Operand(OperandType=arso.OperandType(value="output"), StepId=arso.StepId(value=step_name),
                                       OutputId=arso.OutputId(value=result))
                typ, unit = io.type, io.unit
            else:
                declared_ = parameters[c.operand]
                operand = arso.Operand(OperandType=arso.OperandType(value="parameter"), StepId=arso.StepId(value=""),
                                       SourceElement=arso.SourceElement(value=own(c.operand)))
                typ, unit = declared_.type, declared_.unit
            expected = arso.Expected(DataType=arso.DataType(value="boolean" if typ == "BOOL" else "number"),
                                     Value=arso.Value(value=text(c.value) if isinstance(c.value, bool) else text(float(c.value)),
                                                      value_type="xs:boolean" if typ == "BOOL" else "xs:double"))
            return arso.FlowCondition(ConditionType=arso.ConditionType(value="comparison"), Operator=arso.Operator(value=c.op),
                                  Unit=arso.Unit(value=unit or ""), Expected=expected, Operand=operand, **numbered)

        def branch(order: int, id_short: str, name: str, nodes: list) -> arso.FlowBranch:
            j = f"Branch_{order:04d}"
            return arso.FlowBranch(BranchId=arso.BranchId(value=f"{name}_{order + 1}"), Name=arso.Name(value=f"{name} {order + 1}"),
                                   Order=arso.Order(value=str(order), value_type="xs:nonNegativeInteger"),
                                   Steps=self.steps(owner, nodes, node, key, concept, where, at, command, results,
                                                    below(id_short, (SMC, "Branches"), (SMC, j))))

        def of_skill(name: str, variable: str) -> ModelReference:
            return path(self.home(name), (SMC, name), (SMC, "Start"), ("Operation", "Start"),
                        ("Property", variable))

        for order, step in enumerate(sequence):
            id_short = f"Step_{order:04d}"
            common = dict(NodeId=arso.NodeId(value=step.name), Name=arso.Name(value=step.name),
                          Order=arso.Order(value=str(order), value_type="xs:nonNegativeInteger"))
            if isinstance(step, Parallel):
                made = arso.SkillStep(Kind=arso.Kind(value="parallel"), description=f"{step.name}: runs its branches at once",
                                      Branches=arso.Branches(FlowBranch={f"Branch_{j:04d}": branch(j, id_short, step.name, b)
                                                                         for j, b in enumerate(step.branches)}), **common)
                self.instances[f"{owner}.{step.name}"] = (q(f"SKILL_Join{len(step.branches)}"), here(id_short))
                put(held.SkillStep, id_short, made)
                continue
            if isinstance(step, Decision):
                made = arso.SkillStep(Condition=condition(step.condition), description=f"{step.name}: runs a branch by its condition",
                                      Kind=arso.Kind(value="decision" if step.otherwise else "conditional"), **common)
                if step.otherwise:
                    made.Branches = arso.Branches(FlowBranch={f"Branch_{j:04d}": branch(j, id_short, step.name, b)
                                                              for j, b in enumerate((step.then, step.otherwise))})
                else:
                    made.Steps = self.steps(owner, step.then, node, key, concept, where, at, command, results, below(id_short))
                self.instances[f"{owner}.{step.name}"] = (q("SKILL_Merge"), here(id_short))
                put(held.SkillStep, id_short, made)
                continue
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
            self.instances[f"{owner}.{step.name}"] = (block_type(self.spec, step.skill), here(id_short))
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
        Stop; a primitive runs nothing and states what ends it (Conditions, Completion). A skill the module offers
        has an action per command and publishes its state, why it last failed, its parameters and
        its results as data points; one that only runs as a step has a Start that nothing calls."""
        spec = self.spec
        composite = name in spec.composites
        decl = spec.composites[name] if composite else spec.skills[name]
        item = decl.equipment if not composite and decl.equipment in self.components else None
        offered, node, here = decl.offered, f"/Skills/{name}", ((SMC, name),)
        where = self.home(name)                         # as the module sees it (the mapping is the module's)
        interface = AID if item is None else f"{self.module_id}/submodels/AssetInterfacesDescription"
        # Every skill is the same kind of element; what kind of skill it is and what it does (its
        # type) are said beside it, as supplemental semantic ids.
        skill = model.ModuleSkill(description=decl.description or f"Skill {name}")
        skill.supplemental_semantic_ids = [f"{COMMAND}/{'Composite' if composite else 'Primitive'}", skill_id(name)]
        if composite and decl.capability:
            skill.supplemental_semantic_ids.append(meaning(decl.capability))      # what it was written for
        if composite:
            # Generated from the spec, so the program carries it out.
            skill.Deployment = arso.Deployment(**prop("Built"))

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
                                        pr, value, means=self.means_of(name, p)))
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
            skill.Conditions, skill.Completion = conditions(decl), completion(decl)
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
            here = ((SMC, name),)
            skill = model.ModuleSkill(description=about)
            skill.supplemental_semantic_ids = [f"{COMMAND}/ModuleControl", meaning]
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

    def coordinates(self) -> Coordinates:
        """Where the module and its points are: its base, not placed until it is put on a line; for an
        item with a location, its mount, and for an axis also its end effector, which moves along the
        mount's Z axis as the axis' actual position (a record field); its points of interest."""
        spec, base = self.spec, coordinate_ref("ModuleBase")
        found = {"ModuleBase": coordinate("ModuleBase", "ModuleBase", description=f"The base of the {spec.module} module")}
        for item, eq in spec.equipment.items():
            if eq.location is None:
                continue
            actual = f"{item}_ActualPosition"
            if eq.position is not None and actual in self.datapoints:
                found[f"{item}Mount"] = coordinate(f"{item}Mount", "Mount", eq.location, base,
                                                   description=f"Where {item} is mounted, at its zero; Z along its travel")
                found[item] = coordinate(item, "EndEffector", None, coordinate_ref(f"{item}Mount"), {"Z": field_ref(spec, actual)},
                                         description=f"The tool point of {item}, its actual position along the mount's Z")
            else:
                found[item] = coordinate(item, None, eq.location, base, description=eq.description or f"Equipment {item}")
        for name, point in spec.points.items():
            found[name] = coordinate(name, point.meaning, point.location, base,
                                     description=point.description or f"{point.meaning} of the {spec.module} module")
        return Coordinates(coordinate=found)

    def interface_and_data(self, asset: Module):
        """Put the actions, properties and data points described so far into ``asset``."""
        interface = asset.asset_interfaces_description.InterfaceTemplateForOPCUA["interface_opcua"]
        # aas-model leaves a container out until something is in it.
        interface.InteractionMetadata.actions = interface.InteractionMetadata.actions or OpcuaActions()
        interface.InteractionMetadata.properties = interface.InteractionMetadata.properties or DmpProperties()
        for key, action in self.actions.items():
            put(interface.InteractionMetadata.actions.property_name, key, action)
        for key, p in self.properties.items():
            put(interface.InteractionMetadata.properties.property_name, key, p)
        # No value is kept in the AAS: each is a field of a time series, whose rows are in the time
        # series database; the series says where (aas-model's Variables, IDTA 02008 as SMCs). A field
        # is a decimal (states and counts as their number, a Boolean as 0 or 1); what it shows is its
        # supplemental semantic id.
        made = {group: {series: time_series(
                    name=f"{series} ({group})", measurement=f"{group}_{series}".lower(),
                    description=SERIES_ABOUT.get(series, SERIES_ABOUT[group]).format(series=series),
                    fields={name: record_field("xs:decimal", concept=concept, description=title)
                            for name, (_, concept, title) in points.items()})
                         for series, points in found.items()}
                for group, found in self.series().items()}
        if made.get("State"):
            asset.variables.State = StateGroup(value=made["State"])
        if made.get("Measurements"):
            asset.variables.Measurements = MeasurementsGroup(value=made["Measurements"])
        # Every call of a command is logged: how it ended, how long it took, and the variables of its
        # Operation (referenced, so they follow its definition: the session, the parameters, the answer).
        if self.operations:
            asset.variables.Log = LogGroup(value={
                action: operation_log(at, name=f"{action} calls", measurement=f"log_{action}".lower())
                for action, (at, _) in self.operations.items()})

    def series(self) -> dict[str, dict[str, dict[str, tuple[str, str, str]]]]:
        """The values described so far by group and series (``series_of``): name -> (interface
        property, concept, title)."""
        found: dict[str, dict[str, dict[str, tuple[str, str, str]]]] = {}
        for name, point in self.datapoints.items():
            group, series = series_of(self.spec, name)
            found.setdefault(group, {}).setdefault(series, {})[name] = point
        return found

    def mappings(self) -> Aimc:
        """How the interface reaches the other submodels (AIMC): the properties of the interface give
        the rows of the time series (one mapping per series: each property a field, the row written to
        the series' segment in the database), and every action of the interface is invoked by one
        Operation (a command of a skill, in this AAS or in a component's; a command of the module)."""
        mappings = []
        for group, found in self.series().items():
            for series, points in found.items():
                # A field is a decimal: a Boolean is written as 0 or 1.
                flags = {name for name, (key, _, _) in points.items() if self.properties[key].type.value == "boolean"}
                lines = "\n".join(f"            {name} = {'number(' if name in flags else ''}sources.{name}{')' if name in flags else ''},"
                                  for name in points)
                number = "local function number(flag)\n    if flag == nil then return nil end\n    return flag and 1 or 0\nend\n\n"
                mappings.append(mapping_configuration(
                    id_short=f"{group}_{series}",
                    sources=[source(name, affordance("properties", key)) for name, (key, _, _) in points.items()],
                    sinks=[sink("Live", series_segment_ref(group, series))],
                    transformation=(f"-- A row of {group}/{series}: each property of the interface is the field of its name\n"
                                    f"{number if flags else ''}"
                                    f"function aimc_main(sources)\n    return {{\n        Live = {{\n{lines}\n        }},\n    }}\nend\n")))
        for action, (at, arguments) in self.operations.items():
            fields = "\n".join(f"            {self.argument(i, a)} = op.{a}," for i, a in enumerate(arguments, 1))
            mappings.append(mapping_configuration(
                id_short=action, sources=[source(action, at)], sinks=[sink(action, affordance("actions", action, "input"))],
                transformation=(f"-- {action}: the invocation's inputs are the arguments of the OPC UA method, in this order\n"
                                f"function aimc_main(sources)\n    local op = sources.{action}\n    return {{\n"
                                f"        {action} = {{\n{fields}\n        }},\n    }}\nend\n"),
                # The method's answer is the Operation's: whether the command was accepted, and why not.
                # The call is logged as well, also one that failed (then only its log row is written).
                response_sources=[response_source("Reply", affordance("actions", action, "output"))],
                response_transformation=(
                    f"-- {action}: the method's answer is the Operation's; the call is logged\n"
                    f"function aimc_main(sources, requestSources)\n"
                    f"    local reply, call = sources.Reply or {{}}, requestSources.{action} or {{}}\n"
                    f"    local answer = {{ Accepted = reply.{self.argument(1, 'Accepted', True)}, "
                    f"ErrorID = reply.{self.argument(2, 'ErrorID', True)} }}\n"
                    f"    local log = {{ Outcome = meta.invocation.outcome, DurationMs = meta.invocation.durationMs, Operation = {{\n"
                    + "".join(f"        {a} = call.{a},\n" for a in arguments)
                    + "        Accepted = answer.Accepted, ErrorID = answer.ErrorID } }\n"
                    "    if meta.invocation.outcome ~= \"Succeeded\" then return { Log = log } end\n"
                    f"    return {{ {action} = answer, Log = log }}\nend\n"),
                response_sinks=[response_sink(action, at), response_sink("Log", series_segment_ref("Log", action))]))
        return Aimc(id_short="AssetInterfacesMappingConfiguration",
                    MappingConfigurations=AimcMappingConfigurations(value=mappings))

    def capabilities(self) -> model.ModuleCapabilityDescription | None:
        """The capabilities the module offers (IDTA 02020), derived from its skills (``offers``),
        with the facts of the machine the spec states for each. A capability the spec states that
        no skill offers is refused."""
        if not self.derive:
            return None
        from .capabilities import component_sets          # it builds on this module's helpers
        found = offers(self.spec)
        stated = {meaning(name, cap.semantic_id): (name, cap) for name, cap in self.spec.capabilities.items()}
        if unknown := sorted(name for iri, (name, _) in stated.items() if iri not in {o.capability for o in found}):
            raise ValueError(f"{self.spec.module} states the capabilities {unknown}, which none of its skills offers")
        description, sets = capability_description(found, stated), component_sets(self.spec)
        if sets:
            description = description or model.ModuleCapabilityDescription(id_short="CapabilityDescription", CapabilitySet={})
            description.CapabilitySet.update(sets)
        return description

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
                Skill=ref(what))
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
            put(held.SkillError, name, arso.SkillError(**prop(code, "xs:integer")))

    def build(self) -> list[tuple[Module | Component, str]]:
        """The module and its components, each with the id of its asset."""
        spec = self.spec
        id_short, aas_id, asset_id = identity(spec)
        asset = Module(id_short=id_short, id=aas_id, asset_type=spec.aas.asset_type or f"{model.RESOURCE}/Module",
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
        parts = {item: Component(
            id_short=found[0], id=found[1], asset_type=found[3],
            description=f"{spec.equipment[item].description or item}: a component of the {spec.module} module, which carries out its skills")
            for item in self.components for found in [component_identity(spec, item)]}
        for name in [*spec.composites, *spec.skills]:
            decl = spec.skills.get(name)
            item = decl.equipment if decl is not None and decl.equipment in parts else None
            if name in control:
                raise ValueError(f"{name} is a command of the module itself: a skill cannot be called that")
            put((parts[item] if item else asset).skills.Skill, name, self.skill(name))
        for name, made in control.items():
            put(asset.skills.Skill, name, made)
        for held in (asset, *parts.values()):
            self.errors(held.skills.Errors)
        asset.skills.RuleSet = arso.RuleSet(**prop(RULES))
        nodes = {}
        for item, eq in spec.equipment.items():
            # A component is found by its asset id; an item no skill moves is only a part.
            nodes[item] = model.LocatedNode(entity_type="SelfManagedEntity" if item in parts else "CoManagedEntity",
                                            global_asset_id=component_identity(spec, item)[2] if item in parts else "",
                                            description=eq.description or f"Equipment {item}")
            for s, io in eq.inputs.items():
                key = self.property(f"Equipment_{item}_{s}", f"/Equipment/{item}/{s}", io.type, f"{item} {s}", io.unit)
                self.observe(f"{item}_{s}", key, f"{BASE_URL}/variables/{item}/{s}",
                             f"{item} {s}" + (f" ({io.unit})" if io.unit else ""))
        asset.hierarchical_structures = model.LocatedStructures(
            id_short="HierarchicalStructures", ArcheType=ArcheType(value="OneDown"),
            EntryNode=model.LocatedEntryNode(global_asset_id=asset_id, description=f"The {spec.module} module", Node=nodes))

        interface = asset.asset_interfaces_description.InterfaceTemplateForOPCUA["interface_opcua"]
        interface.title.value = f"{spec.module} module"
        interface.EndpointMetadata.base.value = self.opcua
        interface.EndpointMetadata.contentType.value = "application/octet-stream"
        interface.EndpointMetadata.securityDefinitions.nosec_sc = wot.nosec_sc(scheme=wot.Scheme(value="nosec"))
        self.interface_and_data(asset)
        # Beside the measurement series, where the module and its points are.
        asset.variables.Measurements = asset.variables.Measurements or MeasurementsGroup()
        asset.variables.Measurements.value["Coordinates"] = self.coordinates()
        asset.capability_description = self.capabilities()
        asset.asset_interfaces_mapping_configuration = self.mappings()
        return [(Module.model_validate(asset.model_dump()), asset_id),
                *[(Component.model_validate(part.model_dump()), component_identity(spec, item)[2])
                  for item, part in parts.items()]]


def capability_property(name: str, iri: str, value: CapabilityProperty, derived: bool):
    """A property of a capability: a value, the values it takes (IDTA 02020's list) or a range, in a
    unit; ``derived``: a skill sets it."""
    marks = [Qualifier(type_="Unit", value=value.unit, kind="ConceptQualifier")] if value.unit else []
    if derived:
        marks.append(Qualifier(type_="Derived", value="true", kind="ConceptQualifier"))
    about = dict(id_short="Value", supplemental_semantic_ids=[iri], display_name={"en": name},
                 description=value.description, qualifiers=marks)
    if value.values:
        kind = "xs:string" if all(isinstance(v, str) for v in value.values) else "xs:double"
        return model.StatedProperty(PropertySubmodelList={"Value": cd.PropertySubmodelList(
            type_value_list_element="Property", value_type_list_element=kind,
            value=[Property(value=text(v), value_type=kind) for v in value.values], **about)})
    if value.value is None:
        return model.StatedProperty(PropertyRange={"Value": cd.PropertyRange(
            min=text(value.minimum), max=text(value.maximum), value_type="xs:double", **about)})
    kind = "xs:boolean" if isinstance(value.value, bool) else "xs:string" if isinstance(value.value, str) else "xs:double"
    return model.StatedProperty(PropertyProperty={"Value": cd.PropertyProperty(value=text(value.value), value_type=kind, **about)})


def capability_description(found: list[Offer], stated: dict[str, tuple[str, CapabilitySpec]],
                           named: dict[tuple[str, str], str] | None = None) -> model.ModuleCapabilityDescription | None:
    """The capabilities ``found`` (derived from the skills), each with its meaning (marked Derived),
    the properties its skill sets (marked Derived), the facts ``stated`` for its class (meaning ->
    (name, what is stated)), and the skill realizing it (CapabilityRealizedBy, a reference into the
    Skills submodel; the skill does not refer back). A skill that is described but not built offers
    it only after a reconfiguration (Availability). Two skills offering one capability: each gets a
    container of its own, named after the capability and the skill, unless ``named`` (capability,
    skill element) -> idShort keeps the name it has."""
    from .capabilities import constrain_offer, vocabulary            # it builds on this module's helpers
    containers, count, named = {}, Counter(o.capability for o in found), named or {}
    # A name stays taken while the skill it names still offers its capability.
    taken = {n for (iri, skill), n in named.items() if any(o.capability == iri and o.skill == skill for o in found)}
    for offer in found:
        name, cap = stated.get(offer.capability, (offer.name, None))
        if cap is None:            # a narrower capability (BottomUpFilling): the machine's facts of the broader one
            broader = (f"{offer.capability.rsplit('/', 1)[0]}/{c}" for c in vocabulary().lineage(offer.name)[1:])
            cap = next((stated[iri][1].model_copy(update={"description": ""}) for iri in broader if iri in stated), None)
        id_short = named.get((offer.capability, offer.skill))
        if id_short is None:
            id_short = name if count[offer.capability] == 1 and name not in taken else f"{name}_{offer.skill_name or 'Planned'}"
            taken.add(id_short)
        # The booleans are xs:boolean in the AAS (model.typed_qualifiers): aas-model cannot convert them.
        marks = [Qualifier(type_="CapabilityRoleQualifier/Offered", value="true", semantic_id=OFFERED, kind="ConceptQualifier"),
                 Qualifier(type_="Derived", value="true", kind="ConceptQualifier")]
        if not offer.built:
            marks.append(Qualifier(type_="Availability", value="AfterReconfiguration", kind="ConceptQualifier"))
        how = (f"realized by {offer.skill_name}" if offer.keys else
               "kept by the resource itself: it changes only what the resource has in its custody" if offer.built else
               "a skill for it can be planned from its components' capabilities")
        capability = Capability(
            id_short="Capability", semantic_id=CAPABILITY, supplemental_semantic_ids=[offer.capability],
            display_name={"en": name}, description=(cap.description if cap else "") or f"{name}, {how}",
            qualifiers=marks)
        properties = {}
        for prop, value in (cap.properties.items() if cap else ()):
            put(properties, prop, capability_property(prop, meaning(prop, value.semantic_id), value, derived=False))
        for found_prop in offer.properties:
            prop = local(found_prop.meaning)
            value = (CapabilityProperty(value=found_prop.value, unit=found_prop.unit) if found_prop.value is not None else
                     CapabilityProperty(minimum=float(found_prop.minimum), maximum=float(found_prop.maximum), unit=found_prop.unit))
            put(properties, prop, capability_property(prop, found_prop.meaning, value, derived=True))
        # A capability only a plan would realize has no skill yet (``offer.planned_offers``).
        realized = {"RealizedBy": model.RealizedBySkill(id_short="RealizedBy", first=capability_path(id_short),
                                                        second=path(offer.keys[0][1], *offer.keys[1:]))} if offer.keys else {}
        containers[id_short] = model.ModuleCapabilityContainer(
            id_short=id_short, Capability=capability,
            PropertySet={"PropertySet": model.StatedPropertySet(id_short="PropertySet", PropertyContainer=properties)} if properties else {},
            CapabilityRelations=model.ModuleCapabilityRelations(id_short="CapabilityRelations", CapabilityRealizedBy=realized))
        constrain_offer(containers[id_short], OFFERED_SET, local(offer.capability))
    if not containers:
        return None
    return model.ModuleCapabilityDescription(id_short="CapabilityDescription", CapabilitySet={
        OFFERED_SET: model.ModuleCapabilitySet(id_short=OFFERED_SET, CapabilityContainer=containers)})


_OFFERS: dict[str, tuple[Offer, ...]] = {}         # spec (as JSON) -> what its skills offer


def lean(spec: ModuleSpec) -> list[dict]:
    """The AASs of the module and its components with only what the derivation reads, the Skills:
    the other submodels (the interface above all) take seconds."""
    describer = Describer(spec, next(iter(spec.targets)), None, None, None, None)
    describer.derive = False
    envs = []
    for asset, asset_id in describer.build():
        kept = asset.model_copy(update={f: None for f in type(asset).model_fields
                                        if f != "skills" and hasattr(getattr(asset, f), "id_short")})
        model.inject_ids(kept)
        envs.append(model.environment(kept, asset_id))
    return envs


def offers(spec: ModuleSpec) -> list[Offer]:
    """The capabilities the module's skills offer (modreg.derive); once per spec."""
    key = spec.model_dump_json()
    if key not in _OFFERS:
        _OFFERS[key] = tuple(derived_offers(project(lean(spec), structure=False)))
    return list(_OFFERS[key])


def describe_with_record(spec: ModuleSpec, target: str, snap: Snapshot | None = None, drift: Drift | None = None,
                         spec_path: str | None = None, opcua: str | None = None) -> tuple[list[dict], dict]:
    """The profiles of the module (the first) and of its components, and the integrator's record of
    what was built (``record``); with a snapshot, values, hashes and the sync state are the running ones."""
    describer = Describer(spec, target, snap, drift, spec_path, opcua)
    built = describer.build()
    return [model.profile(asset, global_asset_id=asset_id) for asset, asset_id in built], record(describer, built[0][0])


def record(describer: Describer, module: Module) -> dict:
    """The record of what was built, as a Control Configuration submodel (ARSO's module), kept outside
    the module's AAS: the AAS of ``module`` with only that submodel, and that submodel taken out."""
    holder = module.model_copy(update={f: None for f in type(module).model_fields if hasattr(getattr(module, f), "id_short")})
    holder.control_configuration = describer.control_configuration()
    model.inject_ids(holder)
    env = model.environment(holder)
    return next(sm for sm in env["submodels"] if sm["idShort"] == "ControlConfiguration")


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
