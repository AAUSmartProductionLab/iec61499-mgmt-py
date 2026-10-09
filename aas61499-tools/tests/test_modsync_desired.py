"""modsync offline: the AAS as the desired state of a module. What the AASs of a module and its
components describe is read without the module spec, compared with the running program, and the
program is brought to it online (a constant, a limit, a module level skill that is described but
not built).

The AASs are the ones modreg builds; the program is a FORTE stand-in that answers like one.
"""
import copy

import pytest
import yaml

pytest.importorskip("aas_model")

from modgen import SPECS, library_specs, load, specs                         # noqa: E402
from modgen.spec import ModuleSpec                                           # noqa: E402
from modreg import model, profile as profiles                                # noqa: E402
from modsync import desired                                                  # noqa: E402
from modsync.desired import at, described, instances, read, reconfigure, record, submodel   # noqa: E402
from modsync.structure import stated                                         # noqa: E402
from modsync.sync import Refused                                             # noqa: E402
from iec61499_mgmt.bootfile import boot_file, deployment                     # noqa: E402
from test_modsync import FakeForte, Recorder, composed, filling              # noqa: E402

FILLING = SPECS / "filling.yaml"


def aas(spec: ModuleSpec, target: str = "pi") -> tuple[dict, list[dict]]:
    """The AAS of a module and those of its components, as modreg builds them."""
    module, *components = [model.build(profile) for profile in profiles.describe_all(spec, target)]
    return module, components


def wanting(spec: ModuleSpec, built: dict) -> tuple[dict, list[dict]]:
    """The AASs that describe ``spec`` while their record of what was built is still ``built``'s:
    what an engineer's change to the AAS of a delivered module looks like."""
    module, components = aas(spec)
    module["submodels"] = [submodel(built, "ControlConfiguration") if s["idShort"] == "ControlConfiguration" else s
                           for s in module["submodels"]]
    return module, components


@pytest.fixture(scope="module")
def delivered():
    return aas(load(FILLING))


@pytest.fixture(scope="module")
def with_double_dose(delivered):
    return wanting(composed().spec, delivered[0])


@pytest.mark.parametrize("path", [*specs(), *library_specs()], ids=lambda p: p.stem)
def test_the_aas_describes_what_the_module_spec_states(path):
    """Equipment, skill primitives, module level skills with their steps, and procedures: read from
    the AASs alone they are what the module spec states."""
    spec = load(path)
    found = described(*aas(spec, next(iter(spec.targets))), spec.module, spec.package, spec.opcua_root)
    assert stated(found) == stated(spec)


def test_a_delivered_module_is_what_its_aas_describes(delivered):
    reading = read(FakeForte(filling()), "pi", 61499, *delivered)
    assert reading.differences.empty, reading.differences.lines()
    assert (reading.spec.module, reading.spec.package, reading.spec.opcua_root) == ("Filling", "filling", "/Objects/Filling")
    # The record of what was built names instances the program has, with their block types.
    assert ("Dispensing.Execute.Dispense", "filling::SK_Dispense", None) in instances(delivered[0])


def test_a_program_that_was_changed_differs_from_its_aas(delivered):
    forte = FakeForte(filling())
    forte.values["Dispensing.Execute.Dispense.FlowRate"] = "2.5"
    found = read(forte, "pi", 61499, *delivered).differences
    assert found.online and found.values == {"Dispensing.Execute.Dispense.FlowRate": ("1.0", "2.5")}
    assert found.lines() == ["Dispensing.Execute.Dispense.FlowRate = 2.5, the AAS describes 1.0"]
    # Another block where a step is described is nothing an online change repairs.
    forte.fbs["Dispensing.Execute.Home"] = "filling::SK_Tare"
    found = read(forte, "pi", 61499, *delivered).differences
    assert not found.online
    assert any("Dispensing.Execute" in line and "the program runs" in line for line in found.restart)
    assert found.built == ["Dispensing.Execute.Home is filling::SK_Tare, recorded as filling::SK_Home"]
    with pytest.raises(Refused, match="not possible online"):
        reconfigure(forte, "pi", 61499, *delivered)


def test_a_constant_and_a_limit_changed_in_the_aas_are_written_online(delivered):
    """The engineer raises the flow rate of the dispensing step and lowers the largest volume."""
    module, components = copy.deepcopy(delivered)
    dispensing = at(submodel(module, "Skills"), "Skills", "Dispensing")
    at(dispensing, "Start", "Steps", "Step_0001", "Bindings", "Binding_0001", "Value")["value"] = "2.0"
    volume = next(v["value"] for v in at(dispensing, "Start", "Start")["inputVariables"] if v["value"]["idShort"] == "Volume")
    next(q for q in volume["qualifiers"] if q["type"] == "Maximum")["value"] = "8.0"
    forte = FakeForte(filling())
    found = read(forte, "pi", 61499, module, components).differences
    assert found.online and found.values == {"Dispensing.Execute.Dispense.FlowRate": ("2.0", "1.0"),
                                             "Dispensing.Volume.Upper": ("8.0", "10.0")}
    done, after = reconfigure(forte, "pi", 61499, module, components)
    assert forte.writes == [("Dispensing.Execute.Dispense.FlowRate", "2.0"), ("Dispensing.Volume.Upper", "8.0")]
    assert after.differences.empty and done[-2].startswith("verified")
    # Values are written only while nobody works with the module.
    busy = FakeForte(filling(), state="Execute", occupied=True)
    with pytest.raises(Refused, match="occupied"):
        reconfigure(busy, "pi", 61499, module, components)


def test_a_skill_that_is_described_and_not_built_is_created_online(delivered, with_double_dose):
    """DoubleDose is in the Skills submodel; the Control Configuration records no instance of it."""
    module, components = with_double_dose
    assert "DoubleDose" in described(module, components).composites
    assert not any(path.startswith("DoubleDose") for path, _, _ in instances(module))
    forte = FakeForte(filling(), state="Execute", occupied=True)          # an orchestrator is working
    found = read(forte, "pi", 61499, module, components).differences
    assert found.create == ["DoubleDose"] and found.online and not found.values
    assert reconfigure(forte, "pi", 61499, module, components, dry_run=True)[0][0].startswith("create DoubleDose: ")
    assert "DoubleDose.Control" not in forte.fbs

    deployer = Recorder()
    deployer.load = lambda: boot_file(deployment(filling().app))
    done, after = reconfigure(forte, "pi", 61499, module, components, deployer)
    # The program is the one the generator makes from a module spec with that skill.
    new = composed().app
    assert forte.fbs == new.fbs
    assert forte.connections == set(new.event_connections + new.data_connections)
    assert forte.triggered == ["DoubleDose.Control.INIT"]         # the INIT chain enters there, once
    assert forte.values["DoubleDose.Dose.Default"] == "0.5"
    assert done[0].startswith("create DoubleDose: ") and after.differences.empty
    assert reconfigure(forte, "pi", 61499, module, components)[0] == ["the program is what the AAS describes, nothing to do"]
    # The boot file got the same instances, values and connections, before the resource starts.
    old, saved = boot_file(deployment(filling().app)).splitlines(), deployer.saved[0].splitlines()
    assert saved[:len(old) - 1] == old[:-1] and done[-1] == "added to the boot file"
    assert sum('Action="CREATE"><FB Name="DoubleDose.' in line for line in saved) == len(new.fbs) - len(filling().app.fbs)
    assert saved[-1].startswith(';<Request ID="') and 'Action="START"><FB Name="RES"' in saved[-1]
    assert not any("$e" in line for line in saved)


def test_what_was_built_is_recorded_in_the_control_configuration(with_double_dose):
    module, components = with_double_dose
    forte = FakeForte(filling())
    done, after = reconfigure(forte, "pi", 61499, module, components)
    recorded = record(module, after, done, "changeover to two doses")
    assert submodel(module, "ControlConfiguration") != submodel(recorded, "ControlConfiguration")      # a copy
    built = {path: (typ, digest) for path, typ, digest in instances(recorded)}
    assert built["DoubleDose.Control"] == ("modlib::SKILL_Core", f"v2:SHA3-512:{len('modlib::SKILL_Core')}")
    assert built["DoubleDose.Execute.NeedleDown"][0] == "filling::SK_MoveAxis"
    assert built["Dispensing.Execute.Dispense"][1].startswith("v2:SHA3-512:")      # the delivered ones get their hash too
    config = submodel(recorded, "ControlConfiguration")
    step = at(config, "Instances", "DoubleDose_Execute_NeedleDown", "Skill")["value"]["keys"]
    assert [k["value"] for k in step[1:]] == ["Skills", "DoubleDose", "Start", "Steps", "Step_0000"]
    assert at(config, "SyncState")["value"] == "InSync"
    change = at(config, "ChangeLog")["value"][-1]
    assert at(change, "Trigger")["value"] == "changeover to two doses"
    assert at(change, "Result")["value"].startswith("create DoubleDose: ")
    # With the record, the hashes are part of what is verified.
    forte.fbs["DoubleDose.Execute.NeedleDown"] = "filling::SK_Home"
    assert any("recorded as filling::SK_MoveAxis" in line
               for line in read(forte, "pi", 61499, recorded, components).differences.built)


def test_from_the_command_line_with_the_aas_in_a_folder(with_double_dose, tmp_path, monkeypatch, capsys):
    """verify, then reconfigure: the AASs are files, the module is where its AAS says it is."""
    import json

    import modsync.__main__ as cli
    module, components = with_double_dose
    for env in (module, *components):
        (tmp_path / f"{env['assetAdministrationShells'][0]['idShort']}.json").write_text(json.dumps(env), encoding="utf-8")
    assert desired.endpoint(module) == ("192.168.0.134", 61499)
    forte, asked = FakeForte(filling()), []
    monkeypatch.setattr(cli, "Client", lambda host, port, timeout: asked.append((host, port)) or forte)
    monkeypatch.setattr(cli, "is_local", lambda host: False)

    def run(*argv) -> tuple[int, str]:
        monkeypatch.setattr("sys.argv", ["modsync", *argv])
        with pytest.raises(SystemExit) as exit_:
            cli.main()
        return exit_.value.code, capsys.readouterr().out

    code, out = run("verify", str(tmp_path))
    assert code == 1 and "1 differences from its AAS (FillingModuleAAS)" in out
    assert "described, not in the program: DoubleDose" in out and asked == [("192.168.0.134", 61499)]
    code, out = run("reconfigure", str(tmp_path), "--dry-run")
    assert code == 0 and "create DoubleDose: " in out and "DoubleDose.Control" not in forte.fbs
    code, out = run("reconfigure", str(tmp_path), "--trigger", "two doses")
    assert code == 0 and "as its AAS describes it" in out and "recorded in" in out
    # The file now records what was built, and the module verifies against it.
    written = desired.load(str(tmp_path))[0]
    assert any(path == "DoubleDose.Control" and digest for path, _, digest in instances(written))
    assert at(at(submodel(written, "ControlConfiguration"), "ChangeLog")["value"][-1], "Trigger")["value"] == "two doses"
    assert run("verify", str(tmp_path))[0] == 0


def step_of(module: dict, step: str) -> dict:
    return at(submodel(module, "Skills"), "Skills", "Dispensing", "Start", "Steps", step)


def test_a_description_the_module_cannot_carry_out_is_refused(delivered):
    module, components = copy.deepcopy(delivered)
    step = at(submodel(module, "Skills"), "Skills", "Dispensing", "Start", "Steps", "Step_0000")
    at(step, "Skill")["value"]["keys"][-1]["value"] = "Polish"
    with pytest.raises(desired.NotDescribed, match="Polish, which no component of the module has"):
        described(module, components)
    module, components = copy.deepcopy(delivered)
    at(step_of(module, "Step_0000"), "Bindings", "Binding_0000", "Value")["value"] = "75.0"
    data = yaml.safe_load(FILLING.read_text(encoding="utf-8"))
    assert data["skills"]["MoveAxis"]["parameters"]["Position"]["maximum"] == 60.0
    with pytest.raises(desired.NotDescribed, match="outside"):
        described(module, components)
    # A skill may not offer more than the component it hands the value to can do (the pump: 10 mL).
    module, components = copy.deepcopy(delivered)
    start = at(submodel(module, "Skills"), "Skills", "Dispensing", "Start", "Start")
    volume = next(v["value"] for v in start["inputVariables"] if v["value"]["idShort"] == "Volume")
    next(q for q in volume["qualifiers"] if q["type"] == "Maximum")["value"] = "12.0"
    with pytest.raises(desired.NotDescribed, match="more than Dispense takes"):
        described(module, components)
    # ARSO describes more kinds of step than this module's control runs.
    module, components = copy.deepcopy(delivered)
    at(step_of(module, "Step_0000"), "Kind")["value"] = "parallel"
    with pytest.raises(desired.NotDescribed, match="of the kind parallel"):
        described(module, components)
    # The order of the steps is their Order, not their place in the collection.
    module, components = copy.deepcopy(delivered)
    steps = at(submodel(module, "Skills"), "Skills", "Dispensing", "Start", "Steps")
    steps["value"].reverse()
    assert [s.name for s in described(module, components).composites["Dispensing"].execute] == \
        ["NeedleDown", "Dispense", "Home", "Weigh"]
