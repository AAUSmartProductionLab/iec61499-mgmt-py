"""The interface of a skill that was built on a running module, added to the module's AAS.

A skill that is described and then built online (``modsync reconfigure``) is in the Skills submodel,
but nothing in the AAS says yet how it is reached: no action of the interface calls its commands,
no property shows its state, no data point means it. All of that follows from the description by
the same rules a module's AAS is written by, so it is written here with the same code
(``profile.Describer``): what the module's control publishes for a module level skill is fixed by
the module rules.

``offered`` takes the module's AAS (an environment as JSON) and the module as its AAS describes it
(``modsync.desired.described``), and gives the AAS with, for each of the named skills:

- the actions of its commands and the properties of its state, error, parameters and results, and
  of each of its steps, in the Asset Interfaces Description;
- a data point for every one of those properties in Operational Data;
- the mappings from property to data point and from each command's Operation to its action;
- in the skill itself, the reference of each command to its action, and how its Operation is
  invoked. A command the description left out (Abort, Reset) is added: a built skill has all four.

``capabilities`` derives the module's offered capabilities anew from its skills (``modreg.derive``),
after a skill was built online or described in the skill editor.
"""
from __future__ import annotations

import base64
import copy

from modgen.spec import Capability as CapabilitySpec, CapabilityProperty, ModuleSpec
from modsync.aasjson import at, children, submodel

from . import model
from .derive import local, offers as derived_offers
from .model import ModuleTypeAAS
from .profile import OFFERED_SET, Describer, capability_description, put
from .projection import project, target


def add(holder: dict, elements: list[dict], key: str = "value") -> None:
    """Append the elements the holder does not have yet (by idShort)."""
    have = {e.get("idShort") for e in holder.setdefault(key, [])}
    holder[key] += [e for e in elements if e.get("idShort") not in have]


def targets(config: dict, which: str) -> list[str]:
    """What the sources or sinks of a mapping refer to: the last key of each reference."""
    single = which[:-1]
    return [at(entry, single)["value"]["keys"][-1]["value"] for entry in children(at(config, which))]


def feeds_data(config: dict) -> bool:
    """The mapping from the interface's properties to the data points (the others invoke an action)."""
    return any(key["value"] == "properties" for entry in children(at(config, "Sources"))
               for key in at(entry, "Source")["value"]["keys"])


def lua(config: dict) -> str:
    return base64.b64decode(at(config, "Transformation")["value"]).decode("utf-8")


def offered(module: dict, spec: ModuleSpec, skills: list[str]) -> dict:
    """The module's AAS with the interface of the module level ``skills`` (see the module docstring).
    ``spec``: the module as its AAS describes it, with its name and OPC UA root as the program
    states them."""
    shell = module["assetAdministrationShells"][0]
    interface = at(submodel(module, "AssetInterfacesDescription"), "interface_opcua")
    describer = Describer(spec, "", None, None, None, at(interface, "EndpointMetadata", "base")["value"])
    describer.module_id = shell["id"]
    asset = ModuleTypeAAS(id_short=shell["idShort"], id=shell["id"],
                          asset_type=shell["assetInformation"].get("assetType") or f"{model.RESOURCE}/Module",
                          derived_from=model.RESOURCE_TEMPLATE)
    for name in skills:
        put(asset.skills.Skill, name, describer.skill(name))
    describer.interface_and_data(asset)
    asset.asset_interfaces_mapping_configuration = describer.mappings()
    # The same way a module's AAS is built: profile, then the AAS it describes.
    built = model.build(model.profile(ModuleTypeAAS.model_validate(asset.model_dump()),
                                      global_asset_id=shell["assetInformation"].get("globalAssetId", "")))

    module = copy.deepcopy(module)
    for kind in ("actions", "properties"):
        add(at(submodel(module, "AssetInterfacesDescription"), "interface_opcua", "InteractionMetadata", kind),
            children(at(submodel(built, "AssetInterfacesDescription"), "interface_opcua", "InteractionMetadata", kind)))
    add(submodel(module, "OperationalData"), children(submodel(built, "OperationalData")), "submodelElements")

    held = at(submodel(module, "AssetInterfacesMappingConfiguration"), "MappingConfigurations")
    data = next(c for c in children(held) if feeds_data(c))
    invoked = {t for c in children(held) if not feeds_data(c) for t in targets(c, "Sinks")}
    for config in children(at(submodel(built, "AssetInterfacesMappingConfiguration"), "MappingConfigurations")):
        if not feeds_data(config):
            if not set(targets(config, "Sinks")) <= invoked:
                held["value"].append(config)
            continue
        fed = set(targets(data, "Sinks"))
        new = [i for i, name in enumerate(targets(config, "Sinks")) if name not in fed]
        for which in ("Sources", "Sinks"):
            at(data, which)["value"] += [children(at(config, which))[i] for i in new]
        # One more line of the transformation per property: it hands each source to its data point.
        keys = [targets(config, "Sources")[i] for i in new]
        text, end = lua(data), "\n    }\nend\n"
        if not text.endswith(end):
            raise ValueError("the mapping of the interface's properties has a transformation this tool did not write")
        text = text[:-len(end)] + "".join(f"\n        {key} = sources.{key}," for key in keys) + end
        at(data, "Transformation")["value"] = base64.b64encode(text.encode("utf-8")).decode("ascii")

    for name in skills:
        described, complete = at(submodel(module, "Skills"), name), at(submodel(built, "Skills"), name)
        for command in [c for c in children(complete) if c.get("modelType") == "SubmodelElementCollection" and at(c, "InterfaceReference")]:
            mine = at(described, command["idShort"])
            if mine is None:
                described["value"].append(command)            # Abort, Reset: every built skill has them
                continue
            if at(mine, "InterfaceReference") is None:
                mine["value"].insert(0, at(command, "InterfaceReference"))
            operation, invoking = at(mine, command["idShort"]), at(command, command["idShort"])
            if operation is not None and invoking is not None and invoking.get("qualifiers"):
                operation["qualifiers"] = invoking["qualifiers"]
    return module


def qualifiers(element: dict | None) -> dict[str, str]:
    return {q.get("type"): q.get("value") for q in (element or {}).get("qualifiers") or []}


def english(texts: list[dict] | None) -> str:
    return next((t.get("text", "") for t in texts or [] if t.get("language") == "en"), "")


def bare(element):
    """An element without its embedded data specifications, whose ids aas-model draws anew for
    every build."""
    if isinstance(element, dict):
        return {k: bare(v) for k, v in element.items() if k != "embeddedDataSpecifications"}
    return [bare(v) for v in element] if isinstance(element, list) else element


def stated_facts(description: dict | None) -> tuple[dict, dict, list[dict]]:
    """What a Capability Description states beyond the skills: per capability class (meaning ->
    (name, its facts)), the names its containers have (capability, skill element) -> idShort, and
    the containers written by hand (no Derived mark on the capability)."""
    stated, named, by_hand = {}, {}, []
    for box in children(at(description, OFFERED_SET)):
        capability = at(box, "Capability")
        if capability is None or not capability.get("supplementalSemanticIds"):
            continue
        iri = capability["supplementalSemanticIds"][0]["keys"][0]["value"]
        name = english(capability.get("displayName")) or local(iri)
        if qualifiers(capability).get("Derived") != "true":
            by_hand.append(box)
        for relation in children(at(box, "CapabilityRelations")):
            if relation.get("modelType") == "RelationshipElement" and relation.get("second"):
                named[(iri, str(target(relation["second"])))] = box["idShort"]
        facts = {}
        for container in children(at(box, "PropertySet")):
            value = at(container, "Value")
            if value is None or qualifiers(value).get("Derived") == "true":
                continue
            if value["modelType"] != "Range" and value.get("value") is None:
                continue                                  # a state its constraints are about, not a fact

            meaning = value["supplementalSemanticIds"][0]["keys"][0]["value"]
            unit = qualifiers(value).get("Unit")
            if value["modelType"] == "Range":
                facts[container["idShort"]] = CapabilityProperty(minimum=float(value["min"]), maximum=float(value["max"]),
                                                                 unit=unit, semantic_id=meaning)
            else:
                kind, text = value.get("valueType"), value.get("value")
                found = float(text) if kind == "xs:double" else text == "true" if kind == "xs:boolean" else text
                facts[container["idShort"]] = CapabilityProperty(value=found, unit=unit, semantic_id=meaning)
        about = english(capability.get("description"))
        old = stated.get(iri, (name, CapabilitySpec()))[1]
        stated[iri] = (name, CapabilitySpec(
            description=old.description or ("" if ", realized by " in about else about),
            properties={**old.properties, **facts}))
    return stated, named, by_hand


def capabilities(module: dict, components: list[dict]) -> dict:
    """The module's AAS with its offered capabilities derived anew from its skills and those of its
    components (``modreg.derive``): what a skill sets is replaced, the facts the description states
    for a capability are kept, a container keeps its name, a capability written by hand that no
    skill offers stays, and one a skill no longer offers goes. A skill described but not built
    offers its capability after a reconfiguration."""
    module = copy.deepcopy(module)
    old = next((s for s in module["submodels"] if s["idShort"] == "CapabilityDescription"), None)
    stated, named, by_hand = stated_facts(old)
    found = derived_offers(project([module, *components], structure=False))
    description = capability_description(found, stated, named)
    derived = {o.capability for o in found}
    kept = [box for box in by_hand if at(box, "Capability")["supplementalSemanticIds"][0]["keys"][0]["value"] not in derived]
    # The components' capabilities (a set per component) are not derived: they stay as they are.
    others = [s for s in children(old) if s.get("idShort") != OFFERED_SET]
    if description is None and not kept and not others:
        module["submodels"] = [s for s in module["submodels"] if s is not old]
        return module
    shell = module["assetAdministrationShells"][0]
    asset = ModuleTypeAAS(id_short=shell["idShort"], id=shell["id"],
                          asset_type=shell["assetInformation"].get("assetType") or f"{model.RESOURCE}/Module",
                          derived_from=model.RESOURCE_TEMPLATE)
    if description is not None:
        asset.capability_description = description
    lean = asset.model_copy(update={f: None for f in type(asset).model_fields
                                    if f != "capability_description" and hasattr(getattr(asset, f), "id_short")})
    model.inject_ids(lean)
    built = model.environment(lean)
    new = next((s for s in built["submodels"] if s["idShort"] == "CapabilityDescription"), None)
    if new is None:                     # nothing derived: what was written by hand and the components' sets
        new = copy.deepcopy(old)
        new["submodelElements"] = [s for s in children(new) if s.get("idShort") == OFFERED_SET and kept]
        if kept:
            at(new, OFFERED_SET)["value"] = []
    if kept:
        at(new, OFFERED_SET)["value"] += [box for box in kept if box["idShort"] not in {b["idShort"] for b in children(at(new, OFFERED_SET))}]
    have = {s.get("idShort") for s in children(new)}
    new["submodelElements"] += [s for s in others if s.get("idShort") not in have]
    if old is not None:
        new["id"] = old["id"]
        if bare(new) == bare(old):                     # only the ids aas-model draws anew differ
            return module
        module["submodels"] = [new if s is old else s for s in module["submodels"]]
    else:
        module["submodels"].append(new)
        shell.setdefault("submodels", []).append({"type": "ModelReference", "keys": [{"type": "Submodel", "value": new["id"]}]})
    return module

