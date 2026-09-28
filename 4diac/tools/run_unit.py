"""Run a generated unit for manual testing (UaExpert, 4diac IDE monitoring): Modbus simulator,
FORTE and the deployed application, until Ctrl+C.

    python 4diac/tools/run_unit.py                       # FillerUnit: OPC UA opc.tcp://localhost:4840
    python 4diac/tools/run_unit.py --no-deploy           # empty FORTE; deploy from the 4diac IDE instead

The unit's OPC UA objects are below /Objects/<Unit>. Occupy with any string as session ID (a UUID),
then pass the same string to every method.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import socket
import subprocess
import sys
import time

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(ROOT))
from cell_sim import Cell, CellServer  # noqa: E402
from iec61499_mgmt.protocol import Client, Command  # noqa: E402
from iec61499_mgmt.sysfile import load_application  # noqa: E402


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
    """Start simulator and FORTE, deploy the unit, and keep running until Ctrl+C."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--project", default="FillerUnit")
    parser.add_argument("--application", default="Filler")
    parser.add_argument("--forte", default=str(TOOLS / "fbe" / "build" / "filler-win" / "output" / "bin" / "forte.exe"))
    parser.add_argument("--mgmt-port", type=int, default=61499)
    parser.add_argument("--opcua-port", type=int, default=4840)
    parser.add_argument("--modbus-port", type=int, default=1502)
    parser.add_argument("--travel-s", type=float, default=2.0, help="Simulated needle travel time, top to bottom")
    parser.add_argument("--no-deploy", action="store_true")
    args = parser.parse_args()

    sys_file = ROOT / "4diac" / args.project / f"{args.project}.sys"
    cell = Cell(travel_s=args.travel_s)
    log = (TOOLS / ".cache" / "run_unit-forte.log").open("wb")
    with CellServer(cell, port=args.modbus_port):
        forte = subprocess.Popen([args.forte, "-c", f"127.0.0.1:{args.mgmt_port}", "-op", str(args.opcua_port)],
                                 cwd=TOOLS / ".cache", stdout=log, stderr=subprocess.STDOUT)
        try:
            wait_port(args.mgmt_port)
            if not args.no_deploy:
                app = load_application(sys_file, args.application)
                ports = {k: v.replace(":1502:", f":{args.modbus_port}:")
                         for k, v in app.parameters.items() if k.endswith("_Modbus")}
                with Client("127.0.0.1", args.mgmt_port) as client:
                    client.execute(Command(op="create_fb", resource="", name="RES", type="iec61499::system::EMB_RES"))
                    for command in app.commands("RES", ports):
                        client.execute(command)
                    client.execute(Command(op="start", resource="", name="RES"))
            print(f"FORTE management 127.0.0.1:{args.mgmt_port}, OPC UA opc.tcp://localhost:{args.opcua_port}, "
                  f"Modbus simulator 127.0.0.1:{args.modbus_port}; FORTE log {log.name}", flush=True)
            while forte.poll() is None:
                time.sleep(1)
                print(f"needle {cell.position_mm:5.1f} mm  top={cell.inputs['NeedleUp']!s:5} "
                      f"bottom={cell.inputs['NeedleDown']!s:5}  coils={[c for c, on in cell.coils.items() if on]}",
                      flush=True)
            print(f"FORTE exited with code {forte.returncode}")
        except KeyboardInterrupt:
            pass
        finally:
            if forte.poll() is None:
                forte.terminate()
                forte.wait(timeout=5)


if __name__ == "__main__":
    main()
