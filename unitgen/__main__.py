"""python -m unitgen units/filler.yaml: regenerate the unit's 4diac project."""
import argparse

from . import generate, load, manifest_path


def main():
    """Validate a unit specification and regenerate its 4diac project."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", help="Unit specification (YAML)")
    args = parser.parse_args()
    spec = load(args.spec)
    project = generate(spec)
    print(f"Generated {project.root} ({sum(e for *_, e in project.manifest)} exported types); "
          f"manifest {manifest_path(spec)}")
    print(f"Build: 4diac/tools/build-runtime.ps1 -Project {spec.project} -Config {spec.package}-win "
          f"-Manifest {manifest_path(spec)} -Export 4diac/tools/.cache/export-{spec.package} -Module {spec.package}")


if __name__ == "__main__":
    main()
