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

class NodeId(Property):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/NodeId/1/0"
    description: str = "The node's identifier, unique in its command."
    value_type: str = "xs:string"

class Kind(Property):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Kind/1/0"
    description: str = "Step, parallel, decision or conditional."
    value_type: str = "xs:string"

class Name(Property):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Name/1/0"
    description: str = "What a step, a branch or an output is called for a person; of a Binding, the input of the step's skill it is about."
    value_type: str = "xs:string"

class Order(Property):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Order/1/0"
    description: str = "The position among its siblings, from 0; it decides the order, not the place in the collection."
    value_type: str = "xs:string"

class Skill_production_sequence(ReferenceElement):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Skill/1/0"
    description: str = "The skill a step runs, the whole of it: running it is its Start, and its other commands are what ends it early."

class Value(Property):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Value/1/0"
    description: str = "A constant: what a Binding hands to the input (the value as it runs), or what a Condition compares with."
    value_type: str = "xs:string"

class SourceElement(ReferenceElement):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/SourceElement/1/0"
    description: str = "The variable of the command's Operation that is handed down to the input, or that a Condition looks at."

class InputReference(ReferenceElement):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/InputReference/1/0"
    description: str = "The input itself: the variable of the Start Operation of the step's skill."

# alias so field ``Name_t`` can name a class of the same id_short
Name_t: TypeAlias = Name
# alias so field ``Value_t`` can name a class of the same id_short
Value_t: TypeAlias = Value
# alias so field ``SourceElement_t`` can name a class of the same id_short
SourceElement_t: TypeAlias = SourceElement
# alias so field ``InputReference_t`` can name a class of the same id_short
InputReference_t: TypeAlias = InputReference
class StepBinding(SubmodelElementCollection):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Binding/1/0"
    description: str = "One input of the step's skill (Name): a constant (Value) or a variable of the command's Operation (SourceElement)."
    Name: Name_t
    Value: Optional[Value_t] = None
    SourceElement: Optional[SourceElement_t] = None
    InputReference: Optional[InputReference_t] = None

# alias so field ``StepBinding_t`` can name a class of the same id_short
StepBinding_t: TypeAlias = StepBinding
class Bindings(SubmodelElementCollection):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Bindings/1/0"
    description: str = "What the inputs of the step's skill are handed."
    StepBinding: Dict[str, StepBinding_t] = {}

class OutputId(Property):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/OutputId/1/0"
    description: str = "The output's identifier: the idShort of the output variable of the command's Operation."
    value_type: str = "xs:string"

class DataType(Property):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/DataType/1/0"
    description: str = "Boolean, number or string."
    value_type: str = "xs:string"

class Unit(Property):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Unit/1/0"
    description: str = "The unit of an output or of what a Condition compares; empty for none."
    value_type: str = "xs:string"

class ResultReference(ReferenceElement):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/ResultReference/1/0"
    description: str = "The result: an output variable of the Start Operation of the step's skill."

# alias so field ``OutputId_t`` can name a class of the same id_short
OutputId_t: TypeAlias = OutputId
# alias so field ``DataType_t`` can name a class of the same id_short
DataType_t: TypeAlias = DataType
# alias so field ``Unit_t`` can name a class of the same id_short
Unit_t: TypeAlias = Unit
# alias so field ``ResultReference_t`` can name a class of the same id_short
ResultReference_t: TypeAlias = ResultReference
class StepOutput(SubmodelElementCollection):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Output/1/0"
    description: str = "One result: OutputId names the output variable of the command's Operation, ResultReference the result of the step's skill it is."
    Name: Optional[Name_t] = None
    OutputId: OutputId_t
    DataType: Optional[DataType_t] = None
    Unit: Optional[Unit_t] = None
    ResultReference: Optional[ResultReference_t] = None

# alias so field ``StepOutput_t`` can name a class of the same id_short
StepOutput_t: TypeAlias = StepOutput
class Outputs(SubmodelElementCollection):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Outputs/1/0"
    description: str = "The results of the command that this step gives."
    StepOutput: Dict[str, StepOutput_t] = {}

class BranchId(Property):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/BranchId/1/0"
    description: str = "The branch's identifier, unique in its command."
    value_type: str = "xs:string"

# alias so field ``Order_t`` can name a class of the same id_short
Order_t: TypeAlias = Order
# alias so field ``BranchId_t`` can name a class of the same id_short
BranchId_t: TypeAlias = BranchId
class FlowBranch(SubmodelElementCollection):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Branch/1/0"
    description: str = "One branch: BranchId, Name, Order and its Steps."
    Steps: Optional[Steps_t] = None
    Name: Name_t
    Order: Order_t
    BranchId: BranchId_t

# alias so field ``FlowBranch_t`` can name a class of the same id_short
FlowBranch_t: TypeAlias = FlowBranch
class Branches(SubmodelElementCollection):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Branches/1/0"
    description: str = "The branches of a parallel step (two or more, all have to end) or of a decision (exactly two)."
    FlowBranch: Dict[str, FlowBranch_t] = {}

class ConditionType(Property):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/ConditionType/1/0"
    description: str = "EveryNthProduct or comparison."
    value_type: str = "xs:string"

class Operator(Property):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Operator/1/0"
    description: str = "Eq, ne, gt, gte, lt or lte."
    value_type: str = "xs:string"

class EveryNProducts(Property):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/EveryNProducts/1/0"
    description: str = "The condition holds on every N-th run."
    value_type: str = "xs:string"

class CounterScope(Property):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/CounterScope/1/0"
    description: str = "What the runs are counted over."
    value_type: str = "xs:string"

class Expected(SubmodelElementCollection):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Expected/1/0"
    description: str = "What the operand is compared with: DataType and Value."
    Value: Optional[Value_t] = None
    DataType: Optional[DataType_t] = None

class OperandType(Property):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/OperandType/1/0"
    description: str = "Parameter or output."
    value_type: str = "xs:string"

class StepId(Property):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/StepId/1/0"
    description: str = "The NodeId of the step whose output is compared."
    value_type: str = "xs:string"

# alias so field ``OperandType_t`` can name a class of the same id_short
OperandType_t: TypeAlias = OperandType
# alias so field ``StepId_t`` can name a class of the same id_short
StepId_t: TypeAlias = StepId
class Operand(SubmodelElementCollection):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Operand/1/0"
    description: str = "What is compared: a variable of the command's Operation (OperandType parameter: SourceElement) or the output of an earlier step (OperandType output: StepId, OutputId)."
    SourceElement: Optional[SourceElement_t] = None
    OutputId: Optional[OutputId_t] = None
    OperandType: Optional[OperandType_t] = None
    StepId: Optional[StepId_t] = None

# alias so field ``ConditionType_t`` can name a class of the same id_short
ConditionType_t: TypeAlias = ConditionType
# alias so field ``Operator_t`` can name a class of the same id_short
Operator_t: TypeAlias = Operator
# alias so field ``EveryNProducts_t`` can name a class of the same id_short
EveryNProducts_t: TypeAlias = EveryNProducts
# alias so field ``CounterScope_t`` can name a class of the same id_short
CounterScope_t: TypeAlias = CounterScope
# alias so field ``Expected_t`` can name a class of the same id_short
Expected_t: TypeAlias = Expected
# alias so field ``Operand_t`` can name a class of the same id_short
Operand_t: TypeAlias = Operand
class Condition(SubmodelElementCollection):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Condition/1/0"
    description: str = "What a decision or a conditional step looks at: every N-th run (ConditionType everyNthProduct: EveryNProducts, CounterScope) or a comparison (ConditionType comparison: Operand, Operator, Expected, Unit)."
    Unit: Optional[Unit_t] = None
    ConditionType: Optional[ConditionType_t] = None
    Operator: Optional[Operator_t] = None
    EveryNProducts: Optional[EveryNProducts_t] = None
    CounterScope: Optional[CounterScope_t] = None
    Expected: Optional[Expected_t] = None
    Operand: Optional[Operand_t] = None

# alias so field ``NodeId_t`` can name a class of the same id_short
NodeId_t: TypeAlias = NodeId
# alias so field ``Kind_t`` can name a class of the same id_short
Kind_t: TypeAlias = Kind
# alias so field ``Bindings_t`` can name a class of the same id_short
Bindings_t: TypeAlias = Bindings
# alias so field ``Outputs_t`` can name a class of the same id_short
Outputs_t: TypeAlias = Outputs
# alias so field ``Branches_t`` can name a class of the same id_short
Branches_t: TypeAlias = Branches
# alias so field ``Condition_t`` can name a class of the same id_short
Condition_t: TypeAlias = Condition
class SkillStep(SubmodelElementCollection):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Step/1/0"
    description: str = "One node of the flow."
    Steps: Optional[Steps_t] = None
    NodeId: NodeId_t
    Kind: Kind_t
    Name: Name_t
    Order: Order_t
    Skill: Optional[Skill_production_sequence] = None
    Bindings: Optional[Bindings_t] = None
    Outputs: Optional[Outputs_t] = None
    Branches: Optional[Branches_t] = None
    Condition: Optional[Condition_t] = None

# alias so field ``SkillStep_t`` can name a class of the same id_short
SkillStep_t: TypeAlias = SkillStep
class Steps(SubmodelElementCollection):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Steps/1/0"
    description: str = "What a command runs (or a branch, or the body of a conditional step): steps in the order of their Order."
    SkillStep: Dict[str, SkillStep_t] = {}

class Start(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "One command of a skill: the action that calls it, its Operation, and what it runs."
    InterfaceReference: Optional[ReferenceElement] = None
    SkillOperation: Dict[str, Operation] = {}
    Steps: Optional[Steps_t] = None

class Skill_production_sequence_2(ReferenceElement):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Skill/1/0"
    description: str = "The skill a step runs, the whole of it: running it is its Start, and its other commands are what ends it early."

class Stop(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "One command of a skill: the action that calls it, its Operation, and what it runs."
    InterfaceReference: Optional[ReferenceElement] = None
    SkillOperation: Dict[str, Operation] = {}
    Steps: Optional[Steps_t] = None

class Skill_production_sequence_3(ReferenceElement):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Skill/1/0"
    description: str = "The skill a step runs, the whole of it: running it is its Start, and its other commands are what ends it early."

class Abort(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "One command of a skill: the action that calls it, its Operation, and what it runs."
    InterfaceReference: Optional[ReferenceElement] = None
    SkillOperation: Dict[str, Operation] = {}
    Steps: Optional[Steps_t] = None

class Skill_production_sequence_4(ReferenceElement):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Skill/1/0"
    description: str = "The skill a step runs, the whole of it: running it is its Start, and its other commands are what ends it early."

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
    semantic_id: str = "https://smartproductionlab.aau.dk/skill"
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

# alias so field ``Steps_t`` can name a class of the same id_short
Steps_t: TypeAlias = Steps

# ── Resolve forward references (Pydantic circular refs) ──
Interfaces.model_rebuild()
NodeId.model_rebuild()
Kind.model_rebuild()
Name.model_rebuild()
Order.model_rebuild()
Skill_production_sequence.model_rebuild()
Value.model_rebuild()
SourceElement.model_rebuild()
InputReference.model_rebuild()
StepBinding.model_rebuild()
Bindings.model_rebuild()
OutputId.model_rebuild()
DataType.model_rebuild()
Unit.model_rebuild()
ResultReference.model_rebuild()
StepOutput.model_rebuild()
Outputs.model_rebuild()
BranchId.model_rebuild()
FlowBranch.model_rebuild()
Branches.model_rebuild()
ConditionType.model_rebuild()
Operator.model_rebuild()
EveryNProducts.model_rebuild()
CounterScope.model_rebuild()
Expected.model_rebuild()
OperandType.model_rebuild()
StepId.model_rebuild()
Operand.model_rebuild()
Condition.model_rebuild()
SkillStep.model_rebuild()
Steps.model_rebuild()
Start.model_rebuild()
Skill_production_sequence_2.model_rebuild()
Stop.model_rebuild()
Skill_production_sequence_3.model_rebuild()
Abort.model_rebuild()
Skill_production_sequence_4.model_rebuild()
Reset.model_rebuild()
Contract.model_rebuild()
Skill.model_rebuild()
Skills_2.model_rebuild()
Error.model_rebuild()
Errors.model_rebuild()
Skills.model_rebuild()
