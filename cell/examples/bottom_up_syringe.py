"""A product for showing Match and plan: the example line's syringe, filled from the bottom, under ids of
its own (PrefilledSyringe1mLBottomUpAAS), next to the example line on an AAS server.

    python cell/examples/example_line.py --out <folder> --publish <AAS server>
    python cell/examples/bottom_up_syringe.py <folder> <AAS server>

It asks for BottomUpFilling instead of Filling, with the bounds of its requirement (the needle at most 2 mm
above and 3 mm below the liquid) and its barrel's geometry as product parameters of its Filling process
(vocabulary 0.10). The example line's own syringe asks for Filling: its process AAS, the plan check and
the agents' tests rest on that."""
import base64
import copy
import json
import sys
import warnings

warnings.filterwarnings("ignore")
from modreg.service import AasServer                                # noqa: E402

FOLDER, REPO = sys.argv[1], sys.argv[2]
LAB = "https://smartproductionlab.aau.dk/semantics"
OLD, NEW = "PrefilledSyringe1mL", "PrefilledSyringe1mLBottomUp"


def b64(text):
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


text = open(f"{FOLDER}/{OLD}AAS.json", encoding="utf-8").read()
old_id, new_id = f"https://smartproductionlab.aau.dk/aas/{OLD}AAS", f"https://smartproductionlab.aau.dk/aas/{NEW}AAS"
assert b64(old_id) in text, "the process plan's id is not the base64 of the product's"
text = text.replace(b64(old_id), b64(new_id)).replace(OLD, NEW)
env = json.loads(text)
shell = env["assetAdministrationShells"][0]
shell["displayName"] = [{"language": "en", "text": "Prefilled syringe 1 mL, filled from the bottom"}]


def at(element, *path):
    for step in path:
        held = element.get("submodelElements") or element.get("value") or []
        element = next(c for c in held if isinstance(c, dict) and c.get("idShort") == step)
    return element


def submodel(id_short):
    return next(s for s in env["submodels"] if s["idShort"] == id_short)


required = at(submodel("CapabilityDescription"), "RequiredCapabilities", "Filling")
capability = at(required, "Capability")
capability["supplementalSemanticIds"][0]["keys"][0]["value"] = f"{LAB}/BottomUpFilling"
capability["displayName"] = [{"language": "en", "text": "Bottom-up filling"}]
def in_mm(element):
    """The element's unit made mm wherever it is stated: its Unit qualifier and its data specification
    (both are copied from FillVolume's, in mL; the matcher reads the qualifier first, 9 Nov)."""
    for q in element.get("qualifiers", []):
        if q.get("type") == "Unit" or q.get("type", "").endswith("Unit"):
            q["value"] = "mm"
    for spec in element.get("embeddedDataSpecifications") or []:
        content = spec.get("dataSpecificationContent") or {}
        if "unit" in content:
            content["unit"] = "mm"


properties = at(required, "PropertySet")
volume = at(properties, "FillVolume")
for name, value in (("MinImmersion", "-2.0"), ("MaxImmersion", "3.0")):
    made = copy.deepcopy(volume)
    made["idShort"] = name
    inner = made["value"][0]
    inner["displayName"] = [{"language": "en", "text": name}]
    inner["supplementalSemanticIds"][0]["keys"][0]["value"] = f"{LAB}/{name}"
    inner["value"] = value
    in_mm(inner)
    properties["value"].append(made)
parameters = at(submodel("ProcessParameters"), "Processes", "Filling", "ProductParameters") if any(
    c.get("idShort") == "Processes" for c in submodel("ProcessParameters")["submodelElements"]) else \
    at(submodel("ProcessParameters"), "Filling", "ProductParameters")
fill = at(parameters, "FillVolume")
for name, value in (("InnerDiameter", "6.35"), ("InnerBottomHeight", "11.0"), ("RimHeight", "66.0")):
    made = copy.deepcopy(fill)
    made["idShort"] = name
    made["semanticId"]["keys"][0]["value"] = f"{LAB}/{name}"
    made["value"] = value
    in_mm(made)
    parameters["value"].append(made)
json.dump(env, open(f"{FOLDER}/{NEW}AAS.json", "w", encoding="utf-8"), indent=1)
done = AasServer(REPO).publish(env)
print(f"{NEW}AAS: {sum(d.startswith('POST') for d in done)} created, {sum(d.startswith('PUT') for d in done)} replaced")
