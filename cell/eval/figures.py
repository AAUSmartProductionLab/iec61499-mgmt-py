"""The evaluation's figures for the CIRP paper, from the newest results in cell/eval/results.

    python cell/eval/figures.py                 # -> docs/paper/cirp/figures/downtime.pdf and effort.pdf
    python cell/eval/figures.py --png out-dir   # ... and PNGs to look at

downtime: how long the module is down for each change, made online (modsync reconfigure) and by a
restart (a new boot file); one axis, seconds. effort: the user actions to add a skill by hand in
4diac, in the skill editor and planned (cell/eval/effort.py). Each one column wide. Needs matplotlib
(not one of the project's extras).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import statistics
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                              # noqa: E402
from matplotlib.patches import PathPatch                                     # noqa: E402
from matplotlib.path import Path as Shape                                    # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RESULTS, FIGURES = ROOT / "cell" / "eval" / "results", ROOT / "docs" / "paper" / "cirp" / "figures"
# The palette of docs/figures (ours: the method's green; the usual way: blue; planned: berry), checked
# as a set, all pairs, with the dataviz validator.
ONLINE, RESTART, PLANNED = "#5B963B", "#3B78B0", "#B8336A"
TEXT, MUTED, GRID = "#252B2D", "#6E777B", "#E3E6E8"
SCENARIOS = {"value": "A value changed", "written": "A skill written", "planned": "A skill planned",
             "changeover": "Changeover,\ntwo modules"}
WIDTH = 3.31                                  # inches: one column of Procedia CIRP, 8.4 cm


def newest(pattern: str, exclude: str = "") -> Path:
    found = sorted(p for p in RESULTS.glob(pattern) if not (exclude and p.name.startswith(exclude)))
    if not found:
        sys.exit(f"no {pattern} in {RESULTS}")
    return found[-1]


def bar(ax, y: float, width: float, height: float, color: str, radius: float):
    """A horizontal bar from 0, its data end rounded (in data units along x: ``radius``)."""
    r = min(radius, width / 2)
    top, bottom = y + height / 2, y - height / 2
    if width <= 0:
        return
    k = 0.5523                                              # a quarter circle by a cubic Bézier
    ry = height * 0.18
    points = [(0, bottom), (width - r, bottom), (width - r + k * r, bottom), (width, bottom + ry - k * ry),
              (width, bottom + ry), (width, top - ry), (width, top - ry + k * ry), (width - r + k * r, top),
              (width - r, top), (0, top), (0, bottom)]
    codes = [Shape.MOVETO, Shape.LINETO, Shape.CURVE4, Shape.CURVE4, Shape.CURVE4, Shape.LINETO,
             Shape.CURVE4, Shape.CURVE4, Shape.CURVE4, Shape.LINETO, Shape.CLOSEPOLY]
    ax.add_patch(PathPatch(Shape(points, codes), facecolor=color, edgecolor="none"))


def axes(height: float, top: float, rows: int, label: str):
    """One column wide: a horizontal axis from 0 to ``top``, rows from the top, a recessive grid."""
    fig, ax = plt.subplots(figsize=(WIDTH, height))
    ax.set_xlim(0, top)
    ax.set_ylim(-0.6, rows - 0.4)
    ax.set_xlabel(label, fontsize=7.5, color=MUTED)
    ax.xaxis.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", length=0, labelsize=7)
    return fig, ax


def legend(fig, colors: list[str], names: list[str]):
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in colors]
    fig.legend(handles, names, loc="upper center", ncol=len(names), frameon=False, fontsize=7,
               handlelength=1.0, handleheight=0.8, borderaxespad=0.2, columnspacing=1.5)


def downtime(runs: dict):
    keys = [k for k in SCENARIOS if k in runs]
    fig, ax = axes(2.2, 8.0, len(keys), "Time the module is down (s)")
    height, gap = 0.3, 0.04
    for row, key in enumerate(keys):
        y = len(keys) - 1 - row
        online = statistics.median(r["online"]["down_s"] for r in runs[key])
        restart = statistics.median(r["restart"]["down_s"] for r in runs[key])
        for value, colour, offset in ((online, ONLINE, height / 2 + gap / 2), (restart, RESTART, -height / 2 - gap / 2)):
            bar(ax, y + offset, value, height, colour, radius=0.1)
            said = f"{value:.1f} s" if value > 0 else "0 s, kept running"
            ax.text(max(value, 0) + 0.1, y + offset, said, va="center", ha="left", fontsize=7, color=TEXT)
    ax.set_yticks(range(len(keys)), [SCENARIOS[k] for k in reversed(keys)])
    legend(fig, [ONLINE, RESTART], ["Online", "By a restart"])
    fig.tight_layout(pad=0.3, rect=(0, 0, 1, 0.92))
    return fig


def effort(table: str):
    """The effort table of cell/eval/effort.py: per skill, actions by hand, in the editor, planned."""
    rows = []
    for line in table.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 4 or not re.match(r"\d", cells[1]):
            continue
        name = cells[0].split(" (")[0]
        rows.append((name, *(int(m.group()) if (m := re.match(r"\d+", c)) else None for c in cells[1:])))
    fig, ax = axes(2.0, 180, len(rows), "User actions to add the skill")
    height, gap = 0.24, 0.03
    for row, (name, hand, editor, plan) in enumerate(rows):
        y = len(rows) - 1 - row
        bars = [(v, c) for v, c in ((hand, RESTART), (editor, ONLINE), (plan, PLANNED)) if v is not None]
        span = len(bars) * height + (len(bars) - 1) * gap
        for i, (value, colour) in enumerate(bars):
            yy = y + span / 2 - height / 2 - i * (height + gap)
            bar(ax, yy, value, height, colour, radius=2.5)
            ax.text(value + 2.5, yy, str(value), va="center", ha="left", fontsize=7, color=TEXT)
    ax.set_yticks(range(len(rows)), [r[0] for r in reversed(rows)])
    legend(fig, [RESTART, ONLINE, PLANNED], ["By hand in 4diac", "Skill editor", "Planned"])
    fig.tight_layout(pad=0.3, rect=(0, 0, 1, 0.9))
    return fig


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--png", help="also write PNGs into this folder, to look at")
    args = parser.parse_args(argv)
    plt.rcParams.update({"font.family": "Arial", "font.size": 8, "text.color": TEXT, "axes.labelcolor": TEXT,
                         "xtick.color": MUTED, "ytick.color": TEXT, "svg.fonttype": "none", "pdf.fonttype": 42})
    runs = json.loads(newest("*.json", exclude="planners-").read_text(encoding="utf-8"))["scenarios"]
    figures = {"downtime": downtime(runs), "effort": effort(newest("effort-*.md").read_text(encoding="utf-8"))}
    FIGURES.mkdir(parents=True, exist_ok=True)
    for name, fig in figures.items():
        out = FIGURES / f"{name}.pdf"
        fig.savefig(out)
        print(out)
        if args.png:
            fig.savefig(Path(args.png) / f"{name}.png", dpi=300)
    return 0


if __name__ == "__main__":
    sys.exit(main())
