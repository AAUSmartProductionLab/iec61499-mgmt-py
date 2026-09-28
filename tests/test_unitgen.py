"""Offline tests of the unit generator: spec validation, reproducible output, flattened system."""
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest
import yaml

from iec61499_mgmt.sysfile import load_application
from unitgen import generate, load
from unitgen.spec import UnitSpec

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "units" / "filler.yaml"


def raw():
    """The filler spec as plain data, for mutation."""
    return yaml.safe_load(SPEC.read_text(encoding="utf-8"))


@pytest.mark.parametrize("mutate, message", [
    (lambda d: d["skills"]["MoveNeedleDown"].update(ensures="Position >= Depth"), "unknown names"),
    (lambda d: d["skills"]["MoveNeedleDown"].update(command="Stop"), "not a driving command"),
    (lambda d: d["skills"]["MoveNeedleDown"].update(equipment="Pump"), "unknown equipment"),
    (lambda d: d["skills"]["MoveNeedleDown"]["parameters"]["Distance"].update(default=80.0), "default outside"),
    (lambda d: d["equipment"]["NeedleAxis"].update(commands={"Down": ["Down"], "Stop": []}), "safe state"),
    (lambda d: d["equipment"]["NeedleAxis"]["commands"].update(Both=["Down", "Lift"]), "unknown outputs"),
    (lambda d: d["skills"]["MoveNeedleDown"]["parameters"].update(AtTop={"type": "BOOL", "default": True}),
     "shadow"),
    (lambda d: d["procedures"].update(Execute=["MoveNeedleDown", "MoveNeedleDown"]), "appears twice"),
    (lambda d: d["equipment"]["NeedleAxis"]["inputs"]["AtTop"].update(modbus="i0"), "BOOL inputs"),
])
def test_invalid_specs_are_rejected(mutate, message):
    data = raw()
    mutate(data)
    with pytest.raises(ValueError, match=message):
        UnitSpec.model_validate(data)


def canonical(path):
    """File content independent of formatting: the 4diac IDE rewrites generated XML on import
    (tabs, CDATA, empty elements), so XML is compared in canonical form."""
    data = path.read_bytes()
    if data.lstrip().startswith(b"<"):
        return ET.canonicalize(data.decode("utf-8-sig"), strip_text=True)
    return data.decode("utf-8-sig").strip()


def tree(root):
    """Relative path -> canonical content of every file below ``root``."""
    # The IDE keeps per-type documentation in .<Type>.fbt.assets folders; they are not generated.
    return {p.relative_to(root).as_posix(): canonical(p) for p in sorted(root.rglob("*"))
            if p.is_file() and not any(part.endswith(".assets") for part in p.parts)}


def test_committed_project_matches_the_generator(tmp_path):
    spec = load(SPEC)
    generate(spec, tmp_path / spec.project, tmp_path / "manifest.json")
    assert tree(tmp_path / spec.project) == tree(ROOT / "4diac" / spec.project)
    assert (tmp_path / "manifest.json").read_bytes() == (ROOT / "4diac" / "tools" / "manifests" /
                                                         f"{spec.project}.json").read_bytes()


def test_system_flattens_to_unit_equipment_and_procedure():
    app = load_application(ROOT / "4diac" / "FillerUnit" / "FillerUnit.sys", "Filler")
    commands = app.commands("RES")
    created = {c.name: c.type for c in commands if c.op == "create_fb"}
    assert created == {"Boot": "iec61499::events::E_RESTART", "Occupation": "unitlib::UNIT_Occupation",
                       "Unit": "unitlib::UNIT_StateManager", "NeedleAxis": "filler::EQ_NeedleAxis",
                       "Execute.MoveNeedleDown": "filler::SK_MoveNeedleDown"}
    wired = {(c.source, c.destination) for c in commands if c.op == "connect"}
    # The procedure subapp dissolves: the unit starts the skill, the skill reports to the unit.
    assert {("Unit.EXECUTE", "Execute.MoveNeedleDown.START"),
            ("Execute.MoveNeedleDown.SUCCESS", "Unit.EXECUTE_DONE"),
            ("Execute.MoveNeedleDown.FAILURE", "Unit.EXECUTE_FAILED")} <= wired
    # No wiring between skill, equipment and occupation: they meet on local channels.
    assert not {w for w in wired if "NeedleAxis" in w[0] + w[1] and "INIT" not in w[0] + w[1]}
    written = {c.destination: c.value for c in commands if c.op == "write"}
    assert written["Execute.MoveNeedleDown.UaPath"] == '"/Execute/MoveNeedleDown"'
    assert "Execute.MoveNeedleDown.Distance" not in written      # the type's default applies


def test_skill_logic_carries_contract_range_and_session_check():
    root = ET.parse(ROOT / "4diac" / "FillerUnit" / "Type Library" / "Skills" / "Logic" / "SL_MoveNeedleDown.fbt")
    code = "\n".join(st.get("Text") or st.text or "" for st in root.iter("ST"))
    assert "(S_Distance >= 0.0) AND (S_Distance <= 50.0)" in code
    assert 'Owned := (Session = Owner) AND (Owner <> "")' in code
    conditions = {t.get("Condition") for t in root.iter("ECTransition")}
    assert "SAMPLE[(Position >= Distance) OR AtBottom]" in conditions


def test_project_follows_the_ide_conventions():
    """What the IDE's system editor needs, which its headless checks did not catch."""
    project = ROOT / "4diac" / "FillerUnit"
    assert not (project / ".buildpath").exists()          # else the root .sys is outside the type library
    system = ET.parse(project / "FillerUnit.sys").getroot()
    for sub in system.iter("SubApp"):
        assert sub.find("InterfaceList") is None and sub.find("SubAppInterfaceList/SubAppEventInputs/SubAppEvent") is not None
    resource = system.find("Device/Resource/FBNetwork")
    assert len(resource) == 0                              # mapped blocks are rebuilt by the IDE
    assert {m.get("To") for m in system.iter("Mapping")} == {"FORTE_PC.RES"}
    assert system.find("Device/Attribute[@Name='Color']") is not None
