# Authoring skills: the skill editor, the planner and a backend for both

Proposal of 27 Oct 2026; decided the same day (phase 2 before the paper) and **built the same day:
phases 1 and 2** (section 7). How the two web UI modules (the process sequence planner and the skill
editor) are to change, so that:

- the Skills submodel opens on an **overview**, and a single skill opens in the **editor**;
- a skill can have **branches, conditions and parallel steps**, edited with the planner's own
  flow editor instead of a list of steps;
- a new skill is **recommended and partly made from the ontology**, starting from a product's
  requirement the line does not offer yet;
- one **backend** does the checking, deriving and proposing, for both modules.

Where the tools stand today: [tools.md](tools.md). The model: [aas-models.md](aas-models.md) and
[ppr-model.md](ppr-model.md). The Control Configuration question, which touches the overview:
[control-configuration.md](control-configuration.md).

## 1. Today

Both modules live in the web UI fork (`basyx-aas-web-ui`, branch `feat/process-sequence-pharma`,
folder `aas-web-ui/src/pages/modules/ProcessSequence`).

| | Planner | Skill editor |
| --- | --- | --- |
| Opens on | A product AAS (its own page) | A Skills submodel (submodel plugin `ArsoSkills_v1_0.vue`, on the submodel's semantic id) |
| Edits | The recipe: steps, calls, parallel, decision and conditional blocks with typed conditions (all, any, comparisons of parameters and step outputs, every Nth product) | One skill at a time, chosen from a drop-down: a list of steps, parameters' defaults and limits, a new skill from an existing one |
| Flow kinds | All five, with a type selector and safe transformations (wrap in a decision, keep a branch) | Steps only; it reads a parallel block but refuses to save one |
| Graph | `PlanGraph.vue` on the plan's scopes, processes and materials | `SkillFlowGraph.vue`, its own simpler graph on the planner's layout (`buildPlanGraph`) |
| Checks | Its own (structure, bindings) | A TypeScript copy of what modsync refuses (`flowIssues`) |
| Capabilities | Matches required against offered by meaning; ignores `Availability` | Does not show what a skill offers; does not call the derivation after saving |
| Uncommitted | | The fixes from the look in a browser, and ARSO 0.9 (the skills directly in the submodel); 107 tests pass |

Both write the same AAS elements for a flow: ARSO took the planner's Production Sequence elements
(`NodeId`, `Kind`, `Name`, `Order`, `Skill`, `Bindings`, `Outputs`, `Branches`, `Condition`) on 9 Oct,
so a skill's steps and a product's recipe are already one format. What is missing is one editor
for it, and a control that runs more than a list.

## 2. The skill editor in two views

The BaSyx web UI picks a plugin by the semantic id of what is selected in the tree, for a submodel
and for a submodel element alike (`SubmodelElementVisualization.vue`). Every skill element carries
`https://smartproductionlab.aau.dk/skill`. So:

| Selected in the tree | Plugin | Shows |
| --- | --- | --- |
| The Skills submodel | `ArsoSkills_v1_0.vue` (exists, becomes the overview) | Every skill of the module at a glance |
| One skill (a collection with the semantic id `.../skill`) | A new submodel element plugin, `ArsoSkill_v1_0.vue` | That skill in the editor |

### The overview (the Skills submodel)

One card or table row per skill, grouped by kind:

| Group | Per skill |
| --- | --- |
| The module's skills (Composite) | Name and description; parameters with unit, default and limits; results; a one-line summary of the flow ("NeedleDown, Dispense, Home, Weigh"); the capability it offers with its ranges (derived); **Built** or **Described**; problems the check finds |
| Building blocks (the components' Primitive skills) | Grouped by component: name, skill type, parameters and limits, results; which of the module's skills use it |
| The module's own (ModuleControl) | Occupy, Release, Reset, Start, Stop, Abort, Clear; the procedures Reset and Stop run |

Actions on the overview: open a skill (selects it in the tree, so the skill view opens); **new
skill** (empty, from an existing one, or for a required capability, section 5); delete a skill
that is only described (a built one needs a restart, so it is refused with that reason).

### The skill view (one skill)

- **Composite:** the flow editor (section 3) for what Start runs and what Stop runs; the step
  inspector (the component skill a step runs, what each input is handed, which result it gives);
  the skill's parameters and results; a live panel "this skill offers": the capability and ranges
  the derivation gives for the skill as it stands (section 4, preview), and whether it meets the
  requirement it was made for.
- **Primitive:** read only (it is a block type: changing it is a new FORTE build): its contract,
  parameters and limits, and which skills use it.
- **ModuleControl:** the procedure's steps, editable with the note that a change needs a restart.

Saving writes **only that skill's element** (the AAS server's API replaces one submodel element by
its path), not the whole submodel, so two skills edited in two tabs do not overwrite each other.
After saving, the editor asks the backend to derive the capabilities again (step F3, still
missing today).

## 3. Branches, conditions and parallel steps in a skill

### In the editor: one flow editor for recipes and skills

The planner's graph, type selector, transformations and condition editor are made to work on a
list of nodes, not on a product plan, and the skill editor uses them with its own step card and
step inspector:

| Planner part | Today tied to | Becomes |
| --- | --- | --- |
| `PlanGraph.vue`, `buildPlanGraph` | A plan's scope, processes, materials | A sequence graph over `PlanNode[]`; materials stay a planner option |
| `PlanNodeType.vue`, `planTransforms.ts` | `ProcessPlan` and a scope id | Transformations of a node list (wrap in a decision, keep a branch, unwrap) |
| `PlanCondition.vue`, `conditions.ts` | Operands from the plan: product parameters, step outputs | Operands given by the context: for a skill, its parameters and the results of earlier steps |
| Step card and inspector | Process, resource and skill binding | Slots: the planner keeps its own; the skill editor puts in `SkillStepInspector` |

Which of the planner's kinds a skill can use:

| Kind | In a skill | What it means there |
| --- | --- | --- |
| `step` | Yes | Run a component's primitive with bound inputs |
| `parallel` | Yes | Run the branches at once; done when all are done |
| `decision` | Yes | After the steps before it: if the condition holds, the first branch, else the second |
| `conditional` | Yes | A decision with an empty second branch |
| `call` | Later | Run another skill of the same module as one step (nesting) |
| Condition `everyNthProduct` | No | A skill counts no products |
| Condition `comparison`, `all`, `any` | Yes | On a parameter of this run, or a result of an earlier step that runs on every path to the condition |

Example: Dispensing with a check-weigh. After Weigh, a decision on `Weigh.Weight < Volume * 0.95`
(written as a comparison with a bound expected value) runs a second Dispense with the rest.
(That needs a computed value; a first version compares a result with a constant or a parameter
only.)

### In the AAS: nothing new

ARSO already has `Branches` and `Condition` on a step, as the Production Sequence has them. The
editor's reader and writer (`skillFlow.ts`) handle `parallel` today and need the decision and
conditional kinds and the condition tree, written the way the planner already writes them.

### In IEC 61499: the hard part

A module level skill must stay **instances of library types and of the module's primitives only**:
that is what lets modsync create it online without a new FORTE build. So each kind needs a fixed
pattern of library blocks, added to the module rules (rule set 2; a program by rule set 1 is still
read):

| Kind | Pattern | New library types |
| --- | --- | --- |
| `parallel` | The event that starts the block fans out to the first step of each branch (an event output may drive several inputs). Each branch's end goes to a join block, which gives `DONE` when all branches are done. On the first failure it halts the branches still running, waits until they have ended, then gives `FAILED` with that error | `SKILL_Join_<n>` (n = 2, 3, 4), with failure handling; `E_REND` alone cannot fail |
| `decision` | The previous step's `SUCCESS` triggers a condition block, which reads its operand (a parameter's latched value or a step's `R_<result>`) and compares it with the expected value; its `TRUE` or `FALSE` event starts the first step of one branch. `all` and `any` are chains of condition blocks (for `all`, `TRUE` triggers the next; for `any`, `FALSE` does). The two branches' ends meet in an `E_MERGE` | `SKILL_Condition_<type>` (one per data type: an operand, an expected value, an operator; `TRUE` and `FALSE` out) |
| `conditional` | As a decision; `FALSE` goes straight to the merge | – |
| Failures | As today: every step's `FAILURE` goes through `SKILL_FailMerge` to the sequence's `FAILED` | – |
| Stop, Abort, Reset | As today: `HALT`, `ABORT` and `RESET` go to every step instance | – |

Rules the check has to add:

1. Two parallel branches never use the same equipment item. All steps of a skill hold their
   equipment under the skill's name, so two branches commanding one item would fight over it.
2. A condition's operand is available on every path to it (a parameter, or a result of a step that
   runs on every path before it).
3. A result of the skill comes from a step that runs on every path (outside a decision), so it is
   never undefined. A result from inside a decision needs a selection block: later.
4. `ReleaseAfter` is `FALSE` on every step of a skill with branches: which step is "the last to use
   an item" depends on the path. `Control` already gives up everything the skill holds at the end of
   every run (22 Oct), so nothing is lost.

What changes where:

| Part | Change |
| --- | --- |
| ModLib (`modgen/library.py`) | The new types; then **one new FORTE build** for the PC and the Pi, installed on both Pis. After that every kind is created online |
| Module spec and modgen | `execute` and `stop` become a list of nodes (step, parallel, decision, conditional); `sequence()` builds them recursively |
| modsync | `described()` reads the kinds from the AAS and checks the rules above; `structure()` reads them back from a program (the join and condition blocks mark them); `differences()` compares trees; `fragment()` is unchanged (it calls modgen's pattern) |
| modreg | The derivation: a capability counts when a step contributes it on every path (a Dispense on one branch only does not make the skill offer Filling); the interface of a built skill is unchanged (its steps keep their OPC UA paths below `Execute/<step>`) |
| modlink, the HMI | Nothing: a skill's interface does not change |
| Module rules | Section 3 extended; rule set 2 |

Rough size: library types and the FORTE builds 1 to 2 days, modgen 1 to 2, modsync's read-back,
comparison and checks 2 to 3, the shared flow editor 2 to 3, tests on FORTE 1: about one and a
half to two weeks. Changing an existing skill's order online (deleting its blocks while it is idle
and creating them anew) is a separate step, untried: FORTE crashed deleting a resource with IO
handles, deleting a skill's blocks may well be fine, but it needs trying.

## 4. The backend

One service for the planner and the skill editor, so the rules exist once (in Python, where
modsync applies them) and the ontology is queried where it is loaded. It extends the registration
service `modreg serve`, which already allows a browser to call it and already derives
capabilities:

| Request | Does | Built from |
| --- | --- | --- |
| `POST /skills/check` (a Skills submodel or one skill, the module's shell) | Every problem a description has, in the terms modsync refuses it by | `modsync.desired.described`, changed to collect all problems instead of raising the first. Replaces the editor's TypeScript copy (`flowIssues`) |
| `POST /capabilities/<shell>?preview` | What the module would offer with the given skills, without storing | `modreg.offer.capabilities` (exists without `preview`) |
| `POST /capabilities/<shell>` | Derive and store (exists) | |
| `POST /skills/propose` (a shell, a required capability with its properties and ranges) | Proposed skill descriptions, each with why (section 5) | The projection and SPARQL queries on the vocabulary |
| `GET /vocabulary/...` | Skill types, capabilities, properties with labels, for pickers | `ontology/Vocabulary` |
| `POST /reconfigure/<shell>?dry_run` | What modsync would do on the module: create, write, or refused (needs a restart) | `modsync.desired.reconfigure(dry_run=True)` |
| `POST /reconfigure/<shell>` | Apply it, guarded as on the command line | The same. On a Pi only with someone at the bench (our rule for anything that can move an axis; creating a skill moves nothing, but a written value can) |
| `GET /build/<shell>` | The backend's record of what was built, if the Control Configuration moves there | [control-configuration.md](control-configuration.md), option C |

## 5. Recommendations and automation from the ontology

### What the vocabulary can say today

- A skill type (`ontology/Vocabulary/skills.ttl`) says which capability it contributes
  (`skl:Dispense lab:contributes lab:Filling`), and whether that is a process capability (a product
  can require it) or an auxiliary one (Positioning, Weighing).
- A parameter of a primitive says what it means (`Dispense.Volume` means `FillVolume`); a module
  level skill's parameter inherits the meaning through its binding.
- The derivation turns that into offered capabilities with ranges (`10-capabilities.rq`).
- A product says which capabilities its processes require, with values or ranges.

### What the editor can recommend with it (first level, before or soon after the paper)

Starting from the planner, where a step's required capability is **not offered** by any module:

1. **Which module to change:** the modules with a component whose primitive contributes the
   required capability (the filling module, for Filling).
2. **A starting skill:** the module's existing skill that offers the capability ("from this"), or,
   if none, the primitives that contribute it, with the auxiliary steps the module's existing skills
   put around such a primitive (Dispense comes after a MoveAxis and before a Home in Dispensing):
   patterns read from the module's own skills on the projection, not invented.
3. **Parameters:** a step input whose meaning is a property of the required capability becomes a
   parameter of the new skill with that meaning; its limits are the primitive's limits, narrowed to
   the requirement's range; its default the requirement's value.
4. **Constants:** the values the module's existing skills bind to the same input (NeedleDown's
   position 40 mm).
5. **Results:** a step's result whose meaning is a property of the capability (Weight).
6. **Name:** `<Capability>_<Skill>` as the derivation names a second skill for one capability, or
   the requirement's name.
7. **The check and the preview** before saving: what the module could not carry out, and what the
   skill will offer, against the requirement it was made for.

The user then edits the proposal and saves it. The skill is **described**, the planner shows the
module as "offered after a reconfiguration", and `modsync reconfigure` (or the button, with the
dry run first) builds it. Later a resource agent calls the same `propose`, `check` and
`reconfigure` without the editor.

### What the vocabulary needs for more (after the paper)

- **Preconditions and effects of skill types** (Dispense needs the needle at the filling position;
  Home leaves the axis at its switch; MoveAxis needs the axis homed). With them a sequence can be
  composed by planning instead of copied from an existing skill. CSS describes capabilities with
  such conditions; the lab's vocabulary has none yet.
- **Meanings of positions and other constants** (NeedlePosition is the filling height for a
  container), so a constant can be proposed from the product's container instead of copied.
- **Aggregate rules** (DoubleDose fills twice the volume), so a skill with two dispensing steps
  offers the right range.

## 6. The planner

| Change | Why |
| --- | --- |
| Show each match as **offered**, **offered after a reconfiguration** (with the skill and module), or **not offered** | Step F3; the AAS has `Availability` since 26 Oct |
| On "not offered": **make a skill for this**, which opens the proposed module's Skills with the proposal (section 5) | The product-driven entry into the skill editor |
| Re-read the offered capabilities when the skill editor has saved | So the planner sees the new skill at once |
| Share its flow editor with the skill editor (section 3) | One editor for recipes and skills |

## 7. Order of work

| Phase | Work | Size | When |
| --- | --- | --- | --- |
| 1 | The overview and the skill view; saving one skill; the derivation after saving; the planner showing `Availability`; `POST /skills/check` replacing the TypeScript checks; `Deployment` shown if the Control Configuration moves (option C) | 3 to 4 days | Before the paper: it is what the paper's figures and the demonstration of the editor show |
| 2 | Branches, conditions and parallel steps: the library types, rule set 2, modgen, modsync, the shared flow editor, tests on FORTE | 1.5 to 2 weeks | Only before the paper if the paper is to show it; otherwise after. It competes with B1 and B2, which are not started |
| 3 | `POST /skills/propose` and "make a skill for this" in the planner (first level of section 5) | 3 to 5 days | After phase 1; before the paper only if time allows |
| 4 | Preconditions and effects in the vocabulary; composing sequences by planning; the agents calling the same service | Weeks | After the paper |

**State on 27 Oct:** phase 1 built (the overview, the skill view, one skill saved, the derivation
after saving, `Availability` in the planner; `Deployment` and `RuleSet` in the AAS). Phase 2 built:
ModLib's `SKILL_Join2` to `4`, `SKILL_Condition_LREAL` and `_BOOL`, `SKILL_Merge`; rule set 2 in
[module-rules.md](module-rules.md); the spec, the generator, modsync's read-back from the program
and from the AAS, modreg's AAS and derivation (a step counts when it runs on every path); the editor
with parallel blocks, decisions and conditional steps (its own step and block cards; the planner's
graph layout, not yet its components); tried on FORTE on this PC (two decisions and a parallel block
created online while the module ran, and run). FORTE for the Pi is built and in `runtime/bin`, **not
installed on the Pis** (waits for you at the bench). Not built: `POST /skills/check` (the editor
checks in TypeScript, kept the same as modsync's rules by a shared fixture), phase 3.

**Decisions needed (answered 27 Oct: C; phase 2 before the paper; the fork committed):**

1. The Control Configuration: option A, B or C ([control-configuration.md](control-configuration.md)).
2. Does the paper show a skill with a branch? It decides whether phase 2 comes before B1 and B2.
3. Your go to commit the fork's pending changes (the fixes and ARSO 0.9), which phase 1 builds on.
4. Rule set 2 and the new library types: they change the module rules and need one FORTE build
   installed on both Pis.
