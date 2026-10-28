"""Offline tests of the module generator: spec validation, reproducible output, flattened systems."""
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest
import yaml

from iec61499_mgmt.sysfile import load_application
from modgen import (LIBRARY_PROJECT, LIBRARY_SPECS, SPECS, generate, generate_library, library_specs, load,
                    manifest_path, project_dir, specs, system_file)
from modgen.module import app_name
from modgen.spec import ModuleSpec

FILLER = LIBRARY_SPECS / "filler.yaml"
ALL = [*specs(), *library_specs()]                 # the line's modules and the generator's test module


def raw(path=FILLER):
    """A spec as plain data, for mutation."""
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


@pytest.mark.parametrize("mutate, message", [
    (lambda d: d["skills"]["MoveNeedleDown"].update(postcondition="Position >= Depth"), "unknown names"),
    (lambda d: d["skills"]["MoveNeedleDown"].update(command="Stop"), "not a driving command"),
    (lambda d: d["skills"]["MoveNeedleDown"].update(equipment="Pump"), "unknown equipment"),
    (lambda d: d["skills"]["MoveNeedleDown"]["parameters"]["Distance"].update(default=80.0), "default outside"),
    (lambda d: d["skills"]["MoveNeedleDown"].update(after=2.0), "either by postcondition"),
    (lambda d: d["skills"].update(Dose={"parameters": {"Volume": {"default": 1.0}}, "after": "Volume / Rate",
                                        "offered": False}), "not an expression over LREAL parameters"),
    (lambda d: d["skills"].update(Dose={"parameters": {"Volume": {"default": 1.0}, "Rate": {"default": 1.0, "minimum": 0.0}},
                                        "after": "Volume / Rate", "offered": False}), "minimum has to be above 0"),
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
    # What reaches a step is not checked by the step itself, so it is checked here.
    (lambda d: d["composites"]["Fill"].update(execute=[{"MoveNeedleDown": {"Distance": 80.0}}]), "beyond the limits"),
    (lambda d: d["composites"]["Fill"]["parameters"]["Depth"].update(maximum=80.0), "beyond the limits"),
    (lambda d: d["composites"]["Fill"]["parameters"]["Depth"].pop("minimum"), "beyond the limits"),
    (lambda d: d["composites"]["Fill"]["parameters"].update(Depth={"type": "INT", "minimum": 0, "maximum": 50, "default": 50}),
     "Depth is INT, the parameter LREAL"),
    (lambda d: d["equipment"]["NeedleAxis"]["inputs"]["AtTop"].update(modbus="i0"), "BOOL inputs"),
    (lambda d: d["equipment"]["NeedleAxis"]["inputs"]["Position"].update(gpio=4), "only BOOL inputs"),
    (lambda d: d["equipment"]["NeedleAxis"]["outputs"]["Up"].update(gpio=5), "share gpio"),
    (lambda d: d["equipment"]["NeedleAxis"]["outputs"]["Up"].pop("modbus"), "Up has no Modbus address"),
    (lambda d: d.update(targets={}), "At least one target"),
    (lambda d: d.update(capabilities={"Filling": {"properties": {
        "Volume": {"value": 1.0, "minimum": 0.5, "maximum": 2.0}}}}), "a value, values or a range"),
    (lambda d: d.update(capabilities={"Filling": {"properties": {
        "Volume": {"minimum": 2.0, "maximum": 0.5}}}}), "minimum <= maximum"),
    (lambda d: d.update(capabilities={"Filling": {"realized_by": "Fill"}}), "Extra inputs are not permitted"),
])
def test_invalid_specs_are_rejected(mutate, message):
    data = raw()
    mutate(data)
    with pytest.raises(ValueError, match=message):
        ModuleSpec.model_validate(data)


def test_a_capability_states_the_facts_of_the_machine():
    """Which skill realizes it is derived from the skills (modreg.derive), not stated."""
    data = raw()
    data["capabilities"] = {"Filling": {"properties": {
        "ContainerType": {"value": "vial"}, "Depth": {"minimum": 0.0, "maximum": 50.0, "unit": "mm"}}}}
    spec = ModuleSpec.model_validate(data)
    assert spec.capabilities["Filling"].properties["Depth"].unit == "mm"


def test_repeated_steps_get_their_own_instance_names():
    spec = load(SPECS / "stoppering.yaml")
    assert [s.name for s in spec.composites["Stoppering"].execute] == ["HeadDown", "PressStopper", "Home"]
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
            for attr in ("x", "y", "dx1", "dx2", "dy") + (("width", "height") if node.tag == "Group" else ()):
                node.attrib.pop(attr, None)
            for group in [g for g in node if g.tag in ("InputVars", "OutputVars") and len(g) == 0]:
                node.remove(group)
            # The IDE stores the size of a subapp shown unfolded.
            for size in [a for a in node if a.tag == "Attribute" and a.get("Name") in ("width", "height")]:
                node.remove(size)
        return ET.canonicalize(ET.tostring(root, encoding="unicode"), strip_text=True)
    return data.decode("utf-8-sig").strip()


def tree(root):
    """Relative path -> canonical content of every file below ``root``."""
    # The IDE keeps per-type documentation in .<Type>.fbt.assets folders; they are not generated.
    return {p.relative_to(root).as_posix(): canonical(p) for p in sorted(root.rglob("*"))
            if p.is_file() and not any(part.endswith(".assets") for part in p.parts)}


def committed(project):
    return project_dir(project), manifest_path(project)


@pytest.mark.parametrize("spec_path", ALL, ids=lambda p: p.stem)
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
    for spec_path in ALL:
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
    assert ("START.COLD", "Occupation.INIT") in wired and ("START.WARM", "Occupation.INIT") in wired
    assert created == {
        "Occupation": "modlib::MOD_Occupation",
        "Module": "modlib::MOD_StateManager", "NeedleAxis": "filler::EQ_NeedleAxis",
        "MoveNeedleDown": "filler::SK_MoveNeedleDown", "MoveNeedleUp": "filler::SK_MoveNeedleUp",
        "Fill.Control": "modlib::SKILL_Core", "Fill.UaStart": "iec61499::net::SERVER_2_2",
        "Fill.Depth": "modlib::SKILL_Param_LREAL", "Fill.PubParams": "iec61499::net::PUBLISH_1",
        "Fill.Execute.MoveNeedleDown": "filler::SK_MoveNeedleDown",
        "Fill.Execute.MoveNeedleUp": "filler::SK_MoveNeedleUp", "Fill.Execute.Fail1": "modlib::SKILL_FailMerge",
        "Fill.Stop.MoveNeedleUp": "filler::SK_MoveNeedleUp", "Resetting.MoveNeedleUp": "filler::SK_MoveNeedleUp",
        "Stopping.MoveNeedleUp": "filler::SK_MoveNeedleUp"}
    # The Start argument is range checked, latched and passed to the child that runs first.
    assert {("Fill.UaStart.IND", "Fill.Depth.CHECK"), ("Fill.Depth.CHECKED", "Fill.Control.START_REQ"),
            ("Fill.Control.RUN", "Fill.Depth.LATCH"), ("Fill.UaStart.RD_1", "Fill.Control.Session"),
            ("Fill.UaStart.RD_2", "Fill.Depth.Requested"),
            ("Fill.Depth.LATCHED", "Fill.Execute.MoveNeedleDown.START"),
            ("Fill.Execute.MoveNeedleDown.SUCCESS", "Fill.Execute.MoveNeedleUp.START"),
            ("Fill.Execute.MoveNeedleUp.SUCCESS", "Fill.Control.EXECUTE_DONE"),
            ("Fill.Depth.Value", "Fill.Execute.MoveNeedleDown.Distance"),
            ("Fill.Control.RUN_STOPPING", "Fill.Stop.MoveNeedleUp.START"),
            ("Module.RUN_RESETTING", "Resetting.MoveNeedleUp.START"),
            ("Resetting.MoveNeedleUp.SUCCESS", "Module.RESETTING_DONE")} <= wired
    assert (written["Fill.Depth.Default"], written["Fill.Depth.Lower"], written["Fill.Depth.Upper"]) == ("50.0", "0.0", "50.0")
    assert written["Fill.PubParams.ID"] == '"opc_ua[WRITE;/Objects/Filler/Skills/Fill/Parameters/Depth]"'
    # Control gives up everything the skill holds when a run ends, on the module's release channel.
    assert (written["Fill.Control.Holder"], written["Fill.Control.ReleaseAll"]) == ('"Fill"', "TRUE")
    # No wiring between skills, equipment and the module level: they meet on local channels.
    assert not {w for w in wired if any(p.startswith("NeedleAxis.") for p in w) and "INIT" not in w[0] + w[1]}
    assert written["MoveNeedleDown.UaPath"] == '"/Skills/MoveNeedleDown"'
    assert written["MoveNeedleDown.Methods"] == "TRUE"
    # Children are private (no methods) and keep the composite's equipment lock.
    assert written["Fill.Execute.MoveNeedleDown.Methods"] == "FALSE"
    assert written["Fill.Execute.MoveNeedleDown.Holder"] == '"Fill"'
    # They keep it to the end of the run: the composite's Control gives everything up then.
    assert written["Fill.Execute.MoveNeedleDown.ReleaseAfter"] == "FALSE"
    assert written["Fill.Execute.MoveNeedleUp.ReleaseAfter"] == "FALSE"
    assert written["Fill.Control.ReleaseAll"] == "TRUE"
    # Procedure children release after each step.
    assert written["Resetting.MoveNeedleUp.ReleaseAfter"] == "TRUE"
    assert "MoveNeedleDown.Distance" not in written                        # the type's default applies


def test_stoppering_binds_constants_per_instance():
    created, wired, written = flat("StopperingModule", "Stoppering")
    assert written["Stoppering.Execute.HeadDown.Position"] == "40.0"
    assert "Stoppering.Execute.Home.Position" not in written              # homing takes no position
    assert created["Stoppering.Execute.HeadDown"] == "stoppering::SK_MoveAxis"
    assert created["Stoppering.Execute.Home"] == created["Stoppering.Stop.Home"] == "stoppering::SK_Home"


def st(project, folder, name):
    root = ET.parse(project_dir(project) / "Type Library" / folder / f"{name}.fbt").getroot()
    return root, "\n".join(s.text or "" for s in root.iter("ST"))


@pytest.mark.parametrize("project", [LIBRARY_PROJECT, *[load(p).project for p in ALL]])
def test_every_pin_of_a_generated_type_says_what_it_is(project):
    """The IDE shows a pin's comment as its tooltip: every event and variable of every type we
    generate has one (modgen/pins.py)."""
    missing = []
    for path in (project_dir(project) / "Type Library").rglob("*.fbt"):
        if {"Std", "Generic"} & set(path.parts):
            continue
        for el in ET.parse(path).getroot().find("InterfaceList").iter():
            if el.tag in ("Event", "VarDeclaration") and not el.get("Comment"):
                missing.append(f"{path.stem}.{el.get('Name')}")
    assert missing == []


@pytest.mark.parametrize("project", [LIBRARY_PROJECT, *[load(p).project for p in ALL]])
def test_group_names_are_not_names_of_blocks_or_pins(project):
    """The IDE refuses a network where a group and a block (or a pin of the type) share a name."""
    from modgen.layout import networks
    clashes = []
    files = [system_file(project), *(project_dir(project) / "Type Library").rglob("*.fbt")]
    for path in files:
        root = ET.parse(path).getroot()
        pins = {el.get("Name") for el in (root.find("InterfaceList") or [])
                for el in el.iter() if el.tag in ("Event", "VarDeclaration")}
        for net in networks(root):
            groups = {g.get("Name") for g in net.findall("Group")}
            blocks = {el.get("Name") for el in net if el.tag in ("FB", "SubApp")}
            clashes += [f"{path.stem}: {n}" for n in groups & (blocks | pins)]
    assert clashes == []


@pytest.mark.parametrize("project", [load(p).project for p in ALL])
def test_every_connection_ends_on_a_pin_its_block_has(project):
    """What the IDE's system check reports as a missing endpoint, found without the IDE: every end of
    every connection of every application is a pin of its block's type (or the resource's START)."""
    from iec61499_mgmt.sysfile import load_application
    files = {path.stem: path for path in (project_dir(project) / "Type Library").rglob("*.fbt")}
    pins = {}

    def has(typ: str, pin: str) -> bool:
        name = typ.rpartition("::")[2]
        if name not in pins:
            iface = ET.parse(files[name]).getroot().find("InterfaceList")
            pins[name] = {el.get("Name") for el in iface.iter() if el.tag in ("Event", "VarDeclaration")}
        return pin in pins[name]

    root = ET.parse(system_file(project)).getroot()
    missing = []
    for app in root.iter("Application"):
        flat = load_application(system_file(project), app.get("Name"))
        for s, d in flat.event_connections + flat.data_connections:
            for end in (s, d):
                block, _, pin = end.rpartition(".")
                if block != "START" and not has(flat.fbs[block], pin):
                    missing.append(f"{app.get('Name')}: {end}")
    assert missing == []


def test_a_module_level_skill_gives_up_all_it_holds_when_a_run_ends():
    """SKILL_Core announces every end of a run (success, failure, abort) and, with ReleaseAll, publishes
    its holder on the module's release channel, which every equipment item listens to."""
    core, _ = st(LIBRARY_PROJECT, "Skills", "SKILL_Core")
    wired = {(c.get("Source"), c.get("Destination")) for c in core.iter("Connection")}
    assert {("Control.RELEASE", "PubRelease.REQ"), ("ReleaseAll", "PubRelease.QI"), ("Holder", "PubRelease.SD_1"),
            ("Control.ReleaseId", "PubRelease.ID")} <= wired
    assert list(groups(core.find("FBNetwork"))) == ["StateMachine", "ModuleViews", "OpcUa", "Release"]
    control, code = st(LIBRARY_PROJECT, "Skills/Base", "SKILL_Control")
    ends = {s.get("Name"): [a.get("Output") for a in s.iter("ECAction")] for s in control.iter("ECState")}
    for state in ("Succeed", "Fail", "Interrupted", "AbortActive"):
        assert "RELEASE" in ends[state], state
    assert 'ReleaseId := CONCAT(CONCAT("loc[", Module), "/release]");' in code
    _, logic = st("FillingModule", "Equipment/Base", "EL_LinearAxis")
    assert 'IdRelease := CONCAT(CONCAT("loc[", Module), "/release]");' in logic


def test_skill_logic_carries_contract_range_and_lock():
    root, code = st("FillerModule", "Skills/Logic", "SL_MoveNeedleDown")
    conditions = {t.get("Condition") for t in root.iter("ECTransition")}
    assert "SAMPLE[(Position >= Distance) OR AtBottom]" in conditions
    assert 'SAMPLE[(EqHolder <> "") AND (EqHolder <> Holder)]' in conditions  # lost the equipment
    assert "C_Holder := Holder;" in code
    assert "IdParams := " in code and "/Parameters/Distance" in code          # SL_ names its OPC UA variables
    skill, _ = st("FillerModule", "Skills", "SK_MoveNeedleDown")
    latch = next(fb for fb in skill.iter("FB") if fb.get("Name") == "Par_Distance")
    assert latch.get("Type") == "modlib::SKILL_Param_LREAL"
    assert {p.get("Name"): p.get("Value") for p in latch.iter("Parameter")} == {"Lower": "0.0", "Upper": "50.0"}


@pytest.mark.parametrize("spec_path", ALL, ids=lambda p: p.stem)
def test_module_level_skills_need_no_type_of_their_own(spec_path):
    """A module level skill is only instances of library types, generic comm FBs and the module's
    skill primitives, so FORTE can create a new one online without being rebuilt."""
    spec = load(spec_path)
    created = flat(spec.project, app_name(spec, next(iter(spec.targets))))[0]
    primitives = {f"{spec.package}::SK_{s}" for s in spec.skills}
    for name in spec.composites:
        types = {t for n, t in created.items() if n.startswith(name + ".")}
        assert types and all(t.startswith(("modlib::", "iec61499::net::")) or t in primitives for t in types), types


def test_composite_parameters_must_not_take_the_names_of_its_blocks():
    data = raw()
    data["composites"]["Fill"]["parameters"]["Execute"] = {"default": 1.0}
    with pytest.raises(ValueError, match="taken by the skill's own blocks"):
        ModuleSpec.model_validate(data)


def servo(tmp_path):
    """The test module with a servo: a command that passes its argument to an output."""
    data = raw()
    data["equipment"]["Arm"] = {"outputs": {"Angle": {"type": "LREAL", "modbus": "h1", "minimum": 0, "maximum": 180}},
                                "commands": {"Detach": {}, "Turn": {"Angle": "Arg"}}}
    data["skills"]["MoveArm"] = {"equipment": "Arm", "command": "Turn", "arg": "Angle", "after": "Settle",
                                 "parameters": {"Angle": {"minimum": 0.0, "maximum": 180.0, "default": 90.0},
                                                "Settle": {"minimum": 0.0, "maximum": 5.0, "default": 1.0}}}
    spec = ModuleSpec.model_validate(data)
    generate(spec, tmp_path / spec.project)
    return tmp_path / spec.project / "Type Library"


def code_of(path):
    root = ET.parse(path).getroot()
    return root, "\n".join(s.text or "" for s in root.iter("ST"))


def test_open_loop_skill_ends_by_time_and_passes_its_argument(tmp_path):
    types = servo(tmp_path)
    root, code = code_of(types / "Skills" / "Logic" / "SL_MoveArm.fbt")
    assert "TimerDT := MUL_TIME(T#1s, Settle);" in code
    assert "C_Arg := Angle;" in code
    conditions = {(t.get("Source"), t.get("Condition")) for t in root.iter("ECTransition")}
    assert ("Running", "TIMER") in conditions
    assert "N_Angle := Arg;" in code_of(types / "Equipment" / "Commands" / "EC_Arm.fbt")[1]
    # A press of a fixed time: no argument, and a final command that takes time itself.
    _, code = st("StopperingModule", "Skills/Logic", "SL_PressStopper")
    assert "TimerDT := MUL_TIME(T#1s, 3.0);" in code and "C_Command := 3;" in code       # Back, when it ends


def test_the_command_table_is_in_the_skills_not_in_the_equipment_io():
    """EC_ (inside every skill of the equipment) turns a command into output values, phase by phase;
    the equipment IO only writes the values its holder sends."""
    _, code = st("StopperingModule", "Equipment/Commands", "EC_Piston")
    assert "IF Phase = 0 THEN\n    N_Retract := TRUE;\n    PhaseDT := T#3000ms;" in code   # Back: in for the stroke, then off
    assert "O_Release := Release AND NOT Timed;" in code                                 # released with the last phase
    logic, code = st("StopperingModule", "Equipment/Base", "EL_Piston")
    assert "Command" not in code and "Phase" not in code and "3000" not in code
    assert "N_Extend := C_Extend;" in code and "O_Extend := O_Extend AND N_Extend;" in code   # break before make
    skill, _ = st("FillingModule", "Skills", "SK_Home")
    assert {fb.get("Name"): fb.get("Type") for fb in skill.iter("FB")}["Driver"] == "filling::EC_LinearAxis"
    assert ("Ending", "EndDone", "PLAYED[Outcome = 1]") in {
        (x.get("Source"), x.get("Destination"), x.get("Condition"))
        for x in st("FillingModule", "Skills/Logic", "SL_Home")[0].iter("ECTransition")}


def test_an_axis_with_a_position_moves_itself_to_where_it_is_told():
    """A stepper axis has no position sensor: the equipment keeps the position (home at the limit
    switch, then the time it steps), and a skill only says where to go."""
    axis = load(SPECS / "filling.yaml").equipment["LinearAxis"]
    assert [s for s, i in axis.inputs.items() if i.computed] == ["ActualPosition", "Homed", "Moving"]
    assert list(axis.commands) == ["Stop", "Up", "Down", "MoveTo"]
    # The skill: where to, as the command's argument; it needs the position to be known and ends there.
    move = load(SPECS / "filling.yaml").skills["MoveAxis"]
    assert (move.command, move.arg, move.precondition) == ("MoveTo", "Position", "Homed")
    assert move.postcondition == "NOT Moving AND ABS(ActualPosition - Position) < 0.001"
    _, code = st("FillingModule", "Equipment/Commands", "EC_LinearAxis")
    assert "N_Move := TRUE;\n  N_Goal := Arg;" in code
    # The equipment: the direction from where it is, the time from the distance, then it is there.
    logic, code = st("FillingModule", "Equipment/Base", "EL_LinearAxis")
    assert "IF N_Goal > ActualPosition THEN\n      MoveDir := 1.0;\n      N_Enable := TRUE;\n      N_Down := TRUE;" in code
    assert "MoveDT := MUL_TIME(T#1s, ABS(N_Goal - ActualPosition) / 12.5);" in code    # the speed in mm/s
    assert "ActualPosition := MoveGoal;\nMoving := FALSE;\nN_Enable := FALSE;" in code
    assert "ELSIF AtHome THEN\n  ActualPosition := 0.0;\n  Homed := TRUE;" in code       # the reference
    transitions = {(x.get("Source"), x.get("Destination"), x.get("Condition")) for x in logic.iter("ECTransition")}
    assert ("START", "MoveEnd", "MOVE_T[Moving AND NOT MoveStart]") in transitions
    assert ("Settled", "MoveGo", "MoveStart") in transitions                              # timed from when the outputs are on
    eq, _ = st("FillingModule", "Equipment", "EQ_LinearAxis")
    blocks = {fb.get("Name"): fb.get("Type") for fb in eq.iter("FB")}
    assert blocks["MoveT"] == "iec61499::events::E_DELAY" and "In_AtHome" in blocks
    assert not {"In_ActualPosition", "In_Homed", "In_Moving"} & set(blocks)               # no IO point behind them
    wired = {(c.get("Source"), c.get("Destination")) for c in eq.iter("Connection")}
    assert {("Logic.MOVE_START", "MoveT.START"), ("MoveT.EO", "Logic.MOVE_T"), ("Logic.ActualPosition", "PubUa.SD_2")} <= wired


@pytest.mark.parametrize("mutate, message", [
    (lambda d: d["skills"]["MoveAxis"]["parameters"]["Position"].update(maximum=80.0), "within the travel"),
    (lambda d: d["skills"]["MoveAxis"].update(command="Down"), "move_to sets these itself"),
    (lambda d: d["skills"]["Home"].update(command="MoveTo"), "is commanded by move_to"),
    (lambda d: d["skills"].update(Lift={"equipment": "Scale", "move_to": "Position",
                                        "parameters": {"Position": {"default": 0.0}}}), "Scale has no position"),
    (lambda d: d["equipment"]["LinearAxis"]["position"].update(home="Weight"), "not a digital input"),
    (lambda d: d["equipment"]["LinearAxis"]["position"].update(increase="Stop"), "have to drive"),
    (lambda d: d["equipment"]["LinearAxis"]["inputs"].update(Homed={}), "has these itself"),
])
def test_invalid_positions_are_rejected(mutate, message):
    data = raw(SPECS / "filling.yaml")
    mutate(data)
    with pytest.raises(ValueError, match=message):
        ModuleSpec.model_validate(data)


def groups(net):
    """Group name -> its members, for a network."""
    found = {g.get("Name"): [] for g in net.findall("Group")}
    for el in net:
        attr = el.find("Attribute[@Name='GroupName']")
        if attr is not None:
            found[attr.get("Value")].append(el.get("Name"))
    return found


def test_blocks_inside_equipment_skills_and_module_level_skills_are_grouped():
    eq, _ = st("StopperingModule", "Equipment", "EQ_Piston")
    assert groups(eq.find("FBNetwork")) == {
        "Core": ["Logic", "Cycle"], "Channels": ["Mode", "SubCmd", "SubRelease", "PubState"],
        "Outputs": ["Out_Retract", "Out_Extend"]}
    axis, _ = st("StopperingModule", "Equipment", "EQ_LinearAxis")
    assert groups(axis.find("FBNetwork")) == {
        "Core": ["Logic", "Cycle", "MoveT"], "Channels": ["Mode", "SubCmd", "SubRelease", "PubState", "PubUa"],
        "Inputs": ["In_AtHome"], "Outputs": ["Out_Enable", "Out_Down", "Out_Step"]}
    skill, _ = st("StopperingModule", "Skills", "SK_PressStopper")
    assert list(groups(skill.find("FBNetwork"))) == ["SkillControl", "Execution", "Equipment"]
    system = ET.parse(system_file("FillingModule")).getroot()
    app = next(a for a in system.iter("Application") if a.get("Name") == "Filling").find("SubAppNetwork")
    inner = next(s for s in app.findall("SubApp") if s.get("Name") == "Dispensing").find("SubAppNetwork")
    assert groups(inner) == {"Core": ["Control"], "Start": ["UaStart", "Volume", "PubParams"],
                             "Sequences": ["Execute", "Stop"], "Results": ["PubResults"]}
    assert all(len(g) for g in groups(inner).values())


@pytest.mark.parametrize("project", [LIBRARY_PROJECT, *[load(p).project for p in ALL]])
def test_projects_follow_the_ide_conventions(project):
    """What the IDE's system editor needs, which its headless checks did not catch."""
    folder = project_dir(project)
    assert not (folder / ".buildpath").exists()          # else the root .sys is outside the type library
    system = ET.parse(folder / f"{project}.sys").getroot()
    for sub in system.iter("SubApp"):
        assert sub.find("InterfaceList") is None and sub.find("SubAppInterfaceList/SubAppEventInputs/SubAppEvent") is not None
    for device in system.iter("Device"):
        assert device.find("Resource/FBNetwork/FB") is None    # mapped blocks are rebuilt by the IDE
        assert device.find("Attribute[@Name='Color']") is not None


def test_filler_maps_one_application_per_target():
    system = ET.parse(system_file("FillerModule")).getroot()
    mappings = {(m.get("From").split(".")[0], m.get("To")) for m in system.iter("Mapping")}
    assert mappings == {("Filler", "FORTE_PC.RES"), ("Filler_pi", "FORTE_PI.RES")}


def test_pi_target_names_each_gpio_line_in_its_io_points_address():
    """On the Pi each IO point sets up its own line: the address names chip, line, bias and polarity
    (no line blocks of their own); the PC reaches the same points over Modbus."""
    created, wired, written = flat("FillerModule", "Filler_pi")
    assert not any(t.endswith(("GPIOChip", "PWMChip")) for t in created.values())
    addresses = {k.split(".")[1]: v for k, v in written.items() if k.endswith("_Address")}
    assert addresses == {"AtTop_Address": "'gpio[0:17:pull_up:active_low]'",
                         "AtBottom_Address": "'gpio[0:27:pull_up:active_low]'",
                         "Down_Address": "'gpio[0:5]'", "Up_Address": "'gpio[0:6]'", "Position_Address": "'sim'"}
    assert ("START.COLD", "Occupation.INIT") in wired                         # the resource's own START
    pc = flat("FillerModule", "Filler")[2]
    assert pc["NeedleAxis.Position_Address"].startswith("'modbus[")


def test_an_io_block_sets_up_the_line_its_address_names():
    """IO_DI, IO_DO and IO_AO hold the GPIOChip or PWMChip that claims their line, initialised
    before the IX/QX/QW binds to it; IO_AI has none (a Pi has no analog inputs)."""
    from modgen.library import route
    for kind, line in (("DI", "GPIOChip"), ("DO", "GPIOChip"), ("AO", "PWMChip"), ("AI", None)):
        root = ET.parse(project_dir(LIBRARY_PROJECT) / "Type Library" / "IO" / f"IO_{kind}.fbt").getroot()
        inner = {fb.get("Name"): fb.get("Type") for fb in root.iter("FB")}
        events = {(c.get("Source"), c.get("Destination")) for c in root.iter("Connection")}
        if line is None:
            assert "Line" not in inner and ("Route.INIT_IO", "Local.INIT") in events
            continue
        assert inner["Line"].endswith(line)
        assert {("Route.INIT_IO", "Line.INIT"), ("Line.INITO", "Local.INIT")} <= events
    assert "LineBias := 2;" in route("DI") and "FIND(Address, ':active_low')" in route("DO")
    assert "Root := STRING_TO_WSTRING" in route("AO") and "gpio[" not in route("AI")


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


def test_regeneration_keeps_each_applications_own_layout(tmp_path):
    """Blocks of the same name in two applications keep their own places, and a group its size."""
    spec = load(FILLER)
    project, manifest = tmp_path / spec.project, tmp_path / "manifest.json"
    generate(spec, project, manifest)
    path = project / f"{spec.project}.sys"
    doc = ET.parse(path)
    apps = {a.get("Name"): a.find("SubAppNetwork") for a in doc.getroot().iter("Application")}
    next(fb for fb in apps["Filler_pi"].iter("FB") if fb.get("Name") == "Module").set("x", "4321.5")
    next(g for g in apps["Filler"].iter("Group") if g.get("Name") == "ModuleLevel").set("width", "7093.33")
    doc.write(path, encoding="utf-8", xml_declaration=True)
    generate(spec, project, manifest)
    apps = {a.get("Name"): a.find("SubAppNetwork") for a in ET.parse(path).getroot().iter("Application")}
    module = {name: next(fb for fb in net.iter("FB") if fb.get("Name") == "Module").get("x") for name, net in apps.items()}
    assert module["Filler_pi"] == "4321.5" and module["Filler"] != "4321.5"
    assert next(g for g in apps["Filler"].iter("Group") if g.get("Name") == "ModuleLevel").get("width") == "7093.33"


def boxes(net, size, labelled=False):
    """Each block of a network with its box (left, top, right, bottom), groups' offsets added (a
    grouped block is placed below the group's comment); ``labelled``: with the room for its
    connection labels and parameter values on either side."""
    from modgen.layout import group_of, header, measure
    groups = {g.get("Name"): (float(g.get("x")), float(g.get("y")) + header(g)) for g in net.findall("Group")}
    box = measure(net, size)
    found = {}
    for el in net:
        if el.tag in ("FB", "SubApp"):
            gx, gy = groups.get(group_of(el), (0.0, 0.0))
            left, w, h, right = box(el) if labelled else (0.0, *size(el)[1:], 0.0)
            x, y = gx + float(el.get("x")), gy + float(el.get("y"))
            found[el.get("Name")] = (x - left, y, x + w + right, y + h)
    return found


def outside(net, size):
    """The blocks of a network that do not fit in their group, with their labels."""
    from modgen.layout import group_of
    found = boxes(net, size, labelled=True)
    groups = {g.get("Name"): g for g in net.findall("Group")}
    return [el.get("Name") for el in net if el.tag in ("FB", "SubApp") and group_of(el) in groups
            and not (lambda g, b: float(g.get("x")) <= b[0] and b[2] <= float(g.get("x")) + float(g.get("width"))
                     and b[3] <= float(g.get("y")) + float(g.get("height")))(groups[group_of(el)], found[el.get("Name")])]


def overlaps(found):
    names = sorted(found)
    return [(a, b) for i, a in enumerate(names) for b in names[i + 1:]
            if found[a][0] < found[b][2] and found[b][0] < found[a][2] and found[a][1] < found[b][3] and found[b][1] < found[a][3]]


@pytest.mark.parametrize("project", ["FillingModule", "StopperingModule", "FillerModule"])
def test_no_two_blocks_overlap_in_any_network(project):
    """By the sizes the IDE draws blocks at (its own overlap check agrees); in the applications and
    inside every subapplication."""
    from modgen.layout import Sizer, networks
    size = Sizer(project_dir(project) / "Type Library")
    for net in networks(ET.parse(system_file(project)).getroot()):
        assert overlaps(boxes(net, size)) == []


@pytest.mark.parametrize("project", ["FillingModule", "StopperingModule", "FillerModule"])
def test_arranged_layouts_get_room_for_labels_and_comments(project):
    """A layout arranged in the IDE is spread where it is too tight: in the applications and inside
    every subapplication no block nor its labels overlap another, each fits in its group below the
    group's comment, and no two groups overlap."""
    from modgen.layout import Sizer, networks
    size = Sizer(project_dir(project) / "Type Library")
    for net in networks(ET.parse(system_file(project)).getroot()):
        groups = {g.get("Name"): (float(g.get("x")), float(g.get("y")), float(g.get("x")) + float(g.get("width")),
                                  float(g.get("y")) + float(g.get("height"))) for g in net.findall("Group")}
        assert (overlaps(boxes(net, size, labelled=True)), outside(net, size), overlaps(groups)) == ([], [], [])


@pytest.mark.parametrize("project", [LIBRARY_PROJECT, *[load(p).project for p in ALL]])
def test_composite_types_leave_room_for_labels_and_comments(project):
    """Inside every composite type no block nor the labels of its hidden connections overlap
    another, and each block with its labels fits in its group, below the group's comment."""
    from modgen.layout import Sizer
    size = Sizer(project_dir(project) / "Type Library")
    for path in (project_dir(project) / "Type Library").rglob("*.fbt"):
        net = ET.parse(path).getroot().find("FBNetwork")
        if net is None or {"Std", "Generic"} & set(path.parts):
            continue
        assert (path.stem, overlaps(boxes(net, size, labelled=True)), outside(net, size)) == (path.stem, [], [])


def test_a_layout_too_tight_is_spread_keeping_its_order(tmp_path):
    """Blocks arranged in the IDE too close for their labels move apart, each staying in its row and
    in the order they had."""
    from modgen.layout import Sizer
    spec = load(FILLER)
    project = tmp_path / spec.project
    generate(spec, project, tmp_path / "manifest.json")
    path = project / f"{spec.project}.sys"
    doc = ET.parse(path)
    net = next(a for a in doc.getroot().iter("Application") if a.get("Name") == "Filler").find("SubAppNetwork")
    squeezed = {el.get("Name"): (float(el.get("x")) / 4, el.get("y")) for el in net if el.tag in ("FB", "SubApp")}
    for el in net:
        if el.get("Name") in squeezed:
            el.set("x", str(squeezed[el.get("Name")][0]))
    doc.write(path, encoding="utf-8", xml_declaration=True)
    generate(spec, project, tmp_path / "manifest.json")
    net = next(a for a in ET.parse(path).getroot().iter("Application") if a.get("Name") == "Filler").find("SubAppNetwork")
    assert overlaps(boxes(net, Sizer(project / "Type Library"), labelled=True)) == [] and outside(net, Sizer(project / "Type Library")) == []
    after = {el.get("Name"): (float(el.get("x")), el.get("y")) for el in net if el.tag in ("FB", "SubApp")}
    assert {k: y for k, (_, y) in after.items()} == {k: y for k, (_, y) in squeezed.items()}
    order = lambda placed: sorted(placed, key=lambda k: (placed[k][1], placed[k][0]))  # noqa: E731
    assert order(after) == order(squeezed)


def test_a_skill_added_later_gets_a_free_place_in_its_group(tmp_path):
    """Regenerating keeps the layout arranged in the IDE; a new module level skill goes below the
    others in its group, which grows to hold it."""
    from modgen.layout import Sizer
    spec = load(FILLER)
    project = tmp_path / spec.project
    generate(spec, project, tmp_path / "manifest.json")
    path = project / f"{spec.project}.sys"
    app = lambda: next(a for a in ET.parse(path).getroot().iter("Application") if a.get("Name") == "Filler")  # noqa: E731
    before = {el.get("Name"): (el.get("x"), el.get("y")) for el in app().find("SubAppNetwork") if el.tag in ("FB", "SubApp")}
    data = yaml.safe_load(FILLER.read_text(encoding="utf-8"))
    data["composites"]["FillTwice"] = {**next(iter(data["composites"].values()))}
    generate(ModuleSpec.model_validate(data), project, tmp_path / "manifest.json")
    net = app().find("SubAppNetwork")
    after = {el.get("Name"): (el.get("x"), el.get("y")) for el in net if el.tag in ("FB", "SubApp")}
    assert {k: after[k] for k in before} == before
    group = next(g for g in net.findall("Group") if g.get("Name") == "ModuleLevelSkills")
    found = boxes(net, Sizer(project / "Type Library"))
    assert overlaps(found) == []
    left, top, right, bottom = found["FillTwice"]
    assert float(group.get("y")) < top and bottom <= float(group.get("y")) + float(group.get("height"))


def test_the_resources_start_block_starts_the_init_chain():
    """No E_RESTART of the module's own: the resource's START (COLD, WARM) drives the head of the chain."""
    system = ET.parse(system_file("FillingModule")).getroot()
    assert not [fb for fb in system.iter("FB") if fb.get("Type") == "iec61499::events::E_RESTART"]
    links = {d.get("Name"): [(c.get("Source"), c.get("Destination")) for c in d.iter("Connection")]
             for d in system.iter("Device")}
    assert links == {"FORTE_PC": [("START.COLD", "Filling.Occupation.INIT"), ("START.WARM", "Filling.Occupation.INIT")],
                     "FORTE_PI": [("START.COLD", "Filling_pi.Occupation.INIT"), ("START.WARM", "Filling_pi.Occupation.INIT")]}


def test_application_is_grouped():
    """Five groups, top to bottom (module level, module level skills, procedures, skill primitives, equipment IO);
    every block of the application in one of them."""
    system = ET.parse(system_file("FillingModule")).getroot()
    net = next(a for a in system.iter("Application") if a.get("Name") == "Filling").find("SubAppNetwork")
    groups = [g.get("Name") for g in net.findall("Group")]
    assert groups == ["ModuleLevel", "ModuleLevelSkills", "Procedures", "SkillPrimitives", "EquipmentIO"]
    member = {el.get("Name"): el.find("Attribute[@Name='GroupName']").get("Value")
              for el in net if el.tag in ("FB", "SubApp")}
    assert member["Dispensing"] == "ModuleLevelSkills" and member["MoveAxis"] == "SkillPrimitives"
    assert member["LinearAxis"] == "EquipmentIO" and member["Resetting"] == "Procedures"



@pytest.mark.parametrize("project", [LIBRARY_PROJECT, *[load(p).project for p in ALL]])
def test_every_connection_is_hidden(project):
    """A hidden connection is drawn as a label at both ends: in the applications, the subapplications,
    the resources and every composite type (which cannot be edited in the IDE to hide them)."""
    files = [system_file(project), *(project_dir(project) / "Type Library").rglob("*.fbt")]
    shown = [f"{path.stem}: {c.get('Source')} -> {c.get('Destination')}" for path in files
             if not {"Std", "Generic"} & set(path.parts)
             for c in ET.parse(path).getroot().iter("Connection")
             if c.find("Attribute[@Name='Visible']") is None]
    assert shown == []


def test_stop_sequence_nodes_do_not_collide_with_the_stop_method():
    """A module level skill's stop sequence publishes below /Skills/<name>/Stopping: FORTE would put an
    object /Skills/<name>/Stop inside the skill's Stop method node."""
    from iec61499_mgmt.sysfile import flatten
    from modgen.module import application
    spec = load(SPECS / "filling.yaml")
    app = flatten(application(ET.Element("System"), spec, "pc").find("SubAppNetwork"))
    paths = {k: v for k, v in app.parameters.items() if k.startswith("Dispensing.Stop.") and k.endswith(".UaPath")}
    assert paths == {"Dispensing.Stop.Home.UaPath": '"/Skills/Dispensing/Stopping/Home"'}


def test_a_module_names_its_pwm_channels_as_its_board_does():
    """Channel 0 is GPIO18 on every board; a Raspberry Pi 5 numbers that pin 2. The stepper driver's
    enable is inverted: the line is low while the motor is on."""
    assert load(SPECS / "filling.yaml").targets["pi"].board == "pi5"
    written = flat("FillingModule", "Filling_pi")[2]
    # Channel 2 of the PWM chip, 2 kHz, the PWM folder as the FORTE container sees it.
    assert written["LinearAxis.Step_Address"] == "'pwm[0:2:500000:/hostsys/class/pwm]'"
    assert written["LinearAxis.Enable_Address"] == "'gpio[0:17:active_low]'"
    assert written["LinearAxis.Down_Address"] == "'gpio[0:27]'"
    assert written["LinearAxis.AtHome_Address"] == "'gpio[0:23:pull_up:active_low]'"     # a switch to GND
    assert flat("StopperingModule", "Stoppering_pi")[2]["LinearAxis.Step_Address"].startswith("'pwm[0:2:")  # a Pi 5 too
