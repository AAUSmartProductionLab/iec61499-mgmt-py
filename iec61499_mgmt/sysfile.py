"""Flatten a 4diac IDE system (.sys) application into FORTE management commands.

Untyped subapplications become name prefixes (``EM_Filler.Dose``), as FORTE 3 creates
containers for dotted instance names. Connections through subapplication interface pins
are resolved to the FB ports they finally reach; pins with no FB on one side are dropped.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from defusedxml.ElementTree import parse

from .protocol import Command


@dataclass
class FlatApplication:
    """An application flattened to FORTE instance names and connections."""
    fbs: dict[str, str] = field(default_factory=dict)  # instance -> type
    parameters: dict[str, str] = field(default_factory=dict)  # "fb.port" -> literal
    event_connections: list[tuple[str, str]] = field(default_factory=list)
    data_connections: list[tuple[str, str]] = field(default_factory=list)

    def commands(self, resource: str = "RES", overrides: dict[str, str] | None = None) -> list[Command]:
        """CREATE FBs, WRITE parameters, CREATE connections (the order of a boot file)."""
        values = {**self.parameters, **(overrides or {})}
        result = [Command(op="create_fb", resource=resource, name=n, type=t) for n, t in self.fbs.items()]
        result += [Command(op="write", resource=resource, destination=d, value=v) for d, v in values.items()]
        result += [Command(op="connect", resource=resource, source=s, destination=d)
                   for s, d in self.event_connections + self.data_connections]
        return result


def load_application(path: str | Path, application: str) -> FlatApplication:
    """Read one application from a .sys file and flatten its subapplications."""
    root = parse(str(path)).getroot()
    app = next((a for a in root.iter("Application") if a.get("Name") == application), None)
    if app is None:
        raise ValueError(f"Application {application!r} not found in {path}")
    return flatten(app.find("SubAppNetwork"))


def load_resource(path: str | Path, device: str, resource: str) -> FlatApplication:
    """Read the network mapped to ``device.resource`` (what the IDE deploys) and flatten it."""
    root = parse(str(path)).getroot()
    for dev in root.iter("Device"):
        for res in dev.iter("Resource"):
            if (dev.get("Name"), res.get("Name")) == (device, resource):
                return flatten(res.find("FBNetwork"))
    raise ValueError(f"Resource {device}.{resource} not found in {path}")


def flatten(network) -> FlatApplication:
    """Flatten an FB network (application or resource) with its untyped subapplications."""
    flat = FlatApplication()
    pins: set[str] = set()
    edges = {"EventConnections": [], "DataConnections": []}

    def walk(network, prefix):
        for fb in network.findall("FB"):
            name = prefix + fb.get("Name")
            flat.fbs[name] = fb.get("Type")
            for p in fb.findall("Parameter"):
                flat.parameters[f"{name}.{p.get('Name')}"] = p.get("Value")
        for sub in network.findall("SubApp"):
            name = prefix + sub.get("Name")
            # The IDE writes SubAppInterfaceList; older generated files used InterfaceList.
            iface = sub.find("SubAppInterfaceList")
            for group in iface if iface is not None else sub.find("InterfaceList"):
                pins.update(f"{name}.{e.get('Name')}" for e in group)
            inner = sub.find("SubAppNetwork")
            if inner is not None:
                walk(inner, name + ".")
        for kind in edges:
            for c in network.findall(f"{kind}/Connection"):
                # Bare names inside a subapp network are that subapp's interface pins.
                edges[kind].append(tuple(prefix + c.get(k) for k in ("Source", "Destination")))

    walk(network, "")
    for kind, target in [("EventConnections", flat.event_connections), ("DataConnections", flat.data_connections)]:
        outgoing: dict[str, list[str]] = {}
        for s, d in edges[kind]:
            outgoing.setdefault(s, []).append(d)

        def ends(port, seen=()):
            if port not in pins:
                return [port]
            if port in seen:
                raise ValueError(f"Connection cycle through subapplication pin {port}")
            return [e for d in outgoing.get(port, []) for e in ends(d, seen + (port,))]
        for s, d in edges[kind]:
            if s not in pins:
                target.extend((s, e) for e in ends(d))
    return flat
