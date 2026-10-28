"""The evaluation's figure for the paper, from the newest scenario results (cell/eval/results).

    python cell/eval/figures.py            # -> docs/figures/evaluation-downtime.pdf and .svg
    python cell/eval/figures.py --png x.png    # ... and a PNG to look at

How long the module is down for each change, made online (modsync reconfigure) and by a restart
(a new boot file): one axis, seconds. Needs matplotlib (not one of the project's extras).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                              # noqa: E402
from matplotlib.patches import PathPatch                                     # noqa: E402
from matplotlib.path import Path as Shape                                    # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RESULTS, FIGURES = ROOT / "cell" / "eval" / "results", ROOT / "docs" / "figures"
# The palette of docs/figures (online: the method's green), checked with the dataviz validator.
ONLINE, RESTART = "#5B963B", "#3B78B0"
TEXT, MUTED, GRID = "#252B2D", "#6E777B", "#E3E6E8"
SCENARIOS = {"value": "A value changed", "written": "A skill written", "planned": "A skill planned"}


def newest() -> dict:
    found = sorted(p for p in RESULTS.glob("*.json") if not p.name.startswith("planners-"))
    if not found:
        sys.exit(f"no scenario results in {RESULTS}")
    return json.loads(found[-1].read_text(encoding="utf-8"))


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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--png", help="also write a PNG to look at")
    args = parser.parse_args(argv)
    results = newest()
    runs = results["scenarios"]
    plt.rcParams.update({"font.family": "Arial", "font.size": 8, "text.color": TEXT, "axes.labelcolor": TEXT,
                         "xtick.color": MUTED, "ytick.color": TEXT, "svg.fonttype": "none", "pdf.fonttype": 42})
    fig, ax = plt.subplots(figsize=(3.35, 1.9))
    height, gap = 0.3, 0.04
    top = 4.0
    for row, (key, title) in enumerate(SCENARIOS.items()):
        y = len(SCENARIOS) - 1 - row
        online = statistics.median(r["online"]["down_s"] for r in runs[key])
        restart = statistics.median(r["restart"]["down_s"] for r in runs[key])
        for value, colour, offset in ((online, ONLINE, height / 2 + gap / 2), (restart, RESTART, -height / 2 - gap / 2)):
            bar(ax, y + offset, value, height, colour, radius=0.06)
            said = f"{value:.1f} s" if value > 0 else "0 s, kept running"
            ax.text(max(value, 0) + 0.06, y + offset, said, va="center", ha="left", fontsize=7, color=TEXT)
    ax.set_yticks(range(len(SCENARIOS)), list(reversed(SCENARIOS.values())))
    ax.set_xlim(0, top)
    ax.set_ylim(-0.6, len(SCENARIOS) - 0.4)
    ax.set_xlabel("Time the module is down (s)", fontsize=7.5, color=MUTED)
    ax.xaxis.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", length=0, labelsize=7)
    handles = [plt.Rectangle((0, 0), 1, 1, color=ONLINE), plt.Rectangle((0, 0), 1, 1, color=RESTART)]
    fig.legend(handles, ["Online (modsync)", "By a restart"], loc="upper center", ncol=2, frameon=False, fontsize=7,
               handlelength=1.0, handleheight=0.8, borderaxespad=0.2, columnspacing=1.5)
    fig.tight_layout(pad=0.3, rect=(0, 0, 1, 0.9))
    for suffix in ("pdf", "svg"):
        out = FIGURES / f"evaluation-downtime.{suffix}"
        fig.savefig(out)
        print(out)
    if args.png:
        fig.savefig(args.png, dpi=300)
    return 0


if __name__ == "__main__":
    sys.exit(main())
