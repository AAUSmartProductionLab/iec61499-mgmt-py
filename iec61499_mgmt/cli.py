"""Offline deployment plans, type libraries and boot files; only ``types`` contacts a FORTE."""
import argparse
import json
from pathlib import Path

from .models import Network, NetworkPatch, TypeLibrary
from .planner import Plan, plan


def read(model, path):
    """Load a pydantic model from a JSON file."""
    return model.model_validate_json(Path(path).read_text(encoding="utf-8"))


def write_types(args):
    """Query the runtime for type hashes and write the resulting library."""
    import hashlib
    from .protocol import Client
    from .sysfile import load_application
    from .typelib import build_library, query_hashes, read_types
    types = read_types(args.types_dir)
    digest = None
    if args.runtime_exe:
        with open(args.runtime_exe, "rb") as binary:
            digest = hashlib.file_digest(binary, "sha256").hexdigest()
    with Client(args.host, args.port) as client:
        hashes = query_hashes(client, args.resource, [n for n in types if n.startswith(args.prefix)])
    fixed = load_application(args.system, args.application) if args.system else None
    library = build_library(types, hashes, build_id=args.runtime_exe or f"{args.host}:{args.port}",
                            runtime_binary_sha256=digest, fixed=fixed)
    Path(args.out).write_text(library.model_dump_json(indent=2) + "\n", encoding="utf-8")


def main():
    """Parse arguments and run the plan, types, boot or schema command."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan_parser = commands.add_parser("plan", help="Ordered management commands from a current to a desired network")
    plan_parser.add_argument("--current", required=True)
    inputs = plan_parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--desired")
    inputs.add_argument("--patch")
    plan_parser.add_argument("--library", required=True, help="types.json")
    plan_parser.add_argument("--out", required=True)
    types_parser = commands.add_parser("types", help="Query a running FORTE and write types.json")
    types_parser.add_argument("--types-dir", required=True, help="4diac 'Type Library' folder")
    types_parser.add_argument("--prefix", default="", help="Only types whose name starts with this")
    types_parser.add_argument("--system", help=".sys file whose fixed application gives the boundary ports")
    types_parser.add_argument("--application", help="Application in --system (required with it)")
    types_parser.add_argument("--host", default="127.0.0.1")
    types_parser.add_argument("--port", type=int, default=61499)
    types_parser.add_argument("--resource", default="RES")
    types_parser.add_argument("--runtime-exe", help="Pin the library to this executable's SHA-256")
    types_parser.add_argument("--out", required=True)
    boot_parser = commands.add_parser("boot", help="Write a FORTE boot file for a .sys application")
    boot_parser.add_argument("--system", required=True)
    boot_parser.add_argument("--application", required=True)
    boot_parser.add_argument("--resource", default="RES")
    boot_parser.add_argument("--procedure", help="Network JSON of a change added in the owned scope")
    boot_parser.add_argument("--library", help="types.json, required with --procedure")
    boot_parser.add_argument("--out", required=True)
    schema_parser = commands.add_parser("schema")
    schema_parser.add_argument("model", choices=["network", "patch", "plan", "library"])
    schema_parser.add_argument("--out", required=True)
    args = parser.parse_args()

    try:
        if args.command == "plan":
            current = read(Network, args.current)
            desired = read(Network, args.desired) if args.desired else read(NetworkPatch, args.patch).apply(current)
            result = plan(current, desired, read(TypeLibrary, args.library))
        elif args.command == "types":
            if args.system and not args.application:
                parser.error("--application is required with --system")
            write_types(args)
            return
        elif args.command == "boot":
            from .bootfile import boot_file, deployment
            from .sysfile import load_application
            procedure = read(Network, args.procedure) if args.procedure else None
            library = read(TypeLibrary, args.library) if args.library else None
            commands = deployment(load_application(args.system, args.application), args.resource,
                                  procedure=procedure, library=library)
            # LF only: FORTE ends a boot-file command at "/>\n" or "</Request>\n", so CRLF from a
            # Windows text write merges all lines on Linux (Windows FORTE reads in text mode).
            Path(args.out).write_text(boot_file(commands), encoding="utf-8", newline="\n")
            return
        else:
            model = {"network": Network, "patch": NetworkPatch, "plan": Plan, "library": TypeLibrary}[args.model]
            Path(args.out).write_text(json.dumps(model.model_json_schema(), indent=2) + "\n", encoding="utf-8")
            return
        Path(args.out).write_text(result.model_dump_json(indent=2, exclude_none=True) + "\n", encoding="utf-8")
    except (ValueError, OSError) as exc:
        parser.exit(2, f"{exc}\n")


if __name__ == "__main__":
    main()
