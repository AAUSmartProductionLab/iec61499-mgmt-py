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
from modsync.compare import Candidate                                        # noqa: E402
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
    """The AASs that describe ``spec`` on a module that was delivered as ``built``: a skill ``built``
    does not have is described, not built (Deployment Described). What an engineer's change to the
    AAS of a delivered module looks like."""
    module, components = aas(spec)
    have = {s["idShort"] for s in desired.skills_in(submodel(built, "Skills"))}
    for skill in desired.skills_in(submodel(module, "Skills")):
        if skill["idShort"] not in have:
            at(skill, "Deployment")["value"] = "Described"
    return module, components


@pytest.fixture(scope="module")
def delivered():
    return aas(load(FILLING))


@pytest.fixture(scope="module")
def delivered_record():
    """What the integrator's record says was built on the delivered module."""
    return profiles.describe_with_record(load(FILLING), "pi")[1]


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


def test_a_delivered_module_is_what_its_aas_describes(delivered, delivered_record):
    reading = read(FakeForte(filling()), "pi", 61499, *delivered, record_=delivered_record)
    assert reading.differences.empty, reading.differences.lines()
    assert (reading.spec.module, reading.spec.package, reading.spec.opcua_root) == ("Filling", "filling", "/Objects/Filling")
    # The record of what was built names instances the program has, with their block types.
    assert ("Dispensing.Execute.Dispense", "filling::SK_Dispense", None) in instances(delivered_record)
    # Without a record the AAS and the program are enough.
    assert read(FakeForte(filling()), "pi", 61499, *delivered).differences.empty


def test_a_program_that_was_changed_differs_from_its_aas(delivered, delivered_record):
    forte = FakeForte(filling())
    forte.values["Dispensing.Execute.Dispense.FlowRate"] = "2.5"
    found = read(forte, "pi", 61499, *delivered).differences
    assert found.online and found.values == {"Dispensing.Execute.Dispense.FlowRate": ("1.0", "2.5")}
    assert found.lines() == ["Dispensing.Execute.Dispense.FlowRate = 2.5, the AAS describes 1.0"]
    # Another block where a step is described is nothing an online change repairs.
    forte.fbs["Dispensing.Execute.Home"] = "filling::SK_Tare"
    found = read(forte, "pi", 61499, *delivered, record_=delivered_record).differences
    assert not found.online
    assert any("Dispensing.Execute" in line and "the program runs" in line for line in found.restart)
    assert found.built == ["Dispensing.Execute.Home is filling::SK_Tare, recorded as filling::SK_Home"]
    with pytest.raises(Refused, match="not possible online"):
        reconfigure(forte, "pi", 61499, *delivered)


def test_a_constant_and_a_limit_changed_in_the_aas_are_written_online(delivered):
    """The engineer raises the flow rate of the dispensing step and lowers the largest volume."""
    module, components = copy.deepcopy(delivered)
    dispensing = at(submodel(module, "Skills"), "Dispensing")
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
    """DoubleDose is in the Skills submodel, described and not built."""
    module, components = with_double_dose
    assert "DoubleDose" in described(module, components).composites
    assert desired.deployment(at(submodel(module, "Skills"), "DoubleDose")) == "Described"
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


def test_what_was_built_is_recorded(with_double_dose, delivered_record):
    """The AAS says the skill is built now (Deployment); the record outside it says which blocks it is."""
    module, components = with_double_dose
    forte = FakeForte(filling())
    done, after = reconfigure(forte, "pi", 61499, module, components, record_=delivered_record)
    recorded, config = record(module, after, done, "changeover to two doses", record_=delivered_record)
    assert desired.deployment(at(submodel(recorded, "Skills"), "DoubleDose")) == "Built"
    assert desired.deployment(at(submodel(module, "Skills"), "DoubleDose")) == "Described"         # a copy
    assert config is not delivered_record and not any(p.startswith("DoubleDose") for p, _, _ in instances(delivered_record))
    assert submodel(recorded, "ControlConfiguration") is None
    built = {path: (typ, digest) for path, typ, digest in instances(config)}
    assert built["DoubleDose.Control"] == ("modlib::SKILL_Core", f"v2:SHA3-512:{len('modlib::SKILL_Core')}")
    assert built["DoubleDose.Execute.NeedleDown"][0] == "filling::SK_MoveAxis"
    assert built["Dispensing.Execute.Dispense"][1].startswith("v2:SHA3-512:")      # the delivered ones get their hash too
    step = at(config, "Instances", "DoubleDose_Execute_NeedleDown", "Skill")["value"]["keys"]
    assert [k["value"] for k in step[1:]] == ["DoubleDose", "Start", "Steps", "Step_0000"]
    assert at(config, "SyncState")["value"] == "InSync"
    change = at(config, "ChangeLog")["value"][-1]
    assert at(change, "Trigger")["value"] == "changeover to two doses"
    assert at(change, "Result")["value"].startswith("create DoubleDose: ")
    # With the record, the hashes are part of what is verified.
    assert at(config, "Runtime", "ManagementEndpoint")["value"] == "pi:61499"
    forte.fbs["DoubleDose.Execute.NeedleDown"] = "filling::SK_Home"
    assert any("recorded as filling::SK_MoveAxis" in line
               for line in read(forte, "pi", 61499, recorded, components, record_=config).differences.built)


def test_from_the_command_line_with_the_aas_in_a_folder(with_double_dose, delivered_record, tmp_path, monkeypatch, capsys):
    """verify, then reconfigure: the AASs are files, the module is where the record of what was built
    says it is."""
    import json

    import modsync.__main__ as cli
    module, components = with_double_dose
    folder, records = tmp_path / "aas", tmp_path / "records"
    folder.mkdir()
    for env in (module, *components):
        (folder / f"{env['assetAdministrationShells'][0]['idShort']}.json").write_text(json.dumps(env), encoding="utf-8")
    desired.store_record(str(records), module, delivered_record)
    assert desired.endpoint(desired.load_record(str(records), module)) == ("192.168.0.203", 61499)
    forte, asked = FakeForte(filling()), []
    monkeypatch.setattr(cli, "Client", lambda host, port, timeout: asked.append((host, port)) or forte)
    monkeypatch.setattr(cli, "is_local", lambda host: False)

    def run(*argv) -> tuple[int, str]:
        monkeypatch.setattr("sys.argv", ["modsync", *argv, "--records", str(records)])
        with pytest.raises(SystemExit) as exit_:
            cli.main()
        return exit_.value.code, capsys.readouterr().out

    code, out = run("verify", str(folder))
    assert code == 1 and "1 differences from its AAS (FillingModuleAAS)" in out
    assert "described, not in the program: DoubleDose" in out and asked == [("192.168.0.203", 61499)]
    code, out = run("reconfigure", str(folder), "--dry-run")
    assert code == 0 and "create DoubleDose: " in out and "DoubleDose.Control" not in forte.fbs
    code, out = run("reconfigure", str(folder), "--trigger", "two doses")
    assert code == 0 and "as its AAS describes it" in out and "record of what was built: " in out
    # The AAS says the skill is built, the record which blocks it is; the module verifies against both.
    written = desired.load(str(folder))[0]
    assert desired.deployment(at(submodel(written, "Skills"), "DoubleDose")) == "Built"
    kept = desired.load_record(str(records), written)
    assert any(path == "DoubleDose.Control" and digest for path, _, digest in instances(kept))
    assert at(at(kept, "ChangeLog")["value"][-1], "Trigger")["value"] == "two doses"
    assert run("verify", str(folder))[0] == 0


def test_a_skill_written_in_the_skill_editor_is_built(delivered):
    """The web UI's skill editor (basyx-aas-web-ui fork, ProcessSequence/skills) saves the Skills
    submodel. tests/data/FillingSkills-edited.json.gz is what it wrote in its own test: a new skill
    DoubleDose made from Dispensing, with a second dispensing step and other limits, described and
    not built (Deployment Described). It has no action of the interface yet; built, it is callable
    like the others."""
    import gzip
    import json
    from pathlib import Path
    edited = json.loads(gzip.decompress((Path(__file__).parent / "data" / "FillingSkills-edited.json.gz").read_bytes()))
    module, components = copy.deepcopy(delivered)
    module["submodels"] = [edited if s["idShort"] == "Skills" else s for s in module["submodels"]]
    made = described(module, components).composites["DoubleDose"]
    assert at(edited, "DoubleDose", "Start", "InterfaceReference") is None and made.offered
    assert [(s.name, s.skill) for s in made.execute] == [("NeedleDown", "MoveAxis"), ("Dispense", "Dispense"),
                                                         ("Dispense_2", "Dispense"), ("Home", "Home"), ("Weigh", "Weigh")]
    assert made.execute[2].bind == {"Volume": "Volume", "FlowRate": 1.0} and made.results == {"Weight": "Weigh.Weight"}
    assert (made.parameters["Volume"].default, made.parameters["Volume"].maximum) == (0.5, 5.0)
    # Described, not built: it offers Filling after a reconfiguration, for what its two doses of its
    # Volume (0.5 to 5.0 mL) fill (modplan runs it through the states).
    from modreg.offer import capabilities
    double = at(submodel(capabilities(module, components), "CapabilityDescription"), "OfferedCapabilities", "Filling_DoubleDose")
    assert {q["type"]: q["value"] for q in at(double, "Capability")["qualifiers"]}["Availability"] == "AfterReconfiguration"
    assert (at(double, "PropertySet", "FillVolume", "Value")["min"], at(double, "PropertySet", "FillVolume", "Value")["max"]) \
        == ("1.0", "10.0")
    forte = FakeForte(filling())
    done, after = reconfigure(forte, "pi", 61499, module, components)
    assert done[0].startswith("create DoubleDose: ") and after.differences.empty
    # The program is the one the generator makes from the same skill in a module spec.
    data = yaml.safe_load(FILLING.read_text(encoding="utf-8"))
    data["composites"]["DoubleDose"] = {
        "parameters": {"Volume": {"unit": "mL", "minimum": 0.5, "maximum": 5.0, "default": 0.5}},
        "execute": [{"MoveAxis": {"Position": 40.0}, "as": "NeedleDown"}, {"Dispense": {"Volume": "Volume", "FlowRate": 1.0}},
                    {"Dispense": {"Volume": "Volume", "FlowRate": 1.0}}, "Home", "Weigh"],
        "stop": ["Home"], "results": {"Weight": "Weigh.Weight"}}
    wanted = Candidate(None, ModuleSpec.model_validate(data), "pi").app
    assert forte.fbs == wanted.fbs and forte.connections == set(wanted.event_connections + wanted.data_connections)
    assert forte.values["DoubleDose.Control.Methods"] == "TRUE" and forte.values["DoubleDose.Volume.Upper"] == "5.0"
    # Recorded, the skill is reachable: its commands name their actions, and the interface, the data
    # points and the mappings are those of a module that was delivered with this skill.
    recorded = record(module, after, done, "two doses")[0]
    # Recorded with its components' AASs, the capabilities are derived anew: built, it offers now.
    double = at(submodel(record(module, after, done, "two doses", components)[0], "CapabilityDescription"),
                "OfferedCapabilities", "Filling_DoubleDose")
    assert "Availability" not in {q["type"] for q in at(double, "Capability")["qualifiers"]}
    whole = model.build(profiles.describe(ModuleSpec.model_validate(data), "pi"))
    def bare(element):
        """Without the ids aas-model draws anew for every build."""
        if isinstance(element, dict):
            return {k: bare(v) for k, v in element.items() if k != "embeddedDataSpecifications"}
        return [bare(v) for v in element] if isinstance(element, list) else element

    own = lambda elements: {e["idShort"]: bare(e) for e in elements if "DoubleDose" in e["idShort"]}      # noqa: E731
    for kind in ("actions", "properties"):
        there = ("AssetInterfacesDescription", "interface_opcua", "InteractionMetadata", kind)
        got = own(at(submodel(recorded, there[0]), *there[1:])["value"])
        assert got == own(at(submodel(whole, there[0]), *there[1:])["value"]) and len(got) > 3
    # Its values are a series of their own, State/DoubleDose, as in a module built with it.
    state = lambda env: at(submodel(env, "Variables"), "State")["value"]      # noqa: E731
    assert own(state(recorded)) == own(state(whole)) and set(own(state(recorded))) == {"DoubleDose"}
    start = at(submodel(recorded, "Skills"), "DoubleDose", "Start")
    assert at(start, "InterfaceReference")["value"]["keys"][-1]["value"] == "DoubleDose_Start"
    assert {q["type"] for q in at(start, "Start")["qualifiers"]} == {"invocationDelegation", "Synchronous"}
    assert [c["idShort"] for c in at(submodel(recorded, "Skills"), "DoubleDose")["value"]
            if c["modelType"] == "SubmodelElementCollection"] == ["Start", "Stop", "Abort", "Reset"]
    mappings = lambda env: at(submodel(env, "AssetInterfacesMappingConfiguration"), "MappingConfigurations")["value"]   # noqa: E731
    # Four actions to invoke, and the rows of its series to write.
    assert len(mappings(recorded)) == len(mappings(whole)) == len(mappings(module)) + 5
    from modreg.offer import lua, series_of_mapping
    rows = lambda env: next(c for c in mappings(env) if series_of_mapping(c) == ("State", "DoubleDose"))   # noqa: E731
    assert lua(rows(recorded)) == lua(rows(whole))
    # It is what the ontology describes, and the module still is what the recorded AAS describes.
    from modreg.ontology import Blueprint, check
    arso = Blueprint(Path(__file__).resolve().parents[2] / "ontology" / "ARSO")
    assert check(recorded, arso).ok and len(check(recorded, arso).unknown) == len(check(whole, arso).unknown)
    assert read(forte, "pi", 61499, recorded, components).differences.empty
    assert record(recorded, after)[0] == record(record(recorded, after)[0], after)[0]   # nothing is added twice
    # Stored on an AAS server, every submodel the record changed is put back, and no other.
    import http.server
    import threading
    put = []

    class Server(http.server.BaseHTTPRequestHandler):
        def do_PUT(self):                                   # noqa: N802
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            put.append(body["idShort"])
            self.send_response(204)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Server)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        where = desired.store(f"http://127.0.0.1:{server.server_address[1]}", recorded, module)
    finally:
        server.shutdown()
        server.server_close()
    assert sorted(put) == ["AssetInterfacesDescription", "AssetInterfacesMappingConfiguration",
                           "Skills", "Variables"] and "Skills" in where
    # A binding that hands nothing is refused.
    at(edited, "DoubleDose", "Start", "Steps", "Step_0000", "Bindings", "Binding_0000", "Value")["value"] = ""
    with pytest.raises(desired.NotDescribed, match="is handed nothing"):
        described(module, components)


def step_of(module: dict, step: str) -> dict:
    return at(submodel(module, "Skills"), "Dispensing", "Start", "Steps", step)


def test_a_description_the_module_cannot_carry_out_is_refused(delivered):
    module, components = copy.deepcopy(delivered)
    step = at(submodel(module, "Skills"), "Dispensing", "Start", "Steps", "Step_0000")
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
    start = at(submodel(module, "Skills"), "Dispensing", "Start", "Start")
    volume = next(v["value"] for v in start["inputVariables"] if v["value"]["idShort"] == "Volume")
    next(q for q in volume["qualifiers"] if q["type"] == "Maximum")["value"] = "12.0"
    with pytest.raises(desired.NotDescribed, match="more than Dispense takes"):
        described(module, components)
    # ARSO describes more kinds of step than this module's control runs (a call of another flow).
    module, components = copy.deepcopy(delivered)
    at(step_of(module, "Step_0000"), "Kind")["value"] = "call"
    with pytest.raises(desired.NotDescribed, match="of the kind call"):
        described(module, components)
    # The order of the steps is their Order, not their place in the collection.
    module, components = copy.deepcopy(delivered)
    steps = at(submodel(module, "Skills"), "Dispensing", "Start", "Steps")
    steps["value"].reverse()
    assert [s.name for s in described(module, components).composites["Dispensing"].execute] == \
        ["NeedleDown", "Dispense", "Home", "Weigh"]
