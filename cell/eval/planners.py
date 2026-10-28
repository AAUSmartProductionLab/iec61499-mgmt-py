"""The planning cases through GTPyhop and through standard planners on the exported PDDL and HDDL
(G6 in docs/next-steps.md), timed.

    python cell/eval/planners.py --runs 5

For each case, on the domain read from the module's AAS (built from its spec): GTPyhop's plan
(modplan.plan), ENHSP's on the PDDL and Aries's on the HDDL (through unified-planning, which starts
the planner for every problem: its time includes that). Every plan is validated against the PDDL or
HDDL problem and carried out by the domain's own semantics. Writes cell/eval/results/planners-<when>.json
and .md, a table of medians.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "aas61499-tools" / "tests")]

from modgen import SPECS, load                                              # noqa: E402
from modplan.export import hddl, hddl_steps, pddl, pddl_steps, plan_text   # noqa: E402
from modplan.plan import plan                                              # noqa: E402
from modplan.read import read                                              # noqa: E402
from modreg import model, profile as profiles                              # noqa: E402
from test_modplan_export import carried_out                                # noqa: E402

from unified_planning.io import PDDLReader                                 # noqa: E402
from unified_planning.shortcuts import OneshotPlanner, PlanValidator, get_environment   # noqa: E402

RESULTS = Path(__file__).parent / "results"
CASES = [("filling", "Filling", {"FillVolume": 2.0}, ("FillWeight",)),
         ("filling", "Filling", {"FillVolume": 15.0}, ("FillWeight",)),
         ("filling", "Filling", {"FillVolume": 0.5}, ()),
         ("stoppering", "Stoppering", {}, ())]


def label(case) -> str:
    module, capability, values, results = case
    said = ", ".join(f"{k} {v:g}" for k, v in values.items())
    return f"{capability}" + (f" ({said})" if said else "") + (f" + {', '.join(results)}" if results else "")


def valid(problem, found) -> bool:
    with PlanValidator(problem_kind=problem.kind) as validator:
        return validator.validate(problem, found).status.name == "VALID"


def run(domain, case) -> dict:
    _, capability, values, results = case
    started = time.perf_counter()
    steps = plan(domain, capability, values, results)
    found = {"gtpyhop": {"s": time.perf_counter() - started, "steps": len(steps)}}

    started = time.perf_counter()
    domain_text, problem_text = pddl(domain, capability, values, results, steps=steps)
    problem = PDDLReader().parse_problem_string(domain_text, problem_text)
    export_s = time.perf_counter() - started
    found["gtpyhop"]["valid"] = valid(problem, PDDLReader().parse_plan_string(problem, "\n".join(plan_text(domain, steps, problem_text))))
    started = time.perf_counter()
    with OneshotPlanner(name="enhsp") as planner:
        result = planner.solve(problem)
    actions = [(a.action.name, [str(p) for p in a.actual_parameters]) for a in result.plan.actions]
    found["enhsp"] = {"s": time.perf_counter() - started, "export_s": export_s, "steps": len(actions),
                      "valid": valid(problem, result.plan) and carried_out(domain, capability, values, results,
                                                                            pddl_steps(domain, actions, problem_text))}

    started = time.perf_counter()
    domain_text, problem_text = hddl(domain, capability, values, results)
    problem = PDDLReader().parse_problem_string(domain_text, problem_text)
    export_s = time.perf_counter() - started
    started = time.perf_counter()
    with OneshotPlanner(name="aries") as planner:
        result = planner.solve(problem, timeout=60)
    actions = [(a.action.name, [str(p) for p in a.actual_parameters]) for a in result.plan.action_plan.actions]
    found["aries"] = {"s": time.perf_counter() - started, "export_s": export_s, "steps": len(actions),
                      "valid": valid(problem, result.plan) and carried_out(domain, capability, values, results,
                                                                            hddl_steps(domain, actions))}
    return found


def table(runs: list[dict]) -> list[str]:
    lines = ["| Case | GTPyhop: steps, ms | ENHSP (PDDL): steps, ms | Aries (HDDL): steps, ms | All valid |",
             "| --- | --- | --- | --- | --- |"]
    for case in runs[0]:
        each = [r[case] for r in runs]
        cell = lambda who: f"{each[0][who]['steps']}, {1000 * statistics.median(e[who]['s'] for e in each):.0f}"  # noqa: E731
        ok = all(e[who]["valid"] for e in each for who in ("gtpyhop", "enhsp", "aries"))
        lines.append(f"| {case} | {cell('gtpyhop')} | {cell('enhsp')} | {cell('aries')} | {'yes' if ok else 'no'} |")
    return lines


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=5)
    args = parser.parse_args(argv)
    get_environment().credits_stream = None
    domains = {}
    for name in sorted({case[0] for case in CASES}):
        envs = [model.build(p) for p in profiles.describe_all(load(SPECS / f"{name}.yaml"), "pi")]
        domains[name] = read(envs[0], envs[1:])
    runs = [{label(case): run(domains[case[0]], case) for case in CASES} for _ in range(args.runs)]
    when = datetime.now().strftime("%Y-%m-%dT%H%M")
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"planners-{when}.json").write_text(json.dumps({"when": when, "runs": runs}, indent=1), encoding="utf-8")
    lines = [f"# Planners of {when}, {args.runs} runs each, medians", "",
             "Time to plan; for ENHSP and Aries through unified-planning, which starts the planner for each problem.",
             "", *table(runs), ""]
    (RESULTS / f"planners-{when}.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
