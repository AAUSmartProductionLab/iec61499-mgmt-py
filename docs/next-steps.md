# Next steps

Plan of 6 Oct 2026. The guiding star is the integrated architecture in *Plug and produce
architecture: components, flow and status* (the ten-step loop: connect, identify, discover,
verify, register, match, plan and bind, execute, monitor, reconfigure). What is built and how is
in [work.md](work.md); how the work divides into repositories in
[repositories.md](repositories.md).

## What we are aiming at

The work specifies three things: how a module is built, what its AAS holds, and how the AAS is
used to control and reconfigure it. The test is a module we did not generate:

> A vendor builds a module in an IEC 61499 IDE inside our module shell, describes it with the AAS
> generator from its spec sheets, and delivers the program and the AAS. We plug it in. From the
> AAS and the running program alone it is verified, registered, matched to a product's process,
> operated, and given a new skill or new parameter values online.

Today the bottom of the loop works (spec → FORTE → AAS on the server → HMI and `modlink`), but
the integrator's tools still lean on our own module spec, and the middle of the loop (match,
bind, execute across modules) is missing. The CIRP full paper is due 18 Nov 2026.

## The phases

Each step names where the work lands and how we know it is done. Days are working days and
rough.

### Phase 0: one vocabulary, one ontology, a volume to fill (about 3 days)

Small things everything else stands on.

| # | Step | Where | Done when | Days |
| --- | --- | --- | --- | --- |
| 0.1 | **One ARSO.** Bring the generation project's copy up to this repository's (reconfiguration elements of a skill, Control Configuration, parameter entry). This copy is the one that is edited until the ontologies get their own repository | `ontology/`, generation project | Both projects load the same files; each one's tests pass | 0.5 |
| 0.2 | **Capability vocabulary.** The capability and property meanings as lab IRIs kept in `ontology/`; module specs and the planner's recipes use them | `ontology/`, `cell/modules`, planner | A required capability of a recipe and the offered one of a module carry the same IRI | 1 |
| 0.3 | **Fill volume.** A Volume parameter on Dispensing, turned into a dwell time at the station's flow rate; FillVolume of the Filling capability names it | module library, `cell/modules/filling.yaml`, FORTE rebuild | `Dispensing.Start(Session, 2.0)` dwells for the matching time on FORTE; the AAS links FillVolume to the parameter | 1.5 |

### Phase 1: the AAS is all the integrator needs (about 8 days)

This is the paper's core claim, and where this repository does not yet match the aim.

| # | Step | Where | Done when | Days |
| --- | --- | --- | --- | --- |
| 1.1 | **The model says what a skill can be built from.** Building blocks that are not offered (Dwell) with their block type, parameters and equipment; the fixed pattern of a module level skill written down as a rule of the module, not only as generator code. Declared in ARSO, classes regenerated | `ontology/ARSO`, `modreg`, module library notes | The AAS of the filling module lists Dwell as a building block; `modreg check` still passes | 1.5 |
| 1.2 | **Structure from the running module.** The structural half of a profile (skills, parameters, sequences, equipment, interface, type hashes) read from FORTE alone; the descriptive half (nameplate, capabilities, units, descriptions) from a description file; merged | `modreg`, `modsync` | The profile built without the module spec equals the one built from it, for both modules | 2.5 |
| 1.3 | **Identify and verify against the AAS.** The module publishes its identity (asset id, AAS id, program digest); `modsync` compares the running program with what the AAS states, not with the spec | module library (one block, FORTE rebuild), `modsync` | A program that differs from its AAS is reported; loop steps 2 and 4 hold without a spec | 1.5 |
| 1.4 | **Reconfigure from the AAS.** A new module level skill described as steps and bindings (as the AAS describes one) is created online from that description; a parameter value is changed; the change is recorded in Control Configuration and the AAS is registered again | `modsync`, `modreg` | The live test that creates DoubleDose online passes when driven by a skill description instead of a module spec; the change log shows it | 2 |
| 1.5 | **Conformance.** One command checks a module against the rules: the library blocks are present with their hashes, the address space equals the one the AAS describes, the AAS passes the ontology check | `modsync`, `modreg` | Both modules pass; a module with a missing block or an undescribed node fails with the reason | 0.5 |

### Phase 2: the middle of the loop (about 7 days)

| # | Step | Where | Done when | Days |
| --- | --- | --- | --- | --- |
| 2.1 | **Matcher.** Required against offered capability on the RDF projection of the Capability Descriptions (the generation project's projection), SHACL rules for values and ranges; the planner's and `modlink`'s matching stay as cross-checks | `ontology/`, validation code | The pharma recipes give the same verdicts as the planner's matcher, or the differences are explained | 2 |
| 2.2 | **Planner on our modules.** The planner reads ARSO's Skills submodel and the shared vocabulary, and binds a step's parameter to a skill parameter (FillVolume → Volume) | planner (TypeScript) | A recipe step binds to Dispensing of the registered filling module in the planner | 1.5 |
| 2.3 | **Plan executor.** Walks a Production Sequence: occupies the modules it needs, runs each step's skill with its bindings, follows optional and parallel flows, keeps the product counter | `modlink` | One product runs Dispense then Close on the filling and stoppering modules, on the simulators and on FORTE | 2.5 |
| 2.4 | **Check before running.** A plan is refused when a step has no candidate, a bound value is outside the skill's range, or a module's AAS no longer matches its program | executor, matcher | Three broken plans are refused with the reason | 1 |

### Phase 3: experiments and the paper (the last three weeks)

| # | Step | Done when |
| --- | --- | --- |
| 3.1 | **Scenario runner.** Plug in a module (register → match → bind → run); change a parameter (new fill volume); change the flow (inspection every fifth product: plan only); change the composition (a new skill created online). Each timed: downtime, commands sent, verification | The four scenarios run unattended and write their numbers |
| 3.2 | **Baseline.** The same changes by full redeployment (boot file and restart) | Numbers side by side |
| 3.3 | **Hardware.** The same scenarios on the two Pis once they are wired; until then FORTE on the Pi with simulated IO | Depends on the wiring |
| 3.4 | **Writing.** | 18 Nov |

### After the paper, or beside it when the lab answers

- **Module shell.** A 4diac template project with the fixed parts in place; one skill written by
  hand in the IDE goes through phase 1 like a generated one.
- **Generator on the pydantic profile.** The LLM writes the descriptive half of a profile; the
  generation project uses the shared model and validator.
- **Live side of the AAS.** Mapping execution into Operational Data (the lab's node or a small
  bridge), history, a registry.
- **Lab deployment.** Registration on the lab's AAS server; `modreg` beside or inside the lab's
  registration.
- **Repository split**, CI, retiring `modsync/aas.py`, agents.

## Timeline against 18 Nov

| Week | Work |
| --- | --- |
| 6 to 12 Oct | Phase 0; 1.1, 1.2 |
| 13 to 19 Oct | 1.3 to 1.5 |
| 20 to 26 Oct | 2.1 to 2.4 |
| 27 Oct to 2 Nov | 3.1, 3.2; hardware if wired; paper outline and figures |
| 3 to 18 Nov | Experiment runs, writing |

That is about 18 days of building in three weeks: it fits only if nothing slips. If it does, cut
in this order:

1. 1.5 Conformance (the tests already show it).
2. 2.1 The ontology matcher (the planner's matcher carries the demonstration; the ontology one
   becomes future work).
3. 1.2 for the stoppering module (show it on the filling module only).
4. 3.3 Hardware (FORTE on the Pi with simulated IO).

Not to be cut: 0.2, 0.3, 1.3, 1.4, 2.3 and 3.1. Without them there is no loop to show.

## What I need from you

Decisions, each blocking a step:

| Decision | Blocks | My recommendation |
| --- | --- | --- |
| May ARSO be extended for building blocks and for what a skill's Contract, Step and Implementation contain? | 1.1 | Yes; additions only, in the control component module |
| Is the validator closed (refuses what ARSO does not describe) or open (reports it)? | 0.1 | Open for now, closed once ARSO describes the Web of Things terms of the interface |
| Fill volume as dwell time at a fixed flow rate, or a pump? | 0.3 | Flow rate; no hardware change |
| Does the plan executor live in `modlink`? | 2.3 | Yes; an export for the lab's orchestrator later |
| Which product and which changes does the paper show? | 3.1 | One vial product on two modules; the four scenarios above |

Facts only you or the lab have: when the two modules are wired; the measured values of each
station (fill range and accuracy, diameters) and the flow rate; who changes the planner (2.2 is
TypeScript in your fork); whether we may publish to the lab's AAS server.
