"""The 2 mL vial on the filling line: its process AAS (ISA-88's master recipe).

The vial's recipe (``products/vial_2ml.py``) says what is done to it, in which order, and what each
process requires. This AAS binds that recipe to the filling line: per step, which module carries it
out, with which skill, and what each input of the skill is handed. Only filling hands anything: the
Dispensing skill's Volume is the vial's FillVolume.

    Filling     -> FillingModule.Dispensing     Volume <- Filling.FillVolume (2 mL)
    Stoppering  -> StopperingModule.Stoppering
    Capping     -> CappingModule.Capping
    Inspection  -> InspectionModule.Inspection

Why apart from the product AAS: when the line is reconfigured, this AAS changes and the product's
does not; the same vial on another line is another process AAS. The asset is the process; it names
the vial's and the line's assets as specific asset ids, so it is found from either.

Every element is written out here, as the classes of aas-model make it (``aas_model.process_template``
and ``aas_model.submodel_templates.process``). The plan check (``plan_check.check_process``)
follows each binding into the product's and the modules' AASs; its result is the Validation.
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
RECIPE = plan_id(PRODUCT)                       # the product's Production Sequence
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
                        ("Submodel", RECIPE), ("SubmodelElementCollection", "Steps"), ("SubmodelElementCollection", "Step_0000"))),
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
                        ("Submodel", RECIPE), ("SubmodelElementCollection", "Steps"), ("SubmodelElementCollection", "Step_0001"))),
                    Resource=b.Resource(value=reference(("AssetAdministrationShell", STOPPERING))),
                    Skill=b.BoundSkill(value=reference(
                        ("Submodel", f"{STOPPERING}/submodels/Skills"), ("SubmodelElementCollection", "Stoppering"))),
                    ExecutionMode=b.ExecutionMode(value="station"),
                ),
                "Capping": b.ProcessStepBinding(
                    id_short="Capping",
                    NodeId=b.NodeId(value="Capping"),
                    Step=b.BoundStep(value=reference(
                        ("Submodel", RECIPE), ("SubmodelElementCollection", "Steps"), ("SubmodelElementCollection", "Step_0002"))),
                    Resource=b.Resource(value=reference(("AssetAdministrationShell", CAPPING))),
                    Skill=b.BoundSkill(value=reference(
                        ("Submodel", f"{CAPPING}/submodels/Skills"), ("SubmodelElementCollection", "Capping"))),
                    ExecutionMode=b.ExecutionMode(value="station"),
                ),
                "Inspection": b.ProcessStepBinding(
                    id_short="Inspection",
                    NodeId=b.NodeId(value="Inspection"),
                    Step=b.BoundStep(value=reference(
                        ("Submodel", RECIPE), ("SubmodelElementCollection", "Steps"), ("SubmodelElementCollection", "Step_0003"))),
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
