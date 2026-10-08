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
import functools
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from modgen import SPECS, load                          # noqa: E402
from aas_model.constants import BASE_URL                                  # noqa: E402
from aas_pydantic.submodel_templates.hierarchical_structures import (     # noqa: E402
    ArcheType, EntryNode, HierarchicalStructures, Node)
from modreg import model, profile as profiles           # noqa: E402
from modreg.service import AasServer                    # noqa: E402

import plan_check                                        # noqa: E402

# The resources of the example line, in the order a vial passes them.
RESOURCES = [SPECS / "filling.yaml", SPECS / "stoppering.yaml", SPECS / "planned" / "capping.yaml",
             SPECS / "planned" / "inspection.yaml"]


# The line: what it is called, and the modules a vial passes that are not described yet (each has a
# Kuka robot and a gripper, and a Raspberry Pi of its own).
LINE = "FillingLine"
BEFORE, AFTER = ["LoadingModule"], ["UnloadingModule"]


@functools.lru_cache(maxsize=None)
def described(path: Path) -> tuple[dict, ...]:
    """The AASs of a module and of its components, from its spec (for its first target; the module
    is not read). The module's is the first."""
    spec = load(path)
    found = profiles.describe_all(spec, next(iter(spec.targets)), spec_path=path.relative_to(HERE.parents[1]).as_posix())
    return tuple(model.build(profile) for profile in found)


def resource(path: Path) -> dict:
    """The AAS of a module."""
    return described(path)[0]


def components() -> dict[str, dict]:
    """The AASs of the components of every module of the line, by idShort."""
    return {plan_check.shell_of(env)["idShort"]: env for path in RESOURCES for env in described(path)[1:]}


def line_profile(resources: dict[str, dict]) -> dict:
    """The profile of the line: a system made of its modules, each found by its asset id."""
    asset = lambda name: f"{BASE_URL}/assets/{name}"                                       # noqa: E731
    nodes = {name: Node(entity_type="SelfManagedEntity", global_asset_id=asset(name), description=f"{name}: not described yet")
             for name in BEFORE}
    for env in resources.values():
        shell = plan_check.shell_of(env)
        name = shell["assetInformation"]["globalAssetId"].rsplit("/", 1)[-1]
        nodes[name] = Node(entity_type="SelfManagedEntity", global_asset_id=shell["assetInformation"]["globalAssetId"],
                           description=shell["idShort"])
    nodes.update({name: Node(entity_type="SelfManagedEntity", global_asset_id=asset(name), description=f"{name}: not described yet")
                  for name in AFTER})
    system = model.SystemTypeAAS(id_short=f"{LINE}AAS", id=f"{BASE_URL}/aas/{LINE}AAS", asset_type=f"{model.RESOURCE}/System",
                                 description="The line a vial passes: loading, filling, stoppering, capping, inspection, unloading")
    system.hierarchical_structures = HierarchicalStructures(
        id_short="HierarchicalStructures", ArcheType=ArcheType(value="OneDown"),
        EntryNode=EntryNode(global_asset_id=asset(LINE), description="The line", Node=nodes))
    return model.profile(model.SystemTypeAAS.model_validate(system.model_dump()), global_asset_id=asset(LINE))


def line(resources: dict[str, dict]) -> dict:
    """The AAS of the line."""
    return model.build(line_profile(resources))


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
    system = line(resources)
    everything = {plan_check.shell_of(system)["idShort"]: system, **resources, **components(), **products}
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, env in everything.items():
        (out / f"{name}.json").write_text(json.dumps(env, indent=1), encoding="utf-8")
        print(f"{name}: {len(env['submodels'])} submodels -> {out / (name + '.json')}")
    for name, found in broken.items():
        for line in found:
            print(f"  {name}: {line}")
    if broken:
        print("not published: a plan does not fit its resources" if args.publish else "a plan does not fit its resources")
        return 1
    print(f"every plan fits its resources ({len(products)} product(s), {len(resources)} modules, "
          f"{len(components())} components, 1 line)")
    if args.publish:
        server = AasServer(args.publish)
        for name, env in everything.items():
            done = server.publish(env)
            print(f"{name}: {sum(d.startswith('POST') for d in done)} created, {sum(d.startswith('PUT') for d in done)} replaced")
    return 0


if __name__ == "__main__":
    sys.exit(main())
