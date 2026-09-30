"""Run a generated module for manual testing (UaExpert, 4diac IDE monitoring): its Modbus
simulator, FORTE and the deployed module, until Ctrl+C.

    python cell/sim/run_module.py cell/modules/filling.yaml             # OPC UA opc.tcp://localhost:4840
    python cell/sim/run_module.py cell/modules/stoppering.yaml --opcua-port 4841
    python cell/sim/run_module.py cell/modules/filling.yaml --no-deploy  # empty FORTE; deploy from the 4diac IDE

The module's OPC UA objects are below /Objects/<Module>: Occupation (Occupy/Release), Module
(Reset/Start/Stop/Abort/Clear, State), Skills/<Skill> (Start/Stop/Abort/Reset, State, ErrorID,
Parameters, Results) and Equipment/<Item>. Occupy with any string as session ID (a UUID), pass
the same string to every method; Reset and Start the module, then start skills.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import socket
import subprocess
import sys
import time

from iec61499_mgmt.bootfile import deployment
from iec61499_mgmt.protocol import Client
from iec61499_mgmt.sysfile import load_application
from modgen import SPECS, load, system_file
from modgen.module import app_name

SIM = Path(__file__).resolve().parent
ROOT = SIM.parents[1]
sys.path.insert(0, str(SIM))
from module_sim import ModuleSim, SimServer  # noqa: E402

FORTE = ROOT / "runtime" / "fbe" / "build" / "modules-win" / "output" / "bin" / "forte.exe"
CACHE = ROOT / "runtime" / ".cache"


def wait_port(port, timeout=15):
    """Wait until a local TCP port accepts connections."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                return
        except OSError:
            if time.monotonic() > deadline:
                raise TimeoutError(f"Nothing listens on port {port}")
            time.sleep(0.1)


def main():
    """Start simulator and FORTE, deploy the module, and keep running until Ctrl+C."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("spec", nargs="?", default=str(SPECS / "filling.yaml"))
    parser.add_argument("--forte", default=str(FORTE))
    parser.add_argument("--mgmt-port", type=int, default=61499)
    parser.add_argument("--opcua-port", type=int, default=4840)
    parser.add_argument("--no-deploy", action="store_true")
    args = parser.parse_args()

    spec = load(Path(args.spec))
    sim = ModuleSim(spec)
    CACHE.mkdir(parents=True, exist_ok=True)
    log = (CACHE / f"run_module-{spec.package}.log").open("wb")
    with SimServer(sim, port=spec.modbus.port):
        forte = subprocess.Popen([args.forte, "-c", f"127.0.0.1:{args.mgmt_port}", "-op", str(args.opcua_port)],
                                 cwd=CACHE, stdout=log, stderr=subprocess.STDOUT)
        try:
            wait_port(args.mgmt_port)
            if not args.no_deploy:
                app = load_application(system_file(spec.project), app_name(spec, next(iter(spec.targets))))
                with Client("127.0.0.1", args.mgmt_port) as client:
                    for command in deployment(app):
                        client.execute(command)
            print(f"{spec.module}: FORTE management 127.0.0.1:{args.mgmt_port}, OPC UA "
                  f"opc.tcp://localhost:{args.opcua_port}{spec.opcua_root}, Modbus simulator 127.0.0.1:"
                  f"{spec.modbus.port}; FORTE log {log.name}", flush=True)
            while forte.poll() is None:
                time.sleep(1)
                axes = " ".join(f"{eq}={sim.position(eq):.2f}" for eq in sim.axes)
                print(f"{axes}  on={sim.outputs_on()}", flush=True)
            print(f"FORTE exited with code {forte.returncode}")
        except KeyboardInterrupt:
            pass
        finally:
            if forte.poll() is None:
                forte.terminate()
                forte.wait(timeout=5)


if __name__ == "__main__":
    main()
