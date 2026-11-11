# Design log

A running log of design considerations made while building, for writing the papers afterwards.

**What each entry holds:**
- what was chosen;
- why;
- what it was chosen instead of;
- which paper it serves: *CIRP* ([paper-outline.md](paper-outline.md)), *Journal*, the models
  ([journal-paper.md](journal-paper.md)), or *Orchestration*
  ([orchestration-paper.md](orchestration-paper.md); since 3 Nov, earlier entries say *Journal*), or
  more than one.

**Rules:**
- Newest entries first, dated.
- Add an entry whenever code or a design changes for a reason a reader of the paper would want to
  know.
- What was decided, without the reasons, still goes into [decisions.md](decisions.md). The method's
  settled decisions are in [design-decisions.md](design-decisions.md).

## 11 Nov 2026

- **Q3 sampled: 10 drifts of each kind and 20 clean runs (105) instead of every drift (1,258).** *CIRP*.
  Detection is reading the program and comparing it with the generator's from the AAS, the same answer
  for the same drift; the full run showed it for every value and connection of the test program, and
  on the Pi a sample of each kind shows that it holds there. `--per-kind` draws the sample at random
  from every drift the full run would make. Instead of fewer kinds or only the program's kinds, which
  would leave out the AAS side or the cut reconfiguration.
- **The reduced Q1 and Q3 run on the PC first (simulated IO), their numbers in the paper until the
  Pi's.** *CIRP*. 120 and 105 runs, every check passed; 0.33 s for 32 steps in 20 composites, 3.3 s
  down for a restart, all 85 drifts found. The paper marks them in red until the runs at the bench.

- **Q1 on the module's Pi: 12 cells of 10 runs (120) instead of 42 of 30 (1,260).** *CIRP*. The paper's
  evaluation runs on the real module (the Pi 5 with FORTE, the scale simulated in FORTE), where a run
  takes seconds of the axis's motion. What the 1,260 runs on the PC showed (linear growth with the
  steps and the program, no effect on a running skill, the restart's downtime) needs the corners of
  the grid, not every point: 1, 8 and 32 steps in programs of 1, 10 and 20, one parallel case, a value
  and a restart. Instead of the full grid with fewer runs, which would keep cells that add nothing.

- **Q4b's products up to 10 mL.** *CIRP*. 25 mL is not a product the line fills; the largest found is a
  multi-dose vial of 10 mL, so the 20R vial of 15 to 25 mL left Q4b (20 products, 80 cases, from 26 and
  104). With it went 21 of the 23 planned skills: they split a dose only because Dispense stops at
  10 mL, which the paper already set aside as a parameter limit (8 Nov). Instead of other products made
  up to keep planned cases in Q4b, planning is shown where it matters, by the bottom-up filling of Q4t.

## 10 Nov 2026

- **Section 3.3 lists what the base application contains instead of naming the Control Component
  templates.** *CIRP*. "It holds what IDTA's Control Component templates describe" read as if the
  program held those templates (or the registration manifest, the profile sent to the registration
  service, which is outside the IEC 61499 program). As generated (`modgen/module.py`), the base
  application has the occupation block, the PackML state manager, one block per equipment item, an
  instance of each offered primitive skill and the Resetting and Stopping procedures; every skill
  is called through Start, Stop, Abort and Reset over OPC UA. The paragraph now says that. IDTA
  02015 and 02016 left the paper: no submodel of them is used.

- **The resource hierarchy nests as deep as needed; the paper considers two levels.** *CIRP*. The
  co-author's point: a component may have components of its own, and composite skills over their
  primitives, as Hierarchical Structures nests to any depth. The paper says so first, then that it
  considers the module and its components only, which is what the planner and the synchroniser were
  evaluated on.

- **A balanced voice: "this paper", "the approach", "the planner", "we" only for choices and
  experiments.** *CIRP*. The rewrite of the same day used "we" 50 times. Now: "this paper" where the
  work is positioned (abstract, introduction, related work, conclusion); the approach, the planner or
  the synchroniser as subject, or the passive, where the system is explained; "we" kept where the
  authors chose or did something (the extended constraints, GTPyhop over PDDL, constant rates assumed,
  composites as subapplications, the evaluation, the reference model, the expectation that it carries
  over): eight left. The reviewer's second version was not pasted in, as it brought back its content
  errors (units converted, submodel identifiers, the depth range, postconditions checked, the
  application rebuilt) and three display equations.

- **The paper rewritten for readers: the workflow and the filling example first, the planner in named
  steps, "we" and shorter sentences.** *CIRP*. A review (ChatGPT, passed on by the co-author) found the
  paper precise but dense: Section 3 catalogued submodels before saying what the system does, and the
  planner mixed goal regression, parallel execution and coordination in long sentences. Its rewrites
  were taken, checked against what is built, and corrected where they were wrong: units are never
  converted in matching (a unit that differs gives unknown); the primitives' capabilities are in the
  module's Capability Description, one set per component, not in the components' AASs; the elements
  keep the templates' semantic identifiers (not "submodel identifiers"); the needle starts at the
  middle of the positions all bounds allow (the bottom clearance included), not of the depth window;
  the checker applies postconditions and checks preconditions, invariants, the bounds and the end at
  rest; a new primitive needs a new build of the runtime, not of the application; the check takes
  1.8 ms as a median, not a mean; the validation requirement is GAMP 5's, not the modular-pharma
  paper's. Added, as the review asked: a Method opening that walks the workflow; the bottom-up example
  in the introduction; GAMP 5 softened (reuse is attractive, but a composition must still be verified);
  the planner's goal regression, parallel execution, coordinated execution and checking as named
  steps, with h = ax + by and ar + bs = 0 inline; the two evaluation tests said to be separate (104
  matching cases and 24 bottom-up cases; 1,260 deployment runs and 1,258 drift runs); what the rule
  baseline is (six sequence rules as a tool expert writes them). The conclusion follows in the same
  tone. 4,574 body words, about 80 more than before (the room the co-author said was left); 17 sources.
  Not done: Fig. 1's simplification, which the review also asked for.

## 9 Nov 2026

- **Second cut: half a column more.** *CIRP*. At 4,726 words the paper was still half a column over
  (with the taller Fig. 1 and its references), so about 290 words more had to go; the body is now
  4,468 words. Out: Albus et al. (one sentence and one row of Table 1; Blumhofer et al. stay as the
  closer AAS work), 17 sources; the Method section's roadmap paragraph (its subsections and Fig. 1
  carry it); the Control Component comparison in the Skills paragraph (the templates are now named,
  with their IDTA numbers, in Section 3.3, where the base application holds what they describe); the
  placement below DIN 8580 and VDI 2860; the conclusion's limits said in fewer words, every point kept;
  shorter captions of Fig. 1, Fig. 2 and Table 1.

- **The paper cut back to six pages: the PDDL comparison down to one sentence, every paragraph
  tightened, two sources out.** *CIRP*. Compiled at 5,462 words it ran onto a seventh page (about 18
  lines of text and all the references); the body before the day's additions, 4,624 words, had fit.
  Estimated from the PDF at about nine words a line, the body had to lose some 650 words; it is now
  4,726. Kept: the product, process and resource AASs with their IDTA numbers, the vocabulary and its
  link to the AAS, how the AAS becomes a GTPyhop domain with the vial, the coordinated steps and their
  one pattern, the refused bounds, the shortcomings in the conclusion. Cut: the PDDL 2.1 and HDDL
  comparison and the export to standard planners (one sentence says why GTPyhop: numbers and formulas
  directly, a method computes a rate, milliseconds in the process that reads the AAS); the roadmap at
  the end of the introduction; the deployment tests' opening question; implementation details of
  Section 3.3 (the publish/subscribe channels, what the management protocol reports, the arguments
  checked against limits); the sentence that composites offer what their steps contribute; repeats
  (decisions drawn by hand, said in the conclusion; networks of instances costing blocks, said in
  3.3). Sources: PDDL 2.1 (Fox and Long) went with the comparison, and Terzimehic et al., one sentence
  and one row of Table 1, went as the least needed; Schwörer et al. stay. 18 sources.

- **One capability matcher, in Python, for the web UI, the agents, the plan check and Q4.** *Journal*,
  *CIRP* where the matching rules are described. Matching was written four times in two languages
  (the web UI's `capabilityMatching.ts`, `lineagents.aas`, `modreg.plancheck.covers`, `cell/eval/q4.py`),
  with the broader-class route only in the UI. Now `modreg/match.py`, behind the skill service's
  `POST /match`; the UI is its client (commits c94af1a to 437236f; the fork's 8e9a0a7 to 7c96c87,
  local, not pushed). Instead of keeping the matchers alike, or a shared rule specification: the
  agents, the plan check and Q4 are Python, and the service already plans and checks.
  - The UI's strict rules, not `covers`: units and value types must agree (the unit read from the Unit
    qualifier first, then the IEC 61360 data specification); where no rule compares, the answer is
    unknown, never yes. Extended: a property listing the values a module takes (ContainerType) is
    matched as "one of"; an offered property without a value (a state) is unknown.
  - Each property comparison carries a reason code (`why`: unit, undescribed, state, ...), and each
    caller keeps its own decision: the agents ignore an undescribed property, the plan check writes a
    finding, Q4 needs every property. Instead of forcing one decision on all.
  - Constraints are flagged in matching, not evaluated there: the checker evaluates them in time.
  - Narrower classes count as an option (`narrower=`), on for the agents only: unknown ranks above
    mismatch, so a narrower offer could otherwise win where it should not (a syringe skill for a vial).
  - Only capabilities of role Offered count (the agents and the plan check looked at the components'
    sets too); the plan check takes the offer the bound skill realizes, not the first of its meaning.
  - The service computes the values a plan or check is asked with, text included (ContainerType =
    syringe), and `/plan` with write derives the module's offered capabilities, so the Skills plugin
    and Match and plan behave alike. Differences found and fixed between them: the Skills plugin sent
    the capability's display name, keyed values by display names, turned text into NaN, suggested
    property names as results and never derived. Left, as right: its default name `Planned<Capability>`
    (no product there), and planning without a requirement check (it has no requirement).
  - A constant a planned skill sets is written as a number (`xs:double`), not as text; the strict rules
    showed it.
  - Q4 re-run on the matcher: every verdict and answer as in the paper's run (373 rows, 0 differ). The
    agents' offers on the example line: 1,134 calls, all as before.
  - Data fixed with it: `cell/examples/bottom_up_syringe.py` set mm in the Unit qualifier of the bounds
    and the barrel's geometry but left FillVolume's mL in their data specification; both now say mm
    (the product on the server keeps the old until the script is run again).

- **The paper describes how the AAS becomes a GTPyhop domain, with GTPyhop's use in production
  cited.** *CIRP*. The co-author found the conversion under-described. As `modplan.plan` builds it
  (dumped for the filling module on 9 Nov): a state variable per meaning a constraint is about
  (`v_Position`, `v_ContentVolume`, each subject to value); an action per capability of a component
  (Positioning, Dosing, Referencing, Taring, Weighing), a Python function that applies the Post if
  the Pre holds and every invariant and the requirement's bounds hold at its start and its end; a
  unigoal method per postcondition (`m_Dosing_ContentVolume`; `m_Referencing_Position` before
  `m_Positioning_Position`, as a Post `=` comes before `given`), which returns the action's unmet
  preconditions as goals and then the action; GTPyhop's `m_split_multigoal` for the two goal lists
  (the required capability's Post, then the rest state); depth-first refinement with a verification
  of each goal after its method (`_verify_g`), backtracking otherwise. The trace for 2 mL into a vial
  (Dosing, its precondition a goal reached by Positioning, Referencing for the rest state) is the
  paper's example. Source: Belcamino et al. (RO-MAN 2024), GTPyhop for HTN planning of collaborative
  assembly, whose plans are built by hand from primitive actions and whose conclusion names automating
  that as what would make it more versatile, which is what the generated methods do. Searched for
  GTPyhop or Pyhop in production systems: none other peer-reviewed; Parashar et al. (arXiv 2103.07544)
  use Pyhop for robotic assembly, "sufficient" for tasks of low complexity, but their venue is unclear,
  so not cited. The paper now has 20 sources, one above the 19 it had; the memory note of 17 is out
  of date.

- **The paper says why GTPyhop and not a planner for PDDL 2.1 or HDDL.** *CIRP*, *Journal*. Asked by
  the co-author. Three reasons, each from what was built: GTPyhop works on the AAS's numbers and
  formulas directly, which HDDL 1.0 lacks (the export makes every value an object and every sum a
  fact, and Aries grew from 0.08 s to 6.8 s from 1 to 20 doses on it); a method computes the rate of
  coordinated steps by one equation, where a PDDL action takes only objects, so rates would have to
  be discretised and left to a temporal planner's search (OPTIC, COLIN, PDDL+: hard to bound in time,
  6 Nov); and it plans in milliseconds in the process that reads the AAS and runs the checker (1 to
  2 ms, against about 300 ms for ENHSP and 40 to 60 ms for Aries through unified-planning, which
  starts the planner for each problem). That the domain is not tied to GTPyhop rests on the export:
  the four sequential cases of `cell/eval/planners.py`, re-run today on the current tools, are planned
  by ENHSP on the PDDL and Aries on the HDDL, every plan valid (results of 28 Oct kept; today's run
  the same). HDDL, ENHSP and Aries are named without a reference: the paper is at its 19 sources.
  GTPyhop is used for goals only (hierarchical goal networks), not for HTN tasks: the methods are
  generated from the capabilities, one per postcondition, and the same methods are what the HDDL
  export writes as compound tasks.

- **The paper says where the vocabulary comes from, how the AAS links to it, how simple the planner
  is and what it cannot do.** *CIRP*. Asked for by the co-author after tracing each fact of the
  planning to its source. Section 3.1: the vocabulary is an OWL ontology of our own on the CSS
  ontology; each capability, property and skill parameter names a class of it as a supplemental
  semantic id, the semantic id staying the template's; it states what holds of a class everywhere,
  the AASs what holds of one product or module; it is an ontology because narrowing and rates are
  relations between classes that tools follow by inference; a module's Capability Description
  restates its classes' constraints. Corrected: the rate relation is the vocabulary's (`rateOf`), not
  an element of the template; a composite's decisions may be on a parameter, not only a result.
  Section 3.2: the planner is deliberately simple; the rate set is the one the module states as a
  range; the one pattern of coordinated steps is spelled out; a bound on a quantity with no formula,
  or a nonlinear one, is refused (the fix of the same day). Conclusion: the shortcomings that matter
  most, each checked: first plan, success and exact rates assumed (the planned filling keeps the
  needle 0.5 mm within its bound; with the checker, a pump 1.7 % slow breaks it, 15 % fast does
  not); decisions drawn by hand; the recipe's conditional steps modelled and bound but skipped by the
  agents (`lineagents.aas.steps` reads the top-level steps only); the vocabulary the lab's own and
  restated in each module. To make room: Section 3.3's two details of reading back (dotted names,
  constants), Related Work's 2^n sentence (Section 3.3 says it with the citation) and Section 4.1's
  two runtime patches (the conclusion still names them). The paper is about 290 words longer.

- **A requirement's bound is kept or refused, never assumed; the rate rule completed; ComposedOf
  out of the planner.** *CIRP*, *Journal*. Three gaps found while tracing where each fact of the
  planning comes from. (1) The checker skipped a bound whose quantity no running step defines, which
  is right between doses (the needle's depth is defined only while it doses) but also let a module
  that states no formula for the depth have plain Filling planned and checked as BottomUpFilling
  (tried: without Dosing's formula the planner returned MoveAxis 40, Dispense, Home). Now the
  planner refuses a bound on a quantity the module neither defines by a formula, changes, nor
  starts with, and the checker reports a bound of the requirement that no step made known.
  (2) `Domain.nonlinear` existed but nothing used it, although checking bounds at the events only is
  exact for linear formulas alone: a requirement with bounds over time is now refused by the planner
  and reported by the checker when a formula is not linear in what changes. (3) The coordinated steps
  set a rate only if exactly one of the pair's rates was a parameter (a Range in the Capability
  Description); with both settable the pair was refused unless the defaults matched. Now the rate of
  the step that would break the bound is set to follow its partner's, else the partner's to follow
  it, whichever stays within its range. Which rate can be set is the module's to say (a Range or
  one value: the pump's FlowRate is a Dispense input with limits, the axis's Speed its equipment's
  one value); the vocabulary says only what a rate is the rate of. The FlowRate input's description
  in `filling.yaml` said "calibration", which the planner contradicts: now "a planned skill may set
  it within these limits". (4) IDTA 02020's ComposedOf (an optional relation of a capability, beside
  RealizedBy, GeneralizedBy and the constraints) was an outer loop of the search that nothing fed:
  `read.py` never read it. Removed rather than wired, as a module's few primitives need no hint and
  a composite's parts are already its Skills flow; it could return as a search hint for large
  domains. The paper never mentioned it. Tests: `tests/test_modplan_bounds.py`. Q4 re-run on these
  changes before they were committed (`cell/eval/results/q4-2026-11-09T1348.jsonl`): every mutant's
  verdict and every answer as in the run behind the paper (`q4-2026-11-06T1253`), so its numbers stand.

- **Section 3.2 in plain words, walked along the filling case; the equation out.** *CIRP*. The
  co-author asked what "lifted to a partial order" and the COLIN sentence meant, so a reader would
  too. The section now names the planner's three inputs (the task from the vocabulary, a narrower
  class inheriting the broader one's conditions; the primitives' capabilities; the module at rest
  and the product's Process Parameters), says that it works backwards from the goal with
  Dispense, MoveAxis and Home as the example, and says instead of "lifted" that only the orders
  that matter are kept (the planning term is deordering, Bäckström 1998, not cited for the limit of
  19 sources). Equation (1) became a sentence: constant rates between events make a weighted sum of
  states a straight line, so a bound that holds at both ends holds in between. GTPyhop is said to be
  used with goals only and with methods generated from the capabilities, not written by hand, as
  a reader who knows HTN planning would ask; COLIN is named for the shared assumption, with the
  difference (a linear program over all events, against one equation and a domain read from the
  AAS). Section 3.1 points to case 3 of Fig. 2 for the three additions instead of its "top", which
  does not show them. About as long as before: 79 words more, the display equation gone. Not said,
  as the paper has no room: IDTA 02020's ComposedOf, which the planner would try first, is not read
  from the AAS yet, so it plays no part.
- **Fig. 1 and Section 3.1 name every AAS with the submodels the approach uses, as on the lab's AAS
  server.** *CIRP*. The figure showed two of the product's submodels and no process AAS, while the
  approach follows a step of the Production Sequence to its process in Process Parameters (IDTA
  02031-1) and from there to the required capability in the Capability Description (IDTA 02020); and
  the product's facts that the planner starts from (a container's diameter, bottom and rim) are
  Process Parameters' product parameters, not the Capability Description's, as the text had said.
  Now the product shows all three; a process AAS card of its own shows Process Information,
  Bindings and Validation, which matching writes (an arrow back from Match and plan) and the
  orchestrator runs; the module adds Hierarchical Structures and notes Nameplate, Variables and
  AIMC; a component shows its Skills holding its primitive. The product's requirement reaches
  matching under the process card, so no arrow crosses a card. The line row grows by 13 px and
  the module card by 11 px (Fig. 1 is 18 pt taller). The text says that one resource type describes
  line, module and component alike, a component holding only its primitives' Skills and a module
  what it needs as the unit the line calls, connects and reconfigures, and that the process AAS
  holds the full plan, authored by hand or written by matching, into which a planned and deployed
  skill is bound like any other. The IDTA numbers stand in the text (02006, 02011, 02017, 02020,
  02027, 02031-1; Control Components 02015 and 02016) instead of as references, which would break
  the limit of 19 sources; the lab's own submodels are named as such.

## 8 Nov 2026

- **Pharma enters through validation (GAMP 5); the approach is said to carry over.** *CIRP*. "Pharma
  shows this most clearly" overstated it, and "sometimes to single units" rested on a source not
  checked here. What sets pharma apart is that every change of a line must be validated: GAMP 5 (ISPE,
  2nd ed., 2022) scales validation with risk and treats configured software (category 4) as less risky
  than bespoke software (category 5), so reconfiguring proven parts instead of engineering new ones
  lowers the risk and shortens validation. That is why building a skill from fixed primitives matters
  there. GAMP 5 is the 19th source. The conclusion now says nothing is specific to filling or to
  pharmaceuticals, so the approach carries over to discrete production in other domains, with the
  coordinated steps as the example and the caveat that only filling was evaluated.

- **Broad opening, pharma as the clearest case; the title stays general.** *CIRP*. The abstract and the
  introduction began with pharmaceutical production, which the title never named. Both now open with
  manufacturing in general (small batches of varied and personalised products). The introduction then
  brings pharma in as the domain where the trend is clearest ("as medicines become personalised, batches
  shrink, sometimes to single units, and modular factories are proposed to keep pace", Schwörer et al.
  2025), and returns to modular lines in general ("In such lines, the AAS …"). The abstract names pharma
  only where the evaluation does, so the filling module reads as the case, not the scope. Instead of
  putting pharma in the title, which would narrow a method that is not specific to filling.

- **The abstract opens with why and closes with what it means.** *CIRP*. 247 words (limit about 250).
  It starts where the introduction does (small batches and personalised medicines; modules exchanged
  although their components could already do the job), keeps the submitted abstract's framing (IEC 61499
  as "a key enabler of software-defined manufacturing", the AAS "in a standardised, interoperable way",
  "how AAS content can drive such … remains open", the three AASs, primitives as fixed function blocks,
  changes applied online, read back and recorded, Eclipse 4diac on a pharmaceutical filling module),
  and states the evaluation in broad terms ("shows promise": plans agree with the process model, the
  check catches most spoiling flows, new skills in under a second with the module running) instead of
  the figures, which are in Section 4 and Table 2. It ends on the consequence for a line: new products
  through software instead of new modules.

- **Title case for the title and every heading.** *CIRP*. Major words capitalised, minor words (and,
  of, to, on, in, the) in lower case, both parts of a hyphenated compound capitalised ("AAS-Driven").

- **One Method section with a subsection per contribution.** *CIRP*. Sections 3 to 5 (modelling,
  planning, deploying) were three sections with eight subsections between them, which read as
  separate topics. They are now Section 3, Method, with a two-line lead naming its three parts and
  Fig. 1, and three subsections; the former subsections are paragraphs, each opening with a sentence
  that joins it to the one before ("What the module can do is described in two of its submodels",
  "The second, the Capability Description, …", "A checked skill is deployed …", "How a change reaches
  the running program …", "The synchroniser carries out these changes …"). No subsubsections.

- **Discussion and Conclusion merged into "Conclusion and outlook".** *CIRP*. One closing section:
  what the paper showed, what the approach is for (engineering, not changes on the fly) and why it
  generalises, its limits (the process model's authors, the check's misses, simulated inputs and
  outputs, one quantity tracked), and an outlook: the line's agents request plans, decisions on
  measured results are planned (the gap to Schwörer et al.'s planning submodel that matters inside a
  module), and the module's real inputs and outputs. The Discussion's "Matching rates" is now
  "Coordinated steps", and the Introduction's roadmap names one closing section.

- **Related work checked against the sources; Rooker out.** *CIRP*. Every statement in Section 2 and
  every cell of Table 1 was checked against the papers themselves. The planners of Nabizada et al. and
  Köcher et al. sequence capabilities, not skills ("skill-level details are not needed here"; "valid
  capability sequences"), so the Introduction and Section 2 say so. Nabizada's four submodels are their
  own schema built on VDI 3682, IEC 61360 and IDTA 02011/02016, not standard submodels. Lindorfer and
  Froschauer run their own workflow engine (4diac FORTE is their future work), so the paragraph opens
  "For composing skills" instead of "In IEC 61499". Dorofeev's user actions are weighted. Huang's timed
  test replaced a whole network, so "applies it" instead of "applies the differences". "None of these
  approaches" instead of "No approach". Table 1: Albus generate the PFDL their agents run (New (✓)),
  and Nabizada's plans are checked like Köcher's (Check (✓)). Rooker et al. (2007) could not be read and
  backed only what IEC 61499-1 states, so it left; the paper cites 18 sources.

- **Fig. 2's coordinated steps without the plot of h.** *CIRP*. The small plot (a band, the dose alone
  leaving it) came from the bottom-up filling and was hard to read without it. The link between the two
  primitives is now a dashed tie between their tasks, "linked", and one line says how: r is set so that
  a·r + b·s = 0, which keeps h = a·x + b·y within its bounds while both run. The figure is 306 px tall.

- **Repetition and the 15 mL example out of the CIRP paper.** *CIRP*. A dose above 10 mL was split
  in two only because Dispense's Volume parameter stops at 10 mL; a pump dosed by time runs longer, so
  the case is a parameter limit, not a planning problem. Repetition pays off where a step is limited
  for real (a pipette tip, a piston's stroke, a gripper's capacity, a peck's depth), and there the
  repeated unit has a step between (aspirate, return, retract), which the planner would add by
  regression but which no module here models or tests. The planner still splits such a goal; the paper
  shows the three kinds of flow that matter (sequence, parallel block, coordinated steps). The 15 mL
  product's input counts (6, 14, 71) leave the text and Table 2, and with them the Discussion's effort
  comparison with Dorofeev et al.; E1's data stay in the repository.

- **Fig. 2: the four kinds of flow, one annotated row each; "coordinated steps" for the tracking.**
  *CIRP*. The decision and the closing cell left the figure; what remains is what the planner builds,
  drawn bigger in BPMN with why it builds it: the sequence's arrow carries the condition (B sets
  y = p0, A needs it), the repetition fills x in two halves, the parallel block names a component per
  branch, and the coordinated steps show h kept in its band where A alone leaves it. "Matched rates"
  read oddly; "synchronised steps" would clash with the synchroniser (the deployment), so the paper,
  Fig. 2 and Fig. 1's Plan card say coordinated steps. The code keeps "tracking".

- **The planner described as built: GTPyhop with goals only; reuse out of Fig. 2.** *CIRP*. Checked
  against the code and the 81 tests of modplan: sequence (goal methods), repetition (the `+=` method's
  equal doses) and matched rates (the tracking method and its paired action) are GTPyhop; parallel
  blocks come after it, from `lift.py`. There are no task methods, so "hierarchical task networks"
  and "three methods tried in order" overstated it. Stated compositions are not read from the AAS and
  existing composites are not reused (designed, not built), so the Reuse case left the figure; its
  place says that every flow is checked in time and then described. Building them (read
  `ComposedOf` in `read.py`, inline an existing composite's steps) would put the case back.

## 7 Nov 2026

- **Fig. 2 shows what the planner builds, in six cases, not one parallel example.** *CIRP*. The
  planner builds sequences (goal regression orders the steps), repetitions (a goal beyond one step's
  range in equal steps), parallel blocks (lifting: steps that share no component or state), steps at
  matched rates (tracking) and reused compositions or composites. It does not plan decisions: a plan
  has no branches, so decisions come only from flows drawn by hand, which the checker covers (both
  branches). The figure shows the five as small BPMN flows and the decision greyed, "drawn by hand,
  then checked", so that it does not claim more than the planner does. Planning decisions on a
  measured result (conditional planning) would be the next step, not attempted.

- **Fig. 2 made simple: the two inputs, three regression steps with the plan growing beside them, the
  skill in BPMN.** *CIRP*. The five-part version (methods, regression tree, time plot) was hard to
  follow. Now the product's requirement and the module's primitives sit side by side, the planner's
  steps read as sentences with the plan drawn next to each (A; B then A; B then A with B alongside),
  and the result is the BPMN skill. The time model and the order of the methods are in the text only.
  The figure is 312 px tall instead of 480. Fig. 1's short arrows (Match and plan to Plan, OPC UA, the
  arrows in S's flow) were only heads: the module row moved 14 px down and S's steps apart.

- **The CIRP paper restructured after the co-authors' review: generic method, use case in the
  evaluation, related work verified.** *CIRP*.
  - Framing: modules are exchanged when products change, but a module often has the primitives a
    product needs and only the composite skill is missing; the work sits one level below the
    orchestration of a product's process (a single required capability, inside a module). The value
    is engineering and integration, not changing skills on the fly in production: an engineer still
    reviews a planned skill, and the check is a helper, not proof. Online deployment and read-back are
    therefore results, not claims of uniqueness; Table 1 drops the Online and Read columns and adds
    Time (durations or parallel steps planned) and New (a new skill or orchestration).
  - Sections 3 to 5, one per contribution, with subsections instead of italic run-in labels; the
    method is written without the filling case (Fig. 2 made generic, page `planning-generic`), the
    filling module, the syringe and the depth formula are in 6.1. Abbreviations spelled out where they
    occur once (computer-aided design, Module Type Package kept as MTP for the table).
  - The related-work check (sources read, 7 Nov) changed three statements: Nabizada et al. (CASE
    2026) use standard AAS submodels, not planning-specific ones, and leave durations and numbers to
    future work; Terzimehić et al. also generate a network of function blocks (SMT decides only where
    services run); Lindorfer and Froschauer's rules are a tool expert's and the engine is their own.
    Dorofeev et al.'s factor is of user actions, and the 2^n states for n parallel skills is their own
    statement. No code of their generator was found, and no paper names a reason against instance
    networks; the price named here is more blocks and events per skill.
  - Two sources added (19 in all): PDDL2.1 and COLIN, as temporal planning with linear continuous
    change is what the planner's time model restricts to one module. Rooker's year and Lindorfer's DOI
    added. IDTA's Control Component templates are named without a source.
  - Answers to the review's questions, now in the text: Deployment (Built/Described) is a property of
    each skill in the Skills submodel; read-back loses that subapplications are flattened into dotted
    names (the naming rules restore them) and whether a step's value was written or left at its
    default (steps are read with all their constants); Q1's steps are the dose cycle (MoveAxis,
    Dispense, Home, Weigh) and 8 steps in two or three parallel branches; the planner produces
    sequences and parallel blocks, decisions only come from flows drawn by hand.

- **Fig. 3 (activation) stays teal.** *CIRP*. It was recoloured in the paper's gold (the colour of a
  change over the management protocol in Fig. 1) and set back the same day: the co-authors keep the
  green ramp it had.

- **In the papers, the reconciler is called the synchroniser, and the CIRP text is written in plainer
  sentences.** *CIRP*, *Journal*.
  - "Reconciler" is a term from Kubernetes-style controllers and reads as jargon to a manufacturing
    reader; "synchroniser" says what it does (makes the running program equal to the AAS) and matches
    the tool's name, modsync. Fig. 1's box says Synchronise. The code keeps its names.
  - The wording pass splits colon and semicolon chains into sentences, replaces stacked possessives
    ("the module's components' primitives") with "of" phrases and keeps every number and source. It
    costs about 250 words (sections 4,170 against 3,920). Two references then fell onto page 7, so
    the repetition went first: the method's comparisons with Albus, Köcher and Lindorfer shrank to
    one clause each or none (related work and Table 1 hold them), the three levels became one
    sentence, and Fig. 3's caption no longer repeats the restart time (sections 4,084).

- **The CIRP paper rescoped to three contributions on one pipeline: the PPR model in the AAS, the
  planner, the deployment.** *CIRP*.
  - Claim: a product's requirement, stated in its AAS, becomes a new skill running in a module's IEC
    61499 program, from the AASs alone. C1 the product-process-resource model (required capabilities
    with values and bounds, skills down to the primitives, capabilities derived and constrained, the
    vocabulary); C2 the planner (a composite from the requirement and the components' capabilities,
    parallel steps at set rates, checked in time); C3 the deployment (composites as networks of
    instances, the reconciler). Each has its evaluation already: C3 by Q1 and Q3, C1 and C2 by Q4 and E1.
  - Why: the skill editor is close to what Dorofeev et al. have; planning a skill from a product's
    requirement, with what must happen at the same time, is what no related work does, and it is what
    makes the AAS and the capabilities necessary rather than convenient (the user, 6 Nov). Instead of:
    four contributions led by the module architecture (3 Nov), or a paper on the planner alone, which
    would drop the deployment the evaluation measures most.
  - What went to fit six pages: the figures aas-to-blocks and product-to-process, the shell's details,
    the comparison of state machines, BPMN and the editor (a sentence), Q2 from the abstract;
    stolze2024proactive for koecher2024smt (planning on a capability model, no durations). No new
    experiments: the Pi's Q1 runs are added when made. Title chosen by the user: "From product
    requirements to running skills: AAS-driven planning and reconfiguration of IEC 61499 modules".

## 6 Nov 2026

- **Found by Q4b's re-run: the tracking planned a dose the pump cannot give; the checker now says an
  argument beyond its parameter's range.** *CIRP* (Q4).
  - 0.25 mL into the syringe was planned as one tracked dose of 0.25 mL; the pump doses 0.5 to 10 mL.
    The plain dosing method checked the range, the tracking method did not, and neither the paired
    action nor the checker looked at ranges (the spec's validation did, in Q4a only). Now the tracking
    method and the pair keep every argument within its parameter's range, and the checker reports one
    beyond it (`Dispense: Volume = 0.25 is beyond its range (0.5 to 10.0)`), in the editor too. The
    oracle, which knows nothing of the model, is what found it.

- **Match and plan: one button in the process planner binds every step, and plans a skill where none
  matches.** *CIRP* (the automatic planning request; no agents).
  - In the web UI's Process Sequence toolbar (the fork's `utils/matchAndPlan.ts`, committed there, not
    pushed). For each step without a resource: a skill that matches is bound, as Match resources would
    bind it; one that matches but states constraints (a skill written for BottomUpFilling) is checked
    against the requirement in time by the skill service and bound if it keeps it; otherwise a skill is
    planned on a module the matching says can be planned for it, or one that offers a class the required
    one narrows, described in that module's AAS, its capabilities derived anew, and the step bound to it.
    The draft is saved as any other; `modsync reconfigure` builds the skill.
  - Why the narrower class's broader one decides where to plan, and not a module type: no AAS of ours
    has a module type (every module is `.../Resource/Module`), and a type would say what the module is,
    not what it can do; its capabilities say that, for any process. The user's idea ("only plan in
    modules that offer the filling capability") is this, with the lineage from the vocabulary.
  - Checked in a browser (Playwright, the scratch AAS server): the syringe asking for BottomUpFilling, the
    filling module offering Filling; one press planned `BottomUpFillingForPrefilledSyringe1mL` on it
    (the needle to 57.5 mm, the dose at 0.396 mL/s beside the rise to 25.9 mm, home) and bound the step.
    The example line's syringe still asks for Filling: its process AAS, the plan check and the agents'
    tests assume it.

- **The skill service answers what the process planner's Match and plan asks; matching stays in the
  web UI.** *CIRP* (the automatic planning request).
  - `GET /vocabulary/<class>`: what a required class narrows (BottomUpFilling, Filling), so the UI tries
    to plan a narrower requirement on the modules that offer, or can be planned for, a class it narrows.
    No module type is needed: every module's asset type is `.../Resource/Module`, and what a module can
    do is what its capabilities say, which works for any process.
  - `POST /plan/<shell>` plans a class the module does not offer (as the vocabulary defines it) and
    checks every plan in time first; `POST /check/<shell>` with `{"capability", "values"}` checks the
    module's skills against a requirement (Dispensing against the syringe: the needle 19 mm above the
    liquid, then 12.6 mm in it). Instead of: a matching endpoint in the service, which would say again
    what `capabilityMatching.ts` says (meaning, ranges, units, availability).

- **The planner keeps invariants and tracks: a dose paired with the needle rising alongside, the rates
  set so that the depth in the liquid stays as it is.** *CIRP* (the planner, the main contribution) and
  *Journal*.
  - Every action keeps its own invariants and the requirement's at its start and its end; one that
    would break them is not applied (a dose with the needle still ends 30 mm under the surface). GTPyhop
    then backtracks to a second method, **tracking**: the action changes x at a rate (the content), a
    formula of it defines a quantity the requirement bounds from x and y (the depth in the liquid from
    the content and the needle), and another action sets y to what it is given at a rate (Positioning).
    The pair runs as one step, the second in parallel (`Planned.along`, lifted to a parallel block).
    The rate that can be set is set so that the quantity does not change (the axis's speed is fixed, so
    the pump's flow rate: 0.396 mL/s for the 1 mL syringe at 12.5 mm/s); where y starts is the middle of
    what every bound of both actions and of the requirement leaves at the start and at the end, each
    linear in it (57.5 mm: between 2 mm above the liquid and 1 mm above the bottom), or where it is if
    that will do (a second dose). Nothing in it is about filling: the pair, the rates and the start
    follow from the formula, the rates and the bounds the domain states.
  - Instead of: PDDL+ or a temporal planner (OPTIC, ENHSP's processes): the domain would have to be
    rewritten as processes and events, the planners are hard to bound in time, and tracking a quantity
    is one linear equation here. Instead of: a fixed rate pairing written into the module (a
    "bottom-up skill"): it would hold for one container.
  - Every plan is checked in time against the requirement before it is described (`compose.planned`).
    A capability the module does not offer yet is planned as the vocabulary defines it
    (`compose.requiring`); planned for a narrower one, the skill says it was written for it
    (`pprl:writtenFor`), so the module offers BottomUpFilling after a reconfiguration. `discover` leaves
    out a class whose constraints need what only a product says (BottomUpFilling's bounds): it is
    planned when a product asks.
  - What follows, on the module as described: 0.25, 0.5 and 1 mL into the syringe plan in about 2 ms;
    raised 5 mm (the bottom 64 mm down, the axis 60 mm long) there is no plan, which is Q4b's "not
    offered" where the written BottomUpFilling said "offered".

- **The checker runs a parallel block in time, event by event, and checks a requirement's invariants.**
  *CIRP* (Q4, the time model) and *Journal*.
  - A step keeps its invariants from its start to its end: checked at both (before, a step's invariants
    were looked at only against another branch). A parallel block whose steps all say how long they
    take is run in time: a branch starts its next step when the one before ends, every state a step
    changes moves at its rate, and at each event (a step starting or ending) every running step's
    invariants, a defined quantity (OutletImmersion) and the requirement's invariants are checked.
    Between two events every rate is constant, so a linear invariant that holds at both holds all along:
    exact without time steps. Instead of: a 10 ms simulation like the oracle's (a second model of the
    physics to keep in step, and not exact), or a hybrid-automaton checker (more than linear needs).
  - Where a step does not say how long it takes, or a decision is in the block, the block is checked
    as before (each invariant against every state the other branch passes through): conservative, never
    weaker than it was.
  - What it changes, against the physics: at 0.7 mL/s a 1 mL dose is in after 1.43 s, and a needle
    rising from 58 mm at 12.5 mm/s passes 40 mm at 1.44 s: kept, where the ends of the move alone
    (30 mm) were a refusal (Q4a's nine refusals stricter than the physics were so). Home from home moves
    nothing, so weighing beside it is no longer a conflict. `check(..., task=, values=)` takes a
    requirement (BottomUpFilling and the product's bounds), and `timed` gives how long a skill takes
    (Dispensing: 7.6 s).

- **Rates, durations and the container's geometry in the Capability Description (vocabulary 0.10).**
  *CIRP* (the time model, the syringe) and *Journal*.
  - A property can be the rate of another (`lab:rateOf`): FlowRate of ContentVolume, and a new Speed
    of Position. A capability that has it changes that state steadily from its start to its end and
    runs as long as the change takes. The axis's Speed is written into Referencing's and Positioning's
    PropertySet from the spec's `position.speed`, for any item with a position. A primitive with no
    rate takes what its Completion `After` says, read from the component's Skills submodel (not through
    `described()`, whose skills regenerate programs). Instead of: durations as a property of their own,
    which would say twice what the rate and the change already say.
  - The container's geometry is the product's: InnerDiameter, InnerBottomHeight and RimHeight above
    the face it stands on in its nest, product properties with no value in the module's AAS. Where that
    face is on the axis is the module's (NestPosition, 70 mm). From them the module's Dosing states
    OutletImmersion, how deep the tip is in the liquid, by a formula; Positioning keeps the tip 1 mm
    above the inner bottom (the crashes Q4a missed). Chosen by the user over the geometry in the process
    AAS (the planner would need a process AAS first) or per container in the module (every new
    container would mean editing every module).
  - The needle stays 5 mm below the container's rim while it doses (`>= NestPosition - RimHeight +
    InsertDepth`), in place of `>= FillPosition`. Why: a 1 mL syringe filled from the bottom has the
    needle follow the liquid up to about 27 mm, above the fill position of 40 mm, which was a vial's
    rule written as the module's; in a 2R vial the new bound is 40 mm again. The fill position stays
    the dose's precondition, where it starts. What it costs: without a product the checker cannot tell
    whether a needle that rises while dosing leaves the container (T14 now gives the 2R vial).
  - BottomUpFilling is now a Filling that keeps OutletImmersion between MinImmersion and MaxImmersion,
    bounds the product gives. What made it narrower (vocabulary 0.6: how the skill moves) is now a
    constraint, so it can be planned, and a skill written for it can be checked against a product. The
    upper bound is what makes the needle's rise necessary: with the tip allowed anywhere deep in the
    liquid, a needle that stays at the bottom would do. The classical PDDL export leaves the formulas
    out: they say how a state follows in time, which a sequential plan does not see.

- **A constraint's operand may be a linear formula of the capability's properties.** *CIRP* (the
  time model) and *Journal* (the constraint language).
  - `BasicConstraint` held `<op> <value or one property>` (ARSO 0.11). It now also takes a formula of
    numbers and properties with `+ - * /`, brackets and `pi`: `= LinearAxisPosition - NestPosition +
    InnerBottomHeight + 1000 * ContentVolume / (pi * InnerDiameter * InnerDiameter / 4)`. Still one
    BasicConstraint, so the AAS stays IDTA 02020; the language is ours, as 02020 leaves it open.
  - It has to be linear in the states the capabilities change; a product of two of them, or a division
    by one, is refused when the domain is read (`Domain.nonlinear`). Constants may be multiplied (the
    diameter squared). Why linear: with every rate constant between two events, a linear condition
    holds all along a stretch if it holds at both its ends, so the checker looks at events only and is
    still exact, with no time steps and no hybrid-systems solver.
  - An Invariant `=` a formula about a property nothing else sets defines that property while the
    capability runs: a derived quantity (how deep the needle is below the liquid's surface) that a
    product's requirement can then bound.
  - Instead of: derived properties defined by formula in the vocabulary (chosen against by the user,
    6 Nov). A formula that mixes the module's facts (where the nest is on its axis) with the product's
    (its inner diameter) belongs to the module's capability, not to a vocabulary shared by every line.
  - A capability also says how long it runs (`Capability.duration`): the longest change it makes at a
    rate, else its skill's Completion `After`; not known if neither says.

- **The capabilities placed below DIN 8580 and VDI 2860, as HSU's ontology design patterns state
  them (vocabulary 0.9).** *CIRP* (a sentence and a citation) and *Journal* (the ontologies).
  - A capability class of the lab is also a subclass of the standard's class it is a kind of: DIN 8580
    for what changes the product (Filling and Dosing pouring, 4.2.1; Stoppering and Pressing press
    fitting, 4.3.4; Crimping joining by forming sheet metal, 4.5.2; Capping joining, as a cap may be
    crimped or screwed), VDI 2860 for what moves or checks it (Positioning, Transporting as conveying,
    Weighing as measuring, Imaging and Inspection as checking). Copies of both are in `ontology/`.
  - Why: the split between what a product can require and what only serves other skills (load a
    magazine, turn a vial, move an axis) then rests on standard classes a reader knows, and CaSk and
    Köcher's planning use the same two. The standards' classes carry no constraints, so nothing that
    planning reads is inherited; our process/auxiliary split stays ours and runs across both standards.
    Instead of: our own classes under each other (the caution of 0.2), or no taxonomy at all.
  - Not placed, rather than guessed: Referencing and Taring (they set a component up), Receiving and
    Releasing (custody; VDI 2860's holding and releasing mean clamping), Loading, Unloading, Unpacking
    and Packing. VDI 3682 was read and not imported: its states, inputs and outputs say what pre and
    post say, with no time or rates.

- **The effort of a reconfiguration measured in the UI's own inputs, against 4diac counted from the
  generated program.** *CIRP* (E1, a table).
  - The skill editor and the planner are driven in a browser (`cell/eval/ui/effort-ui.cjs`, Playwright)
    on the shortest path the UI offers, and every input is counted. The skill each run saves is read back
    from the AAS and compared with the task's target, so a count stands for a change made right.
    Instead of: the 29 Oct estimate from the skill's model (an action per element), which counted
    parameters typed in the editor that the editor never asks for.
  - 4diac cannot be driven so. Its count is the difference between the program before and the
    generator's program for the target, an input per element. A new skill is made by copying
    Dispensing, with the pasted blocks paired to the target's so that the inputs are fewest. Instead
    of: building every skill new in 4diac (143 to 164 inputs), which would flatter the method. The count
    is a lower bound: no searching, reading or renaming.
  - Four tasks: a value, DoubleDose, BottomUpFilling and a 15 mL product. 4diac takes 3, 55, 60 and 71
    inputs; the editor 4, 14, 25 and 14; the planner 6 for the product. Reaching the running module is
    counted apart: a restart against one command online.

- **Q1 and Q3 run again on the refactored types; the paper reports the new runs.** *CIRP* (Q1, Q3).
  - The runs of 4 Nov ran on block types from before the 4 Nov refactor. The application program is
    the same, but the program the paper describes runs on the new types, so the evaluation's FORTE
    was rebuilt with them and both full runs were made again. Instead of: keeping the 4 Nov runs and
    stating that the types changed since, which would leave the paper's numbers measured on code it
    does not describe.
  - Every count and verdict is the same. Activation is 3 to 28 % slower (0.396 s instead of 0.352 s
    at 32 steps and 20 composites): the new types have more inputs that the reconciler reads back and
    compares. The 4 Nov runs stay in `cell/eval/results`, and the differences are in
    [cirp-evaluation.md](cirp-evaluation.md).
  - New figures: the time a module cannot take a product, per kind of change and split into its
    parts (`unavailable.pdf`), and detection per kind of drift against the baseline
    (`detection.pdf`). Instead of tables only: the first shows at a glance that a value changed
    during an order costs almost a restart, as both re-home the axis.

## 5 Nov 2026

- **Q4 judged by a process model of the filling station, not by the AAS's own conditions.** *CIRP*
  (Q4), *Journal* (how far capability conditions carry).
  - The oracle (`cell/eval/process_model.py`) runs a flow in 10 ms steps: the tip moving at the axis's
    speed, the pump dosing, the scale, the branches at once, one holder per item. It knows the
    containers (rim, bottom, capacity, diameter) and the physics: spill, crash, overflow, foam when
    filled from the bottom, volume, a weighing on a tared scale with nothing touching or moving, the
    tip out at the end. It shares only the hardware's ranges with the AAS. Instead of: the outline's
    "a process model of needle depth, liquid, spill and weight" left open; and instead of judging by
    the module's conditions, which would measure the model against itself.
  - The check is what the paper describes, in three parts: the module spec takes the skill (limits,
    names, results), `modplan.check` finds no failing condition, and what the flow leaves
    (`modplan.check.simulate`) is the product's volume and weight. The baselines are the structure
    the 4diac IDE checks, and six sequence rules written beforehand, as a tool expert writes them for
    a workflow engine [lindorfer2019user].
  - Matching (Q4b) is judged against a truth found by running, in the oracle, the built skill and
    then witness flows built from the product and the hardware alone. A capability whose narrowing
    lies in how the skill moves (BottomUpFilling) cannot be planned, so it is offered only by a
    skill written for it.
  - The first runs are not counted, as the harness was not committed yet. They showed what the
    conditions leave out: Taring has no condition, and the container's geometry, the foam and the
    timing are in no condition at all. The checker also takes only the ends of a move, without its
    speed, so it rejects a rise that the dose finishes before. Kept as found; they are the paper's
    limits of the check.

- **Templates for the students' new types: generated, with their own part marked.** *CIRP* (what a
  person makes by hand per primitive and per piece of equipment, and what is the same in every one).
  - For the stoppering and capping modules, `docs/filling-program/templates` holds one template of
    each type a student makes: `EC_`, `EL_`, `EV_`, `EQ_`, `EP_Template` (equipment with one input
    and one output), and `SC_`/`SK_TemplateUntil` and `SC_`/`SK_TemplateTimed` (a primitive that a
    signal ends, and one that a time parameter ends).
  - In each template, every pin, block, algorithm line and channel size that is the student's own
    says *YOUR OWN* in its comment, with how many there are (one per input pin, one per command).
    The rest is the same in every type of its kind.
  - `make_templates.py` generates them with `modgen` from a neutral entry added to a copy of each
    module's spec, and then marks them. So they are always the generator's current types and pass
    the IDE's check. The marking rule is that a line or pin naming a placeholder (`MyInput`,
    `MyOutput`, `MyParameter`) is the student's own, plus the contract's two algorithms and the
    sizes.
  - Chosen instead of:
    - hand-written template files, which go out of date with the generator;
    - only "copy the nearest lab type" (section 10 of the guide), which leaves the student to find
      which parts of `EL_Piston` are the piston's. Both routes stay.
  - The marked templates make the split between the student's own part and the shared part, which
    the paper measures, visible in the types themselves.
- **The student package is complete: the FORTE kit and a PDF of the guide go into the zip.** The
  PDF is made by pandoc to HTML and then printed by a headless Chrome. LaTeX was not chosen because
  the guide's pictures are SVG, which a browser prints as drawings (sharp at any zoom), and because
  the guide's contents links and its bookmarks carry over. *CIRP* (the material students build
  with).

## 4 Nov 2026

- **Students make the real modules' new blocks by hand, by copying the nearest type.** *CIRP* (the
  effort of a new skill by hand in 4diac: what a person makes per primitive and per piece of
  equipment, without the generator).
  - The students build the stoppering and capping modules' new equipment and primitives in the
    4diac IDE and FORTE with the kit (`build-project.ps1`, `deploy-pi.ps1`), never with `modgen`.
    So the filling guide (`docs/filling-program.md`) now says nothing about the generator; its
    section 10 makes a stopper feeder and its primitive block by block, and section 11 builds and
    deploys them with the kit. The generator's side of the guide went to
    `docs/filling-program/maintaining.md`, which the students' zip leaves out.
  - The way of working is to copy the nearest type with the IDE (copy, paste, a new name; *Change
    Type* for the blocks inside) and change only one's own part, rather than to make types from
    nothing. It works because what modgen makes is regular: `EL_` and `EC_` have the same state
    machine in every piece of equipment without a position (`EL_Piston` and the feeder's `EL_Feeder`
    differ only in their pins' names), and the stoppering `SK_Home` has the same 5 blocks and 44
    connections as `SK_FeedStopper`. The guide counts what is one's own: for a primitive on
    equipment that exists, the contract's two algorithms (8 lines for the feeder) and 5 of the 44
    connections in `SK_`; for a piece of equipment, its pins (one IO block each, the pins' names in
    the algorithms) and its command table. That count shows how much of a hand-made skill is reuse,
    next to the paper's count of user actions.
  - The kit now carries the capping project too (`make-kit.ps1 -Projects`).

- **Adapters join a primitive's contract, run and port: one connection each.** *Journal* (how much a
  person wires per primitive).
  - The contract told the run eight values with two events, and the run and the port exchanged a
    command of four values, two events and the holder: 16 single wires in every primitive, the same
    every time. Now `AContract` (contract's plug `Run` into the run's socket `Contract`) and
    `AEquipment` (the run's plug `Equipment` into the port's socket `Skill`) carry them, and the
    contract writes `Run.Post := AtHome;` instead of having outputs of its own. The stopper feeder
    is 44 connections instead of 56. A primitive without equipment gets `SKILL_NoEquipment` as its
    port, which plays every command at once.
  - Only inside the generated types: the application has no adapter, so the boot file, the reading
    of a running program (`modsync`) and the module rules are unchanged. Chosen instead of an
    adapter between a module level skill and its steps (the 4diac skills example's `IAS_Skill`),
    which would take the most wires out of a sequence but needs adapter connections created online,
    flattened from the system and read back by `modsync`: the next step if wanted. The equipment's
    signals stay single wires from the port to the contract, because they differ per equipment and
    an adapter type is fixed. The IDE export names an adapter `_adp`: `runtime/validate.ps1` counts
    those too.

- **A skill primitive is its contract; the run and the equipment port are shared.** *Journal* (how
  much has to be engineered per skill), *CIRP* (a new primitive is a small, checkable piece).
  - Before, each primitive had its own basic type `SL_<Skill>` of 23 states and 41 transitions, of
    which only five things were its own (precondition, postcondition, invariant, the command with its
    argument and time, the closing command and results), and five blocks to reach its equipment
    (`EqState`, `EqView`, `Driver`, `PhaseT`, `EqCmd`) wired the same way in every primitive of that
    equipment: 13 blocks and 68 connections for a primitive without parameters.
  - Now: `SC_<Skill>`, the contract, a basic type of 5 states whose two algorithms are those five
    things in ST (`Pre := Homed; Post := NOT Moving AND ...; Command := 3; Arg := Position; ...`);
    `SKILL_Run` in the library, one run of any primitive (the old `SL_` state machine, its conditions
    and constants as inputs, with its two timers); `EP_<Item>`, the equipment as a skill sees it, one
    type per equipment (state in, command out, the command table inside). A primitive is now
    `Control`, `UaStart` and its parameter blocks, `Contract`, `Run` and `Port`: 7 blocks for MoveAxis
    instead of 13. `EV_` also names the equipment's channels, which `SL_` used to.
  - The interface of `SK_<Skill>` (rule set 2, section 2) and the behaviour are unchanged; FORTE has to
    be built again (new types). Chosen instead of one contract block of library comparisons
    (`SKILL_Condition_*`), which would make a primitive need no type at all but cannot express
    `ABS(ActualPosition - Position) < 0.001` without a block per operator; that is the next step if
    primitives are to be made online.
  - Found while building FORTE: the 4diac IDE 3.3 export cannot give a value to an input of a
    composite inside a composite (the C++ has no such member), so the port takes the item's name from
    its type (`EP_<Item>`, which names the channels), and `modsync` reads a primitive's equipment from
    the port's type instead of the old `Logic.Equipment` value. And a parameter may not take one of
    the contract's names (Capping's `Crimp` has a `Duration`): the contract's time is `RunTime`, and
    the spec refuses such names.

- **Who may command a skill is decided in front of its state machine (SKILL_Gate).** *Journal*
  (the skill's behaviour as a readable state machine), *CIRP* (the same skill interface, unchanged).
  - `SKILL_Control` had 25 states and 101 transitions: each of its 7 waiting states had to take each
    of the 4 OPC UA requests, each check had to jump back to the state it came from (`Here = 0..6`),
    and the module's Aborting, Stopping and Clearing were handled again in every state.
  - Now `SKILL_Gate` (in `SKILL_Core`, 10 states, 24 transitions) answers a client's Start, Stop,
    Abort and Reset at once, with the same checks and error codes as before, and passes an accepted
    one on as the command a parent gives; a parent's command goes through unchecked, and the module's
    state becomes a command too (Aborting or Aborted aborts, Stopping halts a skill a client started,
    Clearing or Stopped resets an aborted one). It decides on the skill state `SKILL_Control`
    publishes. `SKILL_Control` sees only START, HALT, ABORT and RESET: 20 states, 32 transitions.
  - The behaviour seen from outside is the same: the methods, answers, error codes and states. Chosen
    instead of keeping one block with a better drawing only: the transitions were many because the
    one block mixed two questions (may this caller do this now? what does the skill do?).
  - The module's PackML state machine had the same pattern (18 states, 87 transitions). Now
    `MOD_StateGate` (11 states, 20 transitions) decides Reset, Start, Stop, Abort and Clear on the
    state `MOD_StateLogic` publishes, and `MOD_StateLogic` takes only the accepted commands: 13
    states, 24 transitions. `Module.Logic.State`, which the tools read, is where it was.

- **Every ECC is laid out as the IDE draws it: states in rows, each condition between its states.**
  *Journal* (a generated program a person can read and change in the IDE).
  - Before, the generator put the states on a grid narrower than a state is drawn, and every
    transition at 0,0. The IDE draws a transition as a curve through its condition's place, so all
    101 transitions of `SKILL_Control` met in one point and the states lay on each other: unreadable.
  - Now (`modgen/ecc.py`) the states go in rows by how many transitions they are from the initial
    state, ordered by where they are reached from, sized as the IDE draws a state (its name, then
    one row per action); each condition is halfway between its two states, moved aside where several
    would land on one place. A guard without an event is written in brackets (`[Accepted]`), as the
    IDE writes it, so opening a type in the IDE no longer changes it.
  - An ECC somebody arranged in the IDE is kept as long as it is the same state machine (states and
    transitions); one that changed is laid out anew. Chosen instead of always keeping the old places
    (a new state would land on the others) and of never keeping them (the IDE arrangement of
    `IO_RouteAO` would be lost). Tried and dropped: taking transitions over several rows round the
    outside, which drew long loops across the picture.

- **The audit takes the module's identity and its IO wiring from the boot file.** *CIRP* (Q3).
  - Found by Q3's first full run: the module's name and OPC UA root are not in the AAS, and the reading
    took them from the running program; when the occupation's root or name changed in the program,
    that became the desired value, and the audit "repaired" every other block to it (2 of 411 values
    written). The linear axis's four IO addresses, which the program built from the AAS has no value
    for, were never compared (4 of 411).
  - Now, given the deployed boot file, the reading takes the name and root from it, and the audit
    compares every IO address the boot file writes. Without a boot file both are as before.

- **The reconciler compares the program block by block as well, and audits every value on request.**
  *CIRP* (Q3), *Journal*.
  - Found by Q3's pilot: reading the program only as skills (steps, bindings, parameters) misses drift
    outside that model: a value outside the skills (the OPC UA root path of a skill's blocks), wiring
    outside a flow (the abort wiring), a stray instance. A stray linked into the INIT chain beside a
    skill also made the reading follow it and lose the rest of the chain: four complete skills were
    taken for missing, "completed" and initialised again.
  - Now the INIT chain is followed into every branch; a skill the program has all of, running, that
    was not read as one is a restart, never completed; and the program is compared with the one the
    generator builds from the AAS, instance by instance and connection by connection, with their run
    states (from what is read anyway), and with `audit` value by value (one READ each).
  - The equipment's IO addresses (pins, PWM channels, Modbus registers) are not in the AAS: the spec
    rebuilt from it lacks them, 5 of the filling module's 132 values, on both targets; everything else
    round-trips. The audit compares them with the module's boot file, the record of its wiring.
  - Instead of: auditing every value in every reading (about 400 requests for five skills, a second
    more per reading over the Pi's network); or describing the IO wiring in the AAS (for the journal
    paper).

- **A skill that a cut change left half there is completed, not created again.** *CIRP* (Q3), *Journal*.
  - Found by a trial for Q3 on the tests' fake FORTE, a new skill's 165 commands cut after each: cut
    after the connections but before the blocks were started and INIT fired, the reconciler read the
    program as what the AAS describes (it looked neither at whether instances run nor at whether the
    skill was initialised); halfway through the connections, reading crashed (KeyError); later, the
    half-connected skill was refused as a changed binding; before that, it created the skill's blocks
    again, which FORTE refuses (INVALID_STATE).
  - The user's choice (of: complete it; detect and refuse; roll back and create anew): a described
    skill with an instance never started (IDLE) or its OPC UA method not opened (`UaStart.QO` FALSE)
    is compared with what the rules build of it, the program read without it, and the skill completed:
    the instances it lacks created, all its values written, the connections it lacks made, what has
    not run started, INIT fired once at its entry. An instance of another type, or one the skill does
    not have, is refused (deleting online is further work). A skill that cannot be read as one, its
    parts missing, is reported (a restart) instead of crashing the reading.
  - The reconciler waits until a created skill's INIT has opened its OPC UA method before it
    verifies, so verified includes initialised. Q1's runs (commit `4ab503c`) were made before.
  - The tests' fake FORTE refuses a name it has, reports a created instance IDLE until it is
    started, and opens a skill's method at INIT, as FORTE does; offline, every one of the 164 cuts
    now converges.

## 3 Nov 2026

- **Reading a large program back: by part, on a FORTE of the evaluation's own.** *CIRP*, *Journal*.
  - Found by the Q1 pilot: FORTE 3.3.0 sends a management answer in one frame whose length field has
    16 bits and cuts off what lies beyond 64 KiB, and its connection query takes no filter (the
    command parser reads the Source, the resource ignores it). A program of more than about 600
    connections, some 9 skills of Dispensing's size (13 instances, 63 connections each, with long
    hierarchical names), cannot be read back, so the reconciler cannot verify it. Deploying is not
    affected (one small request per element), nor is monitoring; the IDE's upload from a device
    would be.
  - Also found: the module's mode reaches every block at once, one event each, and with 20 such
    skills FORTE's event list (256) drops events at boot.
  - The user's choice: the lab's FORTE and the kit stay as they are. The evaluation runs on a FORTE
    of its own (`cell/eval/forte/build.ps1`): the lab's patches, `0008-connection-query-by-part`
    (the query answers the connections leaving a named instance or container), and event lists of
    1024 (`configurations/eval/modules-win-eval.txt`). The paper says so and why.
  - The reader asks for the whole first and, when that does not fit, part by part (each instance and
    container below the resource, a container by its own parts again); on a FORTE without the patch
    it says so instead of failing on broken XML. Instead of: always by part (more round trips for
    every program), or a longer frame (the IDE could not talk to that FORTE any more).
  - Not solved: the instance query has the same limit, at about 600 instances.

- **A value written online takes the place of the boot file's own write of it.** *CIRP*.
  - The reconciler amended the boot file by appending everything it sent, so a changed value was
    written twice at boot, the old value and then the new; the module came up right, but every change
    left a stale line, and the boot file was not the one the generator makes of the changed program.
    Found by the Q1 pilot's check V8 (the amended and the generated boot file compared as sets).
  - Now a write to a port the boot file already writes replaces that line (its request id kept); new
    instances, connections and their values are still added before the resource starts.

- **The evaluation as a study, and a scaling limit it found.** *CIRP*, *Journal*.
  - What: Q1, Q3 and Q4 of the outline as protocols with hypotheses, checks in every run and an
    analysis fixed beforehand ([cirp-evaluation.md](cirp-evaluation.md)); the reconciler times its
    phases (`stats` of `modsync.desired.reconfigure` and `read`) for Q1.
  - Found: deriving a module's capabilities (the RDF projection and its SPARQL queries) grows much
    faster than its skills: 17 s for 1 composite, 565 s for 10, over two hours for 20. The
    reconciler does not need it, so Q1 builds its AASs without it.
  - Why it matters: the skill editor derives the capabilities after every save, so a module with many
    skills would wait minutes. Instead of: deriving for the whole module, derive for the changed skill
    only, or index the projection; after the paper.

- **The kit carries the lab's FORTE (`bin/forte-aarch64`).** *CIRP* (the demonstrator's tooling).
  - A new Pi is set up with `install-pi.ps1` straight away; before, it needed a first build of
    half an hour, as install-pi sends `bin/`. The first `deploy-pi.ps1` replaces it with the
    project's build. Instead of: build-project before install-pi (one more step to get wrong).
  - The README now says how to open PowerShell, what to change in the commands, and how to tell
    a Pi without FORTE (`ssh ... ls forte`), as deploy-pi notices it only after the build.
  - A fresh unzip to a short folder built in 10 minutes (FillingModule, with the lab's modules).

- **The kit for students: one command, and a README in steps.** *CIRP* (the demonstrator's
  tooling).
  - `deploy-pi.ps1` removes a block of the resource's type (EMB_RES's `START`) that the IDE saved
    into the resource as well, keeping the `.sys` as `.sys.bak`: once on the filling project, it
    failed the IDE's check and every Deploy (`INVALID_STATE`). Instead of telling students to edit
    the XML.
  - The README leads with the steps a student runs (set up once, `deploy-pi.ps1`, what to do after
    which change) and a table from each message to what to do; the details come last.

- **Deploy from the IDE works on the Pis again: FORTE's crash on deleting running IO blocks is
  fixed (patches 0004 to 0006).** *Orchestration* (redeploying a module's program), *CIRP* (the
  demonstrator's runtime).
  - Found with gdb on the filling Pi (a debug container with the unstripped build), by deploying
    parts of the program and deleting them: `IO_DI`, `IO_DO` and `IO_AO` each crashed FORTE when
    deleted after INIT, and not before it. `~IOConfigFBController` called `deInit` and so
    `stopped()`, which sets `STATUS()`: a pure virtual of GPIOChip and PWMChip, already destroyed in
    the base destructor, so the call jumped to address 0. 0006: when destructing, only the
    controller is stopped and deleted.
  - 0004: a GPIO input is never written; its handle is reset to FALSE when its observer is
    deleted, the write failed and the controller restarted during the teardown. 0005: TCP servers
    open with `SO_REUSEADDR`, so a restarted FORTE always takes its port back.
  - Tested on .203 with the build: the filling program deployed four times as the IDE does (KILL
    and DELETE RES, then the program), over the running one; no crash, every IO block `QO` TRUE.
  - The boot file route (`deploy-pi.ps1`) stays: it builds FORTE with the types, and its program
    is the one the Pi starts with after a reboot.
  - 0007: every deployment still ended in "errors reported from the devices". The IDE queries
    each type with its declaration's hash; a generic block (`SERVER_2_2`) is FORTE's `GEN_SERVER`,
    whose entry has no hash (it builds the interface from the name), so FORTE answered
    `UNSUPPORTED_TYPE`. A type without a hash is not compared now; a real type with a wrong hash is
    still refused. Not ours: any program with generic communication blocks hits it, and any with
    IO configuration blocks hits the crash at its second deployment, on FORTE 3.3.0 as released.

- **A program made in the IDE goes onto a Pi as a boot file, not by Deploy.** *Orchestration* (how
  a module's program is replaced).
  - What: `update-pi.ps1 -Program <file.fboot>` (the IDE's Create FORTE Boot-Files) makes it
    `boot/forte.fboot`, stops FORTE, waits until port 61499 is free and starts FORTE with it; it
    checks that the program loaded (no `UNSUPPORTED_TYPE`) and that FORTE answers from the PC.
  - Why: Deploy deletes the running resource first, and FORTE 3.3 crashed doing so on the filling
    Pi whenever the program held GPIO blocks. After the crash, Docker restarted FORTE within 2 s,
    and FORTE could not take back its port: it does not set `SO_REUSEADDR`, and the IDE's
    connection still held the port in TIME_WAIT. A boot file never deletes anything, and it
    survives a reboot, which a deployment does not.
  - Instead of: Deploy after a restart into an empty FORTE (two steps, gone at the next reboot);
    patching FORTE's teardown of GPIO handles (not found yet); `modsync push`, which only takes
    modgen's modules.
  - Tested on the filling Pi (.203): the program alone, replacing the running one while a
    connection held the port, a program with a missing type, and binary and program together.
  - Then from fresh in one command, `deploy-pi.ps1 -Pi <login@address> -Project <folder>`: the
    program of the device whose `MGR_ID` is the Pi's address, made from the `.sys`
    (`make-bootfile.ps1`: the blocks mapped to its resources, their parameters and connections,
    subapplications as name prefixes), FORTE built with the project's types, the container stopped
    and deleted, the image built and a new container run. In PowerShell rather than with
    `iec61499_mgmt.sysfile`, which does the same: the kit needs no Python then. Its boot file for
    the filling module is byte-identical to the Python one; tested end to end on .203 from the kit.

- **The robot modules run in Python: modpy serves a module spec as FORTE serves a generated
  module.** *CIRP* (the demonstrator's six modules), *Journal* (a module described by the same models,
  whatever runs it), *Orchestration* (the module rules apart from IEC 61499).
  - What:
    - `module-py/` (package `modpy`, a future repository) runs a module spec in Python: the module
      rules' state machines answering as ModLib's blocks do (occupation, the PackML state manager,
      the skill state machine; after the planar controller's `statemachines.py`, MIT), and the spec's
      semantics as modgen compiles them (an item plays a command's phases; a primitive checks its
      precondition, waits 0.5 s for a held item, is done at once if its postcondition holds, drives
      its command until the postcondition or `after` with the invariant and the timeout over it, and
      ends with its stop command; flows of steps; Resetting and Stopping as FORTE's);
    - its OPC UA server lays the nodes out as FORTE does: namespace 1, `RD_n` and `SD_n` arguments,
      Byte states, UInt16 ErrorIDs, steps under Execute and Stopping, procedures, the items'
      inputs; several modules share one server as several share one FORTE;
    - the loading and unloading specs are in `cell/modules/python/`, in the format of every module
      spec; the folder keeps modgen from generating them for FORTE, as `planned/` does;
    - modreg describes them with the Describer of a FORTE module, without the rule set
      (`modreg/pymodules.py`); a test checks that every node and argument the AAS names is on the
      Python server, and the AASs follow ARSO;
    - a skill is a job of the robot program, `AwaitJob` waits for a job to end (the Stopping
      procedure, a skill's stop flow, Resetting before `Home`); the robot is simulated (`SimPoints`)
      until its interface is chosen; the vocabulary's skills 0.3: picking up realizes Receiving,
      putting down Releasing, as the gripper has the container in its custody in between.
  - Why: the user's choice: a Python process per robot's Pi with the same state machines and
    occupation as the other modules, the skills selecting programs on the KUKA, several modules on a
    Pi while there are few. Served node for node as FORTE serves a module, the agents, the DMP,
    modlink, discovery and the registration service drive and describe it as they do any module.
  - Instead of: a FORTE module with a Python equipment service between it and the robot (proposed
    on 1 Nov: two runtimes on the Pi to pass on a job number); a server with a layout of its own, as
    the planar controller's, with a Describer of its own; a `runtime:` field in the spec, while
    modgen generates only the specs at the top of `cell/modules`.

- **A robot job ends on its own JobDone, and starts with Start off.** *Orchestration*.
  - What: the contract with the robot program gains `JobDone`, the number of the job that ended
    with `Done` (cleared with it); a job's command sets `Job` with `Start` off for 200 ms, then
    `Start`; its postcondition is `Done AND JobDone = <job>`; `Error` is cleared with `Done` when
    `Start` falls, `ErrorCode` stays until the next job starts.
  - Why: a primitive's postcondition is checked before its command, and a primitive whose
    postcondition already holds is done at once (a move to where the axis is). A `Done` left from the
    job before, read before the robot has cleared it, would end the next job unstarted. The 200 ms
    give the robot a falling edge of `Start` between two jobs. `Error` has to be off before the next
    job's invariant (`NOT Error`) is checked, and why a job failed must stay readable.
  - Instead of: `Done` alone; a primitive after every job that waits for `Done` to fall (a step more
    after every job in every flow).

- **The capping module is built as the filling module, with `Crimp` as its new primitive.** *CIRP*
  (the demonstrator's line), *Orchestration* (the crimp's planning facts).
  - What:
    - `cell/modules/capping.yaml` moves out of `planned/` and its program is generated
      (`cell/control/CappingModule`), so FORTE is built with it;
    - its linear axis is filling's: a TB6600 on the same pins, a limit switch at the top, 12.5 mm/s at
      2 kHz, 0 to 60 mm, the same timeouts (Home 60 s, MoveAxis 30 s); its Pi target is written as
      filling's (`board: pi5`) for when its Pi comes;
    - the crimper is one output, `Close`, simulated (Modbus only, no pin) until a crimper is chosen;
    - `Crimp` closes it for `Duration` (0 to 5 s, 1.5 s) and opens it again (`after`), as `Dispense`
      runs the pump for a time: a primitive of the module rules, no new function block type;
    - its planning facts are stoppering's `PressStopper`'s: the head at `CrimpPosition` (40 mm) and
      kept there while it crimps; `CrimpPosition` is a new term of the vocabulary (0.8), a Position
      that characterizes Crimping, as `PressPosition` characterizes Pressing;
    - the composite `Capping` lowers the head to 40 mm, crimps and homes; Resetting and Stopping home
      the head.
  - Why: the user asked for capping like filling and stoppering, with cap crimping as a new
    primitive (the axis and the simulated crimper decided on 1 Nov). A primitive by time needs no
    sensor on the crimper; a real crimper later is an output on a pin (a valve, a relay) or a servo,
    and the skill stays.
  - Instead of: a crimper with a sensor that reports it closed (a postcondition on an input), while
    no crimper is chosen; keeping the spec planned until its Pi is there (its program now runs
    against the simulator, so the line has three generated modules).

- **A measurement series is written asynchronously, a state change synchronously.** *Journal*.
  - What: modreg gives the segments of the Measurements series (an axis's position, `Moving`,
    `Homed`) the WriteMode `Asynchronous`; the State, Skills and Log series have none, which is the
    DMP's default, `Synchronous`.
  - Why: a measurement is sampled while the equipment moves, so its points are batched and the DMP
    does not wait for InfluxDB at each one; a lost point is followed by the next. A state change or a
    skill's run happens once and the history is wrong without it, so its write waits for InfluxDB to
    acknowledge it.
  - Instead of: one mode for every series; or the mode in the DMP's configuration, away from the AAS
    that describes the series.

- **The DMP fork takes upstream's main: WriteMode, AID security and one endpoint class.** *Journal*,
  *Orchestration* (what the data path of the models runs on).
  - What: the `lab-modules` branch merges Tristan's main (Java 25, bounded AAS reads, `OpcUaEndpoint`
    in place of the data source and sink configurations, `AidSecurity`, a WriteMode on a segment's
    InfluxDB target). Kept from ours: an Operation bound to the one action its Sinks address (an ARSO
    `Skills/<skill>/Start/Start`), the wait while a connection reconnects, and `overrideHost`, now
    one of `OpcUaEndpoint`'s defaults. Dropped: our `onlyNoSecurity` check, since `AidSecurity`
    accepts nosec. Upstream now checks that an Operation's delegation is its own invoke path, so our
    test of the binding gives the Operation that path.
  - Why: the user chose to update the fork, so that the measurement series can be written
    asynchronously, and so that the fork stays close to upstream for the pull requests.
  - Instead of: the old fork, with a WriteMode in the AAS that it would not read.
  - Checked: the DMP's Maven tests of every module; pushed to the fork (`lab-modules`, 5382fcdc).

- **The journal paper is about the models; the machinery behind them goes to an orchestration paper
  (decided by the user).** *Journal*, *Orchestration*.
  - What:
    - the models' paper: the blueprints, their ontologies and constraints, and the design
      considerations for using them in real systems, with a small showcase of integration, planning
      (matching and binding) and execution;
    - the execution in the showcase is a minimal executor that follows a process AAS through the AAS
      API alone: the agents' executor through the AAS server (`DmpExecutor`), without the agents;
    - IEC 61499 and online reconfiguration, the HTN and standard planners, FOND and behaviour trees,
      the agents and the comparison of orchestrators go to
      [orchestration-paper.md](orchestration-paper.md), which takes those parts of journal-paper.md;
    - the elements of the models that serve reconfiguration and planning (`Deployment`, `RuleSet`,
      `Availability`, `Conditions`, `Completion`, the components' constraints) stay in the blueprints,
      counted and checked, and are named in one paragraph;
    - [journal-rationale.md](journal-rationale.md) gains a section on what real systems demand of
      the models (R1 to R12: derived ids, generated shells, stable interface names, the order of
      publication, the metamodel's limits, strict consumers, security, versions side by side, one
      writer, a module's own description, large data by reference, commands not repeated). Its
      technologies are now the showcase's only.
  - Why: one paper on the models, and one on what runs on them. A modelling paper that also argues
    the controllers, planners and orchestrators shows each half only briefly. An executor that knows
    nothing but the AAS API is the plainest evidence for "invoked from its AAS alone".
  - Instead of: one journal paper with both; the agents, or the behaviour tree, as the showcase's
    executor (each would bring its own argument into the paper).

- **AASPIRE's documentation site in MkDocs, in `aaspire/` (the user's request).** *Journal*.
  - What: MkDocs with the Material theme in `aaspire/`, the future main repository: a section per
    pillar (AAS, Planning, Integration, Reconfiguration, Execution; then Interfaces, Deployment,
    Lines), a page per part with its figure, how-to pages, a glossary and the repository map;
    `python -m mkdocs build --strict` passes. The `docs` extra installs it.
  - Why:
    - **MkDocs, not Sphinx with MyST.** The framework plan (section 6) recommended Sphinx; the user
      asked for MkDocs, which settles its open question 6. The pages are plain Markdown, and the Python
      reference can come later from the code (mkdocstrings).
    - **Its own folder, not `docs/`.** The working notes stay with the line and are not on the site
      (framework plan, section 6); the site is written from them for a reader who was not there and
      links to them on GitHub. `aaspire/` is where the plan puts the site.
    - **A page per part, organized by pillar,** so the site has the framework's structure and each
      repository later brings its own pages.
    - Material announces its end of life for 5 May 2027; its successor, Zensical, reads `mkdocs.yml`,
      so moving is cheap.
- **The site's figures: draw.io pages drawn by a kit in the style of `docs/figures`, shown as PNG.**
  *Journal*.
  - What: `aaspire/figures/aaspire.drawio`, one page per part and one for the framework, drawn by
    `build_figures.py` with `figlib.py` (lanes, cards, pills, tags, step numbers, the framework's icons,
    the arrows' colours by meaning) and exported by `export_png.py` (the VS Code extension's draw.io
    viewer and headless Chrome, at twice the size, cropped to the drawing). The logo is the framework's
    AASPIRE icon.
  - Why: one look across the old figures and the new; the arrows' colours mean the same on every
    figure; the PNGs the user asked for (the plan had SVG); no draw.io desktop needed. The builder adds
    pages and leaves a page edited in draw.io alone unless told to draw it again, so the `.drawio` file
    stays the source.
  - Instead of: drawing each figure by hand (seventeen figures, the style drifting), or Mermaid in the
    pages (no layout control, a look of its own).

## 2 Nov 2026

- **The journal method rebuilt around the blueprints (proposed,
  [journal-method.md](journal-method.md)).** *Journal*.
  - What:
    - a blueprint per asset class in four parts (composition, structure, relations, constraints),
      built by one procedure; a submodel's three origins (as published, with additions, ours);
    - each of J1 to J7 one relation of PPRL, stated by a named element and checked by a numbered
      constraint. The constraints, C01 to C21, have four scopes: submodel, shell, shells of one class,
      across classes;
    - a step may have several step bindings, each a validated candidate the run chooses from; the
      record of a run is IDTA 02031-2 in the product's instance AAS, with four added references (both
      proposed, D1 and D2);
    - sections in the order product, resource, process; planning and the comparison of the
      orchestrators out of this paper (proposed, D3 and D4);
    - eleven points to settle with the colleagues (A1 to A11). Among them: where the connections
      live, where their BoM puts them, which reverses our choice of the same day; and one recipe, as a
      partial order.
  - Why:
    - **The frame came after the first version.** The colleagues' introduction states the
      contributions (blueprints; an abstract ontology mapped onto APSO, APrSO and ARSO; constraints
      from the mapping) and the research questions. The first version of the file was written before
      them.
    - **Candidates serve both cases with one structure:** a step bound once before the batch
      (pharma), and a step chosen by the unit's condition (battery).
    - **The record reuses an IDTA template** instead of adding one.
  - Instead of:
    - the first version's order (concepts, references, then the three AASs);
    - a process instance AAS per unit as the control recipe: one more shell per unit, and a deviation
      would become a recipe;
    - a record template of our own.

- **The evaluation of the two cases, planned per research question
  ([journal-evaluation.md](journal-evaluation.md)).** *Journal*.
  - What:
    - E1 composition by origin, and who reads and writes which submodel, measured on the AAS server
      (RQ1);
    - E2 each joint's closing element taken away to see which stage breaks; E3 plug and produce on
      the line, timed and counted (RQ2);
    - E4 faults made by element kind, against five checkers from the metamodel to the constraints
      across classes, and the real errors of the project's history (RQ3);
    - E6 reuse across the cases, and E7 runs of the battery cell with conditions found while it runs
      (RQ4); E5 traceability; E8 authoring effort;
    - the battery case's dynamics in the blueprint's terms: validated candidates per step, checked
      again when a condition is written into the pack's instance AAS;
    - three ways to couple Plant Simulation: a bridge (the stations as OPC UA modules), a decision
      service (recommended), a replay.
  - Why:
    - "seven joints closed" is circular, since we chose the joints. Taking each closing element away
      and seeing what breaks makes it a test;
    - faults made per constraint would find only what the constraints were written for, so they are
      made per element kind;
    - the decision service gives many packs, faster than real time, which the statistics need. The
      bridge shows that the way a skill is called carries over, for a few packs.
  - Instead of: counting the joints closed and the violations found only, as the related work
    announces; the replay alone, where the models would decide nothing.

- **The design decisions, set against the alternatives
  ([journal-rationale.md](journal-rationale.md)).** *Journal*.
  - What:
    - seventeen decisions of the blueprints (M), five of the ontologies and checks (O);
    - eight things left out on purpose (X);
    - twelve technologies, each with what could replace it (T);
    - a table for the discussion;
    - a first pass, from the related work's text, at how far each reviewed work closes J1 to J7.
  - Why: the paper needs one sentence per added element in section 3, naming the alternative and who
    uses it, and the full comparison in its discussion. The normative decisions are kept apart from the
    technologies, so it is clear what another implementation must follow and what it may replace.
  - Found on the way:
    - **The call has to be described in the shell (M9).** IDTA 02027 1.0 considers only a mapping from
      asset to AAS, and leaves the other direction to later versions. FA³ST builds asset connections
      from AID and AIMC, but needs its own configuration to write or to call operations. BaSyx's
      DataBridge has route files of its own.
    - **The record template names no resource (M15).** IDTA 02031-2 Executed Processes records, per
      run and per process, the values as executed, the times, the status, the stages and the errors,
      but no resource or skill.
  - Instead of: [design-decisions.md](design-decisions.md), which serves the CIRP paper and is about
    the module in IEC 61499.

- **The Production Sequence 4.0 in aas-model, as a template with classes.** *Journal*.
  - What:
    - `templates/product/ProductionSequence4.json` beside the 2.0 template, generated into a module
      of its own (`production_sequence_4`) and described in `docs/lab-submodels/`;
    - AnnotatedRelationshipElement in `aas_pydantic`: built, read back and generated, its
      annotations as named fields;
    - `Product.assembly_sequence` and `Product.disassembly_sequence`;
    - the battery and vial examples in `aas_model.product_instances` and `process_instances`, with
      an export script that checks them, as `cell/examples/precedence/build.py` does.
  - Why:
    - **The examples are built again from the library.** BaSyx-written sequences would drift from
      any later template; with generated classes the template, the classes and the examples are
      checked together (`tests/test_lab_templates.py`, `tests/test_precedence_examples.py`).
    - **Annotations as named fields,** as a collection's children are, so a joint reads
      `joint.JointType.value`. Annotations without a field land in an `annotations` map, so a joint
      from elsewhere still reads back.
    - **Two fields on Product, one per archetype,** instead of a list of sequences: the rule "at most
      one of each" is then the model's, and the field says which one a reader wants.
    - **Next to 2.0, not in its place:** the server's products and the planner still use 2.0.
  - Left out of the 4.0 template: PlanSchema, SequenceId, Role, Subprocesses and a step's
    equipment (Resource, Skill, ExecutionMode, Bindings). The process AAS binds the equipment.
  - On the branch `production-sequence-4` of the aas-model fork, not pushed yet, so the open pull
    request to Tristan stays as it is.

- **Example models of the Production Sequence 4.0 (`cell/examples/precedence/`).** *Journal*.
  - What:
    - the battery pack with four module AASs and a cell type, the pack's Disassembly and Assembly
      sequences, and its process AAS in the simulated disassembly cell;
    - the 2 mL vial with a 4.0 Assembly sequence, its flip-off seal (bought, no sequence) and its
      process AAS on the line;
    - a build that writes AAS JSON and checks references, `After`, joints and bindings.
  - Why these choices:
    - **One sequence per archetype is told apart by the submodel id.** It is
      `…/process-plan/<AAS>/<ArcheType>`, the idShort `ProductionSequence<ArcheType>`. Two submodels
      named `ProductionSequence` in one AAS would leave readers that look up by idShort guessing.
    - **The pack and its modules are instances.** In remanufacturing each comes back with its own
      history, and a module's state of health is its own. The cell is a type, counted twelve times,
      until cells are tested one by one.
    - **The battery process AAS binds only the recipe it runs (Disassembly).** Closing the pack may
      be another cell's job, so the Assembly sequence waits for its own process AAS.
    - **The vial's cap becomes the flip-off seal**, a bought subassembly, as in the figures. It shows
      a part with an AAS and no sequence.
    - **The sequences are written with BaSyx's classes.** aas-model's template is 2.0, and its
      `aas_pydantic` has no AnnotatedRelationshipElement.
  - Instead of: hand-written JSON (no type checks); waiting for the 4.0 template in aas-model.

- **The Production Sequence as a partial order, with joints and archetypes (proposed, drawn in
  `production-sequence`).** *Journal*.
  - What, as a version 4.0 of the sequence:
    - a step kind `partial`: its steps run in any order that respects each step's `After`, a list of
      references to sibling steps;
    - edges only between siblings of one `partial` block, never across block boundaries;
    - `Order` stays, and in a `partial` block it must be a valid order (the check says so), so a
      reader that knows only `Order` still runs the plan, without the freedom;
    - `call` stays: a subassembly's sequence is a node of the graph, run by an agent of its own,
      so the four modules of a pack are taken apart at once;
    - the joints (the colleagues' `JointConnection`, an AnnotatedRelationshipElement, `first` and
      `second` the two parts as BoM entities, `JointType` and `JointStandard` as annotations) sit in
      the step that makes or breaks them, in a `Joints` collection (a collection, not a list, so
      that a joint keeps its idShort and can be referred to);
    - their `JointParamsRef` is left out: it would point at the process the step's
      `ProcessReference` already names; their `ProcessOrder` between joints becomes `After`;
    - one Production Sequence per archetype in an AAS (`ArcheType` Assembly or Disassembly); a joint
      is defined in one of them and referred to from the other, so a remanufactured pack, taken
      apart and closed again, holds each joint once.
  - Why:
    - nested sequence and parallel blocks express only series-parallel orders; the N shape (busbars
      after cover and HV plug, BMS after the HV plug only) needs a graph;
    - a product agent can call for proposals on every ready step, not only the next; real
      parallelism comes from the subassemblies, since one workpiece is at one station at a time;
    - disassembly is planned on joints in the literature (liaison and disassembly precedence
      graphs); the colleagues model it so;
    - Hierarchical Structures stays the tree of parts and HasPart: the joints only refer to it.
  - Instead of:
    - a separate precedence-graph submodel beside the sequence (a second description of the recipe,
      one more entry in aas-models.md section 7);
    - the joints in Hierarchical Structures, as the colleagues have them (it mixes the plan's facts
      into the tree);
    - AND/OR graphs for alternatives: capability matching covers "Unscrewing or Cutting", decisions
      on a step's output cover the state of health.
  - Open: inside a module's skills `partial` is not allowed (FORTE runs blocks), unless the planner
    lifts it to blocks; the BPMN editor needs a box in which free wiring is allowed; the 4.0
    template goes with the 3.0 update in aas-model (F5).
  - Described for the colleagues in [precedence-graphs.md](precedence-graphs.md).
- **The journal figures: generic first, then two use cases.** *Journal*.
  - What: each figure that is built on the example line gets three pages:
    - `<page>`, generic: ProductAAS, ModuleMAAS, CapabilityA, ParameterA, …;
    - `<page>-battery`: remanufacturing of an EV battery pack in a simulated disassembly cell;
    - `<page>-pharma`: the example line.

    The method section takes the generic page; the case study picks examples.
  - Why: every figure was pharma, which reads as if the models were made for filling. Battery
    remanufacturing stresses the models where pharma does not:
    - the product is an instance whose condition is not known until it is tested;
    - parts are taken out (the material role `output`), not only built in;
    - a subassembly (a battery module) has a plan of its own, which the pack's plan calls.
  - Instead of: pharma-only figures, or one page per figure with the generic structure above two
    example strips (too tall and dense for a paper).
- **`submodel-references` redrawn with every reference.** *Journal*.
  - What, besides capability and skill:
    - the module's interface description (actions, properties) and mapping configuration (properties
      to a time series, an Operation to an action);
    - the Variables and the Operation's input and output variables (the skill's parameters and
      results);
    - a primitive's `InterfaceReference` into the module's interface.

    The product side gets a subassembly and parts, each its own AAS found by asset id, as a module's
    components are. The process AAS sits between the two hierarchies, with its bindings to a step of
    the product and to a step of the subassembly it calls. The rows one value passes through, from
    the product's parameter to the interface action, are shaded.
  - Why: the figure has to show that the three kinds of AAS reach each other on every level, not
    only at the capability; the mapping and the interface were missing.
  - 1760 px wide, a full-page figure, instead of 960 (two columns): a tree per AAS with every link
    does not fit in two columns.
  - Open:
    - where a remanufactured product's measured condition (state of health) lives is not modelled
      yet;
    - in the pharma version the flip-off seal is a bought subassembly with no plan of its own, so
      that page has no call step.

## 1 Nov 2026

- **Candidate figures for the journal paper on the product, process and resource AASs.** *Journal*.
  - What: eleven pages of [figures/journal-figures.drawio](figures/journal-figures.drawio), listed in
    [journal-paper.md](journal-paper.md) ("Candidate figures"). There is an overview, the submodels
    with their references, the bills of material of products and line, the skill hierarchy, a map
    from parts to components through the process AAS, the capability match, ISA-88's levels, two
    BPMN figures and a matrix of which activity reads and writes which submodel.
    - Trees as the web UI shows them, as in `skill-hierarchies.drawio`; bills of material in the
      isometric style of slide 07. The product's parts (vial, stopper, cap, syringe barrel, plunger,
      cartridge) are new icons drawn in that style.
    - BPMN as a notation, not run by an engine, as journal-paper.md says of the plan and skill
      editors. Transport is dashed: the process AAS binds no transport; a shuttle is chosen at run
      time.
    - ISA-88's procedural elements against ours: a composite skill is an operation and runs on the
      unit (a module); a primitive is a phase and runs on an equipment module (a component). This
      is a proposal; [ppr-model.md](ppr-model.md) maps only the recipe levels.
    - The module's data submodel is drawn as Variables (time series, no live value in the AAS). The
      trees of `skill-hierarchies.drawio` still show the Operational Data it replaced.
  - Why: the paper argues that the three models are what plug and produce and AAS-driven
    reconfiguration need. The figures show the whole structure, and every element drawn exists in the
    example line's AASs.
  - Instead of: one figure per aspect chosen in advance; figures that show only the filling module.
- **A figure of the product's, the module's and the process's AASs as trees, from requirement to
  binding (proposed for Fig. 3).** *CIRP*.
  - What: the three AASs drawn as the BaSyx web UI shows them, as in `skill-hierarchies.drawio`.
    The product's required capability Filling is matched against the module's offered Filling (2).
    The product's FillVolume goes into the planned skill PlannedFilling (3), which is built online
    (4). The process AAS binds the recipe's step, the module and the new skill by references (5).
    The numbers are Fig. 1's steps.
    - The module has no composite for Filling yet. Its offer of 0.5 to 10 mL is the planner's
      (discovery), qualified as after a reconfiguration.
    - The leaves share one icon in the web UI, so they carry its badges (Cap, Prop, Ref); the
      submodels and collections do not, to save width.
  - Why: it shows in the standard's own terms how product, resource and process meet. Every element
    drawn exists in the AASs of the example line and the planner.
  - Instead of: the goal regression drawn (Fig. 3 now), which the text already gives in three steps.
- **The skill hierarchy is folded into Fig. 1, and the filling module gets a figure.** *CIRP*.
  - What:
    - Fig. 1's rows are the three levels (line, module, components) and its columns are the asset,
      its AAS, the tools and the running system. The pipeline's five steps run over that grid, and
      a step's line to a component's primitive shows the hierarchy.
    - The assets are small icons copied from the slides' drawings: the line on its planar table,
      the filling module, the axis, the pump and the scale.
    - The module's figure is its side view with numbered parts. The photo goes beside it, numbered
      alike.
  - Why: six figures were too many for six pages. One figure now shows where each level's AAS and
    program sit and what the pipeline changes. A reader of the evaluation sees the machine it ran on.
  - Instead of: a figure of its own for the hierarchy; a figure of the test setup as boxes.
- **The evaluation's charts share one palette with the method's colours, validated.** *CIRP*.
  - What: the usual way in blue (a restart; by hand in 4diac), ours in green (online; the skill
    editor), planned in berry `#B8336A`, with each value written at its bar's end. The downtime
    chart is drawn from the runs of 29 Oct and has the changeover of two modules.
  - Why: a colour means the same in both charts, and the three pass the dataviz validator's
    colour-vision checks over all pairs.
  - Instead of: orange or gold beside the green (too close under protanopia); purple or the AAS
    teal (too close to the blue).
- **Six figures: the pipeline across two columns, five in one column.** *CIRP*.
  - What:
    - Fig. 1, the pipeline: requirement, match, author, reconcile, bind and run, in three lanes
      (line, module AAS, program). Changing goes over the management protocol and operating over
      OPC UA, with the restart drawn as the baseline.
    - The skill hierarchy: line, module, components; a step runs a component's primitive.
    - A skill in the AAS and its blocks, in numbered pairs: the skill and its Control block, a
      parameter and its latch, a step and its instance, a value, a data connection, the order and
      the event chain.
    - A planned skill: goal regression, the lifted flow, Described and then reconciled.
    - The downtime (E2) and the effort (E1).
  - Why: one big pipeline figure, and small figures of the hierarchy, the conversion from the AAS
    to blocks and the tests, as the authors planned on 1 Nov. The sixth is the planned skill,
    because planning is a contribution (C3) that no other figure shows.
  - Instead of: the shell's architecture as the sixth (the pipeline's program box shows the shell
    and the composites); a figure of the test setup (one sentence covers it).
- **The paper's diagrams are drawn at print size in one draw.io file, exported to PDF.** *CIRP*.
  - What: [figures/cirp-figures.drawio](figures/cirp-figures.drawio), one page per diagram. The
    pipeline is 960 px wide for two columns (17.4 cm); the others are 440 px for one (8.4 cm). No
    text is below 12 px, so none prints below about 6.5 pt.
    [figures/export_pdf.py](figures/export_pdf.py) writes each page as a cropped vector PDF with
    Arial embedded, into `paper/cirp/figures/`, beside the section that includes them.
  - Why: the slide drafts are 1,100 to 2,300 px wide, so their text would print at 3 to 4 pt.
    A PDF keeps text and lines sharp at any zoom.
  - Instead of: the drafts scaled down; PNG exports; the draw.io desktop app, which is not
    installed (the VS Code extension's viewer in Chrome renders the same).
- **The inspection images are stored beside the AAS server and linked by URL.** *Journal*.
  - What: SeaweedFS runs as a container of its own in the stack that runs BaSyx. The AAS links to the
    images and holds none of them:
    - the camera's interface description gives the store's address and a URL template;
    - the product's batch record has a `File` element per image whose value is the image's URL;
    - the image's number is in the skill's results in InfluxDB.
  - Why: images are neither a description nor a live value; a `File` may name its file by URL, so
    the AAS points to them in its own terms.
  - Instead of: BaSyx's attachments (the image uploaded into a `File` element, so into the AAS
    server's database); a store with no link from the AAS.

- **On a KR C4 the robot's interface follows what is installed; digital IO is the fallback that needs
  no licence.** *Journal*.
  - What: Ethernet KRL or OPC UA if installed; else KukaVarProxy over the KLI; else the contract on
    spare channels of the IO module the gripper already needs, wired to the Pi's pins.
  - Why: every network interface KUKA offers for the KR C4 is an option package; the KLI port,
    EtherCAT and Automatic External are standard, user IO depends on the modules fitted.
  - Instead of: choosing the interface before the controllers are checked (2 Nov).

- **Python beside FORTE: a service that serves the equipment's points over Modbus (decided 1 Nov, as
  the start).** *Journal*.
  - What: a module whose equipment needs Python (cameras, a robot's protocol) gets an equipment service
    on its Pi: a Modbus TCP server that holds the equipment's points and runs a handler when an output
    changes. FORTE reaches it through the IO route it already has (`modbus[...]`), and a Pi target
    already mixes pins and a Modbus server per point ([demo-modules.md](demo-modules.md), section 2).
  - Why: no new block type, no change to `modgen` or to the runtime. The program is the same in
    simulation and on the Pi, because the simulator serves the same points.
  - Instead of: DINASORE (a second runtime that cannot run ModLib's C++ blocks); CPython embedded in
    FORTE (an interpreter in the static binary, and a Python fault stops the module's control);
    python61499's request and answer over FORTE's `CLIENT` (needs the ASN.1 encoding in Python and a
    new kind of primitive; kept for when a call needs text).

- **A KUKA robot runs one program and takes a job number (decided 1 Nov).** *Journal*.
  - What: the robot program waits for a job and runs it. The module and the program share a contract
    (`Job`, `Start` to the robot; `Ready`, `Busy`, `Done`, `Error` from it) with the usual PLC-robot
    handshake. The robot's network interface (Ethernet KRL or OPC UA, whichever the controllers have)
    is behind the equipment service, so a skill is a plain primitive: a command, the postcondition
    `Done`, the invariant `NOT Error`.
  - Why: the robots' network interfaces write variables and cannot select programs. One running
    program starts a job at once. The module's program and AAS do not change with the interface.
  - Instead of: programs selected by Automatic External on digital inputs (24 V wiring to the Pi);
    FORTE speaking the robot's protocol itself.

- **Inspection images go straight to an S3 store; IEC 61499 carries only the verdict and the image's
  number (SeaweedFS decided 1 Nov).** *Journal*.
  - What: the camera service puts each JPEG into an object store over HTTP (S3). The skill's results
    are `Passed` and `ImageNo`, logged as every result is. The camera's AAS says where its images are:
    an HTTP interface with a URL template.
  - Why: images are large and are not live values; the AAS keeps no live values (28 Oct). A store
    keeps them by name for the batch record.
  - Instead of: images base64 in MQTT messages (AP2030-UNS) or over OPC UA; images in the AAS; MinIO
    (its open-source edition was archived in April 2026), so SeaweedFS.

- **The capping module is built as the filling module, its crimper simulated.** *Journal*. The user's
  decision: the same linear axis on a stepper; a second actuator crimps and is simulated until it is
  chosen.

- **The centralized orchestrator is the colleagues'; ours keeps what both share compatible.** *Journal*.
  - What: we build the multi-agent orchestrator only. FOND-AAS and the BT controller are built by the
    colleagues. A change they need goes into what both orchestrators share (the AASs, a module run
    only through its skills over OPC UA, occupation), so it holds for both.
  - Why: the user does not work on the centralized half, and the comparison still needs both to run
    the same line without a path of their own.
  - Instead of: building the BT controller's action nodes ourselves. The shared way to run a skill
    stays in the plan (framework-plan.md, section 4, item 7); reconfiguration as a service waits until
    the colleagues need it.

## 31 Oct 2026

- **A line keeps the planar table's routing as a parameter of its own.** *Journal*.
  - What: the planar controller has a line mode: the shuttles travel only on lanes (one-way or
    two-way), turn only on turn spots and wait in an idle area (the loading queue), so the way
    between two stations is always the same. The Configurator draws it on the table for a line and
    keeps it in the line's AAS: `Parameters/PlanarRouting/Value`, the controller's JSON as it is. The
    controller reads it at startup from that value's URL (`MODE=line`, `LINE_LAYOUT`).
  - Why: the routes join the line's stations, which the line places; another line on the same table
    has other routes. The line's AAS is the configurator's own, so nothing else overwrites it.
  - Instead of: in the table's AAS (modreg writes that one again from the controller, and a table
    serves more than one line); as a collection of lanes and points in the AAS (an element per point,
    and a second format for the controller to read); free routing only (the planner's ways change
    with the traffic, which a line engineer cannot foresee).

- **The planar table's frame is a parameter, read from the PMC and never written.** *Journal*.
  - What: modreg gives the table's AAS `Parameters` (ARSO's) with `Columns`, `Rows` and
    `FlywaySize`, as the PMC is set up, from what the controller shows. Which positions of that frame
    hold a flyway stays the flyways' coordinates. The Configurator draws the table from both and
    writes neither.
  - Why: the frame is fixed and a flyway may be in any position of it; from the flyways alone a
    configurator cannot tell a table with an empty edge from a smaller table. Only Planar Motor's
    tool changes the frame, so the AAS shows it and nothing writes it back.
  - Instead of: deriving the frame from the outermost flyways (as the Configurator did); a
    measurement series (the frame is set up, not measured, and a configurator would have to read
    its latest record); the frame in the controller's configuration (the PMC already knows it).

- **One line, two orchestrators: only the orchestration changes.** *Journal*.
  - What: the demo runs the line centralized, with a FOND policy planned with PDDL from the AASs and
    run as a behaviour tree [schwoerer2026fond], and multi-agent, with product agents that follow
    their recipes and resource agents that bid for the steps. Both start from the same order and share
    everything below them:
    - the resource, product and process AASs;
    - the IEC 61499 modules with ModLib's occupation, PackML module state and skill state machines;
    - one way of running a skill (occupy, Execute, start, wait, release);
    - the DMP, registration and online reconfiguration.

    Occupation hands the line from one to the other. AP2030-UNS, the project's first stack (PackML
    stations over MQTT run by behaviour trees), is the predecessor and is archived
    ([framework-plan.md](framework-plan.md), section 1).
  - Why: plug and produce should not depend on who orchestrates; a module is made once and runs under
    either. With everything else equal, the two can be compared on one scenario, which is the journal
    paper's evaluation of orchestration.
  - Instead of: one orchestrator for the demo; two stacks for one line, as AP2030-UNS and ours were;
    each orchestrator calling the modules its own way.

- **The framework is AASPIRE, in one organization for the AP2030 project.** *CIRP*, *Journal*.
  - What: AASPIRE, AAS-based Planning, Integration, Reconfiguration and Execution. The AP2030
    organization holds every repository, ours and the colleagues'; its main repository `aaspire` is the
    framework, with the parts grouped by the pillars and the line (`aseptic-line`) as one more part.
    What exists twice in the lab (three registration services, two web UI forks, two planar
    controllers, two brokers, two time-series databases) is resolved with the colleagues
    ([framework-plan.md](framework-plan.md)).
  - Why: the framework has to hold the lab's other AAS work too (planning with PDDL, behaviour trees,
    the DMP); one letter per pillar gives each group's part its place; the papers cite one name.
  - Instead of: Skillshell (skills and IEC 61499 only, below); an organization of the framework's
    own, with AP2030 as its main repository.

- **The framework gets a name, one organization and a main repository (proposed; superseded the same
  day by AASPIRE above).** *CIRP*, *Journal*.
  - What: Skillshell as the name; one GitHub organization; 17 repositories by family (definitions,
    module, engineering, operation, deployment, the line); only the main repository has submodules;
    one documentation site; an icon per repository in the figures' colours
    ([framework-plan.md](framework-plan.md)). Waiting for the user's decisions.
  - Why: the papers need the code citable at their version; the demo needs a server and modules set
    up from repositories made for that; a vendor or another lab needs the parts without our line.
  - Instead of: six repositories split late (`repositories.md`, 6 Oct, removed 31 Oct); the lab's
    organization, which holds 19 unrelated repositories.

- **The editors' side panels hide to a tab along their edge.**
  - What: in the planner, the product structure and the details each hide to a narrow tab with their
    name (a button in the sequence's header hides or shows both); in the skill editor, so do the details.
    The choice is kept per browser, and alike in every editor on the page; the BPMN diagram fits again
    into the width it gets.
  - Why: the flow is what is worked on; the panels are needed now and then.
  - Instead of: fixed columns; only resizing them (the existing splitter, which stays).

## 30 Oct 2026

- **The BPMN editors' catalog floats over the canvas, and the drawing help sits behind an (i).** *Journal*.
  - What: the catalog opens from a Catalog button in the toolbar as a panel over the canvas's left
    edge (closed by default, kept per browser); Fit then lays the diagram out beside it. The help text
    under the canvas became a tooltip; under the canvas there is now only what keeps the drawing from
    being a flow.
  - Why: between the page's side columns, a fixed catalog column left the canvas too narrow to read
    a flow.
  - Instead of: a fixed catalog column; a "+" menu (an item cannot stay open to drag from).

- **The BPMN editors draw freely, and a validator reads the drawing back into the block-structured
  flow.** *Journal*.
  - What: steps, calls and blocks are dragged from a catalog (a product's process steps, a module's
    component skills, the gateways) onto an arrow, after a shape, or anywhere on the canvas, and wired
    by hand: from a shape's port, by moving an arrow's end, single gateways too. After each change a
    validator reads the drawing back into the flow (sequence, parallel blocks, decisions, conditional
    steps), or names what keeps it from being one: a shape not on the way from Start to End, a task with
    two ways out, a gateway that neither splits nor joins, branches that do not meet at one join of
    their kind, a loop, an exclusive split without one otherwise. Until it is a flow, the last valid
    flow is kept and Save is off. Auto layout (default) lays the drawing out as the flow's structure
    says; off, shapes stay where they are put. The skill service's checker (modplan) runs on a skill by
    itself after each change. The layout is not saved: the AAS keeps the flow, not a diagram.
  - Why: drawing by hand is what users of a BPMN modeler expect, and the block-only editing of the
    first version felt like a form. Reading the drawing back into blocks keeps what the blocks gave:
    every flow that is saved is well structured (a split has its join, no step runs twice), so FORTE's
    rules for a module and the agents' plans need nothing new; the validator only says what to fix. This
    is the classic result that well-structured BPMN is the part that maps to blocks without loss.
  - Instead of: block-only editing (sound by construction but rigid); a free graph saved as it is and
    checked on save (the flows would need a graph model in the AAS and in FORTE's rules); saving
    diagram positions in the AAS (a second, presentational model next to the flow; asked first if wanted).

- **Plans and composite skills in BPMN notation, as a view of the block-structured flow, without an
  engine.** *Journal*.
  - What: a second planner module and a second skill editor in the web UI fork (`ProcessSequenceBpmn`)
    draw the same flows in BPMN: a step is a service task, a call a call activity, a parallel block a
    pair of AND gateways, a decision or conditional steps a pair of XOR gateways (otherwise is the
    default flow). Editing is by blocks only (insert on a sequence flow or after a step), so every
    diagram is a well-structured BPMN process. Both read and write the existing AAS data; a step links
    to the skill it runs, so a plan, a module's skill and its building blocks open in one notation. A
    flow exports as a BPMN 2.0 file with its diagram, marked not executable. The classic editors stay;
    a setting chooses which skill editor shows.
  - Why: BPMN is the notation the related work and industry use (koecher2022bpmn, Lindorfer and
    Froschauer, Stolze et al.), but as a free graph it allows unpaired gateways (a flow that hangs, a
    step that runs twice) and knows nothing of equipment, stop propagation or parameter ranges. Drawing
    our blocks in its symbols gives the familiar notation and the exchange file, keeps the flows sound
    by construction and keeps the checks; FORTE runs a skill and the agents a plan, so an engine would
    only add a central server.
  - Instead of: bpmn-js as a free modeler with rules and a check on save (its licence also requires its
    logo); executing BPMN in Camunda as koecher2022bpmn does; storing BPMN XML in the AAS.

- **The kit installs FORTE on a Pi over SSH, without the internet.** *Journal* (a module needs no
  cloud to be set up).
  - What: the kit carries the container files and the arm64 base images (alpine, busybox, saved with
    `docker save`); `install-pi.ps1` copies them with FORTE and `install.sh` to the Pi with scp and runs
    the installer over ssh. The installer downloads only what is not next to it, and checks the
    clock only before a download.
  - Why: lab and shop-floor networks often have no internet, and a Pi without a clock chip starts
    with a wrong date, which only matters for certificates.
  - Instead of: the installer fetching the container files from GitHub and the images from Docker
    Hub every time. Docker itself is still installed from the internet when missing.

- **A FORTE kit for others' block types: the lab's runtime plus theirs, from any 4diac project.**
  *Journal* (the runtime can be extended by people outside the project).
  - What: `runtime/make-kit.ps1` zips the build scripts, FBE configurations, FORTE patches and the
    lab's exported modules; `build-project.ps1` exports any 4diac IDE project next to them and builds
    FORTE for the Pi (or the PC). Without modgen's type manifest, a type whose header path FORTE has
    already (a copied standard block) is not compiled again.
  - Why: a FORTE runs only the types compiled into it, so one binary per Pi has to hold the lab's
    modules and the newcomer's blocks; with the lab's exports in the kit, the newcomer's FORTE still
    runs the module programs and can go on a lab Pi.
  - Instead of: sending the whole repository (modgen, Python, the module specs), or a FORTE with
    only the newcomer's types, which would break the lab module on the same Pi.

- **Custody: a product and the resource that carries it are bound by capability constraints, not by
  a rule of the agents.** *Journal* (and the slides).
  - What: vocabulary 0.7. A resource that carries or holds a container has it in its custody from
    Receiving to Releasing. Holding (the resource has this container), Occupancy (how many it has) and
    Capacity (how many it can have) are states; HeldBy is the container's side of Holding. The
    constraints: Transporting needs `Holding = true`; Receiving needs `Occupancy < Capacity` and gives
    `Holding = true`; Releasing needs `Holding = true` and gives `Holding = false`. A shuttle's AAS
    offers Receiving (Capacity 1) and Releasing next to Transporting; no skill realizes them, they
    change only the custody, so the agent carries them out itself. The product agent sends its state
    (HeldBy) with every call and sends every call to every resource agent: for its first transport it
    asks for Receiving (the free shuttles propose, the modules refuse), then for Transporting (only the
    shuttle that holds it proposes), and at the end for Releasing. A resource agent checks the Pre
    constraints of its offered capabilities against the product's state and its own custody; a
    constraint about a state nobody gives is not checked. A refusal only because of the resource's own
    state that changes (Occupancy: a full shuttle) says Busy, so the product agent asks again; the rest
    are for good. Custody is a lease (an hour), renewed by every call of the product's agent, so a
    product agent that is gone does not hold a shuttle for ever.
  - Why: the binding is the same kind of fact as a vial's content volume: a state that a capability
    needs and changes. In the AAS it is what the IDTA Capability Description already has (Pre and Post
    as BasicConstraints), so a resource's AAS says who may carry a product, and nothing in the agents
    is about shuttles: an AGV, a gripper or a tray with room for twenty works the same. It answers the
    question of the holonic literature (PROSA's order holon bound to its workpiece; the intelligent
    product bound to its pallet, McFarlane et al. 2003) with the commitment rules of Jennings (1993):
    how it starts (Receiving), how it ends (Releasing), when it lapses (the lease).
  - Instead of: the product agent remembering its carrier and asking only it, and the shuttle refusing
    others until a release message (built earlier the same day: two rules in the agents' code, one of
    them about shuttles); one agent for the whole table (transport out of the bidding); custody as a
    message protocol of its own. Loading as the step that starts the custody waits for the loading
    module's AAS (the Kuka has none yet): when it exists, Loading is a step at the loading station and
    Receiving happens before the shuttle drives there.
  - Open: a handover between two carriers (a robot moving the vial from one shuttle to another) is
    Releasing by one and Receiving by the other, with the robot's step between; not tried. `Holding`
    from a product's side and from a resource's side is one fact seen twice (HeldBy, Holding), which
    the vocabulary says in words, not in a rule.

- **Transport: each shuttle bids for Transporting like a module; the product is carried to the
  module's station before the module's proposal is accepted.** *Journal* (and the slides).
  - What: a shuttle's AAS offers Transporting (TargetX, TargetY, TargetRz over the table's extent;
    vocabulary 0.6), realized by MoveToPosition, whose parameters now mean those properties
    (`modreg.planar`). A module's proposal carries its station: its transfer point in the table's
    frame, computed by the manager from the module's, the line's and the table's coordinates. The
    product agent chooses the module, calls for Transporting to that station (every resource the first
    time, then only the shuttle carrying the product), and accepts the module's proposal once the
    shuttle reports the product there. The carrying shuttle bids for no other product until the
    product agent releases it at the end. A proposal holds its module for up to 300 s; a late proposal
    is rejected at once so it holds nothing.
  - Why: the user's decision (30 Oct: the shuttles bid like modules). It keeps one mechanism for every
    resource, and the transport is in the same conversation record as the steps. Accepting only once
    the product is there makes VDI/VDE 2193-2's binding proposal the booking, without a message type of
    our own.
  - Instead of: the product agent commanding the table directly (transport outside the bidding); one
    agent for the whole table (it would have to decide which xbot, which is the controller's or the
    shuttle's own business); accepting the module first and moving afterwards (the module would start
    with no vial under the needle); a separate "start" message after booking (not in VDI/VDE 2193).

- **A product agent's step can need a reconfiguration: the syringe asks for BottomUpFilling, the
  filling module's agent creates the skill online and runs it.** *Journal* (and the CIRP demo).
  - What: a resource agent offers a capability of the required meaning or a narrower one (an exact
    one first, then a built skill first); on acceptance of an offer whose skill is only described,
    the agent rebuilds the module (`execute.rebuild`: modsync creates the skill in the running FORTE
    program, records it with its interface, derives the capabilities anew) and runs it over OPC UA.
    `test_agents_live.py`: the syringe's Filling step goes to BottomUpFilling, created online, run with
    1 mL, the weight back. modlink skips a capability offered after a reconfiguration (no interface yet).
  - Why: this is the step from "a module that can be changed" to "a line that changes a module because
    a product asks for it", the journal paper's claim; a narrower capability meets a broader request
    (a bottom-up filler can fill a vial) but never the reverse.
  - Instead of: matching capabilities by identical meaning only (a module that only fills bottom-up
    would refuse a vial); a planned-only reconfiguration in the agent (the agent now does the real one
    on FORTE).

- **A skill can be written for a narrower capability than its steps contribute: BottomUpFilling, a
  Filling (vocabulary 0.6).** *CIRP* and *Journal*.
  - What: `lab:BottomUpFilling rdfs:subClassOf lab:Filling`; a composite skill names the capability it
    was written for (`capability:` in the spec, a supplemental semantic id of the skill element in the
    lab's semantics, `pprl:writtenFor` in the projection); the derivation offers that capability
    instead of the one its steps contribute, characterized by the broader class's properties; what
    holds of Filling (its constraints, the machine's stated facts: the containers it takes) holds of
    it. `discover` does not plan narrower capabilities.
  - Why: the user's call (30 Oct): a new or changed skill needs a capability of its own, or a product
    cannot ask for it and the offer of "the same Filling, after a reconfiguration" is no reason to
    reconfigure. What makes bottom-up filling different (the needle rising with the liquid) is how
    the skill moves, which no constraint on the states before and after states, so it is declared by
    whoever writes or plans the skill, not inferred.
  - Instead of: a capability per skill name (`Filling_BottomUpFilling`: the product cannot name it);
    inferring it from the flow's shape (a Dispense beside a rising axis: clever, and wrong for an axis
    that moves down); planning narrower capabilities from their constraints (they are Filling's, so
    any Dispense would be "bottom-up").
  - Found on the way: `described_skill` named the components after "Module", so the steps of every
    skill described through it referred to components that do not exist (`ModuleLinearAxisAAS`) and
    the derivation saw no steps; it now takes the module's name from its components' AASs.

- **Orders go to an order agent, which starts a product agent per unit; a module is reserved from its
  proposal until the decision.** *Journal*.
  - What: an `order` message (Product, Quantity) to `orders@<domain>`, or `POST /orders` on the
    manager, starts one product agent per unit (`<product>-<n>`); the orderer gets `orderConfirm`
    with the agents' JIDs, then from each product agent `informConfirm` with its steps (who did each,
    the results) or `failure`, all in the order's conversation. A resource agent refuses a call with
    `Busy` while it carries out a step or while one of its proposals waits for a decision; a product
    agent that hears only busy refusals asks again a second later.
  - Why: an agent per product is how product-driven control is described (the product carries its
    own process through the line), and it lets three vials share four modules without a central
    schedule. A binding proposal (VDI/VDE 2193-2) must reserve the module, or two products that both
    accept the same module's proposals collide. Ordering is not in VDI/VDE 2193-2, so it is a small
    protocol of the lab's own in the same frame.
  - Instead of: one product agent per order walking the units one after another (no sharing of the
    line); the manager as a plain REST service only (orders could not come from another agent);
    refusing a busy module's call like any other (the product would end with "nobody").

- **The line's agents: SPADE on the server, VDI/VDE 2193 over XMPP, an agent per module started by a
  manager that watches the AAS server.** *Journal*.
  - What: `line-agents` (`lineagents`): a resource agent per module bids for one step at a time with
    the module's offer (the offered capability of the required meaning whose properties cover the
    product's values, the realizing skill, built or only described, the skill's arguments mapped by
    meaning); on acceptance it creates a described skill first (modsync, recorded back on the AAS
    server) and runs the skill over the module's OPC UA with modlink; a product agent per order walks
    the Production Sequence; the manager starts, updates and stops resource agents to match the
    module AASs on the AAS server. Messages are VDI/VDE 2193-1 frames as JSON in XMPP bodies;
    Prosody in the lab stack.
  - Why: the agent is the module's active part and the module stays an IEC 61499 program and an AAS;
    the server location with a direct OPC UA client is IEEE 2660.1's recommended practice when the
    device should not host agents, and it keeps the skills' state as it changes; the AAS registration
    is the one place a module becomes known, so the agents follow it rather than a list of their own.
    VDI/VDE 2193 is the I4.0 standard the AAS community implements (over MQTT and Kafka so far).
  - Instead of: SMIA (closest system, but its own FIPA-ACL dialect, an OWL capability model instead of
    IDTA 02020, OPC UA without method calls, copyleft and pinned to an older SPADE); agents on the Pis;
    executing through the AAS and the DMP (kept as a second executor: slower, the state polled);
    SPADE's own XMPP server for deployment (it lost registrations from other processes).

## 29 Oct 2026

- **Modules are discovered: FORTE announces itself (LDS-ME), the service fetches the module's
  manifest and registers it.** *CIRP* (the plug step), *Journal*.
  - What: FORTE is built with `FORTE_COM_OPC_UA_MULTICAST` (open62541 with mdnsd, our own recipe), so
    its OPC UA server announces itself by mDNS as OPC UA Part 12's multicast discovery has it.
    `modreg serve --discover` browses for `_opcua-tcp._tcp`, connects to each server, finds the modules
    by the module rules' layout (Occupation and Module), fetches the module's manifest (the pydantic
    dumps of its AAS and its components', `{"module", "profiles"}`) from
    `http://<host>:8088/manifest.json`, and registers it as a profile sent to it is. The planar
    controller is recognised by its namespace and described from what it shows.
  - Why: plug and produce means the integrator does not have to tell the service a module is there;
    the module brings what describes it. The standard OPC UA discovery is what any client of the line
    already understands, and it comes from the runtime itself, not from a helper on the device.
  - Instead of: an Avahi service file on each Pi (no rebuild, but a second thing to keep in step with
    FORTE's port); a scan of address ranges; the manifest inside the OPC UA address space (FORTE would
    need blocks to serve it); an AASX package (the service takes the profiles already). The manifest
    sits beside FORTE over HTTP because FORTE's mDNS record carries only the server's name, path and
    capabilities.
  - Found on the way: the FBE leaves mDNS out because GitHub's release archive of open62541 lacks the
    mdnsd submodule, and its unpack helper fails on Windows (a rename onto an empty folder); mdnsd also
    needs `inet_pton`, which the XP-compatible Windows target does not declare.

- **The evaluation's scenario is a changeover to the prefilled syringe, with filling from the bottom.**
  *CIRP*.
  - What: one product changeover, timed as one: the filling module gets a new composite skill that
    fills from the bottom (NeedleDeep → Dispense ∥ NeedleRise → Home → Weigh: the needle starts low in
    the barrel and rises while the pump doses), with the syringe's values, and the stoppering module a
    new stopper depth. Online against a restart of both modules; the new skill written in the skill
    editor, and planned if a model of the liquid level fits.
  - Why: the change has to be one no parameter can make, and one a product asks for. Filling from the
    bottom is what a tall barrel or a foaming liquid needs; it runs two components at once, which is
    what the parallel block of the module rules is for (one join block, where a generated type has 2ⁿ
    states). The filling module is the one whose primitives span three components and whose Pi moves
    an axis, so the run is visible at the bench.
  - Instead of: DoubleDose or a planned 15 mL (two equal doses next to each other: what a larger
    range would give); the net fill weight (Tare moved into the skill; not chosen by the authors);
    stoppering, capping or inspection (one sensible sequence, or no program and hardware yet).
- **Dosing's integration constraint: the needle in the container, not the needle still.** *CIRP*,
  *Journal*.
  - What: on the filling module Dispense needs `Position >= FillPosition` and keeps it while it runs
    (an invariant that is a comparison). The checker accepts a parallel branch that moves the
    variable as long as the comparison holds at each state the branch passes through (a move goes
    straight, so its ends are enough); the planner and the PDDL and HDDL exports reach a comparison's
    bound when it does not hold. Cases T13 and T14.
  - Why: "unchanged" said more than the machine needs: it ruled out filling from the bottom, which
    is sound as long as the needle stays in the container. The constraint states what is physically
    required, so the checker tells a skill that may move the needle while dosing from one that takes
    it out of the vial.
  - Instead of: keeping "unchanged" and a second Dosing capability for filling from the bottom; or
    leaving the check to the engineer.
- **The replanning example needs a new step, not a new value: TaredDispensing.** *Journal*, *CIRP*.
  - What: a step that needs the dose's own weight checked is not covered by Dispensing (it weighs the
    vial and the liquid together); the composite made of the filling module's primitives puts Tare in
    front of Dispensing's steps, and its derived capability covers the step after a reconfiguration.
    The agents call for proposals one step at a time (Filling, then the transport), and the table's
    agent is a resource agent like the modules'.
  - Why: DoubleDose is, on our module, a parameter change (one dose within range twice is a volume);
    an example of replanning should change the structure of a skill. The table is a resource in the
    model, so its agent is one too.
  - Instead of: DoubleDose for 12 mL; a call for the whole recipe at once; a separate transport agent.

- **The figures' shapes as a draw.io shape pack.** *Journal* (figures, and anyone drawing the lab).
  - What: six draw.io libraries in `docs/figures/library` (the line, parts, computers and software, AAS,
    planes and sketches, flat), 125 shapes taken by cell id from the pages they were drawn on, each a
    group with its shadow; the AAS shell as an isometric solid, standing or lying flat; a catalogue page
    per library; registered for the VS Code draw.io extension in `.vscode/settings.json`.
  - Why: new figures then reuse the same drawn things, at the same angles, instead of copying cells
    out of old pages.
  - Instead of: copying from the figure files by hand.

- **In an isometric figure the AAS shell is an isometric solid.** *Journal* (figures).
  - What: the shell's outline, with the logo's rounded corners, extruded and drawn on the figure's own
    30° axes, shaded like the stations, its name on the band; it stands on the AAS plane, and the lines
    from the tools end on its top.
  - Why: a flat logo in an isometric drawing reads as pasted on; the solid belongs to the scene.
  - Instead of: the flat shell, kept for flat diagrams.

- **An agent is drawn as the active part of an AAS, in our parts.** *Journal* (agents, future work).
  - What: a module's agent is a SPADE agent; its messenger is XMPP, carrying VDI/VDE 2193 messages; an interaction manager with the
    service provider's state machine, bidding (capability, availability, time), reconfiguration (the
    planner composes, modsync builds online) and execution (modlink over OPC UA, or an Operation of the
    AAS over HTTP that the DMP turns into the OPC UA call); its passive part is the module's AAS. A
    product agent is the same build as the service requester, writing the process AAS.
  - Why: it places the tools that exist (planner, modsync, modlink, DMP) inside the agent, so the
    agents are a role around them, not a new system.
  - Instead of: agents as one box beside the tools.

- **The talk shows modsync as the commands it sends, and agents in the I4.0 language.** *Journal*
  (how the method is shown to people who did not build it).
  - What: the slide from the AAS to function blocks has a console beside the network: per step the
    operations of the management API that build it (create_fb, connect, write, start) and, last, those
    that verify it (query_fbs, query_connections, query_type, read) before the skill is recorded as
    Built. The agents are shown on the line, the vial's product agent calling for proposals and the
    modules' agents proposing or refusing, as VDI/VDE 2193 messages; replanning is one slide: match,
    the missing effect (12 mL), a composite from the module's primitives, matched again.
  - Why: the network alone shows the result, not that it is built step by step online and read back;
    the commands are the method's evidence. Interaction protocols make the agents' part concrete
    without claiming more than is planned.
  - Instead of: a pipeline of six boxes for modsync; agents as boxes beside a picture; two slides
    for the change from recipe to running program.

- **The DMP rides out a module that restarts: two more changes on its `lab-modules` branch.**
  *Journal* (what an AAS-driven connection needs from its runtime when modules come and go).
  - What: a route's OPC UA subscription is deleted without waiting for the server's answer, and a
    method call or a signature read that finds the shared connection reconnecting waits for it (a
    call a third of its timeout, a read 10 s) instead of failing; a read that meets a stale session
    is made once more.
  - Why: a module that restarts (FORTE, a Pi rebooting) is normal on a reconfigurable line. Before,
    the first call after a restart failed for about 13 s (`Device transport failed`, HTTP 424 at the
    AAS server), and removing the routes of a module that had gone away waited out a request timeout
    per consumer: the DMP took 71 to 213 s to converge after a republish, 47 s with the delete sent
    and not waited for. A server that is gone drops the subscription with its session anyway.
  - Instead of: retrying the call itself (a method is not idempotent: Dispensing must not start
    twice), so only what has not been sent waits, and only the read is made again.
  - Checked: the DMP's OPC UA tests (37), and `test_dmp_live.py` three runs in a row against the
    same DMP, where the second run had failed before. Left as found: a mapping blocked on a submodel
    published after its AIMC is not resolved when the submodel arrives (publishing order avoids it).

- **The planner's bindings make the process AAS: the registration service writes it after a save.**
  *Journal, CIRP* (ISA-88's master recipe, apart from the general recipe).
  - What: `POST /process/<product>` (`modreg/process.py`) reads the product's recipe as the planner
    saved it, with a module, a skill and input bindings per step, finds the line that holds every
    bound module (its Hierarchical Structures), and writes the process AAS: Process Information,
    a step binding per bound step (the recipe's step, the module, the skill, each input's source or
    constant and the Operation variable it is handed to), and the plan check's result as its
    Validation. The planner asks for it after saving a recipe with a bound step. The plan check
    moved into `modreg` (`modreg.plancheck`) for it.
  - Why the service and not the planner: the process AAS is built with aas-model's classes and
    checked by the same plan check as the reference processes, so the hand-written ones and the
    planner's are one structure; the planner has no notion of a line, and the service finds it.
    Instead of: the planner writing the process AAS's JSON itself (a second copy of the structure in
    TypeScript), or asking the engineer for the line.
  - First step: the bindings stay in the product's recipe as well, since the planner and the HMI
    read them there. Taking them out is the next step, once every reader reads the process AAS.

- **The skill editor asks the checker and the planner.** *Journal* (the engineer's side of planning).
  - What: in the skill editor, Check sends the skill as it is on screen (not saved) to `modreg
    serve`'s `/check` and shows each finding at its step, with the skills that would fix it; a
    changed flow clears the result. In the skills overview, Plan a skill takes a capability the
    module offers, its range properties as the values and what it should report as results, shows
    the planner's steps, and on "Plan and describe" has the skill described on the AAS server and
    opens it in the editor; `modsync reconfigure` builds it.
  - Why the check before saving: a finding is cheapest while the flow is being drawn; saving
    first would put a skill on the server the module cannot run. Instead of: checking on save only.
  - The values come from the Capability Description the editor already reads (its ranges), so the
    dialog asks for no names: what a module can be planned for is what it offers.

- **Every call of a module's command is logged, as a time series in `Variables/Log`.** *Journal.*
  - What: per command an Operation invokes (`Dispensing_Start`, `Occupy`, ...), a series
    `Log/<action>` (aas-model's `operation_log`): how the call ended (`Outcome`), how long it took
    (`DurationMs`), and the Operation itself, referenced, so its variables are fields (the session,
    the parameters, Accepted and ErrorID). The DMP writes the row from the bridge mapping's response
    half, also for a call that failed (then the log row only).
  - Why: who called which skill with what, and what the module answered, was in no record; the
    module's own state series show what it did, not who asked. With the session in the row, a
    module's history can be read per client (an agent, the HMI, the planner).
  - A reference, not copies of the variables: the record follows the Operation when its parameters
    change, as aas-model's stations do. Instead of: one log per skill with a command field (a
    record refers to one Operation), or a log in FORTE (it has no clock or storage to keep it in).

## 28 Oct 2026

- **The lab's AAS stack runs the DMP beside BaSyx, with InfluxDB behind the Variables and MQTT
  for BaSyx's submodel events.** *Journal* (the architecture: an AAS that is the configuration of
  its own connection). Asked for by the user.
  - What: `deploy/aas/compose.yaml` (`python deploy/aas.py up`): the BaSyx AAS environment with
    operation delegation and its MQTT feature, registries, discovery, the web UI, Mosquitto,
    InfluxDB 2 (org and bucket `ap2030`, as aas-model's segments name them) and the DMP built from
    the `aas-camel-dmp` submodule, named `dmp` because the delegation URLs name `http://dmp:8080`.
  - Why MQTT for the events, not Kafka: the DMP takes either; Mosquitto is one small container and
    the lab's stations speak MQTT already. Kafka needs a broker and its coordination for one
    consumer. The modules' values do not go through the broker: the DMP observes them over OPC UA
    and writes them to InfluxDB.
  - The secrets (InfluxDB's password and token) are made up on the first `up` and kept in
    `deploy/aas/.env`, which is not committed: the repository is public.
  - The DMP did not run our modules out of the box. Four changes, on a branch of the DMP fork
    (`lab-modules`), each with a test:
    - it refused aas-model's AIDs: since 24 Oct aas-model has every interface select its `nosec_sc`
      (AID 1.1 requires a selection), and the DMP (23 Oct) refused any selection, since it holds no
      credentials. A `nosec` scheme needs none: a selection of `nosec` schemes only is accepted now.
      Instead of: leaving the selection out of our AID (no longer AID, and aas-model adds it back);
    - it bound an Operation to the action named like the Operation's parent (aas-model's
      `Skills/<skill>/operation` and action `<skill>`). ARSO has `Skills/<skill>/<command>/<command>`
      and an action per command of every skill (`Dispensing_Start`), which cannot all be named
      `Start`. Now, where the names differ, the one action all the mapping's Sinks address: the
      AIMC states the binding. Instead of: changing ARSO's skill structure for a naming rule;
    - it could not call a method whose owning object is named by a browse path (it read the
      signature only with a NodeId owner, and resolved a missing one at the call). FORTE numbers its
      nodes anew at every start, so we name them by browse path; aas-model's stations have fixed
      NodeIds, so this had not come up;
    - it connected to the host a server names in its endpoints (FORTE: the computer's hostname,
      `MartinPC`, the Pi's name), which does not resolve in the DMP's container. It now reaches a
      server at the AID's base (Camel Milo's `overrideHost`), as the AID says.
  - Found, not changed (the first is fixed on 29 Oct, see there): removing or replacing a route
    whose OPC UA server has gone away waits out a shutdown timeout per route, and leaves the mapping
    stale and the DMP degraded until it is restarted; and a mapping whose referenced submodel is published after the AIMC stays blocked
    (not resolved when the submodel arrives). So the components' AASs are published before the
    module's (`modreg.service.mapped_last`), and within an AAS its AIMC after its other submodels
    (`AasServer.publish`); a module keeps its OPC UA address across restarts.
  - Checked end to end (`cell/tests/test_dmp_live.py`): the filling module simulated on FORTE;
    Occupy, Reset, Start and Dispensing invoked at the AAS environment, answered by the module
    through the DMP (and a refusal for another session), and the rows of the module's state and of
    the Dispensing run, with its volume and weight, in InfluxDB. And a shuttle of the planar table
    (the planar controller, a Python OPC UA server, which names a method's arguments by meaning:
    the describer says how a server names them): the table to Execute, the shuttle occupied and
    moved, its run, its pose and the call log in InfluxDB.

- **A module's AAS is what the DMP (aas-camel-dmp) runs: a skill's Operation calls the module's
  OPC UA method through it, and its values reach InfluxDB through it.** *Journal.* Asked for by
  the user.
  - What changed in the generated AAS:
    - each Operation's delegation URL is filled in: the DMP's origin and the path where the AAS API
      invokes that Operation (`/submodels/{base64url(id)}/submodel-elements/{idShortPath}/invoke`),
      as aas-model now writes it. Before, the `{operation_path}` placeholder was left in it;
    - an action's arguments are named as FORTE names them: `RD_1, RD_2, …` in, `SD_1, SD_2` out.
      FORTE's OPC UA server names a method's arguments after the data ports of the SERVER block
      that serves it, and the DMP calls a method with its arguments by name. What each argument is
      (Session, Volume; Accepted, ErrorID) is its title;
    - a mapping that invokes an action writes into the action's `input`, and has a response half:
      the method's answer (`SD_1, SD_2`) becomes the Operation's Accepted and ErrorID. A skill's
      results are marked Optional (aas-model's qualifier): the method answers at once, the results
      come when the skill is done, and the DMP requires every output not marked so;
    - a Boolean (the occupation) goes into its decimal field as 0 or 1: the DMP writes a field as
      its type and refuses a Boolean for a float;
    - aas_pydantic's `temp_id_short_attribute_*` Properties (it keeps a list item's idShort in them
      to read the model back) are stripped before publishing, as aas-model does. The DMP refuses a
      mapping with elements it does not know, and every mapping had them.
  - Why the AID names FORTE's argument names: the AID describes the device as it is, and the DMP
    checks it against the server. Instead of: renaming FORTE's arguments (its server takes them
    from the block's port names) or a mapping by position (the DMP matches by name on purpose,
    so that a reordered method cannot be called with the wrong values).
  - Nothing else needed: the DMP already resolves browse paths (`uav_browsePath`, and
    `uav_componentOf` as one), which FORTE's changing numeric node ids require.

- **Every block of a generated program explains itself in plain words, in 4diac and in the docs.**
  *Journal.* Asked for by the user.
  - What: the generator (`modgen/explain.py`) writes a type comment on every type ("what it does,
    for whom", then "Technical:" the detail) and an instance comment on every block of the
    application and of every composite: where its calls come from and where its data goes (a
    parameter "from Dispensing's Volume", a result "is Dispensing's result"). The same is written
    out once by hand in [filling-program.md](filling-program.md), with each OPC UA call followed to
    the pins, and [building-skills.md](building-skills.md) says how to add a skill, a primitive or
    equipment.
  - Why: an engineer opening the program in the 4diac IDE sees dozens of blocks and their wires; without
    the comments it takes reading the generator to know what a channel carries or why a block is
    there. Written by the generator, the comments follow every regeneration and never go stale.
  - Comments are not part of a type's hash (checked with the 4diac IDE 3.3 export), so they need
    no FORTE rebuild and a running module keeps matching its program.
  - Instead of: a separate manual only (goes stale and is not where the engineer looks), or
    comments written in the IDE by hand (lost on the next `modgen`).
  - The guide states the rule the architecture gives: a module level skill is blocks of types FORTE
    has and is added while the module runs; a primitive or equipment is new types and needs a new
    FORTE. That is the split between reconfiguring a module and changing it.

- **A module keeps no live value in its AAS: its values are time series in the database, and the
  AAS says where.** *Journal.* Decided by the user.
  - Why: the values change fast (a position while the axis moves, a weight while it fills). Pushing
    each change into the AAS server loads it with writes nobody reads there, and keeps no history.
    A time series database keeps every row; a reader asks it for the latest or for a span.
  - The Variables of a module hold aas-model's time series SMCs (IDTA 02008 as SMCs): `State/Module`
    (PackML state, occupation), `State/<Skill>` (one skill's run: its state, error, parameters and
    results and its steps'), `State/Procedures`, `Measurements/<Item>` (an item of equipment's
    inputs). A series groups what changes together, as aas-model asks, not one value each. Each field
    is a decimal with its meaning as supplemental id; each series has a segment naming its InfluxDB
    measurement (`state_dispensing`, `measurements_linearaxis`), tagged with the module's AAS.
  - Instead of: a Property per value that the mapping keeps current (45 for the filling module), and
    instead of aas-model's stations' both (a Property and a series).
  - One mapping per series writes a row: each interface property is the field its SourceId names.
    modlink finds what a skill's state shows through that (the field's meaning); a capability's
    `SameAs` and a coordinate's `ZSource` refer to a record field. `Log` (the calls of skills) is
    not written yet.
- **A shuttle is its xbot: no AAS of the xbot apart from the shuttle's.** *Journal.* The shuttle's
  `MoveToPosition` is its own skill. Until now the xbot was a component (`PlanarShuttle<N>XbotAAS`)
  because it is the shuttle spec's equipment that the skill moves; but there is no part to tell
  apart from the shuttle. Decided by the user. The table's PMC was never a component (no skills).
- **Three products and their process AASs, written out in Python.** *Journal.*
  - A 2 mL vial, a prefilled syringe of 1 mL and a cartridge of 3 mL (`cell/examples/products`),
    with the values of the planner's pharma example. One process AAS each on the filling line
    (`cell/examples/processes`).
  - **Long files, every element constructed with its class,** instead of helpers that build
    elements. They are the reference a reader looks up ("this is how this part looks"), so nothing
    is hidden. Decided by the user.
  - **The recipe names no equipment; the process AAS holds the bindings** (the model of 26 Oct,
    `ppr-model.md`). The planner still writes bindings into the product's recipe (F6); `plan_check`
    reads both (`check_process`, `check`).
  - **The plan check guards the reference:** a process AAS whose Validation says something else than
    the check finds is refused by `example_line.py`.
  - **The syringe accepts a fill error of 0.05 mL,** where the planner's example asks 0.01 mL: the
    line's filling module fills to 0.05 mL. A product asks for its fill error as a range (0 to the
    most it accepts); the check now compares an offered value against a required range.
- **A capability property may list the values a module takes** (IDTA 02020's `SubmodelElementList`
  property). *Journal.*
  - Filling, stoppering and inspection take vials, syringes and cartridges (`ContainerType`); capping
    takes vials. The spec says `values: [vial, syringe, cartridge]`.
  - Why: one capability with the set of containers it takes, instead of one capability per container
    as the planner's example has it (Filling_vial, Filling_syringe, ...), which multiplies offers and
    skills that are the same.
  - Read by the plan check, modlink and `modreg offer`. The planner's matching is not checked yet.
- **The table's three shuttles are part of the example line**, so the line's resources are complete.
  Loading and unloading are still named only (each a Kuka robot and a Pi; no spec yet).
- **The reference models: the library in aas-model, the instances here.** *Journal.*
  - aas-model (branch `lab-ppr-models`) holds the lab's own submodel templates (ARSO's Skills,
    Parameters, Control Configuration; the product's Process Parameters and Production Sequence; the
    process AAS's Process Information, Bindings, Validation), the classes generated from them
    (`scripts/lab_generate.py`), and the types `Module`, `Component`, `ProductionSystem`, `Product`,
    `Process`.
  - This repository builds the instances with them: the modules from their specs (`modreg`), the
    products and the processes as Python.
  - Why: the module spec stays the one source of a module's program and its AAS (a module's AAS is
    4 to 7 MB, about 1,200 interface and 600 mapping elements, all derived). The types and
    templates are shared with the lab's stations. Instead of: the instances in aas-model as well,
    which would duplicate the specs.
  - modreg's own generated classes and templates are gone; `modreg generate` writes the ARSO
    templates into aas-model and has it make the classes.
- **aas-model's Variables replace ARSO's Operational Data.** *Journal.*
  - Variables has the shape decided for the operational data: live values as Properties, and
    `State`, `Measurements` and `Log` holding time series (IDTA 02008 as SMCs, an InfluxDB segment
    each). One model for the lab's stations and the modules.
  - A data point is a `VariableProp`: the semantic id says it is a variable, its meaning (what it
    shows) is its supplemental id. modlink reads the meaning there, and still the semantic id of
    the older AASs.
  - The coordinates are in `Variables/Measurements/Coordinates`, with their own semantic ids
    (`.../variables/Coordinate/1/0`). Their classes have names of their own (`RelativeCoordinate`,
    `CoordinateX`): aas_pydantic reads an element back as the class its dump names, among all
    classes, and aas-model already has a `Coordinate`.
  - ARSO follows (0.14).
- **The skill protocol's variables keep their id.** *Journal.* Session, Accepted and ErrorID carry
  `.../ControlComponent/Skill/OperationVariable/1/0`, stated where it holds. aas-model used to give
  it to every Operation variable; its variables are plain Properties now. The planner, the skill
  editor and the projection tell protocol from parameter by it.
- **The process AAS's templates are written by hand, not from an ontology.** *Journal.* AProSO is
  not remade yet. The templates follow the draft of 26 Oct (`process_aas.py`). Their classes are
  named apart from the skills' and the recipe's (`ProcessStepBinding`, `InputBinding`), which have
  the same idShorts but other fields.
- **Coordinates built (ARSO 0.13, vocabulary 0.5).** *Journal.*
  - What exists: modules (base, a mount and an end effector per axis, points), the table (base and
    flyways), the shuttles (the xbot, following the controller's X, Y, Rz) and the line's points.
    The example line places each module's base on the table, as a module will report it.
  - **A moving part is a fixed mount plus the moving coordinate.** Then every moving value is a plain
    data point (the end effector's Z is the axis' actual position), not an offset plus a signal, and
    a time-series record of it is just that value.
  - **The source of a moving value is a reference to the existing data point,** not a second
    mapping in AIMC. A client needs nothing new to follow it.
  - **No `History` segment yet:** it would be an empty container until the database exists.
  - **Operational Data may now hold no data points:** the line's has only its points. The rule
    requiring one was dropped.
  - **A module described from its spec alone is not placed:** its base is the root of its own small
    tree until `place` puts it on the table.
  - **Products are not done.** A product's coordinate (relative to the xbot, or a fixture on it) is
    instance data that changes at each handover. The product AAS (APSO) has no Operational Data
    yet; it comes with the product instances.
- **Coordinates: settled with the user.** *Journal.*
  - **One measurement series per coordinate,** in Operational Data's `Measurements`. It is shaped
    like every series of the plan of 26 Oct ([state-and-parameters.md](state-and-parameters.md),
    section 3): records in a time-series database, a `Latest` in the AAS. Positions will be
    reported by the modules themselves (RFID), so even fixed ones are measured.
  - **The parent is part of the record.** A record holds the time, the coordinate it is relative
    to, and x, y, z, roll, pitch, yaw.
    - A product on a shuttle: the xbot's series gets a record per move (the controller); the
      fixture is fixed relative to the xbot; the product's series gets a record only when it is put
      somewhere else, with the new parent and offset.
    - Where the product was at time t is composed from these. It is never stored.
  - **Rotation:** R = Rz(yaw)·Ry(pitch)·Rx(roll), about the parent's fixed axes (ROS's RPY;
    `modreg/frames.py` already composes so). Units mm and degrees.
  - **Granularity:** a module may hold several coordinates. Ours hold two: the module base, and the
    sled or end effector relative to it. No coordinate per component.
  - **Root:** the table.
- **Proposed (the user's whiteboard): coordinates as a transform tree in the operational data,
  instead of frames on Hierarchical Structures nodes.** *Journal.* Under evaluation, not built.
  - **Structure:**
    - a `Measurements` collection holding `Coordinates`;
    - each coordinate holds a reference to the coordinate it is relative to, and x, y, z, roll,
      pitch, yaw;
    - the semantic id says *Coordinate*; a supplemental id gives its meaning (end effector, top of
      vial).
  - **Why better than frames on nodes:**
    - The parent is a reference, not the part-of tree, so a product can sit on a fixture on a
      shuttle without being part of it, and be re-parented as it moves.
    - Coordinates that move (the needle, a shuttle) live with the other live data.
    - IDTA 02011 is no longer extended.
  - **Pitfalls to settle:**
    - Live values are not streamed into the AAS: a moving coordinate names the signal it follows,
      as data points do through the mapping.
    - A moving coordinate should change only in its joint: a fixed mount, then the moving part
      relative to it.
    - The rotation order and the units must be stated (roll, pitch, yaw about fixed axes,
      Rz·Ry·Rx, as ROS and `modreg/frames.py` already take it).
    - Each coordinate lives in the AAS of the asset it belongs to; references across AASs must
      resolve.
    - The tree must have one root (the table) and no cycles: a check.
    - Fixed poses under "Measurements" mislabel configuration as measurement.
    - "Variables" (aas-model) or Operational Data (ours) must be chosen.

- **No building, no hall, no IDTA 02045: the line is the root of all locations.** *Journal.*
  Decided by the user, overriding the entry below: the site level is not needed.
- **The frame on a Hierarchical Structures node extends IDTA 02011.** *Journal.*
  - What it adds: a statement the template does not define.
  - Why it is acceptable: 02011 (1.1, section 1.6) is meant to be "extended upon … specified
    further". The frame sits beside the template's elements and changes none, and its six properties
    carry IDTA 02075's ids. A reader of the bill of material is not affected.
  - The difference from extending 02045: there, a missing concept (orientation) would have been
    pushed into elements that mean something else (time-stamped records). Here a new, separately
    identified element is added. Both are extensions; this one is milder.
  - Open: the six properties straight on the node, without the `Frame` collection (fewer wrappers);
    or the placement in the part's own AAS, if IDTA 02075 has a submodel for it.
- **Locations: IDTA 02045 Asset Location for the site, frames for the line.** *Journal.* (Superseded
  above.)
  - 02045 holds the site and hall level: the address, the hall's coordinate system (local, with
    ground control points to WGS84), the hall as an area, and time-stamped records of where an asset
    was.
  - The line's geometry stays as frames on Hierarchical Structures nodes (AutomationML Frame, IDTA
    02075 ids): a module in the line, a component and its transfer points in the module.
  - The two meet at one place: the line's origin is a location record in the hall's coordinate
    system.
  - Why not 02045 alone: it has no orientation (it says so: no 6DoF "for now"), no frames relative
    to a parent, and positions only as event records with a time, not as a static pose.
  - Why not extend 02045: an extended template no longer conforms to the standard, and its readers
    would not understand the additions; frames on 02011 nodes are already standard elements.
  - A use for 02045 that fits it exactly: each station as a fence (an area in the line's coordinate
    system), and the product AAS recording entry and exit events as it passes. That is a location
    trace for the batch record.
  - Needs the lab's address and a measured origin of the hall; not built.
- **The CIRP paper's scope is narrowed to restructuring a module through its AAS.** *CIRP, Journal.*
  - Why: four contributions and three planners in six pages left each half-shown.
  - Instead of: models, planning, architecture and updating as equal contributions.
  - The capability model, the planner comparison, discovery, agents and locations move to the
    journal paper.
- **Effort is counted as user actions, as Dorofeev et al. (ETFA 2021) count them** (`cell/eval/effort.py`).
  *CIRP.*
  - Three ways of making the same skill: by hand in 4diac, in the skill editor, planned.
  - Why: the method is published and is the closest work's own measure, so the numbers compare.
  - Instead of: timing engineers (needs a study), or counting AAS elements (no counterpart in the IDE).
  - By hand counts every instance, subapplication, connection and value the rules build. The editor
    counts each element entered: 2 for a parameter or a step, 1 per field or binding. Planned counts
    the requirement.
  - First numbers: 131 to 151 by hand, 19 to 26 in the editor, 3 planned.
- **The argument for composites as instances rests on the standard, not on FORTE's limits.** *CIRP.*
  - FORTE can load basic and composite types online with its optional Lua loader, though never
    service interface blocks.
  - Why it still holds: creating instances and connections is what every IEC 61499 runtime does
    through management commands. Instances keep each step readable and monitorable.
  - Instead of: "FORTE cannot load types", which is not true.
- **Dorofeev et al. (ETFA 2021) generate one basic function block per composite, from a given
  sequence.** *CIRP.*
  - Their parallel steps grow as 2ⁿ states. Their future work is to keep the skill description in
    the AAS.
  - This is what our instance-only composites, join block and AAS-as-desired-state answer, and is
    why the paper cites them as the closest work.
- **The three planners' plans differ.** *Journal.*
  - GTPyhop follows the module's convention (home after every operation).
  - Aries returns by MoveAxis(0).
  - ENHSP adds a weighing of the empty vial.
  - Why it matters: it is the case for HTN methods carrying the integrator's way.
- **Scaling probe** (1 to 20 doses). *Journal.*
  - Aries grows from 0.08 s to 6.8 s on our HDDL encoding, whose value objects and sum facts grow
    with the doses.
  - GTPyhop and ENHSP stay flat.
  - To report as a property of the encoding, not of Aries alone.
