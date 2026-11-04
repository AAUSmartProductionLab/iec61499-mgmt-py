"""The analysis of Q3 (docs/cirp-evaluation.md) from the runs of cell/eval/q3.py.

    python cell/eval/q3_analysis.py cell/eval/results/q3-<when>.jsonl

Writes q3-<when>.md beside the runs: the runs and their checks, per kind of drift the rates of
detection (against the generator's oracle), location, class and removal with 95 % Wilson intervals,
the false alarms, the confusion matrix of kind and class, the baseline, every drift missed, and the
cut changes (P4) one by one.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

KINDS = ("P1", "P2", "P3", "P4", "P5", "A1", "A2", "A3", "A4", "clean")
EXPECTED = {"P1": "value", "P2": "restart", "P3": "restart", "P4": "create", "P5": "record",
            "A1": "value", "A2": "restart", "A3": "restart", "A4": "restart", "clean": "none"}
ONLINE = {"value", "create"}
CLASSES = ("value", "create", "restart", "record", "none", "error")
NAMES = {"P1": "a value written in the program", "P2": "a connection deleted", "P3": "a stray instance",
         "P4": "a change cut after command i", "P5": "another type version than recorded",
         "A1": "a value changed in the AAS", "A2": "a step added in the AAS", "A3": "two steps swapped in the AAS",
         "A4": "a skill removed from the AAS", "clean": "nothing"}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    if n == 0:
        return (math.nan,) * 3
    p = k / n
    d = 1 + z * z / n
    centre, half = (p + z * z / (2 * n)) / d, z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, centre - half), min(1.0, centre + half)


def rate(k: int, n: int) -> str:
    if n == 0:
        return "-"
    p, lo, hi = wilson(k, n)
    return f"{k}/{n} ({100 * p:.0f} % [{100 * lo:.0f}, {100 * hi:.0f}])"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", type=Path)
    a = ap.parse_args()
    rows = [json.loads(line) for line in a.runs.read_text(encoding="utf-8").splitlines() if line.strip()]
    ok = [r for r in rows if r.get("ok")]
    md = [f"# Q3 results: {a.runs.name}", "", "## Runs", "",
          f"- {len(rows)} runs; {len(ok)} passed R1 to R3 and are counted.",
          f"- Setups (commit, FORTE hash, tools changed): {sorted({(r.get('commit'), r.get('forte_sha256'), r.get('tools_dirty')) for r in rows}, key=str)}"]
    for r in rows:
        if not r.get("ok"):
            failed = [k for k, v in (r.get("checks") or {}).items() if not v]
            md.append(f"  - not counted: {r['out']['drift']}: {r.get('failure')} {failed} {r.get('error', '')[:200]}"
                      f"{' ' + str(r['out'].get('forte_errors'))[:200] if r['out'].get('forte_errors') else ''}")

    by_kind: dict[str, list[dict]] = defaultdict(list)
    for r in ok:
        by_kind[r["out"]["drift"]["kind"]].append(r["out"])

    # Per kind: the drift as the oracle sees it, and what the reconciler made of it.
    md += ["", "## Per kind", "",
           "Drift: the oracle finds the program differs from what the AAS describes (P5: the record, by "
           "construction). Of those: detected by the reading the reconciler makes before every change, and "
           "by its audit (also every value; the IO addresses against the deployed boot file); of the audit's: "
           "located (a reported line names the element), sorted as the kind calls for, and removed online "
           "(value, create) or refused (restart, record).", "",
           "| Kind | What | Runs | Drift | Detected, reading | Detected, audit | Located | Class as expected | Removed or refused | Baseline detects |",
           "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    missed, alarms = [], []
    for kind in KINDS:
        rs = by_kind.get(kind, [])
        if not rs:
            continue
        drift = [o for o in rs if o["oracle_differs"]]
        quiet = [o for o in rs if not o["oracle_differs"]]
        seen = [o for o in drift if o["read"].get("detected")]
        hit = [o for o in drift if o.get("detected")]
        missed += [(kind, o) for o in drift if not o.get("detected")]
        alarms += [(kind, o) for o in quiet if o.get("detected")]
        expected = EXPECTED[kind]
        right = [o for o in hit if expected in o["audit"]["classes"]]
        handled = [o for o in hit if (o.get("removed") if expected in ONLINE else o.get("outcome") == "refused")]
        md.append(f"| {kind} | {NAMES[kind]} | {len(rs)} | {len(drift)} | {rate(len(seen), len(drift))} | {rate(len(hit), len(drift))} | "
                  f"{rate(sum(bool(o.get('located')) for o in hit), len(hit))} | {rate(len(right), len(hit))} | "
                  f"{rate(len(handled), len(hit))} | {rate(sum(bool(o.get('baseline_detects')) for o in drift), len(drift))} |")
    quiet_all = [o for kind in KINDS for o in by_kind.get(kind, []) if not o["oracle_differs"]]
    md += ["", f"False alarms, where the oracle finds no difference (the clean runs, and drifts that changed "
               f"nothing): {rate(len(alarms), len(quiet_all))}."]

    # The confusion matrix: the kind of drift against the classes the reconciler reported.
    md += ["", "## Kind of drift and the classes the audit reported (a run may report several)", "",
           "| Kind | Expected | " + " | ".join(CLASSES) + " |", "| --- | --- | " + " | ".join("---" for _ in CLASSES) + " |"]
    for kind in KINDS:
        rs = [o for o in by_kind.get(kind, []) if o["oracle_differs"]]
        if rs:
            count = Counter(c for o in rs for c in o["audit"]["classes"])
            md.append(f"| {kind} | {EXPECTED[kind]} | " + " | ".join(str(count.get(c, 0)) for c in CLASSES) + " |")

    # The outcomes of the attempt to remove the drift.
    md += ["", "## What the reconciler did", "", "| Kind | " + " | ".join(
        ("removed", "nothing to do", "refused", "applied, still differs", "failed")) + " |", "| --- " * 6 + "|"]
    for kind in KINDS:
        rs = [o for o in by_kind.get(kind, []) if o["oracle_differs"]]
        if rs:
            count = Counter(o.get("outcome") for o in rs)
            md.append(f"| {kind} | " + " | ".join(str(count.get(c, 0)) for c in
                                                  ("removed", "nothing to do", "refused", "applied, still differs", "failed")) + " |")
    reasons = Counter((kind, (o.get("refused") or "").split(":")[0]) for kind in KINDS
                      for o in by_kind.get(kind, []) if o.get("outcome") == "refused")
    if reasons:
        md += ["", "Refused, with the reason's first words:"] + [f"- {k}: {why} ({n})" for (k, why), n in sorted(reasons.items())]
    failures = [(kind, o) for kind in KINDS for o in by_kind.get(kind, []) if o.get("outcome") in ("failed", "applied, still differs")]
    if failures:
        md += ["", "Failed, or still different afterwards:"] + [
            f"- {k}: {o['drift']} {o.get('error', '')[:200]} {o.get('after', '')}" for k, o in failures[:40]]

    # Every drift missed, to look at.
    md += ["", f"## Drifts missed ({len(missed)})", ""]
    by_missed = Counter(k for k, _ in missed)
    md += [f"- {k}: {n} of {sum(o['oracle_differs'] for o in by_kind[k])}" for k, n in sorted(by_missed.items())]
    for kind, o in missed[:200]:
        d = {k: v for k, v in o["drift"].items() if k != "kind"}
        md.append(f"  - {kind} {d}: the oracle saw {json.dumps(o.get('oracle'))[:160]}")
    if alarms:
        md += ["", f"## False alarms ({len(alarms)})", ""] + [
            f"- {k} {o['drift']}: {o['audit'].get('lines')}" for k, o in alarms[:40]]

    # The cut changes one by one.
    cuts = sorted(by_kind.get("P4", []), key=lambda o: o["drift"]["cut"])
    if cuts:
        md += ["", "## P4: the change cut after command i", "",
               "| From i | To i | Read as | Outcome | The new skill ran | Dispensing ran (every tenth) |",
               "| --- | --- | --- | --- | --- | --- |"]
        groups: list[list] = []
        for o in cuts:
            key = (",".join(o["audit"]["classes"]), o.get("outcome"), o.get("new_skill_ran"))
            if groups and groups[-1][2] == key:
                groups[-1][1] = o["drift"]["cut"]
                groups[-1][3].append(o.get("dispensing_ran"))
            else:
                groups.append([o["drift"]["cut"], o["drift"]["cut"], key, [o.get("dispensing_ran")]])
        for first, last, (classes, outcome, ran), disp in groups:
            seen = [d for d in disp if d is not None]
            md.append(f"| {first} | {last} | {classes} | {outcome} | {ran} | {f'{sum(seen)}/{len(seen)}' if seen else ''} |")
    out = a.runs.with_suffix(".md")
    out.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
