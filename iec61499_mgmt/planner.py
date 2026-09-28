"""Pure planning: no sockets, implicit resource restarts or claimed atomicity."""
from typing import Literal

from .models import Digest, Model, Network, TypeLibrary
from .protocol import Command


class Plan(Model):
    """Reviewable commands for one network change, with pre- and post-checks."""
    base_hash: Digest
    desired_hash: Digest
    required_runtime_binary_sha256: Digest | None = None
    change_class: Literal["none", "parameter", "flow", "structural"]
    requires_quiescence: bool = True
    preflight: list[Command]
    commands: list[Command]
    verification: list[Command]


def plan(current: Network, desired: Network, library: TypeLibrary) -> Plan:
    """Compute the ordered commands that turn ``current`` into ``desired``."""
    if (current.resource, current.scope) != (desired.resource, desired.scope):
        raise ValueError("A plan cannot change resource or ownership scope")
    current.validate_library(library)
    desired.validate_library(library)
    old = {fb.name: fb for fb in current.instances}
    new = {fb.name: fb for fb in desired.instances}
    replaced = {n for n in old.keys() & new.keys()
                if (old[n].type, old[n].type_hash) != (new[n].type, new[n].type_hash)}
    removed = old.keys() - new.keys() | replaced
    added = new.keys() - old.keys() | replaced
    # Omitted values do not mean reset: that would require declared defaults or recreation.
    for n in old.keys() & new.keys() - replaced:
        if old[n].parameters.keys() - new[n].parameters.keys():
            raise ValueError(f"Parameter removal on {n} needs an explicit reset value")
    old_edges = {c.key(): c for c in current.connections}
    new_edges = {c.key(): c for c in desired.connections}

    def touches(edge, names):
        return any(p.rsplit(".", 1)[0] in names for p in (edge.source, edge.destination))

    disconnect = {k: c for k, c in old_edges.items() if k not in new_edges or touches(c, removed)}
    connect = {k: c for k, c in new_edges.items() if k not in old_edges or touches(c, added)}
    writes = [(n, p, v) for n, fb in sorted(new.items()) for p, v in sorted(fb.parameters.items())
              if n in added or old[n].parameters.get(p) != v]
    structural = bool(removed or added)
    flow = bool(disconnect or connect)
    # STOP all procedure FBs on a graph change; fixed FBs stay alive. This conservative
    # policy avoids assuming arbitrary pattern FB internal state survives rewiring.
    stop = sorted(old) if structural or flow else []
    start = sorted(new) if structural or flow else []
    commands = []

    def command(op, **kwargs):
        return Command(op=op, resource=current.resource, **kwargs)

    commands.extend(command("stop", name=n) for n in stop)
    commands.extend(command("disconnect", source=c.source, destination=c.destination)
                    for _, c in sorted(disconnect.items()))
    commands.extend(command("delete_fb", name=n) for n in sorted(removed))
    commands.extend(command("create_fb", name=n, type=new[n].type + (f"#{new[n].type_hash}" if new[n].type_hash else ""))
                    for n in sorted(added))
    commands.extend(command("write", destination=f"{n}.{p}", value=v.literal()) for n, p, v in writes)
    commands.extend(command("connect", source=c.source, destination=c.destination)
                    for _, c in sorted(connect.items()))
    commands.extend(command("start", name=n) for n in start)
    queries = [command("query_fbs"), command("query_connections")]
    return Plan(base_hash=current.digest(), desired_hash=desired.digest(),
                required_runtime_binary_sha256=library.runtime_binary_sha256,
                change_class="structural" if structural else "flow" if flow else "parameter" if writes else "none",
                preflight=queries + [command("query_type", type=t) for t in sorted({f.type for f in desired.instances})],
                commands=commands,
                verification=queries + [command("read", source=f"{n}.{p}")
                                         for n, fb in sorted(new.items()) for p in sorted(fb.parameters)])
