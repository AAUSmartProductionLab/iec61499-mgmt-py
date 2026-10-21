"""What runs on a module's FORTE, read over the management protocol.

FORTE 3.3 answers QUERY with every instance of a resource under its full dotted name (instances
inside subapplications included), QUERY of a type with its hash, QUERY of connections with every
event and data connection, and READ of any input or output, also inside a composite FB. So the
running program can be read back completely, including changes made online since the boot.

A program deployed by the 4diac IDE (or for it to monitor) lies inside its application's container
(``Filling.Home``). The snapshot names the container and leaves it out of every instance name, so
the program reads the same either way; requests to the device add it back (``Snapshot.at``).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import re

from iec61499_mgmt.protocol import Client, Command, ManagementError, ProtocolError


# Instances of the resource type itself (EMB_RES), not of the program.
RESOURCE_FBS = {"START"}


@dataclass
class Snapshot:
    """The program of one resource as FORTE reports it."""
    host: str
    port: int
    resource: str = "RES"
    container: str = ""                                          # the application's, '' if none
    fbs: dict[str, str] = field(default_factory=dict)           # instance -> qualified type
    status: dict[str, str] = field(default_factory=dict)        # instance -> RUNNING, STOPPED, ...
    hashes: dict[str, str] = field(default_factory=dict)        # type -> hash reported by the runtime
    connections: set[tuple[str, str]] = field(default_factory=set)
    values: dict[str, str | None] = field(default_factory=dict)  # "fb.port" -> value as read, None if unreadable
    read_at: str = ""

    @property
    def empty(self) -> bool:
        """No program: the resource does not exist or has no instances."""
        return not self.fbs

    def at(self, command: Command) -> Command:
        """``command`` for this program on the device: inside its container."""
        return command.inside(self.container)


def container(names) -> str:
    """The application's container every instance lies in ('' if none): the first part of each
    name, the same for all, and not an instance itself."""
    firsts = {n.split(".")[0] for n in names}
    found = next(iter(firsts)) if len(firsts) == 1 else ""
    return found if found and all("." in n for n in names) else ""


def outside(name: str, container_: str) -> str:
    return name[len(container_) + 1:] if container_ and name.startswith(container_ + ".") else name


def read_structure(client: Client, host: str, port: int, resource: str = "RES") -> Snapshot:
    """Instances, their types with hashes, and connections; values are read separately (read_values)."""
    snap = Snapshot(host, port, resource, read_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    try:
        fbs = client.execute(Command(op="query_fbs", resource=resource)).fbs
    except ManagementError:              # no such resource: FORTE runs without a program
        return snap
    fbs = [fb for fb in fbs if fb["Name"] not in RESOURCE_FBS]
    snap.container = container([fb["Name"] for fb in fbs])
    for fb in fbs:
        name = outside(fb["Name"], snap.container)
        snap.fbs[name] = fb.get("Type", "").partition("#")[0]
        snap.status[name] = fb.get("Status", "")
    snap.connections = {(outside(c["Source"], snap.container), outside(c["Destination"], snap.container))
                        for c in client.execute(Command(op="query_connections", resource=resource)).connections}
    for typ in sorted(set(snap.fbs.values())):
        types = client.execute(Command(op="query_type", resource=resource, type=typ)).types
        snap.hashes[typ] = types[0]["Name"].partition("#")[2] if types else ""
    return snap


def read_values(client: Client, snap: Snapshot, ports) -> None:
    """READ each ``fb.port`` of an existing instance into ``snap.values`` (None if it cannot be read)."""
    for port in ports:
        if port.rpartition(".")[0] not in snap.fbs and not internal(port, snap):
            continue
        try:
            command = snap.at(Command(op="read", resource=snap.resource, source=port))
            snap.values[port] = client.execute(command).read_value(command.source)
        except (ManagementError, ProtocolError):     # e.g. an empty string answers without a value
            snap.values[port] = None


def internal(port: str, snap: Snapshot) -> bool:
    """A port of an FB inside a composite FB instance (``Module.Logic.State``)."""
    parts = port.split(".")
    return any(".".join(parts[:i]) in snap.fbs for i in range(1, len(parts) - 1))


def literal(text: str | None):
    """A comparable Python value of an IEC literal as written in a .sys or read from FORTE.

    ``"Filling"``, ``'x'`` and ``Filling`` are the same string; ``T#1s`` and ``T#1000ms`` the same
    time (milliseconds); ``LREAL#1.0``, ``1`` and ``1.0`` the same number.
    """
    if text is None:
        return None
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "'\"":
        return text[1:-1]
    if re.fullmatch(r"(T|TIME)#.*", text, re.IGNORECASE):
        from iec61499_mgmt.verify import time_ms
        return ("TIME", time_ms(text))
    bare = text.split("#", 1)[1] if re.match(r"^[A-Z_]+#", text) else text
    if bare in ("TRUE", "FALSE"):
        return bare == "TRUE"
    try:
        return float(bare)
    except ValueError:
        return text
