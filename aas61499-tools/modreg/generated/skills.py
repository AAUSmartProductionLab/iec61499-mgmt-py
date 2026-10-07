"""Skills — generated from IDTA template."""

from __future__ import annotations

from typing import Any, ClassVar, List, Dict, Optional, TypeAlias
from aas_pydantic import (
    Operation, Property, ReferenceElement, RelationshipElement, Submodel, SubmodelElement, SubmodelElementCollection, SubmodelElementList,
)

class Interfaces(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "Mandatory top-level container, always present and always empty."
    pass

class Parameters(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "The skill's parameters as Properties (css:SkillParameter); value is the current (deployed) value, qualifiers Unit, Minimum, Maximum and Default the declaration."
    SkillParameter: Dict[str, Property] = {}

class Contract(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "For primitive skills: Requires (precondition), Ensures (postcondition) or After (open-loop duration), Invariant, Timeout."
    Requires: Optional[Property] = None
    Ensures: Optional[Property] = None
    After: Optional[Property] = None
    Invariant: Optional[Property] = None
    Timeout: Optional[Property] = None

class Uses(SubmodelElementList):
    semantic_id: str = ""
    description: str = "References to the skills a composite skill uses (IDTA 02015 Uses)."
    value: List[Any] = []

class SkillStep(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "One use of a skill in a sequence: Skill [ReferenceElement, 1] to a skill listed in Uses (a Skill or a BuildingBlock), and Bindings [SMC, 0..1] with what is bound to its parameters, each named like the parameter: a Property with the constant (current value), or a ReferenceElement to the parameter of the composite skill that is handed down to the step."
    pass

class SkillSequence(SubmodelElementList):
    semantic_id: str = ""
    description: str = "A composite's sequence of Steps (Execute: what Start runs; Stop: what Stop runs)."
    item_type: ClassVar = SkillStep
    value: List[SkillStep] = []

class Occupies(SubmodelElementList):
    semantic_id: str = ""
    description: str = "References to HierarchicalStructures nodes (equipment) the skill locks while it runs; two skills occupying one node never run at once."
    value: List[Any] = []

class Implementation(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "The runtime block implementing the skill: FBType (qualified IEC 61499 type), TypeHash (as the runtime reports it) and InstancePath (dotted instance name)."
    FBType: Property
    TypeHash: Optional[Property] = None
    InstancePath: Optional[Property] = None

# alias so field ``Parameters_t`` can name a class of the same id_short
Parameters_t: TypeAlias = Parameters
# alias so field ``Contract_t`` can name a class of the same id_short
Contract_t: TypeAlias = Contract
# alias so field ``Uses_t`` can name a class of the same id_short
Uses_t: TypeAlias = Uses
# alias so field ``SkillSequence_t`` can name a class of the same id_short
SkillSequence_t: TypeAlias = SkillSequence
# alias so field ``Occupies_t`` can name a class of the same id_short
Occupies_t: TypeAlias = Occupies
# alias so field ``Implementation_t`` can name a class of the same id_short
Implementation_t: TypeAlias = Implementation
class Skill(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "A named skill."
    SemanticId: Property
    SkillOperation: Dict[str, Operation] = {}
    InterfaceReference: ReferenceElement
    StateMachine: Optional[Property] = None
    Kind: Optional[Property] = None
    Parameters: Optional[Parameters_t] = None
    RealizesProperty: Optional[RelationshipElement] = None
    Contract: Optional[Contract_t] = None
    Uses: Optional[Uses_t] = None
    SkillSequence: Dict[str, SkillSequence_t] = {}
    Occupies: Optional[Occupies_t] = None
    StateReference: Optional[ReferenceElement] = None
    Implementation: Optional[Implementation_t] = None

# alias so field ``Skill_t`` can name a class of the same id_short
Skill_t: TypeAlias = Skill
class Skills_2(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "Mandatory top-level container for all Skill entries."
    Skill: Dict[str, Skill_t] = {}

class Results(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "The results of the building block, one Property each."
    BuildingBlockResult: Dict[str, Property] = {}

# alias so field ``Results_t`` can name a class of the same id_short
Results_t: TypeAlias = Results
class BuildingBlock(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "A skill primitive that only runs as a step of composite skills."
    SemanticId: Property
    Kind: Optional[Property] = None
    Parameters: Optional[Parameters_t] = None
    Contract: Optional[Contract_t] = None
    Occupies: Optional[Occupies_t] = None
    Implementation: Implementation_t
    Results: Optional[Results_t] = None

# alias so field ``BuildingBlock_t`` can name a class of the same id_short
BuildingBlock_t: TypeAlias = BuildingBlock
class BuildingBlocks(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "The skill primitives of the resource that it does not offer through its interface."
    BuildingBlock: Dict[str, BuildingBlock_t] = {}

class Error(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "A named error entry, if populated."
    ErrorCode: Property

# alias so field ``Error_t`` can name a class of the same id_short
Error_t: TypeAlias = Error
class Errors(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "Mandatory top-level container for global CC error entries."
    Error: Dict[str, Error_t] = {}

# alias so field ``Interfaces_t`` can name a class of the same id_short
Interfaces_t: TypeAlias = Interfaces
# alias so field ``BuildingBlocks_t`` can name a class of the same id_short
BuildingBlocks_t: TypeAlias = BuildingBlocks
# alias so field ``Errors_t`` can name a class of the same id_short
Errors_t: TypeAlias = Errors
class Skills(Submodel):
    semantic_id: str = "https://smartproductionlab.aau.dk/ARSO/Skills/1/0/Submodel"
    description: str = "IDTA 02015 CCType \u2014 Control Component Type (Interfaces, Skills, Errors), ARSO-flattened."
    VERSION: ClassVar[str] = "1"
    REVISION: ClassVar[str] = "0"
    Interfaces: Interfaces_t
    Skills: Skills_2
    BuildingBlocks: Optional[BuildingBlocks_t] = None
    Errors: Errors_t

# ── Resolve forward references (Pydantic circular refs) ──
Interfaces.model_rebuild()
Parameters.model_rebuild()
Contract.model_rebuild()
Uses.model_rebuild()
SkillStep.model_rebuild()
SkillSequence.model_rebuild()
Occupies.model_rebuild()
Implementation.model_rebuild()
Skill.model_rebuild()
Skills_2.model_rebuild()
Results.model_rebuild()
BuildingBlock.model_rebuild()
BuildingBlocks.model_rebuild()
Error.model_rebuild()
Errors.model_rebuild()
Skills.model_rebuild()
