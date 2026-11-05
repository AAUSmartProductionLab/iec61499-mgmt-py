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
    ap.add_argument("runs", type=Path, nargs="+", help="a run, then the runs that repeat some of its drifts")
    ap.add_argument("--figure", type=Path, help="folder for detection.pdf")
    a = ap.parse_args()
    latest: dict[str, dict] = {}                      # a drift run again (after a fix) counts as its last run
    repeated = 0
    for path in a.runs:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                drift = row["out"]["drift"]               # as q3.identity: a value (P1) by its port alone
                key = json.dumps({k: v for k, v in drift.items() if not (drift["kind"] == "P1" and k == "was")},
                                 sort_keys=True)
                repeated += key in latest
                latest[key] = row
    rows = list(latest.values())
    ok = [r for r in rows if r.get("ok")]
    md = [f"# Q3 results: {' + '.join(p.name for p in a.runs)}", "", "## Runs", "",
          f"- {len(rows)} runs; {len(ok)} passed R1 to R3 and are counted"
          f"{f'; {repeated} repeated from the later files, the last run of a drift counted' if repeated else ''}.",
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
    out = a.runs[0].with_suffix(".md")
    out.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(out)
    if a.figure:
        figure(by_kind, len(alarms), len(quiet_all), a.figure)


SHORT = {"P1": "A value written", "P2": "A connection deleted", "P3": "A stray block", "P4": "A change cut short",
         "P5": "Another type version", "A1": "A value changed", "A2": "A step added", "A3": "Two steps swapped",
         "A4": "A skill removed"}


def figure(by_kind, alarms: int, quiet: int, folder: Path) -> None:
    """Per kind of drift (rows, in the program and in the AAS), the share detected by the baseline (the
    AAS against the deployed boot file), by the reading before every change, by the audit, and the
    share handled as its class calls for (removed online, or refused): a cell per rate, shaded by it,
    the method's columns in teal, the baseline's in gray."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "Arial", "font.size": 7, "text.color": "#24292B"})
    columns = ["Boot file\n(baseline)", "Read before\na change", "Audit", "Handled\nas its class"]
    kinds = [k for k in KINDS if k != "clean" and by_kind.get(k)]
    fig, ax = plt.subplots(figsize=(3.4, 2.75))
    for i, kind in enumerate(kinds):
        drift = [o for o in by_kind[kind] if o["oracle_differs"]]
        hit = [o for o in drift if o.get("detected")]
        expected = EXPECTED[kind]
        handled = [o for o in hit if (o.get("removed") if expected in ONLINE else o.get("outcome") == "refused")]
        counts = [sum(bool(o.get("baseline_detects")) for o in drift), sum(bool(o["read"].get("detected")) for o in drift),
                  len(hit), len(handled)]
        for j, k in enumerate(counts):
            p = k / len(drift) if drift else 0.0
            ax.add_patch(plt.Rectangle((j, i), 0.97, 0.92, color="#5E676B" if j == 0 else "#1C6560",
                                       alpha=0.08 + 0.92 * p, lw=0))
            ax.text(j + 0.485, i + 0.46, f"{100 * p:.0f} %" if p not in (0.0, 1.0) else ("100 %" if p else "0"),
                    ha="center", va="center", fontsize=6.4, color="white" if p > 0.55 else "#24292B")
        ax.text(-0.08, i + 0.46, f"{SHORT[kind]}  (n = {len(drift)})", ha="right", va="center", fontsize=6.2)
    split = sum(1 for k in kinds if k.startswith("P"))
    ax.axhline(split - 0.04, color="#24292B", lw=0.6, xmin=-0.9, clip_on=False)
    ax.text(-3.3, split / 2, "In the program", rotation=90, ha="center", va="center", fontsize=6.2, color="#5E676B")
    ax.text(-3.3, split + (len(kinds) - split) / 2, "In the AAS", rotation=90, ha="center", va="center",
            fontsize=6.2, color="#5E676B")
    ax.set_xlim(0, len(columns)), ax.set_ylim(len(kinds), 0)
    ax.set_xticks([j + 0.485 for j in range(len(columns))], columns, fontsize=6.2)
    ax.xaxis.tick_top()
    ax.set_yticks([])
    for side in ax.spines.values():
        side.set_visible(False)
    ax.tick_params(length=0)
    fig.text(0.98, 0.012, f"False alarms where nothing differs: {alarms} of {quiet}", ha="right", fontsize=6.2,
             color="#5E676B")
    fig.subplots_adjust(left=0.5, right=0.99, top=0.86, bottom=0.07)
    folder.mkdir(parents=True, exist_ok=True)
    fig.savefig(folder / "detection.pdf")
    fig.savefig(folder / "detection.png", dpi=220)
    print(folder / "detection.pdf")


if __name__ == "__main__":
    main()
