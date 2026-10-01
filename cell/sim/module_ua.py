"""OPC UA client for a generated module (the objects below /Objects/<Module>), used by the live tests.

    ua = ModuleUa(4840, "Filling", host="192.168.0.191")
    ua.call("Occupation/Occupy", "session-1")          # -> [Accepted, ErrorID]
    ua.expect("Module/State", 2)
"""
from __future__ import annotations

import time


class ModuleUa:
    """OPC UA client for a module below /Objects/<Module>."""

    def __init__(self, port, module, host="127.0.0.1"):
        from asyncua import ua
        from asyncua.sync import Client as UaClient
        self.ua, self.module = ua, module
        self.client = UaClient(f"opc.tcp://{host}:{port}", timeout=10)
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
        """Node below /Objects/<Module>."""
        return self.client.nodes.objects.get_child([f"1:{self.module}"] + [f"1:{p}" for p in path.split("/")])

    def call(self, path, session, *args):
        """Call a method with a session ID and Double arguments; return [Accepted, ErrorID].

        The module's methods only accept or refuse and answer at once; a call that takes more
        than 2 s means FORTE is blocked, which is reported as an error."""
        parent, method = path.rsplit("/", 1)
        variants = [self.ua.Variant(session, self.ua.VariantType.String)]
        variants += [self.ua.Variant(float(a), self.ua.VariantType.Double) for a in args]
        started = time.monotonic()
        accepted, error = self.node(parent).call_method(f"1:{method}", *variants)
        if time.monotonic() - started >= 2.0:
            raise TimeoutError(f"{path} took {time.monotonic() - started:.1f} s to answer")
        return [accepted, error]

    def value(self, path):
        """Read a variable."""
        return self.node(path).read_value()

    def expect(self, path, value, timeout=3.0):
        """Wait until a variable has the expected value."""
        deadline = time.monotonic() + timeout
        while True:
            try:
                actual = self.value(path)
            except Exception as exc:                   # node not created yet
                actual = exc
            if actual == value:
                return
            if time.monotonic() > deadline:
                raise AssertionError(f"{path} = {actual!r}, expected {value!r}")
            time.sleep(0.05)

    def record(self, path) -> list:
        """The values a variable takes from now on, in order (an OPC UA subscription, starting with
        the current value). A state that lasts less than the 20 ms sampling may be missed."""
        values = []

        class Handler:
            def datachange_notification(self, node, value, data):
                values.append(value)
        self.client.create_subscription(20, Handler()).subscribe_data_change(self.node(path))
        return values

    def close(self):
        """Disconnect."""
        self.client.disconnect()
