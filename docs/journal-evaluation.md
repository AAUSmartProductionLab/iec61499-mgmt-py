# Journal paper: implementing and evaluating the two cases

Written on 2 Nov 2026, for the authors. It says how the two cases are built and what is measured in
each, so that sections 4 and 5 answer RQ1 to RQ4. It is a plan: the tests themselves are still to be
designed in detail and run.

The method is in [journal-method.md](journal-method.md), the design decisions in
[journal-rationale.md](journal-rationale.md). For each part this file says what exists today; what
has to be built is listed, in order, in section 8.

## 1. From research question to evidence

| RQ | The claim to support | Evidence | Metric | Experiment |
| --- | --- | --- | --- | --- |
| RQ1 | Three blueprints, mostly IDTA templates, serve engineering, integration, planning and execution | The composition; the share of additions; who reads and writes which submodel during the runs | Element definitions by origin, per blueprint; share added; a read and write matrix from the AAS server's log | E1 |
| RQ2 | The additions close J1 to J7, and with them a new module is planned and invoked from its AAS alone | Each joint closed by a named element; taking that element away breaks a named stage; a module plugged into the line runs without code | Joints closed; the stage each removal breaks; manual actions, code changed outside the shell, time to the first run | E2, E3 |
| RQ3 | The constraints across submodels and shells are stated in SHACL over PPRL, and they find errors that metamodel and template checks cannot | Detection per class of error and per checker | Detection rate per mutation operator and checker; false positives; time to check | E4 |
| RQ4 | The blueprints transfer between the domains unchanged. The domains differ in candidates and timing, which needs no change of schema while running | Elements reused across the cases; the battery runs | Share of element definitions both cases use; additions per case; schema changes during the runs (expected 0); conformance after every change; time to check again | E6, E7 |
| Introduction | Traceability: execution data linked to product, process and resource as it is produced | Questions of a batch record, answered from the shells | Share of the questions answered from the shells and the time series alone | E5 |

Two rules for the whole evaluation:
- **No experiment counts what we defined ourselves without a test behind it.** "Seven joints closed"
  is circular on its own, because we chose the joints. E2 makes it a test: take each closing element
  away and see what breaks.
- **Faults are made by element kind, not by constraint.** Otherwise E4 would only find what the
  constraints were written for (section 5, E4).

## 2. What each case has to show

| | Pharma | Battery |
| --- | --- | --- |
| Product | A type, specified in advance | An instance whose condition is found during processing |
| Order of steps | A chain (GMP) | A partial order; the subassemblies' own sequences |
| Candidates per step | One, approved | Several, chosen per unit |
| Bound | Before the batch | Before the run, and again when a condition is found |
| Resources | Physical modules on Raspberry Pis (IEC 61499, OPC UA) | Stations simulated in Plant Simulation |
| What binds the case | Validation (GMP) | What the unit's condition allows |
| Main evidence for | RQ1, RQ2 (plug and produce), RQ3 | RQ1, RQ3, RQ4 |

## 3. Pharma: the physical line

**The system as it stands:**
- a planar table (B&R ACOPOS 6D) with three shuttles;
- the filling and stoppering modules, each running its IEC 61499 program in FORTE on a Raspberry Pi
  with an OPC UA server;
- capping, being built like the filling module, its crimper simulated;
- inspection, a camera service beside FORTE;
- loading and unloading by two KUKA KR C4 robots;
- three products: a 2 mL vial, a 1 mL prefilled syringe and a 3 mL cartridge.

**The blueprints instantiated:**
- **Resource shells:** the line, the modules, their components, the table and the shuttles,
  generated from the module specs by `modreg`. The robots get theirs once their specs exist.
- **Product shells:** the three types, written out in full with aas-model's classes
  (`cell/examples/products`).
- **Process shells:** one per product on the line, with one candidate per step, status Approved
  (`cell/examples/processes`).
- **Records:** Executed Processes in the instance AAS of each batch. To build (D2).

**The stack:**
- BaSyx: the AAS environment with Operation delegation, registries, the web UI;
- the data management platform: AID and AIMC to OPC UA, and time series into InfluxDB;
- Prosody, the XMPP server, for the agents;
- the two orchestrators: our agents, and the colleagues' FOND policy run as a behaviour tree.

**Scenarios:**
- **P1 Changeover.** The line makes the three products in turn. Each process shell says Fits, and the
  batches run.
- **P2 Plug and produce.** The line runs with filling and stoppering. Capping is powered on and joins
  the network:
  1. it is discovered (OPC UA multicast discovery);
  2. it is registered and checked (C01 to C15);
  3. its capabilities are derived;
  4. the vial's process shell said DoesNotFit (Capping unbound); now Capping is bound and it Fits;
  5. the batch runs.

  This is E3.
- **P3 A product the line cannot make.** An ampoule: Validation says DoesNotFit, with the finding, and
  nothing runs.
- **P4 A capability after a reconfiguration.** The syringe needs BottomUpFilling:
  1. a described skill offers it, with `AfterReconfiguration`;
  2. it is built online;
  3. it is bound and run.

  This is the CIRP paper's case. Here it is evidence for `Deployment` and `Availability`.
- **P5 Traceability.** After a batch, the record's questions (E5).

## 4. Battery: the simulated disassembly cell

**First, align with REVAMP** (A10 in journal-method.md). Our example pack was drawn for the figures:
four modules, busbars, a BMS, and a cover with twelve screws. The case is the colleagues' REVAMP truck
battery:
- housing, cover and modules;
- screw, plug and form-fit connections;
- robot cells for cover removal and for module disconnection, a manual station, and a sorting station.

The product shells, the station shells and the `-battery` figure pages are remade from its bill of
material and station list once the colleagues share them.

**The blueprints instantiated:**
- **Product:** the pack's type AAS, holding:
  - the bill of material with the connections;
  - Process Parameters;
  - the required capabilities;
  - the Disassembly sequence.

  Each arriving pack gets an instance AAS derived from the type AAS. It holds the pack's condition
  (A5) and its record.
- **Resources:** one shell per station, with Capability Description, Skills, AID and AIMC. They are
  either generated from station specs (`modreg`), or written to the blueprint by the colleagues. Shells
  written by other people with other tools would themselves show that the blueprint is not tied to our
  generator.
- **Process:** the pack's type on the cell. Each step has the candidates the cell offers, for example:
  - Unscrewing by the robot cell, up to 25 Nm;
  - Unscrewing at the manual station, at any torque;
  - destructive separation, if the part goes to recycling.

**The dynamics, in the blueprint's terms** (a proposal for the colleagues):
1. **A pack arrives.** Its instance AAS is made from the type AAS. Its condition is not known yet, so
   the type's nominal values apply.
2. **Before each step,** its candidates are checked against the instance's values: C17 and C18, with
   the instance's values in place of the type's. The orchestrator takes one that fits.
3. **A station finds a condition.** Examples: a screw that does not break loose at the cell's highest
   torque; a corroded screw; a missing fastener; a module of another variant. The finding is written
   into the pack's instance AAS as a value. No element is added.
4. **The candidates of the steps it affects are checked again.** A candidate whose capability no
   longer covers the values drops out: the robot's Unscrewing to 25 Nm does not cover a seized screw.
   The others remain, such as the manual station, or destructive separation where it is allowed.
5. **If no candidate fits, the step is stuck,** and the finding says why. That is a gap in the cell,
   which E7 counts.
6. **Each executed step is recorded** in the pack's Executed Processes, with the binding that was used.

The only changes during a run are values in existing elements and new entries in the record. The
schema never changes, which is the colleagues' evaluation item (iii).

**Whether destructive separation is allowed** depends on where the part goes: to reuse or to
recycling. So the required capability's property `Destructive` takes its value from a product
parameter, which a decision on the measured condition (the state of health) sets. *[Authors: this says
the same as the effort attribute of the colleagues' JointParams, as a value the matching can use.]*

**Coupling Plant Simulation to the shells.** Three ways, from the strongest to the cheapest:
- **A bridge: the stations behind the same interface as the pharma modules.**
  - How: each simulated station is a module whose OPC UA server is a bridge, written in Python like
    the planar controller. Plant Simulation, as an OPC UA client, reads the bridge's command flags and
    writes back completions, results and the conditions it found. The data management platform, the
    agents or the behaviour tree call the stations as they call the pharma modules.
  - Shows that the resource blueprint, and the way a skill is called, carry over to the second case.
  - Cost: it runs in real time, so only a few packs.
- **A decision service** (recommended for E7's statistics).
  - How: Plant Simulation runs the material flow. At each step, and at each condition found, it asks
    a Python service, over Plant Simulation's COM or OPC UA interface. The service writes the pack's
    instance AAS, checks the candidates and answers with the station to use.
  - Gains: many packs, faster than real time. The resource shells are read for their capabilities but
    not called.
- **A replay** (the fallback).
  - How: Plant Simulation runs on its own and writes a log. A script replays the log against the
    shells, updating and checking them.
  - Cheapest, but the models decide nothing.

Recommendation: the decision service for E7, and the bridge for a handful of packs if there is time,
to show that the way a skill is called carries over too. *[Plant Simulation is an OPC UA client and can
be driven from Python through COM; check the version's interfaces before choosing.]*

**The stochastic model** (to be set with REVAMP's data):
- per connection: the probability that it is seized, corroded or missing;
- per module: its variant, and the distribution of its state of health;
- per station: the distribution of processing times, and the highest torque of the cell's
  screwdriver.

The seeds are fixed and published.

**Scenarios:**
- **B1 Nominal packs** (no defects): every step on its first candidate.
- **B2 Packs with conditions to find:** steps rerouted among their candidates.
- **B3 Sorting by state of health:** a decision on a step's output.
- **B4 A station out of service:** its candidates drop out, by the same mechanism as in B2.

## 5. The experiments

### E1 Composition, and the share of additions (RQ1)

- **Material:**
  - the templates of the three blueprints: IDTA's JSON as published, and ours from `aas-model/templates`;
  - the shells of both cases.
- **Procedure:**
  1. Walk each template. An element definition is a path of idShorts with its semanticId.
  2. Decide its origin by its semanticId:
     - IDTA: `admin-shell.io/idta/...`, `admin-shell.io/zvei/...`, and the W3C WoT terms that AID uses;
     - ours: `smartproductionlab.aau.dk/...`.

     An element of ours inside an IDTA submodel is an addition.
  3. Count the definitions per blueprint and per submodel, by origin.
  4. Count the shells' elements by origin, in each case.
- **Who uses what:** log which client reads and writes which submodel on the AAS server, during P1 to P5
  and B1 to B4. Read per client from BaSyx's request log, this gives each phase's use of each submodel:
  `model-use` measured instead of drawn.
- **Output:** Table 5.1, and the measured read and write matrix.
- **To build:** a counting script (small); logging per client (small).
- **Expected:**
  - few templates of ours: Skills, Variables, Parameters, the recipe, and the three process templates;
  - most of our definitions in Skills;
  - a small share of a module's elements, since AID and AIMC dominate it: about 1,200 and 600 elements.

### E2 The joints, closed and taken away again (RQ2)

- **Purpose:** to show that each addition is needed, not only present.
- **Procedure:** for each joint, replace the closing element by what the template or the related work
  has instead. Then run the stages below on the simulated pharma modules (FORTE on the PC) and on the
  battery models.

  | Joint | Replaced by |
  | --- | --- |
  | J1 | `CapabilityRealizedBy` as an external reference with the skill's name, as 02020 has it |
  | J2 | No `InterfaceReference` and no Operation mapping, so the call has to be configured outside the shell, as FA³ST or the DataBridge would need |
  | J3 | No meanings: matching by idShort |
  | J4 | No input bindings: values sent with the call at run time |
  | J5 | No process shell: the station chosen at run time |
  | J6 | `Steps` replaced by a list of the skills used, as the Control Component templates have it |
  | J7 | The connections as a document |

  The stages: register, derive, match, bind and check, invoke, record.
- **Metric:** for each replacement, the first stage that fails, or that needs code or configuration
  outside the shells, and what the check reports.
- **Output:** Table 5.2: the joint, the element, the stage that needs it, and what breaks without it.
- **To build:** replacement scripts on the example shells (small to medium). The stages already exist:
  `modreg`, the plan check, the data management platform's live test, the agents.

### E3 Plug and produce on the physical line (RQ2)

- **Procedure:** scenario P2 on the hardware, with the user at the bench.
- **Metrics:**
  - the time from power on to each stage: registered, checked, capabilities derived, Fits, first skill
    call answered;
  - the integrator's actions, counted as in the CIRP paper's effort measure [cite: dorofeev2021];
  - code and configuration changed outside the module's shell, in lines (expected zero);
  - the same with the other orchestrator, if the colleagues' behaviour tree runs by then.
- **Runs:** five, reported as medians and ranges.
- **Optional baseline:** the same module added to AP2030-UNS, the project's predecessor, counted the
  same way.

### E4 Which errors the constraints find (RQ3)

- **Shells:**
  - pharma: line, modules, components, the three products and their processes;
  - battery: the pack's type and instances, the stations, the process.
- **Faults (mutants):** made by operators per element kind, not per constraint, so that they do not
  presuppose our checks. Each operator is applied at every place it fits, or at a fixed random sample
  per operator, with published seeds.

  | Element kind | Operators |
  | --- | --- |
  | Any model reference | point it at nothing; at another element of the same kind (a skill of another module, a step of another recipe, a module not on the line); at an element of another kind; remove it |
  | Any semanticId | remove it; replace it by another template's |
  | Any meaning | remove it; replace it by another term of the vocabulary; replace it by an unknown IRI |
  | Any value | break its type; leave its allowed values; move a product's value out of the input's limits or the offered range; change its unit |
  | Any element with a multiplicity | delete a mandatory one; duplicate one allowed once |
  | A recipe | `After` to a step that is not a sibling; `After` that closes a cycle; `Order` against `After` |
  | A connection | a part that is not in the BoM; defined twice; no step that breaks it |
  | A process shell | a step left unbound; an input without a default left unbound; the recipe's revision raised; Validation set to Fits over findings |

- **Checkers,** from the narrowest scope to the widest:

  | # | Checker | Scope |
  | --- | --- | --- |
  | K1 | The metamodel: aas-core's verification, or BaSyx's strict reading | Metamodel |
  | K2 | The AAS Test Engines [otto2025test] | The metamodel, and their two templates: the Digital Nameplate and Contact Information |
  | K3 | Each shell against its structure ontology: SHACL from APSO, APrSO and ARSO | Scope 1 |
  | K4 | K3, plus the constraints within a shell and across the shells of one class | Scopes 1 to 3 |
  | K5 | K4, plus across classes: the whole of 3.6 | Scopes 1 to 4 |

- **Metrics:**
  - detection rate per operator and checker. A fault is found if the checker reports a violation, and
    located if the report names the faulty element or its parent;
  - false positives on the shells before any fault is made (expected zero);
  - the time to check, against the number of shells and elements.
- **Mutants that no checker finds** are looked at one by one: each is either harmless (an equivalent
  mutant), or a gap in the constraints, reported as such.
- **Real errors.** Errors that happened while the models were built, made again and checked
  (design-log.md, work.md):

  | Error | When | Constraint that finds it |
  | --- | --- | --- |
  | A composite's steps referred to components that do not exist (`ModuleLinearAxisAAS`) | 30 Oct | C12 |
  | The syringe asked for a fill error the module cannot meet | 28 Oct | C17 |
  | Temporary idShort properties left in published shells | 28 Oct | C04 |
  | Semantic ids naming single elements | 26 Oct | C04 |
  | The placeholder left in an Operation's delegation URL | 28 Oct | None yet: a gap, or a C22 |

- **Output:** a heatmap of operators against checkers; the table of real errors.
- **To build:**
  - the mutation tool (medium);
  - a runner for K1 to K5 (small);
  - the shapes for K4 and K5 (medium, D5);
  - APSO's and APrSO's shapes (medium, D7).
- **Expected:** K1 and K2 find the metamodel's errors only, K3 those of the templates, and K4 and K5
  those of the joints.

### E5 Traceability

- **Procedure:** after P1 (a batch of n vials) and B2 (m packs), answer a fixed set of questions per
  unit from the shells and the time series alone:
  - which resource and skill carried out each step;
  - with which values, and with what results;
  - when;
  - under which revision of the recipe, and which deployment of the skill;
  - which deviations happened, and why;
  - who called (the session).
- **Metric:** the share of questions answered, and how many references each answer follows.
- **To build:** the record (Executed Processes with the four references), and the orchestrators
  writing it (medium).

### E6 Transfer across the cases (RQ4)

- **Procedure,** from E1's counts:
  - for each element definition, whether pharma, battery or both use it;
  - the additions made for one case only, each with its reason;
  - the constraints that matter in one case only. A constraint about something that is absent holds
    trivially, so none should fail for that reason.
- **Output:** a table, or a Venn diagram, and the list of additions.

### E7 Runs of the battery cell (RQ4)

- **Runs:** N packs per scenario, B1 to B4 (about 200), with fixed seeds.
- **Metrics per pack:**
  - conditions found;
  - checks made again;
  - candidates dropped;
  - steps bound again;
  - steps stuck, with no candidate left.
- **Metrics over all runs:**
  - conformance of every shell after every change (expected 100 %);
  - schema changes (expected 0);
  - time to check again, against the cell's cycle time;
  - whether each choice was right, against the simulation's ground truth: could the chosen station do
    the step under the true condition?
- **Optional contrast:** the same packs on a fixed plan, with no checks made again. Steps then fail at
  the station, instead of being rerouted before.
- **Output:** a table per scenario, and a distribution of the times to check again.

### E8 Authoring effort (optional)

The elements written by hand against those generated, per case:
- the module shells are generated from specs;
- the product and process shells are written;
- the station shells are written or generated.

## 6. The results section, as it would read

| § | Answers | Shows |
| --- | --- | --- |
| 5.1 | RQ1 | Table 5.1 (composition and shares); the measured read and write matrix |
| 5.2 | RQ2 | Table 5.2 (what each removal breaks); E3's times and counts, as a timeline |
| 5.3 | RQ3 | The heatmap of operators against checkers; the real errors; time to check |
| 5.4 | RQ4 | E6's reuse table; E7's tables per scenario |
| 5.5 | Traceability | E5's questions and their answers |

## 7. Threats to validity

- **Internal.** The authors built the models, the constraints and the faults. Mitigations:
  - operators per element kind (E4);
  - real errors from the project's history;
  - every mutant and its seed published;
  - the SHACL shapes tested against the Python checks they replace.
- **Construct.**
  - Counting elements depends on what counts as one. Define it once (a path of idShorts with a
    semanticId), and report the instance counts beside the definitions.
  - The joints are ours. Mitigations: derive them from IDTA's own texts, as section 2 does, and set the
    related work against them (journal-rationale.md, section 6).
- **External.**
  - Two cases; a lab line, not a GMP-validated one; a simulated battery cell.
  - The vocabulary is ours: another lab's would need aligning before matching works across labs.
  - One AAS server and one runtime.
- **Conclusion.** Few physical runs (five per scenario): report medians and ranges, and claim no
  differences that the runs cannot show.
- **Reproducibility.** Publish, at the versions used:
  - the templates, ontologies and shapes;
  - the checkers and the mutation tool;
  - the example shells;
  - the scripts of E1 to E7.

  A Zenodo record per repository would give each its DOI.

## 8. The order of work

Rough sizes: S is a day or less, M a few days, L a week or more.

| # | What | Needs | Size |
| --- | --- | --- | --- |
| 1 | Settle A1 to A11 with the colleagues (journal-method.md, section 5) | – | a meeting |
| 2 | Decide D1 and D2. Then, in aas-model, the record's template (02031-2 with four references), and NotChecked in Validation | 1 | S |
| 3 | PPRL 0.3 (`invokedThrough`, the connection relations); the projection of the product and process shells (D6) | 1 | M |
| 4 | APSO and APrSO remade from the templates; SHACL generated for all three (D7) | 1, 3 | M |
| 5 | The constraints of scopes 2 to 4 as SHACL; C10, C11, C14, C19, C21 added; tested against the Python checks (D5) | 3, 4 | M |
| 6 | E1's counting script and the logging per client | 2 | S |
| 7 | E4's mutation tool and the runner for K1 to K5, first on the pharma shells, which exist | – (until 5 is done, the Python checks stand in for K4 and K5) | M |
| 8 | E2's replacements on the pharma shells, with the modules simulated | – | M |
| 9 | Pharma on the hardware: capping on its Pi; P1 batches; E3, with the user at the bench | capping built | L |
| 10 | The record written by the orchestrators; E5 | 2, 9 | M |
| 11 | Battery: the REVAMP shells (A10), the station shells, candidates, condition, the decision service, the coupling to Plant Simulation | 1, 2, 5 | L |
| 12 | E7 runs; then E6 from E1's script over both cases | 11 | M |

What can start before the meeting: 6, and 7 and 8 on the pharma shells, since they do not depend on
the product's side being settled.
