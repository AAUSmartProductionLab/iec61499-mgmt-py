# From the AAS to IEC 61499 and back

Material for the paper (27 Oct 2026): how a module's AAS becomes the target state of its control
program, how its elements map to IEC 61499 blocks, and the few design choices that make that mapping
cheap in both directions. Figures: [figures/mapping.drawio](figures/mapping.drawio) (three pages: a
skill and its blocks; the flow kinds as library blocks; the AAS as the target) and, smaller for the
paper, [figures/skill-blocks.drawio](figures/skill-blocks.drawio) (a primitive is a block type, a
composite a subapplication of instances; what the AAS says of a sequence and a parallel block, and
the wiring the rules draw around it). How the tools run is
[tools.md](tools.md); the rules themselves are [module-rules.md](module-rules.md).

## 1. The AAS is the target state

Three descriptions of one module exist: the **spec** it was generated from (the vendor's only), its
**AAS** (delivered with it, read by every client), and its **running program** (what is true). The
method takes the AAS as the module's target: a reconfiguration is an edit of the AAS, and a tool brings
the program to it. This is desired-state reconciliation, as a Kubernetes controller does it for a
cluster or the models@run.time line of work proposes for adaptive systems, applied to an IEC 61499
program and with the AAS as the model.

Written as functions: let `described` take an AAS to a structure (what is wanted), and `read` take a
running program to a structure of the same form (what runs, read back by the module rules). The
module is what its AAS describes when `read(program) = described(AAS)`. `reconfigure` changes the
program by management commands until that holds, if the difference lies in what may change online,
and refuses otherwise. Afterwards it reads the program again and checks the equation; then it writes
down what it did: in the AAS (the skill is `Built`, its interface is there) and in the integrator's
record outside the AAS (which blocks, which types and hashes, a change log).

Why the AAS and not the spec: the AAS is what every module is delivered with and what every client
already reads (the planner matches a product's need against it, the HMI and `modlink` call skills
through it). A module from another vendor has no spec of ours. With the AAS as the target, describing,
operating and changing a module meet in one document.

## 2. A small language and its compiler

A module level skill's `Steps` are a small flow language, the same as a product's recipe in the process
planner: steps that run a component's skill with bound inputs, parallel blocks, decisions and
conditional steps, conditions that compare a parameter or an earlier step's result with a value, in
groups of all or any. Its target "instruction set" is fixed and small: the module's skill primitives
(block types, one per skill of a component) and five library types (`SKILL_Core` and the parameter
latch for the skill itself; `SKILL_Join<n>`, `SKILL_Condition_<type>` and `SKILL_Merge` for the flow).

Translating a skill is compiling: each construct has one fixed pattern of instances and connections,
and patterns compose by event connections only (a block is started by the `SUCCESS`, `DONE`, `EO`, `YES`
or `NO` of what precedes it). The generator is deterministic and compositional, so the reverse
direction is a parse, not a search: modsync recognises each construct by the type of its block and
follows the events that start it (figure page 2). A test compiles every shape of flow, reads the
program back and gets the flow it started from.

## 3. The mapping, element by element

| AAS (Skills submodel, ARSO 0.10) | IEC 61499 program (module rules 2) | OPC UA (below `/Objects/<Module>`) |
| --- | --- | --- |
| A skill of the kind Composite, `Dispensing` | Subapplication `Dispensing`; `Dispensing.Control` (`SKILL_Core`), `UaStart` (`SERVER_2_<1+n>`), the publishers | `Skills/Dispensing/{Start,Stop,Abort,Reset}`, `State`, `ErrorID` |
| `Deployment = Built` | `Dispensing.Control` exists | – |
| An input variable of the Start Operation, `Volume`, with limits and default | Latch `Dispensing.Volume` (`SKILL_Param_LREAL`): `Lower`, `Upper`, `Default` as values; argument k + 1 of the Start method | Argument of `Start`; `Parameters/Volume` |
| An output variable, `Weight` | `PubResults.SD_k`, connected from the step's `R_Weight` | `Results/Weight` |
| A step, `NodeId NeedleDown`, `Skill` → `MoveAxis` of the axis | Instance `Dispensing.Execute.NeedleDown` of `filling::SK_MoveAxis` | `Execute/NeedleDown/State`, `Parameters`, `Results` |
| A binding with `Value 40.0` | The input `NeedleDown.Position` written 40.0 | – |
| A binding with `SourceElement` → `Start/Volume` | A data connection `Dispensing.Volume.Value` → `Dispense.Volume` | – |
| `Order` of the steps | The chain `SUCCESS` → `START` | – |
| A step of the kind `parallel`, `Both`, with `Branches` | `SKILL_Join<n>` named `Both`; the start fans out to it first, then to every branch; branch i's end to `DONE_<i>` | – |
| `decision` / `conditional` `Light` with a `Condition` | `SKILL_Merge` named `Light`; comparisons `Light_C1`, … (`SKILL_Condition_<type>`) with `Operator` and `Expected` as values | – |
| A comparison's operand: a parameter / a step's result | A data connection from the latch's `Value` / from the step's `R_<result>` | – |
| A group `all` / `any` | A chain of comparisons on `YES` / on `NO` | – |
| The steps of the module's `Reset` and `Stop` (ModuleControl) | The procedure subapplications `Resetting`, `Stopping` | `Procedures/<name>/<step>/State` |
| The AID actions and properties of a skill | – (written for a built skill by the rules a module's AAS is written by) | Their browse paths |

## 4. What makes the mapping cheap

**Names are the join keys.** A skill's `idShort` is its subapplication's name, a step's `NodeId` its
instance's name, a parameter's `idShort` its latch's name, and the OPC UA paths are made from the same
names. Nothing has to store which block is which element: it follows from the names in both directions.
That is why the record of what was built could leave the AAS (only "built or described" stayed, for
clients).

**Types are the vocabulary, compositions are the sentences.** A primitive is a block type and stands
for one skill of one kind of component (`MoveAxis` of a linear axis), so the AAS of a component and the
type of a block describe the same thing. A module level skill is never a type: it is a composition of
instances, so a new one needs no build and FORTE creates it online. Three flow types suffice for any
nesting of parallel blocks and decisions. Conditions need no expression language in the program: a
comparison is a block, all and any are chains of them, and a condition read back is brought to one
canonical form (a group of one dissolved, nested groups of the same kind merged) before it is compared.

**A skill's network is local.** Equipment, the occupation and the release are reached over FORTE's
local channels (`loc[<Module>/<Item>/cmd]` and so on), not over connections. A skill's blocks are
connected to each other only, and to the running program by exactly one connection: from the end of
the INIT chain to the new skill. Creating a skill touches nothing that runs, so it is created even while
another skill runs; one `WRITE $e` on that link initialises it.

**Values and structure are apart.** Everything a reconfiguration may change without a restart is an
input value of an instance (a constant, a default, a limit, a condition's expected value); everything
else is instances and connections. That split is what sorts a difference into write, create or restart.

**One generator for both directions of time.** The function that generates a module level skill from a
spec is the one modsync calls to create it online from the AAS. The program created online and the
program a vendor would generate with that skill are the same by construction, and a test compares them.

**The interface is derived, not configured.** A skill's OPC UA nodes follow from its names; when a
skill is built online, its interface in the AAS (the actions of its commands, the properties of its
state and results, data points and mappings) is written by the same rules modreg writes a module's AAS
by. A client that follows the AAS's references finds and runs the new skill without a change.

**Meanings, not names, between product and module.** A parameter carries the meaning of the capability
property it sets (`FillVolume`), a skill type the capability it contributes (`Dispense` contributes
`Filling`). So the capabilities a module offers are derived from its skills, a described but not built
skill offers its capability "after a reconfiguration", and a product's requirement is matched by
meaning. The same flow language describes a product's recipe and a module's skill, so one editor serves
both.

## 5. Numbers

| Skill | Flow | Instances | Connections | Commands to create it online |
| --- | --- | --- | --- | --- |
| Dispensing | 4 steps | 13 | 63 | 142 |
| DoubleDose | 5 steps | 15 | 73 | 165 |
| Checked | 6 steps, two decisions, a group of comparisons | 23 | 98 | 224 |
| Ready | a parallel block of two steps | 5 | 31 | 64 |

Measured on a Raspberry Pi 5: verifying the filling module against its AAS 0.15 s over the network;
creating DoubleDose (in the pattern of 9 Oct), verifying it and amending the boot file 1.6 s, most of it
the boot file over SSH, while another skill ran. On FORTE on a PC: Checked and Ready created from their
AAS while the module was in Execute and occupied, then run; the branch a condition chose ran, the
other did not.

## 6. Where the mapping stops

- Nothing is removed or reordered online: a removed skill or another order of steps needs a new boot
  file and a restart, and the AAS does not hold the wiring of the rest of the program.
- A new primitive or new equipment is a new block type: a FORTE build.
- A condition compares a value with a constant (numbers and Booleans); it does not compute (no
  "weight below 0.95 × volume").
- A result of a skill comes from a step that runs on every path; two parallel branches use different
  components.
