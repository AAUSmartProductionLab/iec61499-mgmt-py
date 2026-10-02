"""The AAS type of an IEC 61499 module, on the lab's shared AAS model (``aas_model``).

``aas_model.ResourceTypeAAS`` is the lab's resource: an MQTT station with the skills Halt, Occupy
and Release and a location on the planar table. A module speaks OPC UA and nothing else, and what
makes it reconfigurable has no place there. ``ModuleTypeAAS`` is that resource with

- the MQTT defaults replaced by an (empty) OPC UA interface, and no default skills or mappings;
- per skill the elements reconfiguration needs (``ModuleSkill``): kind, contract or sequences,
  occupied equipment, the state data point and the implementing function block;
- Hierarchical Structures (the equipment) and Control Configuration (what runs on the controller)
  as submodels of their own.

A profile is the dump of such a model without what the type already says (``profile``); ``asset``
builds the model back from it and ``environment`` the AAS. ``TYPES`` names the types a profile may
be of, so the lab's MQTT stations go through the same code.
"""
from __future__ import annotations

import functools
import json
import typing
from typing import Dict, Optional

import aas_pydantic.aas_model
import aas_pydantic.convert_aas_instance

from aas_model.builder import deep_merge
from aas_model.constants import BASE_URL, DELEGATION_BASE
from aas_model.id_injector import inject_ids
from aas_model.resource_template import ResourceTypeAAS, nameplate, variables
from aas_model.resource_template.control_component_instance import ResourceControlComponentInstance
from aas_model.submodel_templates import (
    Aimc, AimcMappingConfigurations, DmpAssetInterfacesDescription, DmpOpcuaInterface, ExtendedSkill, ExtendedSkills,
    MqttInterface,
)
from aas_model.submodel_templates.parameters import Parameters
from aas_model.submodel_templates.variables import Variables
from aas_pydantic import (
    AAS, Property, ReferenceElement, Submodel, SubmodelElementCollection, convert_model_to_aas,
)
from pydantic import BaseModel
from pydantic_core import to_jsonable_python
from aas_pydantic.submodel_templates.control_component_instance import Parameter, Parameters as SkillParameters, Values
from aas_pydantic.submodel_templates.hierarchical_structures import ArcheType, EntryNode, HierarchicalStructures
from aas_pydantic.submodel_templates.nameplate import Nameplate
from basyx.aas import model as basyx
from basyx.aas.adapter.json import AASToJsonEncoder



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

SKILL = f"{BASE_URL}/ControlComponent/Skill"
CONFIGURATION = f"{BASE_URL}/ControlConfiguration"
RESOURCE_TEMPLATE = f"{BASE_URL}/aas/templates/resource"


# Skills: what reconfiguration needs to know about each ------------------------------------------

class ParameterValues(Values):
    """The values a skill parameter accepts: its range, default and unit."""
    Default: Optional[Property] = None
    Minimum: Optional[Property] = None
    Maximum: Optional[Property] = None
    Unit: Optional[Property] = None


class ModuleSkillParameter(Parameter):
    Values: ParameterValues = ParameterValues()


class ModuleSkillParameters(SkillParameters):
    Parameter: Dict[str, ModuleSkillParameter] = {}


class SkillContract(SubmodelElementCollection):
    """What a skill primitive needs before it starts, holds while it runs and reaches when it ends:
    conditions over the equipment's inputs, as the module spec states them."""
    semantic_id: str = f"{SKILL}/Contract/1/0"
    description: str = "Precondition, postcondition or duration, invariant and timeout of a skill primitive."
    Requires: Optional[Property] = None
    Ensures: Optional[Property] = None
    After: Optional[Property] = None
    Invariant: Optional[Property] = None
    Timeout: Optional[Property] = None


class StepBindings(SubmodelElementCollection):
    semantic_id: str = f"{SKILL}/Step/Bindings/1/0"
    description: str = "Values bound to the parameters of the step's skill: a constant, or the name of a parameter of the composite."
    Binding: Dict[str, Property] = {}


class SkillStep(SubmodelElementCollection):
    semantic_id: str = f"{SKILL}/Step/1/0"
    description: str = "One use of a skill in a sequence."
    Skill: ReferenceElement = ReferenceElement(
        semantic_id=f"{SKILL}/Step/Skill/1/0", description="The skill this step runs.")
    InstancePath: Optional[Property] = None
    Bindings: Optional[StepBindings] = None


class SkillSequence(SubmodelElementCollection):
    """The steps of a module level skill, in the order of their idShorts (Step01, Step02, ...)."""
    semantic_id: str = f"{SKILL}/Sequence/1/0"
    description: str = "A sequence of steps."
    Step: Dict[str, SkillStep] = {}


class SkillOccupies(SubmodelElementCollection):
    semantic_id: str = f"{SKILL}/Occupies/1/0"
    description: str = "The equipment (nodes of the Hierarchical Structures) the skill locks while it runs."
    Node: Dict[str, ReferenceElement] = {}


class SkillImplementation(SubmodelElementCollection):
    semantic_id: str = f"{SKILL}/Implementation/1/0"
    description: str = "The IEC 61499 function block that implements the skill."
    InstancePath: Optional[Property] = None
    FBType: Optional[Property] = None
    TypeHash: Optional[Property] = None


class ModuleSkill(ExtendedSkill):
    """A skill of a module: the lab's skill (native interface, delegated operation) plus what
    composing and checking skills needs. Every addition is optional."""
    Parameters: ModuleSkillParameters = ModuleSkillParameters()
    Kind: Optional[Property] = None                 # Primitive | Composite
    Contract: Optional[SkillContract] = None        # primitives
    Execute: Optional[SkillSequence] = None         # composites: what Start runs
    Stop: Optional[SkillSequence] = None            # composites: what Stop runs
    Occupies: Optional[SkillOccupies] = None
    StateReference: Optional[ReferenceElement] = None
    Implementation: Optional[SkillImplementation] = None


class ModuleSkills(ExtendedSkills):
    Skill: Dict[str, ModuleSkill] = {}


class ModuleControlComponentInstance(ResourceControlComponentInstance):
    Skills: ModuleSkills = ModuleSkills()


# Control Configuration: what runs on the controller -----------------------------------------------

class ControlRuntime(SubmodelElementCollection):
    semantic_id: str = f"{CONFIGURATION}/Runtime/1/0"
    description: str = "The runtime that executes the control program."
    Name: Property = Property(value="Eclipse 4diac FORTE")
    ManagementEndpoint: Property = Property()
    Resource: Property = Property(value="RES")


class ControlType(SubmodelElementCollection):
    semantic_id: str = f"{CONFIGURATION}/Type/1/0"
    description: str = "A function block type in use, with the hash the runtime reports for it."
    Name: Property = Property()
    Hash: Property = Property()


class ControlTypes(SubmodelElementCollection):
    semantic_id: str = f"{CONFIGURATION}/Types/1/0"
    description: str = "The function block types the running program uses."
    Type: Dict[str, ControlType] = {}


class ControlDifferences(SubmodelElementCollection):
    semantic_id: str = f"{CONFIGURATION}/Differences/1/0"
    description: str = "Where the running program differs from the one its source generates."
    Difference: Dict[str, Property] = {}


class ControlConfiguration(Submodel):
    """What runs on the module's controller and whether it is still what its source generates."""
    semantic_id: str = f"{BASE_URL}/ARSO/ControlConfiguration/1/0/Submodel"
    description: str = "The control program of the resource: runtime, source, synchronisation state and type hashes."
    Runtime: ControlRuntime = ControlRuntime()
    ModuleSpec: Property = Property()
    Target: Property = Property()
    Generator: Property = Property(value="modgen")
    ProgramDigest: Property = Property(
        description="SHA-256 of the program the module spec generates for the target (instances, types, connections, values).")
    SyncState: Property = Property(
        value="NotRead", description="InSync: the running program is the one the module spec generates; Drift: it "
        "differs (see Differences); NoProgram: the runtime has none; NotRead: described from the spec only.")
    ReadAt: Property = Property()
    Differences: ControlDifferences = ControlDifferences()
    Types: ControlTypes = ControlTypes()


# The module type ----------------------------------------------------------------------------------

class ModuleInterfaces(DmpAssetInterfacesDescription):
    """The interfaces of a module: one OPC UA server, no MQTT."""
    InterfaceTemplateForMQTT: Dict[str, MqttInterface] = {}
    InterfaceTemplateForOPCUA: Dict[str, DmpOpcuaInterface] = {"interface_opcua": DmpOpcuaInterface()}


def structure() -> HierarchicalStructures:
    return HierarchicalStructures(id_short="HierarchicalStructures", EntryNode=EntryNode(),
                                  ArcheType=ArcheType(value="OneDown"))


class ModuleTypeAAS(ResourceTypeAAS):
    """Resource AAS of an IEC 61499 module: OPC UA only, with its equipment and control program."""
    nameplate: Nameplate = nameplate()
    asset_interfaces_description: ModuleInterfaces = ModuleInterfaces(id_short="AssetInterfacesDescription")
    control_component_instance: ModuleControlComponentInstance = ModuleControlComponentInstance(
        id_short="ControlComponentInstance")
    variables: Variables = variables()
    parameters: Parameters = Parameters(id_short="Parameters")
    asset_interfaces_mapping_configuration: Aimc = Aimc(
        id_short="AssetInterfacesMappingConfiguration", MappingConfigurations=AimcMappingConfigurations(value=[]))
    hierarchical_structures: HierarchicalStructures = structure()
    control_configuration: ControlConfiguration = ControlConfiguration(id_short="ControlConfiguration")


TYPES: dict[str, type[ResourceTypeAAS]] = {"ResourceTypeAAS": ResourceTypeAAS, "ModuleTypeAAS": ModuleTypeAAS}
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


def profile(asset: ResourceTypeAAS, **build) -> dict:
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


def validated(profile: dict) -> ResourceTypeAAS:
    """The model a profile describes, as written (self references not filled in yet)."""
    data = {k: v for k, v in profile.items() if k not in BUILD_KEYS}
    aas_type = profile.get("aas_type", "ResourceTypeAAS")
    merged = deep_merge(defaults(aas_type, data), data)
    try:
        return TYPES[aas_type].model_validate(merged)
    except ValueError as e:
        raise ProfileError(str(e)) from e


def asset(profile: dict) -> ResourceTypeAAS:
    """The validated model of a profile, with ids and self references filled in."""
    model = validated(profile)
    inject_ids(model, delegation_base=profile.get("delegation_base") or DELEGATION_BASE)
    return model


def environment(model: ResourceTypeAAS, global_asset_id: str | None = None) -> dict:
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
