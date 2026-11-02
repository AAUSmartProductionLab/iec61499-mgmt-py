# Work on this site

The site is MkDocs with the Material theme, in the repository's `aaspire/` folder: the future main
repository `aaspire`, for now its documentation. It is written for a reader who was not there, from
the working notes in `docs/`.

## Build and serve

```powershell
python -m pip install -e ".[docs]"       # MkDocs and the Material theme
cd aaspire
python -m mkdocs serve                   # http://127.0.0.1:8000, rebuilt on every save
python -m mkdocs build --strict          # into aaspire/site/ (not committed); fails on a broken link
```

## The pages

- `mkdocs.yml` holds the navigation: a section per pillar, a page per part, then the how-to pages.
- A part's page: what it is and its folder; the figure; how it works, its steps numbered as in the
  figure; how to use it (commands that run as written); what it does not do; where to read further.
- Links to the working notes go to GitHub (`https://github.com/AAUSmartProductionLab/iec61499-mgmt-py/blob/main/docs/...`):
  they are not part of the site.
- The words are those of the [glossary](../overview/glossary.md).

## The figures

The figures are draw.io pages in `aaspire/figures/aaspire.drawio`, one page per figure, shown on the
site as PNGs from `aaspire/docs/figures/`. They follow the style of the figures in `docs/figures`:
Arial, grey lanes, white cards, coloured pills and tags, black step numbers, the framework's icons.

| Colour | Means |
| --- | --- |
| black arrow | flow |
| gold arrow | IEC 61499 management protocol |
| blue arrow | operate over OPC UA |
| green arrow | a step runs a primitive |
| teal arrow | reads or writes an AAS |
| orange arrow | a message between agents (XMPP) |
| grey dashed | a reference, part of |
| salmon, dashed | new, planned, or described but not built |

To change a figure, edit its page in draw.io (the VS Code extension, or app.diagrams.net) and export
the PNGs again:

```powershell
cd aaspire/figures
python export_png.py aaspire.drawio ../docs/figures             # every page; --page modsync for one
```

`build_figures.py` drew the first version of every page with the kit in `figlib.py`; it adds a page the
file does not have yet and leaves the others as they are (`--force <page>` draws one again, which
discards what was edited in draw.io). The PNG export uses the draw.io viewer of the VS Code extension
and headless Chrome, like `docs/figures/export_pdf.py`. The logo is the page `logo`, exported to
`docs/assets/logo.png`.

## Later

The plan is one site, `aaspire.readthedocs.io`, built from `aaspire` with its submodules: each
repository keeps a README and a `docs/` folder of its own pages, which the site gathers, and the Python
reference generated from the code.
