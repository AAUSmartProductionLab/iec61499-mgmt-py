"""Export a draw.io page as one PNG per layer, every PNG the size of the whole page, so that the layers
stacked on a slide line up and each can be animated on its own (PowerPoint, Keynote, ...).

    python export_layers.py <file.drawio> <out-dir> [--page N] [--scale 1.5]

Writes <out-dir>/00-still.png (the layers visible in the file, on white) and <out-dir>/<nn>-<layer>.png
(one layer alone, transparent). Renders with the draw.io viewer that the VS Code draw.io extension
ships and headless Chrome; no network.
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


def render(model: ET.Element, width: int, height: int, scale: float, png: Path, background: str | None):
    root = model.find("root")
    model = ET.fromstring(ET.tostring(model))          # a copy
    root = model.find("root")
    # A frame the size of the page in the first visible layer, so every export has the page's bounds.
    first = next(c for c in root if c.get("parent") == "0" and c.get("visible") != "0")
    frame = ET.SubElement(root, "mxCell", id="__frame", value="", vertex="1", parent=first.get("id"),
                          style="rounded=0;fillColor=none;strokeColor=none;")
    ET.SubElement(frame, "mxGeometry", x="0", y="0", width=str(width), height=str(height), **{"as": "geometry"})
    if background:
        model.set("background", background)
    elif "background" in model.attrib:
        del model.attrib["background"]
    xml = ET.tostring(model, encoding="unicode")
    cfg = {"xml": xml, "toolbar": "", "nav": False, "border": 0, "resize": False, "fit": False,
           "lightbox": False, "highlight": "none"}
    page = (f'<!doctype html><html><head><meta charset="utf-8"><style>html,body{{margin:0;padding:0;'
            f'background:{background or "transparent"};overflow:hidden}}</style></head><body>'
            f'<div class="mxgraph" data-mxgraph="{html.escape(json.dumps(cfg))}"></div>'
            f'<script src="{Path(VIEWER).as_uri()}"></script></body></html>')
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "page.html"
        f.write_text(page, encoding="utf-8")
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        "--allow-file-access-from-files", f"--force-device-scale-factor={scale}",
                        f"--window-size={width},{height}", "--default-background-color=00000000",
                        "--virtual-time-budget=4000", f"--user-data-dir={tmp}\\profile",
                        f"--screenshot={png}", f.as_uri()], check=True, capture_output=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("drawio"), ap.add_argument("out")
    ap.add_argument("--page", type=int, default=0), ap.add_argument("--scale", type=float, default=1.5)
    a = ap.parse_args()
    diagram = ET.parse(a.drawio).getroot().findall("diagram")[a.page]
    model = diagram.find("mxGraphModel")
    width, height = int(model.get("pageWidth")), int(model.get("pageHeight"))
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    render(model, width, height, a.scale, out / "00-still.png", model.get("background") or "#FFFFFF")
    layers = [c for c in model.find("root") if c.get("parent") == "0"]
    for i, layer in enumerate(layers, 1):
        alone = ET.fromstring(ET.tostring(model))
        for c in alone.find("root"):
            if c.get("parent") == "0":
                c.set("visible", "1" if c.get("id") == layer.get("id") else "0")
        name = re.sub(r"[^a-z0-9]+", "-", layer.get("value", layer.get("id")).lower()).strip("-")
        render(alone, width, height, a.scale, out / f"{i:02d}-{name}.png", None)
        print(f"{i:02d}-{name}.png")


if __name__ == "__main__":
    main()
