"""python -m modgen [cell/modules/filling.yaml ...]: regenerate ModLib and the modules' 4diac projects.

    python -m modgen --list    # project|folder|type manifest|package per line, ModLib first (for build-modules.ps1)
"""
import argparse
from pathlib import Path

from . import LIBRARY_PROJECT, generate, generate_library, load, manifest_path, project_dir, specs
from .library import LIB


def main():
    """Validate module specifications and regenerate the library and module projects."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("spec", nargs="*", help="Module specifications (default: all cell/modules/*.yaml)")
    parser.add_argument("--list", action="store_true", help="Only list the projects, generate nothing")
    args = parser.parse_args()
    paths = [Path(p) for p in args.spec] or specs()
    if args.list:
        rows = [(LIBRARY_PROJECT, LIB)] + [(s.project, s.package) for s in map(load, paths)]
        for project, package in rows:
            print(project, project_dir(project), manifest_path(project), package, sep="|")
        return
    library = generate_library()
    print(f"Generated {library.root} ({sum(e for *_, e in library.manifest)} exported types)")
    for path in paths:
        project = generate(load(path))
        print(f"Generated {project.root} ({sum(e for *_, e in project.manifest)} exported types)")
    print("Build all modules into one FORTE: runtime/build-modules.ps1 [-Config modules-win | pi/modules-pi]")


if __name__ == "__main__":
    main()
