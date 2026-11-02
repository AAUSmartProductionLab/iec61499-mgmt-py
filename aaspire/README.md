# aaspire

The future main repository of AASPIRE (AAS-based Planning, Integration, Reconfiguration and
Execution), the framework of the AP2030 project ([docs/framework-plan.md](../docs/framework-plan.md)).
For now it holds the framework's documentation site, in MkDocs with the Material theme: a section per
pillar, a page with a figure for every part of the framework, and how-to pages.

```powershell
python -m pip install -e ".[docs]"
cd aaspire
python -m mkdocs serve           # http://127.0.0.1:8000
python -m mkdocs build --strict  # into site/ (not committed)
```

| Path | Holds |
| --- | --- |
| `mkdocs.yml` | The site's settings and navigation |
| `docs/` | The pages; `docs/figures/` the figures as PNG; `docs/assets/` the logo |
| `figures/aaspire.drawio` | The figures' source: one draw.io page per figure |
| `figures/export_png.py` | Every page of a draw.io file as a PNG cropped to its drawing |
| `figures/build_figures.py`, `figures/figlib.py` | The first version of every figure, drawn with a kit in the style of `docs/figures` |

How the pages and the figures are made: [docs/how-to/this-site.md](docs/how-to/this-site.md).
