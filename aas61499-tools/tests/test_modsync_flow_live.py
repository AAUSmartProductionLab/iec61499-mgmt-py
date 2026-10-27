"""Rule set 2 on FORTE: skills whose steps run in a decision and in a parallel block, described in the
AAS, created online while the module runs, and run over OPC UA; the branch a condition chooses runs,
the other does not.

    python -m pytest aas61499-tools/tests/test_modsync_flow_live.py --module-forte-exe <a FORTE with ModLib's flow blocks>
"""
import time

import pytest
import yaml

pytest.importorskip("aas_model")

from modgen import SPECS                                                     # noqa: E402
from modgen.library import SKILL_STATES, STATES                              # noqa: E402
from modgen.spec import ModuleSpec                                           # noqa: E402
from modsync.desired import read, reconfigure, record                        # noqa: E402
from test_modsync_desired import aas, wanting                                # noqa: E402
from test_modsync_live import module                                         # noqa: E402, F401  (the fixture)

DISPENSE = {"Dispense": {"Volume": "Volume", "FlowRate": 1.0}}


def seen(states: list, state: int, within: float = 3.0) -> bool:
    """Whether ``state`` was notified, waiting a little: a step's state may arrive after its skill's."""
    deadline = time.monotonic() + within
    while state not in states and time.monotonic() < deadline:
        time.sleep(0.05)
    return state in states


def flow_spec() -> ModuleSpec:
    """The filling module with two skills more. The simulated scale reads 2.0 g whatever was filled,
    so TopUp (below 2.5 g) runs and Again (below 1.0 g) does not; Ready homes and tares at once."""
    data = yaml.safe_load((SPECS / "filling.yaml").read_text(encoding="utf-8"))
    volume = {"unit": "mL", "minimum": 0.5, "maximum": 5.0, "default": 1.0}
    data["composites"]["Checked"] = {
        "parameters": {"Volume": volume}, "results": {"Weight": "Weigh.Weight"}, "stop": ["Home"],
        "execute": [{"MoveAxis": {"Position": 40.0}, "as": "NeedleDown"}, DISPENSE, "Weigh",
                    {"if": {"operand": "Weigh.Weight", "op": "lt", "value": 2.5},
                     "then": [{"Dispense": {"Volume": 0.5, "FlowRate": 1.0}, "as": "TopUp"}], "else": [{"Weigh": {}, "as": "Fine"}],
                     "as": "Light"},
                    {"if": {"operand": "Weigh.Weight", "op": "lt", "value": 1.0}, "then": [{"Weigh": {}, "as": "Again"}],
                     "as": "Empty"},
                    "Home"]}
    data["composites"]["Ready"] = {"execute": [{"parallel": [["Home"], ["Tare"]], "as": "Both"}]}
    return ModuleSpec.model_validate(data)


def test_skills_with_a_decision_and_a_parallel_block_are_created_online_and_run(module):    # noqa: F811
    ua, a, S = module.ua, "orchestrator-1", SKILL_STATES
    delivered, _ = aas(module.cand.spec, "pc")
    wanted, components = wanting(flow_spec(), delivered)
    assert ua.call("Occupation/Occupy", a) == [True, 0]
    assert ua.call("Module/Reset", a) == [True, 0]
    ua.expect("Module/State", STATES["Idle"], timeout=20)
    assert ua.call("Module/Start", a) == [True, 0]
    ua.expect("Module/State", STATES["Execute"])

    assert sorted(read(module.client, module.host, module.port, wanted, components).differences.create) == ["Checked", "Ready"]
    done, after = reconfigure(module.client, module.host, module.port, wanted, components)
    assert done[0].startswith("create Checked, Ready: ") and after.differences.empty, done
    recorded, config = record(wanted, after, done, "flows", components)

    ran = {step: ua.record(f"Skills/Checked/Execute/{step}/State") for step in ("TopUp", "Fine", "Again", "Home")}
    assert ua.call("Skills/Checked/Start", a, 1.0) == [True, 0]
    ua.expect("Skills/Checked/State", S["Succeeded"], timeout=60)
    assert seen(ran["TopUp"], S["Succeeded"]) and seen(ran["Home"], S["Succeeded"])  # the light vial is topped up
    assert S["Running"] not in ran["Fine"] and S["Running"] not in ran["Again"]       # the other branches are not run
    assert ua.value("Skills/Checked/Results/Weight") == pytest.approx(2.0)

    both = {step: ua.record(f"Skills/Ready/Execute/{step}/State") for step in ("Home", "Tare")}
    assert ua.call("Skills/Ready/Start", a) == [True, 0]
    ua.expect("Skills/Ready/State", S["Succeeded"], timeout=60)
    assert all(seen(states, S["Succeeded"]) for states in both.values())
    # The program is what the recorded AAS describes, with the record of what was built.
    assert read(module.client, module.host, module.port, recorded, components, record_=config).differences.empty
