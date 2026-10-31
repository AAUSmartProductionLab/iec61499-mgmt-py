# AASPIRE: the framework, its repositories, documentation and what is missing

Proposal of 31 Oct 2026, revised the same day with the user's decisions: the framework is called
**AASPIRE**, and one GitHub organization holds the **AP2030** project, with the framework as its
main repository. It replaces the target of [repositories.md](repositories.md) (6 Oct), which stays
as the analysis of our own parts. Nothing here is done yet except the icons (section 8). The
decisions still open are in section 10, each with a recommendation.

The framework has to hold more than our work: the lab's other AAS work has to fit in too, namely
planning with PDDL (FOND-AAS), behaviour trees (the BT controller) and the DMP. The scope is the
demo of January 2027 ([agents.md](agents.md)) and the AP2030 line after it.

## 1. The name

**AASPIRE: AAS-based Planning, Integration, Reconfiguration and Execution.** Plug and produce with
the Asset Administration Shell. Each letter after the AAS is a pillar, and each pillar holds work
already done in the lab:

| Pillar | What it does | Parts |
| --- | --- | --- |
| **AAS** | Describe: what a resource, a product and a process are | aas-model, the ontologies, the skill model, the AAS generator |
| **Planning** | Decide what to do from capabilities | FOND-AAS (PDDL, FOND planners), `modplan` (HTN), the Planner |
| **Integration** | Plug in: register, discover, connect, map data | The registration service, the DMP, the UNS's message schemas, `modlink` |
| **Reconfiguration** | Change a running resource from its AAS | `modsync`, the IEC 61499 library and runtime, the Skill Editor |
| **Execution** | Produce: run processes and skills | The BT controller, the agents, the PackML stations, the IEC 61499 modules, the planar table, the HMI, Orders |

Checked on 31 Oct: free on PyPI and Read the Docs; no AAS work of that name was found. Spoken aloud it
sounds like A.SPIRE, the EU process-industry association behind Processes4Planet; written, the two
differ.

Names that follow from it:

| What | Name |
| --- | --- |
| The organization | AP2030. `github.com/ap2030` is a personal account: if it is a lab member's, it can be turned into an organization; otherwise `ap2030-project` |
| The main repository | `aaspire` |
| The documentation | `aaspire.readthedocs.io` |
| Python distributions | `aaspire-<tool>` (`aaspire-modsync`); import and command names stay (`modsync`) |
| Container images | `ghcr.io/<organization>/<repository>` |

Rules for the rest:

- **Tools keep their names** (`modgen`, `modsync`, `modreg`, `modplan`, `modlink`, `lineagents`, the
  colleagues' own). They are in the papers and the slides.
- **Repositories**: lower case with hyphens, named after what they hold, no prefix; a fork keeps its
  upstream name; a line has a repository of its own (`aseptic-line`).
- **The web UI's apps**: Planner, Skill Editor, Configurator, HMI, Orders.
- **Concepts**: one word for one thing, in a glossary on the site, settled with the colleagues:

| Concept | Proposed word | Also used now |
| --- | --- | --- |
| Anything with an AAS that offers skills | resource (aas-model's `Resource`) | asset, station, module |
| A resource with its own controller, IEC 61499 over OPC UA | module | station |
| A resource that follows PackML over MQTT | PackML station | station |
| A place in the line where a product is handed over | transfer point | station |
| A part of a resource with its own AAS (axis, pump) | component | equipment |
| A skill made of other skills | composite skill (ARSO's kind `Composite`) | module level skill |
| Occupy, Release, Reset, ... | resource commands (kind `ModuleControl`) | module skills |
| The YAML a vendor generates a module from | module spec | spec, description |
| The pydantic dump of an AAS type | profile | description, minimal JSON configuration |
| A product's steps without bindings | recipe | Production Sequence, plan |
| The steps bound to a line's resources | process (its AAS: the process AAS) | plan, production task |

## 2. What there is (31 Oct)

| Part | Where now | Language |
| --- | --- | --- |
| `iec61499_mgmt`, ModLib and `modgen`, the FORTE builds, the Pi's deployment, `modsync`, `modreg`, `modplan`, `lineagents`, our line (`cell/`), the ontologies, the figures, the working notes | This repository (lab organization) | Python, 4diac XML, PowerShell |
| `modlink`, the Python HMI, a stand-in module | iec61499-opcua-hmi (lab organization) | Python |
| The planar table's controller | planar-controller (lab organization) | Python |
| The project's stack: HiveMQ, MQTT Explorer, TimescaleDB, Grafana, Portainer, the Configurator, Groot2, the BT controller, BaSyx; the line's AASs (`AASDescriptions`) and trees (`BTDescriptions`), the MQTT schemas on GitHub Pages, the PackML stations, a planar controller and simulator, a registration service, operation delegation, the DataBridge, the Aseptic Production Ontology, the AAS generator as `ppr-ontology` | AP2030-UNS (lab organization) | C++, Python, Compose |
| aas-model, a registration service (AAS from minimal JSON), the DMP's upstream, a web UI fork, the IDTA templates' fork, the MQTT message schemas, AASBT.CPP (BehaviorTree.CPP with the AAS), FOND-AAS's data, forks of unified-planning and of 4diac FORTE, IDE and FBE | Tristan's account | Python, Java, C++ |
| Planner, Skill Editor, the BPMN editors, Configurator (in progress) | The user's web UI fork; 9 commits not pushed | Vue, TypeScript |
| The DMP with the lab's modules | The user's fork of the DMP, branch `lab-modules` | Java |
| The AAS generator | ARSO_Ontology_AAS_Generation (the user's account) | Python, web |

What stands out:

1. **Two stacks for one line.** AP2030-UNS runs PackML stations over MQTT, orchestrated by behaviour
   trees, with HiveMQ and TimescaleDB. Ours runs IEC 61499 modules over OPC UA, operated by agents,
   with Mosquitto, Prosody and InfluxDB. Both describe the line in AASs on BaSyx.
2. **Several parts exist twice or three times** (section 3).
3. **Three owners on GitHub**: the lab's organization, the user's account and Tristan's account.
4. **Our tools import each other in a circle**: `modreg` imports `modplan` and `modsync`, `modsync`
   imports `modreg`, `modplan` imports both. `modgen.spec` (the skill and flow model) and
   `modsync.aasjson` and `modsync.described` are used by every tool.
5. **A binary in Git** (`runtime/bin/forte-aarch64`, 14 MB), downloaded by `install.sh` from `main`.
6. **No CI, no releases, no published packages, no documentation site** for our parts.

## 3. What exists twice: to resolve with the colleagues

| Part | Copies | Proposal |
| --- | --- | --- |
| Registration service | AP2030-UNS's `Registration_Service`, Tristan's `aas_registration_service`, `modreg serve` | One `registration-service`: building an AAS from a profile, the ontology check, discovery, publishing. Which code is the base is decided with Tristan |
| Web UI | Tristan's fork, the user's fork | One fork in the organization, every app on one branch that follows BaSyx's `main` |
| DMP | Tristan's (upstream), the user's fork | Tristan's moves into the organization; branch `lab-modules` merged into it |
| Planar table | AP2030-UNS's `Planar_Controller` and `PlanarMotorSimulator`, planar-controller | One `planar-controller` with its simulator |
| Ontologies | `ontology/` here, the generator's copy (`ppr-ontology`), the Aseptic Production Ontology | One `ontologies` repository; the generator takes it as a package |
| MQTT schemas | AP2030-UNS's `MQTTSchemas`, Tristan's `mqtt_message_schemas` | One `uns-schemas`, still published on GitHub Pages (aas-model loads them from there) |
| MQTT broker | HiveMQ (the UNS), Mosquitto (BaSyx's events, the DMP, the agents) | One broker for both |
| Time series | TimescaleDB with Grafana, InfluxDB (the DMP, the agents) | One database; the DMP and the agents' DMP executor change with it |
| 4diac FORTE | Tristan's fork, our patches applied by `runtime/` | One fork of FORTE with our patches as commits; `forte-runtime` builds from it |
| A station's logic | PackML stations over MQTT, IEC 61499 modules over OPC UA, for the same stations | Both stay: two kinds of resource, described the same way in their AAS. The documentation says when to use which |
| Orchestration | The BT controller (a planned process run as a tree), the agents (bidding per order) | Both stay, on the same AAS. Which one runs the demo, or both side by side, is decided with the colleagues |

## 4. The code: what changes before the split

The three tools now go to three pillars, so they are split, and their circle is broken first:

1. **`skill-model`**: `modgen.spec` (skills, flows, parameters), `modsync.aasjson`, `modsync.described`,
   `modplan.vocabulary` and `modplan.expression` become a package of their own, used by every tool.
2. **The circle broken.** The profile written from a running program (`modreg.profile` calls `modsync`'s
   reading) moves to `modsync describe`; `described_skill` and storing a described skill move to
   `skill-model`. Then: `skill-model` ← `modplan` ← `modreg` ← `modsync` ← `lineagents`.
3. **`modlink` out of the HMI repository**, its copy of ModLib's state and error numbers generated from
   `iec61499-skill-lib`. The HMI's Python service is retired once the HMI is an app of the web UI (C5 in
   [next-steps.md](next-steps.md)).

And four that the deployment needs:

4. **Binaries as releases**: FORTE per platform as release assets and one multi-arch image (amd64,
   arm64); `install.sh` takes a version, not `main`.
5. **Every service an image**, built by CI: registration, the agent manager, the BT controller, the
   web UI, the DMP, the PackML stations' simulators.
6. **No addresses in code**: the resources' addresses and the server's in one inventory file of the line,
   read by the deployment, the tests and the scenario runner.
7. **The agents' executors as plug-ins** (OPC UA, DMP, simulated), chosen per resource in the
   configuration; a PackML executor (MQTT) next to them lets the agents run PackML stations too.

## 5. The repositories

**24 repositories in the AP2030 organization**, by pillar:

| Pillar | Repository | Holds | Comes from |
| --- | --- | --- | --- |
| Main | **aaspire** | Every repository below as a submodule; the documentation site; `compose.yaml` that runs the whole line in simulation on one PC; the end-to-end tests; the releases | New |
| Main | **.github** | The organization's profile page (the map and the icons), issue templates, shared CI workflows | New |
| AAS | **aas-model** | The lab's pydantic AAS model and its template-to-class generator | Tristan's |
| AAS | **ontologies** | ARSO, APSO, AProSO, PPRL, the vocabularies, the Aseptic Production Ontology, the SHACL shapes, the checks; a Python package with the Turtle files as data | `ontology/`, AP2030-UNS's `Ontology`, the generator's copy |
| AAS | **skill-model** | Skills, flows and parameters as every tool reads them; reading an AAS's skills | `modgen.spec`, `modsync`, `modplan` (section 4) |
| AAS | **aas-generator** | From spec sheets to a profile (LLM pipeline, editor, SHACL validation) | ARSO_Ontology_AAS_Generation |
| Planning | **fond-aas** | Production policies planned from the AAS with FOND planners (PDDL) | Tristan's FOND-AAS |
| Planning | **modplan** | New skills planned from a Capability Description (HTN; PDDL and HDDL exported) | `aas61499-tools/modplan` |
| Integration | **registration-service** | Building, checking, discovering and publishing AASs (`modreg`) | Section 3 |
| Integration | **aas-camel-dmp** | The DMP: AAS operations and values to OPC UA, MQTT, HTTP and time series | Tristan's |
| Integration | **uns-schemas** | The MQTT messages of the unified namespace, on GitHub Pages | Section 3 |
| Integration | **modlink** | Running a resource's skills from its AAS over OPC UA | iec61499-opcua-hmi |
| Reconfiguration | **modsync** | A running IEC 61499 program against its AAS: verify, change online, record, the IDE project | `aas61499-tools/modsync` |
| Reconfiguration | **iec61499-skill-lib** | ModLib, the standard blocks' declarations, `modgen`, the module rules | `iec61499-skill-lib/` |
| Reconfiguration | **iec61499-mgmt-py** | The FORTE management protocol client | `iec61499-mgmt-py/` |
| Reconfiguration | **forte-runtime** | FORTE with ModLib per platform, the kit for one's own blocks; releases and the image | `runtime/`, the FORTE forks |
| Execution | **bt-controller** | Processes run as behaviour trees from the AAS | AP2030-UNS's `BT_Controller` |
| Execution | **lineagents** | Order, product and resource agents | `line-agents/` |
| Execution | **packml-stations** | PackML stations over MQTT and their simulators | AP2030-UNS's `PackML_Stations` |
| Execution | **planar-controller** | The planar table with its simulator | Section 3 |
| Interfaces | **basyx-aas-web-ui** (fork) | Planner, Skill Editor, the BPMN editors, Configurator, HMI, Orders | Section 3 |
| Deployment | **deploy-server** | The server stack by Compose: BaSyx, broker, XMPP, time series, Grafana, the DMP, registration, the web UI, the BT controller and Groot2, the agents; `.env.example`. Images by version, no source | AP2030-UNS's compose files, `deploy/aas` |
| Deployment | **deploy-module** | A Raspberry Pi becomes an IEC 61499 module: `install.sh`, its compose, the manifest server, `pi.py`, the offline kit | `deploy/pi`, `runtime/install.sh`, `runtime/kit` |
| Lines | **aseptic-line** | AP2030's line: its AASs and behaviour trees, the module specs and generated projects, simulators, products and processes, the evaluation, the demo's scenario, the inventory, the working notes | `cell/` and `docs/` here; AP2030-UNS's `AASDescriptions`, `BTDescriptions`, `config` |

Pinned, not ours: Eclipse 4diac FORTE, BaSyx's images, BehaviorTree.CPP and AASBT.CPP, Groot2,
unified-planning, the IDTA templates. Archived afterwards, with a pointer to `aaspire`: AP2030-UNS,
iec61499-opcua-hmi, ARSO_Ontology_AAS_Generation.

How they come together:

- **Only `aaspire` has submodules**, one level deep, in folders by pillar (`aas/`, `planning/`,
  `integration/`, `reconfiguration/`, `execution/`, `interfaces/`, `deployment/`, `lines/`).
- **Everything else depends by version**: Python packages by tag (later PyPI), the ontologies as a
  package, images by tag, FORTE by release.
- **One Python environment for development**: `aaspire` is a uv workspace with every Python part
  installed editable; the C++, Java and TypeScript parts build as images.
- **One command for the line in simulation**: `aaspire`'s `compose.yaml` includes deploy-server's and
  adds the simulated resources (the IEC 61499 modules, the PackML stations, the planar table)
  (`docker compose --profile sim up`).
- **Versions**: the parts by SemVer; `aaspire` by date (`2026.11` with the CIRP paper, with a Zenodo DOI
  to cite; `2027.01` with the demo); ARSO keeps its own numbers.

The split itself: this repository is transferred to the organization and renamed `aseptic-line`
(GitHub redirects the old address). Each part is copied out with its history by `git filter-repo
--path` and then removed here; `iec61499-mgmt-py` becomes the library's name again. AP2030-UNS is split
the same way, with its owners. The installer's address in the README, the slides and the paper is
checked afterwards.

## 6. Documentation on Read the Docs

**One site, `aaspire.readthedocs.io`, built from `aaspire`** with its submodules: one navigation, one
search, one version per release. Sphinx with MyST (Markdown), the Python reference generated from the
code, Mermaid for small diagrams, the draw.io figures as SVG. Each repository keeps a README (what it is,
install, one example, a link to its part of the site) and a `docs/` folder of its own pages, which the
site gathers; each pillar's pages are written by the people who build it.

| Section | Pages |
| --- | --- |
| Overview | What AASPIRE is; the five pillars and the architecture figure; the parts with their icons; glossary; how to cite |
| Tutorials | The AP2030 line in simulation on one PC; plugging in a resource; running a planned process as a behaviour tree; ordering a product from the agents; changing a skill online |
| How-to guides | Deploy the server; deploy a module on a Pi; register a vendor's resource; write a skill in the Skill Editor; plan with FOND-AAS or `modplan`; map an interface with the DMP; build FORTE with your own blocks |
| Concepts | One page per pillar: the AAS and the ontologies; planning; integration; reconfiguration; execution (behaviour trees, agents and when to use which) |
| Reference | Each tool's commands; the Python API; ARSO and the vocabularies (tables from the Turtle); the submodel templates; the UNS messages; the I4.0 messages; the services' HTTP endpoints; settings and ports |

Much of ours exists as notes: [module-rules.md](module-rules.md), [ppr-model.md](ppr-model.md),
[aas-models.md](aas-models.md), [pipeline.md](pipeline.md), [tools.md](tools.md), [tooling.md](tooling.md),
[skill-planning.md](skill-planning.md), [agents.md](agents.md), [forte-for-the-pi.md](forte-for-the-pi.md),
[design-decisions.md](design-decisions.md). They are rewritten for a reader who was not there. The
working notes ([work.md](work.md), [design-log.md](design-log.md), [next-steps.md](next-steps.md), the
papers' drafts) stay in `aseptic-line`'s `notes/` and are not on the site.

## 7. What is missing, for the whole demo

### 7.1 The CIRP paper (to 18 Nov)

| Step | Needs |
| --- | --- |
| B3: the runtime and program on both Pi 5s; the switch mounted; a move measured; the scenarios on the Pi with the axis moving | The user at the bench |
| A model of the liquid level, so that BottomUpFilling is planned and not only written | A decision on how it is modelled |
| Writing from 2 Nov, the figures redrawn as needed | – |
| The code citable: the fork's 9 commits pushed, aas-model's pull request opened; the organization and a first `aaspire` that pins today's repositories as submodules, tagged `2026.11` with a DOI | The user's go; the organization's handle |

### 7.2 The demo (to January)

| Area | Missing |
| --- | --- |
| Filling module | Dispensing on the real axis; the scale is simulated (a real one, e.g. an HX711, later) |
| Stoppering module | The old container removed and the new runtime installed (the user's go); its wiring written down; the axis wired and moving |
| Capping and inspection | Specs in `cell/modules/planned` only; PackML stations of AP2030 may already cover them: in the demo, and as which kind of resource? |
| Loading and unloading | The two Kuka robots (a Pi each): no AAS or agent of ours; AP2030 has trees for loading and unloading. Loading is also where a product's custody starts |
| Planar table | The controller against the real table (only the simulated driver has run); the shuttles' AASs from it; MoveToPosition from the agents, then on the table; the vial holders |
| Agents ([agents.md](agents.md), section 7) | A1: loading and unloading as steps, MoveToPosition on the planar controller. A2 on the filling Pi. A3: a planned skill in a bid. A4: the agents as a service; a Pi plugged in has its agent within seconds. A5: the series' names from Variables. A6: a resource that goes away, timeouts, restarts. A7: the Orders app, the messages logged, the scenario script. A8: the rehearsal |
| Models | Proposals with a time (booking ahead); the product instance's AAS as the batch record; the bindings out of the recipe into the process AAS (F6); the eleven decisions of [state-and-parameters.md](state-and-parameters.md); taring |
| Web UI | One fork (section 3), pushed and following BaSyx; Configurator finished; the classic or the BPMN editors for the demo; the HMI as an app (C5) or the Python HMI fixed (its 7 tests); the Orders app (A7) |
| Server | Which machine runs the stack; publishing to the lab's AAS server (permission); a persistent AAS store (MongoDB) instead of memory; the resources by name instead of by address; the manifest server on every Pi |
| With the colleagues | Their repositories in the organization; each duplicate of section 3 resolved; behaviour trees, agents or both in the demo; the glossary |
| Framework | Sections 4 to 6: the code changes, the split, CI, images, releases, the site; the icons exported (section 8); licences checked; a `CITATION.cff` |

### 7.3 Order of work

| When | Work |
| --- | --- |
| Now to 18 Nov | The paper first. From this plan only what helps it: the organization created; `aaspire` as a main repository that pins today's repositories (no split yet), tagged `2026.11` with a DOI, so the paper can cite it |
| 19 to 30 Nov | A meeting with the colleagues on section 3 and the glossary; the code changes of section 4; the split (section 5) of this repository and AP2030-UNS; CI with the shared workflow; images; FORTE as releases; deploy-server and deploy-module |
| December | The site's first version; agents A3 to A6; the stoppering module; loading and unloading; the Orders app |
| January | The rehearsal on the hardware; release `2027.01` |

## 8. Icons and figures

[figures/framework-icons.drawio](figures/framework-icons.drawio) has an icon for each repository and
app (page *Icons*) and the organization's map (page *Organization*). The icons are also a draw.io
library, [figures/library/tools.xml](figures/library/tools.xml), in the shape panel in VS Code.
`docs/presentation/source/build_icons.py` draws both.

The logo is the AAS shell standing on four pillars in the colours of Planning, Integration,
Reconfiguration and Execution; the name is written with its letters in the same colours. Each icon
takes its pillar's colour, from the figures' palette:

| Colour | Pillar | Icons |
| --- | --- | --- |
| Teal `#2A918B` (every AAS) | AAS | aas-model, ontologies, skill-model, aas-generator |
| Orange `#F07D2E` | Planning | fond-aas, modplan, Planner |
| Gold `#B88A1C` (the protocols) | Integration | registration-service, aas-camel-dmp, uns-schemas, modlink |
| Green `#5B963B` (IEC 61499) | Reconfiguration | modsync, iec61499-skill-lib, modgen, iec61499-mgmt-py, forte-runtime, Skill Editor |
| Blue `#6C91B2` (resources) | Execution | bt-controller, lineagents, packml-stations, planar-controller, HMI, Orders |
| Dark blue `#56708A` | Interfaces | basyx-aas-web-ui |
| Slate `#4A5560` | Deployment | deploy-server, deploy-module, docs |
| Purple `#9080B7` (the product) | Lines | aseptic-line |

Still to do with them: SVG and PNG per icon for the READMEs, the organization's avatar (the logo at
500 px), the site's favicon, a social preview image (1280 × 640).

## 9. Effort (our part)

| Work | Days |
| --- | --- |
| The first `aaspire` that pins today's repositories, with a DOI | 0.5 |
| Code changes of section 4 | 3 |
| The split with history, the main repository, the workspace | 2 |
| CI, images, releases | 2 |
| deploy-server and deploy-module, tried on a fresh Pi and a fresh PC | 2 |
| The site's first version | 3 |

Resolving section 3 depends on the colleagues and is not counted.

## 10. Decisions

Decided on 31 Oct: the name AASPIRE; the AP2030 organization holds everything; the main repository is
the framework (`aaspire`).

| # | Open question | Recommendation |
| --- | --- | --- |
| 1 | The organization's handle | `ap2030` if that account is the lab's (turned into an organization), otherwise `ap2030-project` |
| 2 | The colleagues' repositories into the organization, and who maintains which | Ask them before the split; the BT controller, FOND-AAS, the DMP, aas-model and the schemas stay theirs to maintain |
| 3 | Each duplicate of section 3 | Decided together in one meeting after 18 Nov |
| 4 | Behaviour trees, agents or both in the demo | Both: a planned batch run as a tree, orders placed with the agents, on the same AAS |
| 5 | The line's repository: `aseptic-line` (from this repository, with its history) | Yes |
| 6 | When: the organization and the first `aaspire` before 18 Nov, the split after | Yes |
| 7 | The documentation: Sphinx with MyST, or MkDocs? | Sphinx with MyST |
| 8 | Capping, inspection, the loading and unloading robots in the demo: as IEC 61499 modules, PackML stations or simulated? | Decide before December |
