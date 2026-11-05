"""Bundle the filling program and its documentation for students into one zip.

    python docs/filling-program/student_zip.py <zip file>     (from the repository's root)

The zip keeps the repository's folder layout, so the documents' links between each other and to the
4diac projects work; a link to a document that is not in the zip points to it on GitHub instead.
It also holds the guide as a PDF (make_pdf.py: pandoc, and Chrome or Edge) and the FORTE kit as it is
in runtime/dist/forte-kit.zip: make that first with runtime/make-kit.ps1.
"""
import re
import sys
import tempfile
import zipfile
from pathlib import Path

from make_pdf import make_pdf

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(sys.argv[1])
TOP = "filling-program-for-students"
GITHUB = "https://github.com/AAUSmartProductionLab/iec61499-mgmt-py/blob/main/"

DOCS = ["filling-program.md", "filling-program-screenshots.md", "module-rules.md", "modules.md"]
FOLDERS = ["docs/filling-program", "docs/figures/4diac_figs", "cell/control/FillingModule",
           "cell/control/StopperingModule", "cell/control/CappingModule"]
FILES = ["runtime/kit/README.md"]
KIT = ROOT / "runtime/dist/forte-kit.zip"
PDF = "docs/filling-program.md"
SKIP = (".py", ".pyc")
LEAVE_OUT = {"docs/filling-program/maintaining.md", "docs/filling-program/pdf.css"}

README = """# The lab's module programs, for students

Start with `docs/filling-program.pdf` (or `docs/filling-program.md`): what every function block of
the lab's module programs does, in plain words, and, step by step, how to make a new piece of
equipment and a new skill primitive by hand in the 4diac IDE (section 10), build FORTE with them and
run them on your PC and on the module's Pi (section 11).

What is in here:

| What | Where |
| --- | --- |
| The guide, to print or read | `docs/filling-program.pdf` |
| The guide in Markdown, with its pictures (`docs/filling-program/`) | `docs/filling-program.md` |
| The same with screenshots of the 4diac IDE (`docs/figures/4diac_figs/`) | `docs/filling-program-screenshots.md` |
| Templates of every new type you make, with your own part marked YOUR OWN, and how to use them | `docs/filling-program/templates/README.md` |
| The projects you work on, and the filling module, the example | `cell/control/StopperingModule`, `cell/control/CappingModule`, `cell/control/FillingModule` |
| The FORTE kit: builds FORTE with your block types and puts it on the Pi | `forte-kit.zip`, its README also in `runtime/kit/README.md` |
| The rules every module follows; the lab's modules and their hardware | `docs/module-rules.md`, `docs/modules.md` |

**The projects.** Open one in the 4diac IDE 3.3 with *File > Import > General > Existing Projects
into Workspace*. Choose its folder, tick *Copy projects into workspace*, then open its system (e.g.
`StopperingModule.sys`). Each has two applications: the one ending in `_pi` for the module's
Raspberry Pi, the other for your PC. The kit has the same projects in its folder `projects`: use one
or the other.

**The kit.** Unzip `forte-kit.zip` to `C:\\` so that you get `C:\\forte-kit`, and follow its
`README.md` (section 11 of the guide says when you need it).

**The Markdown** with its pictures: open this folder in VS Code (or any Markdown viewer) and open
the preview of `docs/filling-program.md`. Its links between the documents work there.
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


if not KIT.exists():
    raise SystemExit(f"No {KIT}: make it with runtime/make-kit.ps1")
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z, tempfile.TemporaryDirectory() as scratch:
    z.writestr(f"{TOP}/README.md", README)
    z.write(KIT, f"{TOP}/forte-kit.zip")
    pdf = Path(scratch) / "guide.pdf"
    make_pdf(ROOT / PDF, pdf)
    z.write(pdf, f"{TOP}/{PDF[:-3]}.pdf")
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
print(OUT, count + len(DOCS) + len(FILES) + 3, "files")
