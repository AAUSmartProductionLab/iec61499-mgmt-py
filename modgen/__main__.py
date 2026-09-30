"""python -m modgen [modules/filling.yaml ...]: regenerate ModLib and the modules' 4diac projects."""
import argparse
from pathlib import Path

from . import generate, generate_library, load, specs


def main():
    """Validate module specifications and regenerate the library and module projects."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", nargs="*", help="Module specifications (default: all modules/*.yaml)")
    args = parser.parse_args()
    library = generate_library()
    print(f"Generated {library.root} ({sum(e for *_, e in library.manifest)} exported types)")
    for path in args.spec or specs():
        spec = load(Path(path))
        project = generate(spec)
        print(f"Generated {project.root} ({sum(e for *_, e in project.manifest)} exported types)")
    print("Build all modules into one FORTE: 4diac/tools/build-modules.ps1 [-Config modules-win | pi/modules-pi]")


if __name__ == "__main__":
    main()
