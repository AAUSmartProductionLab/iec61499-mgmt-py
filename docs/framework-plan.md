# The framework: name, repositories, documentation and what is missing

Proposal of 31 Oct 2026. It replaces the target of [repositories.md](repositories.md) (6 Oct: six
repositories, split late), which stays as the analysis of the parts. Nothing here is done yet except
the icons (section 7); the decisions it needs are in section 9, each with a recommendation.

The scope is the whole demo of January 2027, not only the CIRP paper: orders come in, agents bid,
the planar table carries the product, a module that lacks a skill gets one planned and created
online, a module plugged in is found and registered ([agents.md](agents.md)).

## 1. What there is (31 Oct)

| Part | Where now | Owner on GitHub | Language | State |
| --- | --- | --- | --- | --- |
| `iec61499_mgmt`: FORTE management client, boot files, read-back | `iec61499-mgmt-py/` | lab (this repository) | Python | Built, stable |
| ModLib, the standard blocks' declarations, `modgen` | `iec61499-skill-lib/` | lab (this repository) | 4diac XML, Python | Built; rule set 2 |
| FORTE builds (PC, Pi), patches, the kit, `install.sh`, `update-pi.ps1` | `runtime/` | lab (this repository) | PowerShell, CMake, shell | Built; the Pi binary is committed (14 MB) |
| A Pi as a module: FORTE in Docker, `pi.py`, `steptest.py` | `deploy/pi`, `deploy/pi.py` | lab (this repository) | Python, Docker | Built |
| The lab stack: BaSyx (environment, registries, discovery), Mosquitto, Prosody, InfluxDB, DMP, web UI | `deploy/aas` | lab (this repository) | Compose | Built; the AAS environment is in memory |
| `modsync`, `modreg`, `modplan` | `aas61499-tools/` | lab (this repository) | Python | Built |
| `lineagents` | `line-agents/` | lab (this repository) | Python (SPADE) | Built on simulated modules and FORTE on the PC |
| The line: module specs, generated projects, simulators, example AASs, evaluation | `cell/` | lab (this repository) | YAML, 4diac, Python | Built |
| ARSO, APSO, AProSO, PPRL, the vocabularies | `ontology/`, and a copy in ARSO_Ontology_AAS_Generation | lab and user | Turtle, SHACL | Two copies, kept equal by hand |
| `modlink`, the HMI, a stand-in module, a Linux FORTE build | iec61499-opcua-hmi (submodule) | lab | Python | `modlink` built; the HMI's 0.8 reader uncommitted, 7 tests failing |
| Planner, Skill Editor, the BPMN editors, Configurator | basyx-aas-web-ui fork (submodule) | user | Vue, TypeScript | 9 commits not pushed; Configurator in progress |
| DMP | aas-camel-dmp fork (submodule) | user | Java | Built, branch `lab-modules` |
| aas-model | Tristan's; our fork, branch `lab-ppr-models` | Tristan, user | Python | Pull request not opened |
| planar-controller | submodule | lab | Python | Simulated driver only |
| AAS generator (LLM pipeline, editor, SHACL validation) | ARSO_Ontology_AAS_Generation | user | Python, web | ARSO 0.7 pushed, 0.8 uncommitted |
| Figures, the shape pack, the slides' sources | `docs/figures`, `docs/presentation` | lab (this repository) | draw.io, Python | Built |
| Working notes | `docs/`, 30 files, about 10 000 lines | lab (this repository) | Markdown | Notes, not documentation |

What stands out:

1. **No name.** This repository is named after one library (`iec61499-mgmt-py`), its Python project after
   the method (`iec61499-aas-reconfig`), and the framework has no name of its own.
2. **Three owners on GitHub**: the lab's organization, the user's account (four forks and the
   generator) and Tristan's account.
3. **The tools import each other in a circle.** `modreg` imports `modplan` and `modsync`, `modsync`
   imports `modreg`, `modplan` imports both. `modgen.spec` (the skill and flow model) and
   `modsync.aasjson` and `modsync.described` (reading an AAS's skills) are used by every tool.
4. **A binary in Git** (`runtime/bin/forte-aarch64`), which `install.sh` downloads from `main`.
5. **No CI, no releases, no published packages, no documentation site.**
6. **`modgen`, `modreg` and `modlink` are taken on PyPI** by other projects.

## 2. The name

**Recommendation: Skillshell.** It names what the work puts together: a module's skills, carried in
its Asset Administration Shell and run as IEC 61499. It was free on GitHub, PyPI and Read the Docs on
31 Oct. Alternatives: **aas61499** (descriptive, matches `aas61499-tools`, less of a brand), **Moduline**
(the modular line).

Names that follow from it:

| What | Name |
| --- | --- |
| The organization | `github.com/skillshell` |
| The documentation | `skillshell.readthedocs.io` |
| Container images | `ghcr.io/skillshell/<name>` |
| Python distributions | `skillshell-<tool>` (`skillshell-modsync`); the import and command names stay (`modsync`) |

Rules for the rest:

- **Tools** keep their names: `mod` and what the tool does to a module: `modgen`, `modsync`, `modreg`,
  `modplan`, `modlink`. The line's agents stay `lineagents`. These names are in the paper, the slides
  and the docs; changing them buys nothing.
- **Repositories**: lower case with hyphens, named after what they hold, without a `skillshell-`
  prefix inside the organization; the main repository is `skillshell`; a fork keeps its upstream name.
- **The web UI's apps**: Planner, Skill Editor, HMI, Orders (as the menu shows them).
- **Concepts**: one word for one thing, settled in a glossary on the documentation site. To settle:

| Concept | Proposed word | Instead of |
| --- | --- | --- |
| A unit with its own controller and AAS | module | station (a station is a place on the planar table) |
| A part of a module with its own AAS (axis, pump) | component | equipment |
| The whole | line (its AAS type: ProductionSystem) | cell, production system |
| A skill made of other skills | composite skill (ARSO's kind `Composite`) | module level skill |
| Occupy, Release, Reset, ... | module commands (kind `ModuleControl`) | module skills |
| The YAML a vendor generates a module from | module spec | spec, description |
| The pydantic dump of an AAS type | profile | description |
| The profiles a Pi serves on port 8088 | manifest | profile |
| A product's steps without bindings | recipe | Production Sequence, plan |
| The steps bound to a line's modules | process (its AAS: the process AAS) | plan, master recipe |

## 3. The code: what changes before it can be split

A repository split only works if the dependencies run one way. Three changes make them do so:

1. **Break the circle between the tools.** The profile written from a running program
   (`modreg.profile` calls `modsync`'s reading) moves to `modsync describe`, so `modreg` only takes
   profiles. `described_skill` and storing a described skill move out of `modreg.offer` and
   `modsync.desired` into the shared module of point 2. Then: `modplan` ← `modreg` ← `modsync` ←
   `lineagents`.
2. **One shared model.** `modgen.spec` (skills, flows, parameters), `modsync.aasjson`, `modsync.described`,
   `modplan.vocabulary` and `modplan.expression` are used by all tools. They stay where they are while
   the three tools share one repository (recommended, section 4); they become a package of their own
   (`core`) only if the tools are split further.
3. **`modlink` out of the HMI repository**, its copy of ModLib's state and error numbers generated from
   `iec61499-skill-lib` instead of written by hand. The HMI's Python service is retired once the HMI is
   an app of the web UI (C5 in [next-steps.md](next-steps.md)).

And four that the deployment needs:

4. **Binaries as releases**: FORTE per platform as GitHub release assets and as one multi-arch image
   (`ghcr.io/skillshell/forte`, amd64 and arm64); `install.sh` takes a version, not `main`.
5. **Every service an image**, built by CI: the registration service (`modreg serve`), the agent
   manager, the web UI, the DMP.
6. **No addresses in code**: the Pis' addresses, users and the lab server's address in one inventory
   file of the line, read by `deploy/pi.py`, the tests and the scenario runner.
7. **The agents' executors as plug-ins** (OPC UA, DMP, simulated), chosen per module in the
   configuration.

## 4. The repositories

**Recommendation: 17 repositories in one organization**, the three AAS tools kept together.

| Family | Repository | Holds | Comes from |
| --- | --- | --- | --- |
| Main | **skillshell** | Submodules of every repository below at versions tested together; the documentation site; `compose.yaml` that runs the whole line in simulation on one PC; the end-to-end tests; the releases | New |
| Main | **.github** | The organization's profile page (the map and the icons), issue templates, shared CI workflows | New |
| Definitions | **ontologies** | ARSO, APSO, AProSO, PPRL, the vocabularies, the SHACL shapes, the checks; a Python package with the Turtle files as data | `ontology/`; replaces the generator's copy |
| Definitions | **aas-model** (fork) | The lab's pydantic AAS model; our branch for pull requests | Tristan's repository |
| Module | **iec61499-skill-lib** | ModLib, the standard blocks' declarations, `modgen`, the module rules | `iec61499-skill-lib/` |
| Module | **forte-runtime** | FORTE built with ModLib for each platform, the patches, the kit for building with one's own blocks; releases binaries and the image | `runtime/`; the HMI's `tools/forte` |
| Module | **iec61499-mgmt-py** | The FORTE management protocol client | `iec61499-mgmt-py/` (the library only) |
| Engineering | **aas61499-tools** | `modsync`, `modreg` (with the registration service's image), `modplan` | `aas61499-tools/` |
| Engineering | **aas-generator** | The LLM pipeline from spec sheets to a profile, its editor | ARSO_Ontology_AAS_Generation, renamed |
| Operation | **modlink** | Running a module's skills from its AAS over OPC UA | The HMI repository's `modlink/` |
| Operation | **lineagents** | Order, product and resource agents; the agent manager's image | `line-agents/` |
| Operation | **basyx-aas-web-ui** (fork) | Planner, Skill Editor, the BPMN editors, Configurator, later HMI and Orders; its image | The user's fork |
| Operation | **aas-camel-dmp** (fork) | The DMP; its image | The user's fork |
| Operation | **planar-controller** | The planar table over OPC UA, with its simulated driver | The lab's repository |
| Deployment | **deploy-server** | Compose for the lab's server (and any PC): BaSyx with a persistent store, registries, discovery, Mosquitto, Prosody, InfluxDB, DMP, web UI, registration, agents; `.env.example`; `aas.py`. Images by version, no source | `deploy/aas`, `deploy/aas.py` |
| Deployment | **deploy-module** | A Raspberry Pi becomes a module: `install.sh`, its compose, the manifest server, `pi.py` (a program onto a Pi), the offline kit; pulls the FORTE image | `deploy/pi`, `deploy/pi.py`, `runtime/install.sh`, `runtime/kit` |
| The line | **pharma-line** | Our line built with Skillshell: module specs, generated 4diac projects, simulators, products and processes, the evaluation, the demo's scenario, the inventory, the working notes | What remains of this repository |

Retired afterwards: iec61499-opcua-hmi (archived once `modlink` is out and the HMI is in the web UI).
Outside the organization and only pinned: Eclipse 4diac FORTE, Eclipse BaSyx's images, the lab's
AP2030-UNS.

Why 17 when [repositories.md](repositories.md) said six: each of these has its own artefact (a package,
an image, a release, a site), its own audience (a vendor, an integrator, the lab's server) or its own
upstream. The cost is real (17 CI setups, version pins): one shared CI workflow in `.github`, Dependabot
for the pins, and only the main repository with submodules keep it bearable. The three tools stay one
repository because a change still touches two or three of them at once (G and F did); they split, with
the `core` package of section 3, only when someone needs one without the others.

How they depend on each other:

- **Only the main repository has submodules**, one level deep, in folders by family
  (`definitions/`, `module/`, `engineering/`, `operation/`, `deployment/`, `line/`).
- **Everything else depends by version**: Python packages by tag (later PyPI), the ontologies as a
  package, images by tag, FORTE by release.
- **One Python environment for development**: the main repository is a uv workspace with every Python
  submodule installed editable.
- **One command for the whole line in simulation**: the main repository's `compose.yaml` includes
  deploy-server's and adds the simulated modules (FORTE and the simulator per module) and the planar
  controller's simulation (`docker compose --profile sim up`).
- **Versions**: the libraries by SemVer; the main repository by date (`2026.11` with the paper, with a
  Zenodo DOI to cite; `2027.01` with the demo); ARSO keeps its own numbers.

The split itself, once decided: this repository is transferred to the organization and renamed
`pharma-line` (GitHub redirects the old address). Each part is copied out with its history by
`git filter-repo --path`, and then removed here. `iec61499-mgmt-py` is then the library's name again.
The installer's address in the README, the slides and the paper is checked afterwards.

## 5. Documentation on Read the Docs

**One site, built from the main repository** with its submodules: one navigation, one search, one
version per release (`latest`, `2026.11`, `2027.01`). Sphinx with MyST (the notes are Markdown already),
the Python reference generated from the code, Mermaid for small diagrams, the draw.io figures as SVG.
Each repository keeps a README (what it is, install, one example, a link to its part of the site) and a
`docs/` folder of its own pages, which the site gathers.

The site, in the four kinds of the Diátaxis scheme:

| Section | Pages |
| --- | --- |
| Overview | What Skillshell is; the architecture figure; the parts with their icons; glossary; how to cite |
| Tutorials | The line in simulation on one PC; a Raspberry Pi as a module; your first module (spec, program, AAS, registered); changing a skill online; placing an order |
| How-to guides | Deploy the server; deploy a module; register a vendor's module; write a skill in the Skill Editor; plan a skill; build FORTE with your own blocks; run the evaluation |
| Concepts | The module rules; the product, process and resource model; skills and capabilities; the AAS as the desired state; changing a module online; planning; agents and their messages; discovery |
| Reference | Each tool's commands; the Python API; ARSO and the vocabularies (tables generated from the Turtle); the submodel templates; the I4.0 messages; the HTTP endpoints of `modreg serve` and the order agent; settings and ports |

Most of it exists as notes: [module-rules.md](module-rules.md), [ppr-model.md](ppr-model.md),
[aas-models.md](aas-models.md), [pipeline.md](pipeline.md), [tools.md](tools.md), [tooling.md](tooling.md),
[skill-planning.md](skill-planning.md), [agents.md](agents.md), [forte-for-the-pi.md](forte-for-the-pi.md),
[design-decisions.md](design-decisions.md). They are rewritten for a reader who was not there; the
working notes ([work.md](work.md), [design-log.md](design-log.md), [next-steps.md](next-steps.md), the
papers' drafts) stay in pharma-line's `notes/` and are not on the site.

## 6. What is missing, for the whole demo

### 6.1 The paper (to 18 Nov)

| Step | Needs |
| --- | --- |
| B3: the runtime and program on both Pi 5s; the switch mounted; a move measured; the scenarios on the Pi with the axis moving | The user at the bench |
| A model of the liquid level, so that BottomUpFilling is planned and not only written | A decision on how it is modelled |
| Writing from 2 Nov, the figures redrawn as needed | – |
| The code citable at the paper's version: the fork's 9 commits pushed, aas-model's pull request opened, a release with a DOI | The user's go; section 9 |

### 6.2 The demo (to January)

| Area | Missing |
| --- | --- |
| Filling module | Dispensing on the real axis; the scale is simulated (a real one, e.g. an HX711, later) |
| Stoppering module | The old container removed and the new runtime installed (the user's go); its wiring written down; the axis wired and moving |
| Capping and inspection | Specs in `cell/modules/planned` only: in the demo or not? |
| Loading and unloading | The two Kuka robots (a Pi each): no program, no AAS, no agent. Loading is also the step that starts a product's custody |
| Planar table | The controller against the real table (only the simulated driver has run); the shuttles' AASs published from it; MoveToPosition from the agents, on the simulation and then on the table; the holders that carry a vial |
| Agents ([agents.md](agents.md), section 7) | A1: loading and unloading as steps, MoveToPosition on the planar controller. A2 on the filling Pi. A3: a planned skill in a bid. A4: the agents as a service of the stack; a Pi plugged in has its agent within seconds. A5: the series' names from Variables. A6: a module that goes away, timeouts, restarts. A7: the order screen, the messages logged, the scenario script. A8: the rehearsal |
| Models | Proposals with a time (booking ahead); the product instance's AAS as the batch record; the bindings out of the recipe into the process AAS (F6); the eleven decisions of [state-and-parameters.md](state-and-parameters.md); taring |
| Web UI | The fork pushed and rebased on upstream BaSyx; Configurator finished; one of the classic and BPMN editors chosen for the demo; the HMI as an app (C5) or the Python HMI fixed (its 7 tests); the Orders app (A7) |
| Server | Which machine runs the stack in the lab; publishing to the lab's AAS server (permission) or a server of our own; the AAS environment persistent (MongoDB) instead of in memory; the Pis by name instead of by address; the manifest server on every Pi |
| Framework | Sections 2 to 5: name, organization, the split, CI, images, releases, the site; the icons exported (section 7); licences checked (the generator's) and a `CITATION.cff` |

### 6.3 Order of work

| When | Work |
| --- | --- |
| Now to 18 Nov | The paper first. From this plan only what helps it: the name and organization decided, the organization created, the repositories we own transferred into it (GitHub redirects), a release `2026.11` with a DOI |
| 19 to 30 Nov | The code changes of section 3; the split (section 4); the main repository with its submodules and workspace; CI with the shared workflow; images to GHCR; FORTE as releases; deploy-server and deploy-module |
| December | The site's first version (overview, the simulation tutorial, deploying, the commands); agents A3 to A6; the stoppering module; loading and unloading; the Orders app |
| January | The rehearsal on the hardware; release `2027.01` |

## 7. Icons and figures

[figures/framework-icons.drawio](figures/framework-icons.drawio) has an icon for each repository and
app (page *Icons*) and the organization's map (page *Organization*). The icons are also a draw.io
library, [figures/library/tools.xml](figures/library/tools.xml), in the shape panel in VS Code.
`docs/presentation/source/build_icons.py` draws both.

The colours are those of the figures, by what a part works on:

| Colour | Family | Icons |
| --- | --- | --- |
| Teal `#2A918B` (every AAS) | The AAS and its definitions | Skillshell, ontologies, aas-model, aas-generator, modreg |
| Green `#5B963B` (IEC 61499) | The module's control | iec61499-skill-lib, modgen, forte-runtime, modsync |
| Gold `#B88A1C` (the management protocol) | Talking to FORTE | iec61499-mgmt-py |
| Blue `#6C91B2` (resources, OPC UA) | Operating the line | modlink, basyx-aas-web-ui, Planner, Skill Editor, HMI, Orders, aas-camel-dmp, planar-controller |
| Orange `#F07D2E` | Deciding | modplan, lineagents |
| Purple `#9080B7` (the product) | The line that makes products | pharma-line |
| Slate `#4A5560` | Running it | deploy-server, deploy-module, docs |

Still to do with them: SVG and PNG per icon for the READMEs, the organization's avatar (the logo at
500 px), the site's favicon, a social preview image (1280 × 640).

## 8. Effort

| Work | Days |
| --- | --- |
| Code changes of section 3 | 2 |
| The split with history, the main repository, the workspace | 2 |
| CI, images, releases | 2 |
| deploy-server and deploy-module, tried on a fresh Pi and a fresh PC | 2 |
| The site's first version | 3 |

## 9. Decisions for the user

| # | Question | Recommendation |
| --- | --- | --- |
| 1 | The name | Skillshell (or aas61499, Moduline) |
| 2 | Where: an organization of its own, or the lab's (AAUSmartProductionLab, 19 other repositories)? | Its own, with the lab's people as owners and the lab named on its page and in the licences (MIT, Aalborg University) |
| 3 | The lab's repositories (iec61499-opcua-hmi, planar-controller): transferred into the organization, or forked? | Transferred, if their owners agree; planar-controller is used by other lab work, so forking is the fallback |
| 4 | How fine: 17 repositories with the three tools together, or each tool on its own (20, with `core`)? | 17 |
| 5 | This repository becomes pharma-line, the parts copied out with their history? Or new repositories without history? | With history |
| 6 | When: the split after 18 Nov, only the organization and the transfers before? | Yes |
| 7 | The documentation: Sphinx with MyST, or MkDocs? | Sphinx with MyST: Read the Docs' own path, the Python reference generated, Markdown kept |
| 8 | The line's name: pharma-line, filling-line, aseptic-line? | pharma-line |
| 9 | Capping, inspection and the loading and unloading robots in the January demo, or simulated? | Decide before December: the robots need a program, an AAS and an agent each |
