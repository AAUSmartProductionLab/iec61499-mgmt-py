# How a module is built: the rules

Rule set `https://smartproductionlab.aau.dk/rules/module/1`.

A module that follows these rules can be verified, operated and given a new skill online from its
AAS and its running program alone. `modgen` generates such modules from a module spec, but the
rules are the contract, not the generator: a module written by hand in an IEC 61499 IDE inside
the same shell is as good. A module names the rule set it follows in its AAS (Control
Configuration, `Rules`).

The structure of a generated module and the reasons behind it are in [work.md](work.md); the two
lab modules in [modules.md](modules.md). Names in `<angle brackets>` are the module's own.

## 1. The shell

Fixed for every module; nothing here changes online.

1. One module is one application on one FORTE resource, published below `/Objects/<Module>` on
   the resource's OPC UA server.
2. `Occupation` (`modlib::MOD_Occupation`) and `Module` (`modlib::MOD_StateManager`) are the
   module level: who may command the module, and its PackML state.
3. Each equipment item is one block `<Item>` of type `<package>::EQ_<Item>`. It owns the item's
   IO points and knows nothing about what they mean.
4. Blocks reach equipment and occupation over FORTE local channels, not over connections:
   `loc[<Module>/owner]`, `loc[<Module>/<Item>/state]`, `.../cmd` and `.../release`. A block added
   online therefore needs no connection to them.
5. Every block has `INIT` and `INITO`. The application's blocks form one chain from the boot
   event: IO lines, `Occupation`, `Module`, equipment, offered skill primitives, procedures, then
   the module level skills. A block added online is appended to the end of the chain.

## 2. A skill primitive

A skill primitive is a block type. It is the unit a module level skill is built from.

1. Its type is `<package>::SK_<Skill>`.
2. Events in: `INIT`, `START` (with the parameters), `HALT`, `ABORT`, `RESET`. Events out: `INITO`,
   `SUCCESS` (with the results) and `FAILURE` (with `ErrorID`).
3. Data in: `Module`, `UaRoot`, `UaPath`, `UaEnable`, `Methods`, `Token`, `LastUse` (default
   `TRUE`), `Timeout` if a sensor ends it, and one input per parameter, named like the parameter,
   whose value is the default. Data out: `State`, `ErrorID` and `R_<result>` per result.
4. It publishes `State`, `ErrorID`, `Parameters/<p>` and `Results/<r>` below `UaRoot` + `UaPath`
   when `UaEnable` is set, and offers the methods `Start`, `Stop`, `Abort` and `Reset` there when
   `Methods` is set.
5. It takes its equipment under the name `Token` and gives it up when it ends if `LastUse` is
   set. Instances with the same `Token` share the equipment: that is how the steps of one module
   level skill keep it between them.
6. States and error codes are those of `modlib::SKILL_Core` (see *Skill interface* in
   [work.md](work.md)).

An offered primitive is an instance `<Skill>` of its type in the application, with
`UaPath = /Skills/<Skill>`, `Methods = TRUE`, `Token = <Skill>` and `LastUse = TRUE`. A primitive
that is not offered has no instance of its own: it only runs as a step (a building block).

## 3. A module level skill

A module level skill has no type of its own. It is a subapplication `<Skill>` that holds only
instances of library types and of skill primitives, so it can be created online. `<path>` is
`/Skills/<Skill>` and `<root>` the module's OPC UA root.

### Instances

| Instance | Type | Values |
| --- | --- | --- |
| `Control` | `modlib::SKILL_Core` | `Module`, `UaRoot`, `UaPath = <path>`, `UaEnable = TRUE`, `Methods` |
| `UaStart` | `iec61499::net::SERVER_2_<1 + parameters>` (OPC UA method) | `QI = Methods` |
| `<p>`, one per parameter, named like it | `modlib::SKILL_Param_<type>` | `Default`, and `Lower`, `Upper` if declared |
| `PubParams`, if it has parameters | `iec61499::net::PUBLISH_<parameters>` | `QI = TRUE`, `ID` writing `<root><path>/Parameters/<p>` |
| `PubResults`, if it has results | `iec61499::net::PUBLISH_<results>` | `QI = TRUE`, `ID` writing `<root><path>/Results/<r>` |
| `Release`, if it uses equipment | `modlib::SKILL_Release` | `Token = <Skill>` |
| `Rel_<Item>`, one per equipment item | `iec61499::net::PUBLISH_1` | `QI = TRUE`, `ID = loc[<Module>/<Item>/release]` |
| `Execute` | subapplication, see below | |
| `Stop`, if it has a stop sequence | subapplication, see below | |

The OPC UA identifiers are written as values, since no type of the skill's own computes them.

### Connections

1. Start method: `Control.IdStart` → `UaStart.ID`; `UaStart.RD_1` → `Control.S_Start`;
   `Control.RSP_START` → `UaStart.RSP` with `Control.Accepted` → `UaStart.SD_1` and
   `Control.RspError` → `UaStart.SD_2`.
2. Parameters, in declared order. Check: `UaStart.IND` → first `.CHECK`; each `.CHECKED` → the
   next `.CHECK` with `.InRange` → `.OkIn`; the last `.CHECKED` → `Control.CMD_START` with
   `.InRange` → `Control.InRange`. Latch: `Control.GO` → first `.LATCH`; each `.LATCHED` → the next
   `.LATCH`; the last `.LATCHED` → `PubParams.REQ` and → `Execute.START`. Data: `UaStart.RD_<k+1>` →
   `<p>.S`, `Control.FromUa` → `<p>.FromUa`, `<p>.P` → `PubParams.SD_<k>` and → `Execute.<p>`.
   `PubParams.INITO` → `PubParams.REQ` publishes the defaults once.
   Without parameters: `UaStart.IND` → `Control.CMD_START` and `Control.GO` → `Execute.START`.
3. Run: `Control.HALT_O`, `.ABORT_O`, `.RESET_O` → `Execute.HALT`, `.ABORT`, `.RESET`;
   `Execute.DONE` → `Control.EXEC_DONE`; `Execute.FAILED` → `Control.EXEC_FAILED` with
   `Execute.ErrorID` → `Control.ExecError`.
4. Results: `Execute.DONE` → `PubResults.REQ`, `Execute.<r>` → `PubResults.SD_<k>`.
5. Stop: `Control.RUN_STOP` → `Stop.START`; `Control.ABORT_O` → `Stop.ABORT`; `Control.RESET_O` →
   `Stop.RESET`; `Stop.DONE` and `Stop.FAILED` → `Control.STOP_DONE`. Without a stop sequence:
   `Control.RUN_STOP` → `Control.STOP_DONE`.
6. Release: `Control.FAILURE` and `Control.ABORT_O` → `Release.REQ`; `Release.CNF` → each
   `Rel_<Item>.REQ` with `Release.Holder` → `Rel_<Item>.SD_1`.
7. Initialisation: `INIT` → `Control` → `UaStart` → parameters → `PubParams` → `PubResults` →
   `Rel_<Item>` → `Execute` → `Stop` → `INITO`, each `INITO` to the next `INIT`.

### A sequence (`Execute`, `Stop`)

A subapplication with `START` (with the skill's parameters), `HALT`, `ABORT`, `RESET` and `INIT`
in, and `DONE` (with the results), `FAILED` (with `ErrorID`) and `INITO` out.

1. One instance per step, named like the step, of the step's skill primitive type, with `Module`,
   `UaRoot`, `UaEnable = TRUE`, `UaPath = <path>/Execute/<step>` (`<path>/Stopping/<step>` in a stop
   sequence), `Methods = FALSE`, `Token = <Skill>`, and `LastUse = TRUE` only on the last step that
   uses its equipment item.
2. A constant bound to a step's parameter is the value of that input. A parameter of the skill
   bound to it is a data connection from the sequence's input.
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

## 4. What changes online

1. **A new module level skill**: the instances and connections of section 3 are created, its
   `INIT` is linked to the end of the application's chain, and `Control.INIT` is triggered once.
2. **A parameter value**: the input holding it is written; the skill takes it over at its next
   start. It is `<instance>.<parameter>` on a primitive instance (the default of an offered
   primitive, or the constant of a step), and `<Skill>.<parameter>.Default` for a module level
   skill.
3. Types do not change online: a new skill primitive or equipment item needs a new program.

## 5. What the AAS states of this

| In the program | In the AAS (Skills submodel unless noted) |
| --- | --- |
| Offered skill primitive | `Skills/<Skill>` with `Kind = Primitive`; `Implementation`: `FBType`, `InstancePath` |
| Skill primitive that is not offered | `BuildingBlocks/<Skill>`; `Implementation`: `FBType` |
| Its parameters, contract, equipment | `Parameters` (unit, limits, default), `Contract`, `Occupies` |
| Module level skill | `Skills/<Skill>` with `Kind = Composite`; `Implementation` is its `Control` |
| Its sequences | `Execute`, `Stop`: per step the `Skill` it runs, its `InstancePath` and `Bindings` |
| Procedures | `Procedures/<name>`, steps as above |
| Block types and their hashes, as read | Control Configuration, `Types` |
| The rule set | Control Configuration, `Rules` |
