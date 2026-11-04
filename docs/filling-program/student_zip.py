"""Bundle the filling program and its documentation for students into one zip.

    python docs/filling-program/student_zip.py <zip file>     (from the repository's root)

The zip keeps the repository's folder layout, so the documents' links between each other and to the
4diac projects work; a link to a document that is not in the zip points to it on GitHub instead.
"""
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(sys.argv[1])
TOP = "filling-program-for-students"
GITHUB = "https://github.com/AAUSmartProductionLab/iec61499-mgmt-py/blob/main/"

DOCS = ["filling-program.md", "filling-program-screenshots.md", "module-rules.md", "modules.md"]
FOLDERS = ["docs/filling-program", "docs/figures/4diac_figs", "cell/control/FillingModule",
           "cell/control/StopperingModule", "cell/control/CappingModule"]
FILES = ["runtime/kit/README.md"]
SKIP = (".py", ".pyc")
LEAVE_OUT = {"docs/filling-program/maintaining.md"}

README = """# The lab's module programs, for students

What is in here:

- `docs/filling-program.md`: start here. What every function block of the lab's module programs
  does, in plain words, with the filling module as the example and a picture of each block
  (`docs/filling-program/`), the state machines drawn as the 4diac IDE lays them out, and, step by
  step, how to make a new piece of equipment and a skill primitive by hand in the 4diac IDE
  (section 10), build FORTE with them and run them on the PC and the Pi (section 11).
- `docs/filling-program-screenshots.md`: the same text with screenshots of the 4diac IDE where there
  are some (`docs/figures/4diac_figs/`).
- `docs/module-rules.md`, `docs/modules.md`: the rules every module follows, and the lab's modules
  and their hardware. Links to other documents go to the repository on GitHub.
- `cell/control/StopperingModule` and `cell/control/CappingModule`: the projects you work on, and
  `cell/control/FillingModule`, the example. Open one in the 4diac IDE 3.3 with *File > Import >
  General > Existing Projects into Workspace*, choose its folder and tick *Copy projects into
  workspace*, then open its system (`StopperingModule.sys`). Each has two applications: the one
  ending in `_pi` for the module's Raspberry Pi, the other for your PC.
- `runtime/kit/README.md`: the README of the FORTE kit (`forte-kit.zip`, which you get separately),
  which builds FORTE with your block types and puts it on the Pi.

To read the Markdown with its pictures, open the folder in VS Code (or any Markdown viewer) and open
the preview of `docs/filling-program.md`.
"""


def relink(text: str, here: str) -> str:
    """A link to a document or file that is not in the zip goes to GitHub."""
    inside = {f"docs/{d}" for d in DOCS} | set(FILES)

    def fix(m):
        target = m.group(2)
        if re.match(r"[a-z]+:", target) or target.startswith("#"):
            return m.group(0)
        path, _, anchor = target.partition("#")
        full = (Path(here).parent / path).as_posix()
        parts = []
        for part in full.split("/"):
            if part == "..":
                parts.pop()
            elif part != ".":
                parts.append(part)
        full = "/".join(parts)
        if not full.endswith(SKIP) and (full in inside or any(full.startswith(f + "/") or full == f for f in FOLDERS)):
            return m.group(0)
        return f"{m.group(1)}({GITHUB}{full}{'#' + anchor if anchor else ''})"
    return re.sub(r"(\]\s?)\(([^)\s]+)\)", fix, text)


with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr(f"{TOP}/README.md", README)
    for d in DOCS:
        rel = f"docs/{d}"
        z.writestr(f"{TOP}/{rel}", relink((ROOT / rel).read_text(encoding="utf-8"), rel))
    for rel in FILES:
        z.write(ROOT / rel, f"{TOP}/{rel}")
    count = 0
    for folder in FOLDERS:
        for path in sorted((ROOT / folder).rglob("*")):
            rel = path.relative_to(ROOT).as_posix()
            if path.is_file() and path.suffix not in SKIP and "__pycache__" not in path.parts and rel not in LEAVE_OUT:
                z.write(path, f"{TOP}/{path.relative_to(ROOT).as_posix()}")
                count += 1
print(OUT, count + len(DOCS) + len(FILES) + 1, "files")
