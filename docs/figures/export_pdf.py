"""Export the pages of a draw.io file as PDFs for a paper, each cropped to its drawing, vector and with
its fonts embedded, named after the page.

    python export_pdf.py <file.drawio> <out-dir> [--page NAME ...]

Renders with the draw.io viewer that the VS Code draw.io extension ships and headless Chrome, like
export_layers.py; no network.
"""
import argparse
import glob
import html
import json
import os
import re
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
VIEWER = sorted(glob.glob(os.path.expanduser(
    r"~\.vscode\extensions\hediet.vscode-drawio-*\drawio\src\main\webapp\js\viewer-static.min.js")))[-1]
# Once the viewer has drawn the page, the PDF page is made the size of the drawing.
FIT = """<script>
const fit = setInterval(() => {
  const svg = document.querySelector('.mxgraph svg');
  if (!svg) return;
  clearInterval(fit);
  const b = svg.getBoundingClientRect();
  const s = document.createElement('style');
  s.textContent = `@page { size: ${Math.ceil(b.width)}px ${Math.ceil(b.height)}px; margin: 0 }`;
  document.head.appendChild(s);
}, 50);
</script>"""


def export(model: ET.Element, pdf: Path):
    cfg = {"xml": ET.tostring(model, encoding="unicode"), "nav": False, "border": 2, "resize": False,
           "fit": False, "lightbox": False, "highlight": "none"}
    page = (f'<!doctype html><html><head><meta charset="utf-8"><style>html,body{{margin:0;padding:0;'
            f'background:#FFFFFF}}</style></head><body>'
            f'<div class="mxgraph" data-mxgraph="{html.escape(json.dumps(cfg))}"></div>'
            f'<script src="{Path(VIEWER).as_uri()}"></script>{FIT}</body></html>')
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "page.html"
        f.write_text(page, encoding="utf-8")
        started = time.time()
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--allow-file-access-from-files",
                        "--no-pdf-header-footer", "--virtual-time-budget=4000", f"--user-data-dir={tmp}\\profile",
                        f"--print-to-pdf={pdf}", f.as_uri()], check=True, capture_output=True)
        # Chrome's launcher may return before the PDF is written; the page and the profile in tmp must
        # outlive the render, so wait for a new PDF whose size has settled.
        size = -1
        for _ in range(600):
            if pdf.exists() and pdf.stat().st_mtime >= started - 1 and pdf.stat().st_size == size > 0:
                break
            size = pdf.stat().st_size if pdf.exists() and pdf.stat().st_mtime >= started - 1 else -1
            time.sleep(0.1)
        else:
            raise RuntimeError(f"Chrome wrote no {pdf.name}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("drawio"), ap.add_argument("out")
    ap.add_argument("--page", nargs="*", help="only these pages")
    a = ap.parse_args()
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    for diagram in ET.parse(a.drawio).getroot().findall("diagram"):
        name = diagram.get("name")
        if a.page and name not in a.page:
            continue
        pdf = out / (re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") + ".pdf")
        export(diagram.find("mxGraphModel"), pdf)
        print(pdf)


if __name__ == "__main__":
    main()
