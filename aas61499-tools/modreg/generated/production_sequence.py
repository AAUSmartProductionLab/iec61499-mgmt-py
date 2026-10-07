"""ProductionSequence — generated from IDTA template."""

from __future__ import annotations

from typing import Any, ClassVar, List, Dict, Optional, TypeAlias
from aas_pydantic import (
    Property, ReferenceElement, Submodel, SubmodelElement, SubmodelElementCollection, SubmodelElementList,
)

class PlanSchema(Property):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/PlanSchema/1/0"
    description: str = "The schema of the plan: production-sequence/2.0."
    value_type: str = "xs:string"

class Revision(Property):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Revision/1/0"
    description: str = "Counts the saved changes of the plan."
    value_type: str = "xs:nonNegativeInteger"

class SequenceId(Property):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/SequenceId/1/0"
    description: str = "Identifies the sequence among those of its subject."
    value_type: str = "xs:string"

class Name(Property):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Name/1/0"
    description: str = "The name shown for the sequence."
    value_type: str = "xs:string"

class Role(Property):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Role/1/0"
    description: str = "Primary: the subject's own sequence. Subprocess: a sequence others call."
    value_type: str = "xs:string"

class Subject(ReferenceElement):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Subject/1/0"
    description: str = "The AAS of the product the sequence plans."

class Subprocess(ReferenceElement):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/SequenceReference/1/0"
    description: str = "A called sequence (its submodel)."

# alias so field ``Subprocess_t`` can name a class of the same id_short
Subprocess_t: TypeAlias = Subprocess
class Subprocesses(SubmodelElementCollection):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Subprocesses/1/0"
    description: str = "The sequences this one calls."
    Subprocess: Dict[str, Subprocess_t] = {}

class NodeId(Property):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/NodeId/1/0"
    description: str = "Identifies the node within its sequence."
    value_type: str = "xs:string"

class Kind(Property):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Kind/1/0"
    description: str = "step, call, parallel or conditional."
    value_type: str = "xs:string"

class Order(Property):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Order/1/0"
    description: str = "Position among the nodes beside it."
    value_type: str = "xs:nonNegativeInteger"

class ProcessOwner(ReferenceElement):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/ProcessOwner/1/0"
    description: str = "Kind step: the AAS whose process the step runs."

class ProcessReference(ReferenceElement):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/ProcessReference/1/0"
    description: str = "Kind step: the process, in the owner's Process Parameters."

class RequiredCapability(ReferenceElement):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/RequiredCapability/1/0"
    description: str = "A Required capability in a Capability Description."

# alias so field ``RequiredCapability_t`` can name a class of the same id_short
RequiredCapability_t: TypeAlias = RequiredCapability
class RequiredCapabilities(SubmodelElementCollection):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/RequiredCapabilities/1/0"
    description: str = "Kind step: the capabilities the step requires, where they differ from those of its process."
    RequiredCapability: Dict[str, RequiredCapability_t] = {}

class Resource(ReferenceElement):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Resource/1/0"
    description: str = "Kind step: the AAS of the resource the step is assigned to."

class SkillId(Property):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/SkillId/1/0"
    description: str = "Kind step: the name of the skill that runs the step."
    value_type: str = "xs:string"

class Skill(ReferenceElement):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Skill/1/0"
    description: str = "Kind step: the skill, in the resource's Skills submodel."

class ExecutionMode(Property):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/ExecutionMode/1/0"
    description: str = "Kind step: station (a resource runs it) or manual."
    value_type: str = "xs:string"

class Value(Property):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Value/1/0"
    description: str = "The constant; empty when the value comes from a source."
    value_type: str = "xs:string"

class SourceAas(ReferenceElement):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/SourceAas/1/0"
    description: str = "The AAS the value comes from."

class SourceElement(ReferenceElement):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/SourceElement/1/0"
    description: str = "The element the value comes from."

# alias so field ``Name_t`` can name a class of the same id_short
Name_t: TypeAlias = Name
# alias so field ``Value_t`` can name a class of the same id_short
Value_t: TypeAlias = Value
# alias so field ``SourceAas_t`` can name a class of the same id_short
SourceAas_t: TypeAlias = SourceAas
# alias so field ``SourceElement_t`` can name a class of the same id_short
SourceElement_t: TypeAlias = SourceElement
class Binding(SubmodelElementCollection):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Binding/1/0"
    description: str = "What one parameter of the step's skill gets: a constant, or a process parameter."
    Name: Name_t
    Value: Value_t
    SourceAas: Optional[SourceAas_t] = None
    SourceElement: Optional[SourceElement_t] = None

# alias so field ``Binding_t`` can name a class of the same id_short
Binding_t: TypeAlias = Binding
class Bindings(SubmodelElementCollection):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Bindings/1/0"
    description: str = "Kind step: what is bound to the parameters of the skill."
    Binding: Dict[str, Binding_t] = {}

class SequenceReference(ReferenceElement):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/SequenceReference/1/0"
    description: str = "Kind call: the sequence that is run."

class OccurrenceId(Property):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/OccurrenceId/1/0"
    description: str = "Kind call: identifies this use of the called sequence."
    value_type: str = "xs:string"

class GlobalAssetId(Property):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/GlobalAssetId/1/0"
    description: str = "The part's global asset id."
    value_type: str = "xs:string"

# alias so field ``GlobalAssetId_t`` can name a class of the same id_short
GlobalAssetId_t: TypeAlias = GlobalAssetId
class Component(SubmodelElementCollection):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Component/1/0"
    description: str = "Kind call: the part the called sequence makes."
    GlobalAssetId: GlobalAssetId_t
    SourceAas: Optional[SourceAas_t] = None
    SourceElement: Optional[SourceElement_t] = None

class ConditionType(Property):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/ConditionType/1/0"
    description: str = "The kind of condition, e.g. everyNthProduct."
    value_type: str = "xs:string"

class EveryNProducts(Property):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/EveryNProducts/1/0"
    description: str = "everyNthProduct: every how many products."
    value_type: str = "xs:positiveInteger"

class CounterScope(Property):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/CounterScope/1/0"
    description: str = "everyNthProduct: what the count runs over, e.g. productionRun."
    value_type: str = "xs:string"

# alias so field ``ConditionType_t`` can name a class of the same id_short
ConditionType_t: TypeAlias = ConditionType
# alias so field ``EveryNProducts_t`` can name a class of the same id_short
EveryNProducts_t: TypeAlias = EveryNProducts
# alias so field ``CounterScope_t`` can name a class of the same id_short
CounterScope_t: TypeAlias = CounterScope
class Condition(SubmodelElementCollection):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Condition/1/0"
    description: str = "Kind conditional: when the guarded steps run."
    ConditionType: ConditionType_t
    EveryNProducts: Optional[EveryNProducts_t] = None
    CounterScope: Optional[CounterScope_t] = None

class BranchId(Property):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/BranchId/1/0"
    description: str = "Identifies the branch."
    value_type: str = "xs:string"

# alias so field ``BranchId_t`` can name a class of the same id_short
BranchId_t: TypeAlias = BranchId
# alias so field ``Order_t`` can name a class of the same id_short
Order_t: TypeAlias = Order
class Branch(SubmodelElementCollection):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Branch/1/0"
    description: str = "One branch of a parallel node."
    BranchId: BranchId_t
    Name: Name_t
    Order: Order_t
    Steps: Optional[Steps_t] = None

# alias so field ``Branch_t`` can name a class of the same id_short
Branch_t: TypeAlias = Branch
class Branches(SubmodelElementCollection):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Branches/1/0"
    description: str = "Kind parallel: the branches."
    Branch: Dict[str, Branch_t] = {}

# alias so field ``NodeId_t`` can name a class of the same id_short
NodeId_t: TypeAlias = NodeId
# alias so field ``Kind_t`` can name a class of the same id_short
Kind_t: TypeAlias = Kind
# alias so field ``ProcessOwner_t`` can name a class of the same id_short
ProcessOwner_t: TypeAlias = ProcessOwner
# alias so field ``ProcessReference_t`` can name a class of the same id_short
ProcessReference_t: TypeAlias = ProcessReference
# alias so field ``RequiredCapabilities_t`` can name a class of the same id_short
RequiredCapabilities_t: TypeAlias = RequiredCapabilities
# alias so field ``Resource_t`` can name a class of the same id_short
Resource_t: TypeAlias = Resource
# alias so field ``SkillId_t`` can name a class of the same id_short
SkillId_t: TypeAlias = SkillId
# alias so field ``Skill_t`` can name a class of the same id_short
Skill_t: TypeAlias = Skill
# alias so field ``ExecutionMode_t`` can name a class of the same id_short
ExecutionMode_t: TypeAlias = ExecutionMode
# alias so field ``Bindings_t`` can name a class of the same id_short
Bindings_t: TypeAlias = Bindings
# alias so field ``SequenceReference_t`` can name a class of the same id_short
SequenceReference_t: TypeAlias = SequenceReference
# alias so field ``OccurrenceId_t`` can name a class of the same id_short
OccurrenceId_t: TypeAlias = OccurrenceId
# alias so field ``Component_t`` can name a class of the same id_short
Component_t: TypeAlias = Component
# alias so field ``Condition_t`` can name a class of the same id_short
Condition_t: TypeAlias = Condition
# alias so field ``Branches_t`` can name a class of the same id_short
Branches_t: TypeAlias = Branches
class Step(SubmodelElementCollection):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Step/1/0"
    description: str = "One node of the sequence. Kind step: a process run by a skill of a resource. Kind call: another sequence. Kind parallel: branches that all join. Kind conditional: steps that only run when the condition holds."
    NodeId: NodeId_t
    Kind: Kind_t
    Name: Name_t
    Order: Order_t
    ProcessOwner: Optional[ProcessOwner_t] = None
    ProcessReference: Optional[ProcessReference_t] = None
    RequiredCapabilities: Optional[RequiredCapabilities_t] = None
    Resource: Optional[Resource_t] = None
    SkillId: Optional[SkillId_t] = None
    Skill: Optional[Skill_t] = None
    ExecutionMode: Optional[ExecutionMode_t] = None
    Bindings: Optional[Bindings_t] = None
    SequenceReference: Optional[SequenceReference_t] = None
    OccurrenceId: Optional[OccurrenceId_t] = None
    Component: Optional[Component_t] = None
    Condition: Optional[Condition_t] = None
    Steps: Optional[Steps_t] = None
    Branches: Optional[Branches_t] = None

# alias so field ``Step_t`` can name a class of the same id_short
Step_t: TypeAlias = Step
class Steps(SubmodelElementCollection):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Steps/1/0"
    description: str = "The nodes of the sequence."
    Step: Dict[str, Step_t] = {}

# alias so field ``PlanSchema_t`` can name a class of the same id_short
PlanSchema_t: TypeAlias = PlanSchema
# alias so field ``Revision_t`` can name a class of the same id_short
Revision_t: TypeAlias = Revision
# alias so field ``SequenceId_t`` can name a class of the same id_short
SequenceId_t: TypeAlias = SequenceId
# alias so field ``Role_t`` can name a class of the same id_short
Role_t: TypeAlias = Role
# alias so field ``Subject_t`` can name a class of the same id_short
Subject_t: TypeAlias = Subject
# alias so field ``Subprocesses_t`` can name a class of the same id_short
Subprocesses_t: TypeAlias = Subprocesses
class ProductionSequence(Submodel):
    semantic_id: str = "https://smartproductionlab.aau.dk/SubmodelTemplate/ProductionSequence/2/0"
    description: str = "The plan of a product as the process planner writes it (schema production-sequence/2.0): the steps in order, each assigned to a skill of a resource, with what is bound to the skill's parameters."
    VERSION: ClassVar[str] = "2"
    REVISION: ClassVar[str] = "0"
    PlanSchema: PlanSchema_t
    Revision: Revision_t
    SequenceId: SequenceId_t
    Name: Name_t
    Role: Role_t
    Subject: Subject_t
    Subprocesses: Optional[Subprocesses_t] = None
    Steps: Steps_t

# alias so field ``Steps_t`` can name a class of the same id_short
Steps_t: TypeAlias = Steps

# ── Resolve forward references (Pydantic circular refs) ──
PlanSchema.model_rebuild()
Revision.model_rebuild()
SequenceId.model_rebuild()
Name.model_rebuild()
Role.model_rebuild()
Subject.model_rebuild()
Subprocess.model_rebuild()
Subprocesses.model_rebuild()
NodeId.model_rebuild()
Kind.model_rebuild()
Order.model_rebuild()
ProcessOwner.model_rebuild()
ProcessReference.model_rebuild()
RequiredCapability.model_rebuild()
RequiredCapabilities.model_rebuild()
Resource.model_rebuild()
SkillId.model_rebuild()
Skill.model_rebuild()
ExecutionMode.model_rebuild()
Value.model_rebuild()
SourceAas.model_rebuild()
SourceElement.model_rebuild()
Binding.model_rebuild()
Bindings.model_rebuild()
SequenceReference.model_rebuild()
OccurrenceId.model_rebuild()
GlobalAssetId.model_rebuild()
Component.model_rebuild()
ConditionType.model_rebuild()
EveryNProducts.model_rebuild()
CounterScope.model_rebuild()
Condition.model_rebuild()
BranchId.model_rebuild()
Branch.model_rebuild()
Branches.model_rebuild()
Step.model_rebuild()
Steps.model_rebuild()
ProductionSequence.model_rebuild()
