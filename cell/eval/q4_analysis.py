"""The analysis of Q4 (docs/cirp-evaluation.md) from the rows of cell/eval/q4.py.

    python cell/eval/q4_analysis.py cell/eval/results/q4-<when>.jsonl [--figure docs/paper/cirp/figures]

Writes q4-<when>.md beside the rows: Q4a, the method's check and the two baselines against the
oracle on every mutant (precision and recall with 95 % Wilson intervals, per operator, every
disagreement); Q4b, the confusion matrix of the method's answer and the truth, the planned skills
and their times. With --figure, also check.pdf (Q4a) and match.pdf (Q4b).
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from q3_analysis import rate, wilson

METHODS = {"method": "The method's check", "rules": "Hand-written rules", "structure": "Structure only (4diac)"}
ANSWERS = ("offered", "after", "not")
ANSWER_NAMES = {"offered": "offered", "after": "after a reconfiguration", "not": "not offered"}
RULES = {"O1": "a step cannot be carried out", "O2": "spill", "O3": "crash into the bottom", "O4": "overflow",
         "O5": "foam (tip above the liquid)", "O6": "wrong volume", "O7": "no right weight", "O8": "tip left in the container"}


def confusion(rows, key):
    c = Counter((r["wrong"], bool(r[key])) for r in rows)
    return c[(True, True)], c[(True, False)], c[(False, True)], c[(False, False)]   # TP FN FP TN


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("rows", type=Path)
    ap.add_argument("--figure", type=Path)
    a = ap.parse_args()
    rows = [json.loads(line) for line in a.rows.read_text(encoding="utf-8").splitlines() if line.strip()]
    ra = [r for r in rows if r["part"] == "a"]
    rb = [r for r in rows if r["part"] == "b"]
    setups = {(r.get("commit"), r.get("tools_dirty")) for r in rows}
    md = [f"# Q4 results: {a.rows.name}", "", f"Setups (commit, tools changed): {sorted(setups, key=str)}", ""]

    if ra:
        wrong = sum(r["wrong"] for r in ra)
        md += ["## Q4a: the check on mutants", "",
               f"{len(ra)} distinct mutants of {', '.join(sorted({r['skill'] for r in ra}))}; the oracle finds "
               f"{wrong} wrong (the product spoiled or a step that cannot be carried out), {len(ra) - wrong} right.", "",
               "| Method | Caught (TP) | Missed (FN) | Rejected though right (FP) | Passed right (TN) | Recall | Precision |",
               "| --- | --- | --- | --- | --- | --- | --- |"]
        for key, name in METHODS.items():
            tp, fn, fp, tn = confusion(ra, key)
            md.append(f"| {name} | {tp} | {fn} | {fp} | {tn} | {rate(tp, tp + fn)} | {rate(tp, tp + fp)} |")
        md += ["", "Per operator (the method's check): wrong of all, caught, rejected though right.", "",
               "| Operator | Mutants | Wrong | Caught | Rejected though right |", "| --- | --- | --- | --- | --- |"]
        for op in sorted({r["operator"] for r in ra}):
            rs = [r for r in ra if r["operator"] == op]
            tp, fn, fp, tn = confusion(rs, "method")
            md.append(f"| {op} | {len(rs)} | {tp + fn} | {tp} of {tp + fn} | {fp} of {fp + tn} |")
        md += ["", "Per skill (the method's check).", "", "| Skill | Mutants | Wrong | Caught | Rejected though right |",
               "| --- | --- | --- | --- | --- |"]
        for skill in sorted({r["skill"] for r in ra}):
            rs = [r for r in ra if r["skill"] == skill]
            tp, fn, fp, tn = confusion(rs, "method")
            md.append(f"| {skill} | {len(rs)} | {tp + fn} | {tp} of {tp + fn} | {fp} of {fp + tn} |")
        caught = [r for r in ra if r["wrong"] and r["method"] and r["mutated"]]
        md += ["", f"A finding of the check names the mutated step in {sum(r['named'] for r in caught)} of the "
               f"{len(caught)} caught mutants that changed an existing step.",
               f"Time to check a mutant: median {1000 * statistics.median(r['check_s'] for r in ra):.1f} ms, "
               f"at most {1000 * max(r['check_s'] for r in ra):.1f} ms."]
        md += ["", "### Missed by the check (the oracle's rule)", ""]
        missed = Counter()
        for r in ra:
            if r["wrong"] and not r["method"]:
                rule = sorted(r["oracle"])[0]
                missed[rule] += 1
                md.append(f"- {r['skill']}: {r['what']} -> {', '.join(f'{k} {v}' for k, v in sorted(r['oracle'].items()))}")
        md += ["", "By the first rule broken: " + ", ".join(f"{k} {RULES[k]}: {n}" for k, n in sorted(missed.items())), ""]
        md += ["### Rejected by the check though the product is right", ""]
        for r in ra:
            if not r["wrong"] and r["method"]:
                md.append(f"- {r['skill']}: {r['what']} -> {r['method'][0][:160]}")
        md += ["", "### The rules against the check", "",
               f"- Caught by the check, missed by the rules: {sum(r['wrong'] and bool(r['method']) and not r['rules'] for r in ra)}",
               f"- Caught by the rules, missed by the check: {sum(r['wrong'] and bool(r['rules']) and not r['method'] for r in ra)}", ""]
        for r in ra:
            if r["wrong"] and r["method"] and not r["rules"]:
                md.append(f"  - {r['skill']}: {r['what']}")

    if rb:
        md += ["", "## Q4b: matching and planning", "",
               f"{len(rb)} cases: {len({(r['container'], r['volume'], r['weight']) for r in rb})} products on "
               f"{len({r['variant'] for r in rb})} module variants.", "",
               "| Answer \\ truth | " + " | ".join(ANSWER_NAMES[t] for t in ANSWERS) + " |", "| --- | --- | --- | --- |"]
        c = Counter((r["answer"], r["truth"]) for r in rb)
        for ans in ANSWERS:
            md.append(f"| {ANSWER_NAMES[ans]} | " + " | ".join(str(c[(ans, t)]) for t in ANSWERS) + " |")
        agree = sum(c[(t, t)] for t in ANSWERS)
        unsafe = sum(c[(ans, "not")] for ans in ("offered", "after"))
        md += ["", f"- Agreement: {rate(agree, len(rb))}.",
               f"- Offered (now or after a reconfiguration) though the module cannot: {unsafe}."]
        planned = [r for r in rb if r.get("route") == "planned"]
        if planned:
            right = sum(bool(r.get("planned_right")) for r in planned)
            times = [r["plan_s"] for r in planned]
            md += [f"- Planned: {len(planned)}; right the first time in the oracle: {rate(right, len(planned))}.",
                   f"- Time to plan (median of 5 each): median {1000 * statistics.median(times):.2f} ms, "
                   f"at most {1000 * max(times):.2f} ms.",
                   f"- Doses in the plans: {sorted(Counter(sum(1 for s in r['plan'] if s[0] == 'Dosing') for r in planned).items())}"]
        md += ["", "Per variant: agreement.", "", "| Variant | Cases | Agree | Offered | After | Not |", "| --- | --- | --- | --- | --- | --- |"]
        for v in sorted({r["variant"] for r in rb}, key=lambda v: ("full", "no scale", "small pump", "raised").index(v)):
            rs = [r for r in rb if r["variant"] == v]
            md.append(f"| {v} | {len(rs)} | {sum(r['answer'] == r['truth'] for r in rs)} | "
                      + " | ".join(str(sum(r["answer"] == t for r in rs)) for t in ANSWERS) + " |")
        md += ["", "### Disagreements", ""]
        for r in rb:
            if r["answer"] != r["truth"]:
                md.append(f"- {r['variant']}, {r['container']} {r['volume']} mL{', weight' if r['weight'] else ''}: "
                          f"answer {ANSWER_NAMES[r['answer']]} ({r.get('route', '')} {r.get('by', '')}), truth "
                          f"{ANSWER_NAMES[r['truth']]}")
    rt = [r for r in rows if r.get("part") == "t"]
    if rt:
        planned_t = [r for r in rt if r["answer"] == "after"]
        md += ["", "## Q4t: filling from the bottom, the needle rising with the liquid (added 6 Nov)", "",
               f"{len(rt)} cases: the syringe at {sorted({r['volume'] for r in rt})} mL, with and without its weight, "
               f"on {len({r['variant'] for r in rt})} module variants; the needle within 2 mm above and 3 mm below the "
               "liquid, planned by tracking, run in the oracle (which checks the 2 mm, not the 3).", "",
               "| Variant | Cases | Planned | Tracked | Right in the oracle | Not planned | Truth not |",
               "| --- | --- | --- | --- | --- | --- | --- |"]
        for v in sorted({r["variant"] for r in rt}, key=lambda v: ("full", "no scale", "small pump", "raised").index(v)):
            rs = [r for r in rt if r["variant"] == v]
            ps = [r for r in rs if r["answer"] == "after"]
            md.append(f"| {v} | {len(rs)} | {len(ps)} | {sum(bool(r.get('tracked')) for r in ps)} | "
                      f"{sum(bool(r.get('planned_right')) for r in ps)} | {len(rs) - len(ps)} | {sum(r['truth'] == 'not' for r in rs)} |")
        if planned_t:
            right = sum(bool(r.get("planned_right")) for r in planned_t)
            md += ["", f"- Planned: {len(planned_t)}; right the first time in the oracle: {rate(right, len(planned_t))}.",
                   f"- Not planned where the oracle says the module can: "
                   f"{sum(r['answer'] == 'not' and r['truth'] != 'not' for r in rt)}; planned where it cannot: "
                   f"{sum(r['answer'] == 'after' and r['truth'] == 'not' for r in rt)}.",
                   f"- Flow rates set: {sorted({r['flow_rate'] for r in planned_t if r.get('flow_rate')})} mL/s; time to plan: median "
                   f"{1000 * statistics.median(r['plan_s'] for r in planned_t):.2f} ms."]
        for r in rt:
            if r["answer"] == "after" and not r.get("planned_right"):
                md.append(f"- Wrong: {r['variant']}, {r['volume']} mL: {r.get('planned_broken')}")
    out = a.rows.with_suffix(".md")
    out.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(out)
    if a.figure:
        if ra:
            figure_check(ra, a.figure)
        if rb:
            figure_match(rb, a.figure)


# Figures: the method in the line's teal, the baselines in gray; what goes wrong light, labelled.
INK, MUTED, GRID = "#24292B", "#5E676B", "#E4E7E8"
TEAL, TEAL_LIGHT = "#1C6560", "#A9D9D2"
GRAY, GRAY_LIGHT = "#5E676B", "#D5D9DB"


def style():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "Arial", "font.size": 7, "axes.linewidth": 0.6, "axes.edgecolor": MUTED,
                         "xtick.color": MUTED, "ytick.color": MUTED, "text.color": INK, "axes.labelcolor": INK})
    return plt


def figure_check(ra, folder: Path) -> None:
    """Two rows of bars per method: of the wrong mutants, caught and missed; of the right ones,
    passed and rejected. The method's in teal, the baselines' in gray."""
    plt = style()
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 1.55), sharey=True, gridspec_kw={"wspace": 0.08})
    order = list(METHODS)[::-1]
    for ax, (title, good_is) in zip(axes, (("Mutants that spoil the product: caught", True),
                                           ("Mutants that do not: passed", False))):
        for y, key in enumerate(order):
            tp, fn, fp, tn = confusion(ra, key)
            good, bad = (tp, fn) if good_is else (tn, fp)
            n = good + bad
            dark, light = (TEAL, TEAL_LIGHT) if key == "method" else (GRAY, GRAY_LIGHT)
            ax.barh(y, good / n, height=0.62, color=dark, edgecolor="white", linewidth=1.0)
            ax.barh(y, bad / n, left=good / n, height=0.62, color=light, edgecolor="white", linewidth=1.0)
            p, lo, hi = wilson(good, n)
            ax.text(good / n - 0.015 if good / n > 0.25 else good / n + 0.015, y,
                    f"{100 * p:.0f} %  ({good} of {n})", va="center", ha="right" if good / n > 0.25 else "left",
                    color="white" if good / n > 0.25 else INK, fontsize=6.5)
        ax.set_xlim(0, 1)
        ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0], ["0", "25", "50", "75", "100 %" if not good_is else "100"])
        ax.set_title(title, fontsize=7, loc="left", color=INK)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.tick_params(axis="y", length=0)
        ax.xaxis.grid(True, color=GRID, lw=0.5)
        ax.set_axisbelow(True)
    axes[0].set_yticks(range(len(order)), [METHODS[k] for k in order])
    fig.subplots_adjust(left=0.165, right=0.985, top=0.86, bottom=0.16, wspace=0.08)
    folder.mkdir(parents=True, exist_ok=True)
    fig.savefig(folder / "check.pdf")
    fig.savefig(folder / "check.png", dpi=220)
    print(folder / "check.pdf")


def figure_match(rb, folder: Path) -> None:
    """The confusion matrix of the method's answer and the truth: agreement on the diagonal in teal,
    the rest in gray, each cell with its count."""
    plt = style()
    fig, ax = plt.subplots(figsize=(2.6, 1.9))
    c = Counter((r["answer"], r["truth"]) for r in rb)
    peak = max(c.values())
    for i, ans in enumerate(ANSWERS):
        for j, t in enumerate(ANSWERS):
            n = c[(ans, t)]
            base = TEAL if i == j else GRAY
            alpha = 0.12 + 0.88 * n / peak if n else 0.0
            ax.add_patch(plt.Rectangle((j, i), 0.96, 0.96, color=base, alpha=alpha, lw=0))
            ax.text(j + 0.48, i + 0.48, str(n), ha="center", va="center", fontsize=8,
                    color="white" if alpha > 0.55 else INK)
    labels = ["Offered", "After a\nreconfiguration", "Not offered"]
    ax.set_xlim(0, 3), ax.set_ylim(3, 0)
    ax.set_xticks([0.48, 1.48, 2.48], labels, fontsize=6)
    ax.set_yticks([0.48, 1.48, 2.48], labels, fontsize=6)
    ax.set_xlabel("What the module can do (oracle)")
    ax.set_ylabel("Method's answer")
    ax.xaxis.set_label_position("top"), ax.xaxis.tick_top()
    for side in ax.spines.values():
        side.set_visible(False)
    ax.tick_params(length=0)
    fig.subplots_adjust(left=0.30, right=0.98, top=0.76, bottom=0.03)
    folder.mkdir(parents=True, exist_ok=True)
    fig.savefig(folder / "match.pdf")
    fig.savefig(folder / "match.png", dpi=220)
    print(folder / "match.pdf")


if __name__ == "__main__":
    main()
