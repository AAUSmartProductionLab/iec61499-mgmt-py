# Next steps

Plan of 8 Oct 2026; it replaces the plan of 6 Oct ([archive](archive/next-steps-2026-10-06.md)).
What is built and how is in [work.md](work.md); what each AAS holds in
[aas-models.md](aas-models.md); what was decided in [decisions.md](decisions.md); how the work
divides into repositories in [repositories.md](repositories.md).

## What the paper delivers

The CIRP CMS full paper is due 18 Nov 2026. Its claim:

> A module that is delivered with an IEC 61499 program and an AAS can be verified, operated and
> changed online from those two alone, without the files it was generated from.

That is four deliverables:

| # | Deliverable | What it is | State |
| --- | --- | --- | --- |
| D1 | Module rules | How a module is built: the module library (module state machine, occupation, skill state machine), the fixed pattern of a module level skill, what may change online ([module-rules.md](module-rules.md)) | Built |
| D2 | Information model | The resource AAS in ARSO 0.7: the line, each module and each component, checked by a closed validation ([aas-models.md](aas-models.md)) | Built |
| D3 | Method and tools | Register, verify, operate, reconfigure, record | Register and operate are built. Verify, reconfigure and record from the AAS work since 8 Oct for a value and for a new skill (`modsync verify`, `reconfigure`); an editor for the description and a run on the Pi are missing |
| D4 | Evaluation | The same changes online and by full redeployment, timed, on a Raspberry Pi | Not built |

Agents are not part of the paper; they are its future work ([after the paper](#after-the-paper)).

## Which part of the model is used for what

| Submodel | Written by | Read by | Used for |
| --- | --- | --- | --- |
| Nameplate, asset type | `modreg` | the checker | Which kind of resource this is (line, module, component), so which rules apply |
| Hierarchical Structures | `modreg` | plan check | The line's modules and a module's components |
| Capability Description | `modreg` | plan check, `modlink.run_capability` | What a module offers and within which ranges; names the skill that realizes it |
| Skills (in a module's and in each component's AAS) | `modreg` | `modlink`; `modsync verify` and `reconfigure` | How a skill is called (commands, variables with limits) and what it is composed of (steps, constants) |
| Module | `modreg` | `modlink` | The module's own commands (Reset, Start, Stop, Abort, Clear, Occupy, Release) |
| Asset Interfaces Description | `modreg` | `modlink` | The OPC UA endpoint and the browse path of every action and property |
| Asset Interfaces Mapping Configuration | `modreg` | `modlink` | Which interface element carries a skill's state, error and results |
| Control Configuration | `modreg`; `modsync reconfigure` (the record) | `modsync verify` | Block type, instance and type hash of every skill and step; the rule set; the record of a change |
| Operational Data | `modreg` | `modlink`, through the mapping | What a value at the interface means (a skill's state, its error, a result). No live values are written into it |
| Product AAS: bill of material, required capabilities, plan | `modreg` (product) | plan check | What a product needs; today the plan names a resource and a skill per step |

The Steps of a skill and the Control Configuration are what the claim stands on. Since 8 Oct
`modsync` reads both: the Skills submodel says what is wanted, the Control Configuration what was
built.

## Where a reconfiguration comes from

Confirmed on 8 Oct, with the changeover as its scope, and tried the same day
([work.md](work.md), *The AAS as the desired state*).

**The AAS is the desired state.** A reconfiguration is a change to the module's AAS that the
tools then carry into the running program. Who made the change is a separate matter.

What can change online is fixed by the module rules: the value of a parameter or of a step's
constant, and a module level skill (instances and connections of primitives the module already
has). Anything that needs a new block type or new IO is a new FORTE build and a redeployment.

| Change | When it is needed | Where the new content comes from |
| --- | --- | --- |
| A parameter value inside the offered range | Another order of the same product family | The product AAS; the value is handed over when the skill is called. No reconfiguration |
| A step's constant or a limit (flow rate, largest volume) | The required value is outside what the module's skill offers, but inside what its component can do | The limits in the component's AAS and the product's requirement; an engineer sets the new value in the module's AAS |
| A new module level skill | No skill realizes the required capability, or the process needs another sequence of the same primitives | A skill description in the form the AAS already has (commands, variables, steps that name the module's primitives). Written by the vendor as a variant delivered with the module, by the integrator's engineer, by the AAS generator, later by an agent |

A skill that is described in the Skills submodel but has no instance in the Control
Configuration is a skill the module can get. Its capability is listed like the others. Matching
then has three answers: offered now, offered after a reconfiguration (and by which description),
not offered.

When it happens, for the paper: at a changeover, on the engineer's request. One function takes the
module's AAS and its running program and does the following:

1. Compare: which described skills and values differ from the program.
2. Check: the steps name primitives the module has, bound values are inside their limits, the AAS
   passes the validation.
3. Guard: the module is not executing and not occupied by someone else.
4. Apply: online where the rules allow it, otherwise say that a restart is needed.
5. Verify: read the program back, compare type hashes.
6. Record: instances and the change in the Control Configuration; register the AAS again.

Later a resource agent calls the same function when a bid that needs a reconfiguration is accepted.

## The plan to 18 Nov

### A. Reconfigure from the AAS (deliverable D3)

| # | Step | Where | Done when |
| --- | --- | --- | --- |
| A0 | **Try-out.** **Done 8 Oct:** instead of a mock-up, the idea was built as far as it runs: DoubleDose described but not built, created on FORTE, recorded | `modsync/desired.py` | You have confirmed the structure |
| A1 | **Verify against the AAS.** Compare the running program with what the AAS states (instances, block types, hashes, steps, constants), not with the module spec. **Done 8 Oct** (`modsync verify`); hashes are verified once they are recorded | `modsync` | A program that differs from its AAS is reported with the difference; no module spec is read |
| A2 | **Reconfigure from the AAS.** Create a module level skill from its description in the AAS; change a constant; both verified by read-back and recorded. **Done 8 Oct** on FORTE on the PC (`modsync reconfigure`), with the change added to the boot file. **Left:** a way to write the description (the tests take it from `modreg`), with the interface description of the new skill; the same on the Pi | `modsync`, `modreg` | The live test that creates DoubleDose passes when it starts from the AAS; the Control Configuration shows the change |
| A3 | **Operate what was created.** A client that reads the registered AAS again finds and runs the new skill | `modlink` (HMI repository) | `modlink` runs DoubleDose on FORTE from the AAS alone |
| A4 | **Callable functions.** Verify, create a skill, set a value: one Python interface, so a script, the HMI or later an agent calls the same thing. **Started 8 Oct:** `desired.load`, `read`, `reconfigure`, `record`, `store` | `modsync` | The scenario runner (B1) uses only these |

Step 1.2 of the old plan (a whole profile read from the running program) is no longer on the
path: the AAS is delivered with the module, the program is only compared with it.

### B. Evaluation (deliverable D4)

| # | Step | Done when |
| --- | --- | --- |
| B1 | **Scenario runner.** Plug in a module (register, verify, operate); change a constant; create a new skill. Each timed: downtime, commands sent, time to verify | The scenarios run unattended and write their numbers |
| B2 | **Baseline.** The same changes by a new boot file and a restart | Numbers side by side |
| B3 | **Hardware.** The filling module on the Raspberry Pi 5 with the stepper (TB6600 driver, ordered); the stoppering module on the Pi 4 if time allows | The scenarios run on the Pi with the axis moving; until then on the Pi's FORTE with simulated IO |

### C. Keeping the clients in step

| # | Step | Where |
| --- | --- | --- |
| C1 | The HMI's own AAS reader, its built-in module descriptions and its stand-in module still describe the modules before 8 Oct. Read ARSO 0.7 through `modlink`'s reader and drop the built-ins | HMI repository |
| C2 | The scale's weight follows the dispensed volume (it is a constant 2.0 g) | module spec, simulator |
| C3 | The Pi 4: new host name (`stoppering-module`), new runtime | Pi 4 (needs its password) |

C1 to C3 are not needed for the paper's claim; they go in when they block a figure or a run.

### D. Writing

Outline and figures by 1 Nov; experiment runs and text from 2 Nov; submission 18 Nov.

### Timeline

| Week | Work |
| --- | --- |
| 9 to 18 Oct | A2 (writing a description, the Pi), A3 |
| 19 to 25 Oct | A4, B1, B2 |
| 26 Oct to 1 Nov | B3 (when the driver is in), C as needed, outline and figures |
| 2 to 18 Nov | Experiment runs, writing |

If time runs out, cut in this order: C, then B3 on real hardware (keep the Pi with simulated IO),
then A3. Not to be cut: A1, A2, B1, B2.

## After the paper

**Decentralized, order-driven production.** A product agent per order asks for each process step,
resource agents answer with bids, the product agent chooses. What exists: `modlink` (occupy, run a
skill or a capability), capabilities with ranges, the range check of
[plan_check.py](../cell/examples/plan_check.py), occupation as the lock at execution time, and,
after step A4, the reconfiguration as functions. What is missing:

| # | Part | Why |
| --- | --- | --- |
| 1 | An unbound process | The plan names a resource and a skill per step. With bidding the product type holds required capabilities and their order; the binding is the result of a negotiation, per order. AProSO already describes it this way (candidates, then the chosen one) |
| 2 | An order | Nothing says "20 vials of 2.5 mL" and starts a product agent |
| 3 | Messages and protocol | Call for proposals, proposal, accept or reject, result (VDI/VDE 2193), and what carries them (the lab runs MQTT; SPADE needs an XMPP server) |
| 4 | A resource agent per module | Matches a request against its own AAS; answers yes, yes after a reconfiguration, or no, with a time; on acceptance reconfigures and runs the skill |
| 5 | A product agent | Walks the process, compares bids, records what was done to the product |
| 6 | Transport agents | A vial moves between the modules on the shuttles of the ACOPOS 6D table. Their control is Python code, not IEC 61499: the table needs a resource AAS (a Transport capability, an interface the agent can call) and an agent like a module's. It also shows the model on a resource that is not IEC 61499 |
| 7 | Reservation | A module can be occupied now, not booked for later |
| 8 | A matcher both sides use | Required against offered capability, including "after a reconfiguration" |
| 9 | Failure handling | A skill that fails, a module that goes away: ask again |

A first slice: one product agent, two resource agents (filling, stoppering) and the simulators;
one call for proposals per step; then a bid that needs a reconfiguration.

**Also after the paper:** the planner reading a module's skills; a module shell for the 4diac IDE
so a hand-written module goes the same way; the AAS generator writing profiles; live values and
history in the AAS; registration on the lab's AAS server; the repository split and CI.

## Open questions

| Question | Blocks |
| --- | --- |
| Who writes the description of a new skill, and with what? In the try-out `modreg` builds it from a module spec. An engineer needs an editor (the AAS server's own UI, the HMI, the planner), and the interface description of the new skill has to come with it or be derived by rule | A2 |
| A skill that is described but not built is told by its missing instance in the Control Configuration (as tried). Does it also get a state of its own that a client can read (described, deployed)? | A3 |
| A change that needs a restart (a sequence changed, a skill removed) is refused. For the baseline a boot file is needed, and the AAS does not hold the wiring: is the vendor's boot file part of what is delivered? | B2 |
| Which changes does the paper show: a constant and a new skill, or more? | B1 |
| Two components of one kind in a module (the two cameras) need one skill name twice | later |
| What a component's AAS holds besides its skills (a nameplate?) | later |
| Step values are also in the interface description; leave them out there? Operational Data in groups? | later |
| Occupy and Release are access control: are they called skills at all? | later |
| An interface action names its command as a supplemental semantic id; should it be the semanticId? | later |
| What belongs in the Parameters submodel (it does not hold a skill's parameters)? | later |
| Does the plan become an AAS of its own, per product and line? (With bidding it becomes per order) | agents |
| The ACOPOS 6D table: where is its Python code, and which interface does it offer (OPC UA, MQTT, a library)? | transport agents |
| The agents' framework and inner structure (SPADE or plain asyncio over MQTT; fixed plans or BDI) | agents |
| The module specs (YAML) still hold the wiring of each IO point per target; describing it in the AAS is an idea for later | later |

Facts only you or the lab have: the measured values of each station (fill range and accuracy,
diameters, flow rate, the real speed of the axes), and whether we may publish to the lab's AAS
server.
