"""A resource agent's skill run through the AAS server and the DMP (lineagents.execute.DmpExecutor): the
filling module on FORTE with its simulator, its AASs published to the lab stack on this computer with
its interface where the DMP's container reaches it, Dispensing run by invoking its Operations and
followed in InfluxDB. The setup is the DMP's own live test's (cell/tests/test_dmp_live.py).

    python -m pytest line-agents/tests/test_dmp_executor.py --module-forte-exe <a FORTE with every module>
"""
from pathlib import Path
import sys
import uuid

import pytest

pytest.importorskip("aas_model")

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "line-agents"), str(ROOT / "cell" / "tests")]

from test_dmp_live import REPOSITORY, UA_PORT, filling, installed, published, stack   # noqa: E402, F401 (fixture)
from lineagents.aas import Offer                                                         # noqa: E402
from lineagents.execute import DmpExecutor                                               # noqa: E402
from lineagents.xmpp import run                                                          # noqa: E402


def test_a_skill_runs_through_the_aas_and_the_dmp(stack, request, tmp_path):      # noqa: F811
    with filling(request, tmp_path, UA_PORT) as (spec, ua):
        env = published(spec, UA_PORT)["FillingModuleAAS"]
        installed(env)
        executor = DmpExecutor(env, REPOSITORY, timeout=90)
        offer = Offer("FillingModuleAAS", "Filling", "Dispensing", True, {"Volume": 1.5})
        result = run(executor.run(offer, f"agent-{uuid.uuid4()}"))
        assert result.skill == "Dispensing"
        assert result.results.get("Weight") == pytest.approx(2.0)                # the simulated scale
        ua.expect("Occupation/Occupied", False)                                     # released
