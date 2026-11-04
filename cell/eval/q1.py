"""Q1 of docs/cirp-evaluation.md: the activation time, management commands and unavailability of a
change, online and by a restart, and how they scale with the change's and the program's size.

    python cell/eval/q1.py --forte runtime/fbe/build/modules-win/forte/build/forte/forte.exe
    python cell/eval/q1.py --forte ... --runs 1 --warmup 0 -v         # the pilot: one run per cell
    python cell/eval/q1.py --forte ... --resume cell/eval/results/q1-<when>.jsonl

Every run starts a fresh FORTE (cell/eval/scenarios.py's Bench, the filling module's IO simulated)
and appends one JSON line to cell/eval/results/q1-<when>.jsonl: the cell, the measurements, the
checks of the protocol and the setup. Runs go in a random order (``--seed``); the first
``--warmup`` runs are marked and left out of the analysis (cell/eval/q1_analysis.py). The AASs and
described skills, which take seconds to build, are built before the runs and kept in
cell/eval/results/q1-cache (delete it when the AAS generation changes).
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
import copy
import hashlib
import html
import json
import platform
import random
import re
import subprocess
import sys
import tempfile
import time
import traceback
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scenarios as sc                                                       # noqa: E402
from modgen import load                                                      # noqa: E402
from modgen.library import SKILL_STATES, STATES                              # noqa: E402
from modgen.spec import Composite                                            # noqa: E402
from modsync.desired import read, reconfigure                                # noqa: E402
from modsync.device import literal, outside, read_structure, read_values    # noqa: E402
from modsync.sync import LocalDeployer                                       # noqa: E402

SIZES = (1, 2, 4, 8, 16, 32)
BRANCHES = (2, 3)            # the module has three equipment items; branches sharing one are refused
PROGRAMS = (1, 5, 10, 20)
STARTS = ("execute", "idle")  # a value changed while an order runs, or between two orders
DISTURB = {(8, 1), (8, 20), (32, 1), (32, 20)}       # (steps, program size): Dispensing's d0 measured too
NEW = "Synthetic"
# On the Raspberry Pi (--pi), at the bench: the filling module as delivered (program size 1), a new
# composite of 1 and of 8 steps, a value from Execute and from Idle, and the two restarts.
PI_CELLS = ("A-flow-n1-k1-m1", "A-flow-n8-k1-m1", "C-parameter-n0-k0-m1-execute", "C-parameter-n0-k0-m1-idle",
            "D-flow-n8-k1-m1", "D-parameter-n0-k0-m1")
CACHE = sc.RESULTS / "q1-cache"
VERBOSE = False


def log(*parts) -> None:
    if VERBOSE:
        print(f"  {datetime.now():%H:%M:%S}", *parts, file=sys.stderr, flush=True)


def cached(kind: str, key: str, build):
    """``build()``, stored on disk under ``kind`` and the hash of ``key``."""
    path = CACHE / f"{kind}-{hashlib.sha256(key.encode()).hexdigest()[:16]}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    t = time.perf_counter()
    value = build()
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    log(f"built {kind} in {time.perf_counter() - t:.1f} s")
    return value


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


# The cells -------------------------------------------------------------------------------------------

def cells() -> list[dict]:
    out = [{"set": "A", "mode": "online", "change": "flow", "steps": n, "branches": 1, "program": m,
            "start": "execute"} for n in SIZES for m in PROGRAMS]
    out += [{"set": "B", "mode": "online", "change": "flow", "steps": 8, "branches": k, "program": 1,
             "start": "execute"} for k in BRANCHES]
    out += [{"set": "C", "mode": "online", "change": "parameter", "steps": 0, "branches": 0, "program": m,
             "start": s} for s in STARTS for m in PROGRAMS]
    out += [{"set": "D", "mode": "restart", "change": c, "steps": 8 if c == "flow" else 0,
             "branches": 1 if c == "flow" else 0, "program": m, "start": "execute"}
            for c in ("flow", "parameter") for m in PROGRAMS]
    for c in out:
        c["id"] = (f"{c['set']}-{c['change']}-n{c['steps']}-k{c['branches']}-m{c['program']}"
                   + (f"-{c['start']}" if c["set"] == "C" else ""))
    return out


# The programs and the changes -----------------------------------------------------------------------

def program(m: int):
    """The filling module with m - 1 copies of Dispensing generated in (program size m)."""
    spec = load(sc.FILLING)
    base = spec.composites["Dispensing"]
    extra = {f"Dispensing{i:02d}": base.model_copy(deep=True) for i in range(2, m + 1)}
    return spec.model_copy(update={"composites": {**spec.composites, **extra}})


CYCLE = [("MoveAxis", {"Position": 40.0}), ("Dispense", {"Volume": "Volume", "FlowRate": 1.0}), ("Home", {}),
         ("Weigh", {})]
BRANCH = {"axis": [("MoveAxis", {"Position": 40.0}), ("Home", {})],
          "pump": [("Dispense", {"Volume": "Volume", "FlowRate": 1.0})],
          "scale": [("Tare", {}), ("Weigh", {})]}


def synthetic(n: int, k: int) -> Composite:
    """A composite of n steps: the dose cycle repeated (k = 1), or k parallel branches holding n steps,
    each branch on its own equipment item (axis, pump, scale)."""
    counter = iter(range(1, 1000))

    def step(skill: str, bind: dict) -> dict:
        return {skill: dict(bind), "as": f"S{next(counter):02d}"}

    if k == 1:
        execute = [step(*CYCLE[i % len(CYCLE)]) for i in range(n)]
    else:
        items = ["axis", "pump", "scale"][:k]
        sizes = [n // k + (1 if i < n % k else 0) for i in range(k)]
        branches = [[step(*BRANCH[item][j % len(BRANCH[item])]) for j in range(size)]
                    for item, size in zip(items, sizes)]
        execute = [{"parallel": branches, "as": "P01"}]
    return Composite(**{"description": f"Synthetic composite of {n} steps in {k} branch(es) (Q1)",
                        "parameters": {"Volume": {"unit": "mL", "minimum": 0.5, "maximum": 10.0, "default": 1.0,
                                                  "description": "Fill volume"}},
                        "execute": execute, "stop": ["Home"]})


def with_flow(spec, n: int, k: int):
    return spec.model_copy(update={"composites": {**spec.composites, NEW: synthetic(n, k)}})


def with_parameter(spec):
    composites = dict(spec.composites)
    composites["Dispensing"] = sc._with_bound(composites["Dispensing"].model_copy(deep=True), "Dispense", "FlowRate", 2.0)
    return spec.model_copy(update={"composites": composites})


def delivered_spec(spec, target: str = "pc") -> tuple[dict, list[dict]]:
    """The AAS of a module spec as delivered (modreg, as scenarios.delivered does for a spec file), but
    without the derived Capability Description: the reconciler does not read it, and deriving it takes
    hours for 20 composites (docs/cirp-evaluation.md, Q1). The same for every program size."""
    def build():
        from modreg import model, profile
        describer = profile.Describer(spec, target, None, None, None, None)
        describer.derive = False
        module, *components = [model.build(model.profile(asset, global_asset_id=asset_id))
                               for asset, asset_id in describer.build()]
        return [module, components]
    module, components = cached("aas-underived", spec.model_dump_json() + target, build)
    return copy.deepcopy(module), copy.deepcopy(components)


def with_composite(module: dict, components: list[dict], name: str, composite: Composite) -> dict:
    """``composite`` described in the module's AAS as ``name``, as the skill editor saves a skill."""
    def build():
        from modreg.offer import described_skill
        return described_skill(module, components, name, composite)
    return copy.deepcopy(cached("described", json.dumps([digest(module), name, composite.model_dump_json()]), build))


# Timing from OPC UA notifications --------------------------------------------------------------------

class Clock:
    """The changes of one variable with FORTE's source timestamps (or, lacking them, the time the
    notification came), from an OPC UA subscription. The server publishes every 100 ms: a change is
    known here up to that long after it happened, so the clock is waited on, not read at once."""

    def __init__(self, ua, path: str):
        self.changes: list[tuple[object, float, str]] = []
        clock = self

        class Handler:
            def datachange_notification(self, node, value, data):
                ts = data.monitored_item.Value.SourceTimestamp
                clock.changes.append((value, ts.timestamp() if ts else time.time(), "source" if ts else "client"))

        self.sub = ua.client.create_subscription(0, Handler())
        self.sub.subscribe_data_change(ua.node(path))

    def first(self, timeout: float = 5.0) -> None:
        """Until the first notification (the value as it is) has come."""
        deadline = time.monotonic() + timeout
        while not self.changes:
            if time.monotonic() > deadline:
                raise TimeoutError("no first notification")
            time.sleep(0.01)

    def between(self, start, end) -> tuple[float | None, str]:
        """Seconds from the first change to ``start`` to the next change to ``end`` after it."""
        t0 = next((t for v, t, _ in self.changes if v == start), None)
        hit = next(((t, how) for v, t, how in self.changes if v == end and t0 is not None and t >= t0), None)
        return (None, "") if t0 is None or hit is None else (hit[0] - t0, hit[1])

    def wait(self, start, end, give_up=(), timeout: float = 120.0) -> tuple[float | None, str]:
        """``between(start, end)`` once it is known; (None, "") after ``timeout`` or a change to one
        of ``give_up`` after ``start``."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            found = self.between(start, end)
            if found[0] is not None:
                return found
            seen = [v for v, _, _ in self.changes]
            if start in seen and any(v in give_up for v in seen[seen.index(start):]):
                return None, ""
            time.sleep(0.01)
        return None, ""

    def trace(self) -> list:
        """The changes, in seconds after the first notification, for the record."""
        t0 = self.changes[0][1] if self.changes else 0.0
        return [[v, round(t - t0, 4), how] for v, t, how in self.changes]

    def close(self) -> None:
        self.sub.delete()


def unavailable(changes, available) -> float | None:
    """Seconds from the first change of the module's state away from ``available`` to the last change
    back to it, by FORTE's timestamps (``changes`` of a Clock)."""
    away = next((t for v, t, _ in changes if v != available), None)
    back = next((t for v, t, _ in reversed(changes) if v == available), None)
    return None if away is None or back is None or back < away else back - away


def dispense_once(bench, meanwhile=None) -> tuple[float | None, str, object, list]:
    """Dispensing 1.0 mL run once: its duration from Running to Succeeded by FORTE's timestamps, and
    its state's changes. ``meanwhile``: called right after the Start was accepted (the change, made
    while Dispensing runs); its result is returned."""
    clock = Clock(bench.ua, "Skills/Dispensing/State")
    try:
        clock.first()
        assert bench.ua.call("Skills/Dispensing/Start", sc.SESSION, 1.0) == [True, 0]
        result = meanwhile() if meanwhile else None
        seconds, how = clock.wait(SKILL_STATES["Running"], SKILL_STATES["Succeeded"],
                                  give_up=(SKILL_STATES["Failed"], SKILL_STATES["Aborted"]))
        return seconds, how, result, clock.trace()
    finally:
        clock.close()


# The checks -----------------------------------------------------------------------------------------

def boot_set(boot: str) -> list[tuple]:
    """What a boot file creates, writes and connects, without request ids or order (sorted)."""
    out = []
    for ln in boot.splitlines():
        if 'Action="CREATE"' in ln and (m := re.search(r'<FB Name="([^"]+)" Type="([^"]*)"', ln)):
            out.append(("fb", m.group(1), m.group(2)))
        elif m := re.search(r'<Connection Source="([^"]*)" Destination="([^"]*)"', ln):
            out.append(("write" if 'Action="WRITE"' in ln else "connect", m.group(1), m.group(2)))
    return sorted(out)


def predicted(base: str, changed: str) -> dict:
    """The management commands the module rules call for, taken from the generator's boot files of the
    program before and after the change (not from the reconciler): an instance more is created and
    started, a connection more made and one fewer removed, a value more or changed written, and each
    INIT link from the running program into a new instance fired once."""
    before, after = set(boot_set(base)), set(boot_set(changed))
    more, fewer = after - before, before - after
    fbs = {a for kind, a, _ in more if kind == "fb"}
    new = lambda port: port.rpartition(".")[0] in fbs                                # noqa: E731
    return {"create_fb": len(fbs), "start": len(fbs),
            "write": sum(kind == "write" for kind, _, _ in more),
            "connect": sum(kind == "connect" for kind, _, _ in more),
            "disconnect": sum(kind == "connect" for kind, _, _ in fewer),
            "trigger": sum(kind == "connect" and s.endswith(".INITO") and d.endswith(".INIT") and not new(s) and new(d)
                           for kind, s, d in more),
            "other": 0}


READING = ("query_fbs", "query_connections", "query_type", "read")


def measured(commands) -> dict:
    """The management commands sent that change the program, by operation (a write of ``$e``: an
    event fired, a trigger); the reconciler's reading before and after (queries, READ) left out."""
    ops = Counter("trigger" if c.op == "write" and c.value == "$e" else c.op for c in commands if c.op not in READING)
    keys = ("create_fb", "start", "write", "connect", "disconnect", "trigger")
    return {**{k: ops.get(k, 0) for k in keys}, "other": sum(v for k, v in ops.items() if k not in keys)}


def reading(commands) -> dict:
    """The reconciler's reading of the program before and after the change, by operation."""
    return dict(Counter(c.op for c in commands if c.op in READING))


def program_is(bench, boot: str, running: bool = False) -> dict:
    """What differs between the program FORTE runs and the one the generator's boot file ``boot``
    creates: instances and their types, connections, and the values it writes (read back); empty
    lists if nothing. Independent of the AAS and of the reconciler's own reading and comparing.
    ``running``: also every instance running and every skill's OPC UA method open (``UaStart.QO``),
    as after a boot."""
    snap = read_structure(bench.client, bench.host, bench.port)
    rel = lambda name: outside(name, snap.container)                                  # noqa: E731
    want = boot_set(boot)
    fbs = {(rel(a), b) for kind, a, b in want if kind == "fb" and a != "RES"}
    connections = {(rel(a), rel(b)) for kind, a, b in want if kind == "connect"}
    values = {rel(b): html.unescape(a) for kind, a, b in want if kind == "write"}
    opened = [f"{n}.QO" for n, _ in fbs if n.endswith(".UaStart")] if running else []
    read_values(bench.client, snap, [*values, *opened])
    return {"fbs": [list(x) for x in sorted(fbs ^ set(snap.fbs.items()))[:5]],
            "connections": [list(x) for x in sorted(connections ^ snap.connections)[:5]],
            "values": sorted([p, v, snap.values.get(p)] for p, v in values.items()
                             if literal(snap.values.get(p)) != literal(v))[:5],
            "states": sorted([n, s] for n, s in snap.status.items() if running and s != "RUNNING")[:5],
            "closed": sorted(p for p in opened if literal(snap.values.get(p)) is not True)[:5],
            "compared": [len(fbs), len(connections), len(values)]}


def same(found: dict) -> bool:
    return not any(found.get(k) for k in ("fbs", "connections", "values", "states", "closed"))


# The OPC UA server announces itself (LDS-ME) and registers with a discovery server it finds, such as
# the FORTE of the run before, still announced while it stops: a registration that fails, and its
# connection, are logged as errors of the OPC UA library, and do not touch the module's program.
REGISTERING = ("Discovery server", "RegisterServer", "[OPC UA LOGGER] error/network")


def forte_errors(log_: str) -> list[str]:
    """The ERROR lines of a FORTE's log (an event dropped from a full queue, a block that failed): a run
    is right only without them. The OPC UA server's failed registrations with a discovery server are
    not among them (``registering_errors``)."""
    return [ln for ln in _errors(log_) if not any(r in ln for r in REGISTERING)]


def registering_errors(log_: str) -> list[str]:
    return [ln for ln in _errors(log_) if any(r in ln for r in REGISTERING)]


def logged(out: dict, checks: dict, bench, *markers) -> None:
    """V10 from the logs of the FORTEs the ``markers`` name (the bench's: a folder on the PC, the last
    start on the Pi); failed registrations counted apart."""
    logs = [bench.log(m) for m in markers]
    errors = [e for text in logs for e in forte_errors(text)]
    out["forte_errors"] = errors[:5]
    out["registering_errors"] = sum(len(registering_errors(text)) for text in logs)
    checks["V10"] = not errors


def _errors(log_: str) -> list[str]:
    return [ln.strip() for ln in log_.splitlines() if "ERROR" in ln]


# The runs -------------------------------------------------------------------------------------------

BOOTS: dict[str, str] = {}


def boot_of(bench, spec, key: str) -> str:
    if key not in BOOTS:
        BOOTS[key] = bench.boot(spec)
    return BOOTS[key]


@contextmanager
def recording(client, sent: list):
    """Every management command the client sends meanwhile, in ``sent``."""
    real = client.execute

    def execute(command):
        sent.append(command)
        return real(command)

    client.execute = execute
    try:
        yield
    finally:
        client.execute = real


def timed_execute(bench) -> dict:
    """Occupy, Reset and Start, each part timed (the module from Stopped to Execute)."""
    t = time.perf_counter()
    bench.ua.call("Occupation/Occupy", sc.SESSION)
    bench.ua.call("Module/Reset", sc.SESSION)
    bench.ua.expect("Module/State", STATES["Idle"], timeout=bench.reset_s)
    reset = time.perf_counter() - t
    t = time.perf_counter()
    bench.ua.call("Module/Start", sc.SESSION)
    bench.ua.expect("Module/State", STATES["Execute"], timeout=10)
    return {"reset_s": reset, "start_s": time.perf_counter() - t}


def between_orders(bench) -> None:
    """The module Idle and free, as between two orders: occupied, reset, released."""
    bench.ua.call("Occupation/Occupy", sc.SESSION)
    bench.ua.call("Module/Reset", sc.SESSION)
    bench.ua.expect("Module/State", STATES["Idle"], timeout=bench.reset_s)
    bench.ua.call("Occupation/Release", sc.SESSION)
    bench.ua.expect("Occupation/Occupied", False)


def persisting(bench, work: Path, boot: str):
    """Where the reconciler amends the module's boot file: on the Pi its own (over SSH, as deployed),
    on the PC a folder of the run's."""
    return bench.deployer if bench.target == "pi" else deployer_with(work / f"deploy{time.monotonic_ns()}", boot)


def deployer_with(folder: Path, boot: str) -> LocalDeployer:
    """A boot file of the module's own, as the deployer of an installed FORTE keeps it."""
    (folder / "boot").mkdir(parents=True, exist_ok=True)
    (folder / "boot" / "forte.fboot").write_text(boot, encoding="utf-8", newline="\n")
    return LocalDeployer(folder)


def after_change(bench, out: dict, checks: dict, done: list, wanted: dict, components: list, boot: str,
                 generated: str, sent: list, deployer) -> None:
    """The checks V2 to V4 and V8 after an online change (``boot``: the program before it)."""
    checks["V2"] = any("verified by reading the program back" in line for line in done)
    checks["V3"] = read(bench.client, bench.host, bench.port, wanted, components).differences.empty
    out["V3g"] = program_is(bench, generated)
    checks["V3g"] = same(out["V3g"])
    out["predicted"], out["measured"], out["reading"] = predicted(boot, generated), measured(sent), reading(sent)
    checks["V4"] = out["predicted"] == out["measured"]
    checks["V8"] = boot_set(deployer.load()) == boot_set(generated)


def run_online_flow(bench, cell: dict, first: bool, work: Path) -> dict:
    n, k, m = cell["steps"], cell["branches"], cell["program"]
    base = program(m)
    module, components = delivered_spec(base, bench.target)
    wanted = with_composite(module, components, NEW, synthetic(n, k))
    boot = boot_of(bench, base, f"base-{m}")
    generated = boot_of(bench, with_flow(base, n, k), f"flow-{n}-{k}-{m}")
    out, checks = {}, {}
    log("start FORTE")
    bench.start(boot)
    bench.execute()
    first_read = read(bench.client, bench.host, bench.port, module, components)
    checks["V1"] = first_read.differences.empty
    out["V1g"] = program_is(bench, boot)
    checks["V1g"] = same(out["V1g"])
    out["instances_before"], out["connections_before"] = len(first_read.snapshot.fbs), len(first_read.snapshot.connections)
    if (n, m) in DISTURB:
        log("Dispensing alone")
        out["d0_s"], out["d0_clock"], _, out["d0_trace"] = dispense_once(bench)
    deployer = persisting(bench, work, boot)
    stats: dict = {}
    sent: list = []

    def change():
        with recording(bench.client, sent):
            t = time.perf_counter()
            done, _ = reconfigure(bench.client, bench.host, bench.port, wanted, components, deployer=deployer, stats=stats)
            out["t_act_s"] = time.perf_counter() - t
        return done

    state = Clock(bench.ua, "Module/State")
    try:
        state.first()
        log("Dispensing with the change meanwhile")
        out["d1_s"], out["d1_clock"], done, out["d1_trace"] = dispense_once(bench, change)
    finally:
        out["state_trace"] = state.trace()
        state.close()
    checks["V6"] = out["d1_s"] is not None
    checks["V9"] = bool(out["state_trace"]) and all(v == STATES["Execute"] for v, _, _ in out["state_trace"])
    after_change(bench, out, checks, done, wanted, components, boot, generated, sent, deployer)
    out.update(stats)
    if first:
        log("the new composite run")
        t = time.perf_counter()
        try:
            bench.run(NEW, 1.0, timeout=900)
            checks["V5"] = True
        except Exception as exc:                       # noqa: BLE001 (a failed check, recorded)
            checks["V5"], out["V5_error"] = False, f"{type(exc).__name__}: {exc}"[:300]
        out["new_run_s"] = time.perf_counter() - t
    bench.stop()
    logged(out, checks, bench, bench.marker)
    return {"out": out, "checks": checks}


def run_online_parameter(bench, cell: dict, work: Path) -> dict:
    m, start = cell["program"], cell["start"]
    base = program(m)
    module, components = delivered_spec(base, bench.target)
    wanted = sc.with_value(module)
    boot = boot_of(bench, base, f"base-{m}")
    generated = boot_of(bench, with_parameter(base), f"parameter-{m}")
    out, checks = {}, {}
    bench.start(boot)
    if start == "execute":
        bench.execute()
    else:
        between_orders(bench)
    checks["V1"] = read(bench.client, bench.host, bench.port, module, components).differences.empty
    out["V1g"] = program_is(bench, boot)
    checks["V1g"] = same(out["V1g"])
    deployer = persisting(bench, work, boot)
    stats: dict = {}
    sent: list = []
    state = Clock(bench.ua, "Module/State")
    try:
        state.first()
        t0 = time.perf_counter()
        if start == "execute":
            bench.idle()
            out["stop_s"] = time.perf_counter() - t0
        with recording(bench.client, sent):
            t = time.perf_counter()
            done, _ = reconfigure(bench.client, bench.host, bench.port, wanted, components, deployer=deployer, stats=stats)
            out["t_act_s"] = time.perf_counter() - t
        if start == "execute":
            out.update(timed_execute(bench))
            out["u_s"] = time.perf_counter() - t0
        else:
            out["u_s"] = out["t_act_s"]
        time.sleep(0.3)                                # the last notifications (published every 100 ms)
    finally:
        out["state_trace"] = state.trace()
        if start == "execute":
            out["u_clock_s"] = unavailable(state.changes, STATES["Execute"])
        state.close()
    if start == "idle":
        checks["V9"] = (bool(out["state_trace"]) and all(v == STATES["Idle"] for v, _, _ in out["state_trace"])
                        and bench.ua.value("Occupation/Occupied") is False)
    after_change(bench, out, checks, done, wanted, components, boot, generated, sent, deployer)
    out.update(stats)
    bench.stop()
    logged(out, checks, bench, bench.marker)
    return {"out": out, "checks": checks}


def run_restart(bench, cell: dict) -> dict:
    m = cell["program"]
    base = program(m)
    new = with_flow(base, 8, 1) if cell["change"] == "flow" else with_parameter(base)
    module, components = delivered_spec(new, bench.target)
    out, checks = {}, {}
    t = time.perf_counter()
    boot = bench.boot(new)
    out["generate_s"] = time.perf_counter() - t
    out["boot_lines"] = len(boot.splitlines())
    bench.start(boot_of(bench, base, f"base-{m}"))
    before = bench.marker
    bench.execute()
    t0, wall = time.perf_counter(), time.time()
    bench.stop()
    bench.start(boot)
    out["load_s"] = time.perf_counter() - t0
    state = Clock(bench.ua, "Module/State")            # its first notification: Stopped, as the boot set it
    try:
        out.update(timed_execute(bench))
        out["u_s"] = time.perf_counter() - t0
        time.sleep(0.3)
    finally:
        out["state_trace"] = state.trace()
        executing = next((t for v, t, _ in state.changes if v == STATES["Execute"]), None)
        state.close()
    out["u_idle_s"] = out["load_s"] + out["reset_s"]
    # Execute by the server's timestamp (a sample, every 50 ms), on the PC's clock as ``wall`` is. The
    # first value of a new subscription (Stopped) is stamped when sampled, not when set: not used.
    out["u_clock_s"] = None if executing is None else executing - wall
    checks["V7"] = read(bench.client, bench.host, bench.port, module, components).differences.empty
    out["V7g"] = program_is(bench, boot)
    checks["V7g"] = same(out["V7g"])
    bench.stop()
    # On the Pi the log is the container's since its last start: the FORTE the restart started.
    logged(out, checks, bench, *([before, bench.marker] if before is not None else [bench.marker]))
    return {"out": out, "checks": checks}


def prepare(chosen: list[dict], target: str = "pc") -> None:
    """Build the AASs and described skills the cells need, before anything is timed."""
    for m in sorted({c["program"] for c in chosen}):
        base = program(m)
        log(f"program {m}: AAS")
        module, components = delivered_spec(base, target)
        for c in chosen:
            if c["program"] != m:
                continue
            if c["mode"] == "online" and c["change"] == "flow":
                with_composite(module, components, NEW, synthetic(c["steps"], c["branches"]))
            elif c["mode"] == "restart":
                delivered_spec(with_flow(base, 8, 1) if c["change"] == "flow" else with_parameter(base), target)


# The session ----------------------------------------------------------------------------------------

def setup(forte: Path | None, seed: int, pi=None) -> dict:
    root = Path(__file__).resolve().parents[2]
    commit = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "-C", str(root), "status", "--porcelain", "--untracked-files=no",
                                 "aas61499-tools", "iec61499-mgmt-py", "cell/eval", "cell/sim"],
                                capture_output=True, text=True).stdout.strip())
    if pi is not None:                             # FORTE in its container on the Pi: its binary there
        where = pi.deployer.args
        found = subprocess.run(["ssh", f"{where.user}@{where.host}", "sha256sum ~/forte/forte; uname -m"],
                               capture_output=True, text=True).stdout.split()
        forte_id, digest = f"{where.user}@{where.host}:~/forte/forte ({found[-1] if found else '?'})", (found or ["?"])[0][:16]
    else:
        forte_id, digest = str(forte), hashlib.sha256(forte.read_bytes()).hexdigest()[:16]
    return {"machine": platform.platform(), "cpu": platform.processor(), "python": platform.python_version(),
            "forte": forte_id, "forte_sha256": digest, "target": "pi" if pi is not None else "pc",
            "commit": commit[:12], "tools_dirty": dirty, "seed": seed}


def main() -> None:
    global VERBOSE
    ap = argparse.ArgumentParser()
    ap.add_argument("--forte", type=Path, help="FORTE on the PC (not with --pi)")
    ap.add_argument("--pi", action="store_true",
                    help="the module on its Raspberry Pi (the spec's target pi), someone at the bench: PI_CELLS")
    ap.add_argument("--runs", type=int, default=30)
    ap.add_argument("--warmup", type=int, default=5)
    ap.add_argument("--seed", type=int, default=20261103)
    ap.add_argument("--only", nargs="*", help="cell sets (A B C D) or cell ids")
    ap.add_argument("--programs", nargs="*", type=int, help="only these program sizes")
    ap.add_argument("--resume", type=Path)
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    VERBOSE = a.verbose
    if not a.pi and a.forte is None:
        ap.error("--forte is needed on the PC")
    chosen = [c for c in cells() if (not a.only or c["set"] in a.only or c["id"] in a.only)
              and (not a.programs or c["program"] in a.programs) and (not a.pi or c["id"] in PI_CELLS)]
    rng = random.Random(a.seed)
    order = [(c, r) for c in chosen for r in range(a.runs)]
    rng.shuffle(order)
    order = [(rng.choice(chosen), -1 - i) for i in range(a.warmup)] + order
    out = a.resume or sc.RESULTS / f"q1-{datetime.now():%Y-%m-%dT%H%M}.jsonl"
    done = set()
    if a.resume and a.resume.exists():
        for line in a.resume.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r.get("ok") or r.get("failure") in ("method", "check"):
                done.add((r["cell"]["id"], r["replicate"]))
    pi = sc.PiBench() if a.pi else None
    original = pi.deployer.load() if pi else None     # the Pi's program, brought back after the runs
    env = setup(a.forte, a.seed, pi)
    prepare(chosen, "pi" if a.pi else "pc")
    firsts = {c["id"]: min((r for cc, r in order if cc["id"] == c["id"] and r >= 0), default=None) for c in chosen}
    with tempfile.TemporaryDirectory() as tmp:
        bench = pi or sc.Bench(a.forte, Path(tmp))
        try:
            for i, (cell, rep) in enumerate(order):
                if (cell["id"], rep) in done:
                    continue
                record = {"cell": cell, "replicate": rep, "warmup": rep < 0, "index": i,
                          "time": datetime.now().isoformat(), **env}
                started = time.perf_counter()
                try:
                    if cell["mode"] == "restart":
                        result = run_restart(bench, cell)
                    elif cell["change"] == "parameter":
                        result = run_online_parameter(bench, cell, Path(tmp))
                    else:
                        result = run_online_flow(bench, cell, rep == firsts[cell["id"]], Path(tmp))
                    record.update(result)
                    record["ok"] = all(v for v in result["checks"].values() if v is not None)
                    if not record["ok"]:
                        record["failure"] = "check"
                except Exception as exc:                       # noqa: BLE001 (recorded, then the next run)
                    bench.stop()
                    infra = isinstance(exc, (OSError, TimeoutError, ConnectionError))
                    record.update({"ok": False, "failure": "infrastructure" if infra else "method",
                                   "error": f"{type(exc).__name__}: {exc}"[:800], "trace": traceback.format_exc()[-1500:],
                                   "forte_errors": forte_errors(bench.log(bench.marker))[:5]})
                record["run_s"] = time.perf_counter() - started
                with out.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(record, default=str) + "\n")
                o = record.get("out", {})
                bad = [k for k, v in record.get("checks", {}).items() if v is False]
                print(f"{i + 1}/{len(order)} {cell['id']} rep {rep}: {'ok' if record['ok'] else record.get('failure')} "
                      f"{bad or ''} t_act={o.get('t_act_s', '')} u={o.get('u_s', '')} run={record['run_s']:.1f}s"
                      f"{' ' + record['error'][:120] if record.get('error') else ''}", flush=True)
        finally:
            bench.close()
            if pi is not None:
                pi.deployer.restart(original)
    print(out)


if __name__ == "__main__":
    main()
