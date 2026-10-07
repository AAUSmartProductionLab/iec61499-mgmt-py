"""Build the AASs of the example line: its four resources and the products planned on them.

    python cell/examples/example_line.py --out <folder> [--publish http://<host>:8081]

- The filling and stoppering modules are built and run (``cell/modules``); the capping and
  inspection modules are planned only (``cell/modules/planned``: no program behind them yet).
  All four AASs are built by ``modreg`` from their module specs.
- Every product description in this folder (``*.yaml``) becomes a product AAS (``product_aas.py``).

The plan of each product is then followed into the resources (``product_aas.check``), every AAS is
written to ``<folder>/<idShort>.json``, and with ``--publish`` sent to an AAS server (created, or
replaced if it is there already).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from modgen import SPECS, load                          # noqa: E402
from modreg import model, profile as profiles           # noqa: E402
from modreg.service import AasServer                    # noqa: E402

import product_aas as product                            # noqa: E402

# The resources of the example line, in the order a vial passes them.
RESOURCES = [SPECS / "filling.yaml", SPECS / "stoppering.yaml", SPECS / "planned" / "capping.yaml",
             SPECS / "planned" / "inspection.yaml"]


def resource(path: Path) -> dict:
    """The AAS of a module, from its spec (for its first target; the module is not read)."""
    spec = load(path)
    return model.build(profiles.describe(spec, next(iter(spec.targets)), spec_path=path.relative_to(HERE.parents[1]).as_posix()))


def build() -> tuple[dict[str, dict], dict[str, dict]]:
    """The resources and the products of the example line, each as an AAS environment by idShort."""
    resources = {}
    for path in RESOURCES:
        env = resource(path)
        resources[product.shell_of(env)["idShort"]] = env
    template = next(s for s in next(iter(resources.values()))["submodels"] if s["idShort"] == "Nameplate")
    products = {}
    for path in sorted(HERE.glob("*.yaml")):
        env = product.build(yaml.safe_load(path.read_text(encoding="utf-8")), resources, template)
        products[product.shell_of(env)["idShort"]] = env
    return resources, products


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default="aas", help="folder the AASs are written to")
    parser.add_argument("--publish", metavar="URL", help="AAS server to send them to, e.g. http://localhost:8081")
    args = parser.parse_args(argv)

    resources, products = build()
    broken = {name: found for name, env in products.items() if (found := product.check(env, resources))}
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, env in {**resources, **products}.items():
        (out / f"{name}.json").write_text(json.dumps(env, indent=1), encoding="utf-8")
        print(f"{name}: {len(env['submodels'])} submodels -> {out / (name + '.json')}")
    for name, found in broken.items():
        for line in found:
            print(f"  {name}: {line}")
    if broken:
        print("not published: a plan does not fit its resources" if args.publish else "a plan does not fit its resources")
        return 1
    print(f"every plan fits its resources ({len(products)} product(s), {len(resources)} resources)")
    if args.publish:
        server = AasServer(args.publish)
        for name, env in {**resources, **products}.items():
            done = server.publish(env)
            print(f"{name}: {sum(d.startswith('POST') for d in done)} created, {sum(d.startswith('PUT') for d in done)} replaced")
    return 0


if __name__ == "__main__":
    sys.exit(main())
