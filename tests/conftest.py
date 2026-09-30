"""Live tests only launch an explicit executable, never attach to a user's PLC."""
from contextlib import contextmanager
import os
from pathlib import Path
import socket
import subprocess
import time

import pytest

import livecell
from iec61499_mgmt.protocol import Client, Command
from iec61499_mgmt.sysfile import load_application
from iec61499_mgmt.typelib import build_library, query_hashes, read_types


def pytest_addoption(parser):
    """Register the live-test command line options."""
    parser.addoption("--forte-exe", help="Launch this FORTE executable for isolated integration tests")
    parser.addoption("--forte-runtime-dir", help="Prepend this DLL directory to the FORTE child's PATH")
    parser.addoption("--module-forte-exe", help="FORTE built with every module (build-modules.ps1; tests/test_module_live.py)")
    parser.addoption("--pi-host", help="Run tests/test_module_live.py on this Raspberry Pi's FORTE (pi.py install)")
    parser.addoption("--pi-user", help="SSH login on the Pi (default: the pi target's user in modules/filling.yaml)")
    parser.addoption("--sim-host", help="This machine's address as the Pi sees it (the Pi's Modbus clients connect here)")
    parser.addoption("--pi-forte-exe", help="aarch64 FORTE (build-modules.ps1 -Config pi/modules-pi) for tests/test_pwm_emulated.py")


def free_port():
    """Return a free TCP port on localhost."""
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        return reservation.getsockname()[1]


@contextmanager
def launch_forte(executable, directory, runtime_dir=None, extra_args=()):
    """Start FORTE on a free loopback management port; yield the port; always terminate it."""
    environment = os.environ.copy()
    if runtime_dir:
        environment["PATH"] = str(Path(runtime_dir).resolve(strict=True)) + os.pathsep + environment.get("PATH", "")
    port = free_port()
    with (Path(directory) / "forte.log").open("w+b") as log:
        process = subprocess.Popen(
            [str(executable), "-c", f"127.0.0.1:{port}", *extra_args], cwd=directory, env=environment,
            stdout=log, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            deadline = time.monotonic() + 15
            while True:
                if process.poll() is not None:
                    raise RuntimeError(f"FORTE exited with code {process.returncode}")
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                        break
                except (ConnectionRefusedError, TimeoutError):
                    if time.monotonic() >= deadline:
                        raise TimeoutError("FORTE startup timed out; check DLL search PATH")
                    time.sleep(0.1)
            yield port
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            log.seek(0)
            print("FORTE log:", log.read().decode(errors="replace")[-3000:])


@pytest.fixture(scope="session")
def forte_exe(request):
    """FORTE executable from --forte-exe; skips the test if absent."""
    executable = request.config.getoption("--forte-exe")
    if not executable:
        pytest.skip("Pass --forte-exe to run against an isolated FORTE process")
    return Path(executable).resolve(strict=True)


@pytest.fixture
def forte(request, forte_exe, tmp_path):
    """A fresh FORTE with an EMB_RES 'RES'; yields (Resource, opc ua port)."""
    ua_port = free_port()
    with launch_forte(forte_exe, tmp_path, request.config.getoption("--forte-runtime-dir"),
                      ["-op", str(ua_port)]) as port, Client("127.0.0.1", port) as client:
        client.execute(Command(op="create_fb", resource="", name="RES", type="iec61499::system::EMB_RES"))
        yield livecell.Resource(client), ua_port


@pytest.fixture(scope="session")
def library(request, forte_exe, tmp_path_factory):
    """Type library with hashes queried from the runtime (what types.json contains)."""
    with launch_forte(forte_exe, tmp_path_factory.mktemp("types")) as port, Client("127.0.0.1", port) as client:
        client.execute(Command(op="create_fb", resource="", name="RES", type="iec61499::system::EMB_RES"))
        types = read_types(livecell.TYPES)
        hashes = query_hashes(client, "RES", [n for n in types if n.startswith(livecell.FC)])
    return build_library(types, hashes, build_id=str(forte_exe), fixed=load_application(livecell.SYS, "FillingCell"))
