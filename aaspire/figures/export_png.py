"""Export the pages of a draw.io file as PNGs, each cropped to its drawing, named after the page.

    python export_png.py <file.drawio> <out-dir> [--page NAME ...] [--scale 2]

Renders with the draw.io viewer that the VS Code draw.io extension ships and headless Chrome, like
docs/figures/export_pdf.py: no draw.io desktop and no network. Each page is drawn twice: once to
measure the drawing, once to take the picture at that size.
"""
import argparse
import glob
import html
import json
import os
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
VIEWER = sorted(glob.glob(os.path.expanduser(
    r"~\.vscode\extensions\hediet.vscode-drawio-*\drawio\src\main\webapp\js\viewer-static.min.js")))[-1]
# Once the viewer has drawn the page, its size goes where --dump-dom shows it.
MEASURE = """<script>
const measure = setInterval(() => {
  const svg = document.querySelector('.mxgraph svg');
  if (!svg) return;
  clearInterval(measure);
  const b = svg.getBoundingClientRect();
  document.body.setAttribute('data-size', Math.ceil(b.width) + 'x' + Math.ceil(b.height));
}, 50);
</script>"""


def page_html(model: ET.Element, border: int, script: str = "") -> str:
    # No "toolbar" key at all: an empty one still reserves a strip above the diagram and shifts it down.
    cfg = {"xml": ET.tostring(model, encoding="unicode"), "nav": False, "border": border, "resize": False,
           "fit": False, "lightbox": False, "highlight": "none"}
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>html,body{{margin:0;padding:0;'
            f'background:#FFFFFF;overflow:hidden}}</style></head><body>'
            f'<div class="mxgraph" data-mxgraph="{html.escape(json.dumps(cfg))}"></div>'
            f'<script src="{Path(VIEWER).as_uri()}"></script>{script}</body></html>')


def chrome(tmp: str, page: str, *args: str) -> subprocess.CompletedProcess:
    f = Path(tmp) / "page.html"
    f.write_text(page, encoding="utf-8")
    return subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                           "--allow-file-access-from-files", "--virtual-time-budget=4000",
                           f"--user-data-dir={tmp}\\profile", *args, f.as_uri()],
                          check=True, capture_output=True, text=True, encoding="utf-8")


def export(model: ET.Element, png: Path, scale: float, border: int = 8):
    with tempfile.TemporaryDirectory() as tmp:
        dom = chrome(tmp, page_html(model, border, MEASURE), "--dump-dom").stdout
        size = re.search(r'data-size="(\d+)x(\d+)"', dom)
        if not size:
            raise RuntimeError(f"the viewer drew nothing for {png.name}")
        width, height = int(size.group(1)), int(size.group(2))
        chrome(tmp, page_html(model, border), f"--window-size={width},{height}",
               f"--force-device-scale-factor={scale}", f"--screenshot={png}")
    return width, height


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("drawio"), ap.add_argument("out")
    ap.add_argument("--page", nargs="*", help="only these pages")
    ap.add_argument("--scale", type=float, default=2.0, help="pixels per drawing unit (2: sharp on any screen)")
    a = ap.parse_args()
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    for diagram in ET.parse(a.drawio).getroot().findall("diagram"):
        name = diagram.get("name")
        if a.page and name not in a.page:
            continue
        png = out / (re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") + ".png")
        width, height = export(diagram.find("mxGraphModel"), png, a.scale)
        print(f"{png.name}: {width} x {height}")


if __name__ == "__main__":
    main()
