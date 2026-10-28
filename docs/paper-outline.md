# Paper outline (CIRP CMS, due 18 Nov 2026)

A draft of 28 Oct, for the authors: the claim and the four contributions as decided on 27 Oct
([next-steps.md](next-steps.md)), each section with the material it rests on in this repository. The
reasons behind each choice, with what was chosen instead, are [design-decisions.md](design-decisions.md).

## Claim

> A module that is delivered with an IEC 61499 program and an AAS can be verified, operated and
> changed online from those two alone, without the files it was generated from; new skills are
> planned from its skill and capability models and created online the same way.

## Contributions

1. **The models**: skills and capabilities of a resource in its AAS (ARSO 0.12). A skill is its
   commands and the flow of steps it runs, written in the process planner's elements; a module's
   Capability Description holds its offered capabilities and, per component, the capabilities its
   primitives realize, with what each needs, does and keeps as IDTA 02020 property constraints.
2. **Planning new behaviour** from those models: a module composes a new skill for a capability a
   product asks for (HTN and goal regression), checks a skill written by hand, and finds what it can
   carry out without a skill yet.
3. **The IEC 61499 module architecture** that makes skills: a fixed shell (occupation, PackML state,
   equipment), a skill primitive as a block type, a module level skill as instances and connections
   only, flows (parallel blocks, decisions) from three library blocks, the wiring drawn by rules.
4. **Updating a running module**: the AAS as the desired state; the program read back by the rules,
   compared, changed online through IEC 61499's management interface, verified and recorded.

## Sections

| # | Section | What it says | Material |
| --- | --- | --- | --- |
| 1 | Introduction | Reconfigurable lines, changeover by hand; the AAS is delivered but not used to change anything; the claim | [design-decisions.md](design-decisions.md) 1.1, 1.2 |
| 2 | Related work | IEC 61499 reconfiguration (online changes, management protocol); skills and capabilities (CSS, IDTA 02020, PackML skills); AAS-driven engineering; planning from capability models (Köcher et al. 2023, SMT; Nabizada et al. 2026, PDDL from AAS; HTN, GTPyhop) | [skill-planning.md](skill-planning.md) section 7 |
| 3 | The module architecture (C3) | Shell, primitive, module level skill, flows; what may change online | [module-rules.md](module-rules.md), [mapping.md](mapping.md), [design-decisions.md](design-decisions.md) 2 |
| 4 | The models (C1) | The resource AAS: Skills (commands, flows), Capability Description (offered; per component, with constraints), Operational Data; the vocabulary; ids | [aas-models.md](aas-models.md), [skill-planning.md](skill-planning.md) sections 2 to 4, [design-decisions.md](design-decisions.md) 3 |
| 5 | Planning (C2) | The domain read from the AAS; plan, lift, describe; check; discover | [skill-planning.md](skill-planning.md), [tools.md](tools.md) section 5 |
| 6 | Updating online (C4) | Read back, compare, classify, apply, verify, record; created with the generator's own pattern | [tools.md](tools.md) section 3, [design-decisions.md](design-decisions.md) 4 |
| 7 | Evaluation | The filling and stoppering modules on FORTE (PC with simulated IO; the Raspberry Pi 5 with the axis): the scenarios online against a restart; the planning cases | `cell/eval/scenarios.py` and its results; [skill-planning.md](skill-planning.md) section 10 |
| 8 | Discussion and outlook | What cannot change online (types, order); a module's state only; agents (the line is theirs); locations and the planar table | [mapping.md](mapping.md) section 6, [locations-and-layout.md](locations-and-layout.md) |

## Figures

| Figure | Exists | File |
| --- | --- | --- |
| The pipeline: spec, program, AAS; verify, change, operate, plan | Drafted | `figures/reconfiguration-pipeline.drawio`, `figures/module-tools.drawio` |
| A skill as blocks: a primitive a block type, a composite instances; the wiring the rules draw | Yes | `figures/skill-blocks.drawio` |
| The product, process and resource models | Drafted | `figures/ppr-models.drawio` |
| The Capability Description a planner reads: offered capabilities, a set per component, constraints, SameProperty | Drafted 28 Oct | `figures/capability-description.drawio` |
| A planned skill: requirement, plan, flow, created online | Drafted 28 Oct | `figures/planned-skill.drawio` |
| Evaluation: the scenarios online and by restart | Drafted 28 Oct, the PC's numbers (the Pi's to come): time down per change, online and by a restart; caption: a value is written while the module is Idle, so online it is down for the way back to Execute | `figures/evaluation-downtime.pdf`, made by `cell/eval/figures.py` from `cell/eval/results` |

## Evaluation, what the numbers are

- **Scenarios** (`cell/eval/scenarios.py`): plug in (verify), a value, a written skill, a planned
  skill; each online (management commands, time, time to verify, whether the module kept running)
  and by a restart (boot file, time down). On this PC first, then the Pi 5 (B3). First numbers, five
  runs on this PC (`cell/eval/results/2026-10-28T0121.md`): online 0.02 to 0.05 s and 1 to 164
  commands, the running skill kept running (a value is written while Idle); by a restart 3.3 s down.
- **Planning**: the cases T1 to T12 of [skill-planning.md](skill-planning.md) as tests (the module's
  own skills as ground truth, a planned skill run on FORTE); times to read the domain and to plan.
  The same problems exported as PDDL and HDDL and planned by ENHSP and Aries
  (`cell/eval/results/planners-2026-10-28T0218.md`): GTPyhop 1 to 2 ms, Aries 41 to 66 ms, ENHSP 282
  to 348 ms, every plan valid.
