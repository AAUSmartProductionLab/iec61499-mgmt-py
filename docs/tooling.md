# Tools and how the work is checked

The working recipes behind [onboarding.md](onboarding.md): testing, changing the 4diac programs,
talking to a FORTE, running a whole module, deploying to a Pi, and building and publishing the
AASs. Commands run from the repository root with the repository's venv
(`.venv/Scripts/python.exe`, shown as `python`) and `PYTHONUTF8=1`, unless a folder is named.
Learnings behind these recipes are in [work.md](work.md); search it before debugging something odd.

## 1. Tests

| What | Command | Notes |
| --- | --- | --- |
| Offline, every folder | `python -m pytest -q` | 2 to 4 min. One known failure: `test_the_submodule_is_the_aas_model_the_package_installs` (the `aas-model` submodule is on the local branch `arso-submodels`) |
| One folder or test | `python -m pytest -q iec61499-skill-lib/tests/test_modgen.py -k layout` | |
| Live, against a FORTE on this PC | `python -m pytest -q --module-forte-exe runtime/fbe/build/modules-win/forte/build/forte/forte.exe` | About 12 min. Run it in the background with the output in a log file: FORTE's console output drowns the pipe. Each test starts its own FORTE (and Modbus simulator) on free ports and stops it |
| Live, against a Pi | `python -m pytest cell/tests/test_module_live.py --pi-host <Pi IP> --sim-host <this PC's IP>` | Deploys each module as the Pi's boot file (it replaces the Pi's program: ask the user first, and deploy the module again afterwards); the Pi's FORTE talks Modbus to the simulator on this PC, no header pin is used |
| The Pi binary under emulation | `python -m pytest deploy/tests/test_pwm_emulated.py --pi-forte-exe runtime/fbe/build/modules-pi/output/bin/forte` | Docker with arm64 emulation and a fake `/sys/class/pwm`: checks the PWM and IO blocks of the Pi build without a Pi |
| The HMI submodule | `cd iec61499-opcua-hmi; python -m pytest -q` | Its own tests, not run with the repository's |
| The 4diac IDE's own checks | `runtime/check-project.ps1 -ProjectDir cell/control/FillingModule` | Headless: every type loads and compiles, the system has no broken connection and no overlapping blocks in an application. Expect 0 errors and 0 application collisions; the resource views always report collisions (the IDE draws mapped blocks at their group-relative positions) |

Where the tests are: `iec61499-mgmt-py/tests` (protocol, boot files, planner),
`iec61499-skill-lib/tests/test_modgen.py` (the generator and the committed projects),
`aas61499-tools/tests` (`test_modsync*`, `test_modreg*`; `*_live.py` need FORTE), `cell/tests`
(modules live, the example line, the vocabulary), `deploy/tests`. The shared live-test options are
in `conftest.py` at the top.

`test_committed_module_projects_match_the_generator` regenerates every project into a temporary
folder and compares it with the committed one: a change to the generator is committed together
with the regenerated projects.

## 2. Changing the 4diac programs

The projects in `cell/control/` and `iec61499-skill-lib/ModLib` are generated. Do not edit their
XML: change the spec or the generator, regenerate, check.

| To change | Where |
| --- | --- |
| A module's equipment, IO points, skills, parameters, targets (host, board) | `cell/modules/<module>.yaml` (`iec61499-skill-lib/tests/modules/filler.yaml` for the generator's test module); schema in `modgen/spec.py` |
| A library block (module state manager, occupation, skill core, IO blocks, parameter blocks) | `modgen/library.py` (writes ModLib; module projects carry copies) |
| The structure of a module's program (applications, groups, a module level skill's pattern, equipment and skill primitive blocks, start-up) | `modgen/module.py`; the rules it follows are [module-rules.md](module-rules.md) |
| Pin comments | `modgen/pins.py` (a test requires a comment on every pin) |
| Layout | `modgen/layout.py`; XML writing, kept layouts and hidden connections in `modgen/fbxml.py` |

```powershell
cd iec61499-skill-lib; ../.venv/Scripts/python.exe -m modgen     # all projects; or give spec paths
../.venv/Scripts/python.exe -m pytest -q tests/test_modgen.py
cd ..; runtime/check-project.ps1 -ProjectDir cell/control/FillingModule   # and the other projects
```

- **The user's layout.** The user opens the projects from the repository in the 4diac IDE and
  arranges them; the IDE saves into the `.sys` files. Before regenerating, look at `git status`: a
  modified `.sys` is the user's work. Regenerating keeps every position and group size
  (`keep_layout`), gives new blocks a free place (`place_new`) and only spreads what overlaps
  (`make_room`). Anything else the user changed in the IDE (a value, a new block) is not kept:
  compare by content first, and ask. Never lay out an arranged application from scratch.
- **Composite types** (block types with a network inside) are laid out by the same rules; the user
  cannot arrange them in the IDE, so after a change of the rules their positions may be cleared once
  and laid out anew.
- **The IDE's rules that bite:** a group must not share a name with a block, nor in a type with a
  pin; every connection is written hidden (`Visible=false`); ST in FORTE 3.3 has no
  `STRING_TO_UINT`, `FIND` and `LEN` return `ANY_INT` (go through typed `VAR_TEMP` variables), a
  `FOR` counter must be a `VAR_TEMP`, and the IDE treats warnings as failures. `STEP`, `SUB`, `ADD`
  are reserved names.
- **New or changed block types need a new FORTE.** A FORTE only runs programs whose block types it
  was built with:

```powershell
runtime/build-modules.ps1                                     # IDE validation and C++ export, FORTE for Windows (output/bin/forte.exe)
runtime/build-modules.ps1 -Config pi/modules-pi -SkipValidate # FORTE for the Pi (aarch64)
runtime/package-runtime.ps1                                   # the Pi binary into runtime/bin/forte-aarch64 (+ checksum): commit both
```

  The FORTE source is patched (`runtime/forte-patches/*.patch`, a stack applied in order;
  `forte-compat/` holds header shims). The FBE (`C:\4diac-fbe`) takes CMake settings only on a fresh
  cache; `build-runtime.ps1` deletes a stale one. While a running FORTE uses
  `output/bin/forte.exe` (the user's teaching demo), the build cannot replace it: the fresh binary is
  then only in `runtime/fbe/build/modules-win/forte/build/forte/forte.exe`.

## 3. Talking to a FORTE

FORTE listens on the management port 61499 (no authentication, lab network only) and, once a
module runs, on OPC UA port 4840.

**Management protocol** (`iec61499_mgmt`): typed commands, one request at a time.

```python
from iec61499_mgmt.protocol import Client, Command

with Client("192.168.0.203", 61499) as forte:
    fbs = forte.execute(Command(op="query_fbs", resource="RES")).fbs        # every block: Name, Type
    links = forte.execute(Command(op="query_connections", resource="RES")).connections
    src = "Filling_pi.Module.State"
    state = forte.execute(Command(op="read", resource="RES", source=src)).read_value(src)
    # A write changes the running program (here an offered skill's default): only when intended
    forte.execute(Command(op="write", resource="RES", destination="Filling_pi.MoveAxis.Position", value="25.0"))
```

- Operations: `create_fb`, `delete_fb`, `connect`, `disconnect`, `write`, `read`, `start`, `stop`,
  `kill`, `query_fbs`, `query_connections`, `query_type`. An error answer raises `ManagementError`.
- **Names.** A program runs inside its application's container, as the IDE deploys it, so the IDE
  can monitor it: `<Application>.<Block>.<Pin>`. The application is the module's name for the first
  target (`Filling`, on the PC) and `<Module>_<target>` for the others (`Filling_pi`). The
  resource's own block `START` is outside (`START.COLD`). `Command.inside(container)` adds the prefix.
- **A whole program** is a boot file: `load_application(sys_file, app)` (`iec61499_mgmt.sysfile`)
  flattens the application, `deployment(...)` (`iec61499_mgmt.bootfile`) makes the commands (resource,
  blocks inside the container, values, connections, START links, start), `boot_file(commands)` the
  text. `python deploy/pi.py module --spec cell/modules/stoppering.yaml --print` shows one.
- **Do not delete a resource** with a GPIOChip in it (FORTE 3.3 crashes) and do not KILL one that does
  not exist (FORTE shuts down). A program is replaced by a new boot file and a restart of the
  container; changes online go through `modsync`.
- Management STOP/START act on blocks, not on the module's PackML state.

**modsync** (module, spec and AAS in step):

```powershell
python -m modsync pull --host 192.168.0.203            # which module runs there, drift from its spec, its AAS -> aas/
python -m modsync push cell/modules/filling.yaml --target pi --dry-run   # what would change online
python -m modsync verify aas --host 192.168.0.203      # is the module what its AAS describes? (no spec read)
python -m modsync reconfigure http://localhost:8081 --shell FillingModuleAAS --dry-run   # what the AAS wants changed
python -m modsync reconfigure aas --host 192.168.0.203 --record   # apply online, verify, add to the boot file, record
python -m modsync project --host 192.168.0.203         # the 4diac project of what runs -> projects/
python -m modsync watch                                # pull whenever a module comes online or changes
```

`reconfigure` refuses a running or occupied module unless `--force`; it changes values (a step's
constant, a parameter's default or limits) and creates module level skills that are described but
not built. The Python functions behind it (for scripts and the scenario runner, plan step A4) are in
`modsync/desired.py`: `load`, `read`, `differences`, `reconfigure`, `record`, `store`.

**OPC UA**: each module below `/Objects/<Module>`: `Occupation` (Occupy, Release), `Module`
(Reset, Start, Stop, Abort, Clear; State), `Skills/<Skill>` (Start, Stop, Abort, Reset; State,
ErrorID, parameters, results), `Equipment/<Item>`. Occupy with any session string (a UUID) and pass
it to every method; Reset, then Start the module, then skills. Clients: `cell/sim/module_ua.py`
(small, for tests), `modlink` in `iec61499-opcua-hmi` (runs a module from its AAS), the HMI
(`cd iec61499-opcua-hmi; python run.py --aas <AAS file or server> --modules filling`), UaExpert.

## 4. A whole module on this PC

```powershell
python cell/sim/run_module.py cell/modules/filling.yaml --forte runtime/fbe/build/modules-win/forte/build/forte/forte.exe
python cell/sim/run_module.py cell/modules/stoppering.yaml --opcua-port 4841 --mgmt-port 61500 --forte <same>
```

It starts the module's Modbus simulator (`cell/sim/module_sim.py`: the axis, switches, pump and
scale, on ports 1502/1503), FORTE, and deploys the PC target's application; OPC UA at
`opc.tcp://localhost:4840`. `--no-deploy` leaves FORTE empty for a deployment from the IDE. Without
`--forte` it takes `output/bin/forte.exe`, which is older than the IO blocks of 21 Oct until the
Windows build is installed again (section 2).

## 5. Deploying to a Raspberry Pi

A fresh Pi (64-bit Raspberry Pi OS or Ubuntu) is set up once, on the Pi, by a user with sudo:
`curl -fsSL https://raw.githubusercontent.com/AAUSmartProductionLab/iec61499-mgmt-py/main/runtime/install.sh | bash`
(Docker, FORTE from `runtime/bin/forte-aarch64` in a container that restarts after a reboot, the
GPIO chip, the PWM overlay, `fake-hwclock`). Then from this PC, with this PC's SSH key:

```powershell
python deploy/pi.py install --spec cell/modules/stoppering.yaml --forte runtime/bin/forte-aarch64   # new FORTE into ~/forte, container rebuilt
python deploy/pi.py module --spec cell/modules/stoppering.yaml   # the program as boot file, container restarted
python deploy/pi.py status | log | stop | start --spec ...       # the container
python -m modsync pull --host 192.168.0.134                      # check what runs
```

- `pi.py` takes the Pi's address and login from the spec's `pi` target (`--host`, `--user` override
  it); **without `--spec` it uses the filling module**.
- On the Pi: `cd ~/forte && docker compose ps | logs -f`; the program is `~/forte/boot/forte.fboot`;
  keep a copy before replacing it (`forte.fboot.before-<what>`).
- A Raspberry Pi 5 numbers the PWM channels differently (GPIO18 is channel 2): the target says
  `board: pi5`. GPIO is `/dev/gpiochip0` on the current kernels.
- After a deployment the module is Stopped and free. **Occupy and Reset, Home and every skill move
  the axis: only with the user at the bench and their go.**
- sudo on a Pi needs a password the user gives when needed; it is never written to a file.

## 6. The AASs: building, checking, publishing

The AASs are built with the lab's pydantic model `aas-model` (submodule, installed by the
`registration` extra). A **profile** is the pydantic dump of an aas-model type without what the
type says anyway; it is the only description format (no YAML or JSON format of our own). ARSO
(`ontology/ARSO`) is the blueprint every resource AAS is checked against; it is authoritative and
changed only after asking the user.

| Part | Where |
| --- | --- |
| Types: `ModuleTypeAAS`, `ComponentTypeAAS`, `SystemTypeAAS` (aas-model's `Resource` with ARSO's submodels), the products | `modreg/model.py`, `modreg/product.py` |
| A module's AAS from its spec (and what runs): Nameplate, Hierarchical Structures, Asset Interfaces Description and Mapping Configuration, Skills, Capability Description, Operational Data, Control Configuration | `modreg/profile.py` (`describe`, `describe_all`) |
| The interface of a skill built online | `modreg/offer.py` |
| ARSO's own submodels as templates and classes | `modreg/templates/*.json` and `modreg/generated/`, made by `modreg generate` |
| The ontology check | `modreg/ontology.py` |
| The registration service | `modreg/service.py` (`modreg serve`) |
| Where things are: coordinates in Operational Data, a tree of transforms (ARSO 0.13) | `modreg/frames.py` (`where`, `relative`, `chain`, `place`) |
| The planar table and its shuttles, from the planar controller | `modreg/planar.py` (the source `planar`) |

```powershell
python -m modreg profile filling --target pi                         # profiles/ (module and components)
python -m modreg profile filling --target pi --host 192.168.0.203    # ... with what runs
python -m modreg build profiles/FillingModuleAAS.json                # the AAS -> aas/
python -m modreg check profiles/FillingModuleAAS.json --ontology ontology/ARSO
python -m modreg generate --ontology ontology/ARSO                   # after an ontology change: templates and classes (commit both)
python -m modreg graph filling --target pi --out filling.ttl         # the AASs as RDF with what they describe (PPRL)
python -m modreg profile planar --host <controller>                  # the planar table, its shuttles and layout, as the controller shows them
python -m modreg profile planar --layout 4x3 --holes "2,1" --shuttles 1,2,3   # ... as given
python -m modreg register planar --host <controller> --service http://<host>:8090 --every 10   # again whenever they change
python -m modsync describe cell/modules/filling.yaml --target pi     # the AASs from the spec alone -> aas/
```

**Capabilities are derived from the skills** (`modreg/derive.py`, the rule in
`ontology/PPRL/derivation`, on the projection in `modreg/projection.py`): a module spec's
`capabilities` state only the facts of the machine; which skill realizes a capability and the
ranges its parameters set follow from the skill types (`ontology/Vocabulary/skills.ttl`) and what
each parameter means (the spec's `meaning`). `modsync record` derives them anew after a build;
`modreg serve` does it on the AAS server for a module (`POST /capabilities/<shell>`), as the skill
editor is to after saving. The service also checks and plans for the editor (`POST /check/<shell>`,
with a flow not saved yet in the body if wanted, and `POST /plan/<shell>`; `modplan` underneath). A new primitive type: add it to `skills.ttl` with the capability it
contributes (a test fails otherwise).

**A new submodel or element**: ARSO first (ask), then `modreg generate`, then the profile code
(`modreg/profile.py`), then the readers (`modsync/desired.py`, and `modlink` in the HMI submodule if
it uses it), then `docs/aas-models.md`. Tests: `aas61499-tools/tests/test_modreg_*.py` (a test fails
when the templates no longer match the ontology) and `cell/tests/test_example_line.py`.

**Publishing.** The local AAS server is the planner's Docker stack on this PC (`ps-*` containers:
AAS environment `http://localhost:8081`, web UI `http://localhost:3000`); it also holds the
planner's demo data, which is not ours to change.

```powershell
python cell/examples/example_line.py --out aas --publish http://localhost:8081   # the example line's AASs (created or replaced)
python cell/examples/describe.py                                                 # docs/aas-examples.md from them
python -m modreg serve --ontology ontology/ARSO --basyx http://localhost:8081   # the registration service on :8090
python -m modsync pull --host 192.168.0.203 --register http://localhost:8090    # a running module's AAS through it
```

`modsync reconfigure http://localhost:8081 ... --record` writes the changed submodels back to the
server. **The lab's AAS server is never published to without the user's go**: the same ids would
overwrite the shells the lab's stations use.

## 7. Planning new skills (modplan)

`modplan` (in `aas61499-tools/`, the `planning` extra: GTPyhop) reads a module's AAS and plans new
module level skills from its Capability Description ([skill-planning.md](skill-planning.md),
[tools.md](tools.md), section 5). Its argument is what modsync takes: a folder of AAS files or an AAS
server.

```powershell
python -m modplan domain aas/                         # what the planner reads: capabilities, constraints, the rest state
python -m modplan check aas/                          # every module level skill through the states (exit 1 on a finding)
python -m modplan discover aas/                       # the process capabilities the module can carry out
python -m modplan plan aas/ --capability Filling --value FillVolume=2.0 --result FillWeight --name FillTwo --write
python -m modsync reconfigure aas/ --host <FORTE> --port 61499   # then build what was planned, online
```

**A new kind of primitive** gets its capability in the vocabulary: `lab:realizes` on its type in
`ontology/Vocabulary/skills.ttl`, and the capability's `pprl:pre`, `pprl:post` and `pprl:invariant` in
`capabilities.ttl` (`tests/test_modplan_vocabulary.py` fails otherwise). **What holds on one module
only** (the needle in the vial while dosing) is the `capability` of the skill in the module's spec:
`values`, `precondition`, `postcondition`, `invariant`, with `<Item>.<meaning>` for another item's
state. Tests: `aas61499-tools/tests/test_modplan*.py`; on FORTE `test_modplan_live.py` (with
`--module-forte-exe`).
