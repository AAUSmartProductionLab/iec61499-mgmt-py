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
