"""Keep a module, its module spec and its AAS in step, both ways.

- pull: read what runs on the module, find the module spec and target it was generated from, report
  the drift, and describe the module (AAS) with the values that really run.
- push: bring the module to its spec. Changed skill parameters are written online (a skill takes
  them over at its next start); new instances (a module level skill composed of the module's
  primitives) are created online while the module runs; both are read back and saved in the boot
  file. Any other change (removed or retyped instances, rewiring, values only read at INIT such
  as OPC UA paths and IO ids) is deployed as a new boot file and a FORTE restart, because FORTE
  3.3 crashed deleting a resource with IO handles (see pi.py). Writes and restarts only while the
  module is Stopped, Idle or Aborted and not occupied, unless forced.
- watch: pull whenever a module comes online or its program changes.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.util
from pathlib import Path
import time

from iec61499_mgmt.bootfile import boot_file, deployment
from iec61499_mgmt.protocol import Client, Command, ManagementError
from iec61499_mgmt.sysfile import FlatApplication
from modgen import load
from modgen.fbxml import GENERIC
from modgen.library import STATES

from .compare import Candidate, Drift, closest, compare, expected_values, init_link, owner, parameters
from .device import Snapshot, read_structure, read_values

ROOT = Path(__file__).resolve().parents[2]              # the repository (paths in reports are relative to it)
PI_TOOL = ROOT / "deploy" / "pi.py"
# Library internals read for the guard: the state manager's and the occupation's logic FBs.
MODULE_STATE, OCCUPIED = "Module.Logic.State", "Occupation.Logic.Occupied"
# The module's name as deployed: every generated module has this parameter.
MODULE_NAME = "Occupation.Module"
QUIET = {STATES["Stopped"], STATES["Idle"], STATES["Aborted"]}


def candidates(paths) -> list[Candidate]:
    """Every target of every module spec: the programs a module may be running."""
    return [Candidate(Path(p), spec, t) for p in paths for spec in [load(Path(p))] for t in spec.targets]


def relative(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return Path(path).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


@dataclass
class Status:
    """A module as read: the closest spec and target, the snapshot and its drift from them.

    ``identified``: the program is a generated module (it names itself) with a spec among the
    candidates; otherwise ``candidate`` is only the structurally closest one.
    """
    candidate: Candidate
    snapshot: Snapshot
    drift: Drift
    distance: int
    overrides: dict[str, str]
    module: str | None = None
    identified: bool = False

    def summary(self) -> str:
        c, snap = self.candidate, self.snapshot
        where = f"{snap.host}:{snap.port}"
        if snap.empty:
            return f"{where}: no program"
        if not self.identified:
            what = f"module {self.module}, which no module spec here describes" if self.module else                 "a program that is not a generated module"
            names = ", ".join(sorted(snap.fbs)[:8]) + (", ..." if len(snap.fbs) > 8 else "")
            return f"{where}: {what} ({len(snap.fbs)} instances: {names})"
        state = "in sync with" if self.drift.empty else f"{self.drift.size()} differences from"
        return f"{where}: {c.spec.module} ({len(snap.fbs)} instances), {state} {relative(c.path)} target {c.target}"


def inspect(client: Client, host: str, port: int, cands: list[Candidate], resource: str = "RES",
            overrides: dict[str, str] | None = None) -> Status:
    """Read the module and compare it with the closest candidate (``overrides``: values deployed on purpose
    instead of the spec's, e.g. another Modbus endpoint)."""
    overrides = overrides or {}
    snap = read_structure(client, host, port, resource)
    read_values(client, snap, [MODULE_NAME])
    module = snap.values.pop(MODULE_NAME, None)
    named = [c for c in cands if c.spec.module == module]
    best, dist = closest(snap, named or cands)
    values = {**expected_values(best.spec, best.app), **overrides}
    # Also the parameters of skill instances that are not in the generated program (added online).
    online = set(parameters(best.spec, snap.fbs))
    read_values(client, snap, sorted(set(values) | online))
    return Status(best, snap, compare(best.app, values, snap, online), dist, overrides, module, bool(named))


def fingerprint(status: Status) -> str:
    """Changes when the running program or its parameter values change."""
    s = status.snapshot
    text = repr((sorted(s.fbs.items()), sorted(s.connections), sorted(s.values.items())))
    return hashlib.sha256(text.encode()).hexdigest()


# Deployment ------------------------------------------------------------------------------------

class PiDeployer:
    """Boot file on a Raspberry Pi with FORTE in its container (deploy/pi.py install)."""

    def __init__(self, host: str, user: str, port: int = 61499):
        spec = importlib.util.spec_from_file_location("pi_tool", PI_TOOL)
        self.pi = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.pi)
        self.args = type("Args", (), {"host": host, "user": user, "port": port})()

    def save(self, boot: str):
        """Replace the boot file; the running program is not touched."""
        self.pi.ssh(self.args, "cat > ~/forte/boot/forte.fboot", stdin=boot)

    def restart(self, boot: str):
        """Replace the boot file and restart FORTE with it."""
        self.pi.ssh(self.args, "cat > ~/forte/boot/forte.fboot && cd ~/forte && docker compose restart", stdin=boot)
        self.pi.wait_port(self.args.host, self.args.port)


class Refused(RuntimeError):
    """The module may not be changed now (running, occupied) or cannot be (types missing in FORTE)."""


def guard(client: Client, snap: Snapshot):
    """Changes only while the module is Stopped, Idle or Aborted and nobody occupies it."""
    read = lambda p: client.execute(Command(op="read", resource=snap.resource, source=p)).read_value(p)
    try:
        state, occupied = int(read(MODULE_STATE)), read(OCCUPIED) == "TRUE"
    except (ManagementError, ValueError):
        raise Refused("Cannot read the module state and occupation (not a generated module?); use --force")
    names = {v: k for k, v in STATES.items()}
    if state not in QUIET or occupied:
        raise Refused(f"Module is {names.get(state, state)}{' and occupied' if occupied else ''}; "
                      "stop and release it first, or use --force")


def lacking(client: Client, resource: str, types, known) -> list[str]:
    """The types FORTE does not have; generic comm FBs are made on demand (GEN_*), so not asked for."""
    missing = []
    for typ in sorted(set(types) - set(known)):
        if GENERIC.fullmatch(typ):
            continue
        try:
            if not client.execute(Command(op="query_type", resource=resource, type=typ)).types:
                missing.append(typ)
        except ManagementError:
            missing.append(typ)
    return missing


def online(app: FlatApplication, drift: Drift, resource: str = "RES", overrides=None) -> list[Command]:
    """The management commands that apply ``drift`` to the running program without a restart.

    Changed parameters are written. New instances are created, given their values, wired and
    started; then the INIT event where the INIT chain enters them from the running program is
    fired once (``$e``), which initialises them in order (OPC UA nodes, channels).
    """
    fresh = set(drift.missing)
    new = [n for n in app.fbs if n in fresh]              # in the order of the program
    values = {**app.parameters, **(overrides or {})}
    cmd = lambda op, **kw: Command(op=op, resource=resource, **kw)  # noqa: E731
    return [*[cmd("write", destination=p, value=e) for p, (e, _) in drift.values.items()],
            *[cmd("create_fb", name=n, type=app.fbs[n]) for n in new],
            *[cmd("write", destination=p, value=v) for p, v in values.items() if owner(p) in fresh],
            *[cmd("disconnect", source=s, destination=d) for s, d in drift.unexpected_connections],
            *[cmd("connect", source=s, destination=d) for s, d in drift.missing_connections],
            *[cmd("start", name=n) for n in new],
            *[cmd("write", destination=d, value="$e") for s, d in drift.missing_connections
              if init_link((s, d)) and owner(s) not in fresh and owner(d) in fresh]]


def summary(drift: Drift, commands: list[Command]) -> list[str]:
    """What the online change does: the values written, the instances created (by their top-level
    name), where they are initialised from, and the number of management commands."""
    lines = [f"write {p} := {e} (was {r})" for p, (e, r) in drift.values.items()]
    if created := list(dict.fromkeys(n.split(".")[0] for n in drift.missing)):
        count = lambda op: sum(c.op == op for c in commands)  # noqa: E731
        lines.append(f"create {', '.join(created)}: {count('create_fb')} instances, {count('connect')} connections"
                     + (f", {count('disconnect')} INIT links moved" if count("disconnect") else ""))
        lines += [f"initialise from {c.destination}" for c in commands if c.value == "$e"]
    return lines + [f"{len(commands)} management commands"]


def push(client: Client, host: str, port: int, cand: Candidate, deployer=None, overrides=None,
         force: bool = False, dry_run: bool = False, resource: str = "RES") -> list[str]:
    """Bring the module to ``cand``'s program, the least disruptive way; returns what was done (or
    would be, with ``dry_run``).

    - Changed skill parameters are written online (guarded: the module Stopped, Idle or Aborted
      and not occupied, unless ``force``).
    - New instances, e.g. a module level skill, are created online, also while the module runs:
      nothing that runs is touched.
    - Anything else is deployed as a new boot file with a FORTE restart (guarded).
    An online change is checked by reading the module back, then saved in the boot file.
    """
    status = inspect(client, host, port, [cand], resource, overrides)
    drift, snap = status.drift, status.snapshot
    if drift.empty:
        return ["in sync, nothing to do"]
    boot = boot_file(deployment(cand.app, resource, overrides=overrides))
    if missing := lacking(client, resource, cand.app.fbs.values(), snap.hashes):
        raise Refused(f"FORTE lacks the types {missing}: rebuild it (build-modules.ps1) and install it first")
    if drift.restart or snap.empty:
        done = [f"redeploy: {line}" for line in drift.lines()]
        if dry_run:
            return done
        if deployer is None:
            raise Refused("A structural change needs a restart with a new boot file; this target has no deployer "
                          "(an SSH user for a Pi)")
        if not snap.empty and not force:
            guard(client, snap)
        client.close()                       # FORTE restarts: the management connection goes away
        deployer.restart(boot)
        return done + ["boot file replaced, FORTE restarted"]
    commands = online(cand.app, drift, resource, overrides)
    done = summary(drift, commands)
    if dry_run:
        return done
    if drift.values and not force:
        guard(client, snap)
    for command in commands:
        client.execute(command)
    after = inspect(client, host, port, [cand], resource, overrides).drift
    if not after.empty:
        raise RuntimeError("The module differs after the online change: " + "; ".join(after.lines()[:10]))
    done.append("verified by read-back")
    if deployer is not None:
        deployer.save(boot)
        done.append("boot file saved")
    else:
        done.append("not saved in a boot file (no deployer): a FORTE restart loses the change")
    return done


# Watch -----------------------------------------------------------------------------------------

def watch(endpoints: dict[tuple[str, int], list[Candidate]], on_change, interval: float = 5.0,
          rounds: int | None = None, log=print):
    """Poll each FORTE; call ``on_change(status)`` when it comes online or its program changes
    (``rounds``: stop after that many polls; default: forever)."""
    last: dict[tuple[str, int], str] = {}
    done = 0
    while True:
        for (host, port), cands in endpoints.items():
            try:
                with Client(host, port, timeout=5) as client:
                    status = inspect(client, host, port, cands)
            except (OSError, ManagementError) as exc:
                if last.get((host, port)) != "offline":
                    log(f"{host}:{port}: offline ({exc.__class__.__name__})")
                last[(host, port)] = "offline"
                continue
            key = fingerprint(status)
            if last.get((host, port)) != key:
                last[(host, port)] = key
                on_change(status)
        done += 1
        if rounds is not None and done >= rounds:
            return
        time.sleep(interval)
