# Building skills and equipment

How to give a module a new skill, a new skill primitive or a new piece of equipment: in the module
spec (the usual way), or by hand in the 4diac IDE. With one full example, what changes between one
primitive and another, and how to export the types and rebuild FORTE when a primitive or a piece of
equipment is new. Written on 28 Oct 2026 for the lab's engineers and students.

What the blocks of the filling program are and how a call travels through them is in
[filling-program.md](filling-program.md); the rules every module keeps in
[module-rules.md](module-rules.md). Read those first if the names below are new.

## 1. Which kind of change is it?

FORTE, the runtime on the Pi, can only run **block types it was built with**: the types are compiled
into the FORTE program. What it can do at any time, even while the module runs, is create **blocks
of those types**, wire them, and set their values. That decides what a change costs:

| You want | What it is | What changes | Rebuild FORTE? | While running? |
| --- | --- | --- | --- | --- |
| A new sequence of things the module can already do (fill twice, fill and weigh twice) | A **module level skill**, like Dispensing | New blocks and wires of existing types | **No** | Yes (`modsync push`, or from the AAS) |
| A different constant (the fill position, the flow rate) or default | A **parameter value** | One value | No | Yes |
| A new action of existing equipment (prime the pump, home slowly) | A **skill primitive**, like Home or Dispense | New types `SK_<Skill>` and `SL_<Skill>` | **Yes** | No: a new FORTE and a new program |
| Different behaviour of a primitive (another end condition, timeout, command) | A changed skill primitive | Its types | **Yes** | No |
| New hardware (a valve, a second axis, a sensor) or other pins | A **piece of equipment** | New types `EQ_`, `EL_`, `EV_`, `EC_<Item>` | **Yes** | No |
| Another pin for existing equipment (GPIO 22 instead of 27) | An **address** | One value of the equipment block | No | No: a new program (the pin is set up at start) |

A changed comment or description never needs a rebuild: comments are not part of a type's hash.

## 2. A module level skill

A module level skill has no type of its own: it is a **subapplication** of blocks of library types
and of the module's primitives. So it needs no new FORTE.

### 2.1 In the module spec (the usual way)

Add it under `composites:` in the module spec (`cell/modules/filling.yaml`):

```yaml
composites:
  DoubleDose:
    description: Needle down, two doses, needle up, weigh
    parameters:
      Dose: {unit: mL, minimum: 0.5, maximum: 10.0, default: 0.5, description: One dose}
    execute:
      - {MoveAxis: {Position: 40.0}, as: NeedleDown}     # a step, named NeedleDown, with a constant
      - {Dispense: {Volume: Dose, FlowRate: 1.0}}        # Volume from the skill's parameter Dose
      - {Dispense: {Volume: Dose, FlowRate: 1.0}}        # the same primitive again (named Dispense_2)
      - {MoveAxis: {Position: 0.0}, as: NeedleUp}
      - Weigh
    stop: [Home]                                         # what runs when the skill is stopped
    results: {Weight: Weigh.Weight}                      # a result of a step is the skill's result
```

- `execute` is the steps in order. A step is a primitive's name, or `{<Primitive>: {<parameter>:
  <value or the skill's parameter>}, as: <name>}`. Steps may also run side by side (`parallel`) or
  depend on a decision (`if`); see [module-rules.md](module-rules.md), section 3.
- A constant has to lie within the limits of the primitive's parameter; the generator checks it.
- `stop` is optional; without it a stopped skill only ends.

Then:

```powershell
python -m modgen                                                     # regenerate the 4diac projects
python -m modsync push cell/modules/filling.yaml --target pi --dry-run   # what would change on the Pi
python -m modsync push cell/modules/filling.yaml --target pi             # create it in the running program
```

`modsync push` creates the new blocks and wires in the running FORTE, links the skill to the end of
the start-up chain, starts it once, verifies what runs and adds it to the Pi's boot file, so it is
there after a restart too. The module may be in use meanwhile. It can also be done from the AAS:
describe the skill in the skill editor, then `python -m modsync reconfigure`.

### 2.2 By hand in the 4diac IDE

The same skill, block by block. Do it this way only to learn the structure, or for a module that is
not generated: the next `python -m modgen` rewrites the program from the spec and a hand-made skill
that is not in the spec is gone.

1. Open the project in the 4diac IDE (*File > Import > Existing Projects*, `cell/control/FillingModule`),
   then the system `FillingModule.sys` and the application `Filling_pi`.
2. Create a subapplication named `DoubleDose` with one event input `INIT` and one event output
   `INITO`.
3. Inside it, create these blocks (from the palette; the types are in the project's library) and
   set their values:

   | Block | Type | Values |
   | --- | --- | --- |
   | `Control` | `modlib::SKILL_Core` | `Module "Filling"`, `UaRoot "/Objects/Filling"`, `UaPath "/Skills/DoubleDose"`, `UaEnable TRUE`, `Methods TRUE`, `Holder "DoubleDose"`, `ReleaseAll TRUE` |
   | `UaStart` | `iec61499::net::SERVER_2_2` (2 answers; inputs: the session and 1 parameter) | `QI TRUE` |
   | `Dose` | `modlib::SKILL_Param_LREAL` | `Default 0.5`, `Lower 0.5`, `Upper 10.0` |
   | `PubParams` | `iec61499::net::PUBLISH_1` | `QI TRUE`, `ID "opc_ua[WRITE;/Objects/Filling/Skills/DoubleDose/Parameters/Dose]"` |
   | `PubResults` | `iec61499::net::PUBLISH_1` | `QI TRUE`, `ID "opc_ua[WRITE;/Objects/Filling/Skills/DoubleDose/Results/Weight]"` |
   | `Execute` | subapplication | events in `INIT`, `START`, `HALT`, `ABORT`, `RESET`; out `INITO`, `DONE`, `FAILED`; data in `Dose` (LREAL); out `ErrorID` (UINT), `Weight` (LREAL) |
   | `Stop` | subapplication | events as `Execute`; data out `ErrorID` |

4. Inside `Execute`, one block per step, all with `Module "Filling"`, `UaRoot "/Objects/Filling"`,
   `UaEnable TRUE`, `Methods FALSE`, `Holder "DoubleDose"`, `ReleaseAfter FALSE`, and
   `UaPath "/Skills/DoubleDose/Execute/<block>"`:

   | Block | Type | Its own values |
   | --- | --- | --- |
   | `NeedleDown` | `filling::SK_MoveAxis` | `Position 40.0` |
   | `Dispense` | `filling::SK_Dispense` | `FlowRate 1.0` |
   | `Dispense_2` | `filling::SK_Dispense` | `FlowRate 1.0` |
   | `NeedleUp` | `filling::SK_MoveAxis` | `Position 0.0` |
   | `Weigh` | `filling::SK_Weigh` | |
   | `Fail1` to `Fail4` | `modlib::SKILL_FailMerge` | |

   Inside `Stop`: `Home` (`filling::SK_Home`, the same values, `UaPath
   "/Skills/DoubleDose/Stopping/Home"`).
5. Wire `Execute` (events, then data):
   - the chain: `START → NeedleDown.START`, `NeedleDown.SUCCESS → Dispense.START`,
     `Dispense.SUCCESS → Dispense_2.START`, `Dispense_2.SUCCESS → NeedleUp.START`,
     `NeedleUp.SUCCESS → Weigh.START`, `Weigh.SUCCESS → DONE`;
   - `HALT`, `ABORT` and `RESET` to the same input of every step;
   - failures, two at a time: `NeedleDown.FAILURE → Fail1.FAIL_1`, `Dispense.FAILURE →
     Fail1.FAIL_2`, `Fail1.FAIL → Fail2.FAIL_1`, `Dispense_2.FAILURE → Fail2.FAIL_2`,
     `Fail2.FAIL → Fail3.FAIL_1`, `NeedleUp.FAILURE → Fail3.FAIL_2`, `Fail3.FAIL → Fail4.FAIL_1`,
     `Weigh.FAILURE → Fail4.FAIL_2`, `Fail4.FAIL → FAILED`; and the same for the error codes
     (`<step>.ErrorID → Fail<i>.Error1` or `Error2`, `Fail<i>.Error → Fail<i+1>.Error1`,
     `Fail4.Error → ErrorID`);
   - start-up: `INIT → NeedleDown.INIT`, each `INITO` to the next step's `INIT`, `Weigh.INITO → INITO`;
   - data: `Dose → Dispense.Volume`, `Dose → Dispense_2.Volume`, `Weigh.R_Weight → Weight`.
6. Wire `Stop`: `START → Home.START`, `Home.SUCCESS → DONE`, `Home.FAILURE → FAILED`,
   `Home.ErrorID → ErrorID`, `HALT`/`ABORT`/`RESET` to Home's, `INIT → Home.INIT`,
   `Home.INITO → INITO`.
7. Wire the skill itself:
   - the Start method: `Control.StartMethodId → UaStart.ID`, `UaStart.RD_1 → Control.Session`,
     `Control.START_RSP → UaStart.RSP`, `Control.Accepted → UaStart.SD_1`,
     `Control.StartError → UaStart.SD_2`;
   - the parameter: `UaStart.IND → Dose.CHECK`, `UaStart.RD_2 → Dose.Requested`,
     `Control.CalledByClient → Dose.CalledByClient`, `Dose.CHECKED → Control.START_REQ`,
     `Dose.AllInRange → Control.ParamsInRange`, `Control.RUN → Dose.LATCH`,
     `Dose.LATCHED → PubParams.REQ`, `Dose.LATCHED → Execute.START`, `Dose.Value → PubParams.SD_1`,
     `Dose.Value → Execute.Dose`, `PubParams.INITO → PubParams.REQ` (publishes the default once);
   - the run: `Control.HALT_SEQ → Execute.HALT`, `Control.ABORT_SEQ → Execute.ABORT`,
     `Control.RESET_SEQ → Execute.RESET`, `Execute.DONE → Control.EXECUTE_DONE`,
     `Execute.FAILED → Control.EXECUTE_FAILED`, `Execute.ErrorID → Control.ExecuteError`;
   - the result: `Execute.DONE → PubResults.REQ`, `Execute.Weight → PubResults.SD_1`;
   - stopping: `Control.RUN_STOPPING → Stop.START`, `Control.ABORT_SEQ → Stop.ABORT`,
     `Control.RESET_SEQ → Stop.RESET`, `Stop.DONE → Control.STOPPING_DONE`,
     `Stop.FAILED → Control.STOPPING_DONE`;
   - start-up: `INIT → Control.INIT → UaStart → Dose → PubParams → PubResults → Execute → Stop →
     INITO` (each `INITO` to the next `INIT`).
8. In the application, append the skill to the start-up chain: `Dispensing.INITO →
   DoubleDose.INIT` (the last block of the chain to the new one).
9. Map the subapplication to `FORTE_PI.RES` and deploy, either from the IDE (*Deploy* on the device:
   it replaces the whole program) or with `python deploy/pi.py module`, which deploys the application
   from the `.sys` file.

A skill without parameters has `UaStart` of type `SERVER_2_1`, `UaStart.IND → Control.START_REQ`
and `Control.RUN → Execute.START`; with more parameters, one parameter block each, checked and
latched one after the other (`CHECKED → next CHECK`, `AllInRange → next PreviousInRange`,
`LATCHED → next LATCH`).

### 2.3 Calling it

```
Occupation/Occupy("me")       → [TRUE, 0]
Module/Reset("me"), then Module/Start("me")      (Stopped → Resetting → Idle → Execute)
Skills/DoubleDose/Start("me", 1.5)               → [TRUE, 0]: two doses of 1.5 mL
Skills/DoubleDose/State       1 Running ... 3 Succeeded ... 0 Idle
Skills/DoubleDose/Results/Weight
```

## 3. A skill primitive

A primitive is **one command to one piece of equipment, until a sensor says it is done or a time has
passed**. Every primitive has the same skeleton (`SK_<Skill>`, a composite); only its logic
(`SL_<Skill>`, a basic block) and a few sizes differ.

### 3.1 In the module spec

```yaml
skills:
  Prime:
    description: Run the pump for a while to fill its tube before the first dose
    equipment: Pump              # the piece of equipment it commands
    command: Run                 # one of that equipment's commands
    parameters:
      Duration: {unit: s, minimum: 0.5, maximum: 30.0, default: 5.0, description: How long to run}
    after: Duration              # ends after this many seconds (a number or an expression)
```

| Field | Means |
| --- | --- |
| `equipment`, `command` | What it commands: a command from the equipment's `commands` |
| `arg` | The command's argument, an expression over the parameters (a position, a speed) |
| `move_to: <parameter>` | Short for: the command `MoveTo` with that parameter, requiring `Homed`, until the axis is at it (only on equipment with a `position`) |
| `postcondition` | Ends when this holds: an expression over the equipment's inputs and the parameters (`AtHome`, `Weight > 1.9`) |
| `after` | Or ends after a time: seconds, or an expression (`Volume / FlowRate`). Exactly one of `postcondition` and `after` |
| `precondition` | Must hold to start (default TRUE): otherwise error 1 |
| `invariant` | Must hold while it runs (default TRUE): otherwise it stops with error 2 |
| `timeout` | For a skill a sensor ends: fails with error 3 after this long (`30s`; default `10s`) |
| `stop` | The command sent when it ends (default: the equipment's safe command, all off) |
| `parameters` | Name, unit, limits, default; `meaning` says what it is in the lab's vocabulary |
| `results` | Result name to an equipment input: its value when the skill ends (`{Weight: Weight}`) |
| `offered` | `false`: no instance of its own, only usable as a step (default `true`) |

Then regenerate, rebuild FORTE (section 5), and deploy the new program.

### 3.2 What the generator makes, and what differs between primitives

`SK_<Skill>` always holds the same blocks (see [filling-program.md](filling-program.md), section 6):
`Control` (`SKILL_Core`), `UaStart`, one `Par_<p>` per parameter, `PubParams`, `Logic`
(`SL_<Skill>`), `EqState`, `EqView` (`EV_<Item>`), `WaitT`, `Driver` (`EC_<Item>`), `PhaseT`,
`EqCmd`, `Timer`, and `PubResults` if it has results. What a new primitive changes:

| In the spec | Changes in the blocks |
| --- | --- |
| Its parameters | The number of `Par_<p>` blocks; the size of `UaStart` (`SERVER_2_<1 + parameters>`) and of `PubParams` (`PUBLISH_<parameters>`); one input each on `SK_` and `SL_` |
| Its results | `R_<r>` outputs on `SL_`, and `PubResults` |
| Its equipment | Which `EV_<Item>` and `EC_<Item>` it uses; the sizes of `EqState` (one value per input, and the holder) and `EqCmd` (the holder, release, and one value per output); the channels it uses (`loc[<Module>/<Item>/...]`) |
| `command`, `arg`, `stop` | The command number `Logic` hands to `Driver`, its argument, and the closing command |
| `precondition` | `SL_`: the condition under which a start is refused (state Reject) |
| `postcondition` | `SL_`: the condition that ends it (Running → Done) and lets it succeed at once if it already holds (AlreadyDone); its `Timeout` input and the timeout transition (TimedOut) |
| `after` | `SL_`: the time it runs for, computed from the parameters (`TimerDT`), and Running → Done when the timer ends |
| `invariant` | `SL_`: the condition whose loss stops it (Unsafe) |

Everything else in `SL_` is the same in every primitive: waiting for the equipment (WaitFree, then
Busy), noticing that the equipment was taken away (Lost), halting and aborting, and the closing
command. The five filling primitives side by side:

| | `Home` | `MoveAxis` | `Dispense` | `Tare` | `Weigh` |
| --- | --- | --- | --- | --- | --- |
| Equipment, command | LinearAxis, `Up` | LinearAxis, `MoveTo(Position)` | Pump, `Run` | Scale, `Tare` | Scale, `Measure` |
| Starts only if | – | `Homed` | – | – | – |
| Ends when | `AtHome` (switch) | not `Moving` and at `Position` | after `Volume / FlowRate` s | after 2 s | after 0.2 s |
| Already done at start possible | yes (at the switch) | yes (already there) | no | no | no |
| Timeout | 60 s | 30 s | – | – | – |
| Parameters | – | Position | Volume, FlowRate | – | – |
| Results | – | – | – | – | Weight |
| `UaStart`, `PubParams` | `SERVER_2_1`, none | `SERVER_2_2`, `PUBLISH_1` | `SERVER_2_3`, `PUBLISH_2` | `SERVER_2_1`, none | `SERVER_2_1`, none; `PubResults` |

### 3.3 By hand in the 4diac IDE

Copy a primitive of the same kind (one ended by a sensor or one ended by a time) and change only
what the table in 3.2 lists: make `SK_Prime` from `SK_Dispense` (*Save As* in the type's editor),
make `SL_Prime` from `SL_Dispense`, and in `SL_Prime` change the inputs (`Duration` instead of
`Volume` and `FlowRate`), the algorithm that computes `TimerDT` (`Duration` seconds), and the
`IdParams` text (`.../Parameters/Duration`). In `SK_Prime` keep one parameter block, use
`SERVER_2_2` and `PUBLISH_1`, and wire `Par_Duration` as `Par_Volume` was. Keep the block names: the
tools find a skill's parts by them. Then export and rebuild FORTE (section 5).

## 4. A piece of equipment

An equipment block is the only block that touches its pins. It does not know what they mean: the
skills say which outputs to switch, through the command table.

### 4.1 In the module spec

A pinch valve on GPIO 22 that is open while its output is on:

```yaml
equipment:
  Valve:
    kind: PinchValve
    description: Pinch valve on the filling tube, open while powered
    outputs:
      Open: {modbus: c4, gpio: 22}          # the PC target's Modbus coil, the Pi's GPIO line
    commands:
      Stop: {}                               # the safe command: everything off (closed)
      Open: [Open]                           # switch the output Open on
```

| Field | Means |
| --- | --- |
| `kind` | What kind of equipment it is (shared by every module that has one: its component AAS says so) |
| `inputs` | Sensors: `type` BOOL or LREAL, `gpio: {line, bias, active_low}` (digital), `modbus` (`d<n>` or `i<n>`), `scale`, `unit`, `sim` (the value when simulated) |
| `outputs` | Actuators: `type`, `gpio` (digital), `pwm: {channel, period_ns}` (analog, e.g. step pulses), `modbus` (`c<n>` or `h<n>`), `gain`, `bias`, `minimum`, `maximum`, `unit` |
| `commands` | Each command: the outputs it switches on (`[Open]`), their values (`{Enable: true, Step: 50}`), or timed phases (`[{Retract: true, for: 3s}, {}]`). The first is the safe one |
| `position` | For an axis without an encoder: `speed`, `increase` and `decrease` commands, the `home` switch, `minimum`, `maximum`; it then keeps `ActualPosition`, `Homed`, `Moving` and has `MoveTo` |
| `location` | Where it is in the module (for its coordinates in the AAS) |
| `sim` | How the simulator (`cell/sim/module_sim.py`) moves it on the PC |

And a primitive that uses it:

```yaml
skills:
  OpenValve:
    description: Open the valve for a while
    equipment: Valve
    command: Open
    parameters:
      Duration: {unit: s, minimum: 0.1, maximum: 10.0, default: 1.0}
    after: Duration
```

The generator makes `EQ_Valve` (the block in the application), `EL_Valve` (its logic), `EV_Valve`
(its state for the skills) and `EC_Valve` (its command table, used inside the skills). New types:
rebuild FORTE (section 5).

### 4.2 What is inside, if you build it by hand

Copy the equipment block that is most like the new one (`EQ_Pump` has no pins, `EQ_Scale` one
input, `EQ_LinearAxis` outputs, an input and a position) and keep its structure:

- `Logic` (`EL_<Item>`): its inputs `C_<output>` (what the holder sends), outputs `O_<output>` (what
  goes to the pins), one holder at a time, break before make, all off on release or abort;
- `SubCmd` (`SUBSCRIBE_n`, n = 2 + one per output value) on `loc[<Module>/<Item>/cmd]`,
  `SubRelease` on `loc[<Module>/release]`, `PubState` (`PUBLISH_n`, one per input and the holder)
  on `loc[<Module>/<Item>/state]`, `PubUa` for the inputs over OPC UA;
- `Cycle` (reads the inputs), `Mode` (the module state), and `MoveT` on an axis with a position
  (the time a move takes at its speed);
- one IO block per pin, `In_<input>` (`IO_DI` or `IO_AI`) or `Out_<output>` (`IO_DO` or `IO_AO`),
  whose `Address` is the block's input `<pin>_Address`;
- and `EC_<Item>` (the command table: one number per command, the output values per phase) and
  `EV_<Item>` (the state unpacked) for the skills.

The generated types are the reference: a hand-made one that differs is not read back by the tools
(`modsync`) as the rules say.

## 5. Exporting the types and rebuilding FORTE

Needed after a new or changed **primitive** or **equipment** (new block types). **Not needed for a
module level skill** like Dispensing or DoubleDose, a parameter value, or a comment: those use the
types FORTE already has.

Why: FORTE is a compiled program. Each block type becomes C++ code (the 4diac IDE writes it, the
"export"), which is compiled into FORTE together with the library. FORTE also checks every block it
is asked to create against the type's hash, and refuses a type it does not know or whose hash differs.

What is needed on the PC: the 4diac IDE 3.3 (`runtime/validate.ps1` names its path), the 4diac FORTE
Build Environment in `C:\4diac-fbe` (it brings the compilers, also the cross compiler for the Pi),
and PowerShell.

1. **Regenerate** the projects from the spec:

   ```powershell
   python -m modgen
   ```

   Open the project in the IDE if you want to look at the new types; nothing has to be saved there.
2. **Export and build FORTE for the PC** (to test with the simulator):

   ```powershell
   runtime/build-modules.ps1
   ```

   This runs `modgen`, has the 4diac IDE export the library and every module's types as C++ (headless,
   `runtime/validate.ps1`: it also checks that the IDE loads every type and the system), and builds one
   FORTE with all modules (`runtime/build-runtime.ps1`: FORTE 3.3.0 with the repository's patches, in
   the build environment). It prints where the new `forte.exe` is.
3. **Test on the PC**: start the simulator and that FORTE, deploy the PC application and run the
   tests (`cell/tests`).
4. **Build FORTE for the Pi** (aarch64, cross-compiled; the exports of step 2 are reused):

   ```powershell
   runtime/build-modules.ps1 -Config pi/modules-pi -SkipValidate
   runtime/package-runtime.ps1          # puts it into runtime/bin/forte-aarch64 (stripped) with its checksum
   ```

   Commit `runtime/bin/forte-aarch64` and `runtime/bin/forte-aarch64.sha256`: a Pi can only run a
   program whose types its FORTE was built with.
5. **Install it on the Pi**, with someone at the module (the program starts and may move the axis):

   ```powershell
   python deploy/pi.py install          # copies FORTE to ~/forte, rebuilds and restarts its container
   python deploy/pi.py module           # deploys the module's program (Filling_pi from the .sys)
   python deploy/pi.py status           # is it running?
   ```

6. **Check** that the module is what its spec and its AAS describe:

   ```powershell
   python -m modsync pull --spec cell/modules/filling.yaml --target pi
   python -m modsync verify aas --host 192.168.0.203
   ```

The export can also be done by hand in the 4diac IDE (*File > Export > 4diac FORTE*, choosing the
types and a folder); the scripts do the same for every type, and the build takes the exported
folders from `runtime/.cache/modules`.
