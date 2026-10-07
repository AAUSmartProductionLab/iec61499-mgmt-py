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
from product_aas import at, children, resolve, semantic_ids, shell_of, unit_of   # noqa: E402

RESOURCE_STRUCTURE = '''```mermaid
classDiagram
  direction LR
  class ResourceAAS {
    id, idShort
    globalAssetId
    derivedFrom resource template
  }
  class Nameplate {
    <<IDTA 02006>>
    ManufacturerName
    ManufacturerProductDesignation
    AddressInformation
  }
  class HierarchicalStructures {
    <<IDTA 02011>>
    ArcheType = OneDown
  }
  class Equipment {
    <<Entity>>
    idShort
    description
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
    command id: supplemental
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
    Value or Range
    unit
    meaning: supplemental id
  }
  class Skills {
    <<ARSO>>
    Interfaces
    Errors with ErrorCode
  }
  class Skill {
    SemanticId
    Kind = Primitive or Composite
    Operation per command
  }
  class SkillParameter {
    value: deployed
    Unit, Minimum, Maximum, Default
  }
  class Contract {
    Requires
    Ensures or After
    Invariant, Timeout
  }
  class Step {
    InstancePath
    Bindings constant or reference
  }
  class BuildingBlock {
    SemanticId
    Kind = Primitive
    Parameters, Contract
  }
  class Implementation {
    FBType
    TypeHash
    InstancePath
  }
  class ModuleCommands {
    Operation per command
    Methods
    StateReference, OccupiedReference
  }
  class Procedure {
    name Resetting or Stopping
  }
  class OperationalData {
    <<ARSO>>
  }
  class DataPoint {
    value decimal
    meaning: semantic id
  }
  class ControlConfiguration {
    <<ARSO>>
    Rules
    ModuleSpec, Target, Generator
    ProgramDigest
    SyncState, Differences
  }
  class Runtime {
    Name
    ManagementEndpoint
    Resource
  }
  class BlockType {
    Name
    Hash
  }

  ResourceAAS *-- Nameplate
  ResourceAAS *-- HierarchicalStructures
  ResourceAAS *-- AssetInterfacesDescription
  ResourceAAS *-- MappingConfiguration
  ResourceAAS *-- CapabilityDescription
  ResourceAAS *-- Skills
  ResourceAAS *-- OperationalData
  ResourceAAS *-- ControlConfiguration
  HierarchicalStructures *-- "0..*" Equipment
  AssetInterfacesDescription *-- "1" Interface
  Interface *-- "0..*" Action
  Interface *-- "0..*" InterfaceProperty
  MappingConfiguration *-- "1..*" Mapping
  CapabilityDescription *-- "1..*" Capability
  Capability *-- "0..*" CapabilityProperty
  Skills *-- "0..*" Skill
  Skills *-- "0..*" BuildingBlock
  Skills *-- "0..1" ModuleCommands
  Skills *-- "0..*" Procedure
  Skill *-- "0..*" SkillParameter
  Skill *-- "0..1" Contract
  Skill *-- "0..*" Step : Execute, Stop
  Skill *-- "0..1" Implementation
  BuildingBlock *-- "1" Implementation
  Procedure *-- "1..*" Step
  OperationalData *-- "1..*" DataPoint
  ControlConfiguration *-- "0..1" Runtime
  ControlConfiguration *-- "0..*" BlockType

```'''

RESOURCE_LINKS = '''```mermaid
classDiagram
  direction LR
  class Capability
  class CapabilityProperty
  class Skill
  class SkillParameter
  class Step
  class BuildingBlock
  class ModuleCommands
  class Action
  class InterfaceProperty
  class Equipment
  class Mapping
  class DataPoint

  Capability --> Skill : RealizedBy
  SkillParameter --> CapabilityProperty : RealizesProperty
  Skill --> Action : InterfaceReference, Methods
  Skill --> InterfaceProperty : State, Error, Results
  Skill --> Equipment : Occupies
  Skill --> Skill : Uses
  Skill --> BuildingBlock : Uses
  Step --> Skill : Skill
  Step --> BuildingBlock : Skill
  Step --> SkillParameter : Bindings (handed down)
  Step --> InterfaceProperty : StateReference
  ModuleCommands --> Action : Methods
  Mapping --> InterfaceProperty : Source
  Mapping --> DataPoint : Sink
  Mapping --> Skill : Source (its Operation)
  Mapping --> Action : Sink
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
    ProcessParameters
    ResourceParameters
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
  CapabilityDescription *-- "0..*" RequiredCapability
  RequiredCapability *-- "0..*" RequiredProperty
  ProductionSequence *-- "0..*" Step
  Step *-- "0..*" Binding

  Process --> Part : ProcessBoM
  Process --> RequiredCapability : RequiredCapability
  Step --> Process : ProcessReference
  Step --> ResourceAAS : Resource
  Step --> Skill : Skill
  Binding --> ProductParameter : SourceElement
  Binding ..> SkillParameter : Name
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


def resource_section(env: dict) -> list[str]:
    shell, skills_sm = shell_of(env), submodel(env, "Skills")
    name = shell["idShort"]
    equipment = [e["idShort"] for e in children(at(submodel(env, "HierarchicalStructures"), "EntryNode"))]
    listed = children(at(skills_sm, "Skills"))
    blocks = children(at(skills_sm, "BuildingBlocks"))
    kind = lambda s: (at(s, "Kind") or {}).get("value")                                  # noqa: E731
    composites = [s for s in listed if kind(s) == "Composite"]
    primitives = [s for s in listed if kind(s) == "Primitive"]
    access = [s["idShort"] for s in listed if kind(s) is None]
    capabilities = [c for capability_set in children(submodel(env, "CapabilityDescription")) for c in children(capability_set)]
    interface = at(submodel(env, "AssetInterfacesDescription"), "interface_opcua", "InteractionMetadata")
    config = submodel(env, "ControlConfiguration")
    built = "planned" not in at(config, "ModuleSpec")["value"]

    lines = [f"### {name}", "",
             f"`{shell['id']}`, asset `{shell['assetInformation']['globalAssetId']}`. "
             + ("Built: its program is generated and runs on FORTE (against the simulator; the hardware is not wired yet)."
                if built else
                "**Planned only:** described from a spec; there is no program and no hardware behind it yet."), "",
             "```mermaid", "flowchart BT"]
    lines.append(f'  subgraph EQ_{node(name)}["Equipment (Hierarchical Structures)"]')
    lines += [f'    {node(name + e)}["{e}"]' for e in equipment] + ["  end"]
    lines.append(f'  subgraph PR_{node(name)}["Skill primitives (Skills, kind Primitive)"]')
    lines += [f'    {node(name + s["idShort"])}["{s["idShort"]}"]' for s in primitives] + ["  end"]
    if blocks:
        lines.append(f'  subgraph BB_{node(name)}["Building blocks (not offered)"]')
        lines += [f'    {node(name + b["idShort"])}["{b["idShort"]}"]' for b in blocks] + ["  end"]
    lines.append(f'  subgraph CO_{node(name)}["Module level skills (Skills, kind Composite)"]')
    lines += [f'    {node(name + s["idShort"])}["{s["idShort"]}"]' for s in composites] + ["  end"]
    lines.append(f'  subgraph CA_{node(name)}["Capabilities (Capability Description, offered)"]')
    lines += [f'    {node(name + "cap" + c["idShort"])}(["{c["idShort"]}"])' for c in capabilities] + ["  end"]
    for s in [*primitives, *blocks]:
        for occupied in children(at(s, "Occupies")):
            lines.append(f"  {node(name + s['idShort'])} -- occupies --> {node(name + last(occupied['value']))}")
    for s in composites:
        for order, step in enumerate(children(at(s, "Execute")), 1):
            lines.append(f"  {node(name + s['idShort'])} -- \"{order}\" --> {node(name + last(at(step, 'Skill')['value']))}")
    for c in capabilities:
        for relation in children(at(c, "CapabilityRelations")):
            lines.append(f"  {node(name + 'cap' + c['idShort'])} -- realized by --> {node(name + last(relation['second']))}")
    lines += ["```", ""]

    lines += ["| Skill | Kind | Parameters | Equipment | Sequence |", "| --- | --- | --- | --- | --- |"]
    for s in [*listed, *blocks]:
        parameters = ", ".join(f"{p['idShort']} = {shown(p)}" for p in children(at(s, "Parameters"))) or "–"
        occupies = ", ".join(last(o["value"]) for o in children(at(s, "Occupies"))) or "–"
        steps = []
        for step in children(at(s, "Execute")):
            bound = [f"{b['idShort']} = {b['value']}" if b["modelType"] == "Property" else f"{b['idShort']} ← {last(b['value'])}"
                     for b in children(at(step, "Bindings"))]
            steps.append(last(at(step, "Skill")["value"]) + (f" ({', '.join(bound)})" if bound else ""))
        what = (kind(s) or "access control") + ("" if s in listed else ", building block")
        lines.append(f"| {s['idShort']} | {what} | {parameters} | {occupies} | {' → '.join(steps) or '–'} |")
    lines.append("")
    for c in capabilities:
        properties = "; ".join(f"{p['idShort']} {shown(at(p, 'Value'))}" for p in children(at(c, "PropertySet")))
        realized = ", ".join(last(r["second"]) for r in children(at(c, "CapabilityRelations")))
        lines.append(f"- **Capability {c['idShort']}** (`{semantic_ids(at(c, 'Capability'))[1]}`), realized by {realized}: {properties}.")
    procedures = ", ".join(f"{p['idShort']} ({' → '.join(last(at(st, 'Skill')['value']) for st in children(p))})"
                           for p in children(at(skills_sm, "Procedures"))) or "none"
    lines += [f"- **Module:** commands {', '.join(o['idShort'].split('_')[-1] for o in children(at(skills_sm, 'Module')) if o['modelType'] == 'Operation')}; "
              f"access control {', '.join(access)}; procedures: {procedures}.",
              f"- **Interface:** OPC UA at `{at(submodel(env, 'AssetInterfacesDescription'), 'interface_opcua', 'EndpointMetadata', 'base')['value']}`, "
              f"{len(children(at(interface, 'actions')))} actions and {len(children(at(interface, 'properties')))} properties; "
              f"{len(children(submodel(env, 'OperationalData')))} data points; "
              f"{len(children(at(submodel(env, 'AssetInterfacesMappingConfiguration'), 'MappingConfigurations')))} mappings.",
              f"- **Control Configuration:** rules `{at(config, 'Rules')['value']}`, spec `{at(config, 'ModuleSpec')['value']}`, "
              f"sync state {at(config, 'SyncState')['value']}.", ""]
    return lines


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
              "| Process | Product parameters | Materials | Required capability |", "| --- | --- | --- | --- |"]
    for process in processes:
        parameters = ", ".join(f"{p['idShort']} = {shown(p)}" for p in children(at(process, "ProductParameters")))
        materials = ", ".join(m["idShort"] for m in children(at(process, "ProcessBoM"))) or "–"
        required = resolve(envs, at(process, "RequiredCapability")["value"])
        lines.append(f"| {process['idShort']} | {parameters} | {materials} | `{semantic_ids(required)[1]}` |")
    lines += ["", f"The plan (Production Sequence, `{at(plan, 'PlanSchema')['value']}`):", "",
              "| Order | Step | Resource | Skill | Bound |", "| --- | --- | --- | --- | --- |"]
    for step in steps:
        bound = ", ".join(f"{at(b, 'Name')['value']} ← {last(at(b, 'SourceElement')['value'])}" for b in children(at(step, "Bindings"))) or "–"
        lines.append(f"| {int(at(step, 'Order')['value']) + 1} | {at(step, 'Name')['value']} | "
                     f"{by_id[at(step, 'Resource')['value']['keys'][0]['value']]} | {at(step, 'SkillId')['value']} | {bound} |")
    lines.append("")
    return lines


def document() -> str:
    resources, products = example_line.build()
    lines = [
        "# The example line: its AASs",
        "",
        "Five AASs built to the framework: four resources (filling, stoppering, capping, inspection) and",
        "one product planned on them (a 2 mL vial). Each product's plan is followed into the resources when",
        "they are built; a plan that does not fit is refused. What the submodels are and how they link is",
        "in [aas-models.md](aas-models.md).",
        "",
        "This file is written by `python cell/examples/describe.py`. The examples themselves are the",
        "module specs (`cell/modules`, `cell/modules/planned`) and the product descriptions",
        "(`cell/examples/*.yaml`); `python cell/examples/example_line.py --out <folder> --publish <server>`",
        "builds the AASs and puts them on an AAS server.",
        "",
        "| AAS | Kind | Submodels |",
        "| --- | --- | --- |",
    ]
    for env in [*resources.values(), *products.values()]:
        kind = "resource" if env in resources.values() else "product"
        lines.append(f"| `{shell_of(env)['idShort']}` | {kind} | {', '.join(s['idShort'] for s in env['submodels'])} |")
    lines += ["", "## Class diagram: a resource AAS", "",
              "All four resources have this structure. First what the AAS holds: its submodels and their main",
              "elements.", "", RESOURCE_STRUCTURE, "",
              "Then how those elements refer to each other. Every arrow is a reference stored in the AAS, named",
              "like the element that carries it.", "", RESOURCE_LINKS, "",
              "## Class diagram: a product AAS", "",
              "The classes marked as another AAS are in the resource AAS above; the dashed arrows are links that",
              "are followed by meaning or by name, not by a stored reference.", "", PRODUCT_CLASSES, "",
              "## The resources", "",
              "Read upwards: a primitive occupies equipment, a module level skill runs primitives and building",
              "blocks in order, and a capability is realized by a module level skill.", ""]
    for env in resources.values():
        lines += resource_section(env)
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
