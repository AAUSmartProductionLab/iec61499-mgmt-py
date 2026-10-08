"""modsync offline: compare a running program with its module spec, push changes, describe the module (AAS).

FORTE is replaced by FakeForte, which answers the management requests from a program
(instances, connections, values), the way FORTE 3.3 answers them (tests/test_modsync_live.py).
"""
from pathlib import Path

from basyx.aas import model
from basyx.aas.adapter.json import read_aas_json_file
import pytest
import yaml

from iec61499_mgmt.bootfile import boot_file, deployment
from iec61499_mgmt.protocol import ManagementError, Response
from iec61499_mgmt.sysfile import FlatApplication, load_application
from modgen import SPECS, load, specs, system_file
from modgen.library import STATES
from modgen.module import app_name
from modgen.spec import ModuleSpec
from modsync import aas, sync
from modsync.compare import Candidate, expected, expected_values, same
from modsync.device import literal
from modsync.sync import MODULE_STATE, OCCUPIED, Refused, candidates, inspect, push, watch

FILLING = SPECS / "filling.yaml"


def response(**kw):
    return Response(request_id="1", reason=None, raw="", **{"fbs": [], "connections": [], "types": [], **kw})


class FakeForte:
    """Answers QUERY, READ and WRITE from a program as FORTE would (strings read back unquoted)."""

    def __init__(self, cand: Candidate, state="Stopped", occupied=False, lacking=()):
        app, self.spec = cand.app, cand.spec
        self.fbs = dict(app.fbs)
        self.connections = set(app.event_connections + app.data_connections)
        self.values = {p: literal(v) if v.startswith(("'", '"')) else v
                       for p, v in expected_values(cand.spec, app).items()}
        self.values[MODULE_STATE] = str(STATES[state])
        self.values[OCCUPIED] = "TRUE" if occupied else "FALSE"
        self.lacking = set(lacking)
        self.writes, self.started, self.triggered = [], [], []

    def execute(self, c):
        if c.op == "query_fbs":
            return response(fbs=[{"Name": "START", "Type": "iec61499::events::E_RESTART", "Status": "RUNNING"}]
                            + [{"Name": n, "Type": t, "Status": "RUNNING"} for n, t in self.fbs.items()])
        if c.op == "query_connections":
            return response(connections=[{"Source": s, "Destination": d} for s, d in sorted(self.connections)])
        if c.op == "query_type":
            return response(types=[] if c.type in self.lacking else [{"Name": f"{c.type}#v2:SHA3-512:{len(c.type)}"}])
        if c.op == "read":
            if c.source not in self.values:
                raise ManagementError(Response(request_id="1", reason="NO_SUCH_OBJECT", raw="", fbs=[],
                                               connections=[], types=[]))
            return response(connections=[{"Source": c.source, "Destination": self.values[c.source]}])
        if c.op == "write" and c.value == "$e":
            self.triggered.append(c.destination)
        elif c.op == "write":
            self.writes.append((c.destination, c.value))
            self.values[c.destination] = literal(c.value) if c.value.startswith(("'", '"')) else c.value
        elif c.op == "create_fb":
            self.fbs[c.name] = c.type
            # FORTE starts an instance with its type's initial values, here the skills' parameter defaults.
            self.values.update(expected_values(self.spec, FlatApplication(fbs={c.name: c.type})))
        elif c.op == "connect":
            self.connections.add((c.source, c.destination))
        elif c.op == "disconnect":
            self.connections.remove((c.source, c.destination))
        elif c.op == "start":
            self.started.append(c.name)
        else:
            raise AssertionError(c.op)
        return response()

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class Recorder:
    """A deployer that keeps the boot files it was given."""

    def __init__(self):
        self.saved, self.restarted = [], []

    def save(self, boot):
        self.saved.append(boot)

    def restart(self, boot):
        self.restarted.append(boot)


def filling(target="pi") -> Candidate:
    return Candidate(FILLING, load(FILLING), target)


# A new module level skill composed of the filling module's primitives: two doses.
DOUBLE_DOSE = {"description": "Needle down, two doses, needle up, weigh",
               "parameters": {"Dose": {"unit": "mL", "minimum": 0.5, "maximum": 10.0, "default": 0.5}},
               "execute": ["MoveNeedleDown", {"Dispense": {"Volume": "Dose", "FlowRate": 1.0}},
                           {"Dispense": {"Volume": "Dose", "FlowRate": 1.0}}, "MoveNeedleUp", "Weigh"],
               "stop": ["MoveNeedleUp"], "results": {"Weight": "Weigh.Weight"}}


def composed(target="pi", first=False) -> Candidate:
    """The filling module with DoubleDose added (``first``: before Dispensing, else after it)."""
    data = yaml.safe_load(FILLING.read_text(encoding="utf-8"))
    new = {"DoubleDose": DOUBLE_DOSE}
    data["composites"] = {**new, **data["composites"]} if first else {**data["composites"], **new}
    return Candidate(FILLING, ModuleSpec.model_validate(data), target)


def status(forte, cands=None):
    return inspect(forte, "pi", 61499, cands or candidates(specs()))


@pytest.mark.parametrize("path", specs(), ids=lambda p: p.stem)
def test_the_compared_program_is_what_the_projects_deploy(path):
    spec = load(path)
    for target in spec.targets:
        sys_app = load_application(system_file(spec.project), app_name(spec, target))
        app = expected(spec, target)
        assert (sys_app.fbs, sys_app.parameters) == (app.fbs, app.parameters)
        assert set(sys_app.event_connections + sys_app.data_connections) == set(app.event_connections + app.data_connections)


def test_values_compare_as_iec_values():
    assert same('"Filling"', "Filling") and same("'NeedleAxis_Up'", "NeedleAxis_Up")
    assert same("T#1s", "T#1000ms") and same("LREAL#1.0", "1") and same("TRUE", "TRUE")
    assert not same("1.0", "2.5") and not same("TRUE", "FALSE") and not same("T#1s", "T#2s")


def test_a_module_running_its_spec_is_identified_and_in_sync():
    st = status(FakeForte(filling("pi")))
    assert (st.candidate.spec.module, st.candidate.target, st.distance) == ("Filling", "pi", 0)
    assert st.identified and st.drift.empty, st.drift.lines()
    assert "START" not in st.snapshot.fbs                       # the resource's own block
    assert st.snapshot.hashes["filling::SK_Dispense"].startswith("v2:SHA3-512:")


def test_other_programs_are_not_taken_for_a_module():
    forte = FakeForte(filling())
    forte.values["Occupation.Module"] = "Capping"
    st = status(forte)
    assert not st.identified and "module Capping, which no module spec here describes" in st.summary()
    forte.fbs = {"Led": "eclipse4diac::io::gpiochip::GPIOChip", "Toggle": "iec61499::events::E_SWITCH"}   # pi.py blink
    forte.connections, forte.values = set(), {}
    st = status(forte)
    assert not st.identified and "not a generated module (2 instances: Led, Toggle)" in st.summary()


def test_a_changed_skill_parameter_is_drift_pushed_online_and_saved():
    forte = FakeForte(filling())
    forte.values["Dispensing.Execute.Dispense.FlowRate"] = "2.5"
    st = status(forte)
    assert st.drift.values == {"Dispensing.Execute.Dispense.FlowRate": ("1.0", "2.5")}
    assert not st.drift.restart
    deployer = Recorder()
    done = push(forte, "pi", 61499, filling(), deployer)
    assert forte.writes == [("Dispensing.Execute.Dispense.FlowRate", "1.0")]
    assert deployer.saved == [boot_file(deployment(filling().app))] and not deployer.restarted
    assert "boot file saved" in done
    assert status(forte).drift.empty


def test_values_read_at_init_and_structure_need_a_restart():
    forte = FakeForte(filling())
    forte.values["MoveNeedleUp.UaPath"] = "/Skills/Other"
    assert status(forte).drift.restart and not status(forte).drift.structural
    forte.connections.discard(("Dispensing.Execute.Dispense.SUCCESS", "Dispensing.Execute.MoveNeedleUp.START"))
    drift = status(forte).drift
    assert drift.structural
    assert drift.missing_connections == [("Dispensing.Execute.Dispense.SUCCESS", "Dispensing.Execute.MoveNeedleUp.START")]
    with pytest.raises(Refused, match="deployer"):
        push(forte, "pi", 61499, filling())
    assert push(forte, "pi", 61499, filling(), dry_run=True)[0].startswith("redeploy: ")
    deployer = Recorder()
    push(forte, "pi", 61499, filling(), deployer)
    assert deployer.restarted == [boot_file(deployment(filling().app))] and not forte.writes


@pytest.mark.parametrize("state, occupied", [("Execute", False), ("Idle", True)])
def test_push_leaves_a_busy_module_alone_unless_forced(state, occupied):
    forte = FakeForte(filling(), state=state, occupied=occupied)
    forte.values["Dispensing.Execute.Dispense.FlowRate"] = "2.5"
    with pytest.raises(Refused, match="stop and release"):
        push(forte, "pi", 61499, filling(), Recorder())
    assert not forte.writes
    push(forte, "pi", 61499, filling(), Recorder(), force=True)
    assert forte.writes


def test_push_needs_the_types_in_the_runtime():
    forte = FakeForte(filling(), lacking={"filling::SK_AttachNeedle"})      # a type only one instance uses
    del forte.fbs["AttachNeedle"]
    with pytest.raises(Refused, match="rebuild"):
        push(forte, "pi", 61499, filling(), Recorder())


def test_a_new_module_level_skill_is_created_online_while_the_module_runs():
    forte = FakeForte(filling(), state="Execute", occupied=True)          # an orchestrator is working
    new = composed()
    drift = inspect(forte, "pi", 61499, [new]).drift
    assert drift.additive and not drift.restart
    assert all(n.startswith("DoubleDose.") for n in drift.missing)
    deployer = Recorder()
    done = push(forte, "pi", 61499, new, deployer)
    assert forte.fbs == new.app.fbs
    assert forte.connections == set(new.app.event_connections + new.app.data_connections)
    assert set(forte.started) == set(drift.missing)
    assert forte.triggered == ["DoubleDose.Control.INIT"]         # the INIT chain enters there, once
    assert forte.values["DoubleDose.Dose.Default"] == "0.5"
    assert done[0].startswith("create DoubleDose: ") and "initialise from DoubleDose.Control.INIT" in done
    assert "verified by read-back" in done and deployer.saved == [boot_file(deployment(new.app))]
    assert inspect(forte, "pi", 61499, [new]).drift.empty


def test_a_skill_added_before_another_moves_the_init_chain_online():
    forte = FakeForte(filling())
    new = composed(first=True)
    drift = inspect(forte, "pi", 61499, [new]).drift
    assert drift.additive and drift.unexpected_connections == [("Stopping.MoveNeedleUp.INITO", "Dispensing.Control.INIT")]
    done = push(forte, "pi", 61499, new, Recorder())
    assert "1 INIT links moved" in done[0] and forte.triggered == ["DoubleDose.Control.INIT"]


def test_removing_a_module_level_skill_needs_a_restart():
    forte = FakeForte(composed())
    drift = inspect(forte, "pi", 61499, [filling()]).drift
    assert drift.unexpected and not drift.additive and drift.restart
    with pytest.raises(Refused, match="deployer"):
        push(forte, "pi", 61499, filling())


def test_push_deploys_a_module_to_a_forte_without_a_program():
    forte = FakeForte(filling())
    forte.fbs, forte.connections, forte.values = {}, set(), {}            # a fresh install: no resource yet
    deployer = Recorder()
    done = push(forte, "pi", 61499, filling(), deployer)
    assert deployer.restarted == [boot_file(deployment(filling().app))]
    assert done[0].startswith("deploy Filling (target pi): ") and done[1:] == ["boot file replaced, FORTE restarted"]


def test_on_the_modules_own_computer_the_boot_file_is_written_locally(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(sync.subprocess, "run", lambda cmd, cwd, check: calls.append((cmd, cwd)))
    monkeypatch.setattr(sync.socket, "create_connection", lambda *a, **k: open(tmp_path / "x", "w"))
    deployer = sync.LocalDeployer(tmp_path)
    deployer.save("RES;a\n")
    assert (tmp_path / "boot" / "forte.fboot").read_bytes() == b"RES;a\n" and not calls
    deployer.restart("RES;b\n")
    assert (tmp_path / "boot" / "forte.fboot").read_bytes() == b"RES;b\n"
    assert calls == [(["docker", "compose", "restart"], tmp_path)]
    assert sync.is_local("127.0.0.1") and not sync.is_local("192.0.2.1")           # a documentation address


def read_back(store, tmp_path):
    path = aas.write(store, tmp_path / "aas.json")
    with path.open(encoding="utf-8") as f:
        objects = read_aas_json_file(f, failsafe=False)          # strict: every element valid
    return {o.id_short: o for o in objects}


def test_aas_from_the_spec(tmp_path):
    spec = load(FILLING)
    objects = read_back(aas.build(spec, "pi", spec_path="cell/modules/filling.yaml"), tmp_path)
    shell = objects["FillingModuleAAS"]
    assert shell.id == "https://smartproductionlab.aau.dk/aas/FillingModuleAAS"
    assert len(shell.submodel) == 4
    skills = objects["Skills"]
    offered = [n for n, s in spec.skills.items() if s.offered] + list(spec.composites)
    assert [e.id_short for e in skills.submodel_element] == offered
    interface = objects["AssetInterfacesDescription"].get_referable("InterfaceOPCUA")
    assert interface.get_referable("EndpointMetadata").get_referable("base").value == "opc.tcp://192.168.0.191:4840"
    start = interface.get_referable("InteractionMetadata").get_referable("actions").get_referable("Dispensing_Start")
    assert start.get_referable("Forms").get_referable("href").value == "/0:Objects/1:Filling/1:Skills/1:Dispensing/1:Start"
    ref = skills.get_referable("Dispensing").get_referable("InterfaceReference").value
    assert ref.key[-1].value == "Dispensing_Start"
    assert objects["ControlSoftware"].get_referable("SyncState").value == "NotRead"


def test_aas_shows_what_runs_on_the_module(tmp_path):
    forte = FakeForte(filling())
    forte.values["Dispensing.Execute.Dispense.FlowRate"] = "2.5"
    st = status(forte)
    objects = read_back(aas.build(st.candidate.spec, st.candidate.target, st.snapshot, st.drift), tmp_path)
    execute = objects["Skills"].get_referable("Dispensing").get_referable("Execute")
    assert [p.value for p in execute.value] == ["MoveNeedleDown", "Dispense(Volume=Volume, FlowRate=2.5)", "MoveNeedleUp", "Weigh"]
    control = objects["ControlSoftware"]
    assert control.get_referable("SyncState").value == "Drift"
    assert "Dispense.FlowRate = 2.5" in control.get_referable("Differences").get_referable("D001").value
    types = {t.get_referable("Name").value: t.get_referable("Hash").value for t in control.get_referable("Types").value}
    assert types["filling::SK_Dispense"].startswith("v2:SHA3-512:")
    impl = objects["Skills"].get_referable("MoveNeedleUp").get_referable("Implementation")
    assert impl.get_referable("FBType").value == "filling::SK_MoveNeedleUp"


def test_watch_reports_a_module_when_it_comes_online_and_when_it_changes(monkeypatch):
    forte = FakeForte(filling())
    online = iter([False, True, True, True])

    def connect(host, port, timeout):
        if not next(online):
            raise ConnectionRefusedError
        return forte
    monkeypatch.setattr(sync, "Client", connect)
    seen, log = [], []

    def changed(st):
        seen.append(st.drift.size())
        forte.values["Dispensing.Execute.Dispense.FlowRate"] = "3.0"   # changed online after the first report
    watch({("pi", 61499): candidates([FILLING])}, changed, interval=0, rounds=4, log=log.append)
    assert log == ["pi:61499: offline (ConnectionRefusedError)"]
    assert seen == [0, 1]                  # online in sync, then the change; the unchanged round is quiet
