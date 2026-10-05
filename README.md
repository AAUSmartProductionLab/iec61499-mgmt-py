# iec61499-aas-reconfig

AAS-driven online reconfiguration of IEC 61499 devices: modules (filling, stoppering) run as
Eclipse 4diac FORTE programs on Raspberry Pis, are described by their Asset Administration
Shells, and are reconfigured from product, process and resource models.

Each top-level folder is a future repository; for now they share this one, with one Python
project (`pyproject.toml`) for the three packages. `docs/` and the build and modelling plan are
working documents (notes, plans, learnings), in the repository for now so they can be shared
between computers; they are not finished documentation and will be cleaned up or removed. The
ontologies are a working copy kept outside the repository.

## Map

| Folder | Future repository | What |
| --- | --- | --- |
| `iec61499-mgmt-py/` | iec61499-mgmt-py | `iec61499_mgmt`: FORTE management library (typed commands, client, networks and plans, `.sys` flattening, boot files, type library, read-back verification) |
| `iec61499-skill-lib/` | iec61499-skill-lib | `modgen`: generator from module specs to 4diac projects; `ModLib`: the generated module library (occupation, PackML module state manager, skill state machine, composite control, IO primitives for sim, GPIO, PWM, Modbus); `stdtypes`: IDE declarations of standard FBs |
| `aas61499-tools/` | aas61499-tools | `modsync`: module ⇄ spec ⇄ AAS (read what runs, report drift, describe as AAS, push changes); `modreg`: a module's profile on the lab's shared AAS model, the ontology check and the registration service |
| `runtime/` | runtime | FORTE build: FBE configurations (PC, Pi), FORTE patches (IO handle fix, sysfs PWM module), header shims, IDE validation and export (`validate.ps1`), `build-modules.ps1`, `build-runtime.ps1` |
| `deploy/` | deploy | Raspberry Pi: FORTE in Docker (`pi/`), install and deployment (`pi.py`) |
| `cell/` | the filling line | `modules/`: module specs; `control/`: generated 4diac projects (FillingModule, StopperingModule, FillerModule); `sim/`: Modbus simulator, `run_module.py`, OPC UA client |

Each folder has its own `tests/`; `conftest.py` at the top holds the shared live-test options.

Local only, not committed: `AAS_Builder/` (the lab's AAS builder, lives in the lab
repository), `arduino_cpp_examples/` (the ESP32 station code the modules were ported from) and
`ontology/`.

## Quick start

```powershell
python -m pip install -e ".[test]"
python -m pytest -q                                            # offline tests of every folder

python -m modgen                                               # regenerate ModLib and the module projects
runtime/build-modules.ps1                                      # IDE check + export, one FORTE with every module (C:\4diac-fbe)
python -m pytest -q --module-forte-exe runtime/fbe/build/modules-win/output/bin/forte.exe   # + live tests
python cell/sim/run_module.py cell/modules/filling.yaml        # simulator + FORTE + module, OPC UA at opc.tcp://localhost:4840

runtime/build-modules.ps1 -Config pi/modules-pi -SkipValidate  # FORTE for the Raspberry Pi (aarch64)
python deploy/pi.py install                                    # FORTE in Docker on the Pi of cell/modules/filling.yaml
python deploy/pi.py module                                     # run the module on its Pi
python -m modsync pull --host 192.168.0.191                    # which module runs there, drift from its spec, its AAS
```

## Install on a Raspberry Pi

One command each, run on the Pi (64-bit Linux with Docker; the login in the `docker` group):

```bash
# everything: the tools, FORTE in Docker, and the filling module's program
curl -fsSL https://raw.githubusercontent.com/AAUSmartProductionLab/iec61499-mgmt-py/main/deploy/install.sh | bash -s -- filling

# or the parts on their own
curl -fsSL https://raw.githubusercontent.com/AAUSmartProductionLab/iec61499-mgmt-py/main/runtime/install.sh | bash          # FORTE runtime
curl -fsSL https://raw.githubusercontent.com/AAUSmartProductionLab/iec61499-mgmt-py/main/aas61499-tools/install.sh | bash   # modsync, modgen, iec61499
```

Then, on the Pi:

```bash
modsync pull --host localhost                                 # which module runs here, drift from its spec, its AAS
modsync push filling --target pi --host localhost --dry-run   # what would change
modsync push filling --target pi --host localhost             # bring the module to its spec (online where possible)
```

Running an installer again updates it; the module's program (`~/forte/boot/forte.fboot`) is kept.
The runtime installer downloads FORTE as the asset `forte-aarch64` of the latest GitHub release:
publish a new build with `runtime/package-release.ps1` (or set `FORTE_FILE` to a binary copied
to the Pi). Settings are listed at the top of each script.

## Registering a module

A module describes itself with a **profile**: its AAS on the lab's shared pydantic model
([aas-model](https://github.com/tristan-schwoerer/aas-model)) without what its type says anyway.
The registration service reads the profile into the model, builds the AAS from it, checks the
AAS against the ontology and publishes it to an AAS server.

```powershell
python -m pip install -e ".[registration]"                     # aas-model, BaSyx SDK 2.1, rdflib
modreg profile filling --target pi                             # profiles/FillingModuleAAS.json, from the spec
modreg check filling --target pi --ontology ontology/ARSO      # does its AAS follow the ontology?
modreg serve --ontology ontology/ARSO --basyx http://<host>:8081   # the service, on port 8090
modreg register filling --target pi --service http://<host>:8090   # send the profile to it
modsync pull --host 192.168.0.191 --register http://<host>:8090    # ... or with what runs on the module
```

`--register` works with `modsync describe`, `pull`, `push` and `watch` (a module is registered
when it comes online or changes). The service keeps each profile and AAS in its `--store`
folder; a profile registered again unchanged is not published again. A broken restriction of the
ontology refuses the registration; `--strict` also refuses what the ontology does not describe.
`ModuleTypeAAS` (`modreg/model.py`) is a resource in the structure of the resource ontology (ARSO)
for an OPC UA module; profiles of the lab's own `ResourceTypeAAS` go through the same service.
Nameplate, Hierarchical Structures, interface description and mapping configuration are aas-model's
classes. The ontology's own submodels (Skills, Operational Data, Parameters, Control
Configuration) have no IDTA template, so their classes are made the way aas-model makes its own:

```powershell
git submodule update --init aas-model                          # the aas-model checkout (not --recursive)
modreg generate --ontology ontology/ARSO                       # ontology -> modreg/templates/*.json -> modreg/generated/*.py
```

`modreg generate` writes a submodel template per submodel from what the ontology states (element
types, idShorts, semanticIds, cardinalities) and has aas-model's generator
(`aas-model/scripts/idta_generate.py`) make the pydantic classes from it. Both are committed; a
test fails when they no longer match the ontology. The submodule is at the commit the
`registration` extra installs. aas-model loads its message schemas
from the lab's GitHub pages when it is imported, unless `MQTT_SCHEMAS_DIR` names a local copy.

In the 4diac IDE (a workspace outside the repository), import `iec61499-skill-lib/ModLib` and
the projects in `cell/control/` without copying them.

Live tests start their own FORTE on free local ports and stop it afterwards; without the
FORTE options they are skipped. `cell/tests/test_module_live.py` also runs against a Pi
(`--pi-host`, `--sim-host`); `deploy/tests/test_pwm_emulated.py` runs the Pi binary under
arm64 emulation (`--pi-forte-exe`).
