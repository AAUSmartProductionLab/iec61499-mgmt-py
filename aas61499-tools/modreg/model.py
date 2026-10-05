"""The AAS type of an IEC 61499 module: the structure of the resource ontology (ARSO), written with
the lab's shared AAS model (``aas_model``, pydantic).

``aas_model.ResourceTypeAAS`` is the lab's resource: an MQTT station with a Control Component
Instance, Variables and a location. ``ModuleTypeAAS`` is a resource as ARSO describes it, for a
module that speaks OPC UA only:

- **Nameplate**, **Hierarchical Structures** (the equipment), **Asset Interfaces Description**
  (one OPC UA interface) and **Asset Interfaces Mapping Configuration**: the shared model's classes;
- **Skills** (ARSO's control component: Interfaces, Skills, Errors, and the module's procedures) instead of the Control
  Component Instance, **Operational Data** instead of Variables, **Parameters** and **Control
  Configuration**: ARSO's own submodels. Their classes are generated from the ontology by
  aas-model's generator (``modreg.generated``, see ``templates``); only what the ontology leaves
  open inside them is declared here.

A profile is the dump of such a model without what the type already says (``profile``); ``asset``
builds the model back from it and ``environment`` the AAS. ``TYPES`` names the types a profile may
be of, so the lab's MQTT stations go through the same code.
"""
from __future__ import annotations

import copy
import functools
import json
import typing
from typing import Dict, List, Optional

import aas_pydantic.aas_model
import aas_pydantic.convert_aas_instance

from aas_model.builder import deep_merge
from aas_model.constants import BASE_URL, DELEGATION_BASE
from aas_model.id_injector import inject_ids
from aas_model.resource_template import ResourceTypeAAS, nameplate
from aas_model.submodel_templates import (
    Aimc, AimcMappingConfigurations, DmpAssetInterfacesDescription, DmpOpcuaInterface, MqttInterface, SkillOperation,
)
from aas_pydantic import AAS, Property, ReferenceElement, SubmodelElementCollection, convert_model_to_aas
from aas_pydantic.submodel_templates.capability_description import CapabilityDescription
from aas_pydantic.submodel_templates.hierarchical_structures import ArcheType, EntryNode, HierarchicalStructures
from aas_pydantic.submodel_templates.nameplate import Nameplate
from basyx.aas import model as basyx
from basyx.aas.adapter.json import AASToJsonEncoder
from pydantic import BaseModel
from pydantic_core import to_jsonable_python

from .generated import skills
from .generated.control_configuration import ControlConfiguration
from .generated.operational_data import OperationalData
from .generated.parameters import Parameters


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

ARSO = f"{BASE_URL}/ARSO"
SKILL = f"{BASE_URL}/skills"
RESOURCE_TEMPLATE = f"{BASE_URL}/aas/templates/resource"


DelegatedOperation = SkillOperation         # a field cannot be named like its type


# What the ontology leaves open ---------------------------------------------------------------------
#
# The classes of ARSO's own submodels are generated (``modreg.generated``, see ``templates``). The
# ontology names some containers without declaring what is in them; a module fills those, and
# what it puts there is declared here.

class SkillContract(skills.Contract):
    """Conditions over the equipment's inputs, as the module spec states them."""
    Requires: Optional[Property] = None
    Ensures: Optional[Property] = None
    After: Optional[Property] = None
    Invariant: Optional[Property] = None
    Timeout: Optional[Property] = None


class StepBindings(SubmodelElementCollection):
    description: str = "Values bound to the parameters of the step's skill: a constant, or the name of a parameter of the composite."
    Binding: Dict[str, Property] = {}


class ModuleSkillStep(skills.SkillStep):
    """``Skill`` refers to the skill in this submodel, or names it (an external reference) if it
    only runs as a step and so is not listed. ``StateReference`` refers to the step's own State
    in the interface description, as a skill's does (its ErrorID, parameters and results are
    published beside it)."""
    Skill: ReferenceElement = ReferenceElement(description="The skill this step runs.")
    InstancePath: Optional[Property] = None
    Bindings: Optional[StepBindings] = None
    StateReference: Optional[ReferenceElement] = None


class ModuleSkillSequence(skills.SkillSequence):
    item_type: typing.ClassVar = ModuleSkillStep
    value: List[ModuleSkillStep] = []
    type_value_list_element: Optional[str] = "SubmodelElementCollection"


class SkillUses(skills.Uses):
    item_type: typing.ClassVar = ReferenceElement
    value: List[ReferenceElement] = []
    type_value_list_element: Optional[str] = "ReferenceElement"


class SkillOccupies(skills.Occupies):
    item_type: typing.ClassVar = ReferenceElement
    value: List[ReferenceElement] = []
    type_value_list_element: Optional[str] = "ReferenceElement"


class SkillImplementation(skills.Implementation):
    InstancePath: Optional[Property] = None
    FBType: Optional[Property] = None
    TypeHash: Optional[Property] = None


class ModuleSkill(skills.Skill):
    """The ontology's skill with a module's contract, sequences (Execute, Stop), lists and
    implementation, and the lab's delegated Operation as its Operation."""
    SkillOperation: Dict[str, DelegatedOperation] = {}
    Contract: Optional[SkillContract] = None
    Uses: Optional[SkillUses] = None
    SkillSequence: Dict[str, ModuleSkillSequence] = {}
    Occupies: Optional[SkillOccupies] = None
    Implementation: Optional[SkillImplementation] = None


class ModuleSkillSet(skills.Skills_2):
    Skill: Dict[str, ModuleSkill] = {}


class ModuleProcedures(SubmodelElementCollection):
    """What the module's state machine runs itself: a sequence of steps while Resetting and one
    while Stopping, published below ``/Procedures/<name>`` like the steps of a module level skill."""
    description: str = "The procedures the module's state machine runs while Resetting and while Stopping."
    Procedure: Dict[str, ModuleSkillSequence] = {}


class ModuleSkills(skills.Skills):
    Skills: ModuleSkillSet = ModuleSkillSet()
    Interfaces: skills.Interfaces = skills.Interfaces()
    Errors: skills.Errors = skills.Errors()
    # A module without procedures has none.
    Procedures: Optional[ModuleProcedures] = None


class ModuleControlConfiguration(ControlConfiguration):
    SyncState: Property = Property(value="NotRead")


# The module type ----------------------------------------------------------------------------------

class ModuleInterfaces(DmpAssetInterfacesDescription):
    """The interfaces of a module: one OPC UA server, no MQTT."""
    InterfaceTemplateForMQTT: Dict[str, MqttInterface] = {}
    InterfaceTemplateForOPCUA: Dict[str, DmpOpcuaInterface] = {"interface_opcua": DmpOpcuaInterface()}


def structure() -> HierarchicalStructures:
    return HierarchicalStructures(id_short="HierarchicalStructures", EntryNode=EntryNode(),
                                  ArcheType=ArcheType(value="OneDown"))


class ModuleTypeAAS(AAS):
    """Resource AAS of an IEC 61499 module, in ARSO's structure."""
    model_config = {"extra": "forbid"}

    nameplate: Nameplate = nameplate()
    hierarchical_structures: HierarchicalStructures = structure()
    asset_interfaces_description: ModuleInterfaces = ModuleInterfaces(id_short="AssetInterfacesDescription")
    skills: ModuleSkills = ModuleSkills(id_short="Skills")
    operational_data: OperationalData = OperationalData(id_short="OperationalData")
    asset_interfaces_mapping_configuration: Aimc = Aimc(
        id_short="AssetInterfacesMappingConfiguration", MappingConfigurations=AimcMappingConfigurations(value=[]))
    control_configuration: ModuleControlConfiguration = ModuleControlConfiguration(id_short="ControlConfiguration")
    # A module without skill parameters has no Parameters submodel.
    parameters: Optional[Parameters] = None
    capability_description: Optional[CapabilityDescription] = None


TYPES: dict[str, type[AAS]] = {"ResourceTypeAAS": ResourceTypeAAS, "ModuleTypeAAS": ModuleTypeAAS}
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
    return cls(id_short=profile["id_short"], id=profile.get("id") or f"{BASE_URL}/aas/{profile['id_short']}",
               asset_type=profile.get("asset_type", "")).model_dump(mode="json")


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
    """The declared class of the children a container field holds."""
    declared = getattr(cls, "item_type", None) if field == "value" else None
    return declared or aas_pydantic.aas_model._container_item_type(aas_pydantic.aas_model._field_annotation(cls, field))


def slim(node, dumped, known, declared=None, name=None):
    """What a reader cannot know of a dumped model: what differs from ``known``, the dump the reader
    starts from. That is the type's defaults where the type has the element, else the defaults of
    the element's class, which validation fills in again. An element named like its field or its
    key needs no idShort, and a child of a container keeps its ``modelType`` only if its class is
    not the declared one."""
    if isinstance(node, BaseModel):
        new = not isinstance(known, dict)
        start = class_defaults(type(node)) if new else known
        out = {}
        for field in type(node).model_fields:
            part = slim(getattr(node, field), dumped[field], start.get(field, SAME),
                        item_type(type(node), field) if isinstance(node, ELEMENT) else None, field)
            if part is not SAME and not (field == "id_short" and part == name):
                out[field] = part
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
    inject_ids(model, delegation_base=profile.get("delegation_base") or DELEGATION_BASE)
    return model


def environment(model: AAS, global_asset_id: str | None = None) -> dict:
    """The AAS of a model: its shell and submodels as an AAS JSON environment. The shared model
    names the asset like the shell; ``global_asset_id`` gives it its own id."""
    store = convert_model_to_aas(model)
    # json.dumps, not BaSyx's file writer: that one encodes in Python and takes seconds for a module.
    found = {"assetAdministrationShells": [o for o in store if isinstance(o, basyx.AssetAdministrationShell)],
             "submodels": [o for o in store if isinstance(o, basyx.Submodel)]}
    env = json.loads(json.dumps(found, cls=AASToJsonEncoder))
    if global_asset_id:
        for shell in env["assetAdministrationShells"]:
            shell["assetInformation"]["globalAssetId"] = global_asset_id
    return env


def build(profile: dict) -> dict:
    """The AAS a profile describes."""
    return environment(asset(profile), profile.get("global_asset_id"))
