"""Shared helpers for the live filling-cell tests (management, OPC UA, simulator)."""
from pathlib import Path
import sys
import time

from iec61499_mgmt.protocol import Command
from iec61499_mgmt.sysfile import load_application

ROOT = Path(__file__).resolve().parents[1]
SYS = ROOT / "4diac" / "FillingCellFixed" / "FillingCellFixed.sys"
TYPES = ROOT / "4diac" / "FillingCellFixed" / "Type Library"
MANIFEST = ROOT / "4diac" / "tools" / "types-manifest.json"
sys.path.insert(0, str(ROOT / "4diac" / "tools"))
from cell_sim import Cell, CellServer  # noqa: E402,F401

FC = "fillingcell::"
STOPPED, STARTING, IDLE, EXECUTE, ABORTED, HELD, COMPLETE = 2, 3, 4, 6, 9, 11, 17
CELL_OK = dict(NeedleUp=False, NeedleDown=True, VialPresent=True, FilledMl=0.0, Stoppered=False,
               Checked=False, DoorClosed=True, Valid=True, Safe=True)


def literal(value):
    """Format a Python value as an IEC literal."""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, dict):
        return "(" + ",".join(f"{k}:={literal(v)}" for k, v in value.items()) + ")"
    return str(value)


class Resource:
    """Management helper for one FORTE resource."""
    def __init__(self, client, name="RES"):
        self.client, self.name = client, name

    def send(self, op, resource=None, **kw):
        """Execute one management command on this resource."""
        return self.client.execute(Command(op=op, resource=self.name if resource is None else resource, **kw))

    def create(self, name, typ):
        """Create an FB instance."""
        self.send("create_fb", name=name, type=typ)

    def write(self, port, value):
        """Write a value to an input."""
        self.send("write", destination=port, value=literal(value))

    def fire(self, port, settle=0.05):
        """Trigger an event input and let it settle."""
        self.send("write", destination=port, value="$e")
        time.sleep(settle)

    def read(self, port):
        """Read a port value."""
        return self.send("read", source=port).read_value(port)

    def expect(self, port, value, timeout=3.0):
        """Wait until a port reads the expected value."""
        wanted, deadline = literal(value), time.monotonic() + timeout
        while (actual := self.read(port)) != wanted:
            if time.monotonic() > deadline:
                raise AssertionError(f"{port} = {actual}, expected {wanted}")
            time.sleep(0.05)


def start(res):
    """Start the resource RES."""
    res.send("start", resource="", name="RES")


def deploy_cell(res, overrides=None):
    """Deploy the FillingCell application to RES and start it."""
    app = load_application(SYS, "FillingCell")
    for command in app.commands("RES", overrides):
        res.client.execute(command)
    start(res)
    return app


class Ua:
    """Small OPC UA client for the cell address space."""
    def __init__(self, port):
        from asyncua import ua
        from asyncua.sync import Client as UaClient
        self.ua = ua
        self.client = UaClient(f"opc.tcp://127.0.0.1:{port}", timeout=10)
        deadline = time.monotonic() + 10
        while True:
            try:
                self.client.connect()
                break
            except Exception:
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.2)

    def node(self, path):
        """Node below /Objects/FillingCell/Filler."""
        return self.client.nodes.objects.get_child(["1:FillingCell", "1:Filler"] + [f"1:{p}" for p in path.split("/")])

    def call(self, path, requester, *args):
        """Call a method and return [Accepted, ErrorID]."""
        parent, method = path.rsplit("/", 1)
        variants = [self.ua.Variant(requester, self.ua.VariantType.UInt32)]
        for a in args:
            variants.append(self.ua.Variant(a, self.ua.VariantType.Double if isinstance(a, float) else self.ua.VariantType.Byte))
        started = time.monotonic()
        accepted, error = self.node(parent).call_method(f"1:{method}", *variants)
        assert time.monotonic() - started < 2.0          # answered synchronously, well under 4 s
        return [accepted, error]

    def value(self, path):
        """Read a variable."""
        return self.node(path).read_value()

    def expect(self, path, value, timeout=3.0):
        """Wait until a variable has the expected value."""
        deadline = time.monotonic() + timeout
        while (actual := self.value(path)) != value:
            if time.monotonic() > deadline:
                raise AssertionError(f"{path} = {actual}, expected {value}")
            time.sleep(0.05)

    def close(self):
        """Disconnect the client."""
        self.client.disconnect()


def modbus_overrides(port):
    """Parameters that switch the observer and all skills to the Modbus simulator on ``port``."""
    overrides = {}
    for name, value in load_application(SYS, "FillingCell").parameters.items():
        if name.endswith("Modbus"):
            overrides[name] = value.replace(":1502:", f":{port}:")
        elif name.endswith("IoBackend"):
            overrides[name] = "2"
    return overrides
