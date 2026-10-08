"""modsync offline: the structure of a module read from its program by the module rules
(docs/module-rules.md), without the module spec the program was generated from.

The program is the one modgen generates (what a FORTE that runs it reports) and the type files
of the committed project.
"""
import pytest
import yaml

from modgen import SPECS, load, project_dir, specs
from modgen.spec import ModuleSpec
from modsync.compare import expected
from modsync.structure import read_primitives, stated, structure

FILLING = SPECS / "filling.yaml"


def read(spec: ModuleSpec, values: dict | None = None) -> dict:
    """The structure of the program ``spec`` generates for the Pi; ``values``: inputs as read from
    a running module instead of as the program wrote them."""
    app = expected(spec, "pi")
    written = {**app.parameters, **(values or {})}
    return structure(app.fbs, [*app.event_connections, *app.data_connections], written.get,
                     read_primitives(project_dir(spec.project) / "Type Library"))


@pytest.mark.parametrize("path", specs(), ids=lambda p: p.stem)
def test_the_program_tells_what_the_spec_states(path):
    spec = load(path)
    assert read(spec) == stated(spec)


def test_what_a_module_is_made_of():
    found = read(load(FILLING))
    assert (found["module"], found["package"], found["opcua_root"]) == ("Filling", "filling", "/Objects/Filling")
    assert found["equipment"] == ["LinearAxis", "Pump", "Scale"]
    assert all(s["offered"] for s in found["skills"].values())
    dispense = found["skills"]["Dispense"]
    assert dispense["parameters"] == {"Volume": {"type": "LREAL", "default": 1.0, "minimum": 0.5, "maximum": 10.0},
                                      "FlowRate": {"type": "LREAL", "default": 1.0, "minimum": 0.1, "maximum": 5.0}}
    assert dispense["equipment"] == "Pump"                   # no output yet: dispensing is a time
    move = found["skills"]["MoveAxis"]
    assert move["offered"] and move["equipment"] == "LinearAxis" and move["timeout"] == 8000
    assert move["parameters"] == {"Position": {"type": "LREAL", "default": 0.0, "minimum": 0.0, "maximum": 60.0}}
    assert found["skills"]["Weigh"]["results"] == ["Weight"]
    dispensing = found["composites"]["Dispensing"]
    assert dispensing["offered"] and dispensing["results"] == {"Weight": "Weigh.Weight"}
    assert dispensing["parameters"] == {"Volume": {"type": "LREAL", "default": 1.0, "minimum": 0.5, "maximum": 10.0}}
    assert [s["skill"] for s in dispensing["execute"]] == ["MoveAxis", "Dispense", "MoveAxis", "Weigh"]
    # One skill used twice: each step has its own name and its own position, a constant of the step.
    assert [(s["name"], s["bind"]) for s in dispensing["execute"] if s["skill"] == "MoveAxis"] == \
        [("NeedleDown", {"Position": 40.0}), ("NeedleUp", {"Position": 0.0})]
    # The volume is the skill's parameter, the flow rate a constant of the step.
    assert dispensing["execute"][1]["bind"] == {"Volume": "Volume", "FlowRate": 1.0}
    assert [s["skill"] for s in dispensing["stop"]] == ["Home"]
    assert {n: [s["skill"] for s in p] for n, p in found["procedures"].items()} == \
        {"Resetting": ["Home", "Tare"], "Stopping": ["Home"]}


def test_a_skill_added_to_the_program_is_read_like_the_others():
    """A module level skill is instances and connections only, so the type files stay as they are."""
    data = yaml.safe_load(FILLING.read_text(encoding="utf-8"))
    data["composites"]["DoubleDose"] = {
        "parameters": {"Dose": {"unit": "mL", "minimum": 0.5, "maximum": 10.0, "default": 0.5}},
        "execute": [{"MoveAxis": {"Position": 40.0}, "as": "NeedleDown"}, {"Dispense": {"Volume": "Dose", "FlowRate": 1.0}},
                    {"Dispense": {"Volume": "Dose", "FlowRate": 1.0}}, {"MoveAxis": {"Position": 0.0}, "as": "NeedleUp"},
                    "Weigh"],
        "stop": ["Home"], "results": {"Weight": "Weigh.Weight"}}
    spec = ModuleSpec.model_validate(data)
    found = read(spec)
    assert found == stated(spec) and list(found["composites"]) == ["Dispensing", "DoubleDose"]
    doses = [s for s in found["composites"]["DoubleDose"]["execute"] if s["skill"] == "Dispense"]
    assert [s["name"] for s in doses] == ["Dispense", "Dispense_2"]
    assert all(s["bind"] == {"Volume": "Dose", "FlowRate": 1.0} for s in doses)


def test_a_primitive_the_module_does_not_offer_is_read_from_its_type_file():
    """It has no instance of its own in the program: only its type file tells of it."""
    data = yaml.safe_load(FILLING.read_text(encoding="utf-8"))
    data["skills"]["Dispense"]["offered"] = False
    spec = ModuleSpec.model_validate(data)
    found = read(spec)
    assert found == stated(spec) and not found["skills"]["Dispense"]["offered"]
    assert found["skills"]["Dispense"]["timeout"] is None


def test_values_are_the_ones_the_module_runs_with():
    spec = load(SPECS / "stoppering.yaml")
    step = spec.composites["Stoppering"].execute[0]
    assert step.skill == "MoveAxis" and step.bind
    # A constant changed online shows; a limit that was never declared reads as the type's own.
    found = read(spec, {f"Stoppering.Execute.{step.name}.Position": "35.0"})
    assert found["composites"]["Stoppering"]["execute"][0]["bind"]["Position"] == 35.0
    data = yaml.safe_load(FILLING.read_text(encoding="utf-8"))
    data["composites"]["Settle"] = {"parameters": {"Rounds": {"minimum": 0.0, "default": 1.0}}, "execute": ["Tare"]}
    unlimited = ModuleSpec.model_validate(data)
    found = read(unlimited, {"Settle.Rounds.Upper": "1.0E308"})
    assert found["composites"]["Settle"]["parameters"]["Rounds"]["maximum"] is None and found == stated(unlimited)
