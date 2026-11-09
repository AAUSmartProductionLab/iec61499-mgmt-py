"""Capability matching: does a resource offer the capability a product's step requires, and with
which skill. The one matcher of the lab: the skill service's ``POST /match`` (the web UI's Match
resources and Match and plan), the line's agents (``lineagents.aas.offer``), the plan check
(``plancheck.step_fits``) and the CIRP paper's evaluation (``cell/eval/q4.py``) all call it.

It reads Capability Descriptions (IDTA 02020) as an AAS server holds them, the meaning of a capability
and of a property in their supplemental semantic id, and answers match, mismatch or unknown, with
the reasons:

- **A property** (``compare``): the required one and the offered one of the same meaning have to be
  in one unit and of comparable value types, else the answer is unknown. A required value lies in an
  offered range, is one of the values an offered list takes, or equals the offered value; an offered
  value lies in a required range (at most so much fill error), or one of an offered list's does. A
  range against a range is unknown, and so is an offered property without a value: a state the
  capability's constraints are about. Numbers compare as numbers; strings, booleans and URIs as
  written.
- **A capability** (``evaluate``): each offered capability of the required meaning, every required
  property against the offered one of its meaning, a recipe parameter of that meaning in place of a
  required value. Mismatch if a property is outside, unknown if one cannot be compared or either
  capability states constraints (a ConstraintSet, a composition, a generalization: the planner's
  checker runs those in time, not this), else match. ``narrower``: an offered class that narrows the
  required one counts too (a module that fills bottom-up fills), after one of the class itself.
- **A resource** (``match``): per required capability the best of its offers (a match before an
  unknown before a mismatch, one offered now before one offered after a reconfiguration), whether
  all are offered now, and the skills a reconfiguration builds first (described, not built).
- **Planning** (``candidates``): the modules a skill can be planned on: where the matching found the
  capability offered by no skill yet, then those offering the required class or one it narrows (the
  vocabulary's lineage: Filling for BottomUpFilling); ``values``: what the planner is asked with.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
import functools
import math
from typing import Callable, Iterable

from modsync.aasjson import at, children

IDTA = "https://admin-shell.io/idta"
DESCRIPTION = f"{IDTA}/SubmodelTemplate/CapabilityDescription/1/0"
LAB = "https://smartproductionlab.aau.dk/semantics/"
# The first pharma demo's names for classes of the lab's vocabulary (the web UI's examples).
LEGACY = "https://smartproductionlab.aau.dk/demo/pharma/semantics/"
LEGACY_NAMES = {"Unpacking", "Loading", "Filling", "Stoppering", "Capping", "Inspection", "Unloading", "Packing",
                "ContainerType", "GraspDiameter", "FillVolume", "AbsoluteFillError", "StopperDiameter", "CapDiameter",
                "InspectionMethod"}
NUMERIC = {"xs:double", "xs:float", "xs:decimal", "xs:integer", "xs:int", "xs:long", "xs:short", "xs:byte",
           "xs:unsignedLong", "xs:unsignedInt", "xs:unsignedShort", "xs:unsignedByte", "xs:nonNegativeInteger",
           "xs:positiveInteger"}
TEXT = {"xs:string", "xs:boolean", "xs:anyURI"}
DATA = {"Property", "Range", "SubmodelElementList"}
NOW, AFTER = "Now", "AfterReconfiguration"
RANK = {"match": 0, "unknown": 1, "mismatch": 2}
CONSTRAINING = ("ConstraintSet", "ComposedOfSet", "GeneralizedBySet")
CONSTRAINED = "Additional constraints need evaluation"


def idta(name: str) -> str:
    """The semantic id of an element of the Capability Description (IDTA 02020)."""
    return f"{IDTA}/CapabilityDescription/{name}/1/0"


# Reading ------------------------------------------------------------------------------------------

def canonical(meaning: str) -> str:
    """A meaning in the lab's vocabulary: the first demo's names of its classes are mapped onto it;
    any other namespace stays as it is."""
    name = meaning[len(LEGACY):] if meaning.startswith(LEGACY) else None
    return LAB + name if name in LEGACY_NAMES else meaning


def local(meaning: str) -> str:
    """A meaning's local name: its class in the vocabulary (BottomUpFilling)."""
    return canonical(meaning).rstrip("/").rsplit("/", 1)[-1]


def semantic_id(element: dict | None) -> str:
    keys = ((element or {}).get("semanticId") or {}).get("keys") or []
    return str(keys[0].get("value") or "") if len(keys) == 1 else ""


def meanings(element: dict | None) -> list[str]:
    """What an element means: its supplemental semantic ids (each a reference of one key)."""
    return [canonical(str(ref["keys"][0]["value"])) for ref in (element or {}).get("supplementalSemanticIds") or []
            if len(ref.get("keys") or []) == 1 and ref["keys"][0].get("value")]


def english(element: dict | None) -> str:
    return next((str(t.get("text") or "") for t in (element or {}).get("displayName") or [] if t.get("language") == "en"), "")


def number(value) -> float | None:
    """A value as a number, None if it is not one."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def finite(value: str) -> float | None:
    found = number(value) if str(value).strip() else None
    return found if found is not None and math.isfinite(found) else None


def unit_of(element: dict) -> str | None:
    """An element's unit: its ``Unit`` qualifier, else its IEC 61360 data specification."""
    for qualifier in element.get("qualifiers") or []:
        if qualifier.get("type") == "Unit":
            return qualifier.get("value")
    for spec in element.get("embeddedDataSpecifications") or []:
        if spec.get("dataSpecificationContent", {}).get("unit"):
            return spec["dataSpecificationContent"]["unit"]
    return None


def _text(value) -> str:
    return "" if value is None else str(value)


@dataclass
class Property:
    """A property of a capability: a value, a range, or the values it takes (a list), in a unit."""
    name: str
    meaning: str
    unit: str = ""
    value_type: str = ""
    kind: str = "value"                  # value, range or values
    value: str = ""
    min: str = ""
    max: str = ""
    values: list[str] = field(default_factory=list)

    @classmethod
    def read(cls, element: dict, name: str = "") -> Property:
        """A Property, Range or SubmodelElementList of a property container (``name``: the container's)."""
        kind = {"Range": "range", "SubmodelElementList": "values"}.get(element.get("modelType"), "value")
        items = [str(i["value"]) for i in element.get("value") or [] if isinstance(i, dict) and i.get("value") is not None]
        return cls(english(element) or name or str(element.get("idShort") or ""), next(iter(meanings(element)), ""),
                   unit_of(element) or "", str(element.get("valueTypeListElement" if kind == "values" else "valueType") or ""),
                   kind, _text(element.get("value")) if kind == "value" else "", _text(element.get("min")),
                   _text(element.get("max")), items if kind == "values" else [])

    def shown(self) -> str:
        if self.kind == "range":
            return f"{self.min}–{self.max}"
        return f"one of {', '.join(self.values)}" if self.kind == "values" else self.value

    def json(self) -> dict:
        """As the web UI holds a property (CapabilityProperty)."""
        return {"name": self.name, "semanticId": self.meaning, "unit": self.unit, "dataType": self.value_type,
                "kind": self.kind, "value": self.value, "min": self.min, "max": self.max,
                **({"values": self.values} if self.kind == "values" else {})}


def properties(container: dict | None) -> list[Property]:
    """The properties a capability container states: the data element of each property container of
    its property sets."""
    return [Property.read(element, english(item) or str(item.get("idShort") or ""))
            for held in children(container) if semantic_id(held) == idta("PropertySet")
            for item in children(held) if semantic_id(item) == idta("PropertyContainer")
            for element in children(item) if element.get("modelType") in DATA]


@dataclass
class Capability:
    """A capability as a Capability Description states it: required by a product, offered by a
    resource (or by one of its components: NotAssigned)."""
    name: str
    meanings: list[str]
    properties: list[Property] = field(default_factory=list)
    constrained: bool = False                # it states constraints, a composition or a generalization
    role: str = "NotAssigned"
    availability: str = NOW                  # AfterReconfiguration: its skill is described, not built
    realized_by: list[dict] = field(default_factory=list)      # model references to the skills
    aas_id: str = ""
    reference: dict | None = None            # model reference to its Capability element
    container: dict | None = field(default=None, repr=False, compare=False)

    def json(self) -> dict:
        """As the web UI holds a capability (CapabilityDescription)."""
        return {"name": self.name, "reference": self.reference, "aasId": self.aas_id, "role": self.role,
                "availability": self.availability, "semanticIds": self.meanings,
                "realizedBy": self.realized_by, "properties": [p.json() for p in self.properties],
                "hasConstraints": self.constrained}


def _keys(reference: dict | None) -> list[str]:
    return [str(k.get("value")) for k in (reference or {}).get("keys") or []]


def read(container: dict, aas_id: str = "", submodel: str = "", held_in: str = "") -> Capability | None:
    """The capability of a capability container (None if it holds none); ``aas_id``, ``submodel``
    (its id) and ``held_in`` (its capability set) say where it is, for the reference to it."""
    capability = next((c for c in children(container) if c.get("modelType") == "Capability"
                       and semantic_id(c) == idta("Capability")), None)
    if capability is None:
        return None
    marks = capability.get("qualifiers") or []
    roles = [role for role in ("Required", "Offered", "NotAssigned")
             if any(semantic_id(q) == idta(f"CapabilityRoleQualifier/{role}") and q.get("valueType") == "xs:boolean"
                    and str(q.get("value")).lower() in ("true", "1") for q in marks)]
    reference = {"type": "ModelReference", "keys": [
        {"type": "Submodel", "value": submodel}, {"type": "SubmodelElementCollection", "value": held_in},
        {"type": "SubmodelElementCollection", "value": str(container.get("idShort") or "")},
        {"type": "Capability", "value": str(capability.get("idShort") or "")}]}
    relations = [r for held in children(container) if semantic_id(held) == idta("CapabilityRelations") for r in children(held)]
    # A skill realizes it when the relation's first is this capability (or names none).
    realized = [r["second"] for r in relations if r.get("modelType") == "RelationshipElement" and r.get("second")
                and semantic_id(r) == idta("CapabilityRealizedBy") and _keys(r.get("first")) in ([], _keys(reference))]
    return Capability(
        english(capability) or english(container) or str(container.get("idShort") or capability.get("idShort") or ""),
        meanings(capability), properties(container),
        any(semantic_id(r) in {idta(name) for name in CONSTRAINING} for r in relations),
        roles[0] if len(roles) == 1 else "NotAssigned",
        AFTER if any(q.get("type") == "Availability" and q.get("value") == AFTER for q in marks) else NOW,
        realized, aas_id, reference, container)


def capabilities(env: dict) -> list[Capability]:
    """Every capability of an AAS (an environment: its shell and submodels) in its Capability
    Description, in their order."""
    shell = (env.get("assetAdministrationShells") or [{}])[0]
    return [found for held in env.get("submodels") or [] if semantic_id(held) == DESCRIPTION
            for capability_set in children(held) if semantic_id(capability_set) == idta("CapabilitySet")
            for container in children(capability_set) if semantic_id(container) == idta("CapabilityContainer")
            if (found := read(container, str(shell.get("id") or ""), str(held.get("id") or ""),
                              str(capability_set.get("idShort") or ""))) is not None]


def offered(env: dict) -> list[Capability]:
    """The capabilities an AAS offers (role Offered)."""
    return [c for c in capabilities(env) if c.role == "Offered"]


def required(reference: dict | None, envs: list[dict], name: str = "") -> Capability:
    """The capability a requirement refers to: a model reference to a capability (or its container)
    in one of the environments, or an external reference naming its meaning alone. Unresolved, it
    has no meaning."""
    keys = (reference or {}).get("keys") or []
    if (reference or {}).get("type") == "ExternalReference":
        meaning = canonical(str(keys[0].get("value"))) if len(keys) == 1 and keys[0].get("value") else ""
        return Capability(name or local(meaning), [meaning] if meaning else [])
    held = next((s for env in envs for s in env.get("submodels") or [] if keys and s.get("id") == keys[0].get("value")), None)
    element = at(held, *_keys(reference)[1:]) if held is not None else None
    if element is not None and element.get("modelType") == "Capability":
        element = at(held, *_keys(reference)[1:-1])
    owner = next((env for env in envs if held in (env.get("submodels") or [])), {})
    shell = (owner.get("assetAdministrationShells") or [{}])[0]
    found = read(element, str(shell.get("id") or ""), str(held.get("id") or ""), _keys(reference)[1]) if element and len(keys) > 2 else None
    if found is None:
        return Capability(name, [])
    return replace(found, name=name or found.name)


# Comparing --------------------------------------------------------------------------------------

@dataclass
class Check:
    """A required property against the offered one: match, mismatch or unknown, and why. ``why`` of
    an unknown: undescribed (the offer says nothing about it), state (it offers no value), type,
    unit, invalid, rule (no rule compares the two) or recipe (the recipe's parameter does not fit)."""
    name: str
    status: str
    detail: str
    why: str = ""

    @property
    def reason(self) -> str:
        return f"{self.name}: {self.detail}"


def compare(required: Property, offered: Property | None) -> Check:
    """A required property against the offered property of its meaning (see the module's text)."""
    def unknown(why: str, detail: str) -> Check:
        return Check(required.name, "unknown", detail, why)
    if not required.meaning or offered is None:
        return unknown("undescribed", "property not described by the station")
    if (offered.kind == "value" and not offered.value.strip()) or (offered.kind == "values" and not offered.values):
        return unknown("state", "a state the capability's constraints are about, not a value it offers")
    if not required.value_type or not offered.value_type:
        return unknown("type", "unsupported property type")
    if required.unit != offered.unit:
        return unknown("unit", "units differ; conversion has not been verified")
    kinds = (required.kind, offered.kind)
    if required.value_type in NUMERIC and offered.value_type in NUMERIC:
        if kinds in (("value", "range"), ("range", "value")):
            value, low, high = ((required.value, offered.min, offered.max) if kinds[0] == "value"
                                else (offered.value, required.min, required.max))
            values = [finite(value), finite(low), finite(high)]
            if None in values or values[1] > values[2]:
                return unknown("invalid", "invalid numeric value or range")
            matches = values[1] <= values[0] <= values[2]
        elif kinds in (("value", "value"), ("value", "values")):
            given = [finite(v) for v in (offered.values if kinds[1] == "values" else [offered.value])]
            if finite(required.value) is None or None in given:
                return unknown("invalid", "invalid numeric value")
            matches = finite(required.value) in given
        elif kinds == ("range", "values"):
            given, low, high = [finite(v) for v in offered.values], finite(required.min), finite(required.max)
            if None in (*given, low, high) or low > high:
                return unknown("invalid", "invalid numeric value or range")
            matches = any(low <= v <= high for v in given)
        else:
            return unknown("rule", "range-to-range constraints require an explicit comparison rule" if kinds == ("range", "range")
                           else f"no rule compares a required {required.kind} with an offered {offered.kind}")
    else:
        if required.value_type != offered.value_type or required.value_type not in TEXT or kinds not in (("value", "value"), ("value", "values")):
            return unknown("type", "unsupported datatype comparison")
        matches = required.value in (offered.values if kinds[1] == "values" else [offered.value])
    need = f"{required.min}–{required.max}" if required.kind == "range" else required.value
    return Check(required.name, "match" if matches else "mismatch",
                 f"required {need}, offered {offered.shown()} {required.unit}".strip())


@dataclass
class Parameter:
    """A parameter of the product's recipe: it gives a required value of its meaning."""
    name: str
    meanings: list[str]
    value: str
    unit: str = ""
    value_type: str = ""

    @classmethod
    def from_json(cls, item: dict) -> Parameter:
        """As the web UI holds one (PlanParameter)."""
        return cls(str(item.get("name") or ""), [canonical(str(m)) for m in item.get("semanticIds") or []],
                   _text(item.get("value")), str(item.get("unit") or ""), str(item.get("dataType") or ""))


def compatible(a: str, b: str) -> bool:
    return a == b or (a in NUMERIC and b in NUMERIC)


def effective(prop: Property, parameters: Iterable[Parameter] = ()) -> Property | Check:
    """A required value as the recipe gives it: the one parameter of its meaning in its place, in its
    unit and of a compatible type (a Check if that is not so). A range is a tolerance: it stays."""
    if prop.kind != "value":
        return prop
    sources = [p for p in parameters if prop.meaning in p.meanings]
    if len(sources) > 1 or (sources and (sources[0].unit != prop.unit or not compatible(sources[0].value_type, prop.value_type))):
        return Check(prop.name, "unknown", "recipe association is ambiguous or has incompatible type/units", "recipe")
    return replace(prop, value=sources[0].value) if sources else prop


@functools.cache
def _vocabulary():
    from modplan.vocabulary import Vocabulary
    return Vocabulary()


@functools.cache
def lineage(name: str) -> tuple[str, ...]:
    """A capability class and the classes of the lab's vocabulary it narrows, nearest first
    (BottomUpFilling, Filling)."""
    return tuple(_vocabulary().lineage(name))


def narrows(offered: str, wanted: str) -> bool:
    """The class ``offered`` narrows ``wanted`` (both meanings in the lab's vocabulary)."""
    return (offered != wanted and offered.startswith(LAB) and wanted.startswith(LAB)
            and local(wanted) in lineage(local(offered)))


@dataclass
class Candidate:
    """An offered capability against a requirement: its status, each property's check, whether a
    constraint is left to evaluate, and whether it is of the required class (not a narrower one)."""
    capability: Capability
    status: str
    checks: list[Check]
    constrained: bool = False
    exact: bool = True

    @property
    def reasons(self) -> list[str]:
        return [c.reason for c in self.checks] + ([CONSTRAINED] if self.constrained else [])

    @property
    def fits(self) -> bool:
        """Every required property is met (constraints are not evaluated here)."""
        return all(c.status == "match" for c in self.checks)

    def rank(self) -> tuple:
        """The better one first: by status, of the required class, offered now."""
        return RANK[self.status], not self.exact, self.capability.availability != NOW


def evaluate(requirement: Capability, offers: Iterable[Capability], parameters: Iterable[Parameter] = (),
             narrower: bool = False) -> list[Candidate]:
    """Each offered capability of the required meaning (``narrower``: or of a class narrowing it)
    against the requirement, in their order: the best is ``min(found, key=Candidate.rank)``."""
    parameters, found = list(parameters), []
    for offer in offers:
        exact = bool(set(offer.meanings) & set(requirement.meanings))
        if not exact and not (narrower and any(narrows(o, w) for o in offer.meanings for w in requirement.meanings)):
            continue
        checks = []
        for prop in requirement.properties:
            given = effective(prop, parameters)
            checks.append(given if isinstance(given, Check)
                          else compare(given, next((p for p in offer.properties if p.meaning == prop.meaning), None)))
        constrained = requirement.constrained or offer.constrained
        status = ("mismatch" if any(c.status == "mismatch" for c in checks) else
                  "unknown" if constrained or any(c.status == "unknown" for c in checks) else "match")
        found.append(Candidate(offer, status, checks, constrained, exact))
    return found


# Resources and planning ---------------------------------------------------------------------------

@dataclass
class Match:
    """How one resource answers a step's required capabilities (the web UI's CapabilityMatch)."""
    aas_id: str
    status: str
    reasons: list[str]
    capabilities: list[Capability]
    availability: str
    reconfigure: list[str]

    def json(self) -> dict:
        return {"aasId": self.aas_id, "status": self.status, "reasons": self.reasons,
                "capabilities": [c.json() for c in self.capabilities], "availability": self.availability,
                "reconfigure": self.reconfigure}


def match(requirements: list[Capability], resources: Iterable[dict], parameters: Iterable[Parameter] = (),
          narrower: bool = False) -> list[Match]:
    """How each resource that offers a capability answers the requirements: each one has to be met by
    one complete offered capability of the resource, its properties included (none: no match)."""
    if not requirements:
        return []
    parameters, found = list(parameters), []
    for env in resources:
        offers = offered(env)
        if not offers:
            continue
        reasons, chosen, statuses = [], [], set()
        for requirement in requirements:
            if not requirement.meanings:
                reasons.append(f"{requirement.name}: unresolved requirement")
                statuses.add("unknown")
                continue
            ranked = evaluate(requirement, offers, parameters, narrower)
            if not ranked:
                reasons.append(f"{requirement.name}: capability not offered")
                statuses.add("mismatch")
                continue
            best = min(ranked, key=Candidate.rank)
            chosen.append(best.capability)
            reasons += best.reasons
            if best.capability.availability == AFTER:
                reasons.append(f"{requirement.name}: offered after a reconfiguration (the skill is described, not built yet)")
            statuses.add(best.status)
        later = [c for c in chosen if c.availability == AFTER]
        found.append(Match(
            offers[0].aas_id, "mismatch" if "mismatch" in statuses else "unknown" if "unknown" in statuses else "match",
            reasons, chosen, AFTER if later else NOW,
            list(dict.fromkeys(k for c in later for ref in c.realized_by if (k := (_keys(ref) or [""])[-1])))))
    return found


def candidates(requirement: Capability, matches: list[Match], resources: Iterable[dict],
               lineage_of: Callable[[str], Iterable[str]] = lineage) -> list[str]:
    """The AASs a skill for the requirement can be planned on: those where the matching found its
    capability offered by no skill yet (a plan realizes it), then those offering the required class
    or one it narrows (the vocabulary's lineage: a module offering Filling for BottomUpFilling)."""
    plannable = [m.aas_id for m in matches if m.status != "mismatch" and any(not c.realized_by for c in m.capabilities)]
    classes = set(lineage_of(local(requirement.meanings[0]))) if requirement.meanings else set()
    broader = []
    for env in resources:
        offers = offered(env)
        if any(local(m) in classes for o in offers for m in o.meanings):
            broader.append(offers[0].aas_id)
    return list(dict.fromkeys(plannable + broader))


def typed(value: str, value_type: str = "") -> float | str | None:
    """A value as the planner takes it: a number for a numeric type (or none stated), else the text;
    None for no value."""
    if not str(value).strip():
        return None
    found = finite(value)
    if value_type in NUMERIC:
        return found
    return found if found is not None and not value_type else str(value)


def values(requirement: Capability, parameters: Iterable[Parameter] = ()) -> dict[str, float | str]:
    """The values a requirement is planned and checked with, by the local name of each meaning: its
    properties' values, and the recipe's parameters in their place (as the matching takes them)."""
    found = {}
    for prop in requirement.properties:
        value = typed(prop.value, prop.value_type) if prop.kind == "value" and prop.meaning else None
        if value is not None:
            found[local(prop.meaning)] = value
    for parameter in parameters:
        value = typed(parameter.value, parameter.value_type)
        for meaning in parameter.meanings if value is not None else []:
            found[local(meaning)] = value
    return found
