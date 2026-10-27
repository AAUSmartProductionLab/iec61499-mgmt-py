# How a module is built: the rules

Rule set `https://smartproductionlab.aau.dk/rules/module/2` (27 Oct 2026): rule set 1 and, in
section 3, a flow: parallel blocks and decisions. A program by rule set 1 follows rule set 2.

A module that follows these rules can be verified, operated and given a new skill online from its
AAS and its running program alone. `modgen` generates such modules from a module spec, but the
rules are the contract, not the generator: a module written by hand in an IEC 61499 IDE inside
the same shell is as good. A module names the rule set it follows in its AAS (Skills, `RuleSet`).
A program that uses section 3's flows needs a FORTE built with the library's flow blocks.

The structure of a generated module and the reasons behind it are in [work.md](work.md); the two
lab modules in [modules.md](modules.md). Names in `<angle brackets>` are the module's own.

## 1. The shell

Fixed for every module; nothing here changes online.

1. One module is one application on one FORTE resource, published below `/Objects/<Module>` on
   the resource's OPC UA server.
2. `Occupation` (`modlib::MOD_Occupation`) and `Module` (`modlib::MOD_StateManager`) are the
   module level: who may command the module, and its PackML state.
3. Each equipment item is one block `<Item>` of type `<package>::EQ_<Item>`. It owns the item's
   IO points and knows nothing about what they mean. Each IO point is set by one input
   `<Point>_Address` (`STRING`) in the notation of FORTE's IDs: `gpio[<chip>:<line>]` (flags
   `:pull_up` or `:pull_down`, `:active_low`) or `pwm[<chip>:<channel>:<period ns>]` (a fourth
   field: the sysfs folder) for a Raspberry Pi's line, which the IO block sets up itself; a
   Modbus CLIENT's ID (`modbus[...]`); `sim`; or the name of a local IO handle set up elsewhere,
   as `IX` and `QX` take it. Empty means not connected: the point reports `QO = FALSE`. The same
   type then runs on every target, and an equipment block needs no other block for its IO; only
   the addresses differ.
4. Blocks reach equipment and occupation over FORTE local channels, not over connections:
   `loc[<Module>/owner]`, `loc[<Module>/<Item>/state]` and `.../cmd`, and one release channel for
   the module, `loc[<Module>/release]`: a holder named there gives up every item it holds. A block
   added online therefore needs no connection to them.
5. Every block has `INIT` and `INITO`. The application's blocks form one chain, started by the
   resource's own `START` block (`COLD` and `WARM`, drawn in the resource): IO lines,
   `Occupation`, `Module`, equipment, offered skill primitives, procedures, then the module level
   skills. A block added online is appended to the end of the chain.

## 2. A skill primitive

A skill primitive is a block type. It is the unit a module level skill is built from.

1. Its type is `<package>::SK_<Skill>`.
2. Events in: `INIT`, `START` (with the parameters), `HALT`, `ABORT`, `RESET`. Events out: `INITO`,
   `SUCCESS` (with the results) and `FAILURE` (with `ErrorID`).
3. Data in: `Module`, `UaRoot`, `UaPath`, `UaEnable`, `Methods`, `Holder`, `ReleaseAfter` (default
   `TRUE`), `Timeout` if a sensor ends it, and one input per parameter, named like the parameter,
   whose value is the default. Data out: `State`, `ErrorID` and `R_<result>` per result.
4. It publishes `State`, `ErrorID`, `Parameters/<p>` and `Results/<r>` below `UaRoot` + `UaPath`
   when `UaEnable` is set, and offers the methods `Start`, `Stop`, `Abort` and `Reset` there when
   `Methods` is set.
5. It takes its equipment under the name `Holder` and gives it up with its last command when it
   ends if `ReleaseAfter` is set. Instances with the same `Holder` share the equipment: that is how
   the steps of one module level skill keep it between them.
6. States and error codes are those of `modlib::SKILL_Core` (see *Skill interface* in
   [work.md](work.md)).

An offered primitive is an instance `<Skill>` of its type in the application, with
`UaPath = /Skills/<Skill>`, `Methods = TRUE`, `Holder = <Skill>` and `ReleaseAfter = TRUE`. A primitive
that is not offered has no instance of its own: it only runs as a step (a building block).

### An equipment item that keeps its position

An axis without a position sensor (a stepper motor with a limit switch) keeps its position itself.
Its equipment block `EQ_<Item>` then

1. publishes three more signals beside its inputs: `ActualPosition`, `Homed` (the position is
   known) and `Moving`. No IO point is behind them;
2. sets `ActualPosition` to the home position and `Homed` whenever its limit switch is on;
3. has the command `MoveTo`, whose argument is a position. It chooses the direction from where it
   is, drives for the time the distance takes at the axis' speed (the timer `MoveT`), switches off
   and is at the position. Without `Homed` it does not move;
4. when a move is cut short, is where the elapsed time puts it; when it is driven by any other
   command away from the switch, clears `Homed`.

A primitive that moves the axis to a position names the parameter that holds it (`move_to` in the
module description). It requires `Homed`, sends `MoveTo` with the parameter as the argument, and
ends when the item is no longer `Moving` and at the position. The parameter's limits lie within
the axis' travel: nothing else keeps the axis inside it.

## 3. A module level skill

A module level skill has no type of its own. It is a subapplication `<Skill>` that holds only
instances of library types and of skill primitives, so it can be created online. `<path>` is
`/Skills/<Skill>` and `<root>` the module's OPC UA root.

### Instances

| Instance | Type | Values |
| --- | --- | --- |
| `Control` | `modlib::SKILL_Core` | `Module`, `UaRoot`, `UaPath = <path>`, `UaEnable = TRUE`, `Methods`, `Holder = <Skill>`, `ReleaseAll = TRUE` if it uses equipment |
| `UaStart` | `iec61499::net::SERVER_2_<1 + parameters>` (OPC UA method) | `QI = Methods` |
| `<p>`, one per parameter, named like it | `modlib::SKILL_Param_<type>` | `Default`, and `Lower`, `Upper` if declared |
| `PubParams`, if it has parameters | `iec61499::net::PUBLISH_<parameters>` | `QI = TRUE`, `ID` writing `<root><path>/Parameters/<p>` |
| `PubResults`, if it has results | `iec61499::net::PUBLISH_<results>` | `QI = TRUE`, `ID` writing `<root><path>/Results/<r>` |
| `Execute` | subapplication, see below | |
| `Stop`, if it has a stop sequence | subapplication, see below | |

The OPC UA identifiers are written as values, since no type of the skill's own computes them.
In the IDE they are shown in four groups: Core (`Control`), Start (`UaStart`, the parameters,
`PubParams`), Sequences (`Execute`, `Stop`) and Results (`PubResults`).

### Connections

1. Start method: `Control.StartMethodId` → `UaStart.ID`; `UaStart.RD_1` → `Control.Session`;
   `Control.START_RSP` → `UaStart.RSP` with `Control.Accepted` → `UaStart.SD_1` and
   `Control.StartError` → `UaStart.SD_2`.
2. Parameters, in declared order. Check: `UaStart.IND` → first `.CHECK`; each `.CHECKED` → the
   next `.CHECK` with `.AllInRange` → `.PreviousInRange`; the last `.CHECKED` → `Control.START_REQ`
   with `.AllInRange` → `Control.ParamsInRange`. Latch: `Control.RUN` → first `.LATCH`; each
   `.LATCHED` → the next `.LATCH`; the last `.LATCHED` → `PubParams.REQ` and → `Execute.START`.
   Data: `UaStart.RD_<k+1>` → `<p>.Requested`, `Control.CalledByClient` → `<p>.CalledByClient`,
   `<p>.Value` → `PubParams.SD_<k>` and → `Execute.<p>`. `PubParams.INITO` → `PubParams.REQ`
   publishes the defaults once. Without parameters: `UaStart.IND` → `Control.START_REQ` and
   `Control.RUN` → `Execute.START`.
3. Run: `Control.HALT_SEQ`, `.ABORT_SEQ`, `.RESET_SEQ` → `Execute.HALT`, `.ABORT`, `.RESET`;
   `Execute.DONE` → `Control.EXECUTE_DONE`; `Execute.FAILED` → `Control.EXECUTE_FAILED` with
   `Execute.ErrorID` → `Control.ExecuteError`.
4. Results: `Execute.DONE` → `PubResults.REQ`, `Execute.<r>` → `PubResults.SD_<k>`.
5. Stop: `Control.RUN_STOPPING` → `Stop.START`; `Control.ABORT_SEQ` → `Stop.ABORT`;
   `Control.RESET_SEQ` → `Stop.RESET`; `Stop.DONE` and `Stop.FAILED` → `Control.STOPPING_DONE`.
   Without a stop sequence: `Control.RUN_STOPPING` → `Control.STOPPING_DONE`.
6. Release: none to wire. `Control` publishes `Holder` on `loc[<Module>/release]` whenever a run
   ends (succeeded, failed or aborted), so the skill gives up everything it still holds.
7. Initialisation: `INIT` → `Control` → `UaStart` → parameters → `PubParams` → `PubResults` →
   `Execute` → `Stop` → `INITO`, each `INITO` to the next `INIT`.

### A sequence (`Execute`, `Stop`)

A subapplication with `START` (with the skill's parameters), `HALT`, `ABORT`, `RESET` and `INIT`
in, and `DONE` (with the results), `FAILED` (with `ErrorID`) and `INITO` out.

1. One instance per step, named like the step, of the step's skill primitive type, with `Module`,
   `UaRoot`, `UaEnable = TRUE`, `UaPath = <path>/Execute/<step>` (`<path>/Stopping/<step>` in a stop
   sequence), `Methods = FALSE`, `Holder = <Skill>`, and `ReleaseAfter = TRUE` only on the last step
   that uses its equipment item.
2. A constant bound to a step's parameter is the value of that input. A parameter of the skill
   bound to it is a data connection from the sequence's input. Either stays within the limits of
   the step's parameter and has its type: a skill started by a parent does not check its values
   (only a `Start` over OPC UA is range checked), so whoever builds the sequence has to.
3. `START` → the first step's `START`; each step's `SUCCESS` → the next step's `START`; the last
   `SUCCESS` → `DONE`. `HALT`, `ABORT` and `RESET` go to every step.
4. Failures are merged pairwise by `Fail<i>` (`modlib::SKILL_FailMerge`), since a data input takes
   one connection; the last merge gives `FAILED` and `ErrorID`. A single step is connected directly.
5. A result `<step>.<result>` is a data connection from the step's `R_<result>` to the output.
6. `INIT` → first step, each `INITO` → the next `INIT`, the last → `INITO`.

A procedure of the module (`Resetting`, `Stopping`) is a sequence in the application itself,
published below `/Procedures/<name>`, without `HALT`, `ABORT` and `RESET`; each of its steps takes
and gives up its equipment itself. `Module.RUN_<NAME>` starts it, and its `DONE` and `FAILED` go to
`Module.<NAME>_DONE` and `Module.<NAME>_FAILED`.

### A flow (rule set 2)

A sequence's steps may also run in parallel blocks and decisions, nested as deep as needed. A flow
is still only instances of library types and of the module's primitives, so it is created online
like any module level skill. Besides the steps (rule 1 of a sequence, unchanged) it holds:

| Block | Instance | Type | Connections |
| --- | --- | --- | --- |
| A parallel block of n branches (2 to 4) | `<block>`, its name | `modlib::SKILL_Join<n>` | The event that starts the block goes to `<block>.START` first, then to the first step of every branch. Branch i's last `SUCCESS` goes to `<block>.DONE_<i>`, its failures (merged by `<block>_Fail<i>_<k>`, `SKILL_FailMerge`) to `<block>.FAILED_<i>` with `Error<i>`. `<block>.HALT` goes to the `HALT` of every step in the block. `<block>.DONE` goes on; `<block>.FAILED` with `Error` is a failure of the flow |
| A decision | `<block>`, its name | `modlib::SKILL_Merge` | The event that reaches the decision goes to the `EVAL` of its first condition. `YES` leads to the first step of the first branch, `NO` to the second branch's or, if it has none (a conditional step), to `<block>.EI2`. The first branch's last `SUCCESS` goes to `<block>.EI1`, the second's to `<block>.EI2`; `<block>.EO` goes on. The branches' failures are failures of the flow |
| A comparison of a decision | `<block>_C<k>`, k from 1 | `modlib::SKILL_Condition_LREAL` or `_BOOL` | `Operand` from a parameter latch's `Value` (a parameter of the skill) or from a step's `R_<result>` (a step that has run on every path to it); `Expected` and `Operator` (`'eq'`, `'ne'`, `'gt'`, `'gte'`, `'lt'`, `'lte'`; a Boolean `eq` or `ne`) written as values. In a group where all must hold, `YES` evaluates the next comparison and every `NO` leads to the second branch; where one must hold, `NO` evaluates the next and every `YES` leads to the first branch |

1. Two branches of a parallel block use no equipment item in common: every step holds the skill's
   items under the skill's name.
2. Every step of a flow has `ReleaseAfter = FALSE`: which step uses an item last depends on the
   path. `Control` gives up everything the skill holds when a run ends (rule 3.6).
3. A result of the skill comes from a step outside every decision, so it is set on every path.
4. The INIT chain runs through the steps in the order they are written; the flow blocks have no
   `INIT`, like `SKILL_FailMerge`.
5. A flow without blocks is a sequence and is built as above, unchanged.

## 4. What changes online

1. **A new module level skill**, also one with a flow: the instances and connections of section 3 are created, its
   `INIT` is linked to the end of the application's chain, and `Control.INIT` is triggered once.
2. **A parameter value**: the input holding it is written; the skill takes it over at its next
   start. It is `<instance>.<parameter>` on a primitive instance (the default of an offered
   primitive, or the constant of a step), and `<Skill>.<parameter>.Default` for a module level
   skill. The value has to lie within the parameter's limits; the controller does not refuse a
   write.
3. Types do not change online: a new skill primitive or equipment item needs a new program.

## 5. What the AAS states of this

| In the program | In the AAS |
| --- | --- |
| Equipment item that a skill moves | A component: an AAS of its own (`<Module><Item>AAS`), a part in the module's Hierarchical Structures |
| Skill primitive | In its component's Skills: `Skills/<Skill>` with the semantic id `skill`, the kind `skill/Primitive` and its type `skills/<Skill>` as supplemental ids, its commands and its `Contract` |
| Module level skill | In the module's Skills: `Skills/<Skill>` with the semantic id `skill`, the kind `skill/Composite` and its type, and its commands |
| A command (the method, what it takes and answers) | `<Skill>/<Command>`: `InterfaceReference` to the action, the Operation named like the command |
| A parameter, a result | An input or output variable of the Start Operation, with value, unit and limits |
| `Execute` and `Stop` sequences | `Start/Steps` and `Stop/Steps`: `Step_0000`, ... in the elements of the planner's Production Sequence (`NodeId` = the instance name, `Kind` = `step`, `Order`), each with the `Skill` it runs |
| A parallel block, a decision (rule set 2) | A step of the kind `parallel` with `Branches/Branch_<j>/Steps`; `decision` with a `Condition` and two `Branches`; `conditional` with a `Condition` and its own `Steps`. `NodeId` = the block's instance name. A `Condition` is a comparison (`ConditionType comparison`, `Operator`, `Expected` with `DataType` and `Value`, `Unit`, `Operand`: `OperandType parameter` with `SourceElement`, or `output` with `StepId` and `OutputId`) or a group (`all`, `any`) of `Conditions/Condition_<k>` with their `Order` |
| A step's constant; a value handed down | The step's `Bindings`: a `Binding` with `Value`, or with `SourceElement` referring to the command's variable; a result is an `Output` with `ResultReference` |
| Procedures `Resetting`, `Stopping` | The steps of the `Start` of the skills `Reset` and `Stop` (kind `skill/ModuleControl`) |
| Module commands, Occupy and Release | Skills of the kind `skill/ModuleControl` in the module's Skills, each called by its `Start` |
| The rule set | Skills, `RuleSet` |
| Whether the program carries a module level skill out | The skill's `Deployment`: `Built`, or `Described` (in the AAS only) |
| Which block is which skill or step | Not in the AAS: the integrator's record (a Control Configuration submodel kept by the registration service or in a folder), `Instances`: `InstancePath`, `FBType`, `TypeHash`, `Skill`; it follows from the rules anyway |
| Block types and their hashes, as read | The integrator's record, `Types` |
