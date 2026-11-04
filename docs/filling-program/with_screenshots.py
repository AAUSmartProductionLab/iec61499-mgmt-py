"""Make docs/filling-program-screenshots.md: filling-program.md with the 4diac IDE's screenshots.

The text is the same as in filling-program.md; where a screenshot of a picture is in
docs/figures/4diac_figs, it is shown instead of the drawing. Pictures with no screenshot keep the
drawing. Edit filling-program.md, then run this again from the repository's root:

    python docs/filling-program/with_screenshots.py
"""
from pathlib import Path
import re

DOCS = Path(__file__).resolve().parent.parent
SOURCE = DOCS / "filling-program.md"
TARGET = DOCS / "filling-program-screenshots.md"
SHOTS = "figures/4diac_figs"

# Drawing -> the screenshots shown instead (file, what it shows), and the groups with no screenshot.
# Not used since 4 Nov 2026, when these types changed: module.png (MOD_StateManager, now with its
# gate), skill_core.png (SKILL_Core, now with its gate), and those of the primitives' insides
# (homeLogic, home_equipment, move_axis, move_axis_equipment, dispense_equipment, tare_execution,
# tare_equipment, weight_equipment: now Contract, Run and Port).
SCREENSHOTS = {
    "app-Filling_pi.svg": (
        [("moduleLevel.png", "The groups ModuleLevel, ModuleLevelSkills and Procedures"),
         ("equipment_io.png", "The group EquipmentIO"),
         ("primitives.png", "The group SkillPrimitives")], []),
    "inside-MOD_Occupation.svg": ([("occupation.png", "Inside MOD_Occupation")], []),
    "inside-MOD_OwnerView.svg": ([("MODOwner.png", "Inside MOD_OwnerView")], []),
    "inside-MOD_StateView.svg": ([("MODStateview.png", "Inside MOD_StateView")], []),
    "inside-IO_DO.svg": (
        [("down_out_internal.png", "Inside IO_DO, opened from the block Out_Down"),
         ("out_enable.png", "Inside IO_DO, opened from the block Out_Enable"),
         ("out_step_internal.png", "Inside IO_AO, opened from the block Out_Step: PWMChip and QW "
                                   "instead of GPIOChip and QX")], []),
    "inside-EQ_LinearAxis.svg": (
        [("linear_axis_el_logic.png", "Inside EQ_LinearAxis: the group Core"),
         ("linear_axis_channels.png", "Inside EQ_LinearAxis: the group Channels"),
         ("linear_axis_inputs.png", "Inside EQ_LinearAxis: the group Inputs"),
         ("linear_axis_outputs.png", "Inside EQ_LinearAxis: the group Outputs")], []),
    "inside-EQ_Pump.svg": ([("pump_internal.png", "Inside EQ_Pump: the groups Core and Channels")], []),
    "inside-EQ_Scale.svg": (
        [("scale_internal.png", "Inside EQ_Scale: the groups Core, Channels and Inputs")], []),
    "app-Dispensing.svg": (
        [("dispensing.png", "Inside Dispensing: the groups Core, Sequences, Results and Start")], []),
}

PICTURES_OLD = """**The pictures** are in [filling-program/](filling-program/). They are drawn from the program's
files with the positions, groups and sizes the 4diac IDE uses, so they look as the program looks in
the IDE; they are not screenshots of it. Open one on its own to see it full size. The same document
with screenshots of the IDE, where there are some, is
[filling-program-screenshots.md](filling-program-screenshots.md).
"""
PICTURES_NEW = """**This is the version with screenshots.** The text is that of
[filling-program.md](filling-program.md); where there is a screenshot of the 4diac IDE (in
[figures/4diac_figs/](figures/4diac_figs/)), it is shown instead of the drawing, so you see exactly
what the IDE shows. The other pictures are the drawings of [filling-program/](filling-program/),
made from the program's files with the IDE's positions, groups and sizes. Open a picture on its own
to see it full size. The screenshots of `MOD_StateManager`, `SKILL_Core` and the primitives' insides
were taken before these types changed, so their drawings are shown until they are taken again.
"""

LEGEND_OLD = "![How to read a block in the pictures](filling-program/legend.svg)\n"
LEGEND_NEW = LEGEND_OLD + """
The legend is a drawing; the screenshots differ from it in three things. The IDE colours a label by
the data type of its pin: green for an event, brown for a string (names, paths, channel ids),
grey-green for a BOOL, yellow for an LREAL and blue for a whole number or a time. A label with a
number is a green or coloured box with only the number in it (`2`). And inside a block you opened
from the application, a pin on the outside is named after that block: inside the block `Out_Down`
(an `IO_DO`), its input `INIT` is labelled `Out_Down.INIT`.
"""



def screenshots(drawing: str) -> str:
    shots, missing = SCREENSHOTS[drawing]
    text = "\n\n".join(f"![{alt}]({SHOTS}/{png})" for png, alt in shots)
    if missing:
        groups = " and ".join(f"`{g}`" for g in missing)
        word = "group" if len(missing) == 1 else "groups"
        text += (f"\n\nNo screenshot of the {word} {groups} yet; the drawing of the whole type is "
                 f"[{drawing}](filling-program/{drawing}).")
    return text


def main() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    for old, new in ((PICTURES_OLD, PICTURES_NEW), (LEGEND_OLD, LEGEND_NEW)):
        if old not in text:
            raise SystemExit(f"not found in {SOURCE.name}: {old.splitlines()[0]}")
        text = text.replace(old, new, 1)
    for drawing in SCREENSHOTS:
        pattern = re.compile(r"!\[[^\]]*\]\(filling-program/" + re.escape(drawing) + r"\)")
        text, n = pattern.subn(lambda _: screenshots(drawing), text, count=1)
        if n != 1:
            raise SystemExit(f"picture not found in {SOURCE.name}: {drawing}")
    for png in {png for shots, _ in SCREENSHOTS.values() for png, _ in shots}:
        if not (DOCS / SHOTS / png).exists():
            raise SystemExit(f"screenshot missing: {SHOTS}/{png}")
    TARGET.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {TARGET.relative_to(DOCS.parent)}")


if __name__ == "__main__":
    main()
