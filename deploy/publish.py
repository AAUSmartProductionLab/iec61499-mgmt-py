"""Publish every AAS the lab stack shows, created or replaced: aas-model's lab instances, the example
line, and the modules on their Pis.

    python deploy/publish.py                                # to the stack on this PC (http://localhost:8081)
    python deploy/publish.py --only aas-model               # one part: aas-model | line | modules
    python deploy/publish.py --url http://<server>:8081     # the lab's server: only with the user's go

1. aas-model: the lab's resources as aas-model writes them (``aas_model.resource_instances``,
   ``RESOURCE_FACTORIES``): the stations of the industrial line (Syntegon, Cytiva, IMA, Optima,
   Omron), the planar table and its shuttles, the filling line, the orchestrator and the planner.
2. line: the example line (``cell/examples/example_line.py``): the line, the planar table and its
   shuttles as the controller describes them, the modules and their components, the products and
   their processes, each process checked. The modules are described for their Pis (``--target pi``),
   so the DMP calls the modules that run; the inspection module, planned only, for the PC.
3. modules: the modules on their Pis that are not on the example line yet (the second filling module),
   each with its components.

The ids of 1 and 2 differ (``planarTableAAS`` is aas-model's table, ``PlanarTableAAS`` the
controller's), so both are on the server side by side. BaSyx keeps them in MongoDB: a restart of
the stack keeps them.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cell" / "examples"))

from basyx.aas.adapter.json import json_serialization          # noqa: E402

from aas_pydantic.convert_util import strip_temp_id_short_attributes   # noqa: E402

from aas_model.builder import build_from_model                 # noqa: E402
from aas_model.resource_instances import RESOURCE_FACTORIES     # noqa: E402
from modgen import SPECS, load                                  # noqa: E402
from modreg import model, profile as profiles                   # noqa: E402
from modreg.service import AasServer, mapped_last               # noqa: E402

# Modules that run on a Pi and are not on the example line (yet): published alone, from their pi target.
BESIDE_THE_LINE = [SPECS / "filling-2.yaml"]


def aas_model_instances() -> dict[str, dict]:
    """aas-model's lab resources, each as an AAS environment, by idShort."""
    found = {}
    for make in RESOURCE_FACTORIES.values():
        store = build_from_model(make())
        # The items of a SubmodelElementList carry their idShort in a temporary Property on the way
        # through the conversion; it must not be published (the DMP refuses the mapping that has it).
        strip_temp_id_short_attributes(store)
        env = json.loads(json_serialization.object_store_to_json(store))
        found[env["assetAdministrationShells"][0]["idShort"]] = env
    return found


def modules_beside_the_line() -> dict[str, dict]:
    """The modules not on the example line, each with its components, for their Pis, by idShort."""
    found = {}
    for path in BESIDE_THE_LINE:
        spec = load(path)
        for env in (model.build(p) for p in profiles.describe_all(spec, "pi", spec_path=path.relative_to(ROOT).as_posix())):
            found[env["assetAdministrationShells"][0]["idShort"]] = env
    return found


def send(server: AasServer, envs: dict[str, dict]) -> None:
    names = {id(env): name for name, env in envs.items()}
    for env in mapped_last(list(envs.values())):
        done = server.publish(env)
        print(f"{names[id(env)]}: {sum(d.startswith('POST') for d in done)} created, "
              f"{sum(d.startswith('PUT') for d in done)} replaced")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default="http://localhost:8081", help="the AAS environment")
    parser.add_argument("--only", choices=["aas-model", "line", "modules"], help="publish this part only")
    args = parser.parse_args(argv)
    server = AasServer(args.url, timeout=30)
    if args.only in (None, "aas-model"):
        print("== aas-model's lab instances")
        send(server, aas_model_instances())
    if args.only in (None, "line"):
        print("== the example line, its modules on their Pis")
        import example_line
        with tempfile.TemporaryDirectory() as out:
            example_line.main(["--out", out, "--publish", args.url, "--target", "pi"])
    if args.only in (None, "modules"):
        print("== modules beside the line, on their Pis")
        send(server, modules_beside_the_line())
    shells = server.listing("shells")
    print(f"{args.url} holds {len(shells)} shells")
    return 0


if __name__ == "__main__":
    sys.exit(main())
