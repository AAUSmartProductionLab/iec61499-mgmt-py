"""modsync against FORTE: read a deployed module back, push a parameter, respect occupation, pull from the CLI.

    python -m pytest aas61499-tools/tests/test_modsync_live.py --module-forte-exe runtime/fbe/build/modules-win/output/bin/forte.exe
"""
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

from basyx.aas.adapter.json import read_aas_json_file
import pytest

from conftest import free_port, launch_forte
from iec61499_mgmt.bootfile import deployment
from iec61499_mgmt.protocol import Client, Command
from modgen import SPECS, load, specs
from modgen.library import STATES
from modsync import aas
from modsync.compare import Candidate
from modsync.sync import Refused, candidates, inspect, push

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "cell" / "sim"))
from module_sim import ModuleSim, SimServer  # noqa: E402
from module_ua import ModuleUa  # noqa: E402

FILLING = SPECS / "filling.yaml"
DWELL = "Dispensing.Execute.Dwell.Duration"


@pytest.fixture
def module(request, tmp_path):
    """The filling module (pc target) on FORTE with the simulator; the Modbus endpoint is overridden."""
    exe = request.config.getoption("--module-forte-exe")
    if not exe:
        pytest.skip("Pass --module-forte-exe to run modsync against FORTE")
    cand = Candidate(FILLING, load(FILLING), "pc")
    modbus, ua_port = free_port(), free_port()
    endpoint = f":{cand.spec.modbus.port}:"
    overrides = {k: v.replace(endpoint, f":{modbus}:") for k, v in cand.app.parameters.items() if k.endswith("_Modbus")}
    with SimServer(ModuleSim(cand.spec), port=modbus), \
            launch_forte(Path(exe).resolve(strict=True), tmp_path, None, ["-op", str(ua_port)]) as port, \
            Client("127.0.0.1", port) as client:
        for command in deployment(cand.app, overrides=overrides):
            client.execute(command)
        ua = ModuleUa(ua_port, cand.spec.module)
        try:
            ua.expect("Module/State", STATES["Stopped"])
            yield SimpleNamespace(client=client, port=port, overrides=overrides, ua=ua, cand=cand)
        finally:
            ua.close()


def check(m, cands=None):
    return inspect(m.client, "127.0.0.1", m.port, cands or [m.cand], overrides=m.overrides)


def test_a_deployed_module_is_read_back_and_identified(module):
    st = check(module, candidates(specs()))
    assert (st.candidate.spec.module, st.candidate.target, st.distance) == ("Filling", "pc", 0)
    assert st.drift.empty, st.drift.lines()
    assert st.snapshot.fbs == module.cand.app.fbs
    # Exported types carry a hash; FORTE's own standard types (E_RESTART) report none.
    assert all(h.startswith("v2:SHA3-512:") for t, h in st.snapshot.hashes.items() if not t.startswith("iec61499::"))


def test_a_parameter_changed_online_is_reported_described_and_pushed_back(module, tmp_path):
    module.client.execute(Command(op="write", resource="RES", destination=DWELL, value="2.5"))
    st = check(module)
    assert st.drift.values == {DWELL: ("1.0", "2.5")} and not st.drift.restart
    store = aas.build(st.candidate.spec, "pc", st.snapshot, st.drift)
    path = aas.write(store, tmp_path / "aas.json")
    with path.open(encoding="utf-8") as f:
        skills = next(o for o in read_aas_json_file(f, failsafe=False) if o.id_short == "Skills")
    assert skills.get_referable("Dispensing").get_referable("Execute").get_referable("Step02").value == "Dwell(Duration=2.5)"
    done = push(module.client, "127.0.0.1", module.port, module.cand, overrides=module.overrides)
    assert done[0] == f"write {DWELL} := 1.0 (was 2.5)"
    assert check(module).drift.empty


def test_push_leaves_an_occupied_module_alone(module):
    assert module.ua.call("Occupation/Occupy", "orchestrator-1") == [True, 0]
    module.client.execute(Command(op="write", resource="RES", destination=DWELL, value="2.5"))
    with pytest.raises(Refused, match="occupied"):
        push(module.client, "127.0.0.1", module.port, module.cand, overrides=module.overrides)
    assert module.ua.call("Occupation/Release", "orchestrator-1") == [True, 0]
    push(module.client, "127.0.0.1", module.port, module.cand, overrides=module.overrides)
    assert check(module).drift.empty


def test_cli_pull_writes_the_aas(module, tmp_path):
    module.client.close()                # the CLI opens its own management connection
    run = subprocess.run([sys.executable, "-m", "modsync", "pull", "--spec", str(FILLING), "--target", "pc",
                          "--host", "127.0.0.1", "--port", str(module.port), "--out", str(tmp_path)],
                         cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    # The test's Modbus endpoint differs from the spec's: reported as drift, needing a restart.
    assert (f"Filling (21 instances), {len(module.overrides)} differences from cell/modules/filling.yaml target pc"
            in run.stdout)
    with (tmp_path / "FillingModuleAAS.json").open(encoding="utf-8") as f:
        objects = {o.id_short: o for o in read_aas_json_file(f, failsafe=False)}
    assert objects["ControlSoftware"].get_referable("SyncState").value == "Drift"
    assert objects["ControlSoftware"].get_referable("ManagementEndpoint").value == f"127.0.0.1:{module.port}"
