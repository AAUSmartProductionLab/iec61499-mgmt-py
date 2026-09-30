"""Live tests only launch an explicit executable, never attach to a user's PLC."""
from contextlib import contextmanager
import os
from pathlib import Path
import socket
import subprocess
import time

import pytest


def pytest_addoption(parser):
    """Register the live-test command line options."""
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
