"""FORTE boot files: one management request per line, prefixed by its resource (empty = device)."""
from __future__ import annotations

from .models import Network, TypeLibrary
from .planner import plan
from .protocol import Command
from .sysfile import FlatApplication


def boot_file(commands: list[Command]) -> str:
    """Render commands as boot-file lines ``<resource>;<Request .../>``."""
    return "".join(f"{c.resource};{c.xml(i)}\n" for i, c in enumerate(commands, 1))


def deployment(fixed: FlatApplication, resource: str = "RES",
               resource_type: str = "iec61499::system::EMB_RES", overrides: dict[str, str] | None = None,
               procedure: Network | None = None, library: TypeLibrary | None = None) -> list[Command]:
    """Create the resource, the fixed application and the procedure, then start the resource."""
    commands = [Command(op="create_fb", resource="", name=resource, type=resource_type)]
    commands += fixed.commands(resource, overrides)
    if procedure is not None:
        if library is None:
            raise ValueError("A procedure needs the type library it was planned against")
        empty = Network(resource=procedure.resource, scope=procedure.scope)
        commands += [c for c in plan(empty, procedure, library).commands if c.op not in ("start", "stop")]
    commands.append(Command(op="start", resource="", name=resource))
    return commands
