"""Tests for the contract forward check on the filling-cell process versions."""
import json
from pathlib import Path

import pytest

from iec61499_mgmt.models import IECValue
from iec61499_mgmt.sysfile import load_application
from iec61499_mgmt.typelib import build_library, read_types
from skill_compiler import compile_bpmn
from skill_compiler.contracts import Condition, check, check_procedure, mutations
from skill_compiler.models import Call, RecipeBindings
from skill_compiler.targets import bind_library

ROOT = Path(__file__).resolve().parents[1]
CELL = ROOT / "examples" / "cell"
LAB = "https://smartproductionlab.aau.dk/skills/"


@pytest.fixture(scope="module")
def target():
    """Cell target profile bound to the generated types (fake hashes)."""
    types = read_types(ROOT / "4diac" / "FillingCellFixed" / "Type Library")
    library = build_library(types, {n: "v2:test" for n in types if n.startswith("fillingcell::")}, "test",
                            fixed=load_application(ROOT / "4diac" / "FillingCellFixed" / "FillingCellFixed.sys", "FillingCell"))
    return bind_library(json.loads((CELL / "target-template.json").read_text()), library)


def load(version, product):
    """BPMN text, bindings and product values of one process version and product."""
    values = {k: IECValue.model_validate(v) for k, v in json.loads((CELL / f"product-{product}.json").read_text()).items()}
    bindings = RecipeBindings.model_validate_json((CELL / f"bindings-{version}.json").read_text())
    return (CELL / f"fill-{version}.bpmn").read_text(), bindings, values


def calls(order, volume=1.0):
    """Procedure calls for a task order (for edits the compiler would not even accept)."""
    return [Call(id=f"{t}{i}", label=t, skill=LAB + t,
                 parameters={"volume": IECValue(type="LREAL", value=volume)} if t == "Dose" else {})
            for i, t in enumerate(order)]


@pytest.mark.parametrize("version,product,filled", [("v1", "A", 0.5), ("v2", "C", 2.0), ("v3", "D", 2.0)])
def test_valid_versions_pass(target, version, product, filled):
    """The approved versions pass, and the derived ensures reflect loops and parameters."""
    xml, bindings, values = load(version, product)
    report = check_procedure(compile_bpmn(xml, bindings, target, values).procedure, target, bindings.assumes)
    assert report.status == "Passed" and report.violations == []
    assert report.ensures["Filled"] == pytest.approx(filled)
    assert report.ensures.get("Checked", False) == (version == "v3")


def test_dose_before_movedown_is_rejected(target):
    """Plan scenario: Dose before MoveDown, MoveUp deleted; the task and condition are named."""
    _, bindings, _ = load("v2", "A")
    contracts = {k: s.contract for k, s in target.skills.items()}
    report = check(calls(["Dose", "MoveDown", "Stopper"]), contracts, bindings.assumes)
    assert report.status == "Rejected"
    found = {(v.task, v.condition, v.actual) for v in report.violations}
    assert ("Dose0", "Needle = 'Down'", "Up") in found
    assert ("Stopper2", "Needle = 'Up'", "Down") in found


def test_unknown_variable_is_a_violation(target):
    """A condition on a variable that Assumes never set cannot be proven."""
    contracts = {k: s.contract for k, s in target.skills.items()}
    report = check(calls(["MoveDown"]), contracts, [])
    assert report.status == "Rejected" and report.violations[0].actual is None


def test_mutation_study_of_v3(target):
    """Step contracts reject most single edits of v3; product goals reject the rest."""
    _, bindings, _ = load("v3", "D")
    contracts = {k: s.contract for k, s in target.skills.items()}
    order = ["MoveDown", "Dose", "MoveUp", "Stopper", "Inspect"]
    variants = mutations(order, list(dict.fromkeys(order)))
    assert len(variants) == 44
    passed = sorted(n for n, m in variants if check(calls(m), contracts, bindings.assumes).status == "Passed")
    # Locally valid edits: an extra dose, no inspection, needle left down.
    assert passed == ["delete Inspect", "duplicate Dose", "insert Dose at 1", "insert Dose at 2", "insert MoveDown at 5"]
    goals = [Condition(variable="Filled", value=1.0), Condition(variable="Checked", value=True),
             Condition(variable="Needle", value="Up")]
    assert all(check(calls(m), contracts, bindings.assumes, goals).status == "Rejected" for _, m in variants)
    assert check(calls(order), contracts, bindings.assumes, goals).status == "Passed"
