"""Build the AASs of the example line: its four resources and the products planned on them.

    python cell/examples/example_line.py --out <folder> [--publish http://<host>:8081]

Every AAS is built by ``modreg`` from a profile: the pydantic dump of its type (aas-model).

- The profiles of the resources are made from their module specs: the filling and stoppering
  modules are built and run (``cell/modules``); the capping and inspection modules are planned
  only (``cell/modules/planned``: no program behind them yet).
- The profile of a product is a file in this folder (``<Product>AAS.json``, a ``ProductTypeAAS``):
  what it consists of, the processes it needs and the plan that assigns them to the resources.

The plan of each product is then followed into the resources (``plan_check``), every AAS is
written to ``<folder>/<idShort>.json``, and with ``--publish`` sent to an AAS server (created, or
replaced if it is there already).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from modgen import SPECS, load                          # noqa: E402
from modreg import model, profile as profiles           # noqa: E402
from modreg.service import AasServer                    # noqa: E402

import plan_check                                        # noqa: E402

# The resources of the example line, in the order a vial passes them.
RESOURCES = [SPECS / "filling.yaml", SPECS / "stoppering.yaml", SPECS / "planned" / "capping.yaml",
             SPECS / "planned" / "inspection.yaml"]


def resource(path: Path) -> dict:
    """The AAS of a module, from its spec (for its first target; the module is not read)."""
    spec = load(path)
    return model.build(profiles.describe(spec, next(iter(spec.targets)), spec_path=path.relative_to(HERE.parents[1]).as_posix()))


def product_profiles() -> dict[str, dict]:
    """The profiles of the products in this folder, by the idShort of their AAS."""
    found = {}
    for path in sorted(HERE.glob("*.json")):
        profile = json.loads(path.read_text(encoding="utf-8"))
        if profile.get("aas_type") == "ProductTypeAAS":
            found[profile["id_short"]] = profile
    return found


def build() -> tuple[dict[str, dict], dict[str, dict]]:
    """The resources and the products of the example line, each as an AAS environment by idShort."""
    resources = {}
    for path in RESOURCES:
        env = resource(path)
        resources[plan_check.shell_of(env)["idShort"]] = env
    products = {name: model.build(profile) for name, profile in product_profiles().items()}
    return resources, products


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default="aas", help="folder the AASs are written to")
    parser.add_argument("--publish", metavar="URL", help="AAS server to send them to, e.g. http://localhost:8081")
    args = parser.parse_args(argv)

    resources, products = build()
    broken = {name: found for name, env in products.items() if (found := plan_check.check(env, resources))}
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
