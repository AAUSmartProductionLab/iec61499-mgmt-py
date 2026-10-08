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
from plan_check import at, children, resolve, semantic_ids, shell_of, unit_of    # noqa: E402

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
  class Module {
    <<ARSO>>
    the module's own commands
  }
  class Skills {
    <<ARSO, from IDTA 02015>>
    Interfaces (empty)
    Errors: name, ErrorCode
  }
  class Skill {
    semanticId = skill/Primitive or skill/Composite
    SemanticId: what it does
  }
  class Command {
    Start, Stop, Abort, Reset
    of the module: Occupy, Release, Reset, Start, Stop, Abort, Clear
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
    P1, P2, ...
    semanticId: its instance in the program
    constants: Property per variable
  }
  class Contract {
    of a primitive
    Requires
    Ensures or After
    Invariant, Timeout
  }
  class OperationalData {
    <<ARSO>>
  }
  class DataPoint {
    value (decimal)
    semanticId
  }
  class ControlConfiguration {
    <<ARSO>>
    Rules, ModuleSpec, Target
    ProgramDigest, SyncState
    Differences, Types (name, hash)
  }
  class Instance {
    InstancePath
    FBType, TypeHash
  }

  ModuleAAS *-- Nameplate
  ModuleAAS *-- HierarchicalStructures
  ModuleAAS *-- AssetInterfacesDescription
  ModuleAAS *-- MappingConfiguration
  ModuleAAS *-- CapabilityDescription
  ModuleAAS *-- Module
  ModuleAAS *-- Skills
  ModuleAAS *-- OperationalData
  ModuleAAS *-- ControlConfiguration
  HierarchicalStructures *-- "0..*" Part
  AssetInterfacesDescription *-- "1" Interface
  Interface *-- "0..*" Action
  Interface *-- "0..*" InterfaceProperty
  MappingConfiguration *-- "1..*" Mapping
  CapabilityDescription *-- "1..*" Capability
  Capability *-- "0..*" CapabilityProperty
  Module *-- "1..*" Command
  Skills *-- "0..*" Skill
  Skill *-- "1..4" Command
  Skill *-- "0..1" Contract
  Command *-- "1" Operation
  Operation *-- "2..*" Variable
  Command *-- "0..*" Step : Steps
  OperationalData *-- "1..*" DataPoint
  ControlConfiguration *-- "0..*" Instance : Instances
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
    SkillId
    ExecutionMode
  }
  class Binding {
    Name: skill parameter
    Value: constant if no source
  }
  class ResourceAAS {
    <<another AAS>>
  }
  class Skill {
    <<in the resource AAS>>
  }
  class SkillParameter {
    <<in the resource AAS>>
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
  ProductionSequence *-- "0..*" Step
  Step *-- "0..*" Binding

  MaterialUse --> Part : MaterialReference
  MaterialUse --> ProductParameter : QuantityParameterReference
  Process --> RequiredCapability : RequiredCapability
  Step --> Process : ProcessReference
  Step --> ModuleAAS : Resource
  Step --> Skill : Skill
  Binding --> ProductParameter : SourceElement
  Binding ..> Variable : Name (an input of the skill's Start)
  RequiredCapability ..> OfferedCapability : matches (same meaning, values covered)
  OfferedCapability --> Skill : RealizedBy
```'''


def submodel(env: dict, id_short: str) -> dict:
    return next(s for s in env["submodels"] if s["idShort"] == id_short)


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
    for step in children(at(command, "Steps")):
        skill = resolve(envs, at(step, "Skill")["value"])
        wired = []
        for c in children(step):
            if c["idShort"] == "Skill":
                continue
            if c["modelType"] == "Property":
                wired.append(f"{c['idShort']} = {c['value']}")
            else:
                given = last(c["value"])
                inputs = [v["value"]["idShort"] for v in (start_of(skill) or {}).get("inputVariables", [])]
                wired.append(f"{c['idShort']} ← {given}" if c["idShort"] in inputs else f"{c['idShort']} → {given}")
        found.append(skill["idShort"] + (f" ({', '.join(wired)})" if wired else ""))
    return found


def kind_of(skill: dict) -> str:
    return (semantic_ids(skill) or ["/"])[0].rsplit("/", 1)[-1]


def resource_section(env: dict, components: dict[str, dict]) -> list[str]:
    shell, skills_sm = shell_of(env), submodel(env, "Skills")
    name = shell["idShort"]
    parts = children(at(submodel(env, "HierarchicalStructures"), "EntryNode"))
    by_asset = {shell_of(c)["assetInformation"]["globalAssetId"]: c for c in components.values()}
    own = {p["idShort"]: by_asset[p["globalAssetId"]] for p in parts if p.get("globalAssetId") in by_asset}
    envs = [env, *own.values()]
    composites = children(at(skills_sm, "Skills"))
    capabilities = [c for capability_set in children(submodel(env, "CapabilityDescription")) for c in children(capability_set)]
    interface = at(submodel(env, "AssetInterfacesDescription"), "interface_opcua", "InteractionMetadata")
    config, machine = submodel(env, "ControlConfiguration"), submodel(env, "Module")
    built = "planned" not in at(config, "ModuleSpec")["value"]
    skills_of = lambda c: children(at(submodel(c, "Skills"), "Skills"))                   # noqa: E731

    lines = [f"### {name}", "",
             f"`{shell['id']}`, asset `{shell['assetInformation']['globalAssetId']}`. "
             + ("Built: its program is generated and runs on FORTE (against the simulator; the hardware is not wired yet)."
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
        for order, step in enumerate(children(at(s, "Start", "Steps")), 1):
            target = at(step, "Skill")["value"]["keys"]
            owner = target[0]["value"].split("/aas/")[1].split("/submodels/")[0]
            lines.append(f"  {node(name + s['idShort'])} -- \"{order}\" --> {node(owner + target[-1]['value'])}")
    for c in capabilities:
        for relation in children(at(c, "CapabilityRelations")):
            lines.append(f"  {node(name + 'cap' + c['idShort'])} -- realized by --> {node(name + last(relation['second']))}")
    lines += ["```", ""]

    lines += ["| Skill | Held by | Kind | Start runs | Stop runs |", "| --- | --- | --- | --- | --- |"]
    for s in composites:
        lines.append(f"| {signature(s)} | the module | {kind_of(s)} | {' → '.join(ran(envs, at(s, 'Start'))) or '–'} "
                     f"| {' → '.join(ran(envs, at(s, 'Stop'))) or '–'} |")
    for part, component in own.items():
        for s in skills_of(component):
            contract = "; ".join(f"{c['idShort']} {c['value']}" for c in children(at(s, "Contract")))
            lines.append(f"| {signature(s)} | {shell_of(component)['idShort']} | {kind_of(s)} | – ({contract}) | – |")
    lines.append("")
    for c in capabilities:
        properties = "; ".join(f"{p['idShort']} {shown(at(p, 'Value'))}" for p in children(at(c, "PropertySet")))
        realized = ", ".join(last(r["second"]) for r in children(at(c, "CapabilityRelations")))
        lines.append(f"- **Capability {c['idShort']}** (`{semantic_ids(at(c, 'Capability'))[1]}`), realized by {realized}: {properties}.")
    commands = [c["idShort"] + (f" ({' → '.join(ran(envs, c))})" if ran(envs, c) else "") for c in children(machine)]
    lines += [f"- **Module commands:** {', '.join(commands)}.",
              "- **Components:** " + (", ".join(part + " → `" + shell_of(c)["idShort"] + "`" for part, c in own.items()) or "none") + ".",
              f"- **Interface:** OPC UA at `{at(submodel(env, 'AssetInterfacesDescription'), 'interface_opcua', 'EndpointMetadata', 'base')['value']}`, "
              f"{len(children(at(interface, 'actions')))} actions and {len(children(at(interface, 'properties')))} properties; "
              f"{len(children(submodel(env, 'OperationalData')))} data points; "
              f"{len(children(at(submodel(env, 'AssetInterfacesMappingConfiguration'), 'MappingConfigurations')))} mappings.",
              f"- **Control Configuration:** rules `{at(config, 'Rules')['value']}`, spec `{at(config, 'ModuleSpec')['value']}`, "
              f"sync state {at(config, 'SyncState')['value']}, {len(children(at(config, 'Instances')))} blocks named as skills and steps.", ""]
    return lines


def material(use: dict) -> str:
    """A material a process uses: its role, and how much (a fixed quantity, or what a parameter says)."""
    by_parameter = at(use, "QuantityParameterReference")
    amount = last(by_parameter["value"]) if by_parameter else f"{at(use, 'Quantity')['value']} {at(use, 'Unit')['value']}"
    return f"{use['idShort']} ({at(use, 'Role')['value']}, {amount})"


def product_section(env: dict, resources: dict[str, dict]) -> list[str]:
    shell, envs = shell_of(env), [env, *resources.values()]
    by_id = {shell_of(r)["id"]: shell_of(r)["idShort"] for r in resources.values()}
    name = shell["idShort"]
    parts = children(at(submodel(env, "HierarchicalStructures"), "EntryNode"))
    processes = children(at(submodel(env, "ProcessParameters"), "Processes"))
    plan = submodel(env, "ProductionSequence")
    steps = children(at(plan, "Steps"))

    lines = [f"### {name}", "", f"`{shell['id']}`, asset `{shell['assetInformation']['globalAssetId']}`.", "",
             "```mermaid", "flowchart LR"]
    previous = None
    for step in steps:
        process = at(step, "Name")["value"]
        skill = resolve(envs, at(step, "Skill")["value"])
        resource = by_id[at(step, "Resource")["value"]["keys"][0]["value"]]
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
    lines += ["", f"The plan (Production Sequence, `{at(plan, 'PlanSchema')['value']}`):", "",
              "| Order | Step | Resource | Skill | Bound |", "| --- | --- | --- | --- | --- |"]
    for step in steps:
        bound = ", ".join(f"{at(b, 'Name')['value']} ← {last(at(b, 'SourceElement')['value']) if at(b, 'SourceElement') else at(b, 'Value').get('value')}"
                          for b in children(at(step, "Bindings"))) or "–"
        lines.append(f"| {int(at(step, 'Order')['value']) + 1} | {at(step, 'Name')['value']} | "
                     f"{by_id[at(step, 'Resource')['value']['keys'][0]['value']]} | {at(step, 'SkillId')['value']} | {bound} |")
    lines.append("")
    return lines


def document() -> str:
    resources, products = example_line.build()
    components = example_line.components()
    system = example_line.line(resources)
    by_asset = {shell_of(e)["assetInformation"]["globalAssetId"]: e for e in [*resources.values(), *components.values()]}
    lines = [
        "# The example line: its AASs",
        "",
        f"{1 + len(resources) + len(components) + len(products)} AASs built to the framework: the line, its modules "
        "(filling, stoppering, capping, inspection; loading",
        "and unloading are named but not described yet), the components of each module, and one product",
        "planned on them (a 2 mL vial). Each product's plan is followed into the resources when they are",
        "built; a plan that does not fit is refused. What the submodels are and how they link is in",
        "[aas-models.md](aas-models.md).",
        "",
        "This file is written by `python cell/examples/describe.py`. Every AAS is built by `modreg` from a",
        "profile, the pydantic dump of its type: the profiles of a module and of its components are made",
        "from the module spec (`cell/modules`, `cell/modules/planned`), a product's profile is a file",
        "(`cell/examples/Vial2mLAAS.json`). `python cell/examples/example_line.py --out <folder> --publish",
        "<server>` builds the AASs and puts them on an AAS server.",
        "",
        "## The line: what it is made of",
        "",
        "```",
        shell_of(system)["idShort"],
    ]
    for part in children(at(system["submodels"][0], "EntryNode")):
        module = by_asset.get(part["globalAssetId"])
        lines.append(f"  {shell_of(module)['idShort'] if module else part['idShort'] + ' (not described yet)'}")
        if module:
            composites = children(at(submodel(module, "Skills"), "Skills"))
            lines += [f"    skill {signature(s)}" for s in composites]
            for inner in children(at(submodel(module, "HierarchicalStructures"), "EntryNode")):
                component = by_asset.get(inner.get("globalAssetId"))
                if component:
                    held = ", ".join(signature(s) for s in children(at(submodel(component, "Skills"), "Skills")))
                    lines.append(f"    {shell_of(component)['idShort']}: {held}")
    lines += ["```", "",
              "| AAS | Kind | Submodels |",
              "| --- | --- | --- |"]
    for env in [system, *resources.values(), *components.values(), *products.values()]:
        asset_type = shell_of(env)["assetInformation"].get("assetType", "")
        kind = asset_type.split("/Resource/")[-1].lower() if "/Resource/" in asset_type else "product"
        lines.append(f"| `{shell_of(env)['idShort']}` | {kind} | {', '.join(s['idShort'] for s in env['submodels'])} |")
    lines += ["", "## Class diagram: the resources", "",
              "A line is made of modules and a module of components. What kind of resource an AAS is, is its",
              "asset type; a component's ends in its kind, which every component like it shares (the three",
              "linear axes). A part is found by its asset id.", "", LINE_STRUCTURE, "",
              "## Class diagram: a module AAS", "",
              "What the AAS holds: its submodels and their main elements. A component's AAS holds only Skills,",
              "with the same Skill, Command, Operation and Contract.", "", RESOURCE_STRUCTURE, "",
              "Then how those elements refer to each other. Every solid arrow is a reference stored in the AAS,",
              "named like the element that carries it; a dashed arrow is a link by a shared id.", "", RESOURCE_LINKS, "",
              "## Class diagram: a product AAS", "",
              "The classes marked as another AAS are in the resource AAS above; the dashed arrows are links that",
              "are followed by meaning or by name, not by a stored reference.", "", PRODUCT_CLASSES, "",
              "## The modules", "",
              "Read upwards: a module level skill runs skills of the module's components in order, and a",
              "capability is realized by a module level skill.", ""]
    for env in resources.values():
        lines += resource_section(env, components)
    lines += ["## The product", ""]
    for env in products.values():
        lines += product_section(env, resources)
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
