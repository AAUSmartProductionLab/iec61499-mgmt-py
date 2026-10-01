"""python -m modsync: keep modules, their specs and their AAS in step.

    python -m modsync describe cell/modules/filling.yaml --target pi   # AAS from the spec alone (no module needed)
    python -m modsync pull --spec cell/modules/filling.yaml --target pi   # read the module, report drift, write its AAS
    python -m modsync pull --host 192.168.0.191                           # which module is this? (tries every spec)
    python -m modsync push cell/modules/filling.yaml --target pi --dry-run   # what would change on the module
    python -m modsync push cell/modules/filling.yaml --target pi           # bring the module to its spec
    python -m modsync watch                                                # pull whenever a module comes online or changes

Run on the module's own computer with --host localhost: push then writes the boot file in ~/forte
and restarts the FORTE container there (elsewhere it does so over SSH).
The AAS goes to aas/<idShort>.json; --basyx http://<host>:8081 also uploads it to an AAS server.
"""
import argparse
from pathlib import Path
import sys
import time

from iec61499_mgmt.protocol import Client
from modgen import SPECS, load, specs

from . import aas
from .compare import Candidate
from .sync import LocalDeployer, PiDeployer, Refused, Status, candidates, inspect, is_local, push, relative, watch

OUT = Path("aas")


def publish(status: Status | None, args, spec=None, target=None, path=None):
    """Write the AAS (and upload it with --basyx); from a status, the values are the running ones."""
    if status is not None:
        c, snap = status.candidate, status.snapshot
        store = aas.build(c.spec, c.target, snap, status.drift, relative(c.path), f"opc.tcp://{snap.host}:4840")
        spec = c.spec
    else:
        store = aas.build(spec, target, spec_path=relative(path))
    out = aas.write(store, Path(args.out) / f"{aas.identity(spec)[0]}.json")
    print(f"  AAS: {out}")
    if args.basyx:
        for line in aas.upload(store, args.basyx):
            print(f"  {line}")


def report(status: Status):
    print(status.summary())
    if not status.identified:
        return
    for line in status.drift.lines()[:40]:
        print(f"  {line}")
    if status.drift.size() > 40:
        print(f"  ... {status.drift.size() - 40} more")


def endpoint(args, cand: Candidate | None) -> tuple[str, int]:
    t = cand.spec.targets[cand.target] if cand else None
    host = args.host or (t.host if t else None)
    if host is None:
        sys.exit("Give --host, or --spec with --target")
    return host, args.port or (t.port if t else 61499)


def spec_path(arg: str) -> Path:
    """A module spec given as a file, or by its name among the cell's specs (``filling``)."""
    path = Path(arg)
    return path if path.exists() or path.suffix else SPECS / f"{arg}.yaml"


def chosen(args) -> Candidate | None:
    if not args.spec:
        return None
    path = spec_path(args.spec)
    spec = load(path)
    return Candidate(path, spec, args.target or next(iter(spec.targets)))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("describe", "pull", "push", "watch"):
        p = sub.add_parser(name)
        p.add_argument("--out", default=str(OUT), help="Folder for the AAS JSON files")
        p.add_argument("--basyx", help="Also upload the AAS to this AAS server, e.g. http://192.168.0.104:8081")
        if name in ("describe", "push"):
            p.add_argument("spec", help="Module spec: a file, or a module's name (filling)")
        elif name == "pull":
            p.add_argument("--spec", help="Module spec (default: find it among modules/*.yaml)")
        else:
            p.add_argument("spec", nargs="*", help="Module specs (default: modules/*.yaml)")
        p.add_argument("--target", help="Target in the module spec (default: its first)")
        if name in ("pull", "push"):
            p.add_argument("--host", help="FORTE host (default: the target's)")
            p.add_argument("--port", type=int, help="FORTE management port (default: the target's)")
        if name == "push":
            p.add_argument("--user", help="SSH login for a restart (default: the target's user)")
            p.add_argument("--dry-run", action="store_true", help="Only show what would change")
            p.add_argument("--force", action="store_true", help="Change even a running or occupied module")
        if name == "watch":
            p.add_argument("--interval", type=float, default=5.0, help="Seconds between polls")
    args = parser.parse_args()

    if args.command == "describe":
        spec = load(spec_path(args.spec))
        target = args.target or next(iter(spec.targets))
        print(f"{spec.module} target {target}, from the spec only")
        publish(None, args, spec, target, spec_path(args.spec))
    elif args.command == "pull":
        cand = chosen(args)
        cands = [c for c in candidates([cand.path]) if not args.target or c.target == args.target] if cand \
            else candidates(specs())
        host, port = endpoint(args, cand)
        with Client(host, port, timeout=5) as client:
            status = inspect(client, host, port, cands)
        report(status)
        if not status.identified:
            sys.exit(1)
        publish(status, args)
    elif args.command == "push":
        cand = chosen(args)
        host, port = endpoint(args, cand)
        t = cand.spec.targets[cand.target]
        user = args.user or t.user
        # On the module's own computer the boot file is local; from elsewhere it goes over SSH.
        deployer = LocalDeployer(port=port) if is_local(host) else PiDeployer(host, user, port) if user else None
        with Client(host, port, timeout=5) as client:
            try:
                done = push(client, host, port, cand, deployer, force=args.force, dry_run=args.dry_run)
            except Refused as exc:
                sys.exit(f"Refused: {exc}")
        for line in done:
            print(f"  {line}")
        if not args.dry_run:
            time.sleep(1.0)                  # after a restart, FORTE is still loading its boot file
            with Client(host, port, timeout=10) as client:
                status = inspect(client, host, port, [cand])
            report(status)
            publish(status, args)
    else:
        paths = [spec_path(s) for s in args.spec] or specs()
        endpoints: dict[tuple[str, int], list[Candidate]] = {}
        for c in candidates(paths):
            if args.target and c.target != args.target:
                continue
            t = c.spec.targets[c.target]
            endpoints.setdefault((t.host, t.port), []).append(c)
        print("Watching " + ", ".join(f"{h}:{p}" for h, p in endpoints) + " (Ctrl+C to stop)")

        def changed(status: Status):
            report(status)
            if status.identified:
                publish(status, args)
        try:
            watch(endpoints, changed, args.interval)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
