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

``described_skill`` describes a new module level skill in the module's AAS as the skill editor saves
one (a planned skill, ``modplan``): its parameters and steps, not built (Deployment Described), and
no interface yet; ``modsync reconfigure`` builds it and ``modsync record`` gives it its interface.
"""
from __future__ import annotations

import base64
import copy

from aas_model.constants import BASE_URL
from modgen.spec import Capability as CapabilitySpec, CapabilityProperty, Composite, ModuleSpec
from modsync.aasjson import at, children, submodel
from modsync.described import described

from . import model
from .derive import Offer, Property, local, offers as derived_offers
from .model import Module
from aas_model.submodel_templates.arso import skills as arso
from .profile import OFFERED_SET, Describer, capability_description, prop, put
from .projection import project, target


def add(holder: dict, elements: list[dict], key: str = "value") -> None:
    """Append the elements the holder does not have yet (by idShort)."""
    have = {e.get("idShort") for e in holder.setdefault(key, [])}
    holder[key] += [e for e in elements if e.get("idShort") not in have]


def targets(config: dict, which: str) -> list[tuple[str, ...]]:
    """What the sources or sinks of a mapping refer to: the keys of each reference below its submodel
    (an action's input is the action's own: every one is called ``input``)."""
    single = which[:-1]
    return [tuple(k["value"] for k in at(entry, single)["value"]["keys"][1:]) for entry in children(at(config, which))]


def feeds_data(config: dict) -> bool:
    """A mapping from the interface's properties to a time series (the others invoke an action)."""
    return any(key["value"] == "properties" for entry in children(at(config, "Sources"))
               for key in at(entry, "Source")["value"]["keys"])


def series_of_mapping(config: dict) -> tuple[str, ...]:
    """The series a mapping writes rows to: the group and series of its sink's segment."""
    return tuple(k["value"] for entry in children(at(config, "Sinks")) for k in at(entry, "Sink")["value"]["keys"][1:3])


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
    asset = Module(id_short=shell["idShort"], id=shell["id"],
                          asset_type=shell["assetInformation"].get("assetType") or f"{model.RESOURCE}/Module",
                          derived_from=model.RESOURCE_TEMPLATE)
    for name in skills:
        put(asset.skills.Skill, name, describer.skill(name))
    describer.interface_and_data(asset)
    asset.asset_interfaces_mapping_configuration = describer.mappings()
    # The same way a module's AAS is built: profile, then the AAS it describes.
    built = model.build(model.profile(Module.model_validate(asset.model_dump()),
                                      global_asset_id=shell["assetInformation"].get("globalAssetId", "")))

    module = copy.deepcopy(module)
    for kind in ("actions", "properties"):
        add(at(submodel(module, "AssetInterfacesDescription"), "interface_opcua", "InteractionMetadata", kind),
            children(at(submodel(built, "AssetInterfacesDescription"), "interface_opcua", "InteractionMetadata", kind)))
    # The new skills' values are series of their own (State/<Skill>): those the module has not got yet
    # are added, each with the mapping that writes its rows.
    variables = submodel(module, "Variables")
    for group in children(submodel(built, "Variables")):
        mine = at(variables, group["idShort"])
        if mine is None:
            variables.setdefault("submodelElements", []).append(group)
        else:
            add(mine, children(group))

    held = at(submodel(module, "AssetInterfacesMappingConfiguration"), "MappingConfigurations")
    written = {series_of_mapping(c) for c in children(held) if feeds_data(c)}
    invoked = {t for c in children(held) if not feeds_data(c) for t in targets(c, "Sinks")}
    for config in children(at(submodel(built, "AssetInterfacesMappingConfiguration"), "MappingConfigurations")):
        if feeds_data(config):
            if series_of_mapping(config) not in written:
                held["value"].append(config)
        elif not set(targets(config, "Sinks")) <= invoked:
            held["value"].append(config)

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


def program_name(spec: ModuleSpec, components: list[dict]) -> str:
    """The module's name as its components' AASs carry it (``<name><item>AAS``, ``profile.component_identity``)."""
    for env in components:
        short = env["assetAdministrationShells"][0]["idShort"]
        for item in spec.equipment:
            if short.endswith(f"{item}AAS") and len(short) > len(f"{item}AAS"):
                return short[:-len(f"{item}AAS")]
    return spec.module


def described_skill(module: dict, components: list[dict], name: str, skill: Composite) -> dict:
    """The module's AAS with ``skill`` described as ``name`` in its Skills submodel (replacing one of
    that name), as the skill editor saves a skill: its parameters, steps and results, not built
    (Deployment Described), with no action of the interface yet."""
    spec = described(module, components)
    # Not offered while it is only described: it gets its actions once it is built (``offered``). The
    # module's name is what its components' AASs are named after: the steps refer to their skills.
    spec = spec.model_copy(update={"module": program_name(spec, components),
                                   "composites": {**spec.composites, name: skill.model_copy(update={"offered": False})}})
    shell = module["assetAdministrationShells"][0]
    interface = at(submodel(module, "AssetInterfacesDescription"), "interface_opcua")
    describer = Describer(spec, "", None, None, None, at(interface, "EndpointMetadata", "base")["value"])
    describer.module_id = shell["id"]
    asset = Module(id_short=shell["idShort"], id=shell["id"],
                          asset_type=shell["assetInformation"].get("assetType") or f"{model.RESOURCE}/Module",
                          derived_from=model.RESOURCE_TEMPLATE)
    made = describer.skill(name)
    made.Deployment = arso.Deployment(**prop("Described"))
    put(asset.skills.Skill, name, made)
    built = model.build(model.profile(Module.model_validate(asset.model_dump()),
                                      global_asset_id=shell["assetInformation"].get("globalAssetId", "")))
    module = copy.deepcopy(module)
    skills = submodel(module, "Skills")
    skills["submodelElements"] = [e for e in skills["submodelElements"] if e.get("idShort") != name] + [at(submodel(built, "Skills"), name)]
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
            elif value["modelType"] == "SubmodelElementList":     # the values it takes
                kind = value.get("valueTypeListElement")
                facts[container["idShort"]] = CapabilityProperty(
                    values=[float(item["value"]) if kind == "xs:double" else item["value"] for item in value["value"]],
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


def reached_offers(module: dict, components: list[dict], found: list[Offer]) -> list[Offer]:
    """The derived offers with the ranges their skills reach (``modplan.discover.reached``): a property
    the capability's Post compares with is what the skill leaves at the ends of its parameters'
    ranges, not the range of the one parameter that means it (two doses fill twice a dose)."""
    from modplan.discover import reached
    from modplan.read import read
    from .capabilities import vocabulary
    if submodel(module, "CapabilityDescription") is None or not found:
        return found
    domain = read(module, components, vocabulary())
    if not domain.actions():
        return found                                      # an AAS without its components' capabilities
    composites = described(module, components).composites
    for offer in found:
        skill = composites.get(offer.skill_name)
        ranges = reached(domain, skill, offer.name, vocabulary()) if skill is not None else {}
        for prop in offer.properties:
            if local(prop.meaning) in ranges and prop.minimum is not None:
                prop.minimum, prop.maximum = (str(v) for v in ranges[local(prop.meaning)])
    return found


def planned_offers(module: dict, components: list[dict], derived: set[str]) -> list[Offer]:
    """The process capabilities no skill offers that a skill can be planned for (``modplan.discover``):
    offered after a reconfiguration, for the values a plan exists for, realized by no skill yet."""
    from modplan.discover import discover
    from modplan.read import read
    from .capabilities import vocabulary
    if submodel(module, "CapabilityDescription") is None:
        return []
    found = []
    for d in discover(read(module, components), vocabulary()):
        iri = f"{BASE_URL}/semantics/{d.capability}"
        if iri in derived:
            continue
        found.append(Offer(iri, "", False, [Property(f"{BASE_URL}/semantics/{name}", vocabulary().unit(name), str(lo), str(hi))
                                             for name, (lo, hi) in d.ranges.items()]))
    return found


def capabilities(module: dict, components: list[dict]) -> dict:
    """The module's AAS with its offered capabilities derived anew from its skills and those of its
    components (``modreg.derive``): what a skill sets is replaced, the facts the description states
    for a capability are kept, a container keeps its name, a capability written by hand that no
    skill offers stays, and one a skill no longer offers goes. A skill described but not built
    offers its capability after a reconfiguration."""
    module = copy.deepcopy(module)
    old = next((s for s in module["submodels"] if s["idShort"] == "CapabilityDescription"), None)
    stated, named, by_hand = stated_facts(old)
    found = reached_offers(module, components, derived_offers(project([module, *components], structure=False)))
    found += planned_offers(module, components, {o.capability for o in found})
    description = capability_description(found, stated, named)
    derived = {o.capability for o in found}
    kept = [box for box in by_hand if at(box, "Capability")["supplementalSemanticIds"][0]["keys"][0]["value"] not in derived]
    # The components' capabilities (a set per component) are not derived: they stay as they are.
    others = [s for s in children(old) if s.get("idShort") != OFFERED_SET]
    if description is None and not kept and not others:
        module["submodels"] = [s for s in module["submodels"] if s is not old]
        return module
    shell = module["assetAdministrationShells"][0]
    asset = Module(id_short=shell["idShort"], id=shell["id"],
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

