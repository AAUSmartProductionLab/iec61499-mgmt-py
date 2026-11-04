"""Write the table of contents of docs/filling-program.md, with a link to every section.

The contents are the section "## Contents" before "## 1."; it is made from the headings (##, ###
and ####), with the anchors GitHub and VS Code give them. Run it from the repository's root after a
heading changed, then make the version with screenshots again:

    python docs/filling-program/toc.py
    python docs/filling-program/with_screenshots.py
"""
from pathlib import Path
import re

DOC = Path(__file__).resolve().parent.parent / "filling-program.md"
TITLE = "## Contents"


def slug(heading: str) -> str:
    """The anchor GitHub makes of a heading: lower case, no punctuation, spaces as hyphens."""
    text = heading.strip().lower()
    text = re.sub(r"[^\w\- ]", "", text)  # keeps letters, digits, _, - and spaces
    return text.replace(" ", "-")


def headings(lines: list[str]) -> list[tuple[int, str]]:
    found, fenced = [], False
    for line in lines:
        if line.startswith("```"):
            fenced = not fenced
        elif not fenced and (m := re.match(r"(#{2,4}) (.+)", line)):
            found.append((len(m.group(1)), m.group(2).strip()))
    return found


def main() -> None:
    text = DOC.read_text(encoding="utf-8")
    start = text.find("\n## 1. ")
    if start < 0:
        raise SystemExit("no section 1 in " + DOC.name)
    before, after = text[:start + 1], text[start + 1:]
    if TITLE + "\n" in before:
        before = before[:before.index(TITLE + "\n")]
    seen: dict[str, int] = {"contents": 1}
    entries = []
    for level, heading in headings(after.splitlines()):
        anchor = slug(heading)
        if anchor in seen:
            seen[anchor] += 1
            anchor = f"{anchor}-{seen[anchor] - 1}"
        else:
            seen[anchor] = 1
        entries.append("  " * (level - 2) + f"- [{heading}](#{anchor})")
    contents = TITLE + "\n\n" + "\n".join(entries) + "\n\n"
    DOC.write_text(before.rstrip("\n") + "\n\n" + contents + after, encoding="utf-8", newline="\n")
    print(f"{len(entries)} entries in the contents of {DOC.name}")


if __name__ == "__main__":
    main()
