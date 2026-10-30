"""What an agent reads from the AAS server: environments, a product's steps, a resource's offer.

Everything here works on the JSON an AAS server holds (an environment: one shell and its submodels),
whoever built it, with the helpers of the plan check (``modreg.plancheck``).

- A **step** of a product is a step of its Production Sequence, in its order, with the required
  capability it names: a capability container of the product's Capability Description (the
  capability, its meaning as a supplemental id, and the values the product needs in its property
  set). The container is what a call for proposals carries.
- An **offer** is what a resource answers with: the offered capability of the same meaning (or of
  a narrower one: a module that fills bottom-up fills) whose properties cover the required values,
  the skill that realizes it, whether that skill is built (``Deployment``: it runs now) or only
  described (a reconfiguration creates it first), and the skill's arguments: each input of its Start
  command given the required value of the same meaning. Of several, one of the same meaning before a
  narrower one, and a built skill before one a reconfiguration creates. A module's offer also says
  where a shuttle hands it the product (its station).
- A module's **station** is its transfer point (the coordinate meaning TransferPoint) in the planar
  table's frame, through the coordinates the AASs of the module, the line and the table give.
- A **transport** is asked for as a product asks for a step: a required Transporting with the
  target pose (TargetX, TargetY, TargetRz); a shuttle offers it (modreg.planar).
"""
from __future__ import annotations

from dataclasses import dataclass, field
import base64
import functools
import json
import urllib.parse
import urllib.request

from modreg.plancheck import at, children, covers, number, resolve, semantic_ids, shell_of, unit_of

MEANS = "https://smartproductionlab.aau.dk/semantics"
MODULE_TYPE = "Resource/Module"          # the end of a module's assetType
SYSTEM_TYPE = "Resource/System"          # the end of a line's
TRANSPORTING = f"{MEANS}/Transporting"
IDTA = "https://admin-shell.io/idta"


@functools.cache
def _vocabulary():
    from modplan.vocabulary import Vocabulary
    return Vocabulary()


def narrows(offered: str, wanted: str) -> bool:
    """The capability ``offered`` is ``wanted`` or a narrower one (both meanings, IRIs)."""
    if offered == wanted:
        return True
    if not (offered.startswith(MEANS) and wanted.startswith(MEANS)):
        return False
    return wanted.rsplit("/", 1)[-1] in _vocabulary().lineage(offered.rsplit("/", 1)[-1])


def b64(identifier: str) -> str:
    return base64.urlsafe_b64encode(identifier.encode()).decode().rstrip("=")


class AasServer:
    """An AAS repository (part 2 HTTP API), read only."""

    def __init__(self, url: str, timeout: float = 10.0):
        self.url, self.timeout = url.rstrip("/"), timeout

    def get(self, path: str, query: dict | None = None):
        url = f"{self.url}/{path}" + (f"?{urllib.parse.urlencode(query)}" if query else "")
        with urllib.request.urlopen(urllib.request.Request(url, headers={"Accept": "application/json"}),
                                    timeout=self.timeout) as answer:
            return json.loads(answer.read())

    def shells(self) -> list[dict]:
        found, cursor = [], None
        while True:
            page = self.get("shells", {"limit": 100, **({"cursor": cursor} if cursor else {})})
            found += page.get("result", [])
            cursor = (page.get("paging_metadata") or {}).get("cursor")
            if not cursor:
                return found

    def environment(self, shell: dict | str) -> dict:
        """A shell (or its id) with its submodels."""
        if isinstance(shell, str):
            shell = self.get(f"shells/{b64(shell)}")
        submodels = []
        for ref in shell.get("submodels") or []:
            try:
                submodels.append(self.get(f"submodels/{b64(ref['keys'][0]['value'])}"))
            except OSError:
                continue
        return {"assetAdministrationShells": [shell], "submodels": submodels}


def is_module(env: dict) -> bool:
    """A module's AAS (not a component's, the line's or a product's)."""
    return (shell_of(env).get("assetInformation", {}).get("assetType") or "").endswith(MODULE_TYPE)


def submodel(env: dict, id_short: str) -> dict | None:
    return next((s for s in env["submodels"] if s.get("idShort") == id_short), None)


def meanings(element: dict | None) -> set[str]:
    """What an element means: its supplemental semantic ids."""
    return set(semantic_ids(element or {})[1:])


# A product's steps --------------------------------------------------------------------------------

@dataclass
class Step:
    name: str
    order: int
    required: dict                       # the required capability container

    @property
    def meaning(self) -> set[str]:
        return meanings(at(self.required, "Capability"))


def steps(product: dict) -> list[Step]:
    """The steps of a product's Production Sequence, in order, each with its required capability."""
    found = []
    for step in children(at(submodel(product, "ProductionSequence"), "Steps")):
        for ref in children(at(step, "RequiredCapabilities")):
            keys = ref["value"]["keys"]
            container = resolve([product], {**ref["value"], "keys": keys[:-1]})   # without the Capability
            if container is not None:
                found.append(Step(at(step, "Name")["value"] if at(step, "Name") else step["idShort"],
                                  int(number((at(step, "Order") or {}).get("value")) or 0), container))
    return sorted(found, key=lambda s: s.order)


def required_values(required: dict) -> dict[str, dict]:
    """The values a required capability asks for, by meaning: the property's Value element."""
    found = {}
    for container in children(at(required, "PropertySet")):
        value = at(container, "Value")
        for meaning in meanings(value):
            found[meaning] = value
    return found


# A resource's offer ---------------------------------------------------------------------------------

@dataclass
class Offer:
    resource: str                        # the module's AAS idShort
    capability: str                      # the offered capability container
    skill: str                           # the skill that realizes it
    built: bool                          # it runs now; else a reconfiguration creates it first
    arguments: dict[str, float] = field(default_factory=dict)    # the skill's inputs by name
    station: tuple[float, float, float] | None = None            # where the product is handed over (x, y, rz)

    def element(self) -> dict:
        """The offer as an interaction element of a proposal."""
        def prop(name, value, kind="xs:string"):
            return {"modelType": "Property", "idShort": name, "valueType": kind, "value": str(value)}
        args = [prop(name, value, "xs:double") for name, value in self.arguments.items()]
        found = [prop("Resource", self.resource), prop("Capability", self.capability), prop("Skill", self.skill),
                 prop("Reconfiguration", str(not self.built).lower(), "xs:boolean"),
                 {"modelType": "SubmodelElementCollection", "idShort": "Arguments", "value": args}]
        if self.station is not None:
            found.append({"modelType": "SubmodelElementCollection", "idShort": "Station", "value": [
                prop(name, value, "xs:double") for name, value in zip(("X", "Y", "Rz"), self.station)]})
        return {"modelType": "SubmodelElementCollection", "idShort": "Offer", "value": found}

    @classmethod
    def from_element(cls, element: dict) -> "Offer":
        value = lambda name: (at(element, name) or {}).get("value")       # noqa: E731
        station = {p["idShort"]: float(p["value"]) for p in children(at(element, "Station"))}
        return cls(value("Resource"), value("Capability"), value("Skill"), value("Reconfiguration") != "true",
                   {a["idShort"]: float(a["value"]) for a in children(at(element, "Arguments"))},
                   (station["X"], station["Y"], station["Rz"]) if station else None)


def skill_element(module: dict, name: str) -> dict | None:
    return at(submodel(module, "Skills"), name)


def offer(module: dict, required: dict) -> Offer | list[str]:
    """What the module offers for a required capability, or why it offers nothing."""
    name = shell_of(module)["idShort"]
    wanted = meanings(at(required, "Capability"))
    asked = required_values(required)
    reasons, found = [], []
    containers = [c for capability_set in children(submodel(module, "CapabilityDescription")) for c in children(capability_set)]
    for container in containers:
        offered = meanings(at(container, "Capability"))
        exact = bool(wanted & offered)
        if not exact and not any(narrows(o, w) for o in offered for w in wanted):
            continue
        given = {m: at(c, "Value") for c in children(at(container, "PropertySet"))
                 for m in meanings(at(c, "Value"))}
        missing = [f"{container['idShort']}: {meaning.rsplit('/', 1)[-1]} = {_shown(value)} is not offered"
                   for meaning, value in asked.items()
                   if meaning in given and (unit_of(given[meaning]) != unit_of(value) or not covers(given[meaning], value))]
        if missing:
            reasons += missing
            continue
        skills = [s for r in children(at(container, "CapabilityRelations")) if (s := resolve([module], r.get("second")))]
        if not skills:
            reasons.append(f"{container['idShort']}: no skill realizes it")
            continue
        found.append((not exact, not _built(skills[0]),
                      Offer(name, container["idShort"], skills[0]["idShort"], _built(skills[0]), _arguments(skills[0], asked))))
    if found:
        return min(found, key=lambda f: f[:2])[2]
    return reasons or [f"{name} offers no capability of the meaning {', '.join(sorted(wanted)) or '(none)'}"]


def _built(skill: dict) -> bool:
    deployment = at(skill, "Deployment")
    return deployment is None or deployment.get("value") != "Described"


def _arguments(skill: dict, asked: dict[str, dict]) -> dict[str, float]:
    """Each input of the skill's Start command given the required value of the same meaning."""
    found = {}
    for variable in children(at(skill, "Start", "Start")):
        for meaning in meanings(variable):
            value = number((asked.get(meaning) or {}).get("value"))
            if value is not None:
                found[variable["idShort"]] = value
    return found


# Where a product goes on the table -----------------------------------------------------------------

def station(envs: list[dict], module: str) -> tuple[float, float, float] | None:
    """Where a shuttle stands to hand the product to ``module`` (its AAS's idShort): its transfer
    point in the planar table's frame, (x, y, rz) in mm and degrees; None if the AASs do not place
    it on the table."""
    from modreg.frames import coordinates, relative
    env = next((e for e in envs if shell_of(e)["idShort"] == module), None)
    point = next((name for name, c in coordinates(env).items() if f"{MEANS}/TransferPoint" in meanings(c)), None) if env else None
    root = next(((shell_of(e)["idShort"], name) for e in envs for name, c in coordinates(e).items()
                 if f"{MEANS}/TableBase" in meanings(c)), None)
    if point is None or root is None:
        return None
    try:
        pose = relative(envs, root, (module, point))
    except (KeyError, ValueError, StopIteration):
        return None                                   # not placed on the table
    x, y, _ = pose.position
    rz = (pose.heading + 180.0) % 360.0 - 180.0
    return tuple(round(v, 3) + 0.0 for v in (x, y, rz))


def transport_request(x: float, y: float, rz: float) -> dict:
    """A required Transporting to (x, y, rz) on the table, as a product's required capability is
    written (IDTA 02020)."""
    def ref(value):
        return {"type": "ExternalReference", "keys": [{"type": "GlobalReference", "value": value}]}

    def target(name, value, unit):
        return {"modelType": "SubmodelElementCollection", "idShort": name,
                "semanticId": ref(f"{IDTA}/CapabilityDescription/PropertyContainer/1/0"), "value": [
                    {"modelType": "Property", "idShort": "Value", "valueType": "xs:double", "value": str(value),
                     "semanticId": ref(f"{IDTA}/CapabilityPropertyType/Property/1/0"),
                     "supplementalSemanticIds": [ref(f"{MEANS}/{name}")],
                     "qualifiers": [{"type": "Unit", "valueType": "xs:string", "value": unit, "kind": "ConceptQualifier"}]}]}
    return {"modelType": "SubmodelElementCollection", "idShort": "Transporting",
            "semanticId": ref(f"{IDTA}/CapabilityDescription/CapabilityContainer/1/0"), "value": [
                {"modelType": "Capability", "idShort": "Capability", "semanticId": ref(f"{IDTA}/CapabilityDescription/Capability/1/0"),
                 "supplementalSemanticIds": [ref(TRANSPORTING)]},
                {"modelType": "SubmodelElementCollection", "idShort": "PropertySet",
                 "semanticId": ref(f"{IDTA}/CapabilityDescription/PropertySet/1/0"),
                 "value": [target("TargetX", x, "mm"), target("TargetY", y, "mm"), target("TargetRz", rz, "deg")]}]}


def carries(module: dict) -> bool:
    """The resource offers Transporting: a shuttle."""
    return any(TRANSPORTING in meanings(at(c, "Capability"))
               for capability_set in children(submodel(module, "CapabilityDescription")) for c in children(capability_set))


def _shown(value: dict) -> str:
    return value.get("value") if "value" in value else f"{value.get('min')} to {value.get('max')}"
