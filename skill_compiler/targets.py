"""Target profile templates bound to a runtime type library (types.json)."""
import copy

from iec61499_mgmt.models import TypeLibrary

from .models import TargetProfile


def bind_library(template: dict, library: TypeLibrary) -> TargetProfile:
    """Fill a hash-free target template with ``library`` and the runtime type hashes of its skills."""
    data = copy.deepcopy(template)
    data["library"] = library.model_dump()
    for key, binding in data["runtime_bindings"].items():
        typ = library.types.get(binding["fb_type"])
        if typ is None:
            raise ValueError(f"Skill type {binding['fb_type']} of {key} is not in the type library")
        binding["type_hash"] = typ.type_hash
    return TargetProfile.model_validate(data)
