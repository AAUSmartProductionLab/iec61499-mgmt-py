"""modsync against FORTE: a module is verified against its AAS, and brought to what the AAS
describes, without its module spec.

    python -m pytest aas61499-tools/tests/test_modsync_desired_live.py --module-forte-exe runtime/fbe/build/modules-win/output/bin/forte.exe
"""
import copy
import time
from types import SimpleNamespace

import pytest

pytest.importorskip("aas_model")

from iec61499_mgmt.bootfile import boot_file, deployment                     # noqa: E402
from iec61499_mgmt.protocol import Command                                   # noqa: E402
from modgen.library import ERRORS, SKILL_STATES, STATES                      # noqa: E402
from modsync.desired import at, instances, read, reconfigure, record, submodel   # noqa: E402
from modsync.sync import Refused                                             # noqa: E402
from test_modsync import composed                                            # noqa: E402
from test_modsync_desired import aas, wanting                                # noqa: E402
from test_modsync_live import module                                         # noqa: E402, F401  (the fixture)


def test_a_delivered_module_is_what_its_aas_describes(module):    # noqa: F811
    delivered, components = aas(module.cand.spec, "pc")
    reading = read(module.client, module.host, module.port, delivered, components)
    assert reading.differences.empty, reading.differences.lines()
    # Once the hashes FORTE reports are recorded, they are verified too.
    recorded = record(delivered, reading)
    assert all(digest.startswith("v2:SHA3-512:") for _, _, digest in instances(recorded))
    assert read(module.client, module.host, module.port, recorded, components).differences.empty


def test_a_skill_described_in_the_aas_is_created_while_another_runs(module):   # noqa: F811
    """The changeover to two doses: the AAS describes DoubleDose, the program does not have it. It
    is created from the description while the module runs Dispensing; FORTE is neither rebuilt
    nor restarted, and no module spec is read."""
    ua, a, S = module.ua, "orchestrator-1", SKILL_STATES
    delivered, _ = aas(module.cand.spec, "pc")
    wanted, components = wanting(composed("pc").spec, delivered)
    assert ua.call("Occupation/Occupy", a) == [True, 0]
    assert ua.call("Module/Reset", a) == [True, 0]
    ua.expect("Module/State", STATES["Idle"], timeout=15)
    assert ua.call("Module/Start", a) == [True, 0]
    ua.expect("Module/State", STATES["Execute"])
    dispensing = ua.record("Skills/Dispensing/State")
    assert ua.call("Skills/Dispensing/Start", a, 1.0) == [True, 0]
    ua.expect("Skills/Dispensing/State", S["Running"], timeout=1)

    assert read(module.client, module.host, module.port, wanted, components).differences.create == ["DoubleDose"]
    saved = []
    deployer = SimpleNamespace(load=lambda: boot_file(deployment(module.cand.app, overrides=module.overrides)),
                               save=saved.append)
    started = time.perf_counter()
    done, after = reconfigure(module.client, module.host, module.port, wanted, components, deployer)
    took = time.perf_counter() - started
    assert done[0].startswith("create DoubleDose: ") and "added to the boot file" in done, done
    print(f"\n{done[0]}; {done[2]}; {took:.3f} s with reading before and after")

    # The running skill went on (it may have ended while the new one was created).
    deadline = time.monotonic() + 10
    while S["Succeeded"] not in dispensing and time.monotonic() < deadline:
        time.sleep(0.05)
    assert S["Succeeded"] in dispensing and S["Failed"] not in dispensing, dispensing
    # The new skill is there as described: its default, its limits, what it does.
    assert ua.value("Skills/DoubleDose/Parameters/Dose") == 0.5
    assert ua.call("Skills/DoubleDose/Start", a, 20.0) == [False, ERRORS["OutOfRange"]]
    assert ua.call("Skills/DoubleDose/Start", a, 0.6) == [True, 0]
    ua.expect("Skills/DoubleDose/State", S["Succeeded"], timeout=10)
    assert ua.value("Skills/DoubleDose/Results/Weight") == pytest.approx(2.0)

    # What was built is recorded, with the hashes of this FORTE, and holds when read again.
    recorded = record(wanted, after, done, "changeover to two doses")
    built = {path: digest for path, _, digest in instances(recorded)}
    assert built["DoubleDose.Execute.Dispense_2"].startswith("v2:SHA3-512:")
    assert read(module.client, module.host, module.port, recorded, components).differences.empty
    # A FORTE started from the amended boot file runs what the AAS describes.
    module.client.close()
    with module.fresh(saved[0]) as (client, port):
        deadline = time.monotonic() + 10
        while not client.execute(Command(op="query_fbs", resource="RES")).fbs:
            assert time.monotonic() < deadline, "the boot file was not loaded"
            time.sleep(0.2)
        time.sleep(0.5)
        assert read(client, module.host, port, recorded, components).differences.empty


def test_a_limit_and_a_constant_changed_in_the_aas_hold_at_the_next_start(module):   # noqa: F811
    """The largest volume is lowered to 8 mL and the dispensing step's flow rate doubled."""
    ua, a = module.ua, "orchestrator-1"
    wanted, components = copy.deepcopy(aas(module.cand.spec, "pc"))
    dispensing = at(submodel(wanted, "Skills"), "Skills", "Dispensing")
    at(dispensing, "Start", "Steps", "P2", "FlowRate")["value"] = "2.0"
    volume = next(v["value"] for v in at(dispensing, "Start", "Start")["inputVariables"] if v["value"]["idShort"] == "Volume")
    next(q for q in volume["qualifiers"] if q["type"] == "Maximum")["value"] = "8.0"

    assert ua.call("Occupation/Occupy", a) == [True, 0]
    with pytest.raises(Refused, match="occupied"):                  # not while somebody works with the module
        reconfigure(module.client, module.host, module.port, wanted, components)
    assert ua.call("Occupation/Release", a) == [True, 0]
    done, after = reconfigure(module.client, module.host, module.port, wanted, components)
    assert done[:2] == ["write Dispensing.Execute.Dispense.FlowRate := 2.0 (was 1.0)",
                        "write Dispensing.Volume.Upper := 8.0 (was 10.0)"]
    assert after.differences.empty

    assert ua.call("Occupation/Occupy", a) == [True, 0]
    assert ua.call("Module/Reset", a) == [True, 0]
    ua.expect("Module/State", STATES["Idle"], timeout=15)
    assert ua.call("Module/Start", a) == [True, 0]
    ua.expect("Module/State", STATES["Execute"])
    assert ua.call("Skills/Dispensing/Start", a, 9.0) == [False, ERRORS["OutOfRange"]]      # 9 mL was allowed
    started = time.monotonic()
    assert ua.call("Skills/Dispensing/Start", a, 8.0) == [True, 0]
    ua.expect("Skills/Dispensing/State", SKILL_STATES["Succeeded"], timeout=20)
    # 8 mL at 2 mL/s is 4 s of dispensing, 8 s at the old rate; the axis and the scale take about 4 s more.
    assert time.monotonic() - started < 10.5
