"""Module — generated from IDTA template."""

from __future__ import annotations

from typing import Any, ClassVar, List, Dict, Optional, TypeAlias
from aas_pydantic import (
    Operation, Property, ReferenceElement, Submodel, SubmodelElement, SubmodelElementCollection, SubmodelElementList,
)

class SkillStep(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "One use of a skill by a command."
    Skill: ReferenceElement
    StepConstant: Dict[str, Property] = {}
    StepVariable: Dict[str, ReferenceElement] = {}

# alias so field ``SkillStep_t`` can name a class of the same id_short
SkillStep_t: TypeAlias = SkillStep
class Steps(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "What a command runs, one step after the other in the order of their names (P1, P2, ...)."
    SkillStep: Dict[str, SkillStep_t] = {}

# alias so field ``Steps_t`` can name a class of the same id_short
Steps_t: TypeAlias = Steps
class Occupy(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "One command of the resource: the action that calls it, its Operation, and what the resource runs on it."
    InterfaceReference: Optional[ReferenceElement] = None
    SkillOperation: Dict[str, Operation] = {}
    Steps: Optional[Steps_t] = None

class Release(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "One command of the resource: the action that calls it, its Operation, and what the resource runs on it."
    InterfaceReference: Optional[ReferenceElement] = None
    SkillOperation: Dict[str, Operation] = {}
    Steps: Optional[Steps_t] = None

class Reset(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "One command of the resource: the action that calls it, its Operation, and what the resource runs on it."
    InterfaceReference: Optional[ReferenceElement] = None
    SkillOperation: Dict[str, Operation] = {}
    Steps: Optional[Steps_t] = None

class Start(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "One command of the resource: the action that calls it, its Operation, and what the resource runs on it."
    InterfaceReference: Optional[ReferenceElement] = None
    SkillOperation: Dict[str, Operation] = {}
    Steps: Optional[Steps_t] = None

class Stop(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "One command of the resource: the action that calls it, its Operation, and what the resource runs on it."
    InterfaceReference: Optional[ReferenceElement] = None
    SkillOperation: Dict[str, Operation] = {}
    Steps: Optional[Steps_t] = None

class Abort(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "One command of the resource: the action that calls it, its Operation, and what the resource runs on it."
    InterfaceReference: Optional[ReferenceElement] = None
    SkillOperation: Dict[str, Operation] = {}
    Steps: Optional[Steps_t] = None

class Clear(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "One command of the resource: the action that calls it, its Operation, and what the resource runs on it."
    InterfaceReference: Optional[ReferenceElement] = None
    SkillOperation: Dict[str, Operation] = {}
    Steps: Optional[Steps_t] = None

# alias so field ``Occupy_t`` can name a class of the same id_short
Occupy_t: TypeAlias = Occupy
# alias so field ``Release_t`` can name a class of the same id_short
Release_t: TypeAlias = Release
# alias so field ``Reset_t`` can name a class of the same id_short
Reset_t: TypeAlias = Reset
# alias so field ``Start_t`` can name a class of the same id_short
Start_t: TypeAlias = Start
# alias so field ``Stop_t`` can name a class of the same id_short
Stop_t: TypeAlias = Stop
# alias so field ``Abort_t`` can name a class of the same id_short
Abort_t: TypeAlias = Abort
# alias so field ``Clear_t`` can name a class of the same id_short
Clear_t: TypeAlias = Clear
class Module(Submodel):
    semantic_id: str = "https://smartproductionlab.aau.dk/ARSO/Module/1/0/Submodel"
    description: str = "The resource's own commands: its state machine (Reset, Start, Stop, Abort, Clear) and who may use it (Occupy, Release), each described like a command of a skill."
    VERSION: ClassVar[str] = "1"
    REVISION: ClassVar[str] = "0"
    Occupy: Optional[Occupy_t] = None
    Release: Optional[Release_t] = None
    Reset: Optional[Reset_t] = None
    Start: Optional[Start_t] = None
    Stop: Optional[Stop_t] = None
    Abort: Optional[Abort_t] = None
    Clear: Optional[Clear_t] = None

# ── Resolve forward references (Pydantic circular refs) ──
SkillStep.model_rebuild()
Steps.model_rebuild()
Occupy.model_rebuild()
Release.model_rebuild()
Reset.model_rebuild()
Start.model_rebuild()
Stop.model_rebuild()
Abort.model_rebuild()
Clear.model_rebuild()
Module.model_rebuild()
