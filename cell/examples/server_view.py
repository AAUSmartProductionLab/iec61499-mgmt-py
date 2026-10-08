"""What an AAS server holds of the example line, read back from it: the line, its modules and their
components, and the product; and whether the product's plan can be followed into the resources as
they are on the server (``plan_check``), step by step.

    python cell/examples/server_view.py [http://127.0.0.1:8081]
"""
import base64, json, sys, urllib.request
from pathlib import Path
base = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8081").rstrip("/")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import plan_check
def b64(v): return base64.urlsafe_b64encode(v.encode()).decode().rstrip("=")
def get(url): return json.load(urllib.request.urlopen(url, timeout=60))
def everything(kind):
    out, cursor = [], None
    while True:
        page = get(f"{base}/{kind}?limit=100" + (f"&cursor={cursor}" if cursor else ""))
        out += page["result"]; cursor = (page.get("paging_metadata") or {}).get("cursor")
        if not cursor or not page["result"]: return out
shells = everything("shells")
ours = [s for s in shells if s["id"].startswith("https://smartproductionlab.aau.dk/aas/") and
        (s["assetInformation"].get("assetType", "").startswith("https://smartproductionlab.aau.dk/Resource/") or s["idShort"] == "Vial2mLAAS")]
envs = {}
for s in ours:
    subs = [get(f"{base}/submodels/{b64(r['keys'][0]['value'])}") for r in s.get("submodels", [])]
    envs[s["idShort"]] = {"assetAdministrationShells": [s], "submodels": subs}
print(len(shells), "shells on the server;", len(ours), "of the example line")
for name, env in envs.items():
    kind = env["assetAdministrationShells"][0]["assetInformation"].get("assetType", "product").split("/Resource/")[-1]
    print(f"  {name:28} {kind:26} {', '.join(sm['idShort'] for sm in env['submodels'])}"[:200])
vial = envs.pop("Vial2mLAAS")
found = plan_check.check(vial, envs)
print("plan followed into the resources on the server:", found or "every step fits")
plan = next(s for s in vial["submodels"] if s["idShort"] == "ProductionSequence")
for step in plan_check.children(plan_check.at(plan, "Steps")):
    skill = plan_check.resolve(list(envs.values()), plan_check.at(step, "Skill")["value"])
    process = plan_check.resolve([vial], plan_check.at(step, "ProcessReference")["value"])
    binds = [plan_check.at(b, "Name")["value"] for b in plan_check.children(plan_check.at(step, "Bindings"))]
    print(f"  step {plan_check.at(step, 'Name')['value']:11} process {process['idShort']:11} -> {plan_check.at(step, 'Resource')['value']['keys'][0]['value'].rsplit('/', 1)[-1]}.{skill['idShort']}  binds {binds}")
others = [s["idShort"] for s in shells if s not in ours]
print(len(others), "others (the planner's demo data), e.g.", others[:8])
