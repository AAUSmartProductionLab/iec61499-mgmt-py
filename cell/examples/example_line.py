"""Build the AASs of the example line: its four resources and the products planned on them.

    python cell/examples/example_line.py --out <folder> [--publish http://<host>:8081]

Every AAS is built by ``modreg`` from a profile: the pydantic dump of its type (aas-model).

- The profiles of the resources are made from their module specs: the filling and stoppering
  modules are built and run (``cell/modules``); the capping and inspection modules are planned
  only (``cell/modules/planned``: no program behind them yet).
- The profile of a product is a file in this folder (``<Product>AAS.json``, a ``Product``):
  what it consists of, the processes it needs and the plan that assigns them to the resources.

The plan of each product is then followed into the resources (``plan_check``), and each product
gets a process AAS on the line (``process_aas``, a draft: its recipe bound to the resources).
Every AAS is written to ``<folder>/<idShort>.json``, and with ``--publish`` sent to an AAS server
(created, or replaced if it is there already).
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
from aas_pydantic.submodel_templates.hierarchical_structures import ArcheType      # noqa: E402
from modgen.spec import Location, Point                  # noqa: E402
from modreg import model, planar, profile as profiles   # noqa: E402
from modreg.frames import place, relative               # noqa: E402
from aas_model.submodel_templates.coordinates import Coordinates                 # noqa: E402
from aas_model.submodel_templates.variables import MeasurementsGroup, Variables   # noqa: E402
from modreg.service import AasServer                    # noqa: E402

import plan_check                                        # noqa: E402
import process_aas                                       # noqa: E402

# The resources of the example line, in the order a vial passes them.
RESOURCES = [SPECS / "filling.yaml", SPECS / "stoppering.yaml", SPECS / "planned" / "capping.yaml",
             SPECS / "planned" / "inspection.yaml"]


# The line: what it is called, and the modules a vial passes that are not described yet (each has a
# Kuka robot and a gripper, and a Raspberry Pi of its own).
LINE = "FillingLine"
BEFORE, AFTER = ["LoadingModule"], ["UnloadingModule"]
# Where each module's base is relative to the planar table's base (ARSO 0.13), the root of the
# line's coordinates: the table's corner, the frame its shuttles move in (4 x 3 flyways, 960 x 720
# mm). Each module has its front at the table's edge, facing in, so that its transfer point is a
# station of the planar controller's simulated table (planar-controller/tests/line_scenario.py).
# Placeholders until the modules report where they are (RFID).
TABLE = "PlanarTable"
LAYOUT = {
    "LoadingModule": Location(x=0.0, y=180.0, rz=-90.0),
    "FillingModule": Location(x=240.0, y=720.0, rz=180.0),
    "StopperingModule": Location(x=600.0, y=720.0, rz=180.0),
    "CappingModule": Location(x=960.0, y=360.0, rz=90.0),
    "InspectionModule": Location(x=960.0, y=120.0, rz=90.0),
    "UnloadingModule": Location(x=660.0, y=0.0),
}
# Points of the line itself: where the loading robot places a vial on a shuttle and where the
# unloading robot picks it (the robots' modules are not described yet), on the table.
POINTS = {"Infeed": Point(meaning="PlacePoint", location=Location(x=60.0, y=180.0),
                          description="Where the loading robot places a vial on a shuttle"),
          "Outfeed": Point(meaning="PickPoint", location=Location(x=660.0, y=60.0),
                           description="Where the unloading robot picks a vial from a shuttle")}
# The stations a shuttle stops at on its way through the line, in order, each a point of the line or
# a module's transfer point (planar-controller/tests/line_scenario.py names them so): (AAS, coordinate).
STATIONS = {"Infeed": (f"{LINE}AAS", "Infeed"), "Filling": ("FillingModuleAAS", "Transfer"),
            "Stoppering": ("StopperingModuleAAS", "Transfer"), "Capping": ("CappingModuleAAS", "Transfer"),
            "Outfeed": (f"{LINE}AAS", "Outfeed")}


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


@functools.lru_cache(maxsize=None)
def table() -> dict:
    """The AAS of the planar table (4 x 3 flyways), whose base is the root of the line's coordinates.
    Its shuttles are not described here: they come from the controller (``modreg profile planar``)."""
    return model.build(planar.describe_all(planar.Table(columns=4, rows=3, shuttles=()))[0])


def table_base() -> tuple[str, str]:
    """The root of the line's coordinates: (the table's AAS id, its coordinate)."""
    return plan_check.shell_of(table())["id"], "TableBase"


def line_profile(resources: dict[str, dict]) -> dict:
    """The profile of the line: a system made of its modules, each found by its asset id, and the
    coordinates of its own points, relative to the table's base."""
    asset = lambda name: f"{BASE_URL}/assets/{name}"                                       # noqa: E731
    node = lambda found, about: model.LocatedNode(                                          # noqa: E731
        entity_type="SelfManagedEntity", global_asset_id=found, description=about)
    nodes = {name: node(asset(name), f"{name}: not described yet") for name in BEFORE}
    for env in resources.values():
        shell = plan_check.shell_of(env)
        name = shell["assetInformation"]["globalAssetId"].rsplit("/", 1)[-1]
        nodes[name] = node(shell["assetInformation"]["globalAssetId"], shell["idShort"])
    nodes.update({name: node(asset(name), f"{name}: not described yet") for name in AFTER})
    nodes[TABLE] = node(plan_check.shell_of(table())["assetInformation"]["globalAssetId"],
                        "The planar table the shuttles move on (planar-controller)")
    base = profiles.coordinate_ref(table_base()[1], table_base()[0])
    points = {name: profiles.coordinate(name, point.meaning, point.location, base, description=point.description)
              for name, point in POINTS.items()}
    system = model.ProductionSystem(id_short=f"{LINE}AAS", id=f"{BASE_URL}/aas/{LINE}AAS", asset_type=f"{model.RESOURCE}/System",
                                 description="The line a vial passes: loading, filling, stoppering, capping, inspection, unloading")
    system.hierarchical_structures = model.LocatedStructures(
        id_short="HierarchicalStructures", ArcheType=ArcheType(value="OneDown"),
        EntryNode=model.LocatedEntryNode(global_asset_id=asset(LINE), description="The line", Node=nodes))
    system.variables = Variables(id_short="Variables", Measurements=MeasurementsGroup(
        value={"Coordinates": Coordinates(coordinate=points)}))
    return model.profile(model.ProductionSystem.model_validate(system.model_dump()), global_asset_id=asset(LINE))


def line(resources: dict[str, dict]) -> dict:
    """The AAS of the line."""
    return model.build(line_profile(resources))


def stations(envs: list[dict]) -> dict[str, tuple[float, float, float]]:
    """Where a shuttle stops for each station, (x, y, rz) in the planar table's frame, from the AASs
    of the table, the line and its modules (``envs``): what the line scenario of the planar
    controller drives to."""
    found = {}
    for name, point in STATIONS.items():
        pose = relative(envs, (f"{TABLE}AAS", "TableBase"), point)
        x, y, _ = pose.position
        rz = (pose.heading + 180.0) % 360.0 - 180.0                       # in [-180, 180)
        found[name] = tuple(round(v, 3) + 0.0 for v in (x, y, rz))         # + 0.0: no -0.0
    return found


def product_profiles() -> dict[str, dict]:
    """The profiles of the products in this folder, by the idShort of their AAS."""
    found = {}
    for path in sorted(HERE.glob("*.json")):
        profile = json.loads(path.read_text(encoding="utf-8"))
        if profile.get("aas_type") in ("Product", "ProductTypeAAS"):
            found[profile["id_short"]] = profile
    return found


def build() -> tuple[dict[str, dict], dict[str, dict]]:
    """The resources and the products of the example line, each as an AAS environment by idShort."""
    resources = {}
    for path in RESOURCES:
        env = resource(path)
        # Put on the line: the module reports where its base is on the table (later by RFID).
        name = plan_check.shell_of(env)["assetInformation"]["globalAssetId"].rsplit("/", 1)[-1]
        env = place(env, "ModuleBase", table_base(), LAYOUT[name])
        resources[plan_check.shell_of(env)["idShort"]] = env
    products = {name: model.build(profile) for name, profile in product_profiles().items()}
    return resources, products


def processes(resources: dict[str, dict], products: dict[str, dict], system: dict) -> dict[str, dict]:
    """The process AAS of every product on the line, by idShort: its recipe bound to the resources,
    with what the plan check found."""
    made = [process_aas.process(env, system, plan_check.check(env, resources)) for env in products.values()]
    return {plan_check.shell_of(env)["idShort"]: env for env in made}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default="aas", help="folder the AASs are written to")
    parser.add_argument("--publish", metavar="URL", help="AAS server to send them to, e.g. http://localhost:8081")
    args = parser.parse_args(argv)

    resources, products = build()
    broken = {name: found for name, env in products.items() if (found := plan_check.check(env, resources))}
    system = line(resources)
    everything = {plan_check.shell_of(system)["idShort"]: system, plan_check.shell_of(table())["idShort"]: table(),
                  **resources, **components(), **products,
                  **processes(resources, products, system)}
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, env in everything.items():
        (out / f"{name}.json").write_text(json.dumps(env, indent=1), encoding="utf-8")
        print(f"{name}: {len(env['submodels'])} submodels -> {out / (name + '.json')}")
    for name, found in broken.items():
        for told in found:
            print(f"  {name}: {told}")
    if broken:
        print("not published: a plan does not fit its resources" if args.publish else "a plan does not fit its resources")
        return 1
    print(f"every plan fits its resources ({len(products)} product(s), {len(resources)} modules, "
          f"{len(components())} components, 1 line, 1 table)")
    if args.publish:
        server = AasServer(args.publish)
        for name, env in everything.items():
            done = server.publish(env)
            print(f"{name}: {sum(d.startswith('POST') for d in done)} created, {sum(d.startswith('PUT') for d in done)} replaced")
    return 0


if __name__ == "__main__":
    sys.exit(main())
