# iec61499-aas-reconfig

AAS-driven online reconfiguration of IEC 61499 devices: modules (filling, stoppering) run as
Eclipse 4diac FORTE programs on Raspberry Pis, are described by their Asset Administration
Shells, and are reconfigured from product, process and resource models.

Each top-level folder is a future repository; for now they share this one, with one Python
project (`pyproject.toml`) for the three packages. Plans, design notes and the ontologies used
as the design guide are working documents kept outside the repository; proper documentation
follows once everything is finalised.

## Map

| Folder | Future repository | What |
| --- | --- | --- |
| `iec61499-mgmt-py/` | iec61499-mgmt-py | `iec61499_mgmt`: FORTE management library (typed commands, client, networks and plans, `.sys` flattening, boot files, type library, read-back verification) |
| `iec61499-skill-lib/` | iec61499-skill-lib | `modgen`: generator from module specs to 4diac projects; `ModLib`: the generated module library (occupation, PackML module state manager, skill state machine, composite control, IO primitives for sim, GPIO, PWM, Modbus); `stdtypes`: IDE declarations of standard FBs |
| `aas61499-tools/` | aas61499-tools | `modsync`: module ⇄ spec ⇄ AAS (read what runs, report drift, describe as AAS, push changes) |
| `runtime/` | runtime | FORTE build: FBE configurations (PC, Pi), FORTE patches (IO handle fix, sysfs PWM module), header shims, IDE validation and export (`validate.ps1`), `build-modules.ps1`, `build-runtime.ps1` |
| `deploy/` | deploy | Raspberry Pi: FORTE in Docker (`pi/`), install and deployment (`pi.py`) |
| `cell/` | the filling line | `modules/`: module specs; `control/`: generated 4diac projects (FillingModule, StopperingModule, FillerModule); `sim/`: Modbus simulator, `run_module.py`, OPC UA client |

Each folder has its own `tests/`; `conftest.py` at the top holds the shared live-test options.

Local only, not committed: `AAS_Builder/` (the lab's AAS builder, lives in the lab
repository), `arduino_cpp_examples/` (the ESP32 station code the modules were ported from),
`docs/`, `ontology/` and the plan (working documents).

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

In the 4diac IDE (a workspace outside the repository), import `iec61499-skill-lib/ModLib` and
the projects in `cell/control/` without copying them.

Live tests start their own FORTE on free local ports and stop it afterwards; without the
FORTE options they are skipped. `cell/tests/test_module_live.py` also runs against a Pi
(`--pi-host`, `--sim-host`); `deploy/tests/test_pwm_emulated.py` runs the Pi binary under
arm64 emulation (`--pi-forte-exe`).
