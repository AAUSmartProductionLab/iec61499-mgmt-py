"""Three FORTEs on this computer for the PubSubDemo project: two counters publish, one subscriber adds.

    python runtime/demos/PubSubDemo/run.py               # start the three FORTEs; deploy from the 4diac IDE
    python runtime/demos/PubSubDemo/run.py --deploy      # ... and deploy the application from here
    python runtime/demos/PubSubDemo/run.py --deploy --check   # deploy, check the sum for 6 s, stop

FORTE_1 (localhost:61501) and FORTE_2 (:61502) each count (every 1 s, every 2 s) and publish
(source number, count) to the same UDP address, 127.0.0.1:61550. FORTE_3 (:61503) has the
one subscriber: the source number picks which count it keeps, Sum (F_ADD) adds the two, and
Blink.Q toggles with every new sum. Ctrl+C stops the FORTEs.

The blocks are deployed inside the application's container (CountAndAdd.Sum), as the IDE
deploys them, so the IDE can monitor either deployment. The standard types are copied into the
project (Type Library/Std), as in the generated module projects. FORTE serves one management
client at a time: this script reads only with --check, so the IDE can monitor otherwise.
"""
import argparse
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

from defusedxml.ElementTree import parse

from iec61499_mgmt import deployment
from iec61499_mgmt.protocol import Client, Command
from iec61499_mgmt.sysfile import FlatApplication, load_application

HERE = Path(__file__).resolve().parent
SYSTEM = HERE / "PubSubDemo.sys"
APPLICATION = "CountAndAdd"
FORTE = HERE.parents[1] / "fbe/build/modules-win/output/bin/forte.exe"


def devices() -> dict[str, int]:
    """Each device of the system with its management port (MGR_ID localhost:<port>)."""
    found = {}
    for device in parse(str(SYSTEM)).getroot().iter("Device"):
        mgr = next(p.get("Value") for p in device.iter("Parameter") if p.get("Name") == "MGR_ID")
        found[device.get("Name")] = int(mgr.strip('"').rpartition(":")[2])
    return found


def part(app: FlatApplication, device: str) -> FlatApplication:
    """The blocks the system maps to ``device`` with their values and connections among them."""
    mapped = {m.get("From").partition(".")[2] for m in parse(str(SYSTEM)).getroot().iter("Mapping")
              if m.get("To").split(".")[0] == device}
    inside = lambda port: port.rpartition(".")[0] in mapped  # noqa: E731
    return FlatApplication(
        fbs={n: t for n, t in app.fbs.items() if n in mapped},
        parameters={p: v for p, v in app.parameters.items() if inside(p)},
        event_connections=[(s, d) for s, d in app.event_connections if inside(s) and inside(d)],
        data_connections=[(s, d) for s, d in app.data_connections if inside(s) and inside(d)])


def wait_port(port: int, timeout: float = 15):
    deadline = time.monotonic() + timeout
    while True:
        try:
            with socket.create_connection(("localhost", port), timeout=1):
                return
        except OSError:
            if time.monotonic() > deadline:
                raise TimeoutError(f"FORTE on port {port} did not start")
            time.sleep(0.3)


def read(client: Client, port: str) -> str:
    """A value as FORTE gives it; a generic output with its type (Sum.OUT: ``DINT#21``)."""
    command = Command(op="read", resource="RES", source=port).inside(APPLICATION)
    return client.execute(command).read_value(command.source)


def number(text: str) -> int:
    return int(text.rpartition("#")[2])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--forte", type=Path, default=FORTE, help="FORTE executable (any build with the standard blocks)")
    parser.add_argument("--deploy", action="store_true", help="deploy the application from here (else from the IDE)")
    parser.add_argument("--check", action="store_true", help="with --deploy: check the sum for 6 s, then stop")
    args = parser.parse_args()
    logs = Path(tempfile.mkdtemp(prefix="pubsubdemo-"))
    running = []
    try:
        for device, port in devices().items():
            log = open(logs / f"{device}.log", "w")
            running.append(subprocess.Popen([str(args.forte), "-c", f"localhost:{port}"], stdout=log, stderr=log))
            wait_port(port)
            print(f"{device}: FORTE on localhost:{port} (log {log.name})")
        if args.deploy:
            app = load_application(SYSTEM, APPLICATION)
            for device, port in devices().items():
                with Client("localhost", port) as client:
                    for command in deployment(part(app, device), container=APPLICATION):
                        client.execute(command)
                print(f"{device}: deployed {', '.join(part(app, device).fbs)}")
        if args.check:
            time.sleep(6)
            with Client("localhost", devices()["FORTE_3"]) as client:
                a, b, total = (number(read(client, p)) for p in ("Count1In.OUT", "Count2In.OUT", "Sum.OUT"))
            print(f"count 1 = {a}, count 2 = {b}, sum = {total}")
            return 0 if a > 0 and b > 0 and total == a + b else 1
        print("Running; deploy and monitor from the 4diac IDE (PubSubDemo). Ctrl+C stops the FORTEs.")
        while all(p.poll() is None for p in running):
            time.sleep(1)
        print("A FORTE stopped; see its log in", logs)
        return 1
    except KeyboardInterrupt:
        return 0
    finally:
        for p in running:
            p.kill()


if __name__ == "__main__":
    sys.exit(main())
