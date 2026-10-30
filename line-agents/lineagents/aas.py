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
- **Custody** (vocabulary 0.7): a resource that carries or holds a container has it from Receiving
  to Releasing. An offered capability's Pre constraints are checked against the state the call
  gives: the product's (HeldBy, as its agent sends it) and the resource's (Holding: it has this
  product; Occupancy: how many it has), a named operand being a value of the capability (Capacity).
  A constraint about a state nobody gives is not checked. What fails only on the resource's own
  changing state (Occupancy) is a refusal for now (busy), the rest for good. A capability no skill
  realizes whose Posts are about custody only (Receiving, Releasing) the agent carries out itself.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import base64
import functools
import json
import operator
import urllib.parse
import urllib.request

from modreg.plancheck import at, children, covers, number, resolve, semantic_ids, shell_of, unit_of

MEANS = "https://smartproductionlab.aau.dk/semantics"
MODULE_TYPE = "Resource/Module"          # the end of a module's assetType
SYSTEM_TYPE = "Resource/System"          # the end of a line's
TRANSPORTING = f"{MEANS}/Transporting"
RECEIVING, RELEASING = f"{MEANS}/Receiving", f"{MEANS}/Releasing"
HELD_BY, HOLDING, OCCUPANCY = f"{MEANS}/HeldBy", f"{MEANS}/Holding", f"{MEANS}/Occupancy"
CUSTODY = {HOLDING}                      # what a capability no skill realizes may change
IDTA = "https://admin-shell.io/idta"
COMPARE = {"=": operator.eq, "!=": operator.ne, "<": operator.lt, "<=": operator.le, ">": operator.gt, ">=": operator.ge}


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
    effects: dict[str, object] = field(default_factory=dict)     # what its Posts set, by meaning (not sent)

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


class Refusal(list):
    """Why a resource offers nothing; ``busy``: only because of its own state now, which changes."""
    busy = False


def constraints(container: dict) -> list[tuple[str, str, str, object]]:
    """An offered capability's constraints: (kind, the meaning of the property it is about, the
    operator, the operand: a value, or the value of the capability's property it names)."""
    from modplan.expression import parse
    props = {c["idShort"]: at(c, "Value") or {} for c in children(at(container, "PropertySet"))}
    found = []
    for record in children(at(container, "CapabilityRelations", "ConstraintSet")):
        kind = (at(record, "PropertyConditionalType") or {}).get("value")
        has = [r for r in children(at(record, "ConstraintPropertyRelations")) if r.get("second")]
        if kind is None or not has:
            continue
        expression = parse(at(record, "BasicConstraint")["value"], kind)
        about = next(iter(meanings(props.get(has[0]["second"]["keys"][-2]["value"]))), None)
        operand = _typed(props.get(expression.named)) if expression.named else expression.operand
        if about is not None:
            found.append((kind, about, expression.op, operand))
    return found


def unmet(container: dict, state: dict[str, object]) -> list[tuple[str, str]]:
    """The Pre constraints the state breaks: (meaning, as written). Those about a state not given
    are not checked."""
    found = []
    for kind, about, op, operand in constraints(container):
        if kind != "Pre" or about not in state or op not in COMPARE:
            continue
        try:
            holds = COMPARE[op](state[about], operand)
        except TypeError:
            holds = False
        if not holds:
            found.append((about, f"{about.rsplit('/', 1)[-1]} {op} {operand} (it is {state[about]})"))
    return found


def offer(module: dict, required: dict, state: dict[str, object] | None = None,
          changing: frozenset[str] = frozenset()) -> Offer | Refusal:
    """What the module offers for a required capability, or why it offers nothing. ``state``: what
    the Pre constraints are checked against, by meaning; ``changing``: those of its meanings that
    change by themselves (a refusal only for them is busy)."""
    name = shell_of(module)["idShort"]
    wanted = meanings(at(required, "Capability"))
    asked = required_values(required)
    reasons, found, waiting = Refusal(), [], []
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
            waiting.append(False)
            continue
        broken = unmet(container, state or {})
        if broken:
            reasons += [f"{container['idShort']} needs {text}" for _, text in broken]
            waiting.append(all(about in changing for about, _ in broken))
            continue
        effects = {about: operand for kind, about, op, operand in constraints(container) if kind == "Post" and op == "="}
        skills = [s for r in children(at(container, "CapabilityRelations")) if (s := resolve([module], r.get("second")))]
        if not skills and effects and set(effects) <= CUSTODY and _available(container):
            found.append((not exact, False, Offer(name, container["idShort"], "", True, effects=effects)))
            continue
        if not skills:
            reasons.append(f"{container['idShort']}: no skill realizes it")
            waiting.append(False)
            continue
        found.append((not exact, not _built(skills[0]),
                      Offer(name, container["idShort"], skills[0]["idShort"], _built(skills[0]), _arguments(skills[0], asked),
                            effects=effects)))
    if found:
        return min(found, key=lambda f: f[:2])[2]
    reasons.busy = bool(waiting) and all(waiting)
    if not reasons:
        reasons.append(f"{name} offers no capability of the meaning {', '.join(sorted(wanted)) or '(none)'}")
    return reasons


def _available(container: dict) -> bool:
    """Offered now, not only after a reconfiguration."""
    return not any(q.get("type") == "Availability" and q.get("value") == "AfterReconfiguration"
                   for q in (at(container, "Capability") or {}).get("qualifiers") or [])


def _typed(element: dict | None):
    """A property's value as its type says (None if it has none)."""
    text, kind = (element or {}).get("value"), (element or {}).get("valueType")
    if text is None:
        return None
    if kind == "xs:boolean":
        return str(text).lower() == "true"
    if kind == "xs:string":
        return text
    return number(text)


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


def _ref(value: str) -> dict:
    return {"type": "ExternalReference", "keys": [{"type": "GlobalReference", "value": value}]}


def request(capability: str, values: dict[str, tuple[float, str]] | None = None) -> dict:
    """A required capability (the name of its meaning) with values (name -> value, unit), as a
    product's required capability is written (IDTA 02020)."""
    def wanted(name, value, unit):
        return {"modelType": "SubmodelElementCollection", "idShort": name,
                "semanticId": _ref(f"{IDTA}/CapabilityDescription/PropertyContainer/1/0"), "value": [
                    {"modelType": "Property", "idShort": "Value", "valueType": "xs:double", "value": str(value),
                     "semanticId": _ref(f"{IDTA}/CapabilityPropertyType/Property/1/0"),
                     "supplementalSemanticIds": [_ref(f"{MEANS}/{name}")],
                     "qualifiers": [{"type": "Unit", "valueType": "xs:string", "value": unit, "kind": "ConceptQualifier"}]}]}
    found = [{"modelType": "Capability", "idShort": "Capability", "semanticId": _ref(f"{IDTA}/CapabilityDescription/Capability/1/0"),
              "supplementalSemanticIds": [_ref(f"{MEANS}/{capability}")]}]
    if values:
        found.append({"modelType": "SubmodelElementCollection", "idShort": "PropertySet",
                      "semanticId": _ref(f"{IDTA}/CapabilityDescription/PropertySet/1/0"),
                      "value": [wanted(name, value, unit) for name, (value, unit) in values.items()]})
    return {"modelType": "SubmodelElementCollection", "idShort": capability,
            "semanticId": _ref(f"{IDTA}/CapabilityDescription/CapabilityContainer/1/0"), "value": found}


def transport_request(x: float, y: float, rz: float) -> dict:
    """A required Transporting to (x, y, rz) on the table."""
    return request("Transporting", {"TargetX": (x, "mm"), "TargetY": (y, "mm"), "TargetRz": (rz, "deg")})


def state_element(values: dict[str, object]) -> dict:
    """A product's state (meaning -> value) as an interaction element of a call or a result."""
    def kind(value):
        return "xs:boolean" if isinstance(value, bool) else "xs:double" if isinstance(value, (int, float)) else "xs:string"
    return {"modelType": "SubmodelElementCollection", "idShort": "State", "value": [
        {"modelType": "Property", "idShort": meaning.rsplit("/", 1)[-1], "valueType": kind(value),
         "value": str(value).lower() if isinstance(value, bool) else str(value), "semanticId": _ref(meaning)}
        for meaning, value in values.items()]}


def state_of(elements: list[dict]) -> dict[str, object]:
    """The state among interaction elements, by meaning (empty if there is none)."""
    return {meaning: _typed(prop) for element in elements if element.get("idShort") == "State"
            for prop in children(element) for meaning in semantic_ids(prop)[:1]}


def _shown(value: dict) -> str:
    return value.get("value") if "value" in value else f"{value.get('min')} to {value.get('max')}"
