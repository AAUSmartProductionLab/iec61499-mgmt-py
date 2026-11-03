# Orchestration journal paper: what goes in

Started on 3 Nov 2026, for the authors, from what [journal-paper.md](journal-paper.md) had collected
until then. On 3 Nov the journal work was split into two papers:
- **the models' paper** ([journal-paper.md](journal-paper.md)): the product, process and resource
  blueprints, their ontologies and constraints, with a small showcase;
- **this one:** how modules are built and changed in IEC 61499, how new skills are planned, and how a
  line is orchestrated, centralized and by agents, on the same models.

The CIRP CMS paper ([paper-outline.md](paper-outline.md)) is the module-level mechanism: restructuring
a running module through its AAS. Each consideration found while coding goes first into
[design-log.md](design-log.md), tagged *Journal*.

## Scope, as it stands

A module that describes itself:
- its skills and capabilities in the AAS (ARSO [jensen2026ontology]), as the models' paper defines
  them;
- new composite skills planned from them;
- built online in its IEC 61499 program;
- offered to a line run by either of two orchestrators: centralized (FOND policies run as behaviour
  trees [schwoerer2026fond]) or multi-agent (product agents following their recipes). Only the
  orchestration differs (31 Oct, [framework-plan.md](framework-plan.md) section 1).

## Content

| Topic | What we have | Where it is written up |
| --- | --- | --- |
| **The capability model for planning** | One IDTA 02020 Capability Description per module: offered (process) capabilities, a set per component of capabilities realized by primitives, Pre/Post/Invariant as `BasicConstraint` expressions, properties as state variables through `SameProperty`. Kind-level constraints in the vocabulary, integration constraints per module | [skill-planning.md](skill-planning.md) sections 2 to 4, DD 3.9 |
| **Why no planning submodel** | Against AAS2PDDL [nabizada2026capability], Bernhard et al. [bernhard2024leverage] and our own AI-Planning submodel [schwoerer2026fond]. Inside a module: a fixed cast, state as a few values, deletes generated. Execution constraints (occupation) are the shell's business. PDDL/HDDL generated, not modelled. Line level, with relational and uncertain outcomes, keeps a planning model of its own | [skill-planning.md](skill-planning.md) section 7, DD 3.9 |
| **The planner** | HTN with goal regression (GTPyhop): compositions, then existing composites, then generated methods; `+=` in equal doses; lifting to parallel blocks by state and invariants | [skill-planning.md](skill-planning.md) section 6 |
| **Checking and discovery** | Checker for hand-written flows (unmet preconditions with the step that fixes them; invariants broken by parallel branches); discovery of capabilities offered after a reconfiguration | [skill-planning.md](skill-planning.md) section 6; `modplan check`, `discover` |
| **Standard planners** | The same domain as numeric PDDL (ENHSP) and HDDL (Aries), validated by unified-planning; the HDDL encoding with values as objects and sums as static facts | `modplan/export.py`, [skill-planning.md](skill-planning.md) section 6 |
| **Runtime conditions** | A primitive's `Conditions` and `Completion` (ARSO 0.11), and their link to the capability constraints through shared data points | [skill-planning.md](skill-planning.md) section 5 |
| **Orchestration by agents** | Product and resource agents bidding for process steps (VDI/VDE 2193 over XMPP, SPADE); a product agent per unit ordered; shuttles bid for Transporting like modules, the module's binding proposal held until the product is at its station; custody (who carries a product) as capability constraints in the resources' AASs, Receiving and Releasing, so that no rule of the agents is about shuttles; a capability narrower than its steps contribute (BottomUpFilling, a Filling) declared by the skill written for it, so a product can ask for it; the module's agent creating that skill online on FORTE before it carries the step out (built 30 Oct, on the PC). Still to do: the agent planning the skill itself (A3). FOND policies [schwoerer2026fond] are, since 31 Oct, the other orchestrator of the same line (next row) | [agents.md](agents.md), [design-log.md](design-log.md) (30 Oct), `line-agents/` |
| **One line, two orchestrators** | Planned 31 Oct, with the colleagues. The same resource, product and process AASs, the same IEC 61499 modules (occupation, PackML module state, the skills' state machines) and one way of running a skill (occupy, Execute, start, wait, release), under a centralized orchestrator (FOND-AAS's policy run as a behaviour tree [schwoerer2026fond]) and a multi-agent one; occupation hands the line from one to the other | [framework-plan.md](framework-plan.md) section 1, [design-log.md](design-log.md) (31 Oct) |

## Evaluation the CIRP paper leaves out

- **Planning against standard planners:** GTPyhop 1 to 2 ms, Aries 41 to 66 ms, ENHSP 282 to 348 ms;
  all valid (`cell/eval/planners.py`).
- **Plan quality** against the engineer's skill:
  - GTPyhop's plan equals Dispensing.
  - Aries returns by MoveAxis(0) instead of Home.
  - ENHSP weighs the empty vial first.
- **Scaling with plan size:** one probe, 1 to 20 doses. GTPyhop 2 to 4 ms, ENHSP about 0.37 s, Aries
  0.08 to 6.8 s on our HDDL encoding. Five-run medians are to do; the method is borrowed from
  [schwoerer2026fond].
- **Modelling effort** (borrowed from [nabizada2026capability], who report 77 AAS elements for one
  action):
  - Filling: 16 constraints (102 AAS elements), of which 4 are written for the module.
  - Stoppering: 9 constraints, 2 written.
  - The HDDL (9 tasks, 17 methods, 5 actions) is generated.
- **Repeatability:** successful runs out of N (borrowed from [schwoerer2026fond]).
- **The cases T1 to T14**, including discovery (T10), a missing scale (T11), a missing integration
  constraint (T12) and filling from the bottom (T13, T14).
- **Agents:** time from a product's request to a module offering a new skill.
- **The two orchestrators on one scenario** (proposed 31 Oct): the same orders and events (a module
  failing, a rush order, a module plugged in) run by both; the time to finish the orders, the reaction
  to the failure, the time until a new module is used, the work to set each up.

## Related work

All in [paper-references.bib](paper-references.bib) unless said otherwise:
- **Reconfiguration and services:** zoitl2006dynamic, dai2017self, klose2019orchestration (MTP).
- **Planning:** mayr2023skiros2, martin2021plansys2, bennulf2021goal, wally2019production,
  hoeller2020hddl, scala2016interval, godet2022chronicles, blair2009models,
  jarvenpaa2019development.
- **BPMN as an executor:** koecher2022bpmn runs the recipe as BPMN service tasks in Camunda, bound to
  skills when a run starts. Ours carries a plan out by the agents and a skill by FORTE, with no engine,
  and the plan is checked before it runs.
- **Not yet in the file:**
  - Spitzer et al., ETFA 2020: an OPC UA skill interface for PLCs, atomic and composite skills.
  - Stolze et al., ETFA 2024: a proactive AAS through BPMN and the I4.0 language bidding.
- **Agents** (survey of 30 Oct, [agents-literature.md](agents-literature.md), BibTeX in its section 8.2,
  not yet in the bib file): SMIA (Hurtado et al., JII 2025, doi:10.1016/j.jii.2025.100915) as the
  closest system; Lepuschitz et al. (TSMC-C 2011), Zoitl et al. (ETFA 2010), Vallée et al. (TII 2011) for
  agents reconfiguring IEC 61499; Lyu and Brennan (2020, 2025) for SPADE with 4diac; Bernhard et al.
  (2023) and Jungbluth et al. (2022, 2023) for AAS agents with VDI/VDE 2193 bidding and transport; IEEE
  2660.1-2020 and Leitão et al. (OJIES 2023) for the agent-device interface; Smith (1980) for the
  contract net. The contribution against them is in [agents.md](agents.md), section 9: an agent that
  plans and creates a skill online to win a bid.

## Open questions

- **The comparison's place:** the centralized orchestrator is the colleagues' work (FOND-AAS, the BT
  controller); whether the comparison is this paper's or a joint one.
- **Taring:** the plan tares after dispensing from an untared start
  ([skill-planning.md](skill-planning.md) section 9).
- **A discovered offer's range under `+=`:** it needs the container's capacity.
- **Decisions in planned skills:** "top up if light".
