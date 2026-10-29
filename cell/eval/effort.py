"""The engineering effort of a new module level skill, three ways (E1 in docs/paper-outline.md).

    python cell/eval/effort.py      # -> cell/eval/results/effort-<when>.md

Counted as Dorofeev et al. (ETFA 2021) count it: user actions in an editor, one per element added or
value entered. For each skill of the filling module:

- by hand in 4diac: every block instance and subapplication added, every connection drawn, every
  value written, as the module rules build the skill (modsync's fragment, the generator's own
  pattern). The library and primitive types exist, so no type is written;
- in the skill editor on the AAS: the skill; each parameter (name and type: 2) and each of its unit,
  limits, default and meaning given; each step (added, its skill chosen: 2) and each of its
  bindings; each parallel block or decision, each comparison (operand and value: 2); each result;
- planned: the requirement only, its capability, each value and each result asked for.

How it then reaches the running module (a new boot file and a restart, or online) is the scenarios'
measure (cell/eval/scenarios.py), not counted here.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "aas61499-tools"), str(ROOT / "aas61499-tools" / "tests"), str(Path(__file__).parent)]

import scenarios                                                              # noqa: E402
from modplan.compose import compose                                           # noqa: E402
from modsync.described import described                                       # noqa: E402
from modsync.desired import fragment                                          # noqa: E402

RESULTS = Path(__file__).parent / "results"
PARAMETER_FIELDS = ("unit", "minimum", "maximum", "default", "meaning")


def by_hand(spec, name: str) -> dict:
    """User actions to build the skill in 4diac: instances, subapplications, connections, values."""
    flat, links = fragment(spec, [name], "Tail.INITO")
    subapps = {".".join(fb.split(".")[:i]) for fb in flat.fbs for i in range(1, fb.count(".") + 1)}
    counts = {"instances": len(flat.fbs), "subapplications": len(subapps), "connections": len(links),
              "values": len(flat.parameters)}
    return {**counts, "actions": sum(counts.values())}


def flow_actions(steps: list[dict]) -> int:
    """A step is added and its skill chosen (2), plus a binding each; a block or decision is 1, a
    comparison 2, and what it holds is counted the same way."""
    total = 0
    for step in steps:
        if "skill" in step:
            total += 2 + len(step.get("bind") or {})
            continue
        total += 1
        for key, value in step.items():
            if isinstance(value, list) and value and isinstance(value[0], dict):
                total += flow_actions(value) if any("skill" in v or "steps" in v or "branches" in v for v in value) \
                    else 2 * len(value)
            elif isinstance(value, dict) and key == "condition":
                total += 2 * max(1, sum(1 for v in value.values() if isinstance(v, (list, dict))))
    return total


def in_editor(spec, name: str) -> dict:
    """User actions to describe the skill in the skill editor."""
    skill = spec.composites[name].model_dump(exclude_none=True)
    parameters = sum(2 + sum(1 for f in PARAMETER_FIELDS if p.get(f) not in (None, "")) for p in skill.get("parameters", {}).values())
    steps = flow_actions(skill.get("execute", [])) + flow_actions(skill.get("stop", []))
    results = len(skill.get("results", {}))
    return {"parameters": parameters, "steps": steps, "results": results, "actions": 1 + parameters + steps + results}


def main() -> int:
    module, components = scenarios.delivered()
    written = scenarios.with_written(module, components)
    volume, results_asked = 15.0, ("FillWeight",)
    planned = compose(module, components, "Filling", {"FillVolume": volume}, results_asked, name="PlannedFilling").module
    cases = [("Dispensing (the module's own)", described(module, components), "Dispensing", None),
             (f"{scenarios.WRITTEN} (written in the editor)", described(written, components), scenarios.WRITTEN, None),
             (f"PlannedFilling, {volume:g} mL (planned)", described(planned, components), "PlannedFilling",
              1 + 1 + len(results_asked))]
    lines = ["# Engineering effort of a module level skill, user actions",
             "",
             "Counted as in Dorofeev et al. (ETFA 2021): one action per element added or value entered.",
             "",
             "| Skill | By hand in 4diac | In the skill editor | Planned |",
             "| --- | --- | --- | --- |"]
    for label, spec, name, requirement in cases:
        hand, editor = by_hand(spec, name), in_editor(spec, name)
        lines.append(f"| {label} | {hand['actions']} ({hand['instances']} instances, {hand['subapplications']} "
                     f"subapplications, {hand['connections']} connections, {hand['values']} values) | "
                     f"{editor['actions']} | {requirement if requirement is not None else '–'} |")
    text = "\n".join(lines) + "\n"
    print(text)
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"effort-{datetime.now():%Y-%m-%dT%H%M}.md"
    out.write_text(text, encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
