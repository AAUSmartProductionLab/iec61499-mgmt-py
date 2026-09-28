"""Build the type library (types.json) from 4diac type files and a running FORTE build.

Interfaces come from the .fbt files; type hashes come from the runtime (QUERY FBType), so the
library describes exactly the types that really exist in the pinned build.
"""
from __future__ import annotations

from pathlib import Path

from defusedxml.ElementTree import parse

from .models import FBType, Port, TypeLibrary
from .protocol import Client, Command
from .sysfile import FlatApplication

_GROUPS = [("EventInputs", "event", "input"), ("EventOutputs", "event", "output"),
           ("InputVars", "data", "input"), ("OutputVars", "data", "output"),
           ("Sockets", "adapter", "input"), ("Plugs", "adapter", "output")]


def read_fbt(path: str | Path) -> tuple[str, dict[str, Port]]:
    """Qualified type name and interface ports of one .fbt file."""
    root = parse(str(path)).getroot()
    info = root.find("CompilerInfo")
    package = info.get("packageName") if info is not None else None
    name = f"{package}::{root.get('Name')}" if package else root.get("Name")
    ports = {}
    interface = root.find("InterfaceList")
    for tag, kind, direction in _GROUPS:
        group = interface.find(tag) if interface is not None else None
        for element in group if group is not None else []:
            ports[element.get("Name")] = Port(
                kind=kind, direction=direction, data_type=None if kind == "event" else element.get("Type"),
                writable=kind == "data" and direction == "input")
    return name, ports


def read_types(folder: str | Path) -> dict[str, dict[str, Port]]:
    """Interfaces of all FB types (.fbt) below a type library folder."""
    return dict(read_fbt(p) for p in sorted(Path(folder).rglob("*.fbt")))


def query_hashes(client: Client, resource: str, names) -> dict[str, str]:
    """Type hash of each named type as reported by the runtime; raises if one is missing."""
    hashes = {}
    for name in names:
        response = client.execute(Command(op="query_type", resource=resource, type=name))
        reported = response.types[0]["Name"] if response.types else ""
        qualified, _, digest = reported.partition("#")
        if qualified != name:
            raise ValueError(f"Runtime reports {reported!r} for type {name}")
        hashes[name] = digest
    return hashes


def build_library(types: dict[str, dict[str, Port]], hashes: dict[str, str], build_id: str,
                  runtime_binary_sha256: str | None = None, fixed: FlatApplication | None = None,
                  scope: str = "PROC") -> TypeLibrary:
    """Library of the hashed types; every port of the fixed application becomes a boundary port."""
    boundary = {}
    for instance, typ in (fixed.fbs.items() if fixed else []):
        if instance != scope and not instance.startswith(scope + "."):
            boundary.update({f"{instance}.{port}": p for port, p in types.get(typ, {}).items()})
    return TypeLibrary(build_id=build_id, runtime_binary_sha256=runtime_binary_sha256,
                       types={n: FBType(name=n, type_hash=h, ports=types[n]) for n, h in sorted(hashes.items())},
                       boundary_ports=boundary)
