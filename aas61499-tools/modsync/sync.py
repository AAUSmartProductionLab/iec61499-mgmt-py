"""Keep a module, its module spec and its AAS in step, both ways.

- pull: read what runs on the module, find the module spec and target it was generated from, report
  the drift, and describe the module (AAS) with the values that really run.
- push: bring the module to its spec. Changed skill parameters are written online (a skill takes
  them over at its next start) and saved in the boot file; any other change (instances, types,
  connections, or values only read at INIT such as OPC UA paths and IO ids) is deployed as a new
  boot file and a FORTE restart, because FORTE 3.3 crashed deleting a resource with IO handles
  (see pi.py). Both only while the module is
  Stopped, Idle or Aborted and not occupied, unless forced.
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
from modgen import load
from modgen.library import STATES

from .compare import Candidate, Drift, closest, compare, expected_values, parameters
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


def push(client: Client, host: str, port: int, cand: Candidate, deployer=None, overrides=None,
         force: bool = False, dry_run: bool = False, resource: str = "RES") -> list[str]:
    """Bring the module to ``cand``'s program; returns what was done (or would be, with ``dry_run``)."""
    status = inspect(client, host, port, [cand], resource, overrides)
    drift, snap = status.drift, status.snapshot
    if drift.empty:
        return ["in sync, nothing to do"]
    boot = boot_file(deployment(cand.app, resource, overrides=overrides))
    if drift.restart or snap.empty:
        missing = []
        for typ in sorted(set(cand.app.fbs.values()) - set(snap.hashes)):
            try:
                if not client.execute(Command(op="query_type", resource=resource, type=typ)).types:
                    missing.append(typ)
            except ManagementError:
                missing.append(typ)
        if missing:
            raise Refused(f"FORTE lacks the types {missing}: rebuild it (build-modules.ps1) and install it first")
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
    done = [f"write {p} := {e} (was {r})" for p, (e, r) in drift.values.items()]
    if dry_run:
        return done
    if not force:
        guard(client, snap)
    for p, (e, _) in drift.values.items():
        client.execute(Command(op="write", resource=resource, destination=p, value=e))
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
