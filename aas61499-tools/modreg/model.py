"""The AAS types of the lab, as profiles: the resources as the resource ontology ARSO describes
them (a line, a module, a component), the product and the process, all from the lab's shared AAS
model (``aas_model``, pydantic). Their classes and templates are aas-model's (``Module``,
``Component``, ``ProductionSystem``, ``Product``, ``Process``); this module adds the profile: the
dump of such a model without what its type already says (``profile``), ``asset`` building the model
back from it and ``environment`` the AAS. ``TYPES`` names the types a profile may be of, so the lab's
MQTT stations, the modules and the products go through the same code.
"""
from __future__ import annotations

import copy
import functools
import json
import threading
import typing

import aas_pydantic.aas_model
import aas_pydantic.convert_aas_instance

from aas_model.constants import BASE_URL, INVOCATION_ORIGIN
from aas_model.id_injector import inject_ids
from aas_model.invocation_authoring import OPERATION_PATH, operation_path
from aas_model.process_template import Process
from aas_model.product_template import Product
from aas_model.resource_template import Resource
from aas_model.resource_template.modules import (                      # noqa: F401 (the types, here too)
    RESOURCE, Component, LocatedEntryNode, LocatedNode, LocatedStructures, Module, ModuleCapabilityContainer,
    ModuleCapabilityDescription, ModuleCapabilityRelations, ModuleCapabilitySet, ModuleConstraintSet,
    ModuleControlConfiguration, ModuleInterfaces, ModuleSkill, ModuleSkills, ProductionSystem, RealizedBySkill,
    SameAs, StatedProperty, StatedPropertySet, BasicConstraintContainer, structure,
)
from aas_model.submodel_templates import SkillOperation
from aas_pydantic import AAS, Qualifier, convert_model_to_aas
from aas_pydantic.convert_util import strip_temp_id_short_attributes
from basyx.aas import model as basyx
from basyx.aas.adapter.json import AASToJsonEncoder
from pydantic import BaseModel
from pydantic_core import to_jsonable_python


class _Typing:
    """``typing`` with the type hints of a class remembered. aas_pydantic resolves them again for
    every element it dumps, validates or converts, which makes the dump of a module take minutes
    (4 s for the lab's empty resource). The classes do not change after import, so once is enough."""

    def __init__(self):
        self._hints = functools.lru_cache(maxsize=None)(typing.get_type_hints)

    def get_type_hints(self, obj, **options):
        return self._hints(obj, **options)

    def __getattr__(self, name):
        return getattr(typing, name)


aas_pydantic.aas_model.typing = aas_pydantic.convert_aas_instance.typing = _Typing()


class _Once(threading.local):
    """aas_pydantic's serializer of an element dumps the element's children, and then once more to
    keep their own classes; every level does that again for what is below it, so a dump takes time
    exponential in the depth (10 s for a module). Within one dump an element is the same each time
    it is reached, so it is serialized once. Per thread: the registration service dumps in several."""

    def __init__(self, serialize):
        self.serialize, self.depth, self.done = serialize, 0, {}

    def __call__(self, element, handler):
        if id(element) in self.done:
            return self.done[id(element)]
        self.depth += 1
        try:
            data = self.serialize(element, handler)
        finally:
            self.depth -= 1
        if self.depth:
            self.done[id(element)] = data
        else:
            self.done.clear()
        return data


aas_pydantic.aas_model._serialize_element_containers = _Once(aas_pydantic.aas_model._serialize_element_containers)


ARSO = f"{BASE_URL}/ARSO"
SKILL = f"{BASE_URL}/skills"
RESOURCE_TEMPLATE = f"{BASE_URL}/aas/templates/resource"


DelegatedOperation = SkillOperation         # a field cannot be named like its type


def deep_merge(base: dict, override: dict) -> dict:
    """``override`` laid over ``base``: dictionaries merge key by key, anything else replaces."""
    merged = dict(base)
    for key, value in override.items():
        merged[key] = deep_merge(merged[key], value) if isinstance(value, dict) and isinstance(merged.get(key), dict) else value
    return merged


def invocations(node, aas_id_short: str, origin: str) -> None:
    """Fill in the origin of the operation delegation URLs of every Operation below ``node``: the
    DMP the AAS server delegates to (``origin``). Its path is the Operation's own (``operation_paths``)."""
    if isinstance(node, Qualifier):
        if node.type_ == "invocationDelegation" and node.value:
            node.value = (node.value.replace(INVOCATION_ORIGIN, origin.rstrip("/"))
                          .replace("{aas_id_short}", aas_id_short))
    elif isinstance(node, BaseModel):
        for field in type(node).model_fields:
            invocations(getattr(node, field), aas_id_short, origin)
    elif isinstance(node, dict):
        for value in node.values():
            invocations(value, aas_id_short, origin)
    elif isinstance(node, (list, tuple)):
        for value in node:
            invocations(value, aas_id_short, origin)


# A plain ``Resource`` is what the lab's stations export (aas-model authors them as its subtypes). The
# names before the types moved to aas-model (``ModuleTypeAAS``, ...) still read the profiles written then.
TYPES: dict[str, type[AAS]] = {"ResourceTypeAAS": Resource, "Module": Module, "Component": Component,
                               "ProductionSystem": ProductionSystem, "Product": Product, "Process": Process,
                               "ModuleTypeAAS": Module, "ComponentTypeAAS": Component,
                               "SystemTypeAAS": ProductionSystem, "ProductTypeAAS": Product}
# What a resource is, is its asset type; a component's ends in its kind (.../Component/LinearAxis):
# ``RESOURCE``, aas-model's.
# Keys of a profile that are about building the AAS, not part of it.
BUILD_KEYS = ("aas_type", "delegation_base", "global_asset_id")


class ProfileError(ValueError):
    """The profile does not describe an AAS of its type."""


def defaults(aas_type: str, profile: dict) -> dict:
    """The dump of the type alone, with the profile's identity."""
    try:
        cls = TYPES[aas_type]
    except KeyError:
        raise ProfileError(f"unknown AAS type {aas_type!r}; known: {', '.join(TYPES)}") from None
    if not profile.get("id_short"):
        raise ProfileError("a profile needs an id_short")
    stated = {"asset_type": profile["asset_type"]} if "asset_type" in profile else {}      # else the type's own
    return cls(id_short=profile["id_short"], id=profile.get("id") or f"{BASE_URL}/aas/{profile['id_short']}",
               **stated).model_dump(mode="json")


def class_defaults(cls: type) -> dict:
    """What validation gives each field of a class that is left out: the dumps of the field defaults."""
    if cls not in _DEFAULTS:
        found = {}
        for name, field in cls.model_fields.items():
            if not field.is_required():
                default = field.get_default(call_default_factory=True)
                found[name] = default.model_dump(mode="json") if isinstance(default, BaseModel) else to_jsonable_python(default)
        _DEFAULTS[cls] = found
    return _DEFAULTS[cls]


_DEFAULTS: dict[type, dict] = {}
SAME = object()
ELEMENT = (aas_pydantic.SubmodelElement, aas_pydantic.Submodel, AAS)


def item_type(cls: type, field: str):
    """The declared class of the children a container field holds; of a field that may hold one of
    several element classes (the generator makes a class per description of an element), that
    choice."""
    declared = getattr(cls, "item_type", None) if field == "value" else None
    annotation = aas_pydantic.aas_model._field_annotation(cls, field)
    return declared or aas_pydantic.aas_model._container_item_type(annotation) or (annotation if choice(annotation) else None)


def choice(declared) -> bool:
    """Whether a field may hold one of several element classes."""
    return typing.get_origin(declared) is typing.Union and len([a for a in typing.get_args(declared) if a is not type(None)]) > 1


def slim(node, dumped, known, declared=None, name=None):
    """What a reader cannot know of a dumped model: what differs from ``known``, the dump the reader
    starts from. That is the type's defaults where the type has the element, else the defaults of
    the element's class, which validation fills in again. An element named like its field or its
    key needs no idShort, and a child of a container keeps its ``modelType`` only if its class is
    not the declared one."""
    if isinstance(node, BaseModel) and choice(declared):
        # Which of the classes reads it back depends on what it states: what differs from its class,
        # and whatever tells the classes apart.
        own = class_defaults(type(node))
        apart = {f for f in own if len({repr(class_defaults(c).get(f)) for c in typing.get_args(declared)
                                        if c is not type(None)}) > 1}
        return {f: v for f, v in dumped.items()
                if (f in apart or v != own.get(f, SAME)) and not (f == "id_short" and v == name)}
    if isinstance(node, BaseModel):
        new = not isinstance(known, dict)
        start = class_defaults(type(node)) if new else known
        out = {}
        for field in type(node).model_fields:
            part = slim(getattr(node, field), dumped[field], start.get(field, SAME),
                        item_type(type(node), field) if isinstance(node, ELEMENT) else None, field)
            if part is not SAME and not (field == "id_short" and part == name):
                out[field] = part
        if "id" in out and "id_short" not in out:
            # Given an id alone, aas_pydantic names the element like it.
            out = {"id_short": dumped["id_short"], **out}
        if new and declared is not None and declared is not type(node):
            out["modelType"] = type(node).__name__
        if isinstance(node, aas_pydantic.Reference):
            out["type_"] = node.type_                # a field of the base class takes either kind
        return out if out or new else SAME
    if isinstance(node, dict) and any(isinstance(v, BaseModel) for v in node.values()):
        start = known if isinstance(known, dict) else {}
        if set(start) - set(node):
            raise ProfileError(f"a profile cannot take {sorted(set(start) - set(node))} away from its type")
        out = {k: part for k, v in node.items()
               if (part := slim(v, dumped[k], start.get(k, SAME), declared, k)) is not SAME}
        return out if out or not isinstance(known, dict) else SAME
    if dumped == known:
        return SAME
    if isinstance(node, (list, tuple)) and any(isinstance(v, BaseModel) for v in node):
        return [slim(v, d, SAME, declared) for v, d in zip(node, dumped)]
    return dumped


def difference(a, b, path="") -> str | None:
    """Where two dumps first differ."""
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if a.get(k, SAME) != b.get(k, SAME):
                return difference(a.get(k, SAME), b.get(k, SAME), f"{path}/{k}")
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            if x != y:
                return difference(x, y, f"{path}[{i}]")
    return None if a == b else f"{path}: {str(a)[:80]!r} became {str(b)[:80]!r}"


def profile(asset: AAS, **build) -> dict:
    """The asset as a profile: its dump without what its type and its elements' classes say anyway.
    Reading the profile has to give the asset back, which is checked here."""
    full = asset.model_dump(mode="json")
    aas_type = type(asset).__name__
    changed = slim(asset, full, defaults(aas_type, full))
    result = {"aas_type": aas_type, "id_short": asset.id_short, "id": asset.id,
              **({} if changed is SAME else changed), **{k: v for k, v in build.items() if v}}
    # What kind of resource it is, is not the type's to say (``defaults`` starts from what is stated).
    if full.get("asset_type") and full["asset_type"] != type(asset).model_fields["asset_type"].default:
        result["asset_type"] = full["asset_type"]
    lost = difference(full, validated(result).model_dump(mode="json"))
    if lost:
        raise ProfileError(f"the profile does not give the asset back; {lost}")
    return result


def validated(profile: dict) -> AAS:
    """The model a profile describes, as written (self references not filled in yet)."""
    # A copy: validation fills the dictionaries it is given with the elements it makes of them.
    data = copy.deepcopy({k: v for k, v in profile.items() if k not in BUILD_KEYS})
    aas_type = profile.get("aas_type", "ResourceTypeAAS")
    merged = deep_merge(defaults(aas_type, data), data)
    try:
        return TYPES[aas_type].model_validate(merged)
    except ValueError as e:
        raise ProfileError(str(e)) from e


def asset(profile: dict) -> AAS:
    """The validated model of a profile, with ids and self references filled in."""
    model = validated(profile)
    inject_ids(model)
    invocations(model, model.id_short, profile.get("delegation_base") or INVOCATION_ORIGIN)
    return model


def environment(model: AAS, global_asset_id: str | None = None) -> dict:
    """The AAS of a model: its shell and submodels as an AAS JSON environment. The shared model
    names the asset like the shell and calls it an instance; ``global_asset_id`` gives it its own
    id, and a type that states its ``ASSET_KIND`` its own kind."""
    store = convert_model_to_aas(model)
    # aas_pydantic keeps a list item's idShort in a Property of its own to read it back; nothing reads
    # it back here, and the DMP refuses an AIMC with elements it does not know.
    strip_temp_id_short_attributes(store)
    # json.dumps, not BaSyx's file writer: that one encodes in Python and takes seconds for a module.
    found = {"assetAdministrationShells": [o for o in store if isinstance(o, basyx.AssetAdministrationShell)],
             "submodels": [o for o in store if isinstance(o, basyx.Submodel)]}
    env = json.loads(json.dumps(found, cls=AASToJsonEncoder))
    with_units(env["submodels"])
    typed_qualifiers(env["submodels"])
    for sm in env["submodels"]:
        operation_paths(sm["id"], sm.get("submodelElements") or [])
    for shell in env["assetAdministrationShells"]:
        if global_asset_id:
            shell["assetInformation"]["globalAssetId"] = global_asset_id
        if getattr(model, "ASSET_KIND", None):
            shell["assetInformation"]["assetKind"] = model.ASSET_KIND
    return env


IEC61360 = "https://admin-shell.io/DataSpecificationTemplates/DataSpecificationIEC61360/3/0"


def with_units(element) -> None:
    """Every element with a ``Unit`` qualifier also states its unit the standard way, in an IEC 61360
    data specification, first among its data specifications (where readers such as the BaSyx web
    UI's capability matching look). aas-model writes its own data specifications, without units."""
    if isinstance(element, list):
        for item in element:
            with_units(item)
        return
    if not isinstance(element, dict):
        return
    unit = next((q.get("value") for q in element.get("qualifiers") or [] if q.get("type") == "Unit"), None)
    if unit and element.get("modelType") not in (None, "Submodel", "AssetAdministrationShell"):
        names = element.get("displayName") or [{"language": "en", "text": element.get("idShort", "")}]
        element["embeddedDataSpecifications"] = [{
            "dataSpecification": {"type": "ExternalReference", "keys": [{"type": "GlobalReference", "value": IEC61360}]},
            "dataSpecificationContent": {"modelType": "DataSpecificationIec61360", "preferredName": names, "unit": unit},
        }, *(element.get("embeddedDataSpecifications") or [])]
    for value in element.values():
        if isinstance(value, (list, dict)):
            with_units(value)


BOOLEAN_QUALIFIERS = ("CapabilityRoleQualifier/Required", "CapabilityRoleQualifier/Offered",
                      "CapabilityRoleQualifier/NotAssigned", "Derived")


def typed_qualifiers(element) -> None:
    """The capability role qualifiers are booleans (IDTA 02020). aas-model hands a qualifier's value
    to BaSyx uncast, which refuses "true" as xs:boolean, so the model keeps them as strings."""
    if isinstance(element, list):
        for item in element:
            typed_qualifiers(item)
    elif isinstance(element, dict):
        for qualifier in element.get("qualifiers") or []:
            if qualifier.get("type") in BOOLEAN_QUALIFIERS:
                qualifier["valueType"] = "xs:boolean"
        for value in element.values():
            if isinstance(value, (list, dict)):
                typed_qualifiers(value)


def operation_paths(submodel_id: str, elements: list, trail: str = "") -> None:
    """Fill in the path of the delegation URL of every Operation in ``elements``: where the AAS API
    invokes it, ``/submodels/{base64url(submodel id)}/submodel-elements/{idShortPath}/invoke``. The
    DMP serves exactly that path, so no two Operations share one."""
    for i, element in enumerate(elements):
        here = f"{trail}[{i}]" if "idShort" not in element else f"{trail}.{element['idShort']}" if trail else element["idShort"]
        if element.get("modelType") == "Operation":
            for qualifier in element.get("qualifiers") or []:
                if qualifier.get("type") == "invocationDelegation" and OPERATION_PATH in (qualifier.get("value") or ""):
                    qualifier["value"] = qualifier["value"].replace(OPERATION_PATH, operation_path(submodel_id, here))
        elif isinstance(element.get("value"), list):
            operation_paths(submodel_id, [e for e in element["value"] if isinstance(e, dict) and "modelType" in e], here)


def build(profile: dict) -> dict:
    """The AAS a profile describes."""
    return environment(asset(profile), profile.get("global_asset_id"))
