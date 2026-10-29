"""The domain read from a module's AAS as PDDL and HDDL (G6): GTPyhop's plans validate against both,
and standard planners plan the same cases through them (ENHSP on the PDDL, Aries on the HDDL), their
plans carried out by the domain's own semantics reaching what was asked for."""
import copy
from pathlib import Path
import shutil

import pytest

from modgen import load

from modplan.domain import PRODUCT, Constraint, Var, effect, holds, same
from modplan.expression import Expression
from modplan.export import NotExpressible, hddl, hddl_steps, kinds, pddl, pddl_steps, plan_text
from modplan.plan import goals, plan, start_state
from modplan.read import read

from modreg import model, profile as profiles

SPECS = Path(__file__).resolve().parents[2] / "cell" / "modules"
# (module, capability, values, results)
CASES = [("filling", "Filling", {"FillVolume": 2.0}, ("FillWeight",)),
         ("filling", "Filling", {"FillVolume": 15.0}, ("FillWeight",)),      # two doses
         ("filling", "Filling", {"FillVolume": 0.5}, ()),
         ("stoppering", "Stoppering", {}, ())]


@pytest.fixture(scope="module")
def domains() -> dict:
    found = {}
    for name in ("filling", "stoppering"):
        envs = [model.build(p) for p in profiles.describe_all(load(SPECS / f"{name}.yaml"), "pi")]
        found[name] = read(envs[0], envs[1:])
    return found


def carried_out(domain, capability, values, results, steps) -> bool:
    """Whether ``steps`` run, one after the other, and leave what was asked for and the module at rest."""
    state = start_state(domain, capability, values)
    for step in steps:
        cap = domain.capabilities[step.capability]
        args = {**cap.defaults(), **step.args}
        if any(holds(cap, c, state, args) is not True for c in cap.pre):
            return False
        state = effect(cap, state, args)
    return all(same(state.get(var), value) for var, value in [*goals(domain, capability, values, results), *domain.rest.items()])


def test_the_pddl_is_the_modules_actions(domains):
    text, problem = pddl(domains["filling"], "Filling", {"FillVolume": 2.0}, ("FillWeight",))
    assert [line.split()[1] for line in text.splitlines() if line.strip().startswith("(:action")] == [
        "referencing", "positioning", "dosing", "taring", "weighing"]
    assert "(increase (product_contentvolume) (amount ?volume))" in text
    assert "(>= (linearaxis_actualposition_position) 40.0)" in text          # the needle in the vial
    assert "(:goal (and (= (product_contentvolume) 2.0) (product_weighed)" in problem
    assert {str(var): kind for var, kind in kinds(domains["filling"]).items()}["Scale_Weight.Weight"] == "measured"


def test_the_hddl_has_the_tasks_and_methods(domains):
    text, problem = hddl(domains["filling"], "Filling", {"FillVolume": 15.0}, ("FillWeight",))
    assert "(:task filling :parameters (?fillvolume - value))" in text
    assert "(:method m_product_contentvolume_dosing_more" in text            # adding in several doses
    assert "(sum v_7p5 v_7p5 v_15p0)" in problem
    assert "(t0 (filling v_15p0)) (t1 (achieve_product_weighed))" in problem


def test_what_cannot_be_said_is_refused(domains):
    domain = copy.deepcopy(domains["filling"])
    domain.capabilities["Weighing"].pre.append(
        Constraint("ContainerType", Var(PRODUCT, "ContainerType"), Expression("=", "glass")))
    with pytest.raises(NotExpressible, match="glass"):
        pddl(domain, "Filling", {"FillVolume": 2.0})


up = pytest.importorskip("unified_planning", reason="the planners extra: pip install -e .[planners]")


@pytest.fixture(scope="module")
def reader():
    from unified_planning.io import PDDLReader
    from unified_planning.shortcuts import get_environment
    get_environment().credits_stream = None
    return PDDLReader


def validate(problem, found) -> str:
    from unified_planning.shortcuts import PlanValidator
    with PlanValidator(problem_kind=problem.kind) as validator:
        return validator.validate(problem, found).status.name


@pytest.mark.parametrize("module, capability, values, results", CASES)
def test_gtpyhops_plans_validate_against_the_pddl(domains, reader, module, capability, values, results):
    domain = domains[module]
    steps = plan(domain, capability, values, results)
    text, problem_text = pddl(domain, capability, values, results, steps=steps)
    parsing = reader()
    problem = parsing.parse_problem_string(text, problem_text)
    assert validate(problem, parsing.parse_plan_string(problem, "\n".join(plan_text(domain, steps, problem_text)))) == "VALID"


@pytest.mark.skipif(shutil.which("java") is None, reason="ENHSP runs on Java")
@pytest.mark.parametrize("module, capability, values, results", CASES)
def test_enhsp_plans_the_cases_from_the_pddl(domains, reader, module, capability, values, results):
    pytest.importorskip("up_enhsp")
    from unified_planning.shortcuts import OneshotPlanner
    domain = domains[module]
    text, problem_text = pddl(domain, capability, values, results)
    problem = reader().parse_problem_string(text, problem_text)
    with OneshotPlanner(name="enhsp") as planner:
        result = planner.solve(problem)
    assert result.plan is not None, result.status
    assert validate(problem, result.plan) == "VALID"
    steps = pddl_steps(domain, [(a.action.name, [str(p) for p in a.actual_parameters]) for a in result.plan.actions],
                       problem_text)
    assert carried_out(domain, capability, values, results, steps)


@pytest.mark.parametrize("module, capability, values, results", CASES)
def test_aries_plans_the_cases_from_the_hddl(domains, reader, module, capability, values, results):
    pytest.importorskip("up_aries")
    from unified_planning.shortcuts import OneshotPlanner
    domain = domains[module]
    text, problem_text = hddl(domain, capability, values, results)
    problem = reader().parse_problem_string(text, problem_text)
    with OneshotPlanner(name="aries") as planner:
        result = planner.solve(problem, timeout=60)
    assert result.plan is not None, result.status
    assert validate(problem, result.plan) == "VALID"
    actions = result.plan.action_plan.actions
    steps = hddl_steps(domain, [(a.action.name, [str(p) for p in a.actual_parameters]) for a in actions])
    assert carried_out(domain, capability, values, results, steps)
    if module == "filling":       # as much as GTPyhop doses (Aries does not keep the doses few: 1 + 1 for 2)
        doses = lambda found: [s.args["Volume"] for s in found if s.capability == "Dosing"]     # noqa: E731
        assert sum(doses(steps)) == pytest.approx(sum(doses(plan(domain, capability, values, results))))
