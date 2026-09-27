"""Unit access over the filling-cell OPC UA facade (optional dependency: asyncua)."""
from __future__ import annotations

QUIESCENT = {2: "Stopped", 4: "Idle", 9: "Aborted", 17: "Complete"}


class OpcUaUnit:
    """Occupy, release and read unit/skill states through the unit's OPC UA object."""

    def __init__(self, endpoint: str, requester: int, root: tuple[str, ...] = ("FillingCell", "Filler"),
                 namespace: int = 1, timeout: float = 10):
        from asyncua import ua
        from asyncua.sync import Client

        self.ua, self.requester, self.ns = ua, requester, namespace
        self.client = Client(endpoint, timeout=timeout)
        self.client.connect()
        self.root = self.client.nodes.objects.get_child([f"{namespace}:{r}" for r in root])

    def close(self):
        """Disconnect from the server."""
        self.client.disconnect()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def call(self, path: str, *args) -> tuple[bool, int]:
        """Call a facade method (e.g. ``Occupation/Occupy``) as this requester; (Accepted, ErrorID)."""
        parent, method = path.rsplit("/", 1)
        node = self.root.get_child([f"{self.ns}:{p}" for p in parent.split("/")])
        return tuple(node.call_method(f"{self.ns}:{method}", self.ua.Variant(self.requester, self.ua.VariantType.UInt32),
                                      *args))

    def value(self, path: str):
        """Read a published variable below the unit object."""
        return self.root.get_child([f"{self.ns}:{p}" for p in path.split("/")]).read_value()

    def occupy(self) -> bool:
        """Occupy the unit for this requester."""
        return bool(self.call("Occupation/Occupy")[0])

    def release(self) -> bool:
        """Release this requester's occupation."""
        return bool(self.call("Occupation/Release")[0])

    def quiescent(self) -> list[str]:
        """Reasons the unit or any skill is not quiescent (Idle, Complete, Stopped, Aborted)."""
        problems = []
        state = self.value("Unit/State")
        if state not in QUIESCENT:
            problems.append(f"unit state {state}")
        skills = self.root.get_child([f"{self.ns}:Skills"])
        for skill in skills.get_children():
            name = skill.read_browse_name().Name
            state = skill.get_child([f"{self.ns}:State"]).read_value()
            if state not in QUIESCENT:
                problems.append(f"skill {name} state {state}")
        return problems
