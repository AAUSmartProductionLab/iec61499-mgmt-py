"""The analysis of Q1 (docs/cirp-evaluation.md) from the runs of cell/eval/q1.py.

    python cell/eval/q1_analysis.py cell/eval/results/q1-<when>.jsonl [--figure docs/paper/cirp/figures]

Writes q1-<when>.md beside the runs: the runs and their checks, per cell the medians with 95 %
bootstrap intervals, the fits, the disturbance, the outliers and the hypotheses H1.1 to H1.4 answered.
With ``--figure``, also activation.pdf (and .png) for the paper.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

RNG = np.random.default_rng(20261103)
PHASES = ("read_s", "compile_s", "guard_s", "apply_s", "verify_s", "persist_s")
CHECKS = {
    "V1": "before: the program is what the AAS describes (the reconciler's reading)",
    "V1g": "before: the program is what the generator's boot file creates (instances, types, connections, values)",
    "V2": "the reconciler finished and reported the change verified",
    "V3": "after: the program is what the changed AAS describes (read again by the harness)",
    "V3g": "after: the program is what the generator's boot file of the changed program creates",
    "V4": "the commands sent, by operation, are those the generator's boot files call for",
    "V5": "the new composite runs and succeeds (first run of each cell)",
    "V6": "the skill running meanwhile succeeds",
    "V7": "after a restart: the program is what the changed AAS describes",
    "V7g": "after a restart: the program is what the generator's boot file creates",
    "V8": "the amended boot file creates, writes and connects what the generator's does (as sets)",
    "V9": "the module's state did not change during the change (Execute; Idle and free)",
    "V10": "FORTE logged no error (e.g. an event dropped from a full queue)",
}


def ci(values, stat=np.median, n: int = 10_000) -> tuple[float, float, float]:
    """The statistic and its 95 % percentile bootstrap interval."""
    v = np.asarray([x for x in values if x is not None], dtype=float)
    if len(v) == 0:
        return (float("nan"),) * 3
    if len(v) == 1:
        return float(stat(v)), float("nan"), float("nan")
    boot = stat(RNG.choice(v, size=(n, len(v)), replace=True), axis=1)
    return float(stat(v)), float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))


def fmt(t: tuple[float, float, float], scale: float = 1.0, digits: int = 3) -> str:
    m, lo, hi = (x * scale for x in t)
    if np.isnan(lo):
        return f"{m:.{digits}f}"
    return f"{m:.{digits}f} [{lo:.{digits}f}, {hi:.{digits}f}]"


def fit(x, y) -> tuple[float, float, float]:
    """Least squares y = a + b x; returns (a, b, R²)."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    b, a = np.polyfit(x, y, 1)
    pred = a + b * x
    ss_res, ss_tot = float(((y - pred) ** 2).sum()), float(((y - y.mean()) ** 2).sum())
    return float(a), float(b), 1 - ss_res / ss_tot if ss_tot else float("nan")


def outliers(values) -> list[float]:
    v = np.asarray(values, float)
    q1, q3 = np.percentile(v, [25, 75])
    lo, hi = q1 - 3 * (q3 - q1), q3 + 3 * (q3 - q1)
    return [float(x) for x in v if x < lo or x > hi]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", type=Path)
    ap.add_argument("--figure", type=Path)
    a = ap.parse_args()
    rows = [json.loads(line) for line in a.runs.read_text(encoding="utf-8").splitlines() if line.strip()]
    real = [r for r in rows if not r.get("warmup")]
    ok = [r for r in real if r.get("ok")]
    by_cell: dict[str, list[dict]] = defaultdict(list)
    for r in ok:
        by_cell[r["cell"]["id"]].append(r)
    cells = {r["cell"]["id"]: r["cell"] for r in real}
    md = [f"# Q1 results: {a.runs.name}", ""]

    # The runs and their checks.
    setups = {(r.get("commit"), r.get("forte_sha256"), r.get("machine"), r.get("tools_dirty")) for r in rows}
    md += ["## Runs", "",
           f"- {len(rows)} runs, {len(rows) - len(real)} warm-up runs left out, {len(real)} counted; "
           f"{len(ok)} passed every check.",
           f"- Setups (commit, FORTE hash, machine, tools changed): {sorted(setups, key=str)}"]
    failures = [r for r in real if not r.get("ok")]
    if failures:
        md.append(f"- Not passed ({len(failures)}):")
        for r in failures:
            failed = [k for k, v in (r.get("checks") or {}).items() if v is False]
            md.append(f"  - {r['cell']['id']} run {r['replicate']}: {r.get('failure')}, "
                      f"{failed or ''} {r.get('error', '')[:300]}")
    checks = defaultdict(lambda: [0, 0])
    for r in real:
        for k, v in (r.get("checks") or {}).items():
            if v is not None:
                checks[k][0] += bool(v)
                checks[k][1] += 1
    md += ["", "| Check | What | Passed |", "| --- | --- | --- |"] + [
        f"| {k} | {CHECKS.get(k, '')} | {p} of {n} |" for k, (p, n) in sorted(checks.items(), key=lambda kv: (len(kv[0]), kv[0]))]
    registering = [r for r in real if (r.get("out") or {}).get("registering_errors")]
    md.append(f"\nRuns in which the OPC UA server failed to register with a discovery server (not a check): "
              f"{len(registering)} of {len(real)}.")
    per_cell = defaultdict(int)
    for r in ok:
        per_cell[r["cell"]["id"]] += 1
    short = {cid: n for cid, n in per_cell.items() if n < max(per_cell.values(), default=0)}
    md.append(f"\nRuns per cell that passed: {min(per_cell.values(), default=0)} to {max(per_cell.values(), default=0)}"
              + (f"; fewer in {short}" if short else ""))

    def cell_rows(set_, **kw):
        out = []
        for cid, c in sorted(cells.items(), key=lambda kv: (kv[1]["steps"], kv[1]["branches"], kv[1]["program"])):
            if c["set"] == set_ and all(c.get(k, "execute" if k == "start" else None) == v for k, v in kw.items()):
                out.append((c, by_cell.get(cid, [])))
        return out

    # A: flow changes, sequences.
    md += ["", "## A: a new composite (sequence), online", "",
           "Seconds, median [95 % interval]; commands and bytes as in every run of the cell.", "",
           "| Steps | Program | Runs | Activation | read | compile | apply | verify | Commands | Bytes |",
           "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    xs_cmd, ys_act, xs_inst, ys_read, steps_cmd = [], [], [], [], []
    for c, rs in cell_rows("A"):
        if not rs:
            md.append(f"| {c['steps']} | {c['program']} | 0 | | | | | | | |")
            continue
        o = [r["out"] for r in rs]
        cmds = sorted({x["commands"] for x in o})
        md.append(f"| {c['steps']} | {c['program']} | {len(rs)} | {fmt(ci([x['t_act_s'] for x in o]))} | "
                  + " | ".join(fmt(ci([x[p] for x in o])) for p in ("read_s", "compile_s", "apply_s", "verify_s"))
                  + f" | {cmds} | {sorted({x['bytes'] for x in o})} |")
        for x in o:
            xs_cmd.append(x["commands"]), ys_act.append(x["t_act_s"])
            xs_inst.append(x["instances_before"]), ys_read.append(x["read_s"])
        steps_cmd += [(c["steps"], x["commands"]) for x in o]

    # The cost of verifying: the reconciler's own reading, before and after.
    md += ["", "## The reconciler's reading (before the change and to verify it)", "",
           "Management requests that read, per run; of the read phase: the program read, the AAS interpreted, compared.", "",
           "| Steps | Program | Reading requests | program read | AAS | compare |", "| --- | --- | --- | --- | --- | --- |"]
    for c, rs in cell_rows("A"):
        if rs:
            o = [r["out"] for r in rs]
            md.append(f"| {c['steps']} | {c['program']} | {sorted({sum(x.get('reading', {}).values()) for x in o})} | "
                      + " | ".join(fmt(ci([x["read"][p] for x in o])) for p in ("program_s", "aas_s", "compare_s")) + " |")

    # B: parallel.
    md += ["", "## B: a new composite of 8 steps in parallel branches, online, program size 1", "",
           "| Branches | Runs | Activation | Commands | Ran (V5) |", "| --- | --- | --- | --- | --- |"]
    for c, rs in cell_rows("B") + [(c, rs) for c, rs in cell_rows("A", steps=8, program=1)]:
        if rs:
            o = [r["out"] for r in rs]
            ran = any(r["checks"].get("V5") for r in rs)
            md.append(f"| {c['branches']} | {len(rs)} | {fmt(ci([x['t_act_s'] for x in o]))} | "
                      f"{sorted({x['commands'] for x in o})} | {'yes' if ran else 'not run'} |")

    # C and D: parameter online, restarts.
    md += ["", "## C: a parameter, online", "",
           "From Execute (an order running): the module stopped and released, the value written, occupied, "
           "reset and started again. From Idle (between orders): the value written; the module stays Idle.", "",
           "Unavailable as polled (each wait up to 50 ms late) and by FORTE's timestamps.", "",
           "| Start | Program | Runs | Activation | Unavailable | by FORTE's clock | of it: stop | reset | start |",
           "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    online_param = {}
    for start in ("execute", "idle"):
        for c, rs in cell_rows("C", start=start):
            if rs:
                o = [r["out"] for r in rs]
                online_param[(start, c["program"])] = ci([x["u_s"] for x in o])
                md.append(f"| {start} | {c['program']} | {len(rs)} | {fmt(ci([x['t_act_s'] for x in o]))} | "
                          f"{fmt(online_param[(start, c['program'])])} | {fmt(ci([x.get('u_clock_s') for x in o]))} | "
                          + " | ".join(fmt(ci([x[p] for x in o])) if p in o[0] else "" for p in ("stop_s", "reset_s", "start_s"))
                          + " |")
    md += ["", "## D: by a restart (new boot file)", "",
           "Unavailable from stopping FORTE until the module is in Execute again; to Idle: load and reset only.", "",
           "| Change | Program | Runs | Generate | Unavailable | by FORTE's clock | to Idle | of it: load | reset | start | Boot file lines |",
           "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    restart, restart_idle = {}, {}
    for change in ("flow", "parameter"):
        for c, rs in cell_rows("D", change=change):
            if rs:
                o = [r["out"] for r in rs]
                restart[(change, c["program"])] = ci([x["u_s"] for x in o])
                restart_idle[(change, c["program"])] = ci([x["u_idle_s"] for x in o])
                md.append(f"| {change} | {c['program']} | {len(rs)} | {fmt(ci([x['generate_s'] for x in o]))} | "
                          f"{fmt(restart[(change, c['program'])])} | {fmt(ci([x.get('u_clock_s') for x in o]))} | "
                          f"{fmt(restart_idle[(change, c['program'])])} | "
                          + " | ".join(fmt(ci([x[p] for x in o])) for p in ("load_s", "reset_s", "start_s"))
                          + f" | {sorted({x['boot_lines'] for x in o})} |")

    # Disturbance.
    md += ["", "## Disturbance: Dispensing running while a composite is added", "",
           "d1 - d0: its duration with the change made meanwhile less its duration before, in the same FORTE.", "",
           "| Steps | Program | Runs | d0 (s) | d1 - d0 (ms) | relative (%) | clock |", "| --- | --- | --- | --- | --- | --- | --- |"]
    rel_all = []
    for c, rs in cell_rows("A"):
        o = [r["out"] for r in rs if r["out"].get("d0_s") is not None and r["out"].get("d1_s") is not None]
        if o:
            diff = [x["d1_s"] - x["d0_s"] for x in o]
            rel = [100 * (x["d1_s"] - x["d0_s"]) / x["d0_s"] for x in o]
            rel_all += rel
            md.append(f"| {c['steps']} | {c['program']} | {len(o)} | {fmt(ci([x['d0_s'] for x in o]))} | "
                      f"{fmt(ci(diff), 1000, 1)} | {fmt(ci(rel), 1, 2)} | {sorted({x['d1_clock'] for x in o})} |")

    # Fits: each phase on what drives it, and the activation time on both at once.
    md += ["", "## Fits", ""]
    flows = [r["out"] for r in ok if r["cell"]["set"] in "AB"]
    if len({x["commands"] for x in flows}) > 1:
        a0, b0, r2 = fit([x["commands"] for x in flows], [x["apply_s"] for x in flows])
        md.append(f"- Apply phase on commands (sets A, B): {a0 * 1000:.2f} ms + {b0 * 1000:.4f} ms per command, R² = {r2:.3f}")
    if len({x["connections_before"] for x in flows}) > 1:
        a0, b0, r2 = fit([x["connections_before"] for x in flows], [x["read_s"] + x["verify_s"] for x in flows])
        md.append(f"- Read and verify phases on the program's connections before the change: {a0 * 1000:.1f} ms + "
                  f"{b0 * 1000:.4f} ms per connection, R² = {r2:.3f} (reading part by part from about 600 on)")
        x = np.array([[1.0, f["commands"], f["connections_before"]] for f in flows])
        y = np.array([f["t_act_s"] for f in flows])
        coef, *_ = np.linalg.lstsq(x, y, rcond=None)
        pred = x @ coef
        r2 = 1 - float(((y - pred) ** 2).sum()) / float(((y - y.mean()) ** 2).sum())
        md.append(f"- Activation time on both: {coef[0] * 1000:.1f} ms + {coef[1] * 1000:.4f} ms per command + "
                  f"{coef[2] * 1000:.4f} ms per connection of the program, R² = {r2:.3f}")
    if flows:
        worst = max(flows, key=lambda f: f["t_act_s"])
        md.append(f"- The slowest activation of all {len(flows)} runs: {worst['t_act_s']:.3f} s")
    if len(set(xs_inst)) > 1:
        a0, b0, r2 = fit(xs_inst, ys_read)
        md.append(f"- Read phase on the program's instances: {a0 * 1000:.1f} ms + {b0 * 1000:.3f} ms per instance, R² = {r2:.3f}")
    if len({s for s, _ in steps_cmd}) > 1:
        a0, b0, r2 = fit([s for s, _ in steps_cmd], [c for _, c in steps_cmd])
        md.append(f"- Commands on steps (set A): {a0:.2f} + {b0:.3f} per step, R² = {r2:.4f}")

    # Outliers.
    md += ["", "## Outliers (beyond three interquartile ranges, kept)", ""]
    found_any = False
    for cid, rs in sorted(by_cell.items()):
        key = "t_act_s" if cells[cid]["mode"] == "online" else "u_s"
        vals = [r["out"][key] for r in rs if r["out"].get(key) is not None]
        if len(vals) >= 8 and (out := outliers(vals)):
            found_any = True
            md.append(f"- {cid}: {key} {[round(v, 4) for v in out]} (median {np.median(vals):.4f})")
    if not found_any:
        md.append("- none")

    # Hypotheses.
    md += ["", "## Hypotheses", ""]
    big = by_cell.get("A-flow-n32-k1-m20", [])
    if big:
        m = ci([r["out"]["t_act_s"] for r in big])
        md.append(f"- H1.1: 32 steps in a program of 20 composites: {fmt(m)} s; below 1 s: {'yes' if m[2] < 1 else 'no'} (upper bound). "
                  "Linearity: see the fits.")
    v4 = checks.get("V4")
    if v4:
        md.append(f"- H1.2: the commands, by operation, equal what the generator's boot files call for in {v4[0]} of "
                  f"{v4[1]} runs.")
        ops = defaultdict(set)
        for r in ok:
            if r["cell"]["set"] == "A":
                for op, count in r["out"]["measured"].items():
                    ops[op].add((r["cell"]["steps"], count))
        for op, points in sorted(ops.items()):
            if len({s for s, _ in points}) > 1 and len({c for _, c in points}) > 1:
                a0, b0, r2 = fit([s for s, _ in points], [c for _, c in points])
                md.append(f"  - {op}: {a0:.2f} + {b0:.3f} per step, R² = {r2:.4f}")
    if rel_all:
        r = ci(rel_all)
        md.append(f"- H1.3: the running skill's duration changed by {fmt(r, 1, 2)} %; within 2 %: "
                  f"{'yes' if max(abs(r[1]), abs(r[2])) < 2 else 'no'}.")
    for (start, m_), (ro, _, _) in sorted(online_param.items()):
        against = restart if start == "execute" else restart_idle
        if ("parameter", m_) in against:
            rp = against[("parameter", m_)][0]
            md.append(f"- H1.4, a value, from {start}, program {m_}: unavailable {rp:.3f} s by a restart against "
                      f"{ro:.3f} s online (x{rp / ro:.1f}); ten times at least: {'yes' if rp >= 10 * ro else 'no'}.")
    for (change, m_), (rf, _, _) in sorted(restart.items()):
        if change == "flow":
            md.append(f"- H1.4, a new composite, program {m_}: unavailable {rf:.2f} s by a restart against none online "
                      f"(V9: the module stayed in Execute).")
    out = a.runs.with_suffix(".md")
    out.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(out)

    if a.figure:
        figure(by_cell, cells, restart, a.figure)
        figure_unavailable(by_cell, cells, a.figure)


def figure_unavailable(by_cell, cells, folder: Path) -> None:
    """How long the module cannot take a product, per way of making a change, in its parts: a bar per
    way, medians over every program size, each part labelled. The change itself (the reconciler's
    work) in teal, what the module does around it in grays: homing dominates."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "Arial", "font.size": 7, "axes.linewidth": 0.6, "axes.edgecolor": "#5E676B",
                         "xtick.color": "#5E676B", "ytick.color": "#5E676B"})

    def med(cell_filter, key):
        vals = [r["out"][key] for cid, rs in by_cell.items() if cell_filter(cells[cid]) for r in rs
                if r["out"].get(key) is not None]
        return float(np.median(vals)) if vals else 0.0, len(vals)

    def is_c(start):
        return lambda c: c["set"] == "C" and c.get("start", "execute") == start
    restart_flow = lambda c: c["set"] == "D" and c.get("change") == "flow"            # noqa: E731
    idle_u, n_idle = med(is_c("idle"), "u_s")
    exe = {k: med(is_c("execute"), k)[0] for k in ("u_s", "stop_s", "reset_s", "start_s")}
    rst = {k: med(restart_flow, k)[0] for k in ("u_s", "load_s", "reset_s", "start_s")}
    n_flow = sum(len(rs) for cid, rs in by_cell.items() if cells[cid]["set"] in "AB")
    TEAL, DARK, MID, LIGHT = "#1C6560", "#3E4447", "#8A9397", "#C9CED1"
    rows = [  # (label, [(seconds, color, part)])
        ("Add a skill, online", []),
        ("Change a value, online,\nbetween orders", [(idle_u, TEAL, "write")]),
        ("Change a value, online,\nduring an order", [(exe["stop_s"], LIGHT, "stop"),
                                                       (exe["u_s"] - exe["stop_s"] - exe["reset_s"] - exe["start_s"], TEAL, "write"),
                                                       (exe["reset_s"], DARK, "reset (homes)"), (exe["start_s"], LIGHT, "start")]),
        ("Any change,\nby a restart", [(rst["u_s"] - rst["load_s"] - rst["reset_s"] - rst["start_s"], LIGHT, "stop"),
                                       (rst["load_s"], MID, "load FORTE"), (rst["reset_s"], DARK, "reset (homes)"),
                                       (rst["start_s"], LIGHT, "start")]),
    ]
    fig, ax = plt.subplots(figsize=(3.4, 1.75))
    for y, (label, parts) in enumerate(rows):
        left = 0.0
        for seconds, color, part in parts:
            seconds = max(seconds, 0.0)
            ax.barh(y, seconds, left=left, height=0.58, color=color, edgecolor="white", linewidth=0.8)
            if seconds > 1.0:
                ax.text(left + seconds / 2, y, part, ha="center", va="center", fontsize=5.6,
                        color="white" if color in (TEAL, DARK, MID) else "#24292B")
            left += seconds
        total = sum(max(s, 0.0) for s, _, _ in parts)
        ax.text(left + 0.05, y, f"{total:.2f} s" if parts else f"0 s: it keeps running ({n_flow} runs)",
                va="center", fontsize=6.2, color="#24292B")
    ax.set_yticks(range(len(rows)), [r[0] for r in rows], fontsize=6.2)
    ax.invert_yaxis()
    ax.set_xlim(0, 4.0)
    ax.set_xlabel("Seconds the module cannot take a product (median)")
    ax.xaxis.grid(True, color="#E4E7E8", lw=0.5)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(axis="y", length=0)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=TEAL, label="the change"), Patch(color=LIGHT, label="stop, start"),
                       Patch(color=MID, label="load FORTE"), Patch(color=DARK, label="reset (homes)")],
              ncol=4, frameon=False, fontsize=5.8, loc="lower left", bbox_to_anchor=(-0.02, 1.0),
              handlelength=1.0, handleheight=0.8, columnspacing=1.0, handletextpad=0.4)
    fig.tight_layout(pad=0.3)
    fig.savefig(folder / "unavailable.pdf")
    fig.savefig(folder / "unavailable.png", dpi=220)
    print(folder / "unavailable.pdf")


def figure(by_cell, cells, restart, folder: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator
    plt.rcParams.update({"font.family": "Arial", "font.size": 7, "axes.linewidth": 0.6})
    fig, ax = plt.subplots(figsize=(3.4, 2.2))
    # The program's size is a magnitude: one hue, light to dark, and a marker of its own for each size
    # (the light step is pale on white, so the shape carries it too). The hue is the paper's gold, the
    # colour of a change over the management protocol in its other figures; ink and grey as there.
    shades = {1: "#E2C36E", 5: "#C99B2E", 10: "#9C7414", 20: "#5E4508"}
    INK, GREY = "#252B2D", "#6E777B"
    markers = {1: "o", 5: "s", 10: "^", 20: "D"}
    for m in (1, 5, 10, 20):
        xs, ys, lo, hi = [], [], [], []
        for n in (1, 2, 4, 8, 16, 32):
            rs = by_cell.get(f"A-flow-n{n}-k1-m{m}", [])
            if rs:
                c = ci([r["out"]["t_act_s"] for r in rs])
                xs.append(n), ys.append(c[0]), lo.append(c[0] - c[1] if not np.isnan(c[1]) else 0), hi.append(c[2] - c[0] if not np.isnan(c[2]) else 0)
        if xs:
            ax.errorbar(xs, ys, yerr=[lo, hi], marker=markers[m], ms=3.2, lw=1.2, capsize=1.5, color=shades[m],
                        markeredgecolor=shades[20] if m == 1 else shades[m], markeredgewidth=0.5,
                        label=f"{m} composite{'s' if m > 1 else ''}")
    flows = [v[0] for (change, _), v in restart.items() if change == "flow"]
    if flows:
        level = float(np.median(flows))
        ax.axhline(level, color=GREY, lw=0.9, ls=(0, (4, 2)))
        ax.text(1.0, level * 1.13, f"Unavailable by a restart: {level:.1f} s, at every program size", fontsize=6,
                color=INK)
    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ax.set_xticks([1, 2, 4, 8, 16, 32], ["1", "2", "4", "8", "16", "32"])
    ax.yaxis.set_major_locator(FixedLocator([0.03, 0.1, 0.3, 1, 3]))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
    ax.yaxis.set_minor_locator(NullLocator())
    ax.set_ylim(0.025, 6.5)
    ax.set_xlabel("Steps of the new composite")
    ax.set_ylabel("Seconds")
    ax.grid(axis="y", color="#E4E7E8", lw=0.5)
    ax.set_axisbelow(True)
    ax.legend(title="Activated online, in a program of", frameon=False, fontsize=6, title_fontsize=6,
              loc="upper left", bbox_to_anchor=(0.0, 0.84), alignment="left")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    fig.tight_layout(pad=0.3)
    folder.mkdir(parents=True, exist_ok=True)
    fig.savefig(folder / "activation.pdf")
    fig.savefig(folder / "activation.png", dpi=200)
    print(folder / "activation.pdf")


if __name__ == "__main__":
    main()
