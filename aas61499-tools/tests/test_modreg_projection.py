"""modreg.projection: the AASs of a module as RDF, with the individuals and relations they describe.

Needs the ``registration`` extra (aas-model, rdflib); skipped without it.
"""
import pytest

pytest.importorskip("aas_model")
pytest.importorskip("rdflib")

from rdflib import Namespace, RDF, URIRef                                   # noqa: E402

from modgen import SPECS, load                                              # noqa: E402
from modreg import model, profile as profiles                               # noqa: E402
from modreg.projection import CSS, PA, PPRL, project                        # noqa: E402

BASE = "https://smartproductionlab.aau.dk"
LAB = Namespace(f"{BASE}/semantics/")
SKILLS = Namespace(f"{BASE}/skills/")
ARSO = Namespace("https://w3id.org/2025/arso#")


@pytest.fixture(scope="module")
def filling():
    spec = load(SPECS / "filling.yaml")
    return project([model.build(p) for p in profiles.describe_all(spec, "pi")])


def skill(aas: str, name: str) -> URIRef:
    """The individual the element of a skill describes."""
    return URIRef(f"{BASE}/aas/{aas}/submodels/Skills/Skills/{name}#it")


def parameter(aas: str, name: str, p: str) -> URIRef:
    return URIRef(f"{BASE}/aas/{aas}/submodels/Skills/Skills/{name}/Start/Start/{p}#it")


def test_elements_are_named_as_references_address_them_and_typed_by_the_structure(filling):
    element = URIRef(f"{BASE}/aas/FillingModuleAAS/submodels/Skills/Skills/Dispensing")
    assert (element, PA.idShort, None) in filling and (element, PA.semanticId, URIRef(f"{BASE}/skill")) in filling
    assert (element, PPRL.describes, skill("FillingModuleAAS", "Dispensing")) in filling
    assert any(str(t).startswith(str(ARSO)) for t in filling.objects(element, RDF.type))
    # A step's reference resolves to the element of the skill it runs, in the component's AAS.
    runs = URIRef(f"{BASE}/aas/FillingModuleAAS/submodels/Skills/Skills/Dispensing/Start/Steps/Step_0001/Skill")
    assert filling.value(runs, PA.refersTo) == URIRef(f"{BASE}/aas/FillingPumpAAS/submodels/Skills/Skills/Dispense")


def test_skills_are_of_their_kind_and_type_and_use_the_skills_of_their_steps(filling):
    dispensing, dispense = skill("FillingModuleAAS", "Dispensing"), skill("FillingPumpAAS", "Dispense")
    assert {PPRL.CompositeSkill, CSS.Skill} <= set(filling.objects(dispensing, RDF.type))
    assert {PPRL.PrimitiveSkill, CSS.Skill, SKILLS.Dispense} <= set(filling.objects(dispense, RDF.type))
    used = set(filling.objects(dispensing, PPRL.usesSkill))
    assert used == {skill("FillingLinearAxisAAS", "MoveAxis"), dispense, skill("FillingLinearAxisAAS", "Home"),
                    skill("FillingScaleAAS", "Weigh")}
    # The skill type says which capability a step contributes.
    assert (SKILLS.Dispense, LAB.contributes, LAB.Filling) in filling


def test_parameters_say_what_they_mean_and_where_their_value_comes_from(filling):
    volume, handed = parameter("FillingModuleAAS", "Dispensing", "Volume"), parameter("FillingPumpAAS", "Dispense", "Volume")
    assert (skill("FillingModuleAAS", "Dispensing"), CSS.hasParameter, volume) in filling
    assert {CSS.SkillParameter, CSS.InputParameter} <= set(filling.objects(volume, RDF.type))
    assert filling.value(volume, PPRL.means) == filling.value(handed, PPRL.means) == LAB.FillVolume
    assert (handed, PPRL.handedFrom, volume) in filling
    # FlowRate is a constant of the step: handed nothing. Session and the answer are no parameters.
    assert not set(filling.objects(parameter("FillingPumpAAS", "Dispense", "FlowRate"), PPRL.handedFrom))
    assert (parameter("FillingModuleAAS", "Dispensing", "Session"), RDF.type, CSS.SkillParameter) not in filling
    assert (parameter("FillingModuleAAS", "Dispensing", "Weight"), RDF.type, CSS.OutputParameter) in filling


def test_offered_capabilities_are_specified_and_realized_and_provided(filling):
    capability = URIRef(f"{BASE}/aas/FillingModuleAAS/submodels/CapabilityDescription/OfferedCapabilities/Filling/Capability#it")
    assert {LAB.Filling, PPRL.OfferedCapability} <= set(filling.objects(capability, RDF.type))
    assert filling.value(capability, CSS.isRealizedBySkill) == skill("FillingModuleAAS", "Dispensing")
    kinds = {k for p in filling.objects(capability, CSS.isSpecifiedBy) for k in filling.objects(p, RDF.type)}
    assert {LAB.FillVolume, LAB.ContainerType, LAB.GraspDiameter, LAB.AbsoluteFillError} <= kinds
    module = URIRef(f"{BASE}/aas/FillingModuleAAS#it")
    assert (module, CSS.providesCapability, capability) in filling
    assert (module, CSS.providesSkill, skill("FillingModuleAAS", "Dispensing")) in filling
    assert (URIRef(f"{BASE}/aas/FillingPumpAAS#it"), CSS.providesSkill, skill("FillingPumpAAS", "Dispense")) in filling


def test_a_skill_the_program_carries_out_is_implemented_by_a_block(filling):
    built = filling.value(skill("FillingModuleAAS", "Dispensing"), PPRL.implementedBy)
    assert built == URIRef(f"{BASE}/aas/FillingModuleAAS/submodels/ControlConfiguration/Instances/Dispensing_Control#it")
    assert (built, RDF.type, PPRL.FBInstance) in filling
