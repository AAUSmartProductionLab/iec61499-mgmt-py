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
"""
from __future__ import annotations

import base64
import copy

from aas_pydantic import Property

from modgen.spec import ModuleSpec

from . import model
from .model import ModuleTypeAAS
from .profile import Describer, put


def children(element: dict | None) -> list[dict]:
    kids = (element or {}).get("submodelElements") or (element or {}).get("value") or []
    return [k for k in kids if isinstance(k, dict)] if isinstance(kids, list) else []


def at(element: dict | None, *path: str) -> dict | None:
    for step in path:
        element = next((c for c in children(element) if c.get("idShort") == step), None)
    return element


def submodel(env: dict, id_short: str) -> dict:
    return next(s for s in env["submodels"] if s["idShort"] == id_short)


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
        put(asset.skills.Skills.Skill, name, describer.skill(name))
    made = asset.asset_interfaces_description.InterfaceTemplateForOPCUA["interface_opcua"]
    for key, action in describer.actions.items():
        put(made.InteractionMetadata.actions.property_name, key, action)
    for key, shown in describer.properties.items():
        put(made.InteractionMetadata.properties.property_name, key, shown)
    for name, (_, concept, title) in describer.datapoints.items():
        put(asset.operational_data.Datapoint, name, Property(value="0", value_type="xs:decimal", semantic_id=concept, description=title))
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
        described, complete = at(submodel(module, "Skills"), "Skills", name), at(submodel(built, "Skills"), "Skills", name)
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
