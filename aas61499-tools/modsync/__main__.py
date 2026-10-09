"""python -m modsync: keep modules, their specs and their AAS in step.

    python -m modsync describe cell/modules/filling.yaml --target pi   # AAS from the spec alone (no module needed)
    python -m modsync pull --spec cell/modules/filling.yaml --target pi   # read the module, report drift, write its AAS
    python -m modsync pull --host 192.168.0.191                           # which module is this? (tries every spec)
    python -m modsync push cell/modules/filling.yaml --target pi --dry-run   # what would change on the module
    python -m modsync push cell/modules/filling.yaml --target pi           # bring the module to its spec
    python -m modsync watch                                                # pull whenever a module comes online or changes

The AAS as the desired state (no module spec is read; the AASs are a folder of AAS files or an AAS server):

    python -m modsync verify aas --host 192.168.0.134                      # is the module what its AAS describes?
    python -m modsync reconfigure http://localhost:8081 --shell FillingModuleAAS --dry-run   # what would change
    python -m modsync reconfigure aas --host 192.168.0.134                 # bring the module to its AAS, record it

Run on the module's own computer with --host localhost: push then writes the boot file in ~/forte
and restarts the FORTE container there (elsewhere it does so over SSH).
The AASs of the module and of its components go to aas/<idShort>.json, built by modreg (which needs
the registration extra). --register http://<host>:8090 sends their profiles to the registration
service (modreg serve), which checks each AAS against the ontology and publishes it.
"""
import argparse
import json
from pathlib import Path
import sys
import time

from iec61499_mgmt.protocol import Client, Command, ManagementError
from modgen import SPECS, load, specs

from . import desired
from .compare import Candidate
from .sync import LocalDeployer, PiDeployer, Refused, Status, candidates, inspect, is_local, push, relative, watch

OUT = Path("aas")


def publish(status: Status | None, args, spec=None, target=None, path=None):
    """Write the AASs of the module and of its components as modreg builds them, and with
    --register send their profiles to the registration service; from a status, the values are the
    running ones."""
    try:
        from modreg import model, profile as profiles          # needs the registration extra (aas-model)
    except ImportError as e:
        print(f"  no AAS written: modreg needs the registration extra ({e})")
        return
    if status is not None:
        c, snap = status.candidate, status.snapshot
        found = profiles.describe_all(c.spec, c.target, snap, status.drift, relative(c.path), f"opc.tcp://{snap.host}:4840")
    else:
        found = profiles.describe_all(spec, target, spec_path=relative(path))
    for profile in found:
        out = Path(args.out) / f"{profile['id_short']}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(model.build(profile), indent=1), encoding="utf-8")
        print(f"  AAS: {out}")
    if args.register:
        register(found, args)


def register(found: list[dict], args):
    """Send the profiles of the module and of its components to the registration service; a refusal
    is reported, not raised."""
    from modreg.service import send
    for profile in found:
        try:
            code, answer = send(args.register, profile)
        except OSError as e:
            print(f"  registration: {args.register} not reached ({e})")
            return
        if code >= 400:
            print(f"  registration of {profile['id_short']} refused at {answer.get('step')} (HTTP {code})")
            for line in answer.get("reasons", [])[:20]:
                print(f"    {line}")
        else:
            print(f"  registration: {'unchanged' if answer['unchanged'] else 'registered'} {answer['id_short']} at {args.register}")


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


def against_the_aas(args) -> int:
    """verify and reconfigure: the module against the AASs in ``args.aas``."""
    try:
        module, components = desired.load(args.aas, args.shell)
    except (desired.NotDescribed, OSError) as exc:
        sys.exit(f"{args.aas}: {exc}")
    stated_host, stated_port = desired.endpoint(module)
    host, port = args.host or stated_host, args.port or stated_port or 61499
    if host is None:
        sys.exit("Give --host: the AAS states no management endpoint")
    name = module["assetAdministrationShells"][0]["idShort"]
    with Client(host, port, timeout=5) as client:
        try:
            client.execute(Command(op="query_fbs", resource=""))          # is anybody there?
        except OSError as exc:
            sys.exit(f"{name}: its module at {host}:{port} is not reached ({exc})")
        except ManagementError:
            pass
        try:
            if args.command == "verify":
                reading, done = desired.read(client, host, port, module, components), None
            else:
                deployer = LocalDeployer(port=port) if is_local(host) else PiDeployer(host, args.user, port) if args.user else None
                done, reading = desired.reconfigure(client, host, port, module, components, deployer,
                                                    force=args.force, dry_run=args.dry_run)
        except (desired.NotDescribed, Refused) as exc:
            sys.exit(f"{name} at {host}:{port}: {exc}")
    found = reading.differences
    print(f"{host}:{port}: {reading.spec.module} ({len(reading.snapshot.fbs)} instances), "
          + ("as its AAS describes it" if found.empty else f"{len(found.lines())} differences from its AAS") + f" ({name})")
    for line in [*found.lines()[:40], *(done or [])]:
        print(f"  {line}")
    if found.empty and (args.command == "verify" and args.record or done and len(done) > 1 and not args.dry_run):
        print(f"  recorded in {desired.store(args.aas, desired.record(module, reading, done, getattr(args, 'trigger', '')), module)}")
    return 0 if found.empty or args.command == "reconfigure" and args.dry_run else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("verify", "reconfigure"):
        p = sub.add_parser(name)
        p.add_argument("aas", help="The AASs of the module and its components: a folder of AAS files, or an AAS server (http://<host>:8081)")
        p.add_argument("--shell", help="The module's AAS (idShort), when there are several")
        p.add_argument("--host", help="FORTE host (default: the management endpoint the AAS states)")
        p.add_argument("--port", type=int, help="FORTE management port (default: the AAS's, else 61499)")
        if name == "verify":
            p.add_argument("--record", action="store_true", help="Write the block types and hashes found into the Control Configuration")
        else:
            p.add_argument("--user", help="SSH login of the module's computer, to add the change to its boot file")
            p.add_argument("--dry-run", action="store_true", help="Only show what would change")
            p.add_argument("--force", action="store_true", help="Write values even while the module runs or is occupied")
            p.add_argument("--trigger", default="", help="Why: goes into the change log")
    for name in ("describe", "pull", "push", "watch"):
        p = sub.add_parser(name)
        p.add_argument("--out", default=str(OUT), help="Folder for the AAS JSON files")
        p.add_argument("--register", metavar="URL", help="Also send the module's profile to this registration service (modreg serve)")
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

    if args.command in ("verify", "reconfigure"):
        sys.exit(against_the_aas(args))
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
