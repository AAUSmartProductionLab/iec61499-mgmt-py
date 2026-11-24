# Starting on this repository

For a new working session (a person, or an AI coding agent) that picks up the work here. It says
what the work is for, what is where, the rules the work follows, the state on 17 Nov 2026 and what
comes next. The details are in the documents it links; read [pipeline.md](pipeline.md) and, for the
demo, [framework-plan.md](framework-plan.md) section 7 before planning anything.

## What the work is for

Modules of a pharmaceutical filling line (filling, stoppering, capping; inspection planned) run
as Eclipse 4diac FORTE programs (IEC 61499) on Raspberry Pis. Each module is described by an Asset
Administration Shell (AAS). The aim is a specification of three things:

1. how a module is built (its control structure and interface: [module-rules.md](module-rules.md));
2. what its AAS holds ([aas-models.md](aas-models.md), the resource ontology ARSO in `ontology/`);
3. how the AAS drives control and reconfiguration of the running module.

It has to work for a module a vendor delivers with only its IEC 61499 program and its AAS. Our
module specs (`cell/modules/*.yaml`) and the generator `modgen` are one vendor-side way to build
a conforming module, not something the integrator has. When designing, ask: could this be done
for a vendor's module with only its AAS and its FORTE?

**The paper.** The CIRP CMS full paper, *From Product Requirements to Running Skills: AAS-Driven
Planning and Reconfiguration of IEC 61499 Modules*, was **submitted on 17 Nov 2026**. Its code, AASs
and results are in the companion repository https://github.com/MartinJensen37/aas-driven-recon-iec61499
(public); its source (`AASPIRE-material/papers/cirp/`) stays local and is never committed. Its evaluation: matching
on 80 cases against a separate process simulation, planned BottomUpFilling skills (15 of 15 fill
right), the checker (90 % of incorrect skills rejected), new skills deployed and verified on the
filling module's Pi (32 steps in 20 composites in 2.06 s, Q1 of 17 Nov) and drift (on the PC).
**Now: the demo in January** (below). Agents (product and resource agents bidding for process steps)
are the paper's future work and one of the demo's two orchestrators.

## What is where

The map of the folders is in the [README](../README.md); each top-level folder goes to one or more
repositories of the `AAU-AASPIRE` organization ([framework-plan.md](framework-plan.md), section 5;
nothing is split yet). In short:

| Folder | What |
| --- | --- |
| `iec61499-mgmt-py/` | `iec61499_mgmt`: FORTE management protocol client, `.sys` flattening, boot files, read-back |
| `iec61499-skill-lib/` | `modgen` (module spec to 4diac project), `ModLib` (the generated module library), the generator's test module |
| `aas61499-tools/` | `modsync` (module, spec and AAS: read, verify, reconfigure, push, `project`), `modreg` (profiles on aas-model, ontology check, registration service, discovery), `modplan` (new skills planned from a module's Capability Description) |
| `runtime/` | FORTE builds for the PC and the Pi (patches, FBE configurations, `build-modules.ps1`, `build-pi.ps1`), the packaged Pi binary `runtime/bin/forte-aarch64`, the installer `install.sh`, the kit for building FORTE with one's own block types (`make-kit.ps1`) |
| `deploy/` | The Pi: FORTE in Docker, `pi.py` (install, module, log); the lab's AAS stack on this PC: BaSyx, the DMP, InfluxDB, Mosquitto, Prosody (`aas/compose.yaml`, `aas.py`) |
| `cell/` | Module specs, the generated projects (`cell/control/`), simulator, the example line's AASs (`cell/examples/`), the paper's evaluation (`cell/eval/`) |
| `aas-model/`, `aas-camel-dmp/`, `iec61499-opcua-hmi/`, `basyx-aas-web-ui/`, `planar-controller/` | Submodules: the lab's pydantic AAS model (the user's fork, branch `lab-ppr-models`); the DMP that runs an AAS's mappings (Operations to OPC UA methods, values to InfluxDB); the HMI with `modlink`; the BaSyx web UI fork with the process planner and the skill editor; the planar table's controller (Python, OPC UA like a module) |
| `module-py/` | `modpy`: a module run in Python from its spec, served over OPC UA node for node as a generated module on FORTE; the robot modules (`cell/modules/python`), their robots simulated ([demo-modules.md](demo-modules.md), section 3) |
| `line-agents/` | `lineagents`: the line's agents (SPADE, XMPP, VDI/VDE 2193): resource agents per module and per shuttle, an order agent that starts a product agent per unit ordered, the manager that starts them from the AAS server ([agents.md](agents.md)) |
| `ontology/`, `docs/` | Ontologies (ARSO and others); working documents |
| `aaspire/` | The documentation site (MkDocs) for a reader who was not there: a page and a figure per part; `cd aaspire; python -m mkdocs serve` |

The documents in `docs/`: [tooling.md](tooling.md) (every tool, command and check),
[pipeline.md](pipeline.md) (from AAS to running code, and how code is changed),
[tools.md](tools.md) (what modgen, modsync, modlink and modplan each do, and how),
[mapping.md](mapping.md) (an AAS skill as IEC 61499 blocks and back; the AAS as the target state),
[skill-planning.md](skill-planning.md) (composing skills by planning from the Capability Description),
[locations-and-layout.md](locations-and-layout.md) (frames along the hierarchy, points, the planar table's layout),
[design-decisions.md](design-decisions.md) (the decisions the method rests on, with why; for the
paper), [skill-authoring.md](skill-authoring.md) (the skill editor's and the planner's proposal of
27 Oct, decided and built; what stands is in [module-rules.md](module-rules.md), section 3, and the
web UI fork) and [control-configuration.md](control-configuration.md) (option C, decided and built
27 Oct: `RuleSet` and `Deployment` in the AAS, the record outside it), [ppr-model.md](ppr-model.md) (the product, process and resource model with its figures in `figures/`), [next-steps.md](next-steps.md) (the plan), [decisions.md](decisions.md),
[work.md](work.md) (what was built, how, and every learning; long, search it),
[module-rules.md](module-rules.md), [modules.md](modules.md) (the two modules and their hardware),
[building-skills.md](building-skills.md) (a new skill, primitive or piece of equipment, for the lab's
engineers), [filling-program.md](filling-program.md) (the filling program block by block),
[forte-for-the-pi.md](forte-for-the-pi.md) (building FORTE for the Pi),
[aas-models.md](aas-models.md), [aas-examples.md](aas-examples.md),
[state-and-parameters.md](state-and-parameters.md) (a modelling plan waiting for decisions),
[agents.md](agents.md) and [agents-literature.md](agents-literature.md) (the agents),
[demo-modules.md](demo-modules.md) (capping, inspection, and loading and unloading with the KUKA
robots: how the demo's other four modules are built, Python beside FORTE),
the papers' notes (`paper-outline.md`, `journal-paper.md`, `orchestration-paper.md`; kept outside
git in the local `AASPIRE-material/papers` folder since 23 Nov, see CLAUDE.md),
[design-log.md](design-log.md) (design considerations, newest first),
[lab-network.md](lab-network.md) (the lab network from 23 Nov: addresses, names, what to do per
module), [framework-plan.md](framework-plan.md) (AASPIRE: the framework that
holds the lab's AAS work, one line run by two orchestrators, its repositories in the `AAU-AASPIRE`
organization, documentation site and icons, and what the January demo still needs).

## How the work is done

Rules from the user; [CLAUDE.md](../CLAUDE.md) holds the git rules.

- **Git.** Commit and push straight to `main`, many small commits that each pass the tests, 1 to
  3 line messages, author `martinjensen37 <martin.jensen37@gmail.com>`, no AI attribution
  anywhere. Pull first: work also arrives from other machines.
- **Ask on design decisions**, with a recommendation; ask questions during the work rather than
  guessing. Small steps: a minimal slice end to end first. Record learnings in
  [work.md](work.md), decisions in [decisions.md](decisions.md) and every design consideration in
  [design-log.md](design-log.md) (CLAUDE.md).
- **The repository is public.** No passwords, tokens or keys in any file or commit.
- **Layouts the user arranged in the 4diac IDE are kept.** Regenerating with `python -m modgen`
  keeps every position in the `.sys` files and only makes room where blocks or their labels
  overlap (`modgen/layout.py`). Never lay a user's application out again from scratch, and do
  not change a project's content by hand: change the generator or the spec and regenerate.
- **Descriptions** of an AAS are the pydantic dump of an aas-model type, not a format of our own.
  ARSO is authoritative (adapt the code, not the ontology); ask before changing ARSO.
- **Not to be done without the user's go:** publishing to the lab's AAS server (192.168.0.x:8081;
  same ids would overwrite the live stations' shells); pushing the `aas-model` submodule's local
  branch `arso-submodels` (superseded by `lab-ppr-models` on the fork; the pull request to aas-model
  is the user's to open); committing `iec61499-opcua-hmi/hmi/aas.py` (changed, not committed);
  pushing the web UI fork's commits (9 of 30 and 31 Oct not pushed); committing the generation
  project's ARSO 0.8.
- **Never** commit `AAS_Builder/`, `arduino_cpp_examples/` or a generation project's
  `Generation/config.yaml`; never put the teaching demo `C:\Users\marti\Documents\PubSubDemo` (three
  local FORTEs on ports 61501 to 61503) into this repository.
- **Processes** on the PC are stopped only by their PID and only after asking: the three FORTEs
  of the teaching demo usually run and must not be stopped without the user's go.
- **Hardware.** Nothing that moves an axis (Reset, Stop, Home, a skill) is sent to a Pi unless the
  user is at the bench and says go. Reset and Home drive the axis to its limit switch.
- **Windows shell notes.** Bash heredocs halve backslashes on this machine: write scripts with a
  file editor, not a heredoc. Keep a file's line endings when patching it.

## Environment

Every tool with its commands and how each kind of change is checked (tests, the IDE's checks,
FORTE's management protocol, running a module, deploying to a Pi, building and publishing the AASs)
is in **[tooling.md](tooling.md)**. Read it before changing or running anything.

```powershell
python -m venv .venv; .venv/Scripts/python.exe -m pip install -e ".[test,registration,opcua,planning,agents]"
$env:PYTHONUTF8 = 1
.venv/Scripts/python.exe -m pytest -q                         # offline, about 2 to 4 min, no known failure
.venv/Scripts/python.exe -m pytest -q --module-forte-exe runtime/fbe/build/modules-win/forte/build/forte/forte.exe   # + live tests, about 12 min (see below)
cd iec61499-skill-lib; ../.venv/Scripts/python.exe -m modgen # regenerate ModLib and the module projects
runtime/build-modules.ps1                                     # IDE check and export, FORTE for Windows
runtime/build-pi.ps1 -SkipValidate                            # FORTE for the Pi from those exports, packaged into runtime/bin
```

- The `aas-model` submodule and the `registration` extra both follow the user's fork
  (https://github.com/MartinJensen37/aas-model, branch `lab-ppr-models`, `ff7122a`, pushed) until
  its pull request to aas-model is merged; then `.gitmodules` and `pyproject.toml` go back to
  aas-model. The local branch `arso-submodels` (19 Oct) is superseded by `lab-ppr-models`.
  `test_the_submodule_is_the_aas_model_the_package_installs` checks that the two are one commit.
- The 4diac IDE (3.3, updated in place in its 3.2.1 folder) is at
  `C:\Users\marti\Downloads\4diac-ide_3.2.1-win32.win32.x86_64\4diac-ide\`; `runtime/check-project.ps1`
  runs its checks headless, `runtime/validate.ps1` also its export (used by `build-modules.ps1`). The
  FORTE build environment (4diac FBE) is `C:\4diac-fbe`.
- The Windows `forte.exe` in `runtime/fbe/build/modules-win/output/bin/` is from 21 Oct: a newer
  build (29 Oct) is in `runtime/fbe/build/modules-win/forte/build/forte/forte.exe` and could not be
  installed while the teaching demo's FORTEs run from the old file. Run the live tests with the
  newer one: the IO blocks of 21 Oct contain GPIOChip and PWMChip, which only the newer builds have
  (as stand-ins on Windows), and it has the flow blocks of rule set 2 and announces its OPC UA
  server (mDNS). Install it (rerun `runtime/build-modules.ps1`) once the demo is stopped.
- The local AAS stack (`deploy/aas.py up`, `lab-*` containers: AAS environment :8081, web UI :3000,
  DMP :8085, InfluxDB :8086, skill service (`modreg serve`) :8090, Mosquitto :1883, Prosody (XMPP, for
  the agents) :5222; with `up --agents` the agents, orders at :8095) holds the example line's AASs
  (`cell/examples/example_line.py --publish`). Since 17 Nov BaSyx (pinned to 2.0.0-milestone-16) keeps
  them in MongoDB, so they survive a restart (volume `lab-aas_aas-data`). Its secrets are in
  `deploy/aas/.env` (not committed). The planner's demo stack (`ps-*`) uses the same ports and is
  stopped.

## The Raspberry Pis

All are reached with this PC's SSH key; `sudo` needs a password that is never written down: ask
the user for it when needed and pass it only for that command.

| Pi | Address, login | Runs | State |
| --- | --- | --- | --- |
| Pi 5 `filling-module` | 192.168.0.203, `admin` | Filling module: TB6600 stepper driver on GPIO18 (PWM channel 2), GPIO27 (DIR, inverted since 13 Nov), GPIO17 (enable); a normally closed home switch on GPIO23 at the far end of the stage (since 13 Nov); the pump not wired, the scale simulated | **17 Nov:** the lab's FORTE (`~/forte/forte`; the paper's evaluation build kept as `~/forte/forte.eval`) and the filling program with the new polarity (`deploy/pi.py module`); switch, homing and two moves checked at the bench. **To do with the user:** the new `deploy/pi/compose.yaml` onto the Pi (`docker compose up -d` in `~/forte`), so the PWM goes off whenever FORTE ends; the positions (NestPosition, FillPosition) measured again from the new home end (`deploy/bench.py move --to <mm> --stay`). Not reachable on the evening of 17 Nov |
| Pi 5 `stoppering-module` | 192.168.0.134, `admin` | Stoppering module since 22 Oct (spec `cell/modules/stoppering.yaml`, board `pi5`, the new pins of 13 Nov); the hardware is not wired | As on 26 Oct, as far as known: the runtime is copied and its image built, but the new container could not start: the running one (from 20 Oct, old filling program) was created outside the compose project and holds the name `forte`. **To do, with the user's go:** `docker rm -f forte && cd ~/forte && docker compose up -d` on the Pi, then `deploy/pi.py module --spec cell/modules/stoppering.yaml`. Its old program is saved as `~/forte/boot/forte.fboot.before-stoppering` |
| Pi 4 `stoppering-module` | 192.168.0.191, `iiot_gateway` | Nothing: **no longer used** (since 26 Oct). It ran the stoppering module 9 to 22 Oct and is in no spec | Do not deploy to it or use it in tests. Its old host name equals the Pi 5's above: address the Pis by IP. Older docs and examples that name 192.168.0.191 are out of date |

FORTE runs in Docker on each Pi (`~/forte`, `docker compose ps | logs -f`); the program is the boot
file `~/forte/boot/forte.fboot`. A program runs only on a FORTE built with its block types: after a
change of block types, build for the Pi and package (`runtime/build-pi.ps1`), commit, install. The
runtime in `runtime/bin` (4 Nov) has the flow blocks of rule set 2, the module architecture of 4 Nov
and announces its OPC UA server (mDNS), so discovery finds it. The module starts Stopped and
unoccupied; a client occupies it and sends Reset. Two traps on the Pis: FORTE 3.3.0 segfaults when it
is stopped, so its own PWM clean-up never runs (since 17 Nov the container's entrypoint turns the PWM
off; a Pi installed earlier needs the new `compose.yaml`), and an OPC UA discovery server (LDS) on the
network, such as the Windows service `UALDS` on this PC, freezes FORTE's OPC UA server for 5 s about
every minute (FORTE registers at it under a `.local` name it cannot resolve): stop it while a module
runs. `deploy/bench.py` checks a module's switch, homing and moves under a watchdog.

## State and next steps

The plan to 18 Nov and the state per area are in [next-steps.md](next-steps.md) (history now); the
demo's plan is in [framework-plan.md](framework-plan.md), [agents.md](agents.md) and
[demo-modules.md](demo-modules.md), section 7 of each. This is the short form.

**Built:** the module library and rules (D1); the information model in ARSO 0.14 (D2); verify,
reconfigure (a value, a new skill), record, operate from the AAS alone, on FORTE on the PC and on
the Pi 5 (D3); `modsync project` writes the 4diac project of what runs. The program structure was
reworked 21 to 22 Oct (deployed inside the application's container so the IDE monitors it, the
resource's START, one address string per IO point, renamed and commented skill block pins, release
inside the skill's Control, compact layouts, every connection hidden). The filling axis moves on
its Pi under FORTE and from the HMI.

The paper's contributions (27 Oct): the skill and capability models, planning new skills from them,
the IEC 61499 module architecture that makes skills, and updating a running module online.

**Built since 27 Oct** (details in [work.md](work.md) and the plan's sections G, B and H):

- **Planning, G0 to G6** ([skill-planning.md](skill-planning.md)): `modplan` plans a skill from the
  module's AAS, describes it, `modsync reconfigure` creates it online and it runs; the same problems
  as PDDL and HDDL for ENHSP and Aries (`modplan export`); `modreg serve` checks and plans for the
  skill editor, which asks it for both (G7, 29 Oct).
- **The evaluation, B1 and B2 on this PC**: `cell/eval/scenarios.py` (each change online and by a
  restart, five runs in `cell/eval/results`), `cell/eval/planners.py` (the planners timed),
  `cell/eval/figures.py` (the downtime and effort charts). Since 29 Oct the paper's scenario is the changeover
  to the prefilled syringe (BottomUpFilling written as a new skill).
- **The DMP in the lab's AAS stack** (28 and 29 Oct): an Operation invoked at the AAS server calls
  the module's OPC UA method, the module's values are rows in InfluxDB, every call is logged
  (`deploy/aas`, `aas-camel-dmp`, `cell/tests/test_dmp_live.py`); after the planner saves a bound
  recipe, `modreg serve` writes the product's process AAS (F6, 29 Oct).
- **Locations, H1 to H5** ([locations-and-layout.md](locations-and-layout.md)): coordinates in
  Variables, a tree of transforms rooted at the table's base (28 Oct), points of interest, the planar
  table and its shuttles as modules with the flyway layout (`modreg profile planar`), the line
  scenario's stations from the AASs.
- **The reference models** (28 Oct; [aas-examples.md](aas-examples.md)): the types, templates and
  classes of the product, process and resource AASs in aas-model (branch `lab-ppr-models`, its
  `docs/lab-aas.md` and a description per submodel in `docs/lab-submodels`); modreg builds the modules
  with them, and Variables replace Operational Data (ARSO 0.14). Three products (a 2 mL vial, a
  prefilled syringe of 1 mL, a cartridge of 3 mL) and the process of each on the line are written out
  in `cell/examples/products` and `cell/examples/processes`; `cell/examples/example_line.py` builds
  every AAS of the line and checks each process.
- **The paper's outline and figure drafts**: `paper-outline.md` (narrowed on
  28 Oct to restructuring a module through its AAS; 17 references from
  `references.bib`), the figure sources; all in `AASPIRE-material` (local, not in git); the
  effort count `cell/eval/effort.py`.
- **The journal papers**: `journal-paper.md`, the models (since 3 Nov), and
  `orchestration-paper.md`, planning and orchestration: what the CIRP paper
  leaves for them.
  Design considerations go into [design-log.md](design-log.md) as they are made.

**Built since 31 Oct** (details in [design-log.md](design-log.md), newest first):

- **The paper's method finished and evaluated** (Q1 to Q4 in `cell/eval`; the numbers in
  [cirp-evaluation.md](cirp-evaluation.md)): vocabulary 0.10 (the capabilities below DIN 8580 and
  VDI 2860; rates and the container's geometry), BottomUpFilling planned by tracking the needle's
  depth while the pump doses, the checker run in time, one capability matcher (`modreg.match`) for the
  web UI, the agents, the plan check and the evaluation.
- **The module architecture of 4 Nov**: a primitive is its contract (`SC_`), one shared run, one port
  per equipment, `SKILL_Gate`, adapters; FORTE patches 0004 to 0007; the students' kit and the guide
  to the filling program ([filling-program.md](filling-program.md)).
- **The demo's modules**: capping (spec and program, run against the simulator), loading and
  unloading in Python (`modpy`, their robots simulated); the axes home onto a normally closed switch at
  the other end of the stage (13 Nov), checked on the filling Pi on 17 Nov.
- **The web UI fork**: Match and plan binds every step and plans a skill where none matches, matching
  by the skill service, the BPMN editors (18 commits not pushed); a Configurator (products, the line
  on the planar table's grid, shuttle routing, process assignments, orders) is in its working tree,
  not committed.
- **17 Nov**: the Pi's container turns the PWM off whenever FORTE ends; `deploy/bench.py`; the lab
  stack keeps its AASs in MongoDB (BaSyx pinned to 2.0.0-milestone-16), runs the skill service, and
  the agents with `--agents`.

**The demo.** One line run by two orchestrators (decided 31 Oct, [framework-plan.md](framework-plan.md),
section 1): centralized, FOND-AAS's policy planned with PDDL and run as a behaviour tree (the
colleagues' part), and multi-agent, our agents ([agents.md](agents.md)); everything below the
orchestration is the same for both. The timeline (`AASPIRE-material/presentations/demo-plan/README.md`,
not committed): D1 one station and the planar table (**done**); M1 the stations in the lab (all run;
enclosures and end effectors still being 3D printed); D3 capping plugged in (11 Dec); D4 centralized
(18 Dec, the colleagues'); D5 8 Jan, the agents bid; D6 15 Jan, a module fails and production goes
on; D7 22 Jan, the full line with the robots; the partner day on 28 Jan and the demo day at AAU on
10 Feb 2027. D2 (a new sensor) was dropped on 24 Nov.

**State on 24 Nov** (the user's): D1 done; every station runs; the lab stack keeps its AASs in
MongoDB and `deploy/publish.py` publishes all of them, the modules as they run on their Pis.

**Next, in this order:**

1. **The lab network**: every module, the lab server and discovery moved to 172.20.100.x at once
   ([lab-network.md](lab-network.md)); D3 (plug and produce) is then set up on all stations together.
2. **The DMP**: an Operation invoked at the AAS server fails in the DMP ("OPC UA Method invocation
   failed", 502), also on the modules on their Pis (24 Nov), while their values arrive. The agents
   run skills through the DMP or over OPC UA (modlink): both are to stay, chosen per module and
   switchable (today one `--executor` for all).
3. **Locations**: every module's tool centre point and process points sampled at the bench into its
   Coordinates (Variables, Measurements); with the table's base and the shuttles, each product's
   process location follows and changes with the product, the point or a module swapped. Where a
   module stands, by RFID: a proposal is due (tags at the slots or readers on the modules).
4. **The planar controller**: its branch `planner-queue-idle-orientation` (line mode, blended motion,
   to 10 Nov) checked and merged, then on the real table.
5. **The agents for D5 and D6** (agents.md, section 7): beyond one step at a time and the first
   proposal, how a product agent chooses (criteria), how far ahead it plans, and plans shared between
   products, e.g. reservations on each resource's schedule with a dispatching rule (FIFO, round robin,
   earliest deadline first); a proposal is due. Then A3 (a planned skill in a bid), A6 (failures), A7
   (the order screen); all once the stations are up in the lab.
6. **The robots (D7)**: programmed in WorkVisual; a TCP server on each KR C4 selects the program and
   takes its positions (pick from the nest, place on a shuttle, pick from a shuttle, back into the
   nest); `modpy`'s loading and unloading modules talk to it.
7. **Polish**: the web UI fork pushed and the Configurator committed (the user's); the HMI; FORTE's
   crash on stop.

The other four modules of the line (capping, inspection, loading and unloading with the KUKA robots)
are planned in [demo-modules.md](demo-modules.md) (1 Nov), steps M0 to M6.

**Waiting for the user** (do not decide these yourself): the positions at the bench and the new
`compose.yaml` on the filling Pi; the go for the stoppering Pi; the eleven open decisions of
[state-and-parameters.md](state-and-parameters.md); opening aas-model's pull request from the fork's
`lab-ppr-models`; the go to push the web UI fork's commits and to commit the generation project's
ARSO 0.8; merging the planar controller's line mode; whether the order agent takes the Configurator's
orders; whether module level skills become typed subapplications in the IDE; when to commit the HMI's
0.8 reader; the open decisions of the framework plan ([framework-plan.md](framework-plan.md),
section 10) and of the demo's modules ([demo-modules.md](demo-modules.md), section 8); what the KUKA
controllers have (M0 there); how taring is to be modelled.

## Outside this repository

- HMI and `modlink`: https://github.com/AAUSmartProductionLab/iec61499-opcua-hmi (submodule here).
- The lab's AAS model: https://github.com/tristan-schwoerer/aas-model; the submodule here and the
  `registration` extra follow the user's fork https://github.com/MartinJensen37/aas-model (branch
  `lab-ppr-models`) until its pull request is merged.
- The DMP: the user's fork https://github.com/MartinJensen37/aas-camel-dmp, branch `lab-modules`
  (submodule here). The planar table's controller: https://github.com/AAUSmartProductionLab/planar-controller
  (submodule here).
- The organization `AAU-AASPIRE` and the main repository `aaspire`
  ([framework-plan.md](framework-plan.md)) do not exist yet.
- The process planner and skill editor: the user's fork https://github.com/MartinJensen37/basyx-aas-web-ui,
  branch `feat/process-sequence-pharma`; a submodule here since 26 Oct (`basyx-aas-web-ui/`). The
  user's own clone in `C:\Users\marti\Documents\repos\basyx-aas-web-ui` is used by another session:
  leave it alone.
- The ARSO generation and SHACL validation project: https://github.com/MartinJensen37/ARSO_Ontology_AAS_Generation.
- AP2030-UNS, the project's first stack (registration over MQTT, BaSyx, PackML stations run by behaviour
  trees); no longer used, AASPIRE succeeds it: https://github.com/aausmartproductionlab/AP2030-UNS.
- The overall plug-and-produce architecture is a note in the user's own notes; ask for it before
  planning work that crosses repositories.
