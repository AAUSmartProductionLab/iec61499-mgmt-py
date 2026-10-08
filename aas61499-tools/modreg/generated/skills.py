"""Skills — generated from IDTA template."""

from __future__ import annotations

from typing import Any, ClassVar, List, Dict, Optional, TypeAlias
from aas_pydantic import (
    Operation, Property, ReferenceElement, Submodel, SubmodelElement, SubmodelElementCollection, SubmodelElementList,
)

class Interfaces(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "Mandatory top-level container, always present and always empty."
    pass

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
class Start(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "One command of a skill: the action that calls it, its Operation, and what it runs."
    InterfaceReference: Optional[ReferenceElement] = None
    SkillOperation: Dict[str, Operation] = {}
    Steps: Optional[Steps_t] = None

class Stop(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "One command of a skill: the action that calls it, its Operation, and what it runs."
    InterfaceReference: Optional[ReferenceElement] = None
    SkillOperation: Dict[str, Operation] = {}
    Steps: Optional[Steps_t] = None

class Abort(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "One command of a skill: the action that calls it, its Operation, and what it runs."
    InterfaceReference: Optional[ReferenceElement] = None
    SkillOperation: Dict[str, Operation] = {}
    Steps: Optional[Steps_t] = None

class Reset(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "One command of a skill: the action that calls it, its Operation, and what it runs."
    InterfaceReference: Optional[ReferenceElement] = None
    SkillOperation: Dict[str, Operation] = {}
    Steps: Optional[Steps_t] = None

class Contract(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "For primitive skills: Requires (precondition), Ensures (postcondition) or After (open-loop duration), Invariant, Timeout."
    Requires: Optional[Property] = None
    Ensures: Optional[Property] = None
    After: Optional[Property] = None
    Invariant: Optional[Property] = None
    Timeout: Optional[Property] = None

# alias so field ``Start_t`` can name a class of the same id_short
Start_t: TypeAlias = Start
# alias so field ``Stop_t`` can name a class of the same id_short
Stop_t: TypeAlias = Stop
# alias so field ``Abort_t`` can name a class of the same id_short
Abort_t: TypeAlias = Abort
# alias so field ``Reset_t`` can name a class of the same id_short
Reset_t: TypeAlias = Reset
# alias so field ``Contract_t`` can name a class of the same id_short
Contract_t: TypeAlias = Contract
class Skill(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "A named skill."
    SemanticId: Property
    Start: Optional[Start_t] = None
    Stop: Optional[Stop_t] = None
    Abort: Optional[Abort_t] = None
    Reset: Optional[Reset_t] = None
    InterfaceReference: Optional[ReferenceElement] = None
    SkillOperation: Dict[str, Operation] = {}
    Contract: Optional[Contract_t] = None
    StateMachine: Optional[Property] = None

# alias so field ``Skill_t`` can name a class of the same id_short
Skill_t: TypeAlias = Skill
class Skills_2(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "Mandatory top-level container for all Skill entries."
    Skill: Dict[str, Skill_t] = {}

class Error(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "A named error entry, if populated."
    ErrorCode: Property

# alias so field ``Error_t`` can name a class of the same id_short
Error_t: TypeAlias = Error
class Errors(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "Mandatory top-level container for global CC error entries: what the ErrorID in the answer of an Operation can be."
    Error: Dict[str, Error_t] = {}

# alias so field ``Interfaces_t`` can name a class of the same id_short
Interfaces_t: TypeAlias = Interfaces
# alias so field ``Errors_t`` can name a class of the same id_short
Errors_t: TypeAlias = Errors
class Skills(Submodel):
    semantic_id: str = "https://smartproductionlab.aau.dk/ARSO/Skills/1/0/Submodel"
    description: str = "IDTA 02015 CCType \u2014 Control Component Type (Interfaces, Skills, Errors), ARSO-flattened."
    VERSION: ClassVar[str] = "1"
    REVISION: ClassVar[str] = "0"
    Interfaces: Interfaces_t
    Skills: Skills_2
    Errors: Errors_t

# ── Resolve forward references (Pydantic circular refs) ──
Interfaces.model_rebuild()
SkillStep.model_rebuild()
Steps.model_rebuild()
Start.model_rebuild()
Stop.model_rebuild()
Abort.model_rebuild()
Reset.model_rebuild()
Contract.model_rebuild()
Skill.model_rebuild()
Skills_2.model_rebuild()
Error.model_rebuild()
Errors.model_rebuild()
Skills.model_rebuild()
