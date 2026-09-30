"""Compare a running resource with the expected procedure network (read-back after a change)."""
from __future__ import annotations

import math
import re

from .models import IECValue, Network
from .protocol import Client, Command


def same_value(expected: IECValue, observed: str) -> bool:
    """True if a READ result equals the expected value (tolerates typed literals like LREAL#1.0)."""
    text = observed.split("#", 1)[1] if re.match(r"^[A-Z_]+#", observed) and expected.type != "TIME" else observed
    if expected.type == "LREAL":
        try:
            return math.isclose(float(text), expected.value, rel_tol=1e-9, abs_tol=1e-12)
        except ValueError:
            return False
    if expected.type == "TIME":
        return time_ms(text) == expected.value
    return text == expected.literal()


def time_ms(text: str) -> float | None:
    """Milliseconds of an IEC TIME literal such as T#1s500ms, or None if unparsable."""
    match = re.fullmatch(r"(?:T|TIME)#(-)?((?:\d+(?:\.\d+)?(?:d|h|ms|m|s|us|ns)_?)+)", text.strip(), re.IGNORECASE)
    if not match:
        return None
    factors = {"d": 86400000, "h": 3600000, "m": 60000, "s": 1000, "ms": 1, "us": 1e-3, "ns": 1e-6}
    total = sum(float(v) * factors[u.lower()] for v, u in re.findall(r"(\d+(?:\.\d+)?)(ms|us|ns|d|h|m|s)", match[2], re.I))
    return -total if match[1] else total


def verify(client: Client, network: Network, parameters: bool = True, running: bool = True) -> list[str]:
    """Differences between the runtime and ``network`` inside its scope; empty means consistent."""
    prefix = network.scope + "."
    problems = []
    fbs = [fb for fb in client.execute(Command(op="query_fbs", resource=network.resource)).fbs
           if fb.get("Name", "").startswith(prefix)]
    observed = {fb["Name"]: fb for fb in fbs}
    expected = {fb.name: fb for fb in network.instances}
    problems += [f"missing instance {n}" for n in sorted(expected.keys() - observed.keys())]
    problems += [f"unexpected instance {n}" for n in sorted(observed.keys() - expected.keys())]
    for name in sorted(expected.keys() & observed.keys()):
        typ = observed[name].get("Type", "").partition("#")[0]
        if typ != expected[name].type:
            problems.append(f"{name} has type {typ}, expected {expected[name].type}")
        if running and observed[name].get("Status") != "RUNNING":
            problems.append(f"{name} is {observed[name].get('Status')}, expected RUNNING")
    connections = client.execute(Command(op="query_connections", resource=network.resource)).connections
    edges = {(c["Source"], c["Destination"]) for c in connections
             if c["Source"].startswith(prefix) or c["Destination"].startswith(prefix)}
    wanted = {(c.source, c.destination) for c in network.connections}
    problems += [f"missing connection {s} -> {d}" for s, d in sorted(wanted - edges)]
    problems += [f"unexpected connection {s} -> {d}" for s, d in sorted(edges - wanted)]
    if parameters:
        for fb in network.instances:
            if fb.name not in observed:
                continue
            for port, value in sorted(fb.parameters.items()):
                source = f"{fb.name}.{port}"
                actual = client.execute(Command(op="read", resource=network.resource, source=source)).read_value(source)
                if not same_value(value, actual):
                    problems.append(f"{source} = {actual}, expected {value.literal()}")
    return problems
