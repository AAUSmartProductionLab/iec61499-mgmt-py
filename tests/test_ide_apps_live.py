"""The applications mapped in the 4diac system run as the IDE would deploy them (opt-in: --forte-exe).

All four resources of device FORTE_PC are loaded into one FORTE through one boot file.
"""
import time

from conftest import free_port, launch_forte
from iec61499_mgmt import boot_file, deployment
from iec61499_mgmt.protocol import Client
from iec61499_mgmt.sysfile import load_resource
from livecell import IDLE, STOPPED, SYS, Resource, Ua

RESOURCES = ["DEMO", "BENCH", "PATTERNS", "RES"]  # RES last: OPC UA must not depend on order


def wait_for(read, predicate, timeout):
    """Poll ``read()`` until ``predicate`` holds; return the last value."""
    deadline = time.monotonic() + timeout
    while not predicate(value := read()) and time.monotonic() < deadline:
        time.sleep(0.2)
    return value


def test_mapped_applications_run(request, forte_exe, tmp_path):
    """Production cell idles on OPC UA, the demo cell cycles itself, bench and patterns count."""
    commands = [c for r in RESOURCES for c in deployment(load_resource(SYS, "FORTE_PC", r), resource=r)]
    path = tmp_path / "forte.fboot"
    path.write_text(boot_file(commands), encoding="utf-8")
    ua_port = free_port()
    with launch_forte(forte_exe, tmp_path, request.config.getoption("--forte-runtime-dir"),
                      ["-op", str(ua_port), "-f", str(path)]) as port, Client("127.0.0.1", port) as client:
        demo, bench, patterns, cell = (Resource(client, r) for r in ["DEMO", "BENCH", "PATTERNS", "RES"])

        def number(res, port):
            return int(res.read(port))

        cycles = wait_for(lambda: number(demo, "Operator.Cycles"), lambda v: v >= 2, 60)
        assert cycles >= 2, f"demo phase {demo.read('Operator.Phase')}, unit {demo.read('Unit.State')}"
        assert number(demo, "Plant.ShootThrough") == 0
        assert demo.read("EM_Filler.Inspect.State") in ("17", "4")

        done = wait_for(lambda: number(bench, "Done.CV"), lambda v: v >= 2, 10)
        assert done >= 2 and number(bench, "Failed.CV") == 0

        joins = wait_for(lambda: number(patterns, "CtuFalse.CV") + number(patterns, "CtuTrue.CV"), lambda v: v >= 1, 10)
        assert joins >= 1
        assert number(patterns, "CtuBody.CV") >= 3 * number(patterns, "CtuTrue.CV") + 3 * number(patterns, "CtuFalse.CV")

        assert number(cell, "Unit.State") == STOPPED               # production cell waits for OPC UA commands
        assert number(cell, "EM_Filler.Dose.State") == IDLE
        ua = Ua(ua_port)
        try:
            assert ua.call("Occupation/Occupy", 1) == [True, 0]
            assert ua.call("Unit/Reset", 1, 1) == [True, 0]
            ua.expect("Unit/State", IDLE)
        finally:
            ua.close()
