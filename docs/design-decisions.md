# Design decisions

The decisions the method rests on, each with why it was taken and what it was taken instead of.
Written on 27 Oct 2026 as the material for the paper's method section; the log of every decision
with its date is [decisions.md](decisions.md), and this file points there rather than repeating
dates. Decisions still open are listed at the end.

Each decision says where it belongs: **Method** (the paper's contribution), **Model** (the
information model), **Implementation** (how it is built here; another implementation could
decide otherwise), **Not in the paper**.

## 1. The approach

### 1.1 The AAS is the desired state of a module (Method)

**Decision.** A reconfiguration is a change to the module's AAS. The tools carry that change into
the running program, verify it by reading the program back, and record what was built. Who changed
the AAS (an engineer in the skill editor, later an agent) is a separate matter.

**Why.** The AAS is what a module is delivered with and what every client already reads: the
planner matches against it, the HMI calls skills through it. Making it also the description of
what the program should be gives one place for what is wanted, for operating and for changing
alike. It also separates the vendor (who wrote the program, maybe from a spec) from the integrator
(who only has the program and the AAS).

**Instead of.** The module spec as the source (only the vendor has it; a module from another vendor
has none). The running program as the source (it says what is, not what is wanted). A separate
change recipe (one more document that has to agree with the AAS).

### 1.2 The scope is the changeover (Method)

**Decision.** A reconfiguration happens at a changeover, on the engineer's request, with the module
not executing (for values) or untouched (for a new skill).

**Why.** It is the situation in which a filling line changes in practice (another product, another
volume, another sequence), and it keeps the guarantees simple: nothing changes under a running
skill.

**Instead of.** Changes while a product is being processed (needs state transfer and is not what
the lab's lines need), or changes decided by the line itself (the agents, after the paper).

### 1.3 The rules are the contract, not the generator (Method)

**Decision.** How a module's program is structured is written down as rules
([module-rules.md](module-rules.md)): the shell, a skill primitive's interface, the fixed pattern of
a module level skill, what may change online. The generator follows them; so can a module written
by hand. A module names the rule set it follows.

**Why.** A reader of a program can only find skills, steps and values in it if their form is fixed.
Making the rules the contract means a vendor that does not use our generator can still deliver a
module our tools change. It is also what the paper can state in general terms.

**Instead of.** The generator as the only way to make a module (ties every vendor to one tool), or
arbitrary programs (cannot be read back or changed safely).

### 1.4 Changing and operating use different interfaces (Method)

**Decision.** The program is changed only over the IEC 61499 management protocol (modsync) and
operated only over the OPC UA interface it serves (modlink and the HMI). No tool does both.

**Why.** The two interfaces have different users and risks: an operator or an agent calls skills
many times a minute; a change to the program happens at a changeover. Keeping them apart means
operating a module never changes it and a change never runs a skill.

## 2. The module in IEC 61499

### 2.1 One module, one application, one resource (Implementation)

**Decision.** A module is one application on one FORTE resource, published below
`/Objects/<Module>`; one module runs on one Raspberry Pi.

**Why.** A full deployment replaces the program by a boot file and a container restart; with one
module per resource that affects only that module. It also gives each module one management
endpoint and one OPC UA root.

### 2.2 Equipment owns the IO; skills command the equipment (Method)

**Decision.** Each equipment item (an axis, a pump, a scale) is one block that owns its IO points
and knows nothing about what they mean. Skills send it commands. The command tables (which outputs
a command sets, in which timed phases) live in the skill primitive, not in the equipment.

**Why.** FORTE binds one block to an IO point, and several skills share an axis, so the pins have to
be grouped by equipment, not by skill. Equipment is fixed; skills are what changes. With the
command tables in the skills, the equipment block stays the same whatever the pins mean and only
keeps what must see every writer: one holder at a time, break before make, everything off on
release or abort.

### 2.3 Equipment, occupation and release over local channels (Method)

**Decision.** Blocks reach equipment, the occupation and the module's release over FORTE's local
publish and subscribe channels (`loc[<Module>/<Item>/cmd]`, `.../state`, `loc[<Module>/owner]`,
`loc[<Module>/release]`), not over connections.

**Why.** A skill added online then needs no connection to anything that already runs: it only
publishes and subscribes. This is what makes "create a skill online" a matter of new instances
and connections among themselves. The price: these links are not drawn in the IDE.

### 2.4 A primitive is a block type; a module level skill is only instances (Method)

**Decision.** A skill primitive (one equipment command until a sensor or a time says done) is a
block type, compiled into FORTE. A module level skill has no type of its own: it is a
subapplication of library blocks (`SKILL_Core`, the parameter latches, the publishers) and
primitive instances, in a fixed pattern.

**Why.** FORTE creates instances and connections online but cannot load a new block type. Keeping
module level skills free of their own types makes a new one, and a changed one, a matter of
instances and connections. Primitives change rarely (they follow the hardware) and justify a build.

**Instead of.** A type per module level skill (every new skill a FORTE build), or interpreting a
sequence at runtime in one generic block (the program no longer shows the sequence, and the IDE
cannot monitor its steps).

### 2.5 Skills are nodes that succeed or fail; PackML runs once (Method)

**Decision.** Every skill, primitive or module level, has the same small state machine: Idle,
Running, Stopping, Succeeded, Failed, Aborted, with `Start`, `Stop`, `Abort` and `Reset` as OPC UA
methods that answer `[Accepted, ErrorID]` at once. PackML (Stopped, Resetting, Idle, Execute, ...)
runs once, for the module.

**Why.** A skill is called, runs and ends, like a node in a behaviour tree; a full PackML machine per
skill is more than that needs. One machine for every skill means one way to call and watch any of
them, whatever it is made of. A skill already at its goal succeeds without driving.

### 2.6 One instance per call site (Implementation)

**Decision.** Each step of a sequence is its own instance of the primitive, with its own values
and its own OPC UA object (`Skills/Dispensing/Execute/NeedleDown`).

**Why.** A primitive can then be used several times in one skill with other constants, and each
step can be watched on its own.

### 2.7 Parameters travel in the Start call (Method)

**Decision.** A skill's parameters are the arguments of its `Start` method, range-checked and
refused synchronously. The input that holds a parameter's value in the program is its default:
the reconfiguration sets it; a caller overrides it for one run.

**Why.** One call per run, checked before anything moves; a refusal comes back with the call. An
OPC UA variable write carries no caller identity and FORTE cannot refuse it.

### 2.8 Occupation by session id (Implementation)

**Decision.** A client occupies the module with a session id it chooses, and every command carries
it. A cooperative lock, not security.

**Why.** Several clients (the HMI, a script, later agents) may reach a module; only the one that
occupies it may command it. Session ids need no user management on a Pi.

### 2.9 One INIT chain, started by the resource (Implementation)

**Decision.** Every block of the application is on one INIT chain started by the resource's own
`START` block. A block added online is appended to the end of the chain, and INIT is fired once
into it.

**Why.** It is how 4diac programs are usually started, and it gives a new skill a defined place to
be initialised without touching anything that runs.

### 2.10 What may change online (Method)

**Decision.** Online: a parameter's default or limits, a step's constant, and a new module level
skill made of primitives the module has. By a restart: another order of steps, a removed skill.
By a new build: a new primitive, new equipment, other IO.

**Why.** These are what FORTE can do without stopping the resource and without new types, and
what keeps everything that runs untouched: a written value is taken at the skill's next start; a
new skill touches nothing that exists. A changed sequence would mean deleting instances of a skill
that may be in use, and the AAS does not hold the wiring of the rest of the program from which a
whole new boot file could be made.

## 3. The information model

### 3.1 A resource AAS per line, module and component (Model)

**Decision.** The line, each module and each active component (an axis, a pump, a camera) has an
AAS of its own. They are the lab's `Resource` (aas-model) with ARSO's submodels added: Skills,
Operational Data, Control Configuration.

**Why.** A component is the same in every module that has it (every linear axis offers `MoveAxis`
and `Home`), so its skills belong with it and are described once. The module composes them. The
lab's shared model is used so the lab's other tools read our AASs.

### 3.2 A skill is its commands (Model)

**Decision.** A skill is a collection of its commands (Start, Stop, Abort, Reset). Each command
refers to the action of the interface that calls it and has an Operation named like it, whose
variables are the parameters (with unit, limits, default, meaning) and the results. The skills are
the Skills submodel's own elements. The module's own commands (Occupy, Release, Reset, Start, Stop,
Abort, Clear) are skills of the kind ModuleControl. Primitives are in their component's AAS.

**Why.** A client calls commands, so that is what a skill is made of. One form for all skills,
whatever their kind, so one reader finds them all. The kind (Primitive, Composite, ModuleControl)
and the skill type are supplemental ids, not structure.

### 3.3 A skill's steps are written like a product's recipe (Model)

**Decision.** What a command runs is a list of steps in the elements of the planner's Production
Sequence (`NodeId`, `Kind`, `Order`, `Skill`, `Bindings`, `Outputs`, `Branches`, `Condition`), with a
component's skill in place of a process.

**Why.** A skill and a recipe are both sequences of calls with bound values. One format means one
editor, one reader and one matching for both, and a skill can be edited the way a product's plan
is. "The models keep evolving" with it.

### 3.4 Capabilities are derived from skills (Model)

**Decision.** A capability names the skill that realizes it; a skill does not refer back. A skill
parameter carries the meaning of the capability property it sets. The offered capabilities are
derived from the skills by a rule on the ontology: a skill type contributes a capability, a
parameter's meaning and limits give the offered range. Derived elements are marked; facts of the
machine (container type) are stated by hand. A skill that is described but not built offers its
capability "after a reconfiguration".

**Why.** Written by hand, a capability and the skill behind it drift apart as soon as a skill
changes (a new skill without a capability, a changed limit the capability does not follow).
Derived, they cannot. "Offered after a reconfiguration" is the answer a product-driven change
needs: the line can do it once a described skill is built.

### 3.5 Three ids, three jobs (Model)

**Decision.** The `semanticId` says what an element is in its submodel template (ARSO, APSO,
AProSO, IDTA). A `supplementalSemanticId` says what it means in the domain (the lab's vocabulary:
a capability, a skill type, a property, a command). Which individual an element is (this skill,
this step) is its own id or reference, never a semantic id.

**Why.** A template's id lets a checker validate structure; a domain meaning lets a matcher compare
a product's need with a module's offer; neither should depend on names. Mixing them (per-instance
semantic ids) makes ids that name no concept.

### 3.6 Product, process and resource AAS as ISA-88's recipe levels (Model)

**Decision.** The product AAS holds the general recipe (what the product needs, no equipment
named); the process AAS, one per product and line, the master recipe (each step bound to a resource
and a skill); the resource AAS what a resource offers and how it is called.

**Why.** Pharmaceutical batch production already works with these levels. A reconfiguration
changes the resource AAS and at most the process AAS, never the product; one product on two lines
is two process AASs; each AAS has one owner (product designer, line engineer, vendor).

### 3.7 What is wanted and what was built (Model; under review)

**Decision so far.** The Skills submodel says what is wanted; the Control Configuration records
what was built (instances, block types, type hashes, a change log).

**Under review** ([control-configuration.md](control-configuration.md)): only two of its facts are
read by anyone but modsync (the rule set, and whether a skill is built). The proposal keeps those
two in the Skills submodel and moves the rest into the integrator's backend.

### 3.8 States as time series with a latest value (Model; after the paper)

**Decision.** States, measurements and events of a module go into Operational Data as series shaped
like IDTA's Time Series, each with a `Latest` property and a reference to its history in a
time-series database.

**Why.** An HMI or an agent then reads a module's state from its AAS like everything else, and the
history stays out of the AAS. Not built yet; the HMI reads the values over OPC UA today.

## 4. The tools and the method

### 4.1 Read back, compare, apply the least disruptive change, verify, record (Method)

**Decision.** A reconfiguration is one function: read the running program back over the
management protocol; read it by the module rules into a structure; compare it with what the AAS
describes; sort the differences into create, write, restart and wrong record; refuse what is not
possible online or what the module could not carry out; apply the rest; read the program back and
compare again; add the change to the boot file; record it in the AAS.

**Why.** Each step answers a question the engineer would otherwise check by hand: is the module
what its AAS says, is the change possible, did it happen, will it survive a restart, can a client
find the new skill. FORTE reports enough (every instance, connection, type hash and value) to read
the whole program back, so nothing is assumed.

**Measured.** The skill DoubleDose (19 instances, 84 connections, 190 management commands) was
created from its description in 0.04 s on a PC and in 1.6 s in all on a Raspberry Pi 5 (most of it
the boot file over SSH), while another skill of the module ran.

### 4.2 Create online with the generator's own pattern (Implementation)

**Decision.** A skill is created online by the same code the generator uses to generate it.

**Why.** The program created online and the program generated from a spec with that skill are
then the same, by construction and by test; there is no second implementation of the pattern to
drift.

### 4.3 Guarded changes (Method)

**Decision.** Values are written only while the module is Stopped, Idle or Aborted and not occupied.
A new skill is created in any state, since it touches nothing that runs. Missing block types refuse
the change before anything is sent.

### 4.4 Back to the IDE (Implementation)

**Decision.** A 4diac project of exactly what runs can be made from the program (skills added online
included) and is checked to deploy that program.

**Why.** FORTE keeps the program but not the project. An engineer has to be able to open what
runs, monitor it and keep working on it.

### 4.5 Clients read only the AAS (Method)

**Decision.** modlink and the HMI find every node they call or watch by following the references of
the AAS (capability, skill, command, interface action, browse path), never by names.

**Why.** A skill built online is operated as soon as its interface is recorded in the AAS, with no
change to the client. It also shows that the AAS alone suffices to operate the module.

### 4.6 The ontology checks the AAS (Implementation)

**Decision.** Every AAS is checked against the resource ontology before it is registered: every
restriction the ontology states has to hold, and what the ontology does not describe is reported
(and refused in strict mode).

**Why.** The model changes often; a closed check catches an AAS that no longer fits it before a
client reads it.

### 4.7 The skill editor is a web UI plugin in the planner's style (Implementation)

**Decision.** Skills are edited in a plugin of the BaSyx web UI that opens on the Skills submodel,
in the style of the product's sequence editor. A proposal to split it into an overview and a skill
view and to give it the planner's flow kinds: [skill-authoring.md](skill-authoring.md).

## 5. The hardware (Not in the paper, or as the setup only)

| Decision | Why |
| --- | --- |
| FORTE in Docker on each Pi, installed by one script | One way to set up a Pi; the same binary on every Pi |
| An IO block sets up the GPIO line or PWM channel its address names | An equipment block needs no other block for its IO; the same type runs on the PC (simulated) and the Pi |
| A stepper axis with a limit switch keeps its position by time | No encoder on the lab's axes; every operation ends by homing |

## 6. Open

| Question | Where |
| --- | --- |
| The Control Configuration in the AAS or in the backend | [control-configuration.md](control-configuration.md) |
| Branches, conditions and parallel steps in a skill (rule set 2) before or after the paper | [skill-authoring.md](skill-authoring.md) |
| Changing a skill's order online (delete and create while idle) | [skill-authoring.md](skill-authoring.md), section 3 |
| Which changes the paper shows | [next-steps.md](next-steps.md), open questions |
| Are Occupy and Release skills at all? | [next-steps.md](next-steps.md) |
| The eleven decisions on states and parameters | [state-and-parameters.md](state-and-parameters.md) |
