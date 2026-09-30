"""Offline tests of the module generator: spec validation, reproducible output, flattened systems."""
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest
import yaml

from iec61499_mgmt.sysfile import load_application
from modgen import (LIBRARY_PROJECT, SPECS, generate, generate_library, load, manifest_path, project_dir, specs,
                    system_file)
from modgen.spec import ModuleSpec

FILLER = SPECS / "filler.yaml"


def raw(path=FILLER):
    """A spec as plain data, for mutation."""
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


@pytest.mark.parametrize("mutate, message", [
    (lambda d: d["skills"]["MoveNeedleDown"].update(ensures="Position >= Depth"), "unknown names"),
    (lambda d: d["skills"]["MoveNeedleDown"].update(command="Stop"), "not a driving command"),
    (lambda d: d["skills"]["MoveNeedleDown"].update(equipment="Pump"), "unknown equipment"),
    (lambda d: d["skills"]["MoveNeedleDown"]["parameters"]["Distance"].update(default=80.0), "default outside"),
    (lambda d: d["skills"]["MoveNeedleDown"].update(after=2.0), "either by ensures"),
    (lambda d: d["skills"]["MoveNeedleDown"].update(stop="Brake"), "unknown stop command"),
    (lambda d: d["equipment"]["NeedleAxis"].update(commands={"Down": ["Down"], "Stop": []}), "safe state"),
    (lambda d: d["equipment"]["NeedleAxis"]["commands"].update(Both=["Down", "Lift"]), "unknown output"),
    (lambda d: d["equipment"]["NeedleAxis"]["commands"].update(Up=[{"Up": 1.0}]), "is BOOL"),
    (lambda d: d["equipment"]["NeedleAxis"]["commands"].update(Up=[{"Up": True}, {"Up": True, "for": "1s"}]),
     "last phase holds"),
    (lambda d: d["skills"]["MoveNeedleDown"]["parameters"].update(AtTop={"type": "BOOL", "default": True}),
     "shadow"),
    (lambda d: d["composites"]["Fill"].update(execute=["Pump"]), "not a skill primitive"),
    (lambda d: d["composites"]["Fill"].update(execute=[{"MoveNeedleDown": {"Speed": 1}}]), "no parameter Speed"),
    (lambda d: d["composites"]["Fill"].update(execute=[{"MoveNeedleDown": {"Distance": "Depthh"}}]),
     "is not a parameter of Fill"),
    (lambda d: d["equipment"]["NeedleAxis"]["inputs"]["AtTop"].update(modbus="i0"), "BOOL inputs"),
    (lambda d: d["equipment"]["NeedleAxis"]["inputs"]["Position"].update(gpio=4), "only BOOL inputs"),
    (lambda d: d["equipment"]["NeedleAxis"]["outputs"]["Up"].update(gpio=5), "share gpio"),
    (lambda d: d["equipment"]["NeedleAxis"]["outputs"]["Up"].pop("modbus"), "Up has no Modbus address"),
    (lambda d: d.update(targets={}), "At least one target"),
])
def test_invalid_specs_are_rejected(mutate, message):
    data = raw()
    mutate(data)
    with pytest.raises(ValueError, match=message):
        ModuleSpec.model_validate(data)


def test_repeated_steps_get_their_own_instance_names():
    spec = load(SPECS / "stoppering.yaml")
    assert [s.name for s in spec.composites["Stoppering"].execute] == [
        "LowerPiston", "ArmIn", "ArmOut", "ExtendPlunger", "RetractPlunger", "RaisePiston"]
    data = raw()
    data["composites"]["Fill"]["execute"] = ["MoveNeedleUp", "MoveNeedleUp"]
    assert [s.name for s in ModuleSpec.model_validate(data).composites["Fill"].execute] == ["MoveNeedleUp",
                                                                                              "MoveNeedleUp_2"]


def canonical(path):
    """File content independent of formatting: the 4diac IDE rewrites generated XML on import
    (tabs, CDATA, empty elements), so XML is compared in canonical form."""
    data = path.read_bytes()
    if data.lstrip().startswith(b"<"):
        root = ET.fromstring(data)
        # Layout arranged in the IDE is kept by the generator and is not part of the content; the
        # IDE also drops empty variable groups when it saves a type.
        for node in root.iter():
            for attr in ("x", "y", "dx1", "dx2", "dy"):
                node.attrib.pop(attr, None)
            for group in [g for g in node if g.tag in ("InputVars", "OutputVars") and len(g) == 0]:
                node.remove(group)
        return ET.canonicalize(ET.tostring(root, encoding="unicode"), strip_text=True)
    return data.decode("utf-8-sig").strip()


def tree(root):
    """Relative path -> canonical content of every file below ``root``."""
    # The IDE keeps per-type documentation in .<Type>.fbt.assets folders; they are not generated.
    return {p.relative_to(root).as_posix(): canonical(p) for p in sorted(root.rglob("*"))
            if p.is_file() and not any(part.endswith(".assets") for part in p.parts)}


def committed(project):
    return project_dir(project), manifest_path(project)


@pytest.mark.parametrize("spec_path", specs(), ids=lambda p: p.stem)
def test_committed_module_projects_match_the_generator(tmp_path, spec_path):
    spec = load(spec_path)
    generate(spec, tmp_path / spec.project)       # the type manifest is part of the project
    assert tree(tmp_path / spec.project) == tree(committed(spec.project)[0])


def test_committed_library_project_matches_the_generator(tmp_path):
    generate_library(tmp_path / LIBRARY_PROJECT)
    assert tree(tmp_path / LIBRARY_PROJECT) == tree(committed(LIBRARY_PROJECT)[0])


def test_library_types_are_compiled_once():
    """Module projects declare the library types (so the IDE opens them) but do not export them."""
    import json
    for spec_path in specs():
        spec = load(spec_path)
        entries = json.loads(committed(spec.project)[1].read_text())
        assert {e["type"].split("::")[0] for e in entries if e["exported"]} == {spec.package}
        assert any(e["type"].startswith("modlib::") for e in entries)
    lib = json.loads(committed(LIBRARY_PROJECT)[1].read_text())
    assert {e["type"].split("::")[0] for e in lib if e["exported"]} == {"modlib"}


def flat(project, app):
    commands = load_application(system_file(project), app).commands("RES")
    return ({c.name: c.type for c in commands if c.op == "create_fb"},
            {(c.source, c.destination) for c in commands if c.op == "connect"},
            {c.destination: c.value for c in commands if c.op == "write"})


def test_filler_flattens_to_module_level_equipment_skills_and_procedures():
    created, wired, written = flat("FillerModule", "Filler")
    assert created == {
        "Boot": "iec61499::events::E_RESTART", "Occupation": "modlib::MOD_Occupation",
        "Module": "modlib::MOD_StateManager", "NeedleAxis": "filler::EQ_NeedleAxis",
        "MoveNeedleDown": "filler::SK_MoveNeedleDown", "MoveNeedleUp": "filler::SK_MoveNeedleUp",
        "Fill.Control": "filler::SC_Fill", "Fill.Execute.MoveNeedleDown": "filler::SK_MoveNeedleDown",
        "Fill.Execute.MoveNeedleUp": "filler::SK_MoveNeedleUp", "Fill.Execute.Fail1": "modlib::SKILL_FailMerge",
        "Fill.Stop.MoveNeedleUp": "filler::SK_MoveNeedleUp", "Resetting.MoveNeedleUp": "filler::SK_MoveNeedleUp",
        "Stopping.MoveNeedleUp": "filler::SK_MoveNeedleUp"}
    # The composite starts its sequence and passes its parameter to the child.
    assert {("Fill.Control.GO", "Fill.Execute.MoveNeedleDown.START"),
            ("Fill.Execute.MoveNeedleDown.SUCCESS", "Fill.Execute.MoveNeedleUp.START"),
            ("Fill.Execute.MoveNeedleUp.SUCCESS", "Fill.Control.EXEC_DONE"),
            ("Fill.Control.P_Depth", "Fill.Execute.MoveNeedleDown.Distance"),
            ("Fill.Control.RUN_STOP", "Fill.Stop.MoveNeedleUp.START"),
            ("Module.RUN_RESETTING", "Resetting.MoveNeedleUp.START"),
            ("Resetting.MoveNeedleUp.SUCCESS", "Module.RESETTING_DONE")} <= wired
    # No wiring between skills, equipment and the module level: they meet on local channels.
    assert not {w for w in wired if "NeedleAxis" in w[0] + w[1] and "INIT" not in w[0] + w[1]}
    assert written["MoveNeedleDown.UaPath"] == '"/Skills/MoveNeedleDown"'
    assert written["MoveNeedleDown.Methods"] == "TRUE"
    # Children are private (no methods) and keep the composite's equipment lock.
    assert written["Fill.Execute.MoveNeedleDown.Methods"] == "FALSE"
    assert written["Fill.Execute.MoveNeedleDown.Token"] == '"Fill"'
    assert written["Fill.Execute.MoveNeedleDown.LastUse"] == "FALSE"       # MoveNeedleUp comes next
    assert written["Fill.Execute.MoveNeedleUp.LastUse"] == "TRUE"          # releases the needle
    # Procedure children release after each step.
    assert written["Resetting.MoveNeedleUp.LastUse"] == "TRUE"
    assert "MoveNeedleDown.Distance" not in written                        # the type's default applies


def test_stoppering_binds_constants_per_instance():
    created, wired, written = flat("StopperingModule", "Stoppering")
    assert written["Stoppering.Execute.ArmIn.Angle"] == "1.0"
    assert written["Stoppering.Execute.ArmOut.Angle"] == "121.0"
    assert written["Resetting.RaisePiston.Duration"] == "1.5"
    assert created["Stoppering.Execute.ArmIn"] == "stoppering::SK_MoveArm"


def st(project, folder, name):
    root = ET.parse(project_dir(project) / "Type Library" / folder / f"{name}.fbt").getroot()
    return root, "\n".join(s.text or "" for s in root.iter("ST"))


def test_skill_logic_carries_contract_range_and_lock():
    root, code = st("FillerModule", "Skills/Logic", "SL_MoveNeedleDown")
    conditions = {t.get("Condition") for t in root.iter("ECTransition")}
    assert "SAMPLE[(Position >= Distance) OR AtBottom]" in conditions
    assert 'SAMPLE[(Holder <> "") AND (Holder <> Token)]' in conditions      # lost the equipment
    assert "C_Holder := Token;" in code
    _, params = st("FillerModule", "Skills/Parameters", "SP_MoveNeedleDown")
    assert "InRange := (S_Distance >= 0.0) AND (S_Distance <= 50.0);" in params


def test_open_loop_skill_ends_by_time_and_passes_its_argument():
    root, code = st("StopperingModule", "Skills/Logic", "SL_MoveArm")
    assert "TimerDT := MUL_TIME(T#1s, Settle);" in code
    assert "C_Arg := Angle;" in code
    conditions = {(t.get("Source"), t.get("Condition")) for t in root.iter("ECTransition")}
    assert ("Running", "TIMER") in conditions


def test_equipment_runs_command_phases():
    _, code = st("FillingModule", "Equipment/Base", "EL_NeedleAxis")
    assert "N_Speed := 190.0;\n    NE_Speed := TRUE;\n    PhaseDT := T#200ms;" in code   # start boost
    assert "N_Speed := 140.0;" in code
    _, code = st("StopperingModule", "Equipment/Base", "EL_StopperArm")
    assert "N_Angle := Arg;" in code


@pytest.mark.parametrize("project", [LIBRARY_PROJECT, *[load(p).project for p in specs()]])
def test_projects_follow_the_ide_conventions(project):
    """What the IDE's system editor needs, which its headless checks did not catch."""
    folder = project_dir(project)
    assert not (folder / ".buildpath").exists()          # else the root .sys is outside the type library
    system = ET.parse(folder / f"{project}.sys").getroot()
    for sub in system.iter("SubApp"):
        assert sub.find("InterfaceList") is None and sub.find("SubAppInterfaceList/SubAppEventInputs/SubAppEvent") is not None
    for device in system.iter("Device"):
        assert len(device.find("Resource/FBNetwork")) == 0     # mapped blocks are rebuilt by the IDE
        assert device.find("Attribute[@Name='Color']") is not None


def test_filler_maps_one_application_per_target():
    system = ET.parse(system_file("FillerModule")).getroot()
    mappings = {(m.get("From").split(".")[0], m.get("To")) for m in system.iter("Mapping")}
    assert mappings == {("Filler", "FORTE_PC.RES"), ("Filler_pi", "FORTE_PI.RES")}


def test_pi_target_drives_the_io_over_gpio_lines():
    """The Pi application claims each GPIO line once, before the equipment, with mode and bias."""
    created, wired, written = flat("FillerModule", "Filler_pi")
    lines = {n.split(".")[1]: written[n + ".LineNumber"] for n, t in created.items() if t.endswith("GPIOChip")}
    assert lines == {"NeedleAxis_AtTop": "17", "NeedleAxis_AtBottom": "27", "NeedleAxis_Down": "5",
                     "NeedleAxis_Up": "6"}
    assert written["GpioLines.NeedleAxis_AtTop.ReadWriteMode"] == "0"
    assert written["GpioLines.NeedleAxis_Down.ReadWriteMode"] == "1"
    assert written["GpioLines.NeedleAxis_AtTop.BiasMode"] == "2"        # pull-up (FORTE 3.3.0 numbering)
    assert written["GpioLines.NeedleAxis_AtTop.ActiveLow"] == "TRUE"
    assert written["NeedleAxis.Down_Io"] == "'NeedleAxis_Down'"
    assert (written["NeedleAxis.Down_Backend"], written["NeedleAxis.Position_Backend"]) == ("1", "0")
    assert not any(k.endswith("_Modbus") for k in written)
    assert ("Boot.COLD", "GpioLines.NeedleAxis_AtTop.INIT") in wired
    assert ("GpioLines.NeedleAxis_Up.INITO", "Occupation.INIT") in wired
    pc = flat("FillerModule", "Filler")[2]
    assert not any("GpioLines" in k for k in pc) and pc["NeedleAxis.Position_Backend"] == "2"


def test_regeneration_keeps_layout_arranged_in_the_ide(tmp_path):
    spec = load(FILLER)
    project, manifest = tmp_path / spec.project, tmp_path / "manifest.json"
    generate(spec, project, manifest)
    path = project / "Type Library" / "Module" / "MOD_Occupation.fbt"
    doc = ET.parse(path)
    moved = next(fb for fb in doc.getroot().iter("FB") if fb.get("Name") == "Logic")
    moved.set("x", "1234.5")
    doc.write(path, encoding="utf-8", xml_declaration=True)
    generate(spec, project, manifest)
    again = next(fb for fb in ET.parse(path).getroot().iter("FB") if fb.get("Name") == "Logic")
    assert again.get("x") == "1234.5"


def test_application_is_grouped_and_init_chains_are_hidden():
    """Five groups, top to bottom (module level, module level skills, procedures, skill primitives, equipment IO);
    every block of the application in one of them; INIT and start-up connections hidden."""
    system = ET.parse(system_file("FillingModule")).getroot()
    net = next(a for a in system.iter("Application") if a.get("Name") == "Filling").find("SubAppNetwork")
    groups = [g.get("Name") for g in net.findall("Group")]
    assert groups == ["ModuleLevel", "ModuleLevelSkills", "Procedures", "SkillPrimitives", "EquipmentIO"]
    member = {el.get("Name"): el.find("Attribute[@Name='GroupName']").get("Value")
              for el in net if el.tag in ("FB", "SubApp")}
    assert member["Dispensing"] == "ModuleLevelSkills" and member["MoveNeedleUp"] == "SkillPrimitives"
    assert member["NeedleAxis"] == "EquipmentIO" and member["Resetting"] == "Procedures"
    for conn in net.find("EventConnections"):
        hidden = conn.find("Attribute[@Name='Visible']") is not None
        init = conn.get("Destination").endswith(".INIT") or conn.get("Source").startswith("Boot.")
        assert hidden == init, (conn.get("Source"), conn.get("Destination"))


def test_stop_sequence_nodes_do_not_collide_with_the_stop_method():
    """A module level skill's stop sequence publishes below /Skills/<name>/Stopping: FORTE would put an
    object /Skills/<name>/Stop inside the skill's Stop method node."""
    from iec61499_mgmt.sysfile import flatten
    from modgen.module import application
    spec = load(SPECS / "filling.yaml")
    app = flatten(application(ET.Element("System"), spec, "pc").find("SubAppNetwork"))
    paths = {k: v for k, v in app.parameters.items() if k.startswith("Dispensing.Stop.") and k.endswith(".UaPath")}
    assert paths == {"Dispensing.Stop.MoveNeedleUp.UaPath": '"/Skills/Dispensing/Stopping/MoveNeedleUp"'}
