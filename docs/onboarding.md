# Starting on this repository

For a new working session (a person, or an AI coding agent) that picks up the work here. It says
what the work is for, what is where, the rules the work follows, the state on 26 Oct 2026 and what
comes next. The details are in the documents it links; read [next-steps.md](next-steps.md) and
[pipeline.md](pipeline.md) before planning anything.

## What the work is for

Modules of a pharmaceutical filling line (filling, stoppering; capping and inspection planned) run
as Eclipse 4diac FORTE programs (IEC 61499) on Raspberry Pis. Each module is described by an Asset
Administration Shell (AAS). The aim is a specification of three things:

1. how a module is built (its control structure and interface: [module-rules.md](module-rules.md));
2. what its AAS holds ([aas-models.md](aas-models.md), the resource ontology ARSO in `ontology/`);
3. how the AAS drives control and reconfiguration of the running module.

It has to work for a module a vendor delivers with only its IEC 61499 program and its AAS. Our
module specs (`cell/modules/*.yaml`) and the generator `modgen` are one vendor-side way to build
a conforming module, not something the integrator has. When designing, ask: could this be done
for a vendor's module with only its AAS and its FORTE?

**The paper.** CIRP CMS full paper, due **18 Nov 2026**. Its claim: *a module that is delivered
with an IEC 61499 program and an AAS can be verified, operated and changed online from those two
alone, without the files it was generated from.* The evaluation (the same changes online and by a
full redeployment, timed, on a Raspberry Pi) is not built yet and is the most urgent part.
Agents (product and resource agents bidding for process steps) are the paper's future work.

## What is where

The map of the folders is in the [README](../README.md); each top-level folder is a future
repository. In short:

| Folder | What |
| --- | --- |
| `iec61499-mgmt-py/` | `iec61499_mgmt`: FORTE management protocol client, `.sys` flattening, boot files, read-back |
| `iec61499-skill-lib/` | `modgen` (module spec to 4diac project), `ModLib` (the generated module library), the generator's test module |
| `aas61499-tools/` | `modsync` (module, spec and AAS: read, verify, reconfigure, push, `project`), `modreg` (profiles on aas-model, ontology check, registration service) |
| `runtime/` | FORTE builds for the PC and the Pi (patches, FBE configurations, `build-modules.ps1`), the packaged Pi binary `runtime/bin/forte-aarch64` |
| `deploy/` | The Pi: FORTE in Docker, `pi.py` (install, module, log); the lab's AAS stack on this PC: BaSyx, the DMP, InfluxDB (`aas/compose.yaml`, `aas.py`) |
| `cell/` | Module specs, the generated projects (`cell/control/`), simulator, the example line's AASs |
| `aas-model/`, `aas-camel-dmp/`, `iec61499-opcua-hmi/`, `basyx-aas-web-ui/`, `planar-controller/` | Submodules: the lab's pydantic AAS model; the DMP that runs an AAS's mappings (Operations to OPC UA methods, values to InfluxDB); the HMI with `modlink`; the BaSyx web UI fork with the process planner and the skill editor; the planar table's controller (Python, OPC UA like a module) |
| `line-agents/` | `lineagents`: the line's agents (SPADE, XMPP, VDI/VDE 2193): resource agents per module, product agents per order, the manager that starts them from the AAS server ([agents.md](agents.md)) |
| `ontology/`, `docs/` | Ontologies (ARSO and others); working documents |

The documents in `docs/`: [tooling.md](tooling.md) (every tool, command and check),
[pipeline.md](pipeline.md) (from AAS to running code, and how code is changed),
[tools.md](tools.md) (what modgen, modsync, modlink and modreg each do, and how),
[mapping.md](mapping.md) (an AAS skill as IEC 61499 blocks and back; the AAS as the target state),
[skill-planning.md](skill-planning.md) (composing skills by planning from the Capability Description),
[locations-and-layout.md](locations-and-layout.md) (frames along the hierarchy, points, the planar table's layout),
[design-decisions.md](design-decisions.md) (the decisions the method rests on, with why; for the
paper), the proposals [skill-authoring.md](skill-authoring.md) (the editor, the planner and their
backend) and [control-configuration.md](control-configuration.md), [ppr-model.md](ppr-model.md) (the product, process and resource model with its figures in `figures/`), [next-steps.md](next-steps.md) (the plan), [decisions.md](decisions.md),
[work.md](work.md) (what was built, how, and every learning; long, search it),
[module-rules.md](module-rules.md), [modules.md](modules.md) (the two modules and their hardware),
[aas-models.md](aas-models.md), [aas-examples.md](aas-examples.md),
[state-and-parameters.md](state-and-parameters.md) (a modelling plan waiting for decisions),
[repositories.md](repositories.md).

## How the work is done

Rules from the user; [CLAUDE.md](../CLAUDE.md) holds the git rules.

- **Git.** Commit and push straight to `main`, many small commits that each pass the tests, 1 to
  3 line messages, author `martinjensen37 <martin.jensen37@gmail.com>`, no AI attribution
  anywhere. Pull first: work also arrives from other machines.
- **Ask on design decisions**, with a recommendation; ask questions during the work rather than
  guessing. Small steps: a minimal slice end to end first. Record learnings in
  [work.md](work.md) and decisions in [decisions.md](decisions.md).
- **The repository is public.** No passwords, tokens or keys in any file or commit.
- **Layouts the user arranged in the 4diac IDE are kept.** Regenerating with `python -m modgen`
  keeps every position in the `.sys` files and only makes room where blocks or their labels
  overlap (`modgen/layout.py`). Never lay a user's application out again from scratch, and do
  not change a project's content by hand: change the generator or the spec and regenerate.
- **Descriptions** of an AAS are the pydantic dump of an aas-model type, not a format of our own.
  ARSO is authoritative (adapt the code, not the ontology); ask before changing ARSO.
- **Not to be done without the user's go:** publishing to the lab's AAS server (192.168.0.x:8081;
  same ids would overwrite the live stations' shells); pushing the `aas-model` submodule's local
  branch `arso-submodels`; committing `iec61499-opcua-hmi/hmi/aas.py` (changed, not committed);
  committing the skill editor's fixes to the web UI fork or the generation project's ARSO 0.8.
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
python -m venv .venv; .venv/Scripts/python.exe -m pip install -e ".[test,registration,opcua,planning]"
$env:PYTHONUTF8 = 1
.venv/Scripts/python.exe -m pytest -q                         # offline, about 2 to 4 min
.venv/Scripts/python.exe -m pytest -q --module-forte-exe runtime/fbe/build/modules-win/forte/build/forte/forte.exe   # + live tests, about 12 min (see below)
cd iec61499-skill-lib; ../.venv/Scripts/python.exe -m modgen # regenerate ModLib and the module projects
runtime/build-modules.ps1                                     # IDE check and export, FORTE for Windows
runtime/build-modules.ps1 -Config pi/modules-pi -SkipValidate # FORTE for the Pi; then runtime/package-runtime.ps1
```

- The offline suite has one known failure, `test_the_submodule_is_the_aas_model_the_package_installs`:
  the `aas-model` submodule is checked out at the local branch `arso-submodels`, not at the pinned
  `6a03f78`. Leave it until the user decides how that branch reaches aas-model.
- The 4diac IDE (3.3, updated in place in its 3.2.1 folder) is at
  `C:\Users\marti\Downloads\4diac-ide_3.2.1-win32.win32.x86_64\4diac-ide\`; `runtime/check-project.ps1`
  runs its checks headless, `runtime/validate.ps1` also its export (used by `build-modules.ps1`). The
  FORTE build environment (4diac FBE) is `C:\4diac-fbe`.
- The Windows `forte.exe` in `runtime/fbe/build/modules-win/output/bin/` is from 21 Oct: a newer
  build (22 Oct) is in `runtime/fbe/build/modules-win/forte/build/forte/forte.exe` and could not be
  installed while the teaching demo's FORTEs run from the old file. Run the live tests with the
  newer one: the IO blocks of 21 Oct contain GPIOChip and PWMChip, which only the newer build has
  (as stand-ins on Windows). Install it (rerun `runtime/build-modules.ps1`) once the demo is stopped.
- The local AAS stack (`deploy/aas.py up`, `lab-*` containers: AAS environment :8081, web UI :3000,
  DMP :8085, InfluxDB :8086) holds the example line's AASs (`cell/examples/example_line.py --publish`).
  Its AAS environment is in memory: publish again after a restart. Its secrets are in
  `deploy/aas/.env` (not committed). The planner's demo stack (`ps-*`) uses the same ports and is
  stopped.

## The Raspberry Pis

All are reached with this PC's SSH key; `sudo` needs a password that is never written down: ask
the user for it when needed and pass it only for that command.

| Pi | Address, login | Runs | State on 26 Oct |
| --- | --- | --- | --- |
| Pi 5 `filling-module` | 192.168.0.203, `admin` | Filling module: TB6600 stepper driver on GPIO18 (PWM channel 2), 27, 17; limit switch on GPIO23, not mounted (pressed by hand) | Program and runtime of 21 Oct morning. **To do, with the user at the bench:** `deploy/pi.py install --forte runtime/bin/forte-aarch64`, then `deploy/pi.py module`, then Occupy and Reset (homes) |
| Pi 5 `stoppering-module` | 192.168.0.134, `admin` | Stoppering module since 22 Oct (spec `cell/modules/stoppering.yaml`, board `pi5`); wiring not known | Renamed from filling-module on 26 Oct (kept across reboots); the runtime is copied and its image built, but the new container could not start: the running one (from 20 Oct, old filling program) was created outside the compose project and holds the name `forte`. **To do, with the user's go:** `docker rm -f forte && cd ~/forte && docker compose up -d` on the Pi, then `deploy/pi.py module --spec cell/modules/stoppering.yaml`. Its old program is saved as `~/forte/boot/forte.fboot.before-stoppering` |
| Pi 4 `stoppering-module` | 192.168.0.191, `iiot_gateway` | Nothing: **no longer used** (since 26 Oct). It ran the stoppering module 9 to 22 Oct and is in no spec | Do not deploy to it or use it in tests. Its old host name equals the Pi 5's above: address the Pis by IP. Older docs and examples that name 192.168.0.191 are out of date |

FORTE runs in Docker on each Pi (`~/forte`, `docker compose ps | logs -f`); the program is the boot
file `~/forte/boot/forte.fboot`. A program runs only on a FORTE built with its block types: after a
change of block types, build for the Pi, package, commit, install. The module starts Stopped and
unoccupied; a client occupies it and sends Reset.

## State and next steps

The state per area and the timeline are in [next-steps.md](next-steps.md); this is the short form.

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
  skill editor (G7's service half).
- **The evaluation, B1 and B2 on this PC**: `cell/eval/scenarios.py` (each change online and by a
  restart, five runs in `cell/eval/results`), `cell/eval/planners.py` (the planners timed),
  `cell/eval/figures.py` (the downtime figure).
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
- **The paper's outline and figure drafts**: [paper-outline.md](paper-outline.md) (narrowed on
  28 Oct to restructuring a module through its AAS; 17 references from
  [paper-references.bib](paper-references.bib)), `docs/figures`; the effort count
  `cell/eval/effort.py`.
- **The journal paper**: [journal-paper.md](journal-paper.md), what the CIRP paper leaves for it.
  Design considerations go into [design-log.md](design-log.md) as they are made.

**Next, in this order:**

1. **B3, on the Pi**: the runtime and program on both Pi 5s (see the table; needs the user), then
   the scenarios on the Pi with the axis moving (`cell/eval/scenarios.py` against the Pi).
2. **Writing** from 2 Nov, on the outline; the figures redrawn as needed.
3. **G7's editor half** (the web UI fork calls `POST /check` and `/plan`), when the fork's open
   changes are committed.
4. Open modelling points the planner found: when the scale may be tared
   ([skill-planning.md](skill-planning.md), section 9); Asset Location (IDTA 02045) for the line.

If time runs short, cut C (clients), E4 and E5, then B3 on real hardware (keep the Pi with
simulated IO), then A3. Not to be cut: A1, A2, B1, B2.

**After the paper: the agents and the demo in January** ([agents.md](agents.md), started 30 Oct, with
the literature in [agents-literature.md](agents-literature.md)). Built: discovery (FORTE announces itself,
`modreg serve --discover`), resource and product agents bidding in the I4.0 language, started by the AAS
server's events, skills run over OPC UA or through the DMP, Prosody in the lab stack. Next: transport by
the shuttles and offers per skill (decisions 8.1 and 8.2 there).

**Waiting for the user** (do not decide these yourself): the go for the two Pis above; the eleven open
decisions of [state-and-parameters.md](state-and-parameters.md); how the `arso-submodels` branch
reaches aas-model; the go to commit the skill editor's fixes and the generation project's ARSO 0.8;
whether module level skills become typed subapplications in the IDE; when to commit the HMI's 0.8
reader; the go to push the two commits in the planar-controller submodule (the layout over OPC UA,
the stations from outside) and then move its pin; whether to change submodules to subtrees
([repositories.md](repositories.md)); how taring is to be modelled.

## Outside this repository

- HMI and `modlink`: https://github.com/AAUSmartProductionLab/iec61499-opcua-hmi (submodule here).
- The lab's AAS model: https://github.com/tristan-schwoerer/aas-model (submodule here).
- The process planner and skill editor: the user's fork https://github.com/MartinJensen37/basyx-aas-web-ui,
  branch `feat/process-sequence-pharma`; a submodule here since 26 Oct (`basyx-aas-web-ui/`). The
  user's own clone in `C:\Users\marti\Documents\repos\basyx-aas-web-ui` is used by another session:
  leave it alone.
- The ARSO generation and SHACL validation project: https://github.com/MartinJensen37/ARSO_Ontology_AAS_Generation.
- The lab's AAS infrastructure (registration over MQTT, BaSyx): https://github.com/aausmartproductionlab/AP2030-UNS.
- The overall plug-and-produce architecture is a note in the user's own notes; ask for it before
  planning work that crosses repositories.
