# iec61499-aas-reconfig

AAS-driven online reconfiguration of IEC 61499 devices: modules (filling, stoppering) run as
Eclipse 4diac FORTE programs on Raspberry Pis, are described by their Asset Administration
Shells, and are reconfigured from product, process and resource models.

The work is part of AASPIRE (AAS-based Planning, Integration, Reconfiguration and Execution), the
framework of the AP2030 project. Its plan, [docs/framework-plan.md](docs/framework-plan.md) (31 Oct
2026), puts every part into one GitHub organization, `ap2030-project`, with `aaspire` as the main
repository; this repository becomes the line's, `aseptic-line`. Nothing is split yet: the top-level
folders share this repository, with one Python project (`pyproject.toml`) for the six packages, and
the map says which repository each folder goes to. The files in `docs/` are working documents
(notes, plans, learnings), in the repository so they can be shared between computers; they are not
finished documentation. The working notes go with the line, the rest is rewritten for the
framework's documentation site. `ontology/` (the product, process and resource ontologies; ARSO is
what `modreg` generates classes from and checks every resource AAS against) becomes the
`ontologies` repository.

## Map

| Folder | Future repository | What |
| --- | --- | --- |
| `iec61499-mgmt-py/` | iec61499-mgmt-py | `iec61499_mgmt`: FORTE management library (typed commands, client, networks and plans, `.sys` flattening, boot files, type library, read-back verification) |
| `iec61499-skill-lib/` | iec61499-skill-lib (`modgen.spec`: skill-model) | `modgen`: generator from module specs to 4diac projects; `ModLib`: the generated module library (occupation, PackML module state manager, skill state machine, composite control, IO primitives for sim, GPIO, PWM, Modbus); `stdtypes`: IDE declarations of standard FBs; `tests/modules`, `tests/control`: the generator's own small test module (`filler`), built into FORTE with the others |
| `aas61499-tools/` | modsync, modplan, registration-service (`modreg`); skill-model (what every tool shares) | `modsync`: module ⇄ spec ⇄ AAS (read what runs, report drift, describe as AAS, push changes; `verify` and `reconfigure`: the module against its AAS as the desired state, without a spec); `modreg`: a module's profile on the lab's shared AAS model, the ontology check and the registration service (with discovery: `serve --discover`); `modplan`: a new skill planned from a module's Capability Description (HTN; PDDL and HDDL for standard planners) |
| `runtime/` | forte-runtime (`install.sh`, `kit/`: deploy-module) | FORTE build: FBE configurations (PC, Pi), FORTE patches (IO handle fix, sysfs PWM module, stand-ins for GPIOChip and PWMChip where FORTE has no GPIO), header shims, IDE validation and export (`validate.ps1`), the IDE's checks alone (`check-project.ps1`), `build-modules.ps1`, `build-runtime.ps1`; the Pi's FORTE built and packaged (`build-pi.ps1`) and put on a Pi that runs FORTE already (`update-pi.ps1`); the Pi's installer (`install.sh`); a kit for building FORTE with one's own block types (`make-kit.ps1`, `build-project.ps1`, `kit/`) |
| `deploy/` | deploy-server (`aas/`), deploy-module (`pi/`, `pi.py`) | Raspberry Pi: FORTE in Docker and the module's manifest beside it (`pi/`), install and deployment (`pi.py`), a bench test of a stepper driver without FORTE (`steptest.py`); the lab's AAS stack on a PC (`aas/compose.yaml`, `aas.py`): BaSyx, the DMP, InfluxDB, Mosquitto, Prosody (XMPP, for the agents) |
| `module-py/` | module-py | `modpy`: a module run in Python from its spec (the robot modules, `cell/modules/python`), with the module rules' state machines, served over OPC UA node for node as a generated module on FORTE; the robots simulated until their driver is chosen |
| `line-agents/` | lineagents | `lineagents`: the line's agents (SPADE over XMPP, the I4.0 language of VDI/VDE 2193): a resource agent per module and per shuttle that bids for steps and carries them out (over OPC UA with modlink or through the DMP, reconfiguring a described skill first), an order agent that starts a product agent per unit ordered, the manager that starts an agent for each module the AAS server holds |
| `cell/` | aseptic-line | `modules/`: module specs (`planned/`: inspection, described but not built; `python/`: loading and unloading, run by modpy); `control/`: generated 4diac projects (FillingModule, StopperingModule, CappingModule); `sim/`: Modbus simulator, `run_module.py`, OPC UA client; `examples/`: the example line's AASs (the line, the planar table and its shuttles, the four modules and their components, three products and the process of each), built, checked and published by `example_line.py`; `eval/`: the paper's evaluation (each change online and by a restart, the planners timed, the figures) |
| `aas-model/` | aas-model (submodule) | The lab's shared pydantic AAS model, here the user's fork on branch `lab-ppr-models` (the lab's types and ARSO's submodels) until its pull request is merged; `modreg` builds on it and uses its generator |
| `aas-camel-dmp/` | aas-camel-dmp (submodule) | The data-mapping processor (Java, Apache Camel): runs the mappings of the published AASs, so an Operation calls a module's OPC UA method and the module's values are written to InfluxDB; built into the AAS stack's `dmp` image |
| `iec61499-opcua-hmi/` | modlink (submodule; the HMI repository is then archived) | `modlink` (runs a module from its AAS over OPC UA), the HMI, an OPC UA stand-in for a module, the Linux FORTE build, the end-to-end test; here so both can change together. Its tests run in its own folder, not with this repository's |
| `basyx-aas-web-ui/` | basyx-aas-web-ui (submodule) | The user's fork of the BaSyx AAS web UI, branch `feat/process-sequence-pharma`: the process sequence planner and the skill editor (`aas-web-ui/src/pages/modules/ProcessSequence`; in BPMN notation `ProcessSequenceBpmn`); here so the planner, the editor and the tools can change together |
| `planar-controller/` | planar-controller (submodule) | The Planar Motor table's controller (Python): the table and each xbot over OPC UA, built like the generated modules (occupation, module state, `MoveToPosition`), with a multi-xbot planner. Its tests run in its own folder |
| `ontology/` | ontologies | The product, process, resource and link ontologies with their notes; ARSO is the blueprint of the resource AAS |
| `aaspire/` | aaspire | AASPIRE's documentation site (MkDocs): a page and a draw.io figure per part, by pillar, and how-to pages; `cd aaspire; python -m mkdocs serve` ([aaspire/README.md](aaspire/README.md)) |
| `docs/` | aseptic-line (the working notes); the documentation site | `onboarding.md`: where to start (objective, rules, state, next steps), with every document listed; `framework-plan.md`: AASPIRE, its repositories and what the January demo needs; `tooling.md`: every tool, command and check; `pipeline.md`: from AAS to running code and how it is changed; `ppr-model.md`: the product, process and resource model, its ontologies and applications (figures in `figures/`); `work.md`: what is built, how, learnings; `next-steps.md`: the plan; `agents.md`: the agents' design and plan to the demo; `decisions.md`: what was decided; `aas-models.md`: the product, plan and resource AAS, their submodels and how they connect; `aas-examples.md`: the example line's 24 AASs with class diagrams; `module-rules.md`: the rules a module is built by; `modules.md`: the two modules and what was ported; `archive/`: superseded plans and figures |

Each folder has its own `tests/`; `conftest.py` at the top holds the shared live-test options.

Local only, not committed: `AAS_Builder/` (the lab's AAS builder, lives in the lab
repository) and `arduino_cpp_examples/` (the ESP32 station code the modules were ported from).

## Quick start

```powershell
python -m pip install -e ".[test,registration,opcua,planning,agents]"
python -m pytest -q                                            # offline tests of every folder

python -m modgen                                               # regenerate ModLib and the module projects
runtime/build-modules.ps1                                      # IDE check + export, one FORTE with every module (C:\4diac-fbe)
python -m pytest -q --module-forte-exe runtime/fbe/build/modules-win/forte/build/forte/forte.exe   # + live tests
python cell/sim/run_module.py cell/modules/filling.yaml        # simulator + FORTE + module, OPC UA at opc.tcp://localhost:4840

runtime/build-pi.ps1                                           # FORTE for the Raspberry Pi (aarch64), see docs/forte-for-the-pi.md
python deploy/pi.py install                                    # FORTE in Docker on the Pi of cell/modules/filling.yaml
python deploy/pi.py module                                     # run the module on its Pi (--spec cell/modules/stoppering.yaml: the other Pi)
python -m modsync pull --host 192.168.0.134                    # which module runs there, drift from its spec, its AAS
python -m modsync project --host 192.168.0.203                 # a 4diac IDE project of what runs there (projects/)
```

## Install on a Raspberry Pi

A fresh Raspberry Pi 4 or 5 with a 64-bit Linux (Raspberry Pi OS, Ubuntu) becomes an IEC 61499
PLC with one command, run on the Pi by a user with sudo:

```bash
curl -fsSL https://raw.githubusercontent.com/AAUSmartProductionLab/iec61499-mgmt-py/main/runtime/install.sh | bash
```

It installs Docker if it is missing, starts FORTE (with the block types of every module) in a
container that comes back after a reboot, gives it the GPIO lines of the 40-pin header and enables
the two hardware PWM channels (GPIO18 and GPIO19; reboot once for them). It also keeps the clock
across restarts (`fake-hwclock`): a Pi has no battery-backed clock and would start in the past. Afterwards the Pi answers
on the management port 61499, and on OPC UA port 4840 once it runs a program.

A module's program is put on the Pi from the PC (`python deploy/pi.py module`, or `modsync push`
with the Pi's address); the tools themselves are not installed on the Pi.

Running the installer again updates FORTE; the module's program (`~/forte/boot/forte.fboot`) is
kept. It takes FORTE from this repository (`runtime/bin/forte-aarch64`, with its
checksum), or from next to it. A Pi can only run a program whose block types its FORTE was built
with, so after a change of block types: build and package (`runtime/build-pi.ps1`), commit, and run
the installer on the Pi again. Settings are listed at the top of the script. For a Pi without
internet, the FORTE kit (`runtime/make-kit.ps1`) carries FORTE, the container files and the base
images, and its `install-pi.ps1` runs the installer over SSH (Docker itself, when missing, still
needs a download).

On a Raspberry Pi 5 the PWM channels have other numbers than on a Pi 4: GPIO18 is channel 2 and
GPIO19 channel 3 of `pwmchip0` (Pi 4: channels 0 and 1). A module description names the channel.

## Registering a module

A module describes itself with a **profile**: its AAS on the lab's shared pydantic model
([aas-model](https://github.com/tristan-schwoerer/aas-model)) without what its type says anyway.
The types are aas-model's `Module`, `Component` and `ProductionSystem`: its `Resource` with the
resource ontology's Skills and aas-model's Variables (here from the user's fork, branch
`lab-ppr-models`, until its pull request is merged). The registration service reads the profile into
the model, builds the AAS from it, checks the AAS against the ontology and publishes it to an AAS
server. It also takes the plain `Resource` export of the lab's MQTT stations that aas-model
authors.

```powershell
python -m pip install -e ".[registration]"                     # aas-model, BaSyx SDK 2.1, rdflib
modreg profile filling --target pi                             # profiles/FillingModuleAAS.json, from the spec
modreg check filling --target pi --ontology ontology/ARSO      # does its AAS follow the ontology?
modreg serve --ontology ontology/ARSO --basyx http://<host>:8081   # the service, on port 8090
modreg register filling --target pi --service http://<host>:8090   # send the profile to it
modsync pull --host 192.168.0.203 --register http://<host>:8090    # ... or with what runs on the module
```

`--register` works with `modsync describe`, `pull`, `push` and `watch` (a module is registered
when it comes online or changes). The service keeps each profile and AAS in its `--store`
folder; a profile registered again unchanged is not published again. A broken restriction of the
ontology refuses the registration; `--strict` also refuses what the ontology does not describe.
`modreg/model.py` names the types a profile may be of (`TYPES`; the names of before 28 Oct, such
as `ModuleTypeAAS`, still read the profiles written then); the plain `Resource` export of the lab's
own stations goes through the same service.
Nameplate, Hierarchical Structures, interface description, mapping configuration and Variables are
aas-model's classes. The ontology's own submodels (Skills, Parameters, Control Configuration) have
no IDTA template, so their classes are made the way aas-model makes its own:

```powershell
git submodule update --init aas-model                          # the aas-model checkout (not --recursive)
modreg generate --ontology ontology/ARSO                       # ontology -> aas-model/templates/arso/*.json -> aas-model's classes
```

`modreg generate` writes a submodel template per submodel from what the ontology states (element
types, idShorts, semanticIds, cardinalities) into aas-model's `templates/arso` and has aas-model's
generator (`aas-model/scripts/lab_generate.py`) make the pydantic classes from it
(`aas_model.submodel_templates.arso`). Both are committed in aas-model; a test fails when they no
longer match the ontology. The submodule is at the commit the `registration` extra installs.
aas-model loads its message schemas from the lab's GitHub pages when it is imported, unless
`MQTT_SCHEMAS_DIR` names a local copy.

A product and its process are described with aas-model's `Product` (a Nameplate, the bill of
material, Process Parameters (IDTA 02031-1), the required capabilities (Capability Description)
and the recipe, the Production Sequence of the lab's process planner) and `Process` (the recipe
bound to a line's modules and skills, and the plan check's result). The example line's are written
out in Python (`cell/examples/products`, `cell/examples/processes`); `example_line.py` builds them
with the line, the planar table and the modules, checks every process and publishes them:

```powershell
python cell/examples/example_line.py --out aas --publish http://<host>:8081   # every AAS of the example line, each process checked
modreg build profiles/FillingModuleAAS.json                    # the AAS of any profile (aas/)
```

The templates of Process Parameters, Production Sequence and the process AAS's submodels are
aas-model's own (`templates/product`, `templates/process`); `modreg generate` has their classes made
again with ARSO's.

In the 4diac IDE (a workspace outside the repository), import `iec61499-skill-lib/ModLib` and
the projects in `cell/control/` (and `iec61499-skill-lib/tests/control/`) without copying them.

Live tests start their own FORTE on free local ports and stop it afterwards; without the
FORTE options they are skipped. `cell/tests/test_module_live.py` also runs against a Pi
(`--pi-host`, `--sim-host`); `deploy/tests/test_pwm_emulated.py` runs the Pi binary under
arm64 emulation (`--pi-forte-exe`).
