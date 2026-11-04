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

DOCS = ["filling-program.md", "filling-program-screenshots.md", "building-skills.md", "module-rules.md", "modules.md"]
FOLDERS = ["docs/filling-program", "docs/figures/4diac_figs", "cell/control/FillingModule", "cell/control/StopperingModule"]
FILES = ["cell/modules/filling.yaml", "cell/modules/stoppering.yaml"]
SKIP = (".py", ".pyc")

README = """# The filling program, for students

What is in here:

- `docs/filling-program.md`: start here. What every function block of the filling module's
  IEC 61499 program does, in plain words, with a picture of each (`docs/filling-program/`), the
  state machines drawn as the 4diac IDE lays them out, and how to build a new piece of equipment and
  a skill primitive by hand (section 10.5).
- `docs/filling-program-screenshots.md`: the same text with screenshots of the 4diac IDE where there
  are some (`docs/figures/4diac_figs/`).
- `docs/building-skills.md`, `docs/module-rules.md`, `docs/modules.md`: how skills and equipment are
  built, the rules every module follows, and the lab's modules. Links to other documents go to the
  repository on GitHub.
- `cell/control/FillingModule` and `cell/control/StopperingModule`: the two 4diac projects. Open
  them in the 4diac IDE 3.3 with *File > Import > Existing Projects into Workspace*, choose the
  folder, then open the system (`FillingModule.sys`) and the application `Filling_pi` (the Pi) or
  `Filling` (the PC with the simulator).
- `cell/modules/filling.yaml`, `stoppering.yaml`: the specs the programs are generated from.

To read the Markdown with its pictures, open the folder in VS Code (or any Markdown viewer) and open
the preview of `docs/filling-program.md`. To run a program you need FORTE built with the module
types and, for the generator and the simulator, the whole repository:
{github}
""".format(github=GITHUB.replace("/blob/main/", ""))


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
            if path.is_file() and path.suffix not in SKIP and "__pycache__" not in path.parts:
                z.write(path, f"{TOP}/{path.relative_to(ROOT).as_posix()}")
                count += 1
print(OUT, count + len(DOCS) + len(FILES) + 1, "files")
