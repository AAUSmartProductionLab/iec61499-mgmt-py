"""python -m modreg: profiles of the modules and the service that registers them.

    modreg profile filling --target pi                    # the module's profile from its spec -> profiles/
    modreg profile filling --target pi --host 192.168.0.191   # ... with what runs on the module
    modreg build profiles/FillingModuleAAS.json           # the AAS a profile describes -> aas/
    modreg check profiles/FillingModuleAAS.json --ontology ontology/ARSO   # does the AAS follow the ontology?
    modreg serve --ontology ontology/ARSO --basyx http://<host>:8081       # the registration service
    modreg register filling --target pi --service http://<host>:8090       # send the module's profile to it
    modreg generate --ontology ontology/ARSO              # templates of the ontology's own submodels, and all classes

A profile is the module's AAS on the lab's shared model (aas-model) without what its type says
anyway; the service validates it, builds the AAS, checks it against the ontology and publishes it.
A product with its plan is a profile of its own type and goes the same way:

    modreg build cell/examples/Vial2mLAAS.json            # the AAS of a product
"""
import argparse
import json
from pathlib import Path
import sys

from iec61499_mgmt.protocol import Client
from modgen import load
from modsync.__main__ import spec_path
from modsync.compare import Candidate
from modsync.sync import inspect, relative

try:
    from . import model, profile as profiles, templates
    from .ontology import Blueprint, check
    from .service import AasServer, Registry, send, serve
except ImportError as e:
    sys.exit(f"modreg needs the registration extra ({e}): python -m pip install -e \".[registration]\"")


def module_profile(args) -> dict:
    """The profile of a module spec's target; with --host, of what runs there."""
    path = spec_path(args.source)
    spec = load(path)
    target = args.target or next(iter(spec.targets))
    if not args.host:
        return profiles.describe(spec, target, spec_path=relative(path))
    port = args.port or spec.targets[target].port
    with Client(args.host, port) as client:
        status = inspect(client, args.host, port, [Candidate(path, spec, target)])
    if not status.identified:
        sys.exit(f"{args.host}:{port} does not run {spec.module}: {status.summary()}")
    return profiles.describe(spec, target, status.snapshot, status.drift, relative(path), f"opc.tcp://{args.host}:4840")


def given(args) -> dict:
    """A profile from a JSON file, or of a module spec."""
    if args.source.endswith(".json"):
        return json.loads(Path(args.source).read_text(encoding="utf-8"))
    return module_profile(args)


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
        p.add_argument("source", help=what)
        p.add_argument("--target", help="target of the module spec (default: its first)")
        p.add_argument("--host", help="read the module at this address: values, type hashes and sync state are the running ones")
        p.add_argument("--port", type=int, help="FORTE management port (default: the target's)")

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
    p = sub.add_parser("generate", help="write the submodel templates of the ontology's own submodels and their classes")
    p.add_argument("--ontology", required=True, help="folder with the ontology's Turtle files")
    p.add_argument("--aas-model", default=str(templates.AAS_MODEL), help="aas-model checkout (its generator makes the classes)")
    p = sub.add_parser("register", help="send a profile to the registration service")
    source(p, "profile (.json) or module spec")
    p.add_argument("--service", required=True, help="the registration service, e.g. http://<host>:8090")
    p.add_argument("--check", action="store_true", help="only validate and check, do not register")
    args = parser.parse_args(argv)

    if args.command == "generate":
        written = templates.write_templates(args.ontology)
        for path in [*written, *templates.generate([*written, *templates.given()], aas_model=Path(args.aas_model))]:
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
    try:
        profile = given(args)
        if args.command == "profile":
            print(f"profile: {write(args.out, profile['id_short'], profile)}")
        elif args.command == "build":
            print(f"AAS: {write(args.out, profile['id_short'], model.build(profile))}")
        elif args.command == "check":
            return 0 if report(model.build(profile), args.ontology) else 1
        else:
            status, answer = send(args.service, profile, args.check)
            if status >= 400:
                print(f"refused at {answer.get('step')} (HTTP {status})")
                for line in answer.get("reasons", [])[:60]:
                    print(f"  {line}")
                return 1
            what = "checked" if args.check else "unchanged" if answer["unchanged"] else "registered"
            print(f"{what}: {answer['id_short']} ({answer['id']}), {len(answer['submodels'])} submodels")
            for line in [answer["summary"], *([] if answer["unchanged"] else answer["published"])]:
                if line:
                    print(f"  {line}")
    except model.ProfileError as e:
        print(f"not a valid profile: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
