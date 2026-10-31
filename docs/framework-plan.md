# AASPIRE: the framework, its repositories, documentation and what is missing

Proposal of 31 Oct 2026, revised the same day with the user's decisions:
- the framework is called **AASPIRE**;
- one GitHub organization, `ap2030-project`, holds the **AP2030** project, with the framework as its
  main repository;
- AP2030-UNS, the project's first stack, is its predecessor and is archived;
- the demo runs one line with two orchestrators, and only the orchestration differs between them.

It replaces the target of [repositories.md](repositories.md) (6 Oct), which stays as the analysis of
our own parts. Nothing here is done yet except the icons (section 8). The decisions still open are in
section 10, each with a recommendation.

The framework has to hold more than our work: the lab's other AAS work has to fit in too, namely
planning with PDDL (FOND-AAS), behaviour trees (the BT controller) and the DMP. The scope is the
demo of January 2027 and the AP2030 line after it.

## 1. The framework

### The name

**AASPIRE: AAS-based Planning, Integration, Reconfiguration and Execution.** Plug and produce with
the Asset Administration Shell. Each letter after the AAS is a pillar, and each pillar holds work
already done in the lab:

| Pillar | What it does | Parts |
| --- | --- | --- |
| **AAS** | Describe: what a resource, a product and a process are | aas-model, the ontologies, the skill model, the AAS generator |
| **Planning** | Decide what to do from capabilities | FOND-AAS (PDDL, FOND planners), `modplan` (HTN), the Planner |
| **Integration** | Plug in: register, discover, connect, map data | The registration service, the DMP, the MQTT message schemas, `modlink` |
| **Reconfiguration** | Change a running resource from its AAS | `modsync`, the IEC 61499 library and runtime, the Skill Editor |
| **Execution** | Produce: run a product's steps on the line, by either orchestrator | The BT controller (centralized), the agents (multi-agent), the IEC 61499 modules, the planar table, the HMI, Orders |

Checked on 31 Oct: free on PyPI and Read the Docs; no AAS work of that name was found. Spoken aloud it
sounds like A.SPIRE, the EU process-industry association behind Processes4Planet; written, the two
differ.

### One line, two orchestrators

The demo runs the same line in two ways, and the framework is built so that only the orchestration
changes:

- **Centralized:** FOND-AAS plans a policy for the order with PDDL from the AASs, and the BT controller
  runs it as a behaviour tree (Schwörer et al., ETFA 2026).
- **Multi-agent:** a product agent per unit follows its product's recipe, and the resource agents bid
  for its steps (`lineagents`, SPADE over XMPP).

Everything below the orchestration is the same for both:

| Shared | What it is |
| --- | --- |
| The models | The resource, product and process AASs: Skills, Capability Description, the interface descriptions, Operational Data; the product's recipe. Both orchestrators start from the same order |
| The modules | ModLib's behaviour in IEC 61499: occupation, the PackML module state, each skill's state machine, the skills as OPC UA methods |
| Running a skill | Occupy the module, bring it to Execute, start the skill, wait for its end, release. `lineagents`' executors do this now, straight over OPC UA or through the DMP |
| Integration | Registration and discovery; the DMP (Operations to OPC UA, values to the time series) |
| Reconfiguration | A planned skill created online by `modsync` before it is run |
| The line | The same modules, planar table, simulators and inventory |

What it takes (section 4, items 7 and 8; section 7.2):

- **The BT controller's action nodes run a skill as the agents' executors do:** the same steps, by the
  same route. AP2030-UNS's BT controller commanded PackML stations over MQTT instead.
- **FOND-AAS reads the same resource AASs and takes its goal from the same recipe.** Its AI-Planning
  submodel overlaps the Capability Description (section 3).
- **`modsync`'s reconfiguration as a service**, so that a tree can have a planned skill created, as an
  agent does.
- **Occupation is the handover:** whoever holds a module commands it, so the line passes from one
  orchestrator to the other between orders, once every module is released.
- **`aaspire` starts the line with either orchestrator** (`--profile bt` or `--profile agents`).
- **One scenario for both:** the same orders and events (a module failing, a rush order, a module
  plugged in), run by both orchestrators and measured the same way. This comparison is for the
  journal paper.

### Names

| What | Name |
| --- | --- |
| The organization | `ap2030-project` (`github.com/ap2030-project`), for the AP2030 project; `ap2030` is a personal account |
| The main repository | `aaspire` |
| The documentation | `aaspire.readthedocs.io` |
| Python distributions | `aaspire-<tool>` (`aaspire-modsync`); import and command names stay (`modsync`) |
| Container images | `ghcr.io/ap2030-project/<repository>` |

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
| What decides which resource does which step, and when | orchestrator: centralized (the BT controller) or multi-agent (the agents) | controller |
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
| The project's first stack, no longer used: HiveMQ, MQTT Explorer, TimescaleDB, Grafana, Portainer, the Configurator, Groot2, the BT controller, BaSyx; the line's AASs (`AASDescriptions`) and trees (`BTDescriptions`), the MQTT schemas on GitHub Pages, the PackML stations, a planar controller and simulator, a registration service, operation delegation, the DataBridge, the Aseptic Production Ontology, the AAS generator as `ppr-ontology` | AP2030-UNS (lab organization) | C++, Python, Compose |
| aas-model, a registration service (AAS from minimal JSON), the DMP's upstream, a web UI fork, the IDTA templates' fork, the MQTT message schemas, AASBT.CPP (BehaviorTree.CPP with the AAS), FOND-AAS's data, forks of unified-planning and of 4diac FORTE, IDE and FBE | Tristan's account | Python, Java, C++ |
| Planner, Skill Editor, the BPMN editors, Configurator (in progress) | The user's web UI fork; 9 commits not pushed | Vue, TypeScript |
| The DMP with the lab's modules | The user's fork of the DMP, branch `lab-modules` | Java |
| The AAS generator | ARSO_Ontology_AAS_Generation (the user's account) | Python, web |

What stands out:

1. **AP2030-UNS is the predecessor.** It ran PackML stations over MQTT, orchestrated by behaviour
   trees, with HiveMQ and TimescaleDB, and is no longer used. AASPIRE succeeds it: IEC 61499 modules
   over OPC UA, with Mosquitto, Prosody and InfluxDB, run by either orchestrator. What is still of use
   is copied out before it is archived.
2. **Several parts exist twice** (section 3), fewer now that AP2030-UNS's copies go.
3. **Three owners on GitHub**: the lab's organization, the user's account and Tristan's account.
4. **Our tools import each other in a circle**: `modreg` imports `modplan` and `modsync`, `modsync`
   imports `modreg`, `modplan` imports both. `modgen.spec` (the skill and flow model) and
   `modsync.aasjson` and `modsync.described` are used by every tool.
5. **A binary in Git** (`runtime/bin/forte-aarch64`, 14 MB), downloaded by `install.sh` from `main`.
6. **No CI, no releases, no published packages, no documentation site** for our parts.

## 3. What exists twice: to resolve with the colleagues

| Part | Copies | Proposal |
| --- | --- | --- |
| Registration service | Tristan's `aas_registration_service`, `modreg serve` | One `registration-service`: building an AAS from a profile, the ontology check, discovery, publishing. Which code is the base is decided with Tristan |
| Web UI | Tristan's fork, the user's fork | One fork in the organization, every app on one branch that follows BaSyx's `main` |
| DMP | Tristan's (upstream), the user's fork | Tristan's moves into the organization; branch `lab-modules` merged into it |
| Ontologies | `ontology/` here, the generator's copy (`ppr-ontology`) | One `ontologies` repository; the generator takes it as a package. AP2030-UNS's Aseptic Production Ontology goes in only if something still uses it |
| 4diac FORTE | Tristan's fork, our patches applied by `runtime/` | One fork of FORTE with our patches as commits; `forte-runtime` builds from it |
| The behaviour trees' runner | AP2030-UNS's `BT_Controller` (BehaviorTree.CPP, PackML commands over MQTT), Tristan's AASBT.CPP (BehaviorTree.CPP with the AAS) | One `bt-controller`, whose action nodes run a module's skills as in section 1. Which code is the base is decided with Tristan |
| What a resource can do, for planning | FOND-AAS's AI-Planning submodel; the Capability Description and Skills | What the AI-Planning submodel repeats is generated from the other two, so that a module plugged in can be planned by both orchestrators without being modelled twice; what only line-level planning needs (uncertain outcomes) stays its own. Decided with Tristan |

Settled by retiring AP2030-UNS:
- **MQTT broker:** Mosquitto; HiveMQ goes.
- **Time series:** InfluxDB, which the DMP writes and the agents read; TimescaleDB goes.
- **Planar table:** `planar-controller` with its simulator; AP2030-UNS's controller and simulator go.
- **A station's logic:** IEC 61499 modules with ModLib's PackML state machine, for both orchestrators;
  the PackML stations over MQTT go.
- **MQTT schemas:** only Tristan's `mqtt_message_schemas`, if they are still needed without the
  PackML stations (aas-model loads them); AP2030-UNS's `MQTTSchemas` goes.
- **Registration:** AP2030-UNS's `Registration_Service` goes.
- **Orchestration:** both orchestrators stay, as the demo's comparison (section 1).

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

And three that the deployment needs:

4. **Binaries as releases**: FORTE per platform as release assets and one multi-arch image (amd64,
   arm64); `install.sh` takes a version, not `main`.
5. **Every service an image**, built by CI: registration, the agent manager, the BT controller, the
   web UI, the DMP, the simulated modules (FORTE with simulated IO).
6. **No addresses in code**: the resources' addresses and the server's in one inventory file of the line,
   read by the deployment, the tests and the scenario runner.

And two that let either orchestrator run the line (section 1):

7. **One way to run a skill**: the agents' executors (OPC UA, DMP, simulated) become plug-ins, chosen
   per resource in the configuration; the BT controller's action nodes take the same steps by the
   same route.
8. **Reconfiguration as a service**: `modsync`'s online reconfiguration, today a function the agents
   call, behind an endpoint that a behaviour tree can call too.

## 5. The repositories

**23 repositories in `ap2030-project`**, by pillar:

| Pillar | Repository | Holds | Comes from |
| --- | --- | --- | --- |
| Main | **aaspire** | Every repository below as a submodule; the documentation site; `compose.yaml` that runs the whole line in simulation on one PC; the end-to-end tests; the releases | New |
| Main | **.github** | The organization's profile page (the map and the icons), issue templates, shared CI workflows | New |
| AAS | **aas-model** | The lab's pydantic AAS model and its template-to-class generator | Tristan's |
| AAS | **ontologies** | ARSO, APSO, AProSO, PPRL, the vocabularies, the SHACL shapes, the checks; a Python package with the Turtle files as data | `ontology/`, the generator's copy (section 3) |
| AAS | **skill-model** | Skills, flows and parameters as every tool reads them; reading an AAS's skills | `modgen.spec`, `modsync`, `modplan` (section 4) |
| AAS | **aas-generator** | From spec sheets to a profile (LLM pipeline, editor, SHACL validation) | ARSO_Ontology_AAS_Generation |
| Planning | **fond-aas** | Production policies planned from the AAS with FOND planners (PDDL), for the BT controller | Tristan's FOND-AAS |
| Planning | **modplan** | New skills planned from a Capability Description (HTN; PDDL and HDDL exported) | `aas61499-tools/modplan` |
| Integration | **registration-service** | Building, checking, discovering and publishing AASs (`modreg`) | Section 3 |
| Integration | **aas-camel-dmp** | The DMP: AAS operations and values to OPC UA, MQTT, HTTP and time series | Tristan's |
| Integration | **mqtt-schemas** | The MQTT messages' JSON schemas, on GitHub Pages (aas-model loads them) | Tristan's `mqtt_message_schemas`, if still needed (section 3) |
| Integration | **modlink** | Running a resource's skills from its AAS over OPC UA | iec61499-opcua-hmi |
| Reconfiguration | **modsync** | A running IEC 61499 program against its AAS: verify, change online, record, the IDE project | `aas61499-tools/modsync` |
| Reconfiguration | **iec61499-skill-lib** | ModLib, the standard blocks' declarations, `modgen`, the module rules | `iec61499-skill-lib/` |
| Reconfiguration | **iec61499-mgmt-py** | The FORTE management protocol client | `iec61499-mgmt-py/` |
| Reconfiguration | **forte-runtime** | FORTE with ModLib per platform, the kit for one's own blocks; releases and the image | `runtime/`, the FORTE forks |
| Execution | **bt-controller** | The centralized orchestrator: FOND-AAS's policies run as behaviour trees, its action nodes running skills as in section 1 | Section 3 (AP2030-UNS's `BT_Controller` or AASBT.CPP) |
| Execution | **lineagents** | The multi-agent orchestrator: order, product and resource agents, following the products' recipes | `line-agents/` |
| Execution | **planar-controller** | The planar table with its simulator | planar-controller (lab organization) |
| Interfaces | **basyx-aas-web-ui** (fork) | Planner, Skill Editor, the BPMN editors, Configurator, HMI, Orders | Section 3 |
| Deployment | **deploy-server** | The server stack by Compose: BaSyx (environment, registries, discovery), Mosquitto, Prosody (XMPP), InfluxDB, the DMP, registration, the web UI, both orchestrators (the BT controller with Groot2; the agents); `.env.example`. Images by version, no source | `deploy/aas` |
| Deployment | **deploy-module** | A Raspberry Pi becomes an IEC 61499 module: `install.sh`, its compose, the manifest server, `pi.py`, the offline kit | `deploy/pi`, `runtime/install.sh`, `runtime/kit` |
| Lines | **aseptic-line** | AP2030's line: its AASs, the module specs and generated projects, the simulated modules, products and recipes, the scenario both orchestrators run, the evaluation, the inventory, the working notes | `cell/` and `docs/` here |

Pinned, not ours: Eclipse 4diac FORTE, BaSyx's images, BehaviorTree.CPP and AASBT.CPP, Groot2,
unified-planning, the IDTA templates. Archived afterwards, with a pointer to `aaspire`: AP2030-UNS
(the predecessor), iec61499-opcua-hmi, ARSO_Ontology_AAS_Generation.

How they come together:

- **Only `aaspire` has submodules**, one level deep, in folders by pillar (`aas/`, `planning/`,
  `integration/`, `reconfiguration/`, `execution/`, `interfaces/`, `deployment/`, `lines/`).
- **Everything else depends by version**: Python packages by tag (later PyPI), the ontologies as a
  package, images by tag, FORTE by release.
- **One Python environment for development**: `aaspire` is a uv workspace with every Python part
  installed editable; the C++, Java and TypeScript parts build as images.
- **One command for the line in simulation**: `aaspire`'s `compose.yaml` includes deploy-server's and
  adds the simulated resources (the IEC 61499 modules with simulated IO, the planar table) and one
  orchestrator (`docker compose --profile sim --profile bt up`, or `--profile agents`).
- **Versions**: the parts by SemVer; `aaspire` by date (`2026.11` with the CIRP paper, with a Zenodo DOI
  to cite; `2027.01` with the demo); ARSO keeps its own numbers.

The split itself: this repository is transferred to the organization and renamed `aseptic-line`
(GitHub redirects the old address). Each part is copied out with its history by `git filter-repo
--path` and then removed here; `iec61499-mgmt-py` becomes the library's name again. AP2030-UNS is
archived as it is, its README pointing to `aaspire`, once what is still of use (the BT controller, if
it is the base) has been copied out with its history. The installer's address in the README, the
slides and the paper is checked afterwards.

## 6. Documentation on Read the Docs

**One site, `aaspire.readthedocs.io`, built from `aaspire`** with its submodules: one navigation, one
search, one version per release. Sphinx with MyST (Markdown), the Python reference generated from the
code, Mermaid for small diagrams, the draw.io figures as SVG. Each repository keeps a README (what it is,
install, one example, a link to its part of the site) and a `docs/` folder of its own pages, which the
site gathers; each pillar's pages are written by the people who build it.

| Section | Pages |
| --- | --- |
| Overview | What AASPIRE is; the five pillars and the architecture figure; the parts with their icons; glossary; how to cite |
| Tutorials | The AP2030 line in simulation on one PC; plugging in a resource; the same order run by each orchestrator; changing a skill online |
| How-to guides | Deploy the server; deploy a module on a Pi; register a vendor's resource; write a skill in the Skill Editor; plan with FOND-AAS or `modplan`; map an interface with the DMP; build FORTE with your own blocks |
| Concepts | One page per pillar: the AAS and the ontologies; planning; integration; reconfiguration; execution (the two orchestrators, what they share and how they compare) |
| Reference | Each tool's commands; the Python API; ARSO and the vocabularies (tables from the Turtle); the submodel templates; the MQTT messages; the I4.0 messages; the services' HTTP endpoints; settings and ports |

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
| The code citable: the fork's 9 commits pushed, aas-model's pull request opened; `ap2030-project` created and a first `aaspire` that pins today's repositories as submodules, tagged `2026.11` with a DOI | The user's go; the organization created by a lab member |

### 7.2 The demo (to January)

| Area | Missing |
| --- | --- |
| Filling module | Dispensing on the real axis; the scale is simulated (a real one, e.g. an HX711, later) |
| Stoppering module | The old container removed and the new runtime installed (the user's go); its wiring written down; the axis wired and moving |
| Capping and inspection | Specs in `cell/modules/planned` only: modules generated from their specs, simulated (FORTE with simulated IO) where there is no hardware (section 10) |
| Loading and unloading | The two Kuka robots (a Pi each): no AAS or module of ours. Behind a module each (occupation, the PackML state, skills), both orchestrators can use them; AP2030-UNS's trees show the steps. Loading is also where a product's custody starts |
| Planar table | The controller against the real table (only the simulated driver has run); the shuttles' AASs from it; MoveToPosition from the agents, then on the table; the vial holders |
| Centralized orchestration | With the colleagues: FOND-AAS on our AASs, its goal from the product's recipe; the BT controller's action nodes for our modules (section 4, item 7); a batch on the simulated line, then on the hardware; Groot2 to watch it |
| Agents ([agents.md](agents.md), section 7) | A1: loading and unloading as steps, MoveToPosition on the planar controller. A2 on the filling Pi. A3: a planned skill in a bid. A4: the agents as a service; a Pi plugged in has its agent within seconds. A5: the series' names from Variables. A6: a resource that goes away, timeouts, restarts. A7: the Orders app, the messages logged, the scenario script. A8: the rehearsal |
| The comparison | Proposed: one scenario of orders and events, run by both orchestrators; measured the same way: the time to finish the orders, the reaction to a module failing, the time until a module plugged in is used, the work to set each up. In the demo, the line handed from one to the other |
| Models | Proposals with a time (booking ahead); the product instance's AAS as the batch record; the bindings out of the recipe into the process AAS (F6); the eleven decisions of [state-and-parameters.md](state-and-parameters.md); taring |
| Web UI | One fork (section 3), pushed and following BaSyx; Configurator finished; the classic or the BPMN editors for the demo; the HMI as an app (C5) or the Python HMI fixed (its 7 tests); the Orders app (A7), sending an order to either orchestrator |
| Server | Which machine runs the stack; publishing to the lab's AAS server (permission); a persistent AAS store (MongoDB) instead of memory; the resources by name instead of by address; the manifest server on every Pi |
| With the colleagues | Their repositories in the organization; each item of section 3 resolved; the BT controller and FOND-AAS on our modules; the glossary |
| Framework | Sections 4 to 6: the code changes, the split, CI, images, releases, the site; the icons exported (section 8); licences checked; a `CITATION.cff` |

### 7.3 Order of work

| When | Work |
| --- | --- |
| Now to 18 Nov | The paper first. From this plan only what helps it: the organization created; `aaspire` as a main repository that pins today's repositories (no split yet), tagged `2026.11` with a DOI, so the paper can cite it |
| 19 to 30 Nov | A meeting with the colleagues on section 3, the glossary and how the BT controller runs a skill; the code changes of section 4; the split (section 5) of this repository; AP2030-UNS archived; CI with the shared workflow; images; FORTE as releases; deploy-server and deploy-module |
| December | The site's first version; agents A3 to A6; the BT controller on the simulated line; the stoppering module; loading and unloading; the Orders app |
| January | The rehearsal on the hardware, the same orders by both orchestrators; release `2027.01` |

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
| Gold `#B88A1C` (the protocols) | Integration | registration-service, aas-camel-dmp, mqtt-schemas, modlink |
| Green `#5B963B` (IEC 61499) | Reconfiguration | modsync, iec61499-skill-lib, modgen, iec61499-mgmt-py, forte-runtime, Skill Editor |
| Blue `#6C91B2` (resources) | Execution | bt-controller, lineagents, planar-controller, HMI, Orders |
| Dark blue `#56708A` | Interfaces | basyx-aas-web-ui |
| Slate `#4A5560` | Deployment | deploy-server, deploy-module, docs |
| Purple `#9080B7` (the product) | Lines | aseptic-line |

Still to do with them: SVG and PNG per icon for the READMEs, the organization's avatar (the logo at
500 px), the site's favicon, a social preview image (1280 × 640).

## 9. Effort (our part)

| Work | Days |
| --- | --- |
| The first `aaspire` that pins today's repositories, with a DOI | 0.5 |
| Code changes of section 4 (ours; the BT controller's nodes are the colleagues') | 4 |
| The split with history, the main repository, the workspace | 2 |
| CI, images, releases | 2 |
| deploy-server and deploy-module, tried on a fresh Pi and a fresh PC | 2 |
| The site's first version | 3 |

Resolving section 3 depends on the colleagues and is not counted.

## 10. Decisions

Decided on 31 Oct:
- the name AASPIRE;
- one organization, `ap2030-project`, holds the AP2030 project's repositories;
- the main repository is the framework (`aaspire`);
- AP2030-UNS is the predecessor, archived once what is still of use is copied out;
- the demo runs one line with two orchestrators, centralized (PDDL and behaviour trees) and
  multi-agent (product recipes), with everything below the orchestration the same for both (section 1).

| # | Open question | Recommendation |
| --- | --- | --- |
| 1 | The colleagues' repositories into the organization, and who maintains which | Ask them before the split; the BT controller, FOND-AAS, the DMP, aas-model and the MQTT schemas stay theirs to maintain |
| 2 | Each item of section 3 | Decided together in one meeting after 18 Nov |
| 3 | The route by which both orchestrators run a skill: through the AAS server and the DMP, or straight over OPC UA | Through the DMP: one way in for every client in any language, and every call in the module's log. Straight over OPC UA stays an option for both, for speed |
| 4 | The line's repository: `aseptic-line` (from this repository, with its history) | Yes |
| 5 | When: the organization and the first `aaspire` before 18 Nov, the split after | Yes |
| 6 | The documentation: Sphinx with MyST, or MkDocs? | Sphinx with MyST |
| 7 | Capping, inspection, the loading and unloading robots in the demo | Modules with ModLib's behaviour: generated from their specs, simulated where there is no hardware; each robot behind a module of its own, so both orchestrators can use it |
