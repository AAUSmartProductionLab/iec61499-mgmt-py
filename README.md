# iec61499-aas-reconfig

AAS-driven online reconfiguration of IEC 61499 devices. This repository holds all components
for now; each will move to its own repository once its interface is stable (see
[the build plan](AAS-driven%20online%20reconfiguration%20of%20IEC%2061499%20devices%20build%20and%20modelling%20plan.md)).

## iec61499-mgmt-py

Validated JSON network models and deterministic FORTE management plans, plus an
experimental BPMN skill compiler. Read [the modelling and implementation design](docs/design.md)
for the division between operator intent, skill descriptions and runtime wiring.

The first working slice supports sequential BPMN tasks, named skill parameters,
full desired networks and patches. The CLI works offline. Production occupation,
contract checking, live reconciliation, boot persistence and AAS integration are
not implemented yet. Example target types/hashes are illustrative.

```powershell
python -m pip install -e ".[test]"
python -m pytest -q
python -m iec61499_mgmt compile examples/fill.bpmn --bindings examples/bindings.json --target examples/target.json --product examples/product.json --out compilation.json --network-out network.json
python -m iec61499_mgmt plan --current examples/empty-network.json --desired network.json --target examples/target.json --out plan.json
python -m iec61499_mgmt schema patch --out patch.schema.json
```

`compilation.json` contains the procedure IR, draft composite-skill description
and generated network. `plan.json` contains preflight queries, ordered mutations
and read-back queries; emitting queries is not verification of a live runtime.

```python
from iec61499_mgmt import Network, NetworkPatch, TypeLibrary, plan

current = Network.model_validate_json(current_json)
desired = Network.model_validate_json(desired_json)
# Alternatively:
# desired = NetworkPatch.model_validate_json(patch_json).apply(current)
commands = plan(current, desired, TypeLibrary.model_validate_json(types_json))
print(commands.model_dump_json(indent=2))
```

A parameter patch names its instance and parameter, with a required base-network
hash from `current.digest()`:

```json
{
  "base_hash": "<64-character SHA-256 from current.digest()>",
  "operations": [
    {"op": "set_parameter", "instance": "PROC.b_446f7365", "parameter": "P1",
     "value": {"type": "LREAL", "value": 1.0}}
  ]
}
```

The low-level client can execute individual typed commands:

```python
from iec61499_mgmt.protocol import Client, Command

with Client("127.0.0.1") as client:
    response = client.execute(Command(op="query_fbs", resource="RES"))
    print(response.fbs)
```

Mutations require the caller to implement the changeover guard and occupation
protocol described in the design. Management START/STOP are FB lifecycle
operations, distinct from PackML skill commands.

Standard FORTE types report empty per-type hashes. The library accepts these only
with `runtime_binary_sha256` in the type manifest, carries that requirement into the
plan, and provides `library.verify_executable(path)` for local build verification.
Protocol response fixtures captured from FORTE 3 are in `tests/fixtures/forte3-responses.json`.

## Filling-cell skill blocks (4diac types)

The 4diac project in `4diac/FillingCellFixed` is generated. Primitive skills are
composite FBs built from a shared PackML state machine, a command gate, a per-skill
contract block, IO primitives (simulated, GPIO or Modbus) and an OPC UA facade with one
method per PackML command. Procedures are networks of pattern FBs (`P_Call`, `P_Loop`,
`P_Choice`, `P_Fork`, `P_Join`, `P_Wait`) in `PROC`. See [skill-blocks.md](docs/skill-blocks.md).

The library also builds `types.json` from a running build (`types`), writes FORTE boot files
(`boot`) and checks a live resource against the expected network (`iec61499_mgmt.verify`).
`iec61499_mgmt.changeover` applies a change only while the unit is occupied and quiescent, and
`skill_compiler.contracts` forward-checks a procedure against the skill contracts. The
filling-cell processes, bindings and products A–E are in `examples/cell`:

```powershell
python -m iec61499_mgmt compile examples/cell/fill-v2.bpmn --bindings examples/cell/bindings-v2.json --target examples/cell/target-template.json --library types.json --product examples/cell/product-C.json --out compilation.json --network-out network.json
```

```powershell
python 4diac/tools/generate_filling_cell.py
4diac/tools/build-runtime.ps1      # IDE check + export, then FORTE via C:\4diac-fbe (OPC UA, Modbus, IO)
python -m pytest tests -q --forte-exe 4diac/tools/fbe/build/fillingcell-win/output/bin/forte.exe
```

The system maps four applications to device `FORTE_PC` for running from the 4diac IDE: the
production cell (OPC UA driven), a self-running demo cell with a plant model, a skill bench and
a pattern demo. See "Running from the 4diac IDE" in [skill-blocks.md](docs/skill-blocks.md).

Live tests start their own FORTE on free localhost ports and terminate it afterwards;
without `--forte-exe` they are skipped. The FBE build is statically linked and needs
no DLL path.
