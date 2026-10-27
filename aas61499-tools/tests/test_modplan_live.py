"""A skill planned from the filling module's AAS, created online on FORTE while the module runs, and
run over OPC UA (G4): new behaviour from the capability model, through the IEC 61499 management
interface, without a restart.

    python -m pytest aas61499-tools/tests/test_modplan_live.py --module-forte-exe <a FORTE with every module>
"""
import pytest

pytest.importorskip("aas_model")

from modgen.library import SKILL_STATES, STATES                              # noqa: E402
from modsync.desired import read, reconfigure, record                        # noqa: E402

from modplan.compose import compose                                          # noqa: E402

from test_modsync_desired import aas                                         # noqa: E402
from test_modsync_flow_live import seen                                      # noqa: E402
from test_modsync_live import module                                         # noqa: E402, F401  (the fixture)


def test_a_planned_skill_is_created_online_and_runs(module):                 # noqa: F811
    ua, a, S = module.ua, "orchestrator-1", SKILL_STATES
    delivered, components = aas(module.cand.spec, "pc")
    composed = compose(delivered, components, "Filling", {"FillVolume": 2.0}, ("FillWeight",), name="PlannedFilling")
    assert ua.call("Occupation/Occupy", a) == [True, 0]
    assert ua.call("Module/Reset", a) == [True, 0]
    ua.expect("Module/State", STATES["Idle"], timeout=20)
    assert ua.call("Module/Start", a) == [True, 0]
    ua.expect("Module/State", STATES["Execute"])

    assert read(module.client, module.host, module.port, composed.module, components).differences.create == ["PlannedFilling"]
    done, after = reconfigure(module.client, module.host, module.port, composed.module, components)
    assert done[0].startswith("create PlannedFilling: ") and after.differences.empty, done
    recorded, config = record(composed.module, after, done, "planned", components)

    ran = {step: ua.record(f"Skills/PlannedFilling/Execute/{step}/State") for step in ("MoveAxis", "Dispense", "Home", "Weigh")}
    assert ua.call("Skills/PlannedFilling/Start", a) == [True, 0]
    ua.expect("Skills/PlannedFilling/State", S["Succeeded"], timeout=60)
    assert all(seen(states, S["Succeeded"]) for states in ran.values())
    assert ua.value("Skills/PlannedFilling/Results/FillWeight") == pytest.approx(2.0)      # the simulated scale
    # The program is what the recorded AAS describes.
    assert read(module.client, module.host, module.port, recorded, components, record_=config).differences.empty
