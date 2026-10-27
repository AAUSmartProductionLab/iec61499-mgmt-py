"""Rule set 2: a module level skill's flow with parallel blocks and decisions, as the generator makes it
and as modsync reads it back from the program, without the spec.

A flow is read from what FORTE reports of a program (instances, connections, values) by the module
rules alone; it has to be what the spec states, for every shape a flow can take.
"""
import pytest
import yaml

from modgen import SPECS
from modgen.spec import ModuleSpec, always, walk
from modsync.compare import Candidate
from modsync.structure import canonical, shape, stated, structure

FILLING = SPECS / "filling.yaml"
LIGHT = {"operand": "Weigh.Weight", "op": "lt", "value": 1.9}
BIG = {"operand": "Volume", "op": "gt", "value": 4.0}
SMALL = {"operand": "Volume", "op": "lte", "value": 1.0}
EMPTY = {"operand": "Weigh.Weight", "op": "lt", "value": 0.1}

FLOWS = {
    "decision": [{"MoveAxis": {"Position": 40.0}, "as": "NeedleDown"}, {"Dispense": {"Volume": "Volume", "FlowRate": 1.0}}, "Weigh",
                 {"if": LIGHT, "then": [{"Dispense": {"Volume": 0.5, "FlowRate": 1.0}, "as": "TopUp"}, {"Weigh": {}, "as": "Reweigh"}],
                  "as": "Light"}, "Home"],
    "else": [{"Dispense": {"Volume": "Volume", "FlowRate": 1.0}}, "Weigh",
             {"if": LIGHT, "then": [{"Dispense": {"Volume": 0.5, "FlowRate": 1.0}, "as": "TopUp"}], "else": ["Home"], "as": "Light"}],
    "first and last": [{"if": BIG, "then": ["Tare"], "as": "Big"}, {"Dispense": {"Volume": "Volume", "FlowRate": 1.0}}, "Weigh",
                       {"if": EMPTY, "then": ["Home"], "else": [{"MoveAxis": {"Position": 10.0}}], "as": "Empty"}],
    "all of any": [{"Dispense": {"Volume": "Volume", "FlowRate": 1.0}}, "Weigh",
                   {"if": {"all": [LIGHT, {"any": [BIG, SMALL]}]}, "then": ["Home"], "as": "Odd"}],
    "any of all": [{"Dispense": {"Volume": "Volume", "FlowRate": 1.0}}, "Weigh",
                   {"if": {"any": [{"all": [LIGHT, BIG]}, SMALL, {"all": [EMPTY, {"operand": "Volume", "op": "ne", "value": 2.0}]}]},
                    "then": ["Home"], "as": "Odd"}],
    "parallel": [{"parallel": [["Home"], [{"Dispense": {"Volume": "Volume", "FlowRate": 1.0}}], ["Tare"]], "as": "AtOnce"}, "Weigh"],
    "decision in a branch": [{"parallel": [["Home", {"MoveAxis": {"Position": 40.0}}],
                                           ["Tare", "Weigh", {"if": EMPTY, "then": [{"Weigh": {}, "as": "Again"}], "as": "Check"}]],
                              "as": "Both"},
                             {"Dispense": {"Volume": "Volume", "FlowRate": 1.0}}],
    "parallel in a decision": [{"Dispense": {"Volume": "Volume", "FlowRate": 1.0}}, "Weigh",
                               {"if": LIGHT, "then": [{"parallel": [["Home"], ["Tare"]], "as": "Reset"}], "else": ["Home"],
                                "as": "Light"}],
}


def composed(flow: list) -> ModuleSpec:
    """The filling module with one more skill, Flow, running ``flow``."""
    data = yaml.safe_load(FILLING.read_text(encoding="utf-8"))
    data["composites"]["Flow"] = {"parameters": {"Volume": {"unit": "mL", "minimum": 0.5, "maximum": 5.0, "default": 1.0}},
                                  "execute": flow, "stop": ["Home"]}
    return ModuleSpec.model_validate(data)


def read_back(spec: ModuleSpec) -> dict:
    """The structure of the program the spec generates, read as from FORTE."""
    app = Candidate(None, spec, "pi").app
    primitives = {n: {"package": spec.package, **{k: v for k, v in d.items() if k != "offered"}}
                  for n, d in stated(spec)["skills"].items()}
    return structure(app.fbs, set(app.event_connections + app.data_connections), app.parameters.get, primitives)


@pytest.mark.parametrize("name", FLOWS)
def test_a_flow_is_read_back_from_its_program(name):
    spec = composed(FLOWS[name])
    assert read_back(spec) == stated(spec)


def test_the_blocks_of_a_flow_are_library_blocks_named_by_its_nodes():
    app = Candidate(None, composed(FLOWS["decision in a branch"]), "pi").app
    blocks = {n.removeprefix("Flow.Execute."): t for n, t in app.fbs.items() if n.startswith("Flow.Execute.") and "::SK_" not in t}
    assert blocks == {"Both": "modlib::SKILL_Join2", "Check": "modlib::SKILL_Merge", "Check_C1": "modlib::SKILL_Condition_LREAL",
                      "Fail1": "modlib::SKILL_FailMerge", "Both_Fail2_1": "modlib::SKILL_FailMerge",
                      "Both_Fail2_2": "modlib::SKILL_FailMerge", "Both_Fail1_1": "modlib::SKILL_FailMerge"}
    values = app.parameters
    assert (values["Flow.Execute.Check_C1.Operator"], values["Flow.Execute.Check_C1.Expected"]) == ("'lt'", "0.1")
    connected = set(app.event_connections)
    # The join first, then the branches; a failure halts the other branch.
    assert ("Flow.Execute.Both.HALT", "Flow.Execute.Home.HALT") in connected
    # Every step keeps the equipment: Control gives everything up when the run ends.
    assert all(values[f"Flow.Execute.{s.name}.ReleaseAfter"] == "FALSE" for s in walk(composed(FLOWS["decision in a branch"]).composites["Flow"].execute))


def test_a_flow_the_module_cannot_run_is_refused():
    with pytest.raises(ValueError, match="two branches use"):
        composed([{"parallel": [["Home"], [{"MoveAxis": {"Position": 10.0}}]]}])
    with pytest.raises(ValueError, match="neither a parameter of the skill nor a result of a step"):
        composed([{"if": LIGHT, "then": ["Home"]}, "Weigh"])
    with pytest.raises(ValueError, match="compared with"):
        composed(["Weigh", {"if": {"operand": "Weigh.Weight", "op": "lt", "value": True}, "then": ["Home"]}])
    with pytest.raises(ValueError, match="names used twice"):
        composed(["Weigh", {"if": LIGHT, "then": ["Home"], "as": "Weigh"}])


def test_results_come_from_steps_on_every_path():
    flow = FLOWS["decision"]
    assert [s.name for s in always(composed(flow).composites["Flow"].execute)] == ["NeedleDown", "Dispense", "Weigh", "Home"]
    data = yaml.safe_load(FILLING.read_text(encoding="utf-8"))
    data["composites"]["Flow"] = {"execute": flow, "parameters": {"Volume": {"minimum": 0.5, "maximum": 5.0, "default": 1.0}},
                                  "results": {"Weight": "Reweigh.Weight"}}
    with pytest.raises(ValueError, match="runs on every path"):
        ModuleSpec.model_validate(data)


def test_conditions_compare_alike_however_they_are_grouped():
    a, b, c = LIGHT, BIG, SMALL
    assert canonical({"all": [a, {"all": [b, c]}]}) == {"all": [a, b, c]}
    assert canonical({"any": [{"any": [a]}, b]}) == {"any": [a, b]}
    assert canonical({"all": [{"any": [a, b]}]}) == {"any": [a, b]}
    assert shape(stated(composed(FLOWS["else"]))["composites"]["Flow"]["execute"])[2][0] == "decision"


# From the AAS: described, created online, recorded ---------------------------------------------------

def test_a_flow_described_in_the_aas_is_read_and_created_online():
    """The AAS of a module with skills that run decisions and parallel blocks (as modreg writes them)
    describes what the spec states; on a module delivered without them, they are created online, and
    the program is the one the generator makes."""
    pytest.importorskip("aas_model")
    from modsync import desired
    from test_modsync import FakeForte, filling
    from test_modsync_desired import aas, wanting

    spec = composed(FLOWS["decision in a branch"])
    module, components = aas(spec)
    found = desired.described(module, components, spec.module, spec.package, spec.opcua_root)
    assert stated(found)["composites"]["Flow"] == stated(spec)["composites"]["Flow"]

    delivered, _ = aas(Candidate(None, ModuleSpec.model_validate(yaml.safe_load(FILLING.read_text(encoding="utf-8"))), "pi").spec)
    wanted, components = wanting(spec, delivered)
    forte = FakeForte(filling())
    assert desired.read(forte, "pi", 61499, wanted, components).differences.create == ["Flow"]
    done, after = desired.reconfigure(forte, "pi", 61499, wanted, components)
    assert done[0].startswith("create Flow: ") and after.differences.empty
    made = Candidate(None, spec, "pi").app
    assert forte.fbs == made.fbs and forte.connections == set(made.event_connections + made.data_connections)
    # Recorded: built, and every block of it is named, the conditions with their decision.
    recorded, config = desired.record(wanted, after, done)
    assert desired.deployment(desired.at(desired.submodel(recorded, "Skills"), "Flow")) == "Built"
    paths = {p_ for p_, _, _ in desired.instances(config)}
    assert {"Flow.Control", "Flow.Execute.Both", "Flow.Execute.Check", "Flow.Execute.Check_C1", "Flow.Execute.Again"} <= paths


def test_a_condition_in_the_aas_names_what_it_compares():
    pytest.importorskip("aas_model")
    from modsync import desired
    from test_modsync_desired import aas

    spec = composed(FLOWS["any of all"])
    module, components = aas(spec)
    steps = desired.at(desired.submodel(module, "Skills"), "Flow", "Start", "Steps")
    odd = next(s for s in steps["value"] if desired.at(s, "NodeId")["value"] == "Odd")
    assert desired.at(odd, "Kind")["value"] == "conditional"
    condition = desired.at(odd, "Condition")
    assert desired.at(condition, "ConditionType")["value"] == "any"
    first = desired.at(condition, "Conditions", "Condition_0000", "Conditions", "Condition_0000")
    assert [desired.at(first, k)["value"] for k in ("ConditionType", "Operator", "Unit")] == ["comparison", "lt", "g"]
    assert [desired.at(first, "Operand", k)["value"] for k in ("OperandType", "StepId", "OutputId")] == ["output", "Weigh", "Weight"]
    second = desired.at(condition, "Conditions", "Condition_0001")
    assert desired.target(desired.at(second, "Operand", "SourceElement"))[-1] == "Volume"
    assert desired.at(second, "Expected", "Value")["value"] == "1.0"
