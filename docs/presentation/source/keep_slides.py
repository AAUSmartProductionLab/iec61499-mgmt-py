"""Keeps only the slides whose title contains one of the given texts, in deck order: one deck from another.

    python keep_slides.py <in.pptx> <out.pptx> "<title text>" ...
"""
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

SKILL = Path(r"C:\Users\marti\.claude-account2\skills\synced\5c9a5e14-fad1-48b1-9a09-6d75966edaeb_b70593fb-1829-42bc-994f-26c5917e2dec\pptx")
src, out, wanted = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3:]
work = Path(tempfile.mkdtemp())
zipfile.ZipFile(src).extractall(work)
pres = (work / "ppt/presentation.xml").read_text(encoding="utf-8")
rels = (work / "ppt/_rels/presentation.xml.rels").read_text(encoding="utf-8")
target = {m.group(1): m.group(2) for m in re.finditer(r'Id="(rId\d+)"[^>]*Target="([^"]+)"', rels)}
target.update({m.group(2): m.group(1) for m in re.finditer(r'Target="([^"]+)"[^>]*Id="(rId\d+)"', rels)})
kept = 0
for sid in re.findall(r'<p:sldId [^>]*/>', pres):
    xml = (work / "ppt" / target[re.search(r'r:id="(rId\d+)"', sid).group(1)]).read_text(encoding="utf-8")
    title = re.search(r'<p:ph type="title"/>.*?</p:sp>', xml, re.S)
    text = "".join(re.findall(r"<a:t>([^<]*)</a:t>", title.group(0))) if title else ""
    if any(w in text for w in wanted):
        kept += 1
    else:
        pres = pres.replace(sid, "")
(work / "ppt/presentation.xml").write_text(pres, encoding="utf-8")
subprocess.run([sys.executable, str(SKILL / "scripts/clean.py"), str(work)], check=True, capture_output=True)
out.unlink(missing_ok=True)
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    z.write(work / "[Content_Types].xml", "[Content_Types].xml")
    for f in sorted(work.rglob("*")):
        if f.is_file() and f.name != "[Content_Types].xml":
            z.write(f, f.relative_to(work).as_posix())
shutil.rmtree(work)
print(f"kept {kept} slides in {out}")
