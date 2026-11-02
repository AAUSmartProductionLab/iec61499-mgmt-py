# Run a module on a PC

A module running on this PC, its IO simulated: the module's Modbus simulator stands in for the
hardware, FORTE runs the module's program, and the module answers on OPC UA as it would on its Pi.
Windows, with Python 3.11.

## 1. Install

```powershell
git clone --recurse-submodules https://github.com/AAUSmartProductionLab/iec61499-mgmt-py
cd iec61499-mgmt-py
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[test,registration,opcua]"
```

## 2. FORTE for Windows

The module's program needs a FORTE built with its block types: `runtime/build-modules.ps1` builds it
(once the 4diac IDE and the FBE are installed, see [FORTE runtime](../reconfiguration/runtime.md)) into
`runtime/fbe/build/modules-win/output/bin/forte.exe`.

## 3. Start the module

```powershell
.venv/Scripts/python.exe cell/sim/run_module.py cell/modules/filling.yaml
.venv/Scripts/python.exe cell/sim/run_module.py cell/modules/stoppering.yaml --opcua-port 4841 --mgmt-port 61500
```

It starts the simulator, FORTE (`--forte` names another binary) and deploys the PC target's
application. The module answers on `opc.tcp://localhost:4840` until Ctrl+C. `--no-deploy` leaves FORTE
empty, for a deployment from the 4diac IDE.

## 4. Operate it

Every module offers the same OPC UA interface below `/Objects/<Module>`:

| Node | What |
| --- | --- |
| `Occupation/Occupy(Session)`, `Release(Session)` | take and give back the module; the session is any id you choose (a UUID) |
| `Module/Reset`, `Start`, `Stop`, `Abort`, `Clear` `(Session)`; `State` | its PackML state |
| `Skills/<Skill>/Start(Session, parameters...)`, `Stop`, `Abort`, `Reset`; `State`, `ErrorID`, `Results` | a skill |
| `Equipment/<Item>/...` | the equipment's values |

With any OPC UA client (UaExpert): occupy, Reset and Start the module, then start a skill with the
same session id, and watch its `State` turn Succeeded. Or with the HMI, once the module's AAS is on an
AAS server ([register](register.md)): `cd iec61499-opcua-hmi; python run.py --aas http://localhost:8081`.

## 5. Watch it in the 4diac IDE

Import `cell/control/FillingModule` into a 4diac IDE 3.3 workspace without copying it, open the
system, and watch the `Filling` application online on the device at `localhost:61499`: the tools
deploy the program inside the application's container, as the IDE does, so the IDE sees what runs.
