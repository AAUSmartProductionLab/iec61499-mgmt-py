"""The AASs of a module run in Python (modpy, ``module-py/``), whose spec is in ``cell/modules/python``.

modpy serves such a module node for node as FORTE serves a generated module (namespace 1, FORTE's
argument names, the same skills, steps and procedures), so the module is described from its spec by
the Describer that describes a FORTE module. Left out is what is FORTE's: the rule set its program is
built by (there is no IEC 61499 program to reconfigure online) and, in the nameplate, IEC 61499.

    profiles = describe_all(load("cell/modules/python/loading.yaml"))
"""
from __future__ import annotations

from pathlib import Path

from aas_pydantic.submodel_templates.nameplate import ManufacturerProductDesignation

from modgen.spec import ModuleSpec

from . import model
from .profile import Describer

FOLDER = "python"                   # cell/modules/python: the specs of the modules run in Python


def runs_in_python(path: Path | str) -> bool:
    """Whether the spec at ``path`` is of a module run in Python (it is in a folder ``python``)."""
    return Path(path).resolve().parent.name == FOLDER


class PythonDescriber(Describer):
    """The Describer, for a module run in Python."""

    def build(self):
        built = super().build()
        module = built[0][0]
        module.skills.RuleSet = None
        module.nameplate.ManufacturerProductDesignation = ManufacturerProductDesignation(
            value={"en": f"{self.spec.module} module (Python, modpy)"})
        return built


def describe_all(spec: ModuleSpec, target: str | None = None, opcua: str | None = None,
                 spec_path: str | None = None) -> list[dict]:
    """The profiles of the module (the first) and of its components; ``opcua`` where its server is
    (default: the target's host, port 4840)."""
    target = target or next(iter(spec.targets))
    return [model.profile(asset, global_asset_id=asset_id)
            for asset, asset_id in PythonDescriber(spec, target, None, None, spec_path, opcua).build()]
