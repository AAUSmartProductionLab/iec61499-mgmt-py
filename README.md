# iec61499-aas-reconfig

AAS-driven online reconfiguration of IEC 61499 devices: modules (filling, stoppering) run as
Eclipse 4diac FORTE programs on Raspberry Pis, are described by their Asset Administration
Shells, and are reconfigured from product, process and resource models. All components share
this repository for now; each moves to its own repository once its interface is stable.
Plans, design notes and the ontologies used as the design guide are working documents kept
outside the repository; proper documentation follows once everything is finalised.

## Map

**Current: generated modules** (since 28 Sep 2026)

| Path | What |
| --- | --- |
| `modules/*.yaml` | Module specifications: equipment IO, skill primitives, module level skills, procedures, targets (PC with a simulator, Pi with GPIO/PWM) |
| `modgen/` | Generator: module spec → 4diac project (`python -m modgen`) |
| `4diac/ModLib`, `4diac/FillingModule`, `4diac/StopperingModule`, `4diac/FillerModule` | Generated 4diac projects (the `.sys` keeps layouts arranged in the IDE) |
| `modsync/` | Module ⇄ spec ⇄ AAS: read what runs on a module, report drift, write its AAS, push changes (`python -m modsync`) |
| `4diac/tools/` | FORTE build (`build-modules.ps1`, `build-runtime.ps1`, FORTE patches incl. the sysfs PWM module), Pi deployment (`pi.py`, `pi/`), module simulator (`module_sim.py`, `run_module.py`) |
| `iec61499_mgmt/` | FORTE management library: typed commands, client, `.sys` flattening, boot files, read-back verification, type library, guarded changeover |

**Legacy: the filling cell of the first iteration** (kept until the module stack covers its
experiments)

| Path | What |
| --- | --- |
| `4diac/FillingCellFixed`, `4diac/tools/generate_filling_cell.py` | `SK_*` skill composites with PackML, gate and contract blocks, pattern FBs, the OPC UA driven cell |
| `skill_compiler/`, `examples/` | BPMN compiler (sequences, loops), contract forward check, mutation study; the cell's processes, bindings and products A–E |

Local only, not committed: `AAS_Builder/` (the lab's AAS builder, lives in the lab
repository), `arduino_cpp_examples/` (the ESP32 station code the modules were ported from),
`docs/`, `ontology/` and the plan (working documents).

## Quick start

```powershell
python -m pip install -e ".[test]"
python -m pytest tests -q                                  # offline tests

python -m modgen                                           # regenerate ModLib and the module projects
4diac/tools/build-modules.ps1                              # IDE check + export, one FORTE with every module (C:\4diac-fbe)
python -m pytest tests -q --module-forte-exe 4diac/tools/fbe/build/modules-win/output/bin/forte.exe   # + live module tests
python 4diac/tools/run_module.py modules/filling.yaml      # simulator + FORTE + module, OPC UA at opc.tcp://localhost:4840

4diac/tools/build-modules.ps1 -Config pi/modules-pi -SkipValidate   # FORTE for the Raspberry Pi (aarch64)
python 4diac/tools/pi.py install                           # FORTE in Docker on the Pi of modules/filling.yaml
python 4diac/tools/pi.py module                            # run the module on its Pi
python -m modsync pull --host 192.168.0.191                # which module runs there, drift from its spec, its AAS
```

In the 4diac IDE (a workspace outside the repository), import the module projects without
copying them. The legacy cell: `python 4diac/tools/generate_filling_cell.py`,
`4diac/tools/build-runtime.ps1`, live tests with `--forte-exe`.

Live tests start their own FORTE on free local ports and stop it afterwards; without the
FORTE options they are skipped. `tests/test_module_live.py` also runs against a Pi
(`--pi-host`, `--sim-host`).
