"""Where a module's AASs and the integrator's record of what was built are: a folder of AAS files (one
environment per ``.json``) or an AAS server (HTTP API, part 2); the record (a Control Configuration
submodel, ARSO 0.10) in a folder or at the registration service (``/build/<idShort>``)."""
from __future__ import annotations

import base64
import json
from pathlib import Path
import urllib.error
import urllib.request

from .aasjson import BASE, at, children, submodel
from .described import NotDescribed

MODULE_TYPE = f"{BASE}/Resource/Module"
CONFIGURATION = f"{BASE}/ARSO/ControlConfiguration/1/0/Submodel"


def b64(identifier: str) -> str:
    """An identifier as the AAS HTTP API expects it in a path (base64url, no padding)."""
    return base64.urlsafe_b64encode(identifier.encode()).decode().rstrip("=")


def is_server(source: str) -> bool:
    return source.startswith(("http://", "https://"))


def fetch(url: str):
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.loads(response.read())


def load(source: str, shell: str | None = None) -> tuple[dict, list[dict]]:
    """The AAS of a module and those of its components, each as an environment (shell and
    submodels), from ``source``: a folder of AAS files (one environment per ``.json``) or the
    address of an AAS server. ``shell``: the module's idShort, when the source holds several."""
    if is_server(source):
        base, shells, cursor = source.rstrip("/"), [], None
        while True:
            page = fetch(f"{base}/shells?limit=100" + (f"&cursor={cursor}" if cursor else ""))
            shells += page["result"]
            cursor = (page.get("paging_metadata") or {}).get("cursor")
            if not cursor or not page["result"]:
                break

        def environment(found: dict) -> dict:
            return {"assetAdministrationShells": [found],
                    "submodels": [fetch(f"{base}/submodels/{b64(r['keys'][0]['value'])}") for r in found.get("submodels", [])]}
    else:
        files = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(Path(source).glob("*.json"))]
        whole = {env["assetAdministrationShells"][0]["id"]: env for env in files if env.get("assetAdministrationShells")}
        shells = [env["assetAdministrationShells"][0] for env in whole.values()]

        def environment(found: dict) -> dict:
            return whole[found["id"]]

    modules = [s for s in shells if s["assetInformation"].get("assetType") == MODULE_TYPE
               and shell in (None, s["idShort"], s["id"])]
    if len(modules) != 1:
        raise NotDescribed(f"{source} holds {len(modules)} module AASs" + (f" named {shell}" if shell else "")
                           + (": name one of " + ", ".join(s["idShort"] for s in modules) if modules else ""))
    module = environment(modules[0])
    parts = {node.get("globalAssetId") for node in children(at(submodel(module, "HierarchicalStructures"), "EntryNode"))}
    return module, [environment(s) for s in shells if s["assetInformation"].get("globalAssetId") in parts]


def store(source: str, module: dict, loaded: dict | None = None) -> str:
    """Put the recorded AAS of the module back where it came from; returns where it went. On a
    server that is every submodel the record changed against ``loaded`` (the AAS as it was read):
    the skills (Deployment) and, when a built skill got its interface, the interface description,
    the data points and the mappings; the capabilities. Without ``loaded``, every submodel."""
    shell = module["assetAdministrationShells"][0]
    if is_server(source):
        before = {s["id"]: s for s in (loaded or {}).get("submodels", [])}
        changed = [s for s in module["submodels"] if not loaded or s != before.get(s["id"])]
        for model_ in changed:
            url = f"{source.rstrip('/')}/submodels/{b64(model_['id'])}"
            request = urllib.request.Request(url, json.dumps(model_).encode(), method="PUT",
                                             headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=30):
                pass
        return f"{source.rstrip('/')}: " + ", ".join(s["idShort"] for s in changed)
    path = Path(source) / f"{shell['idShort']}.json"
    path.write_text(json.dumps(module, indent=1), encoding="utf-8")
    return str(path)


def record_url(where: str, module: dict) -> str:
    return f"{where.rstrip('/')}/build/{module['assetAdministrationShells'][0]['idShort']}"


def load_record(where: str | None, module: dict) -> dict | None:
    """The record of what was built for ``module``; None if there is none (yet)."""
    if not where:
        return None
    if is_server(where):
        try:
            return fetch(record_url(where, module))
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            raise
    path = Path(where) / f"{module['assetAdministrationShells'][0]['idShort']}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def store_record(where: str, module: dict, record_: dict) -> str:
    """Keep the record of ``module``; returns where it went."""
    if is_server(where):
        request = urllib.request.Request(record_url(where, module), json.dumps(record_).encode(), method="PUT",
                                         headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=30):
            pass
        return record_url(where, module)
    path = Path(where) / f"{module['assetAdministrationShells'][0]['idShort']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record_, indent=1), encoding="utf-8")
    return str(path)


def endpoint(record_: dict | None) -> tuple[str | None, int | None]:
    """Where the record says the module's FORTE is managed: (host, port)."""
    stated_ = (at(record_, "Runtime", "ManagementEndpoint") or {}).get("value") or ""
    host, _, port = stated_.rpartition(":")
    return (host or None, int(port)) if port.isdigit() else (stated_ or None, None)


def instances(record_: dict | None) -> list[tuple[str, str, str | None]]:
    """What the record says was built: (instance, block type, type hash or None)."""
    found = []
    for instance in children(at(record_, "Instances")):
        get = lambda n: (at(instance, n) or {}).get("value")  # noqa: E731
        found.append((get("InstancePath"), get("FBType"), get("TypeHash")))
    return found


def new_record(module: dict) -> dict:
    """An empty record for a module that has none yet."""
    return {"idShort": "ControlConfiguration", "modelType": "Submodel",
            "id": f"{module['assetAdministrationShells'][0]['id']}/submodels/ControlConfiguration",
            "semanticId": {"type": "ExternalReference", "keys": [{"type": "GlobalReference", "value": CONFIGURATION}]},
            "submodelElements": []}
