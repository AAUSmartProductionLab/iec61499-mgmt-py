"""Offline compilation and reviewable deployment plans; never contacts a PLC."""
import argparse
import json
from pathlib import Path

from .models import IECValue, Network, NetworkPatch, TypeLibrary
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
    """Parse arguments and run the compile, plan or schema command."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    compile_parser = commands.add_parser("compile")
    compile_parser.add_argument("bpmn")
    compile_parser.add_argument("--bindings", required=True)
    compile_parser.add_argument("--target", required=True)
    compile_parser.add_argument("--library", help="types.json; --target is then a hash-free template")
    compile_parser.add_argument("--product")
    compile_parser.add_argument("--out", required=True, help="Compilation bundle JSON")
    compile_parser.add_argument("--network-out", help="Standalone network JSON for plan")
    plan_parser = commands.add_parser("plan")
    plan_parser.add_argument("--current", required=True)
    inputs = plan_parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--desired")
    inputs.add_argument("--patch")
    target_inputs = plan_parser.add_mutually_exclusive_group(required=True)
    target_inputs.add_argument("--library")
    target_inputs.add_argument("--target", help="Use the library embedded in a compiler target profile")
    plan_parser.add_argument("--out", required=True)
    types_parser = commands.add_parser("types", help="Query a running FORTE and write types.json")
    types_parser.add_argument("--types-dir", required=True, help="4diac 'Type Library' folder")
    types_parser.add_argument("--prefix", default="", help="Only types whose name starts with this")
    types_parser.add_argument("--system", help=".sys file whose fixed application gives the boundary ports")
    types_parser.add_argument("--application", default="FillingCell")
    types_parser.add_argument("--host", default="127.0.0.1")
    types_parser.add_argument("--port", type=int, default=61499)
    types_parser.add_argument("--resource", default="RES")
    types_parser.add_argument("--runtime-exe", help="Pin the library to this executable's SHA-256")
    types_parser.add_argument("--out", required=True)
    boot_parser = commands.add_parser("boot", help="Write a FORTE boot file for a .sys application")
    boot_parser.add_argument("--system", required=True)
    boot_parser.add_argument("--application", default="FillingCell")
    boot_parser.add_argument("--resource", default="RES")
    boot_parser.add_argument("--procedure", help="Network JSON of the active procedure")
    boot_parser.add_argument("--library", help="types.json, required with --procedure")
    boot_parser.add_argument("--out", required=True)
    schema_parser = commands.add_parser("schema")
    schema_parser.add_argument("model", choices=["network", "patch", "plan", "bindings", "target"])
    schema_parser.add_argument("--out", required=True)
    args = parser.parse_args()
    from skill_compiler.models import RecipeBindings, TargetProfile

    try:
        if args.command == "compile":
            from skill_compiler import compile_bpmn
            product = {} if not args.product else {
                k: IECValue.model_validate(v) for k, v in json.loads(Path(args.product).read_text(encoding="utf-8")).items()
            }
            if args.library:
                from skill_compiler.targets import bind_library
                target = bind_library(json.loads(Path(args.target).read_text(encoding="utf-8")),
                                      read(TypeLibrary, args.library))
            else:
                target = read(TargetProfile, args.target)
            result = compile_bpmn(Path(args.bpmn).read_text(encoding="utf-8"),
                                  read(RecipeBindings, args.bindings), target, product)
            if args.network_out:
                Path(args.network_out).write_text(result.network.model_dump_json(indent=2) + "\n", encoding="utf-8")
        elif args.command == "plan":
            current = read(Network, args.current)
            desired = read(Network, args.desired) if args.desired else read(NetworkPatch, args.patch).apply(current)
            library = read(TypeLibrary, args.library) if args.library else read(TargetProfile, args.target).library
            result = plan(current, desired, library)
        elif args.command == "types":
            write_types(args)
            return
        elif args.command == "boot":
            from .bootfile import boot_file, deployment
            from .sysfile import load_application
            procedure = read(Network, args.procedure) if args.procedure else None
            library = read(TypeLibrary, args.library) if args.library else None
            commands = deployment(load_application(args.system, args.application), args.resource,
                                  procedure=procedure, library=library)
            Path(args.out).write_text(boot_file(commands), encoding="utf-8")
            return
        else:
            model = {"network": Network, "patch": NetworkPatch, "plan": Plan,
                     "bindings": RecipeBindings, "target": TargetProfile}[args.model]
            Path(args.out).write_text(json.dumps(model.model_json_schema(), indent=2) + "\n", encoding="utf-8")
            return
        Path(args.out).write_text(result.model_dump_json(indent=2, exclude_none=True) + "\n", encoding="utf-8")
    except (ValueError, OSError) as exc:
        parser.exit(2, f"{exc}\n")


if __name__ == "__main__":
    main()
