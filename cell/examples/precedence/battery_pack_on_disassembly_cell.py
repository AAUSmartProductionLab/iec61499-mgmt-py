"""The battery pack in the disassembly cell: its process AAS (the master recipe), binding the steps
of the pack's Disassembly sequence and of its four modules' sequences to the cell's stations.

    UnscrewCover   -> UnscrewingStation.Unscrew    Torque <- Unscrewing.BreakawayTorque (8 N·m)
    UnplugHV       -> HandlingStation.Unplug
    RemoveBusbars  -> UnscrewingStation.Unscrew    Torque <- Unbolting.BreakawayTorque (12 N·m)
    RemoveBMS      -> HandlingStation.PickAndPlace
    per module:
      RemoveLid        -> HandlingStation.Unclip
      TestCells        -> TestStation.TestCells    Current <- CellTesting.DischargeCurrent (10 A)
      SortForReuse     -> HandlingStation.Sort
      SortForRecycling -> HandlingStation.Sort

The cell is simulated and its stations' AASs are not written yet, so the Resource and Skill
references point at AASs that do not exist; the Validation says so. A step's path now runs through
the partial block: Steps / Step_0000 / Steps / Step_000n.

Written as ``cell/examples/processes/vial_2ml_on_filling_line.py`` is, with aas-model's classes.
"""
from __future__ import annotations

from aas_model.constants import BASE_URL
from aas_model.process_template import Process
from aas_model.submodel_templates.process import bindings as b, process_information as pi, validation as v
from aas_pydantic import Key, ModelReference

import battery_module
import battery_pack

AAS_ID = f"{BASE_URL}/aas/BatteryPackOnDisassemblyCellAAS"
ASSET_ID = f"{BASE_URL}/assets/BatteryPackOnDisassemblyCell"
PRODUCT = battery_pack.AAS_ID
LINE = f"{BASE_URL}/aas/DisassemblyCellAAS"
RECIPE = battery_pack.DISASSEMBLY
PROCESSES = battery_pack.PROCESSES
UNSCREWING = f"{BASE_URL}/aas/UnscrewingStationAAS"
HANDLING = f"{BASE_URL}/aas/HandlingStationAAS"
TESTING = f"{BASE_URL}/aas/TestStationAAS"


def reference(*keys: tuple[str, str]) -> ModelReference:
    return ModelReference(key=tuple(Key(type_=kind, value=value) for kind, value in keys))


def pack_step(name: str) -> b.BoundStep:
    """A step of the pack's partial block OpenPack."""
    return b.BoundStep(value=reference(
        ("Submodel", RECIPE), ("SubmodelElementCollection", "Steps"), ("SubmodelElementCollection", "Step_0000"),
        ("SubmodelElementCollection", "Steps"), ("SubmodelElementCollection", name)))


def skill(station: str, name: str) -> b.BoundSkill:
    return b.BoundSkill(value=reference(("Submodel", f"{station}/submodels/Skills"), ("SubmodelElementCollection", name)))


def skill_input(station: str, name: str, variable: str) -> b.InputReference:
    return b.InputReference(value=reference(
        ("Submodel", f"{station}/submodels/Skills"), ("SubmodelElementCollection", name),
        ("SubmodelElementCollection", "Start"), ("Operation", "Start"), ("Property", variable)))


def module_bindings(n: int) -> dict[str, b.ProcessStepBinding]:
    """The four steps of module ``n``'s sequence: the same stations and skills for each module."""
    i = battery_module.ids(n)
    teardown = (("Submodel", i["disassembly"]), ("SubmodelElementCollection", "Steps"),
                ("SubmodelElementCollection", "Step_0000"), ("SubmodelElementCollection", "Steps"))
    branch = lambda k: (*teardown, ("SubmodelElementCollection", "Step_0002"),  # noqa: E731
                        ("SubmodelElementCollection", "Branches"), ("SubmodelElementCollection", f"Branch_{k:04d}"),
                        ("SubmodelElementCollection", "Steps"), ("SubmodelElementCollection", "Step_0000"))
    return {
        f"Module{n}RemoveLid": b.ProcessStepBinding(
            id_short=f"Module{n}RemoveLid", NodeId=b.NodeId(value="RemoveLid"),
            Step=b.BoundStep(value=reference(*teardown, ("SubmodelElementCollection", "Step_0000"))),
            Resource=b.Resource(value=reference(("AssetAdministrationShell", HANDLING))),
            Skill=skill(HANDLING, "Unclip"), ExecutionMode=b.ExecutionMode(value="station")),
        f"Module{n}TestCells": b.ProcessStepBinding(
            id_short=f"Module{n}TestCells", NodeId=b.NodeId(value="TestCells"),
            Step=b.BoundStep(value=reference(*teardown, ("SubmodelElementCollection", "Step_0001"))),
            Resource=b.Resource(value=reference(("AssetAdministrationShell", TESTING))),
            Skill=skill(TESTING, "TestCells"), ExecutionMode=b.ExecutionMode(value="station"),
            Bindings=b.InputBindings(Binding={
                "Binding_0000": b.InputBinding(
                    id_short="Binding_0000", Name=b.Name(value="Current"),
                    SourceElement=b.SourceElement(value=reference(
                        ("Submodel", i["processes"]), ("SubmodelElementCollection", "Processes"),
                        ("SubmodelElementCollection", "CellTesting"),
                        ("SubmodelElementCollection", "ProductParameters"), ("Property", "DischargeCurrent"))),
                    InputReference=skill_input(TESTING, "TestCells", "Current")),
            })),
        f"Module{n}SortForReuse": b.ProcessStepBinding(
            id_short=f"Module{n}SortForReuse", NodeId=b.NodeId(value="SortForReuse"),
            Step=b.BoundStep(value=reference(*branch(0))),
            Resource=b.Resource(value=reference(("AssetAdministrationShell", HANDLING))),
            Skill=skill(HANDLING, "Sort"), ExecutionMode=b.ExecutionMode(value="station")),
        f"Module{n}SortForRecycling": b.ProcessStepBinding(
            id_short=f"Module{n}SortForRecycling", NodeId=b.NodeId(value="SortForRecycling"),
            Step=b.BoundStep(value=reference(*branch(1))),
            Resource=b.Resource(value=reference(("AssetAdministrationShell", HANDLING))),
            Skill=skill(HANDLING, "Sort"), ExecutionMode=b.ExecutionMode(value="station")),
    }


def battery_pack_on_disassembly_cell() -> Process:
    return Process(
        id_short="BatteryPackOnDisassemblyCellAAS", id=AAS_ID,
        description="The battery pack in the simulated disassembly cell: its Disassembly sequence bound to the stations",
        display_name={"en": "Battery pack in the disassembly cell"},
        specific_asset_ids={"product": battery_pack.ASSET_ID, "line": f"{BASE_URL}/assets/DisassemblyCell"},

        process_information=pi.ProcessInformation(
            id_short="ProcessInformation",
            Product=pi.Product(value=reference(("AssetAdministrationShell", PRODUCT))),
            Line=pi.Line(value=reference(("AssetAdministrationShell", LINE))),
            # The recipe this line runs: the pack's sequence of the archetype Disassembly.
            Recipe=pi.Recipe(value=reference(("Submodel", RECIPE))),
            RecipeRevision=pi.RecipeRevision(value="1"),
            Status=pi.Status(value="Draft"),
        ),

        bindings=b.ProcessBindings(
            id_short="Bindings",
            StepBinding={
                "UnscrewCover": b.ProcessStepBinding(
                    id_short="UnscrewCover", NodeId=b.NodeId(value="UnscrewCover"), Step=pack_step("Step_0000"),
                    Resource=b.Resource(value=reference(("AssetAdministrationShell", UNSCREWING))),
                    Skill=skill(UNSCREWING, "Unscrew"), ExecutionMode=b.ExecutionMode(value="station"),
                    Bindings=b.InputBindings(Binding={
                        # The joint's parameter, through the step's process, to the skill's input.
                        "Binding_0000": b.InputBinding(
                            id_short="Binding_0000", Name=b.Name(value="Torque"),
                            SourceElement=b.SourceElement(value=reference(
                                ("Submodel", PROCESSES), ("SubmodelElementCollection", "Processes"),
                                ("SubmodelElementCollection", "Unscrewing"),
                                ("SubmodelElementCollection", "ProductParameters"), ("Property", "BreakawayTorque"))),
                            InputReference=skill_input(UNSCREWING, "Unscrew", "Torque")),
                    })),
                "UnplugHV": b.ProcessStepBinding(
                    id_short="UnplugHV", NodeId=b.NodeId(value="UnplugHV"), Step=pack_step("Step_0001"),
                    Resource=b.Resource(value=reference(("AssetAdministrationShell", HANDLING))),
                    Skill=skill(HANDLING, "Unplug"), ExecutionMode=b.ExecutionMode(value="station")),
                "RemoveBusbars": b.ProcessStepBinding(
                    id_short="RemoveBusbars", NodeId=b.NodeId(value="RemoveBusbars"), Step=pack_step("Step_0002"),
                    Resource=b.Resource(value=reference(("AssetAdministrationShell", UNSCREWING))),
                    Skill=skill(UNSCREWING, "Unscrew"), ExecutionMode=b.ExecutionMode(value="station"),
                    Bindings=b.InputBindings(Binding={
                        "Binding_0000": b.InputBinding(
                            id_short="Binding_0000", Name=b.Name(value="Torque"),
                            SourceElement=b.SourceElement(value=reference(
                                ("Submodel", PROCESSES), ("SubmodelElementCollection", "Processes"),
                                ("SubmodelElementCollection", "Unbolting"),
                                ("SubmodelElementCollection", "ProductParameters"), ("Property", "BreakawayTorque"))),
                            InputReference=skill_input(UNSCREWING, "Unscrew", "Torque")),
                    })),
                "RemoveBMS": b.ProcessStepBinding(
                    id_short="RemoveBMS", NodeId=b.NodeId(value="RemoveBMS"), Step=pack_step("Step_0003"),
                    Resource=b.Resource(value=reference(("AssetAdministrationShell", HANDLING))),
                    Skill=skill(HANDLING, "PickAndPlace"), ExecutionMode=b.ExecutionMode(value="station")),
                # The call steps bind nothing themselves: their modules' steps are bound below.
                **module_bindings(1), **module_bindings(2), **module_bindings(3), **module_bindings(4),
            },
        ),

        validation=v.Validation(
            id_short="Validation",
            Result=v.Result(value="NotChecked"),
            CheckedBy=v.CheckedBy(value="build.py: the recipe's structure only"),
            Findings=v.Findings(value=[]),
        ),
    )
