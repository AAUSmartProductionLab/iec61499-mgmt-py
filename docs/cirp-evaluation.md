# The CIRP paper's evaluation: protocols and results

Three experiments, decided on 3 Nov 2026 (Q1, Q3 and Q4 of [paper-outline.md](paper-outline.md),
section 4): how fast a change takes effect and how that scales (Q1), whether the program stays what its
AAS says (Q3), and whether the skills are right for the product (Q4). They are done one at a time. Each
gets a protocol before any data is taken (this file), a harness, a pilot that checks the measurements
themselves, the full runs with checks in every run, and a review of the results before the next.

## Common to all

- **Runs are independent.** Every run starts a fresh FORTE with the module's boot file, so no run
  inherits another's state. Runs go in a random order (seeded, the seed recorded), so that a drift of
  the machine over hours does not line up with a factor. Five warm-up runs at the start are discarded.
- **Every run is checked.** Each run records the checks below with its measurements. A run that fails a
  check is counted and reported, never dropped silently. A run that fails for a reason outside the
  method (a port in use, FORTE not starting) is logged with its error and run again at the end.
- **What is recorded with each run:** the machine (CPU, OS, Python), the FORTE build (its file hash),
  the repository's commit, the time, the seed and the run's place in the order.
- **Statistics:** medians with 95 % bootstrap intervals (10,000 resamples, percentile); least-squares
  fits with R²; rates with 95 % Wilson intervals. Times by `time.perf_counter`.
- **PC setup:** FORTE 3.3.0 built for Windows by the FBE as the evaluation's own
  (`cell/eval/forte/build.ps1`, into `runtime/fbe/build/modules-win-eval`): the lab's patches 0001 to
  0007, and two changes for programs of 10 and 20 composites, which the lab's FORTE cannot read back
  or boot (the second pilot, below): `cell/eval/forte/0008-connection-query-by-part.patch` and event
  lists of 1024 (`runtime/fbe/configurations/eval/modules-win-eval.txt`). The lab's FORTE and the
  kit stay without them. The filling module's IO simulated (`cell/sim/module_sim.py` over Modbus),
  all on one PC (loopback). The Pi 5 runs, at the bench, follow the PC runs (a subset of the cells).

## Q1: activation time, management commands and unavailability, and how they scale

**Question.** How long does a change take from the AAS to the running, verified program; how many
management commands does it need; how long is the module unavailable; how do these grow with the size of
the change and of the program; and how do they compare with a full redeployment?

**Hypotheses** (stated before the runs):

- H1.1 A new composite's activation time grows linearly with its number of steps and with the program's
  size, and stays below 1 s on the PC up to 32 steps in a program of 20 composites.
- H1.2 Its management commands are a linear function of its steps and parallel blocks that the rules
  fix, and the measured counts equal that function in every run.
- H1.3 The module stays available while a composite is added: a skill started before the change
  succeeds, and its duration differs from the same skill's without a change by less than 2 %.
- H1.4 A restart keeps the module unavailable at least ten times longer than an online change of a
  value, and for a new composite (unavailable for no time online) for several seconds.

**Factors.**

| Factor | Levels |
| --- | --- |
| Change class | parameter (a step's constant: Dispense's FlowRate in Dispensing); flow (a new composite) |
| Composite size | 1, 2, 4, 8, 16, 32 steps in sequence |
| Parallel branches | 2, 3 branches holding 8 steps (with the sequence of 8 as one branch) |
| Program size | 1, 5, 10, 20 composites in the program before the change (Dispensing and copies of it) |
| Mode | online (`modsync reconfigure`); restart (the program with the change generated, a new boot file, FORTE restarted) |
| Start, for a parameter | Execute (an order running: the module has to be stopped for the guard) or Idle and free (between orders) |

**Cells,** 30 runs each, 1,260 runs in all:

| Set | Cells |
| --- | --- |
| A, flow, sequences | 6 sizes by 4 program sizes = 24 |
| B, flow, parallel | 8 steps in 2 or 3 branches, program size 1 = 2 |
| C, parameter | 4 program sizes by 2 starts = 8 |
| D, restart | the flow change of 8 steps, and the parameter change, at each program size = 8 |

**The synthetic composites.** A sequence of n steps repeats a dose cycle on the module's own
primitives: MoveAxis to the fill position (40 mm), Dispense the skill's parameter Volume at 1 mL/s,
Home, Weigh. Step names are unique (`S01`, `S02`, ...). In a parallel block each branch uses its own
equipment item (axis, pump, scale), as the equipment blocks allow one holder at a time. The module
has three, so three branches at most: a fourth would share one, and the reconciler refuses such a
composite before it sends anything ("two branches use LinearAxis", seen in the second pilot; a case
for Q4). A program of size m is the filling module with m - 1 copies of Dispensing (`Dispensing02`,
...) generated in.

**Measures.**

- *Activation time* T_act, split into phases measured inside the reconciler (`stats` of
  `modsync.desired.reconfigure`): **read** (the program read over the management protocol and
  compared with the AAS), **compile** (instances, values and connections from the rules, and the
  block types asked of FORTE), **apply** (the commands sent and answered), **verify** (the program
  read again and compared) and **persist** (the boot file amended and written). It starts when the
  reconciler is called with the changed AAS; reading the AAS from a server is outside it.
- *Commands* N_cmd and the *bytes* of their requests.
- *Unavailability* U, the time the module cannot take a product. Online, for a flow change: none by
  construction; checked by a skill started just before the change (Dispensing), which must succeed,
  and whose duration is compared with its duration without a change in the same FORTE (paired), and by
  the module's state, which must stay Execute (V9). Online, for a parameter change from Execute: from
  the call to stop the module (the guard needs it Stopped, Idle or Aborted and free) until it is in
  Execute again; from Idle: the reconciler's time, the module staying Idle. By a restart: from
  stopping FORTE until the module is in Execute again, split into **load** (FORTE started until the
  module reports Stopped), **reset** (Reset until Idle) and **start** (Start until Execute); compared
  with the Idle start, until Idle (load and reset). Also the time to generate the boot file.
- *Clocks.* Times by `time.perf_counter`. States are waited for by polling every 50 ms, so a wait ends
  up to 50 ms late (about the same number of waits online and by a restart); the module's state is
  also recorded by an OPC UA subscription, and U computed from its timestamps as well (`u_clock_s`).
  FORTE writes its variables without timestamps; the server (open62541) stamps them and samples them
  every 50 ms at the fastest (its `MinSupportedSampleRate`, read from it), so a state's time is known
  to 50 ms: the skill durations fall on two values 50 ms apart (7.60 and 7.65 s). That is enough for
  H1.3 (2 % is 150 ms, and the differences are paired). The first value of a new subscription is
  stamped when it is sampled, not when it was set, so it is not used. The server publishes every
  100 ms, so the harness waits for a notification instead of reading the clock at once.

**Procedure of a run.**

- *Online, flow:* start FORTE with the boot file of program size m and wait for Stopped; Occupy, Reset,
  Start; V1. In the disturbance cells (n = 8 and 32 at m = 1 and 20) run Dispensing once for its plain
  duration d0. Start Dispensing (1.0 mL) and at once reconfigure with the composite described; V2 to
  V4. Wait for Dispensing to succeed (duration d1, V6). In the first run of each cell, start the new
  composite and wait for it to succeed (V5). Stop FORTE.
- *Online, parameter, from Execute:* as above up to V1; stop and release the module (the guard);
  reconfigure with the changed value; Occupy, Reset, Start until Execute (U ends); V2 to V4, V8. Stop
  FORTE. *From Idle:* FORTE started, the module occupied, reset and released (Idle and free); V1;
  reconfigure (U); V9 (still Idle and free), V2 to V4, V8. Stop FORTE.
- *Restart:* generate the changed program's boot file (timed); start FORTE with the unchanged program,
  Execute; then stop FORTE, start it with the new boot file and bring the module to Execute (U and its
  parts); V7. Stop FORTE.

**Checks in every run.**

| | Check |
| --- | --- |
| V1 | Before the change the program is what the AAS of program size m describes (the reconciler's reading, no difference) |
| V1g | ... and what the generator's boot file of that program creates: the same instances of the same types, the same connections, the values it writes (read back). Independent of the AAS and of the reconciler's reading |
| V2 | The reconciler finishes without refusing and reports the change verified |
| V3 | A read after it, by the harness, finds no difference to the changed AAS |
| V3g | ... and the program is what the generator's boot file of the changed program creates (as V1g) |
| V4 | The commands sent, by operation, are those the generator's boot files before and after the change call for: an instance more is created and started, a connection more made, a value more or changed written, an INIT link from the running program into a new instance fired once, nothing else |
| V5 | The new composite runs and succeeds (first run of each cell) |
| V6 | The skill running meanwhile succeeds (flow cells) |
| V7, V7g | After a restart the program is what the changed AAS describes, and what the generator's boot file creates |
| V8 | The boot file the reconciler amended creates, writes and connects exactly what the generator's boot file of the changed program does (compared as sets, without request ids and order): the program changed online and the one generated with the change are the same, also after a restart |
| V9 | The module's state did not change during the change: Execute (flow cells), Idle and free (a parameter from Idle) |
| V10 | FORTE logged no error during the run (its whole log; an event dropped from a full queue is one). The OPC UA server's failed registrations with a discovery server (it announces itself, LDS-ME, and finds the FORTE of the run before while that one stops) are counted apart, not as errors: they do not touch the program |

V1g, V3g and V7g give the reconciler's verification an oracle of its own: the generator builds the
program from the module spec by other code than the reconciler's reading, interpreting and comparing.

**The pilots.** One run per cell, to check the measurements and the checks before the runs count. Their
runs are kept in `cell/eval/results`: `q1-2026-11-03T2306.jsonl` (the second), `q1-2026-11-03T2333.jsonl`
(the third) and `q1-2026-11-04T0006.jsonl` (the fourth).

- *First pilot (3 Nov, stopped).* Building the AASs inside the runs made it spend an hour before its
  first run: they are built once before the runs now (and without the derivation, below). Added: V8;
  a real boot file for the persist phase (`LocalDeployer` on a folder per run); the read phase split
  into reading the program (`program_s`), interpreting the AAS (`aas_s`) and comparing (`compare_s`).
  The first read in it took 0.44 s against 0.02 s for the second; that is Python importing the tools
  (0.45 s measured alone), not the AAS: interpreting any AAS takes 1 to 2 ms after it. The warm-up
  runs take it.
- *Second pilot (3 Nov, 39 runs).* 4 passed, 15 failed a check, 20 failed in the method; nothing was
  counted from it. What it found, and what was done:
  - V4 failed in every flow run because the harness's prediction looked for the new instances without
    the application's container (`Filling.`): a fault of the harness. V4 is now predicted by operation
    from the generator's boot files; offline, the prediction equals the counts the pilot measured in
    all eight flow cells (73 commands for 1 step to 716 for 32).
  - V8 failed for the parameter change: the reconciler appended the changed value to the boot file
    behind the old one instead of replacing it. Fixed in the reconciler, with a test (design log).
  - V6 failed twice: the harness read the clock 50 ms after the skill's end, and the server publishes
    every 100 ms. It now waits for the notification and records every state change it times.
  - Four branches were refused (above): set B has 2 and 3.
  - All 19 runs with programs of 10 and 20 composites, and the one with 32 steps added to 5 composites,
    failed reading the program back: FORTE answers a query in one frame whose length field has 16
    bits, cutting the length and the text beyond 64 KiB (`serializeValueString`, a `TForteUInt16`), and
    its connection query takes no filter (`CResource`, `queryConnections`). A program of more than
    about 600 connections cannot be read whole: 511 were read, 655 not.
  - In all runs with 20 composites FORTE dropped 8 to 25 events at boot ("Event queue is full"): its
    event list holds 256 entries, and the module's mode reaches every block at once. That program did
    not run as booted. V10 now checks FORTE's whole log in every run.
  - From Execute, a value cost 2.35 s unavailable (stop 0.11 s, reset 2.12 s, start 0.08 s) against a
    restart's 3.3 s: the guard needs the module stopped, and a stopped module is reset (homed) before
    it is started again. H1.4 is kept as stated, and is likely to fail there. The Idle start was added
    as a second condition, not instead, as a value is changed between orders in practice.
  - The two limits are FORTE's, not the method's, and the reconciler's verification depends on
    reading back: they are reported in the paper. Deploying from the 4diac IDE is not affected (one
    small request per instance, connection and value), nor is monitoring. The evaluation's FORTE
    answers a connection query for a part of the program (patch 0008), and the reader asks part by
    part when the whole does not fit; the instance query has the same limit at about 600 instances,
    beyond the programs here.
- *Third pilot (3 Nov, 22 runs, program sizes 1 and 5, the lab's FORTE).* Every check passed in every
  run but V4, and the one expected failure (32 steps added to 5 composites, 659 connections, not read
  back). V4 failed because the harness counted the reconciler's own reading (queries and READs, 57 to
  120 of them) as commands; the commands that change the program equalled the prediction in all 17
  online runs. The reading is now recorded apart (`reading`). The generator's oracle agreed in every
  run (V1g, V3g, V7g; up to 115 instances, 511 connections and 477 values compared), the module stayed
  in Execute while a composite was added (V9), and FORTE logged no error (V10). Dispensing took
  7.60 to 7.66 s with or without a change (d1 - d0 from -43 to +55 ms in the four paired runs).
- *Fourth pilot (4 Nov, 42 runs, every cell, the evaluation's FORTE).* 41 runs passed every check,
  the programs of 10 and 20 composites included (read back part by part; the oracle compared up to
  342 instances, 1,604 connections and 1,377 values; no event dropped). The phases add up to the
  activation time within 0.2 ms. The one failure was V10: the OPC UA server failed to register with a
  discovery server that closed its connection; such registrations are counted apart now (V10). The
  restart's load time by the subscription (`load_clock_s`) was later than the polled one, which
  showed that a new subscription's first value is stamped when sampled: it is no longer recorded, and
  the clocks above were corrected. One parameter change took 0.35 s against 0.17 s for the same cell
  from Execute, its comparison slowed while another program ran on the PC; the runs that count have
  the PC to themselves.

**A finding on the way (3 Nov): deriving the capabilities does not scale.** Building a module's AAS
with modreg took 17 s for 1 composite, about 77 s for 5, 565 s for 10, and had not finished after
two hours for 20. A profile of the build for 3 composites (22 s) puts most of it in the capability
derivation (`modreg.profile.offers`: the RDF projection and its SPARQL queries in rdflib) and in
`model.build`. The reconciler does not read the derived Capability Description, so Q1 builds every
AAS, for every program size alike, with the derivation switched off (`Describer.derive = False`,
about 10 s each); what Q1 measures is unchanged by it. The derivation itself is a scaling limit of the
tooling, to be fixed after the paper (deriving per changed skill instead of for the whole module, or
indexing the projection), and is noted in [design-log.md](design-log.md).

**Analysis.** Per cell the median and its 95 % interval of T_act and of each phase, N_cmd, bytes, U
and the disturbance d1 - d0. A least-squares fit of T_act on N_cmd and of the read phase on the
program's instances, with R². The ratio of a restart's U to the online U. Each hypothesis is answered
with these numbers. Outliers (beyond three interquartile ranges) are listed and looked at, not removed.

**Outputs.** `cell/eval/results/q1-<when>.jsonl` (one line per run), `cell/eval/q1_analysis.py` writes
`q1-<when>.md` (the tables) and the figure for the paper.

**Results (4 Nov).** 1,260 runs and 5 warm-up runs, 30 per cell in random order, the evaluation's FORTE,
commit `4ab503c` with the tools unchanged; the runs in `cell/eval/results/q1-2026-11-04T0028.jsonl`, the
tables in `q1-2026-11-04T0028.md`, the figure in `docs/paper/cirp/figures/activation.pdf`.

- *Every counted run passed every check*, V1 to V10 and the oracle's (V1g, V3g, V7g; up to 342
  instances, 1,604 connections and 1,377 values compared). In 12 runs the OPC UA server failed to
  register with a discovery server (counted apart, V10).
- *H1.1 holds.* A composite of 32 steps in a program of 20 composites is activated in 0.352 s [0.348,
  0.365], and the slowest of all 780 runs that added a composite took 0.582 s. Applying costs
  0.141 ms per command (R² 0.98), reading and verifying 0.188 ms per connection of the program (R²
  0.84), the two together explain the activation time with R² 0.87. Reading part by part, from about
  600 connections on, adds about 35 ms (the program read in 6 ms at 5 composites, 40 ms at 10).
- *H1.2 holds.* The commands, by operation, are those the generator's boot files call for in 1,020 of
  1,020 runs: 2n + 4 instances created and started, and per step of the dose cycle 9.25 connections
  and 7.5 values; 73 commands (9.8 kB) for 1 step to 716 (99 kB) for 32, the same at every program size.
- *H1.3 holds.* Dispensing, running while a composite was added, took 0.01 % [-0.01, 0.08] longer
  (120 pairs in four cells); the module stayed in Execute throughout (V9, 900 runs).
- *H1.4 holds for a new composite and, for a value, between orders only.* A restart leaves the module
  unavailable 3.31 s; adding a composite online, not at all. A value changed from Execute costs 2.35 to
  2.54 s online, as the guard needs the module stopped and a stopped module is reset (2.13 s, it
  homes), against 3.30 to 3.31 s by a restart (x1.3 to x1.4): H1.4 fails there. Between orders, from
  Idle, it costs 0.02 to 0.21 s online against 3.16 to 3.17 s by a restart (x15 to x133).
- *The restart's parts:* FORTE loads in 0.57 s at every program size (boot files of 246 to 2,875
  lines), the reset takes 2.60 s (online 2.13 s), the start 0.08 s; generating the boot file 4 to 44 ms.
- *Outliers:* 48 of the 1,020 online runs (4.7 %) took 0.2 to 0.25 s longer than their cell's median,
  spread over the session (from run 7 to 1263). The time is lost in the reconciler's comparison, which
  is Python only (32 of them in the verify phase). An offline test found full garbage collections of up
  to 0.41 s in such a process, but none inside a reading in 300, so the cause is not established. They
  are kept; every run stayed below 1 s.

## Q3: does the program stay what its AAS says?

**Question.** When the running program and the module's AAS come apart, does the reconciler notice it,
say what and where, sort it as it should, and bring the program back where it can; and does it never
report a difference where there is none? The two come apart from either side: the program changed
around the reconciler (over the management protocol, as from the IDE or by hand, or by a
reconfiguration that was cut), or the AAS changed by an engineer and not yet applied.

**Hypotheses** (stated before the runs):

- H3.1 Every drift that makes the program differ from what the AAS describes is detected, in every kind.
- H3.2 Where the program is what the AAS describes, no difference is reported (100 clean runs).
- H3.3 Each detected drift is sorted into the class its kind calls for, and the ones the reconciler can
  remove online are removed: afterwards the program is the generator's of the AAS.
- H3.4 A reconfiguration cut after any of its commands is completed by the next one: the new skill then
  runs, and the module still runs what it ran.

**Ground truth.** The drift is made by the harness, so what and where are known. Whether the program
then differs from what the AAS describes at all is the generator's oracle of Q1 (V1g): the program read
from FORTE against the generator's boot file of the module spec the AAS was built from, instances and
types, connections and values, here also every instance running and every skill's OPC UA method open.
An injection after which the oracle finds no difference (a value written that the port had) is counted
with the clean runs.

**The test program.** The filling module with five skills of different shapes: Dispensing as delivered,
DoubleDose (two doses, the tests' skill), BottomUpFilling (a parallel block: the needle rises while the
pump doses), and Q1's synthetic composite of 8 steps, once in sequence (Sequence8) and once in two
parallel branches (Parallel8). The module Idle and free in every run (between orders), so that a value
can be written back (the guard).

**Kinds of drift,** each made on a fresh FORTE started from the test program's boot file:

| Kind | Made by | Population | Expected class |
| --- | --- | --- | --- |
| P1 value | a WRITE of another value (a number + 1, a boolean negated, a string or time changed) to an input the boot file writes | every such input | value |
| P2 connection | a DELETE of a connection | every connection | restart |
| P3 stray instance | a CREATE of an instance of one of the module's block types, unconnected, or with its INIT linked from an INITO of the program | 30 sampled (type, place, linked or not) | restart |
| P4 cut change | Q1's new composite of 4 steps (135 commands) cut after command i: only the first i sent | every i | create (completed) |
| P5 type version | the record of what was built names another hash for an instance's type than FORTE reports | every instance recorded | record |
| A1 value | a step's constant, or a parameter's default or limit, changed in the AAS | every one | value |
| A2 step added | a primitive step without parameters inserted into a skill's sequence | 30 sampled (skill, place, step) | restart |
| A3 flow reordered | two neighbouring steps of a skill's sequence swapped | every pair | restart |
| A4 skill removed | a skill taken out of the AAS | every skill | restart |
| Clean | nothing | 100 runs | none |

The A kinds are made in the module spec and the AAS built from it (as the skill editor saves it), so
that the oracle has the generator's program of the changed AAS.

**Measures,** per run: *detected*, whether the reconciler reports a difference (against the oracle:
true and false positives and negatives), by the reading it makes before every change (its skills, and
block by block the instances, types, connections and run states, from what it reads anyway) and by its
audit (also every value the generator writes, one request each; the equipment's IO addresses, which
the AAS does not describe, against the deployed boot file); *located*, whether a reported line names the drifted element
(its instance, port or skill); *class*, the reported kinds (value, create, restart, record; a confusion
matrix of kind and class); *removed*, for an online class, the reconciler run and the oracle asked again
(the program the generator's of the AAS, read back without a difference), and for a restart class, the
reason it refuses with. For P4 also: the new skill run (V5), and Dispensing run in every tenth.

**Baselines,** on the same runs: a deployment that never reads back (the IDE's) detects no drift by
construction; comparing the AAS with the boot file that was deployed, instead of with the running
program, is computed for every run from the boot files (it sees the A kinds and none of the P kinds).

**Checks in every run:** R1 before the drift, the program is the generator's (V1g) and the reconciler
reads no difference; R2 the drift was made (FORTE accepted the command, or the AAS differs); R3 FORTE
logged no error (as V10). A run failing one is reported, not counted.

**Analysis.** Per kind: detection rate, location rate, class accuracy and removal rate with 95 % Wilson
intervals; the false alarm rate of the clean runs; the confusion matrix; the baseline's detection
rate; every missed drift listed with its element, and looked at.

**The pilots of Q3.**

- *First pilot (4 Nov, 30 runs, three of each kind; `cell/eval/results/q3-2026-11-04T0849.jsonl`).*
  The cut change, the type version and the four AAS kinds were found, sorted and removed or refused as
  expected, and the clean runs raised no alarm. Drift in the program outside the skill model was
  missed: the three values written (the OPC UA root path of a skill's blocks), the three connections
  deleted (the abort wiring, which the reading of a flow does not follow) and two of three stray
  instances (in a skill's container, not linked into its flow). The third stray, linked into the INIT
  chain beside the next skill, misled the reading: it followed one destination of that INITO, the
  stray, lost the rest of the chain, took four complete skills for missing and "completed" them,
  firing INIT into running skills again (285 commands), the stray left in place.
- What was changed (design log, 4 Nov): the INIT chain is followed into every branch; a skill the
  program has all of, running, but that was not read as one is a restart, never completed; the
  reading compares the program block by block with the program the generator builds from the AAS
  (instances, types, connections, run states, with no request more), and an audit also every value.
  Of the 132 values of the filling module's program, the 5 IO addresses are not in the AAS (the
  rebuilt spec has no pins, PWM channels or Modbus registers), on both targets; everything else is,
  so the audit compares those against the module's boot file. R1 now asks the audit for nothing.
- *Second pilot (4 Nov, 30 runs, `cell/eval/results/q3-2026-11-04T0950.jsonl`, commit `5472b1c`).*
  All 30 counted. The audit detected, located and sorted every drift as its kind calls for, and the
  reconciler removed it (P1, P4, A1) or refused it (P2, P3, P5, A2 to A4); no false alarm. The reading
  before a change detected every kind but P1, the values, which only the audit reads (by design).
- *First full run (4 Nov, 1,259 runs, `cell/eval/results/q3-2026-11-04T1004.jsonl`; not counted, it
  led to the changes below).* 1,256 runs passed R1 to R3; no false alarm in 101. P2 to P5 and A2 to A4
  were detected, located and handled in every run. P1: the reading found 42 of 411 values (the ones the
  skills hold), the audit 407; of these, 397 were written back, 8 refused as a restart by design (whether
  a skill is offered, where its results are published: the skill model's structure), and 2 spread to the
  whole program: the module's name and OPC UA root, which the reading took from the program (fixed,
  design log). The audit missed the linear axis's 4 IO addresses, for which the program built from the
  AAS has no value (fixed). A1: 5 of 34 edits lowered a parameter's minimum below what the dosing
  primitive takes; the reconciler refused that AAS as describing a skill the module cannot carry out (the
  check, a case for Q4), so A1 now raises a minimum toward the default, a valid change. Not made: 2
  stray joins, which FORTE refuses to create alone (left out of P3's types), and 1 time value, written
  with a fraction (`T#10001.0ms`) that FORTE's TIME literal does not take (understood in the second
  full run). The runs that count are those of the second full run.
- *Second full run (4 Nov, 1,258 runs in 2 h 36 min, `cell/eval/results/q3-2026-11-04T1252.jsonl`, commit
  `6d4f0d3`, the tools unchanged).* 1,257 runs passed R1 to R3. The one that did not was a drift the
  harness could not make, the module's stop timeout (`T#10000ms`): the time it wrote, `T#11.0s`, came
  from a float, and FORTE refused it (BAD_PARAMS). The harness now writes an integer millisecond (commit
  `3af15c1`), and that drift was made again alone, on the same FORTE
  (`q3-2026-11-04T1252-repeat.jsonl`, commit `a8542a6`); the analysis counts it in place of the first.

**Results (4 Nov).** The second full run with its repeated drift: 1,258 runs, every one counted, the
tables in `cell/eval/results/q3-2026-11-04T1252.md`. No FORTE error in any run; in 8 the OPC UA server
failed to register with a discovery server (counted apart, V10).

- *H3.1 holds.* The audit detected all 1,157 drifts (100 % [99.7, 100]), every kind in every run, and
  located each: a reported line names the instance, port or skill. The reading before a change detected
  every drift of P2 to P5 and A1 to A4, and 42 of the 412 values (P1): those the skills hold, a step's
  constants, a parameter's default and limits, whether a skill is offered and where its results are
  published. The other values, what every block of the module carries (the module's name, the OPC UA
  root and path, the holder) and the IO addresses, only the audit reads, one request each, by design.
- *H3.2 holds.* No difference was reported in the 101 runs where the oracle finds none, the 100 clean
  runs and the change cut after its last command: 0 of 101 (0 % [0, 3.7]).
- *H3.3 holds.* Every drift was sorted into the class its kind calls for. 572 drifts of an online class
  were removed, 404 of the 412 values written in the program, every cut change (135) and every value
  changed in the AAS (33), and afterwards the oracle found the program the generator's of the AAS each
  time. The other 8 values are what the skill model reads as a skill's interface: whether the skill
  offers its OPC UA methods (`Control.Methods`, 5) and where its results are published
  (`PubResults.ID`, 3). Their blocks take them at initialisation, so the audit also reports the skill as
  differing, a restart, and the reconciler refuses, by design. Every drift of a restart or record class
  (P2, P3, P5, A2 to A4; 577) was refused, as not possible online.
- *H3.4 holds.* A reconfiguration cut after any of its 135 commands (i = 0 to 134) was completed by the
  next one: the new skill then ran in all 135, and Dispensing still ran in all 14 of every tenth. Cut
  after its last command, the program was complete and nothing was left to do.
- *The baseline,* the AAS compared with the boot file that was deployed instead of with the running
  program, detected the 220 drifts where the AAS is ahead of the program (P4, A1 to A4) and none of the
  937 made in the program (P1 to P3, P5).

## Q4: are the skills right for the product?

**Question.** Before a skill is built, the method checks its flow against the conditions of the module's
capabilities and matches what it reaches against the product's requirement (section 3.4 of the paper).
Does that check reject the flows that would spoil a product and pass the ones that would not; and does
matching answer offered, offered after a reconfiguration, or not offered as the module can in fact
do it, with a planned skill that makes the product right the first time?

**The oracle: a process model of the filling station** (`cell/eval/process_model.py`). It runs a flow
in time steps of 10 ms: the needle's tip moving at the axis's speed, the pump dosing at its flow rate,
the scale, each branch of a parallel block at once, one holder per equipment item. It knows the
containers and the physics, and **none of the AAS's capability conditions**: no fill position, no
rest state, no pre- or postcondition, no invariant. It shares with the AAS only the hardware's ranges
(the axis's travel 0 to 60 mm, the pump's dose 0.5 to 10 mL and flow rate 0.1 to 5 mL/s, as the
primitives' parameter limits state them), so that what it judges is the flow, not the hardware.
A product is right when all of these hold:

| | Rule of the oracle |
| --- | --- |
| O1 | Every step can be carried out: a target within the axis's travel, a dose and rate within the pump's range, one holder per item (a second branch on the same item is refused, and the run fails) |
| O2 | No spill: liquid leaves the needle only while its tip is inside the container (below the rim) |
| O3 | No crash: the tip never goes within 1 mm of the container's bottom |
| O4 | No overflow: the content stays within the container's capacity |
| O5 | For a product to be filled from the bottom (prefilled syringe), no foam: while the pump doses, the tip is never more than 2 mm above the liquid's surface |
| O6 | The volume: the content equals the required volume within the product's AbsoluteFillError (0.05 mL) |
| O7 | Where the product requires its weight: a weighing after the last dose, on a tared scale, with the needle out of the container, the axis still and the pump off throughout |
| O8 | The container can leave: at the end the tip is out of the container |

The containers stand in the shuttle's nest with their base 30 mm above the table; the tip at home is
100 mm above it. A vial 2R is 35 mm high (rim 35 mm down the stroke, 4 mL to the brim, inner diameter
14 mm), a 10R 45 mm (13.5 mL, 22 mm), a 20R 55 mm (26 mL, 28 mm). A prefilled syringe of 1 mL (long)
stands deeper, its barrel's bottom 59 mm down the stroke, its rim 4 mm, its inner diameter 6.35 mm
(1.0 mL). Weighing is right only with the needle out and still, because a scale reads a load with
nothing touching it; the module's condition (needle at home) is stricter, and where the two differ the
oracle decides.

### Q4a: the check, on mutants of the module's skills

**Population.** Every single mutant of three skills, each run for the product it is written for:
Dispensing (1.0 mL into a vial 2R) and DoubleDose (2 × 0.5 mL into a vial 2R), both delivered or
tested, and BottomUpFilling (1.0 mL into the prefilled syringe), written in the skill editor.

| Operator | Mutants |
| --- | --- |
| M1 delete | each step deleted |
| M2 swap | each two neighbouring steps swapped (in a sequence or a branch) |
| M3 duplicate | each step repeated right after itself |
| M4 insert | each of Home, Tare, Weigh, MoveAxis to 0, 20, 40 and 58 mm, and Dispense of 1 mL inserted at each place |
| M5 value | each numeric constant of a step set to each quarter point of its range (0, 25, 50, 75, 100 %) |
| M6 beyond | each numeric constant set 10 % of its range below its minimum and above its maximum |
| M7 parallel | each two neighbouring steps of a sequence made a parallel block |

A mutant equal to its original (the same flow after the change) is left out. Step names are kept unique.

**What is checked.** The method's check, as the paper describes it: (1) the module spec takes the
skill (steps name the module's primitives, every bound value within the step's limits, results from
steps that exist); (2) `modplan.check` on the domain read from the module's AAS finds no condition
that fails; (3) what the flow leaves (`modplan.check.simulate`) is what the product requires: the
volume, and where required the weight. A mutant is *rejected* if any of them reports something.

**Baselines,** on the same mutants:

- *Structure only,* what the 4diac IDE checks: the types exist and the connections join pins of the same
  type. A mutant of the module's primitives always passes, except where a result names a step that is
  gone.
- *Hand-written sequence rules,* as a tool expert writes them for a workflow engine
  [lindorfer2019user], written here before any run from the module's documentation: R1 a Dispense
  follows a MoveAxis of 40 mm or more, with no move up in between; R2 a Weigh follows a Home or a
  MoveAxis to 0, with no move down in between, and is in no parallel block; R3 the flow ends with a Home
  or a MoveAxis to 0 after its last move down; R4 every value within its step's limits; R5 no two
  branches on the same equipment item; R6 at least one Dispense, and a Weigh after the last one when
  the skill has a weight result.

**Measures.** Against the oracle (wrong: a product not right or a run that fails): true and false
positives and negatives, precision and recall with 95 % Wilson intervals, per method and per
operator; every disagreement listed with the oracle's rule and the check's finding, and looked at.
For a rejected mutant also whether a finding names the mutated step.

**Hypotheses.** H4.1 The check's recall is 100 %: no mutant that spoils the product passes. H4.2 Its
precision is at least 90 %: what it rejects in excess comes from the module's conditions being stricter
than the physics (the fill position, the needle at home to weigh), and every such case is listed.
H4.3 Structure alone finds almost nothing; the hand-written rules reach the check's results only where
a rule was written for the case (none for the needle rising while the pump doses).

### Q4b: matching and planning, on products and module variants

**Products,** 26: a vial 2R of 0.25, 0.5, 1 or 2 mL; a 10R of 2, 5 or 10 mL; a 20R of 15, 20 or 25 mL;
a prefilled syringe of 0.25, 0.5 or 1 mL; each with its weight required or not. A vial asks for
Filling, the syringe for BottomUpFilling (the vocabulary's narrower capability).

**Module variants,** 4, each built by modreg from a changed spec: *full* (as delivered); *no scale*
(no Tare and Weigh, Dispensing without Weigh); *small pump* (a dose of 5 mL at most); *raised*
(the station 5 mm higher: every container 5 mm further down the stroke, the fill position at 45 mm).
On each, Dispensing is built and BottomUpFilling described (written, not built), with the values the
variant needs (NeedleDown 45 mm on the raised one, BottomUpFilling's start at 58 mm or the axis's end).

**The method's answer.** *Offered* when a built skill's offered capability (the module's derived
Capability Description) has the meaning asked for and covers the product's properties, and gives the
weight where it is required; *after a reconfiguration* when a described skill's does, or else the
planner finds a plan (`modplan.plan`, with FillWeight as a result where the weight is required);
*not offered* otherwise.

**The truth, from the oracle.** *Offered* when a built skill, started with the product's volume within
its limits, makes the product right. Otherwise *after a reconfiguration* when the module can do it at
all: a witness flow, built from the product and the hardware alone (into the container, as many doses
as the pump needs, from the bottom rising with the liquid for the syringe at each flow rate of a grid,
out, weigh where required), makes the product right in the oracle. Else *not offered*.

**Measures.** A confusion matrix of answer and truth with the accuracy and its Wilson interval; for
every answer after a reconfiguration by planning, the plan's time (median of 5) and whether the
planned skill, run in the oracle, makes the product right the first time; every disagreement listed
and looked at.

**Hypotheses.** H4.4 The answer equals the truth in at least 90 % of the cases, and the method never
offers what the module cannot do (no *offered* or *after a reconfiguration* where the truth is *not
offered*). H4.5 Every planned skill makes the product right the first time. H4.6 Planning takes less
than 1 s on the PC.

**Outputs.** `cell/eval/q4.py` writes `cell/eval/results/q4-<when>.jsonl` (a line per mutant and per
case), `cell/eval/q4_analysis.py` the tables (`q4-<when>.md`) and the figure. Q4 runs no FORTE: the
check and the match come before anything is built, and are deterministic, so each mutant and case is
run once (the plan's time five times).

**Results (5 Nov).** `cell/eval/results/q4-2026-11-05T2346.jsonl`, commit `2ed3c87` with the tools
unchanged; the tables in `q4-2026-11-05T2346.md`, the figures `docs/paper/cirp/figures/check.pdf` and
`match.pdf`. The first runs, before the harness was committed, gave the same numbers and are not kept.

- *Q4a, the population:* 245 distinct mutants (Dispensing 62, DoubleDose 84, BottomUpFilling 99), of
  which the oracle finds 136 spoil the product or cannot be carried out, 109 not.
- *H4.1 fails.* The check rejects 117 of the 136 (recall 86 % [79, 91]): every deletion, swap, value
  beyond its limits and pair made parallel, and every extra dose (by the volume it leaves). It misses
  19: a Tare inserted after the needle went in or after a dose (13; Taring has no condition in the
  AAS, so nothing says the scale is tared with the empty container), and six of BottomUpFilling's where
  the needle starts too high, or the dose is too slow or too late for the rise (foam, 4) or the needle goes to the
  barrel's bottom (crash, 2). Foam and the container's geometry are in no condition: the narrowing of
  BottomUpFilling lies in how the skill moves (vocabulary 0.6).
- *H4.2 fails.* Of the 143 rejected, 117 spoil the product (precision 82 % [75, 87]). The 26 others are
  as expected stricter than the physics: Weigh needs the needle at home where out of the container is
  enough (14), the module's rest at the end (2), the one holder per item (1), and nine of
  BottomUpFilling's where the needle rises past the fill position after the dose is in: the check takes
  a move's ends, not its speed.
- *H4.3 holds.* Structure alone rejects 3 (2 % [1, 6]), the ones whose result names a deleted Weigh.
  The hand-written rules reject 102 (recall 75 % [67, 82], precision 86 % [78, 91]): all of them the
  check rejects too, and they miss 15 the check catches, the extra doses (no rule about the volume) and a
  dose made parallel to Home. A rule more would catch those; the check needs none, as the volume comes
  from the capabilities' effects.
- *Q4b, H4.4 holds in part.* The answer equals the truth in 100 of 104 cases (96 % [91, 98]): 40
  offered, 33 after a reconfiguration, 27 not offered. Nothing the module cannot do is offered by a
  built skill. The 4 disagreements are the syringe on the raised station: BottomUpFilling, described,
  covers it, but the axis cannot reach the barrel's bottom there (60 mm of travel, the bottom at 64), so
  the needle starts 4 mm above the liquid and it foams. The described skill was not checked against
  the product; the check of Q4a would not see it either (foam is in no condition).
- *H4.5 holds.* All 23 planned skills (15 to 25 mL on all variants, 10 mL on the small pump; two or
  three doses) make the product right the first time in the oracle (100 % [86, 100]).
- *H4.6 holds.* Planning takes 0.72 ms (median), 0.98 ms at most.
