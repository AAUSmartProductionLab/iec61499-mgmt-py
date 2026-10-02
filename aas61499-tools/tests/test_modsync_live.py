"""modsync against FORTE: read a deployed module back, push a parameter, respect occupation, create a module
level skill online, pull from the CLI.

    python -m pytest aas61499-tools/tests/test_modsync_live.py --module-forte-exe runtime/fbe/build/modules-win/output/bin/forte.exe

On a Raspberry Pi instead (FORTE in its container, deploy/pi.py install): the filling module's PC
application runs there, its Modbus IO pointed at the simulator on this machine.

    python -m pytest aas61499-tools/tests/test_modsync_live.py --pi-host 192.168.0.191 --sim-host <this machine>
"""
from contextlib import ExitStack, contextmanager
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace

from basyx.aas.adapter.json import read_aas_json_file
import pytest

from conftest import free_port, launch_forte
from iec61499_mgmt.bootfile import boot_file, deployment
from iec61499_mgmt.protocol import Client, Command
from modgen import SPECS, load, specs
from modgen.library import ERRORS, SKILL_STATES, STATES
from modsync import aas
from modsync.compare import Candidate
from modsync.sync import PiDeployer, Refused, candidates, inspect, push

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "cell" / "sim"))
from module_sim import ModuleSim, SimServer  # noqa: E402
from module_ua import ModuleUa  # noqa: E402
from test_modsync import Recorder, composed  # noqa: E402

FILLING = SPECS / "filling.yaml"
DWELL = "Dispensing.Execute.Dwell.Duration"


@pytest.fixture
def module(request, tmp_path):
    """The filling module (pc target) on FORTE with the simulator; the Modbus endpoint is overridden.

    ``fresh(boot)`` starts a FORTE from a boot file and yields (client, port): here a second FORTE,
    on the Pi the Pi's FORTE restarted with it."""
    cand = Candidate(FILLING, load(FILLING), "pc")
    pi, exe = request.config.getoption("--pi-host"), request.config.getoption("--module-forte-exe")
    if not (pi or exe):
        pytest.skip("Pass --module-forte-exe (or --pi-host and --sim-host) to run modsync against FORTE")
    sim_host = request.config.getoption("--sim-host") if pi else "127.0.0.1"
    if pi and not sim_host:
        pytest.skip("Pass --sim-host (this machine's address as the Pi sees it) with --pi-host")
    modbus = free_port()
    endpoint = f"{cand.spec.modbus.host}:{cand.spec.modbus.port}:"
    overrides = {k: v.replace(endpoint, f"{sim_host}:{modbus}:") for k, v in cand.app.parameters.items()
                 if k.endswith("_Modbus")}
    boot = boot_file(deployment(cand.app, overrides=overrides))
    deployer = PiDeployer(pi, request.config.getoption("--pi-user") or cand.spec.targets["pi"].user) if pi else None

    @contextmanager
    def forte(text, folder):
        """FORTE running the boot file ``text``: yields (management port, OPC UA port)."""
        if pi:
            deployer.restart(text)
            yield 61499, 4840
        else:
            folder.mkdir(exist_ok=True)
            ua_port = free_port()
            with launch_forte(Path(exe).resolve(strict=True), folder, None,
                              ["-f", str(write(folder, text)), "-op", str(ua_port)]) as port:
                yield port, ua_port

    @contextmanager
    def fresh(text):
        with forte(text, tmp_path / "fresh") as (port, _), Client(host, port) as client:
            yield client, port

    host = pi or "127.0.0.1"
    with ExitStack() as stack:
        stack.enter_context(SimServer(ModuleSim(cand.spec), host="0.0.0.0" if pi else "127.0.0.1", port=modbus))
        port, ua_port = stack.enter_context(forte(boot, tmp_path))
        client = stack.enter_context(Client(host, port))
        ua = ModuleUa(ua_port, cand.spec.module, host)
        stack.callback(ua.close)
        ua.expect("Module/State", STATES["Stopped"], timeout=10)
        yield SimpleNamespace(client=client, host=host, port=port, overrides=overrides, ua=ua, cand=cand, fresh=fresh)


def write(folder: Path, boot: str) -> Path:
    path = folder / "forte.fboot"
    path.write_text(boot, encoding="utf-8", newline="\n")
    return path


def loaded(client, host, port, cand, overrides, timeout=10):
    """The module as read once FORTE has loaded its boot file."""
    deadline = time.monotonic() + timeout
    while not (st := inspect(client, host, port, [cand], overrides=overrides)).snapshot.fbs:
        assert time.monotonic() < deadline, "the boot file was not loaded"
        time.sleep(0.2)
    return st


def check(m, cands=None):
    return inspect(m.client, m.host, m.port, cands or [m.cand], overrides=m.overrides)


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
    done = push(module.client, module.host, module.port, module.cand, overrides=module.overrides)
    assert done[0] == f"write {DWELL} := 1.0 (was 2.5)"
    assert check(module).drift.empty


def test_push_leaves_an_occupied_module_alone(module):
    assert module.ua.call("Occupation/Occupy", "orchestrator-1") == [True, 0]
    module.client.execute(Command(op="write", resource="RES", destination=DWELL, value="2.5"))
    with pytest.raises(Refused, match="occupied"):
        push(module.client, module.host, module.port, module.cand, overrides=module.overrides)
    assert module.ua.call("Occupation/Release", "orchestrator-1") == [True, 0]
    push(module.client, module.host, module.port, module.cand, overrides=module.overrides)
    assert check(module).drift.empty


def test_a_new_module_level_skill_is_created_online_while_another_runs(module, tmp_path):
    """The composition change (S1): a module level skill composed of the module's primitives is
    created by management commands while the module runs another skill; FORTE is neither rebuilt
    nor restarted, and the boot file saved afterwards brings up the same program."""
    ua, a, S = module.ua, "orchestrator-1", SKILL_STATES
    DONE = (S["Succeeded"], S["Idle"])          # looked at afterwards, a skill that succeeded may be back in Idle
    assert ua.call("Occupation/Occupy", a) == [True, 0]
    assert ua.call("Module/Reset", a) == [True, 0]
    ua.expect("Module/State", STATES["Idle"], timeout=15)
    assert ua.call("Module/Start", a) == [True, 0]
    ua.expect("Module/State", STATES["Execute"])
    dispensing = ua.record("Skills/Dispensing/State")
    assert ua.call("Skills/Dispensing/Start", a) == [True, 0]
    ua.expect("Skills/Dispensing/State", S["Running"], timeout=1)
    new, deployer = composed("pc"), Recorder()
    done = push(module.client, module.host, module.port, new, deployer, overrides=module.overrides)
    assert done[0].startswith("create DoubleDose: ") and "verified by read-back" in done, done
    # The running skill went on (it may have ended while the new one was created).
    deadline = time.monotonic() + 10
    while S["Succeeded"] not in dispensing and time.monotonic() < deadline:
        time.sleep(0.05)
    assert S["Succeeded"] in dispensing and S["Failed"] not in dispensing, dispensing
    assert ua.value("Skills/DoubleDose/Parameters/Dose") == 0.5
    assert ua.call("Skills/DoubleDose/Start", a, 20.0) == [False, ERRORS["OutOfRange"]]
    assert ua.call("Skills/DoubleDose/Start", a, 0.3) == [True, 0]
    ua.expect("Skills/DoubleDose/State", S["Succeeded"], timeout=10)
    assert ua.value("Skills/DoubleDose/Results/Weight") == pytest.approx(2.0)
    assert ua.value("Skills/DoubleDose/Parameters/Dose") == 0.3
    assert ua.value("Skills/DoubleDose/Execute/Dwell_2/State") in DONE
    # A FORTE started from the saved boot file runs the same program.
    module.client.close()
    with module.fresh(deployer.saved[0]) as (client, port):
        st = loaded(client, module.host, port, new, module.overrides)
        assert st.drift.empty, st.drift.lines()


def test_cli_pull_writes_the_aas(module, tmp_path):
    module.client.close()                # the CLI opens its own management connection
    run = subprocess.run([sys.executable, "-m", "modsync", "pull", "--spec", str(FILLING), "--target", "pc",
                          "--host", module.host, "--port", str(module.port), "--out", str(tmp_path)],
                         cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    # The test's Modbus endpoint differs from the spec's: reported as drift, needing a restart.
    assert (f"Filling ({len(module.cand.app.fbs)} instances), {len(module.overrides)} differences from "
            "cell/modules/filling.yaml target pc" in run.stdout)
    with (tmp_path / "FillingModuleAAS.json").open(encoding="utf-8") as f:
        objects = {o.id_short: o for o in read_aas_json_file(f, failsafe=False)}
    assert objects["ControlSoftware"].get_referable("SyncState").value == "Drift"
    assert objects["ControlSoftware"].get_referable("ManagementEndpoint").value == f"{module.host}:{module.port}"
