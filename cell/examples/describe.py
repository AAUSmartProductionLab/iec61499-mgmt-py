"""Write docs/aas-examples.md: the class diagram of a resource AAS and of a product AAS, and what
each AAS of the example line holds, read from the AASs ``example_line.build`` gives.

    python cell/examples/describe.py [--out docs/aas-examples.md]
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import example_line                                             # noqa: E402
from modgen import load                                         # noqa: E402
from modreg.profile import identity                             # noqa: E402
from plan_check import at, children, resolve, semantic_ids, shell_of, unit_of    # noqa: E402

SKILL = "https://smartproductionlab.aau.dk/skill"
# The modules described from a spec only: no program behind them yet.
PLANNED = {identity(load(path))[0] for path in example_line.RESOURCES
           if path.parent.name == "planned"}

LINE_STRUCTURE = '''```mermaid
classDiagram
  direction LR
  class SystemAAS {
    assetType = .../Resource/System
    the line
  }
  class ModuleAAS {
    assetType = .../Resource/Module
    one per module
  }
  class ComponentAAS {
    assetType = .../Resource/Component/<Kind>
    one per component as built in
  }
  class HierarchicalStructures {
    <<IDTA 02011>>
    ArcheType = OneDown
    parts by their asset id
  }
  class Skills {
    <<ARSO, from IDTA 02015>>
  }
  class Skill {
    kind: Primitive or Composite
    SemanticId: what it does
  }
  SystemAAS *-- HierarchicalStructures
  ModuleAAS *-- HierarchicalStructures
  ModuleAAS *-- Skills : its composites
  ComponentAAS *-- Skills : its primitives
  Skills *-- "0..*" Skill
  SystemAAS ..> ModuleAAS : part (asset id)
  ModuleAAS ..> ComponentAAS : part (asset id)
  Skill --> Skill : a step runs it
```'''

RESOURCE_STRUCTURE = '''```mermaid
classDiagram
  direction LR
  class ModuleAAS {
    id, idShort
    globalAssetId
    assetType = .../Resource/Module
  }
  class Nameplate {
    <<IDTA 02006>>
    ManufacturerName
    ManufacturerProductDesignation
  }
  class HierarchicalStructures {
    <<IDTA 02011>>
    ArcheType = OneDown
  }
  class Part {
    <<Entity>>
    idShort
    globalAssetId of its AAS
  }
  class AssetInterfacesDescription {
    <<IDTA 02017>>
  }
  class Interface {
    title
    EndpointMetadata base, security
  }
  class Action {
    title, synchronous
    input, output
    forms href, browse path
    command and skill: supplemental ids
  }
  class InterfaceProperty {
    key, title, type, unit
    observable
    forms href, browse path
  }
  class MappingConfiguration {
    <<IDTA 02027>>
  }
  class Mapping {
    Sources, Sinks
    Transformation
  }
  class CapabilityDescription {
    <<IDTA 02020>>
  }
  class Capability {
    meaning: supplemental id
    role = Offered
  }
  class CapabilityProperty {
    meaning: supplemental id
    value or range, unit
  }
  class Skills {
    <<ARSO>>
    its skills, its own elements
    Errors: name = code
  }
  class Skill {
    semanticId = skill
    supplemental ids: its kind (Primitive,
    Composite or ModuleControl), its type
  }
  class Command {
    Start, Stop, Abort, Reset
    semanticId = skill/Start ...
  }
  class Operation {
    named like the command
    in: Session, parameters
    out: Accepted, ErrorID, results
  }
  class Variable {
    value, unit, limits
    semanticId of its data point
    meaning of a capability property
  }
  class Step {
    Step_0000, ... (the planner's elements)
    NodeId, Kind, Name, Order
    Kind step: Skill, Bindings, Outputs
    parallel, decision: Branches
    decision, conditional: Condition
  }
  class Conditions {
    of a primitive
    Precondition
    Postcondition
    Invariant
  }
  class Completion {
    of a primitive
    After
    Timeout
  }
  class Variables {
    <<aas-model>>
  }
  class DataPoint {
    value (decimal)
    supplementalSemanticId: what it shows
  }
  class Coordinate {
    <<Variables: Measurements/Coordinates>>
    meaning: ModuleBase, Mount, EndEffector, TransferPoint ...
    RelativeTo: another coordinate
    X Y Z mm, Roll Pitch Yaw deg
    XSource ... YawSource: a variable
  }

  ModuleAAS *-- Nameplate
  ModuleAAS *-- HierarchicalStructures
  ModuleAAS *-- AssetInterfacesDescription
  ModuleAAS *-- MappingConfiguration
  ModuleAAS *-- CapabilityDescription
  ModuleAAS *-- Skills
  ModuleAAS *-- Variables
  HierarchicalStructures *-- "0..*" Part
  AssetInterfacesDescription *-- "1" Interface
  Interface *-- "0..*" Action
  Interface *-- "0..*" InterfaceProperty
  MappingConfiguration *-- "1..*" Mapping
  CapabilityDescription *-- "1..*" Capability
  Capability *-- "0..*" CapabilityProperty
  Skills *-- "0..*" Skill
  Skill *-- "1..4" Command
  Skill *-- "0..1" Conditions
  Skill *-- "0..1" Completion
  Command *-- "1" Operation
  Operation *-- "2..*" Variable
  Command *-- "0..*" Step : Steps
  Variables *-- "1..*" DataPoint
  Variables *-- "1..*" Coordinate
  Coordinate --> Coordinate : RelativeTo
  Coordinate --> DataPoint : follows
```'''

RESOURCE_LINKS = '''```mermaid
classDiagram
  direction LR
  class Capability
  class Skill
  class Command
  class Operation
  class Variable
  class Step
  class Action
  class InterfaceProperty
  class Part
  class ComponentAAS
  class Mapping
  class DataPoint
  class Instance

  Capability --> Skill : RealizedBy
  Command --> Action : InterfaceReference
  Step --> Skill : Skill (of this AAS or of a component's)
  Step --> Variable : a variable of the command's Operation
  Mapping --> InterfaceProperty : Source
  Mapping --> DataPoint : Sink
  Mapping --> Operation : Source
  Mapping --> Action : Sink
  Instance --> Skill : Skill
  Instance --> Step : Skill
  Part ..> ComponentAAS : globalAssetId
  Variable ..> DataPoint : same semanticId
  Variable ..> Capability : same meaning as its property
```'''

PRODUCT_CLASSES = '''```mermaid
classDiagram
  direction LR
  class ProductAAS {
    id, idShort
    globalAssetId
    assetKind = Type
  }
  class Nameplate {
    <<IDTA 02006>>
    ManufacturerProductDesignation
  }
  class HierarchicalStructures {
    <<IDTA 02011>>
    ArcheType = OneDown
  }
  class Part {
    <<Entity>>
    Quantity
    QuantityUnit
  }
  class ProcessParameters {
    <<IDTA 02031>>
  }
  class Process {
    ProcessId, ProcessName
    ProcessDescription
    PlannedProcessTime
    ProcessParameters
    ResourceParameters
  }
  class MaterialUse {
    <<lab extension>>
    Role
    Quantity, Unit
  }
  class ProductParameter {
    value, unit
    meaning: semantic id
  }
  class CapabilityDescription {
    <<IDTA 02020>>
  }
  class RequiredCapability {
    meaning: supplemental id
    role = Required
  }
  class RequiredProperty {
    Value, unit
    meaning: supplemental id
  }
  class ProductionSequence {
    <<planner template 2.0>>
    PlanSchema, Revision
    SequenceId, Name, Role
    Subject
  }
  class Step {
    NodeId, Kind, Name, Order
    no equipment
  }
  class OfferedCapability {
    <<in the resource AAS>>
  }

  ProductAAS *-- Nameplate
  ProductAAS *-- HierarchicalStructures
  ProductAAS *-- ProcessParameters
  ProductAAS *-- CapabilityDescription
  ProductAAS *-- ProductionSequence
  HierarchicalStructures *-- "0..*" Part
  ProcessParameters *-- "1..*" Process
  Process *-- "0..*" ProductParameter : ProductParameters
  Process *-- "0..*" MaterialUse : ProcessBoM
  CapabilityDescription *-- "0..*" RequiredCapability
  RequiredCapability *-- "0..*" RequiredProperty
  ProductionSequence *-- "1..*" Step

  MaterialUse --> Part : MaterialReference
  MaterialUse --> ProductParameter : QuantityParameterReference
  Process --> RequiredCapability : RequiredCapability
  Step --> Process : ProcessReference
  Step --> RequiredCapability : RequiredCapabilities
  RequiredCapability ..> OfferedCapability : matches (same meaning, values covered)
```'''

PROCESS_CLASSES = '''```mermaid
classDiagram
  direction LR
  class ProcessAAS {
    id, idShort
    assetKind = Type
    specificAssetIds: product, line
  }
  class ProcessInformation {
    RecipeRevision
    Status: Draft, Approved, Withdrawn
  }
  class Bindings
  class StepBinding {
    NodeId
    ExecutionMode
  }
  class InputBinding {
    Name: an input of the skill
    Value: constant if no source
  }
  class Validation {
    Result: Fits, DoesNotFit
    CheckedBy
    Findings
  }
  class ProductAAS {
    <<another AAS>>
  }
  class LineAAS {
    <<another AAS>>
  }
  class Step {
    <<in the product's recipe>>
  }
  class ProductParameter {
    <<in the product AAS>>
  }
  class ModuleAAS {
    <<another AAS>>
  }
  class Skill {
    <<in the module AAS>>
  }
  class Variable {
    <<an input of the skill's Start>>
  }

  ProcessAAS *-- ProcessInformation
  ProcessAAS *-- Bindings
  ProcessAAS *-- Validation
  Bindings *-- "1..*" StepBinding : one per step
  StepBinding *-- "0..*" InputBinding : Bindings

  ProcessInformation --> ProductAAS : Product
  ProcessInformation --> LineAAS : Line
  ProcessInformation --> ProductionSequence : Recipe
  StepBinding --> Step : Step
  StepBinding --> ModuleAAS : Resource
  StepBinding --> Skill : Skill
  InputBinding --> ProductParameter : SourceElement
  InputBinding --> Variable : InputReference
```'''


def submodel(env: dict, id_short: str) -> dict:
    return next(s for s in env["submodels"] if s["idShort"] == id_short)


def realizing(capability: dict) -> list[dict]:
    """The CapabilityRealizedBy relations of a capability's container."""
    return [r for r in children(at(capability, "CapabilityRelations")) if r.get("modelType") == "RelationshipElement"]


def constraints_of(capability: dict) -> str:
    """A capability's constraints in short: Pre Referenced = true, ..."""
    found = []
    for record in children(at(capability, "CapabilityRelations", "ConstraintSet")):
        (relation,) = children(at(record, "ConstraintPropertyRelations"))
        found.append(f"{at(record, 'PropertyConditionalType')['value']} {relation['second']['keys'][-2]['value']} "
                     f"{at(record, 'BasicConstraint')['value']}")
    return ", ".join(found)


def last(ref: dict) -> str:
    return ref["keys"][-1]["value"]


def shown(value: dict) -> str:
    """A capability or parameter value with its unit."""
    unit = f" {unit_of(value)}" if unit_of(value) else ""
    if value.get("modelType") == "Range":
        return f"{value['min']} to {value['max']}{unit}"
    return f"{value.get('value')}{unit}"


def node(text: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in text)


def start_of(skill: dict) -> dict:
    """The Operation of a skill's Start: its inputs are the skill's parameters, its outputs the results."""
    return at(skill, "Start", "Start") or {}


def signature(skill: dict) -> str:
    """A skill as it is called: its parameters with value and unit, and what it gives back."""
    operation = start_of(skill)
    ins = [v["value"] for v in operation.get("inputVariables", [])][1:]
    outs = [v["value"] for v in operation.get("outputVariables", [])][2:]
    text = skill["idShort"] + "(" + ", ".join(v["idShort"] + " = " + shown(v) for v in ins) + ")"
    return text + (" → " + ", ".join(v["idShort"] + (f" [{unit_of(v)}]" if unit_of(v) else "") for v in outs) if outs else "")


def ran(envs: list[dict], command: dict | None) -> list[str]:
    """The steps of a command, each as the skill it runs with what is connected to it."""
    found = []
    for step in sorted(children(at(command, "Steps")), key=lambda s: int(at(s, "Order")["value"])):
        skill = resolve(envs, at(step, "Skill")["value"])
        wired = []
        for bound in children(at(step, "Bindings")):
            constant, handed = at(bound, "Value"), at(bound, "SourceElement")
            wired.append(f"{at(bound, 'Name')['value']} " + (f"= {constant['value']}" if constant else f"← {last(handed['value'])}"))
        for given in children(at(step, "Outputs")):
            wired.append(f"{last(at(given, 'ResultReference')['value'])} → {at(given, 'OutputId')['value']}")
        found.append(skill["idShort"] + (f" ({', '.join(wired)})" if wired else ""))
    return found


def skills_in(held: dict | None) -> list[dict]:
    """The skills of a Skills submodel: its elements of the semantic id skill (not its Errors)."""
    return [s for s in children(held) if semantic_ids(s)[:1] == [SKILL]]


def placed(coordinate: dict | None) -> str:
    """Where a coordinate is (ARSO 0.13): mm, the rotations in degrees that are not zero, what it is
    relative to and the data points it follows."""
    if coordinate is None:
        return ""
    value = lambda name: float(at(coordinate, name)["value"])                             # noqa: E731
    turned = [f"{name} {value(name):g}" for name in ("Roll", "Pitch", "Yaw") if value(name)]
    parent = at(coordinate, "RelativeTo")
    follows = [f"{e['idShort'][:-len('Source')]} = {last(e['value'])}" for e in children(coordinate) if e["idShort"].endswith("Source")]
    return (f" at ({value('X'):g}, {value('Y'):g}, {value('Z'):g})" + "".join(f", {r}" for r in turned)
            + (f" relative to {last(parent['value'])}" if parent else "") + (f", {', '.join(follows)}" if follows else ""))


def coordinates_of(env: dict | None) -> dict[str, dict]:
    found = at(submodel(env, "Variables") or {}, "Measurements", "Coordinates") if env else None
    return {c["idShort"]: c for c in children(found)} if found else {}


def meant(coordinate: dict) -> str:
    return (semantic_ids(coordinate)[1:] or ["/"])[-1].rsplit("/", 1)[-1]


def kind_of(skill: dict) -> str:
    """Primitive, Composite or ModuleControl: the supplemental id of a skill element."""
    return (semantic_ids(skill)[1:] or ["/"])[0].rsplit("/", 1)[-1]


def resource_section(env: dict, components: dict[str, dict]) -> list[str]:
    shell, skills_sm = shell_of(env), submodel(env, "Skills")
    name = shell["idShort"]
    structure = at(submodel(env, "HierarchicalStructures"), "EntryNode")
    parts = children(structure)
    points = coordinates_of(env)
    by_asset = {shell_of(c)["assetInformation"]["globalAssetId"]: c for c in components.values()}
    own = {p["idShort"]: by_asset[p["globalAssetId"]] for p in parts if p.get("globalAssetId") in by_asset}
    envs = [env, *own.values()]
    composites = [s for s in skills_in(skills_sm) if kind_of(s) != "ModuleControl"]
    control = [s for s in skills_in(skills_sm) if kind_of(s) == "ModuleControl"]
    sets = children(submodel(env, "CapabilityDescription"))
    capabilities = [c for s in sets if s["idShort"] == "OfferedCapabilities" for c in children(s)]
    parts = [(s["idShort"], c) for s in sets if s["idShort"] != "OfferedCapabilities" for c in children(s)]
    interface = at(submodel(env, "AssetInterfacesDescription"), "interface_opcua", "InteractionMetadata")
    built = name not in PLANNED
    skills_of = lambda c: skills_in(submodel(c, "Skills"))                                 # noqa: E731

    lines = [f"### {name}", "",
             f"`{shell['id']}`, asset `{shell['assetInformation']['globalAssetId']}`. "
             + ("Built: its program is generated and runs on FORTE, on the PC against the simulator and on its own Raspberry Pi 5."
                if built else
                "**Planned only:** described from a spec; there is no program and no hardware behind it yet."), "",
             "```mermaid", "flowchart BT"]
    for part, component in own.items():
        short = shell_of(component)["idShort"]
        kind = shell_of(component)["assetInformation"]["assetType"].rsplit("/", 1)[-1]
        lines.append(f'  subgraph {node(short)}["{short} (component, {kind})"]')
        lines += [f'    {node(short + s["idShort"])}["{s["idShort"]}"]' for s in skills_of(component)] + ["  end"]
    lines.append(f'  subgraph CO_{node(name)}["{name}: module level skills"]')
    lines += [f'    {node(name + s["idShort"])}["{s["idShort"]}"]' for s in composites] + ["  end"]
    lines.append(f'  subgraph CA_{node(name)}["{name}: capabilities (offered)"]')
    lines += [f'    {node(name + "cap" + c["idShort"])}(["{c["idShort"]}"])' for c in capabilities] + ["  end"]
    for s in composites:
        for step in children(at(s, "Start", "Steps")):
            target, order = at(step, "Skill")["value"]["keys"], int(at(step, "Order")["value"]) + 1
            owner = target[0]["value"].split("/aas/")[1].split("/submodels/")[0]
            lines.append(f"  {node(name + s['idShort'])} -- \"{order}\" --> {node(owner + target[-1]['value'])}")
    for c in capabilities:
        for relation in realizing(c):
            lines.append(f"  {node(name + 'cap' + c['idShort'])} -- realized by --> {node(name + last(relation['second']))}")
    lines += ["```", ""]

    lines += ["| Skill | Held by | Kind | Start runs | Stop runs |", "| --- | --- | --- | --- | --- |"]
    for s in composites:
        lines.append(f"| {signature(s)} | the module | {kind_of(s)} | {' → '.join(ran(envs, at(s, 'Start'))) or '–'} "
                     f"| {' → '.join(ran(envs, at(s, 'Stop'))) or '–'} |")
    for part, component in own.items():
        for s in skills_of(component):
            terms = [*children(at(s, "Conditions")), *children(at(s, "Completion"))]
            said = "; ".join(f"{c['idShort']} {c['value']}" for c in terms)
            lines.append(f"| {signature(s)} | {shell_of(component)['idShort']} | {kind_of(s)} | – ({said}) | – |")
    lines.append("")
    for c in capabilities:
        properties = "; ".join(f"{p['idShort']} {shown(at(p, 'Value'))}" for p in children(at(c, "PropertySet"))
                               if at(p, "Value").get("value") is not None or at(p, "Value")["modelType"] == "Range")
        realized = ", ".join(last(r["second"]) for r in realizing(c))
        lines.append(f"- **Capability {c['idShort']}** (`{semantic_ids(at(c, 'Capability'))[1]}`), realized by {realized}: {properties}"
                     + (f"; {constraints_of(c)}" if constraints_of(c) else "") + ".")
    if parts:
        lines.append("- **The components' capabilities** (role NotAssigned: parts of the module's, what the planner composes skills "
                     "from), what each needs, does and keeps: "
                     + "; ".join(f"{item}'s {c['idShort']} ({', '.join(last(r['second']) for r in realizing(c))}): {constraints_of(c)}"
                                 for item, c in parts) + ".")
    commands = [c["idShort"] + (f" ({' → '.join(ran(envs, at(c, 'Start')))})" if ran(envs, at(c, "Start")) else "") for c in control]
    lines += [f"- **The module's own commands** (skills of the kind ModuleControl): {', '.join(commands)}.",
              "- **Components:** " + (", ".join(part + " → `" + shell_of(c)["idShort"] + "`" for part, c in own.items()) or "none") + ".",
              *([f"- **Coordinates** (Variables, mm and degrees): "
                 + "; ".join(f"{name}" + (f" ({meant(c)})" if meant(c) else "") + placed(c) for name, c in points.items()) + "."]
                if points else []),
              f"- **Interface:** OPC UA at `{at(submodel(env, 'AssetInterfacesDescription'), 'interface_opcua', 'EndpointMetadata', 'base')['value']}`, "
              f"{len(children(at(interface, 'actions')))} actions and {len(children(at(interface, 'properties')))} properties; "
              f"{sum(e.get('modelType') == 'Property' for e in children(submodel(env, 'Variables')))} data points; "
              f"{len(children(at(submodel(env, 'AssetInterfacesMappingConfiguration'), 'MappingConfigurations')))} mappings.",
              f"- **Program:** built by the rule set `{at(skills_sm, 'RuleSet')['value']}`; module level skills "
              + ", ".join(f"{s['idShort']} {at(s, 'Deployment')['value'].lower()}" for s in composites if at(s, "Deployment"))
              + ". Which block is which skill or step is the integrator's record, outside the AAS.", ""]
    return lines


def material(use: dict) -> str:
    """A material a process uses: its role, and how much (a fixed quantity, or what a parameter says)."""
    by_parameter = at(use, "QuantityParameterReference")
    amount = last(by_parameter["value"]) if by_parameter else f"{at(use, 'Quantity')['value']} {at(use, 'Unit')['value']}"
    return f"{use['idShort']} ({at(use, 'Role')['value']}, {amount})"


def bound(process: dict, step: dict) -> dict | None:
    """The binding of a step of the recipe in the process AAS."""
    return next((b for b in children(submodel(process, "Bindings"))
                 if last(at(b, "Step")["value"]) == step["idShort"]), None)


def product_section(env: dict, process: dict, resources: dict[str, dict]) -> list[str]:
    process_aas = process
    shell, envs = shell_of(env), [env, process_aas, *resources.values()]
    by_id = {shell_of(r)["id"]: shell_of(r)["idShort"] for r in resources.values()}
    name = shell["idShort"]
    parts = children(at(submodel(env, "HierarchicalStructures"), "EntryNode"))
    processes = children(at(submodel(env, "ProcessParameters"), "Processes"))
    plan = submodel(env, "ProductionSequence")
    steps = children(at(plan, "Steps"))

    lines = [f"### {name}", "", f"`{shell['id']}`, asset `{shell['assetInformation']['globalAssetId']}`; on the line by "
             f"`{shell_of(process_aas)['idShort']}`.", "",
             "```mermaid", "flowchart LR"]
    previous = None
    for step in steps:
        process = at(step, "Name")["value"]
        binding = bound(process_aas, step)
        skill = resolve(envs, at(binding, "Skill")["value"])
        resource = by_id[at(binding, "Resource")["value"]["keys"][0]["value"]]
        required = resolve(envs, at(resolve(envs, at(step, "ProcessReference")["value"]), "RequiredCapability")["value"])
        meaning = semantic_ids(required)[1].rsplit("/", 1)[-1]
        lines.append(f'  subgraph S_{node(process)}["Step {int(at(step, "Order")["value"]) + 1}"]')
        lines.append(f'    {node("p" + process)}["process {process}"] -- requires --> {node("c" + process)}(["{meaning}"])')
        lines.append(f'    {node("c" + process)} -. offered by .-> {node("s" + process)}["{resource}<br/>skill {skill["idShort"]}"]')
        lines.append("  end")
        if previous:
            lines.append(f"  S_{node(previous)} --> S_{node(process)}")
        previous = process
    lines += ["```", ""]

    lines += ["Bill of material (Hierarchical Structures):", "", "| Part | Name | Quantity |", "| --- | --- | --- |"]
    for part in parts:
        lines.append(f"| {part['idShort']} | {part['displayName'][0]['text']} | {at(part, 'Quantity')['value']} {at(part, 'QuantityUnit')['value']} |")
    lines += ["", "Processes (Process Parameters) and what they require (Capability Description):", "",
              "| Process | Planned time | Product parameters | Materials | Required capability |", "| --- | --- | --- | --- | --- |"]
    for process in processes:
        parameters = ", ".join(f"{p['idShort']} = {shown(p)}" for p in children(at(process, "ProductParameters")))
        materials = ", ".join(material(m) for m in children(at(process, "ProcessBoM"))) or "–"
        required = resolve(envs, at(process, "RequiredCapability")["value"])
        lines.append(f"| {process['idShort']} | {at(process, 'PlannedProcessTime')['value']} | {parameters} | {materials} | "
                     f"`{semantic_ids(required)[1]}` |")
    lines += ["", f"The recipe (Production Sequence, `{at(plan, 'PlanSchema')['value']}`) and its binding to the line "
              f"(the process AAS's Bindings; Validation: {at(submodel(process_aas, 'Validation'), 'Result')['value']}):", "",
              "| Order | Step | Resource | Skill | Inputs handed |", "| --- | --- | --- | --- | --- |"]
    for step in steps:
        binding = bound(process_aas, step)
        handed = ", ".join(f"{at(b, 'Name')['value']} ← {last(at(b, 'SourceElement')['value']) if at(b, 'SourceElement') else at(b, 'Value').get('value')}"
                           for b in children(at(binding, "Bindings"))) or "–"
        lines.append(f"| {int(at(step, 'Order')['value']) + 1} | {at(step, 'Name')['value']} | "
                     f"{by_id[at(binding, 'Resource')['value']['keys'][0]['value']]} | {last(at(binding, 'Skill')['value'])} | {handed} |")
    lines.append("")
    return lines


def document() -> str:
    resources, products = example_line.build()
    components = example_line.components()
    system = example_line.line(resources)
    processes = example_line.processes(resources, products)
    planar = list(example_line.planar_table())
    by_asset = {shell_of(e)["assetInformation"]["globalAssetId"]: e for e in [*resources.values(), *components.values(), *planar]}
    lines = [
        "# The example line: its AASs",
        "",
        f"{1 + len(planar) + len(resources) + len(components) + len(products) + len(processes)} AASs, the lab's "
        "reference models: the line, the planar table and its shuttles, the modules",
        "(filling, stoppering, capping, inspection; loading and unloading are named but not described yet),",
        "the components of each module, three products (a 2 mL vial, a prefilled syringe of 1 mL, a",
        "cartridge of 3 mL) and the process of each on the line. A process AAS binds a product's recipe to",
        "the modules: per step the module, the skill and what each of its inputs is handed, each a",
        "reference; the plan check follows every one into the product's and the modules' AASs, and a",
        "process whose Validation says otherwise is refused. Every AAS is an instance of aas-model's types",
        "(`Module`, `Component`, `ProductionSystem`, `Product`, `Process`; aas-model's `docs/lab-aas.md`).",
        "What the submodels are and how they link is in [aas-models.md](aas-models.md).",
        "",
        "This file is written by `python cell/examples/describe.py`. The modules' and their components'",
        "AASs are built by `modreg` from the module specs (`cell/modules`, `cell/modules/planned`), the",
        "table's and the shuttles' from what the planar controller says; the products and the processes are",
        "written out in Python (`cell/examples/products`, `cell/examples/processes`).",
        "`python cell/examples/example_line.py --out <folder> --publish <server>` builds them all and puts",
        "them on an AAS server.",
        "",
        "## The line: what it is made of",
        "",
        "```",
        shell_of(system)["idShort"],
    ]
    for name, c in coordinates_of(system).items():
        lines.append(f"  point {name} ({meant(c)}){placed(c)}")
    for part in children(at(submodel(system, "HierarchicalStructures"), "EntryNode")):
        module = by_asset.get(part["globalAssetId"])
        lines.append(f"  {shell_of(module)['idShort'] if module else part['idShort'] + ' (not described yet)'}"
                     f"{placed(coordinates_of(module).get('ModuleBase'))}")
        if module:
            composites = skills_in(submodel(module, "Skills"))
            lines += [f"    skill {signature(s)}" for s in composites]
            for inner in children(at(submodel(module, "HierarchicalStructures"), "EntryNode")):
                component = by_asset.get(inner.get("globalAssetId"))
                if component:
                    held = ", ".join(signature(s) for s in skills_in(submodel(component, "Skills")))
                    lines.append(f"    {shell_of(component)['idShort']}: {held}")
    lines += ["```", "",
              "| AAS | Kind | Submodels |",
              "| --- | --- | --- |"]
    for env in [system, *planar, *resources.values(), *components.values(), *products.values(), *processes.values()]:
        asset_type = shell_of(env)["assetInformation"].get("assetType", "")
        kind = (asset_type.split("/Resource/")[-1].lower() if "/Resource/" in asset_type
                else "process" if asset_type.endswith("/Process") else "product")
        lines.append(f"| `{shell_of(env)['idShort']}` | {kind} | {', '.join(s['idShort'] for s in env['submodels'])} |")
    lines += ["", "## Class diagram: the resources", "",
              "A line is made of modules and a module of components. What kind of resource an AAS is, is its",
              "asset type; a component's ends in its kind, which every component like it shares (the three",
              "linear axes). A part is found by its asset id.", "", LINE_STRUCTURE, "",
              "## Class diagram: a module AAS", "",
              "What the AAS holds: its submodels and their main elements. A component's AAS holds only Skills,",
              "with the same Skill, Command, Operation, Conditions and Completion.", "", RESOURCE_STRUCTURE, "",
              "Then how those elements refer to each other. Every solid arrow is a reference stored in the AAS,",
              "named like the element that carries it; a dashed arrow is a link by a shared id.", "", RESOURCE_LINKS, "",
              "## Class diagram: a product AAS", "",
              "The classes marked as another AAS are in the resource AAS above; the dashed arrows are links that",
              "are followed by meaning or by name, not by a stored reference. The recipe names no equipment.", "",
              PRODUCT_CLASSES, "",
              "## Class diagram: a process AAS", "",
              "A product's recipe bound to the line: per step of the recipe, the module and the skill that carry",
              "it out, and what each input of the skill is handed.", "", PROCESS_CLASSES, "",
              "## The modules", "",
              "Read upwards: a module level skill runs skills of the module's components in order, and a",
              "capability is realized by a module level skill.", ""]
    for env in resources.values():
        lines += resource_section(env, components)
    lines += ["## The products and their processes", ""]
    for env, process in zip(products.values(), processes.values()):
        lines += product_section(env, process, resources)
    return "\n".join(lines).rstrip() + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=str(HERE.parents[1] / "docs" / "aas-examples.md"))
    args = parser.parse_args(argv)
    Path(args.out).write_text(document(), encoding="utf-8", newline="\n")
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
