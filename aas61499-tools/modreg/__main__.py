"""python -m modreg: profiles of the modules and the service that registers them.

    modreg profile filling --target pi                    # the profiles of the module and its components -> profiles/
    modreg profile filling --target pi --host 192.168.0.203   # ... with what runs on the module
    modreg build profiles/FillingModuleAAS.json           # the AAS a profile describes -> aas/
    modreg check profiles/FillingModuleAAS.json --ontology ontology/ARSO   # does the AAS follow the ontology?
    modreg serve --ontology ontology/ARSO --basyx http://<host>:8081       # the registration service
    modreg register filling --target pi --service http://<host>:8090       # send the module's profile to it
    modreg generate --ontology ontology/ARSO              # templates of the ontology's own submodels, and all classes
    modreg graph filling --target pi --out filling.ttl    # the module's AASs as RDF, with what they describe (PPRL)

A profile is an AAS on the lab's shared model (aas-model) without what its type says anyway; the
service validates it, builds the AAS, checks it against the ontology and publishes it. A module
spec gives several: the module's own and one for every component of it that has skills.
A product with its plan is a profile of its own type and goes the same way:

    modreg build cell/examples/Vial2mLAAS.json            # the AAS of a product

The planar table (planar-controller) is the source ``planar``: the table and its shuttles as the
controller at --host shows them (or as --layout, --holes and --shuttles say), registered again
whenever that changes with --every:

    modreg profile planar --host <controller>             # PlanarTableAAS, PlanarShuttle<N>AAS, ...
    modreg register planar --host <controller> --service http://<host>:8090 --every 10
"""
import argparse
import json
from pathlib import Path
import sys
import time

from iec61499_mgmt.protocol import Client
from modgen import load
from modsync.__main__ import spec_path
from modsync.compare import Candidate
from modsync.sync import inspect, relative

try:
    from . import model, planar, profile as profiles, templates
    from .ontology import Blueprint, check
    from .projection import project
    from .service import AasServer, Registry, mapped_last, send, serve
except ImportError as e:
    sys.exit(f"modreg needs the registration extra ({e}): python -m pip install -e \".[registration]\"")


def module_profiles(args) -> list[dict]:
    """The profiles of a module spec's target (the module's, then its components'); with --host, of
    what runs there."""
    path = spec_path(args.source)
    spec = load(path)
    target = args.target or next(iter(spec.targets))
    if not args.host:
        return profiles.describe_all(spec, target, spec_path=relative(path))
    port = args.port or spec.targets[target].port
    with Client(args.host, port) as client:
        status = inspect(client, args.host, port, [Candidate(path, spec, target)])
    if not status.identified:
        sys.exit(f"{args.host}:{port} does not run {spec.module}: {status.summary()}")
    return profiles.describe_all(spec, target, status.snapshot, status.drift, relative(path), f"opc.tcp://{args.host}:4840")


def planar_profiles(args) -> list[dict]:
    """The profiles of the planar table and its shuttles: as the controller at --host shows them, or
    as --layout, --holes and --shuttles say."""
    if args.host:
        table = planar.read(f"opc.tcp://{args.host}:{args.port or 4840}/")
    elif args.layout:
        columns, rows = (int(v) for v in args.layout.lower().split("x"))
        table = planar.Table(columns, rows, tuple(int(s) for s in args.shuttles.split(",") if s),
                             planar.holes(args.holes.replace(";", " ")))
    else:
        sys.exit("modreg: the planar table needs --host (its controller) or --layout")
    return planar.describe_all(table)


def given(args) -> list[dict]:
    """The profile in a JSON file, those of a module spec, or those of the planar table."""
    if args.source.endswith(".json"):
        return [json.loads(Path(args.source).read_text(encoding="utf-8"))]
    if args.source == "planar":
        return planar_profiles(args)
    return module_profiles(args)


def write(folder: str, name: str, content: dict) -> Path:
    out = Path(folder) / f"{name}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(content, indent=1), encoding="utf-8")
    return out


def report(env: dict, folder: str) -> bool:
    result = check(env, Blueprint(folder))
    print(result.summary())
    for line in result.lines():
        print(f"  {line}")
    return result.ok


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="modreg", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    def source(p, what):
        p.add_argument("source", help=what + "; planar: the planar table")
        p.add_argument("--target", help="target of the module spec (default: its first)")
        p.add_argument("--host", help="read the module at this address: values, type hashes and sync state are the running ones "
                                      "(planar: the controller, its shuttles and layout)")
        p.add_argument("--port", type=int, help="FORTE management port (default: the target's; planar: the OPC UA port, 4840)")
        p.add_argument("--layout", help="planar without --host: columns x rows of flyways, e.g. 4x3")
        p.add_argument("--holes", default="", help="planar without --host: flyways that are not there, e.g. \"2,1 0,2\"")
        p.add_argument("--shuttles", default="1", help="planar without --host: the xbots offered, e.g. 1,2,3")

    p = sub.add_parser("profile", help="write a module's profile")
    source(p, "module spec (file or name)")
    p.add_argument("--out", default="profiles")
    p = sub.add_parser("build", help="write the AAS a profile describes")
    source(p, "profile (.json) or module spec")
    p.add_argument("--out", default="aas")
    p = sub.add_parser("check", help="check a profile's AAS against the ontology")
    source(p, "profile (.json) or module spec")
    p.add_argument("--ontology", required=True, help="folder with the ontology's Turtle files")
    p = sub.add_parser("serve", help="run the registration service")
    p.add_argument("--bind", default="0.0.0.0")
    p.add_argument("--listen", type=int, default=8090, metavar="PORT")
    p.add_argument("--store", default="registry", help="folder the service keeps profiles and AAS in")
    p.add_argument("--ontology", help="folder with the ontology's Turtle files; without it nothing is checked")
    p.add_argument("--strict", action="store_true", help="also refuse what the ontology does not describe")
    p.add_argument("--basyx", help="AAS server to publish to, e.g. http://<host>:8081")
    p = sub.add_parser("generate", help="write the templates of the ontology's own submodels into aas-model, and have it make their classes")
    p.add_argument("--ontology", required=True, help="folder with the ontology's Turtle files")
    p.add_argument("--aas-model", default=str(templates.AAS_MODEL), help="aas-model checkout (its generator makes the classes)")
    p = sub.add_parser("register", help="send a profile to the registration service")
    source(p, "profile (.json) or module spec")
    p.add_argument("--service", required=True, help="the registration service, e.g. http://<host>:8090")
    p.add_argument("--check", action="store_true", help="only validate and check, do not register")
    p.add_argument("--every", type=float, metavar="SECONDS",
                   help="keep reading the source and register again whenever it changed (the planar table's layout and shuttles)")
    p = sub.add_parser("graph", help="write the AASs of a module as RDF with the individuals and relations they describe")
    source(p, "profile (.json) or module spec")
    p.add_argument("--out", default="graph.ttl", help="Turtle file to write")
    args = parser.parse_args(argv)

    if args.command == "generate":
        aas_model = Path(args.aas_model)
        written = templates.write_templates(args.ontology, aas_model / "templates" / "arso")
        for path in [*written, *templates.regenerate(aas_model)]:
            print(path.relative_to(Path.cwd()) if path.is_relative_to(Path.cwd()) else path)
        return 0
    if args.command == "serve":
        registry = Registry(args.store, Blueprint(args.ontology) if args.ontology else None,
                            AasServer(args.basyx) if args.basyx else None, args.strict)
        server = serve(registry, args.bind, args.listen)
        print(f"registration service on {args.bind}:{args.listen}; store {args.store}; "
              f"ontology {args.ontology or 'none (no check)'}; AAS server {args.basyx or 'none'}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        return 0
    if args.command == "graph":
        graph = project([model.build(profile) for profile in given(args)])
        graph.serialize(args.out, format="turtle")
        print(f"{len(graph)} triples: {args.out}")
        return 0
    if args.command == "register" and args.every:
        registered = None
        while True:
            try:
                found = given(args)
            except (OSError, TimeoutError, planar.NotShown) as e:     # the controller is away, or not connected yet
                print(f"not read: {e or type(e).__name__}", flush=True)
            else:
                if found != registered:
                    registered = found if not act(args, found) else None
            time.sleep(args.every)
    try:
        found = given(args)
    except planar.NotShown as e:
        sys.exit(f"modreg: {e}")
    return act(args, found)


def act(args, found: list[dict]) -> int:
    """Write, build, check or register each profile; 1 if one failed."""
    try:
        failed = False
        for profile in mapped_last(found) if args.command == "register" else found:
            if args.command == "profile":
                print(f"profile: {write(args.out, profile['id_short'], profile)}")
            elif args.command == "build":
                print(f"AAS: {write(args.out, profile['id_short'], model.build(profile))}")
            elif args.command == "check":
                print(profile["id_short"])
                failed |= not report(model.build(profile), args.ontology)
            else:
                status, answer = send(args.service, profile, args.check)
                if status >= 400:
                    print(f"{profile['id_short']}: refused at {answer.get('step')} (HTTP {status})")
                    for line in answer.get("reasons", [])[:60]:
                        print(f"  {line}")
                    failed = True
                    continue
                what = "checked" if args.check else "unchanged" if answer["unchanged"] else "registered"
                print(f"{what}: {answer['id_short']} ({answer['id']}), {len(answer['submodels'])} submodels")
                for line in [answer["summary"], *([] if answer["unchanged"] else answer["published"])]:
                    if line:
                        print(f"  {line}")
    except model.ProfileError as e:
        print(f"not a valid profile: {e}", file=sys.stderr)
        return 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
