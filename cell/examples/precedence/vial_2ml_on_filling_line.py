"""The 2 mL vial on the filling line, for the Production Sequence 4.0 (``vial_2ml.py``): the
reference process AAS of ``cell/examples/processes/vial_2ml_on_filling_line.py`` with two changes.

1. ``Recipe`` names the vial's sequence of the archetype Assembly.
2. A step's path runs through the partial block: Steps / Step_0000 / Steps / Step_000n.

The modules, skills and the one input binding (Dispensing's Volume is the vial's FillVolume) are the
same: the line's AASs on the server do not change.

    Filling     -> FillingModule.Dispensing     Volume <- Filling.FillVolume (2 mL)
    Stoppering  -> StopperingModule.Stoppering
    Capping     -> CappingModule.Capping
    Inspection  -> InspectionModule.Inspection
"""
from __future__ import annotations

from aas_model.constants import BASE_URL
from aas_model.process_template import Process
from aas_model.product_template import plan_id
from aas_model.submodel_templates.process import bindings as b, process_information as pi, validation as v
from aas_pydantic import Key, ModelReference

AAS_ID = f"{BASE_URL}/aas/Vial2mLOnFillingLineAAS"
ASSET_ID = f"{BASE_URL}/assets/Vial2mLOnFillingLine"
PRODUCT = f"{BASE_URL}/aas/Vial2mLAAS"
LINE = f"{BASE_URL}/aas/FillingLineAAS"
RECIPE = f"{plan_id(PRODUCT)}/Assembly"         # the product's Production Sequence, archetype Assembly
PROCESSES = f"{PRODUCT}/submodels/ProcessParameters"
FILLING = f"{BASE_URL}/aas/FillingModuleAAS"
STOPPERING = f"{BASE_URL}/aas/StopperingModuleAAS"
CAPPING = f"{BASE_URL}/aas/CappingModuleAAS"
INSPECTION = f"{BASE_URL}/aas/InspectionModuleAAS"


def reference(*keys: tuple[str, str]) -> ModelReference:
    """A model reference along ``keys``: (type, value) pairs."""
    return ModelReference(key=tuple(Key(type_=kind, value=value) for kind, value in keys))


def vial_2ml_on_filling_line() -> Process:
    return Process(
        id_short="Vial2mLOnFillingLineAAS", id=AAS_ID,
        description="The process of the 2 mL vial on the filling line: its recipe bound to the line's modules",
        display_name={"en": "Vial 2 mL on the filling line"},
        specific_asset_ids={"product": f"{BASE_URL}/assets/Vial2mL", "line": f"{BASE_URL}/assets/FillingLine"},

        # ── Process Information: what is bound, and how far ─────────────────────────────────────
        process_information=pi.ProcessInformation(
            id_short="ProcessInformation",
            Product=pi.Product(value=reference(("AssetAdministrationShell", PRODUCT))),
            Line=pi.Line(value=reference(("AssetAdministrationShell", LINE))),
            Recipe=pi.Recipe(value=reference(("Submodel", RECIPE))),
            RecipeRevision=pi.RecipeRevision(value="1"),
            Status=pi.Status(value="Approved"),
        ),

        # ── Bindings: per step of the recipe, the module, its skill and its inputs ──────────────
        bindings=b.ProcessBindings(
            id_short="Bindings",
            StepBinding={
                "Filling": b.ProcessStepBinding(
                    id_short="Filling",
                    NodeId=b.NodeId(value="Filling"),
                    Step=b.BoundStep(value=reference(
                        ("Submodel", RECIPE), ("SubmodelElementCollection", "Steps"), ("SubmodelElementCollection", "Step_0000"),
                        ("SubmodelElementCollection", "Steps"), ("SubmodelElementCollection", "Step_0000"))),
                    Resource=b.Resource(value=reference(("AssetAdministrationShell", FILLING))),
                    Skill=b.BoundSkill(value=reference(
                        ("Submodel", f"{FILLING}/submodels/Skills"), ("SubmodelElementCollection", "Dispensing"))),
                    ExecutionMode=b.ExecutionMode(value="station"),
                    Bindings=b.InputBindings(Binding={
                        # Dispensing's Volume is the vial's fill volume.
                        "Binding_0000": b.InputBinding(
                            id_short="Binding_0000",
                            Name=b.Name(value="Volume"),
                            SourceElement=b.SourceElement(value=reference(
                                ("Submodel", PROCESSES), ("SubmodelElementCollection", "Processes"),
                                ("SubmodelElementCollection", "Filling"),
                                ("SubmodelElementCollection", "ProductParameters"), ("Property", "FillVolume"))),
                            InputReference=b.InputReference(value=reference(
                                ("Submodel", f"{FILLING}/submodels/Skills"), ("SubmodelElementCollection", "Dispensing"),
                                ("SubmodelElementCollection", "Start"), ("Operation", "Start"), ("Property", "Volume"))),
                        ),
                    }),
                ),
                "Stoppering": b.ProcessStepBinding(
                    id_short="Stoppering",
                    NodeId=b.NodeId(value="Stoppering"),
                    Step=b.BoundStep(value=reference(
                        ("Submodel", RECIPE), ("SubmodelElementCollection", "Steps"), ("SubmodelElementCollection", "Step_0000"),
                        ("SubmodelElementCollection", "Steps"), ("SubmodelElementCollection", "Step_0001"))),
                    Resource=b.Resource(value=reference(("AssetAdministrationShell", STOPPERING))),
                    Skill=b.BoundSkill(value=reference(
                        ("Submodel", f"{STOPPERING}/submodels/Skills"), ("SubmodelElementCollection", "Stoppering"))),
                    ExecutionMode=b.ExecutionMode(value="station"),
                ),
                "Capping": b.ProcessStepBinding(
                    id_short="Capping",
                    NodeId=b.NodeId(value="Capping"),
                    Step=b.BoundStep(value=reference(
                        ("Submodel", RECIPE), ("SubmodelElementCollection", "Steps"), ("SubmodelElementCollection", "Step_0000"),
                        ("SubmodelElementCollection", "Steps"), ("SubmodelElementCollection", "Step_0002"))),
                    Resource=b.Resource(value=reference(("AssetAdministrationShell", CAPPING))),
                    Skill=b.BoundSkill(value=reference(
                        ("Submodel", f"{CAPPING}/submodels/Skills"), ("SubmodelElementCollection", "Capping"))),
                    ExecutionMode=b.ExecutionMode(value="station"),
                ),
                "Inspection": b.ProcessStepBinding(
                    id_short="Inspection",
                    NodeId=b.NodeId(value="Inspection"),
                    Step=b.BoundStep(value=reference(
                        ("Submodel", RECIPE), ("SubmodelElementCollection", "Steps"), ("SubmodelElementCollection", "Step_0000"),
                        ("SubmodelElementCollection", "Steps"), ("SubmodelElementCollection", "Step_0003"))),
                    Resource=b.Resource(value=reference(("AssetAdministrationShell", INSPECTION))),
                    Skill=b.BoundSkill(value=reference(
                        ("Submodel", f"{INSPECTION}/submodels/Skills"), ("SubmodelElementCollection", "Inspection"))),
                    ExecutionMode=b.ExecutionMode(value="station"),
                ),
            },
        ),

        # ── Validation: the plan check's result ──────────────────────────────────────────────────
        validation=v.Validation(
            id_short="Validation",
            Result=v.Result(value="Fits"),
            CheckedBy=v.CheckedBy(value="plan_check"),
            Findings=v.Findings(value=[]),
        ),
    )
