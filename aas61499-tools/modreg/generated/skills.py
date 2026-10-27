"""Skills - generated from IDTA template.
Source: modreg/templates/Skills.json
"""

from __future__ import annotations

from typing import Any, ClassVar, List, Dict, Optional, TypeAlias
from aas_pydantic import (
    Operation, Property, ReferenceElement, Submodel, SubmodelElement, SubmodelElementCollection, SubmodelElementList,
)
from pydantic import Field
from aas_pydantic.aas_model import AasIdString
from aas_model.submodel_templates import SkillOperation as DelegatedOperation

class Deployment(Property):
    id_short: AasIdString = "Deployment"
    description: str = "Built: the resource's program carries the skill out; Described: the skill is in the AAS only and is offered after a reconfiguration."
    value_type: str = "xs:string"

class SemanticId(Property):
    id_short: AasIdString = "SemanticId"
    description: str = "What the skill does, as the short form of older AASs states it."
    value_type: str = "xs:string"

class InterfaceReference(ReferenceElement):
    id_short: AasIdString = "InterfaceReference"
    description: str = "The AID action (arso:InterfaceSMC/InteractionMetadata/actions/{action}) that calls the command; in the short form, the action that starts the skill."

class SkillOperation(DelegatedOperation):
    description: str = "Operation \u2014 the invocable Operation of a command (named like it), or in the short form of a skill (named like the skill)."

class NodeId(Property):
    id_short: AasIdString = "NodeId"
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/NodeId/1/0"
    description: str = "The node's identifier, unique in its command."
    value_type: str = "xs:string"

class Kind(Property):
    id_short: AasIdString = "Kind"
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Kind/1/0"
    description: str = "Step, parallel, decision or conditional."
    value_type: str = "xs:string"

class Name(Property):
    id_short: AasIdString = "Name"
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Name/1/0"
    description: str = "What a step, a branch or an output is called for a person; of a Binding, the input of the step's skill it is about."
    value_type: str = "xs:string"

class Order(Property):
    id_short: AasIdString = "Order"
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Order/1/0"
    description: str = "The position among its siblings, from 0; it decides the order, not the place in the collection."
    value_type: str = "xs:string"

class Skill_production_sequence(ReferenceElement):
    id_short: AasIdString = "Skill"
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Skill/1/0"
    description: str = "The skill a step runs, the whole of it: running it is its Start, and its other commands are what ends it early."

class Value(Property):
    id_short: AasIdString = "Value"
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Value/1/0"
    description: str = "A constant: what a Binding hands to the input (the value as it runs), or what a Condition compares with."
    value_type: str = "xs:string"

class SourceElement(ReferenceElement):
    id_short: AasIdString = "SourceElement"
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/SourceElement/1/0"
    description: str = "The variable of the command's Operation that is handed down to the input, or that a Condition looks at."

class InputReference(ReferenceElement):
    id_short: AasIdString = "InputReference"
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/InputReference/1/0"
    description: str = "The input itself: the variable of the Start Operation of the step's skill."

class StepBinding(SubmodelElementCollection):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Binding/1/0"
    description: str = "One input of the step's skill (Name): a constant (Value) or a variable of the command's Operation (SourceElement)."
    Name: Name_t
    Value: Optional[Value_t] = None
    SourceElement: Optional[SourceElement_t] = None
    InputReference: Optional[InputReference_t] = None

class Bindings(SubmodelElementCollection):
    id_short: AasIdString = "Bindings"
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Bindings/1/0"
    description: str = "What the inputs of the step's skill are handed."
    StepBinding: Dict[str, StepBinding_t] = {}

class OutputId(Property):
    id_short: AasIdString = "OutputId"
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/OutputId/1/0"
    description: str = "The output's identifier: the idShort of the output variable of the command's Operation."
    value_type: str = "xs:string"

class DataType(Property):
    id_short: AasIdString = "DataType"
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/DataType/1/0"
    description: str = "Boolean, number or string."
    value_type: str = "xs:string"

class Unit(Property):
    id_short: AasIdString = "Unit"
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Unit/1/0"
    description: str = "The unit of an output or of what a Condition compares; empty for none."
    value_type: str = "xs:string"

class ResultReference(ReferenceElement):
    id_short: AasIdString = "ResultReference"
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/ResultReference/1/0"
    description: str = "The result: an output variable of the Start Operation of the step's skill."

class StepOutput(SubmodelElementCollection):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Output/1/0"
    description: str = "One result: OutputId names the output variable of the command's Operation, ResultReference the result of the step's skill it is."
    Name: Optional[Name_t] = None
    OutputId: OutputId_t
    DataType: Optional[DataType_t] = None
    Unit: Optional[Unit_t] = None
    ResultReference: Optional[ResultReference_t] = None

class Outputs(SubmodelElementCollection):
    id_short: AasIdString = "Outputs"
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Outputs/1/0"
    description: str = "The results of the command that this step gives."
    StepOutput: Dict[str, StepOutput_t] = {}

class BranchId(Property):
    id_short: AasIdString = "BranchId"
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/BranchId/1/0"
    description: str = "The branch's identifier, unique in its command."
    value_type: str = "xs:string"

class FlowBranch(SubmodelElementCollection):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Branch/1/0"
    description: str = "One branch: BranchId, Name, Order and its Steps."
    Steps: Optional[Steps_t] = None
    Name: Name_t
    Order: Order_t
    BranchId: BranchId_t

class Branches(SubmodelElementCollection):
    id_short: AasIdString = "Branches"
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Branches/1/0"
    description: str = "The branches of a parallel step (two or more, all have to end) or of a decision (exactly two)."
    FlowBranch: Dict[str, FlowBranch_t] = {}

class FlowConditions(SubmodelElementCollection):
    id_short: AasIdString = "Conditions"
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Conditions/1/0"
    description: str = "The conditions of a group: all of them hold (ConditionType all) or one does (any)."
    Condition: Dict[str, Condition_t] = Field(default_factory=dict, json_schema_extra={"idta_min_cardinality": 1})

class ConditionType(Property):
    id_short: AasIdString = "ConditionType"
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/ConditionType/1/0"
    description: str = "EveryNthProduct, comparison, all or any."
    value_type: str = "xs:string"

class Operator(Property):
    id_short: AasIdString = "Operator"
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Operator/1/0"
    description: str = "Eq, ne, gt, gte, lt or lte."
    value_type: str = "xs:string"

class EveryNProducts(Property):
    id_short: AasIdString = "EveryNProducts"
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/EveryNProducts/1/0"
    description: str = "The condition holds on every N-th run."
    value_type: str = "xs:string"

class CounterScope(Property):
    id_short: AasIdString = "CounterScope"
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/CounterScope/1/0"
    description: str = "What the runs are counted over."
    value_type: str = "xs:string"

class Expected(SubmodelElementCollection):
    id_short: AasIdString = "Expected"
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Expected/1/0"
    description: str = "What the operand is compared with: DataType and Value."
    Value: Optional[Value_t] = None
    DataType: Optional[DataType_t] = None

class OperandType(Property):
    id_short: AasIdString = "OperandType"
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/OperandType/1/0"
    description: str = "Parameter or output."
    value_type: str = "xs:string"

class StepId(Property):
    id_short: AasIdString = "StepId"
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/StepId/1/0"
    description: str = "The NodeId of the step whose output is compared."
    value_type: str = "xs:string"

class Operand(SubmodelElementCollection):
    id_short: AasIdString = "Operand"
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Operand/1/0"
    description: str = "What is compared: a variable of the command's Operation (OperandType parameter: SourceElement) or the output of an earlier step (OperandType output: StepId, OutputId)."
    SourceElement: Optional[SourceElement_t] = None
    OutputId: Optional[OutputId_t] = None
    OperandType: Optional[OperandType_t] = None
    StepId: Optional[StepId_t] = None

class FlowCondition(SubmodelElementCollection):
    id_short: AasIdString = "Condition"
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Condition/1/0"
    description: str = "What a decision or a conditional step looks at: every N-th run (ConditionType everyNthProduct: EveryNProducts, CounterScope), a comparison (ConditionType comparison: Operand, Operator, Expected, Unit), or a group (ConditionType all or any: Conditions)."
    Order: Optional[Order_t] = None
    Unit: Optional[Unit_t] = None
    Conditions: Optional[Conditions_t] = None
    ConditionType: Optional[ConditionType_t] = None
    Operator: Optional[Operator_t] = None
    EveryNProducts: Optional[EveryNProducts_t] = None
    CounterScope: Optional[CounterScope_t] = None
    Expected: Optional[Expected_t] = None
    Operand: Optional[Operand_t] = None

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

class Steps(SubmodelElementCollection):
    id_short: AasIdString = "Steps"
    semantic_id: str = "https://smartproductionlab.aau.dk/ProductionSequence/Steps/1/0"
    description: str = "What a command runs (or a branch, or the body of a conditional step): steps in the order of their Order."
    SkillStep: Dict[str, SkillStep_t] = {}

class Start(SubmodelElementCollection):
    id_short: AasIdString = "Start"
    semantic_id: str = ""
    description: str = "One command of a skill: the action that calls it, its Operation, and what it runs."
    InterfaceReference: Optional[InterfaceReference_t] = None
    SkillOperation: Dict[str, SkillOperation_t] = {}
    Steps: Optional[Steps_t] = None

class Stop(SubmodelElementCollection):
    id_short: AasIdString = "Stop"
    semantic_id: str = ""
    description: str = "One command of a skill: the action that calls it, its Operation, and what it runs."
    InterfaceReference: Optional[InterfaceReference_t] = None
    SkillOperation: Dict[str, SkillOperation_t] = {}
    Steps: Optional[Steps_t] = None

class Abort(SubmodelElementCollection):
    id_short: AasIdString = "Abort"
    semantic_id: str = ""
    description: str = "One command of a skill: the action that calls it, its Operation, and what it runs."
    InterfaceReference: Optional[InterfaceReference_t] = None
    SkillOperation: Dict[str, SkillOperation_t] = {}
    Steps: Optional[Steps_t] = None

class Reset(SubmodelElementCollection):
    id_short: AasIdString = "Reset"
    semantic_id: str = ""
    description: str = "One command of a skill: the action that calls it, its Operation, and what it runs."
    InterfaceReference: Optional[InterfaceReference_t] = None
    SkillOperation: Dict[str, SkillOperation_t] = {}
    Steps: Optional[Steps_t] = None

class Requires(Property):
    id_short: AasIdString = "Requires"
    description: str = "The precondition: what has to hold when the skill starts."
    value_type: str = "xs:string"

class Ensures(Property):
    id_short: AasIdString = "Ensures"
    description: str = "The postcondition: the skill has succeeded when it holds (a sensor ends it)."
    value_type: str = "xs:string"

class After(Property):
    id_short: AasIdString = "After"
    description: str = "The open-loop duration: the skill has succeeded when it has passed, in seconds (a time ends it)."
    value_type: str = "xs:string"

class Invariant(Property):
    id_short: AasIdString = "Invariant"
    description: str = "What has to hold all the while the skill runs."
    value_type: str = "xs:string"

class Timeout(Property):
    id_short: AasIdString = "Timeout"
    description: str = "The longest the skill may run, a duration."
    value_type: str = "xs:string"

class Contract(SubmodelElementCollection):
    id_short: AasIdString = "Contract"
    semantic_id: str = ""
    description: str = "For primitive skills: Requires (precondition), Ensures (postcondition) or After (open-loop duration), Invariant, Timeout."
    Requires: Optional[Requires_t] = None
    Ensures: Optional[Ensures_t] = None
    After: Optional[After_t] = None
    Invariant: Optional[Invariant_t] = None
    Timeout: Optional[Timeout_t] = None

class StateMachine(Property):
    id_short: AasIdString = "StateMachine"
    description: str = "Present only on asynchronous skills of the short form."
    value_type: str = "xs:string"

class Skill(SubmodelElementCollection):
    semantic_id: str = "https://smartproductionlab.aau.dk/skill"
    description: str = "A named skill, an element of the Skills submodel itself, recognised by its semanticId (no idShort \u2014 the skill name is user-defined)."
    Deployment: Optional[Deployment_t] = None
    SemanticId: Optional[SemanticId_t] = None
    Start: Optional[Start_t] = None
    Stop: Optional[Stop_t] = None
    Abort: Optional[Abort_t] = None
    Reset: Optional[Reset_t] = None
    InterfaceReference: Optional[InterfaceReference_t] = None
    SkillOperation: Dict[str, SkillOperation_t] = {}
    Contract: Optional[Contract_t] = None
    StateMachine: Optional[StateMachine_t] = None

class RuleSet(Property):
    id_short: AasIdString = "RuleSet"
    description: str = "The rule set the resource's program is built by, named by its URI. It says that the program can be read back by the rules and that a described skill can be built online; a tool that does not know the rule set does not change the program."
    value_type: str = "xs:string"

class SkillError(Property):
    description: str = "A named error; its value is the code an ErrorID carries."
    value_type: str = "xs:integer"

class Errors(SubmodelElementCollection):
    id_short: AasIdString = "Errors"
    semantic_id: str = ""
    description: str = "What the ErrorID in the answer of an Operation can be: one property per error."
    SkillError: Dict[str, SkillError_t] = {}

class Skills(Submodel):
    id_short: AasIdString = "Skills"
    semantic_id: str = "https://smartproductionlab.aau.dk/ARSO/Skills/1/0/Submodel"
    description: str = "The Skills submodel (ARSO): a resource's skills with their commands and steps, and the errors they report."
    VERSION: ClassVar[str] = "1"
    REVISION: ClassVar[str] = "0"
    Skill: Dict[str, Skill_t] = {}
    RuleSet: Optional[RuleSet_t] = None
    Errors: Errors_t

# alias so field ``Name_t`` can name a class of the same id_short
Name_t: TypeAlias = Name
# alias so field ``Value_t`` can name a class of the same id_short
Value_t: TypeAlias = Value
# alias so field ``SourceElement_t`` can name a class of the same id_short
SourceElement_t: TypeAlias = SourceElement
# alias so field ``InputReference_t`` can name a class of the same id_short
InputReference_t: TypeAlias = InputReference
# alias so field ``StepBinding_t`` can name a class of the same id_short
StepBinding_t: TypeAlias = StepBinding
# alias so field ``OutputId_t`` can name a class of the same id_short
OutputId_t: TypeAlias = OutputId
# alias so field ``DataType_t`` can name a class of the same id_short
DataType_t: TypeAlias = DataType
# alias so field ``Unit_t`` can name a class of the same id_short
Unit_t: TypeAlias = Unit
# alias so field ``ResultReference_t`` can name a class of the same id_short
ResultReference_t: TypeAlias = ResultReference
# alias so field ``StepOutput_t`` can name a class of the same id_short
StepOutput_t: TypeAlias = StepOutput
# alias so field ``Steps_t`` can name a class of the same id_short
Steps_t: TypeAlias = Steps
# alias so field ``Order_t`` can name a class of the same id_short
Order_t: TypeAlias = Order
# alias so field ``BranchId_t`` can name a class of the same id_short
BranchId_t: TypeAlias = BranchId
# alias so field ``FlowBranch_t`` can name a class of the same id_short
FlowBranch_t: TypeAlias = FlowBranch
# alias so field ``Condition_t`` can name a class of the same id_short
Condition_t: TypeAlias = FlowCondition
# alias so field ``OperandType_t`` can name a class of the same id_short
OperandType_t: TypeAlias = OperandType
# alias so field ``StepId_t`` can name a class of the same id_short
StepId_t: TypeAlias = StepId
# alias so field ``Conditions_t`` can name a class of the same id_short
Conditions_t: TypeAlias = FlowConditions
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
# alias so field ``SkillStep_t`` can name a class of the same id_short
SkillStep_t: TypeAlias = SkillStep
# alias so field ``InterfaceReference_t`` can name a class of the same id_short
InterfaceReference_t: TypeAlias = InterfaceReference
# alias so field ``SkillOperation_t`` can name a class of the same id_short
SkillOperation_t: TypeAlias = SkillOperation
# alias so field ``Requires_t`` can name a class of the same id_short
Requires_t: TypeAlias = Requires
# alias so field ``Ensures_t`` can name a class of the same id_short
Ensures_t: TypeAlias = Ensures
# alias so field ``After_t`` can name a class of the same id_short
After_t: TypeAlias = After
# alias so field ``Invariant_t`` can name a class of the same id_short
Invariant_t: TypeAlias = Invariant
# alias so field ``Timeout_t`` can name a class of the same id_short
Timeout_t: TypeAlias = Timeout
# alias so field ``Deployment_t`` can name a class of the same id_short
Deployment_t: TypeAlias = Deployment
# alias so field ``SemanticId_t`` can name a class of the same id_short
SemanticId_t: TypeAlias = SemanticId
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
# alias so field ``StateMachine_t`` can name a class of the same id_short
StateMachine_t: TypeAlias = StateMachine
# alias so field ``SkillError_t`` can name a class of the same id_short
SkillError_t: TypeAlias = SkillError
# alias so field ``Skill_t`` can name a class of the same id_short
Skill_t: TypeAlias = Skill
# alias so field ``RuleSet_t`` can name a class of the same id_short
RuleSet_t: TypeAlias = RuleSet
# alias so field ``Errors_t`` can name a class of the same id_short
Errors_t: TypeAlias = Errors
# ── Resolve forward references (Pydantic circular refs) ──
Deployment.model_rebuild()
SemanticId.model_rebuild()
InterfaceReference.model_rebuild()
SkillOperation.model_rebuild()
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
FlowConditions.model_rebuild()
ConditionType.model_rebuild()
Operator.model_rebuild()
EveryNProducts.model_rebuild()
CounterScope.model_rebuild()
Expected.model_rebuild()
OperandType.model_rebuild()
StepId.model_rebuild()
Operand.model_rebuild()
FlowCondition.model_rebuild()
SkillStep.model_rebuild()
Steps.model_rebuild()
Start.model_rebuild()
Stop.model_rebuild()
Abort.model_rebuild()
Reset.model_rebuild()
Requires.model_rebuild()
Ensures.model_rebuild()
After.model_rebuild()
Invariant.model_rebuild()
Timeout.model_rebuild()
Contract.model_rebuild()
StateMachine.model_rebuild()
Skill.model_rebuild()
RuleSet.model_rebuild()
SkillError.model_rebuild()
Errors.model_rebuild()
Skills.model_rebuild()
