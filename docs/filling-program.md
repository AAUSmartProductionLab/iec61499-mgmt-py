# The filling program, block by block

What every function block of the filling module's IEC 61499 program does, in plain words: what a
client can call over OPC UA, which blocks a call reaches, how a command ends up on the Raspberry Pi's
pins, and where the values the module shows come from. Written on 28 Oct 2026 for anyone who opens
the program in the 4diac IDE (`cell/control/FillingModule`) or operates the module.

The same descriptions are in the program itself: every block type and every block instance has a
comment (in the IDE: hover over a block, or select it and look at *Properties > Comment*). They are
written by the generator (`iec61499-skill-lib/modgen/explain.py`), so they stay when the program is
regenerated, and they do not change a type's hash: a program with new comments runs on the FORTE
that is already on the Pi.

How to build a new skill or a new piece of equipment is in [building-skills.md](building-skills.md).
The rules every module follows are in [module-rules.md](module-rules.md); the hardware in
[modules.md](modules.md).

## 1. The whole program in one picture

The program runs in FORTE (the IEC 61499 runtime) on the filling module's Raspberry Pi 5
(192.168.0.203). FORTE also runs an OPC UA server, `opc.tcp://192.168.0.203:4840`; everything of
the module is below `/Objects/Filling` there.

```
 OPC UA client (HMI, modlink, an agent)
        │  calls a method (Occupy, Start, ...) / reads a variable (State, Weight, ...)
        ▼
 ┌────────────────────────────── FORTE on the Pi ─────────────────────────────────┐
 │  SERVER blocks: one per OPC UA method; PUBLISH blocks: one per group of variables │
 │        │                                                                         │
 │  Occupation ── who may command            Module ── PackML state, procedures     │
 │        │ owner                                   │ state                         │
 │        ▼  (local channels, not drawn)            ▼                               │
 │  Skills: Dispensing (made of steps), Home, MoveAxis, Dispense, Tare, Weigh       │
 │        │ "switch these outputs" (loc[Filling/<Item>/cmd])                         │
 │        ▼                         ▲ "this is what the inputs say" (.../state)      │
 │  Equipment: LinearAxis, Pump, Scale  ── the only blocks that touch pins           │
 │        │                                                                         │
 │  IO blocks: IO_DI, IO_DO, IO_AO ── one per pin                                    │
 └────────┼─────────────────────────────────────────────────────────────────────────┘
          ▼
 Raspberry Pi pins: GPIO17 Enable, GPIO27 Down, GPIO18 Step (PWM), GPIO23 AtHome
          ▼
 TB6600 stepper driver → stepper motor of the needle's axis; limit switch at the top
```

Four layers, top to bottom:

1. **Module level**: `Occupation` decides who may give commands; `Module` holds the module's
   PackML state (Stopped, Idle, Execute, ...).
2. **Skills**: what the module can do. A *skill primitive* is one action of one piece of equipment
   (move the needle, run the pump, weigh). A *module level skill* (Dispensing) is a sequence of
   primitives. *Procedures* (Resetting, Stopping) are sequences the module runs by itself.
3. **Equipment**: one block per piece of hardware (the axis, the pump, the scale). Only it touches
   the hardware's pins; it does what the skill holding it says.
4. **IO**: one block per pin, which knows how to reach the pin (a Pi GPIO line, a PWM channel, a
   Modbus register, or simulated).

## 2. Two kinds of wire

In the IDE you see lines between blocks: **connections**. Events (the thin lines: "now do this")
and data (the values that go with them). They only connect blocks inside the same network.

Much of the traffic between the layers goes over **local channels** instead: named mailboxes in
FORTE (`loc[<name>]`), written by PUBLISH blocks and read by SUBSCRIBE blocks. Any number of blocks
can write to and read from one channel, and they need no line between them. That is why a skill
added while the program runs needs no wiring to the equipment or to the occupation. The price: these
links are not drawn in the IDE. They are:

| Channel | Written by | Read by | Carries |
| --- | --- | --- | --- |
| `loc[Filling/owner]` | Occupation | every skill, Module | The session id of whoever occupies the module (empty: free) |
| `loc[Filling/owner/query]` | a block at start-up | Occupation | "Tell me the owner" |
| `loc[Filling/state]` | Module | every skill, every equipment block | The PackML state (a number, see section 3) |
| `loc[Filling/state/query]` | a block at start-up | Module | "Tell me the state" |
| `loc[Filling/activity]` | every skill | Module | +1 when a skill starts, -1 when it ends (Stopping waits until no skill runs) |
| `loc[Filling/release]` | every skill when its run ends | every equipment block | "The holder X gives up": the equipment X holds switches off and is free |
| `loc[Filling/LinearAxis/cmd]` | the skills that move the axis | LinearAxis | The holder's name and the output values to switch (Enable, Down, Step), or a move to a position |
| `loc[Filling/LinearAxis/state]` | LinearAxis | the skills that move the axis | AtHome, ActualPosition, Homed, Moving and the holder |
| `loc[Filling/Pump/cmd]`, `.../state` | Dispense / Pump | Pump / Dispense | The holder and the command; the holder |
| `loc[Filling/Scale/cmd]`, `.../state` | Tare, Weigh / Scale | Scale / Tare, Weigh | The holder and the command; Weight and the holder |

## 3. What a client can see and call

Every method takes the caller's session id (`Session`, a text the client chose when it occupied the
module) and answers at once with `[Accepted, ErrorID]`. Whether a skill then succeeds is seen in its
`State`.

| OPC UA node below `/Objects/Filling` | Kind | Served by the block | What it does |
| --- | --- | --- | --- |
| `Occupation/Occupy(Session)` | method | `Occupation.Occupy` | Occupy the module with this session id (when it is free, or again by the owner) |
| `Occupation/Release(Session)` | method | `Occupation.Release` | Give the module up (only the owner) |
| `Occupation/Occupied` | variable | `Occupation.PubUa` | Whether it is occupied (the session id is never shown) |
| `Module/Reset`, `Start`, `Stop`, `Abort`, `Clear` (Session) | methods | `Module.Reset` ... `Module.Clear` | Change the PackML state (only the owner, only where PackML allows it) |
| `Module/State` | variable | `Module.PubUa` | The PackML state |
| `Skills/Dispensing/Start(Session, Volume)` | method | `Dispensing.UaStart` | Start Dispensing with this volume (mL) |
| `Skills/Dispensing/Stop`, `Abort`, `Reset` (Session) | methods | `Dispensing.Control` (its `UaStop`, `UaAbort`, `UaReset`) | Stop, abort or reset Dispensing |
| `Skills/Dispensing/State`, `ErrorID` | variables | `Dispensing.Control` (its `PubState`) | Where Dispensing is, why it last failed |
| `Skills/Dispensing/Parameters/Volume`, `Results/Weight` | variables | `Dispensing.PubParams`, `Dispensing.PubResults` | The volume of the current or last run; the weight it measured |
| `Skills/Dispensing/Execute/<step>/State`, `ErrorID`, `Parameters/...` | variables | each step (e.g. `Dispensing.Execute.NeedleDown`) | Where each step of Dispensing is |
| `Skills/Dispensing/Stopping/Home/...` | variables | `Dispensing.Stop.Home` | The step Dispensing runs when it is stopped |
| `Skills/<primitive>/Start(Session, parameters)`, `Stop`, `Abort`, `Reset` | methods | the primitive's block (`Home`, `MoveAxis`, `Dispense`, `Tare`, `Weigh`), inside it `UaStart` and `Control` | Run one primitive on its own: `MoveAxis(Position)`, `Dispense(Volume, FlowRate)`, `Home`, `Tare`, `Weigh` |
| `Skills/<primitive>/State`, `ErrorID`, `Parameters/...`, `Results/...` | variables | the primitive's block | Its state, error, parameters and results (`Weigh`: `Results/Weight`) |
| `Procedures/Resetting/Home`, `.../Tare`, `Procedures/Stopping/Home` (`State`, `ErrorID`) | variables | `Resetting.Home`, `Resetting.Tare`, `Stopping.Home` | Where the procedures are |
| `Equipment/LinearAxis/AtHome`, `ActualPosition`, `Homed`, `Moving` | variables | `LinearAxis` (its `PubUa`) | The axis: at the switch, where it is (mm), whether that is known, whether it moves |
| `Equipment/Scale/Weight` | variable | `Scale` (its `PubUa`) | The weight (g; simulated) |

**PackML states of the module** (`Module/State`): 1 Clearing, 2 Stopped, 3 Starting, 4 Idle,
6 Execute, 7 Stopping, 8 Aborting, 9 Aborted, 15 Resetting.

**States of a skill** (`.../State`): 0 Idle, 1 Running, 2 Stopping, 3 Succeeded, 4 Failed,
5 Aborted. A skill that succeeded returns to Idle by itself after 1.5 s; a failed one stays Failed
until it is started again; an aborted one needs Reset.

**Error codes** (`ErrorID`, also the second answer of every method): 0 none, 1 PreconditionViolated
(the skill cannot start from here, e.g. MoveAxis before the axis is homed), 2 InvariantViolated
(something it needs stopped holding while it ran), 3 Timeout, 4 NotReady (the module is not in
Execute), 5 NotPermitted (the caller does not hold the occupation), 6 Busy (the skill runs, or its
equipment is held by another skill), 7 Interrupted (it was stopped), 8 OutOfRange (a parameter
outside its limits).

## 4. Following a call through the blocks

### 4.1 Occupying the module

1. The client calls `Occupation/Occupy` with a session id of its own, say `hmi-1`.
2. FORTE's OPC UA server hands the call to the block that created the method: `Occupation.Occupy`
   (a `SERVER` block). It gives the session id to `Occupation.Logic`.
3. `Occupation.Logic` accepts if nobody occupies the module (or `hmi-1` already does) and answers
   `[TRUE, 0]` through `Occupation.Occupy` back to the client; otherwise `[FALSE, 5]`.
4. `Occupation.PubOwner` writes `hmi-1` on `loc[Filling/owner]`; every skill and `Module` keep it
   (their `Owner` blocks). `Occupation.PubUa` sets `Occupation/Occupied` to TRUE.

From now on every command must carry `hmi-1`; any other session gets error 5.

### 4.2 Resetting and starting the module

1. `Module/Reset(hmi-1)` reaches `Module.Reset` (a `SERVER` block), which hands it to
   `Module.Logic`. The owner check uses `Module.Owner`; PackML allows Reset from Stopped.
2. `Module.Logic` answers `[TRUE, 0]`, goes to Resetting (15) and publishes it on
   `Module/State` and on `loc[Filling/state]`.
3. It starts the **Resetting procedure**: `Module.RUN_RESETTING` → `Resetting.START`. The procedure
   is a subapplication with two steps: `Resetting.Home` (drive the needle up to the limit switch) and
   then `Resetting.Tare` (tare the scale). Each step works like any primitive (section 4.4); here they
   take their equipment under the name `Procedures/Resetting`.
4. When both have succeeded, `Resetting.DONE` → `Module.RESETTING_DONE`: the module is Idle (4). If
   a step fails (`Resetting.Fail1` joins the two steps' failures), the module aborts: Aborting, then
   Aborted (9), and needs Clear and Reset again.
5. `Module/Start(hmi-1)` → Execute (6). Only now may a client start skills.

### 4.3 Starting Dispensing

The client calls `Skills/Dispensing/Start(hmi-1, 2.0)`: fill 2 mL.

1. **The call arrives** at `Dispensing.UaStart` (a `SERVER_2_2` block: the method's two inputs are
   the session and the volume). It hands the volume to `Dispensing.Volume` to be checked.
2. **The value is checked.** `Dispensing.Volume` (a parameter block) compares 2.0 with its limits
   (0.5 to 10 mL). Then `Dispensing.Control` gets the start request with the session and whether all
   values were in range.
3. **The start is checked.** `Dispensing.Control` (`SKILL_Core`) accepts only if `hmi-1` occupies
   the module (it knows the owner from `loc[Filling/owner]`), the module is in Execute (from
   `loc[Filling/state]`), Dispensing is not running, and the value was in range. Its answer goes
   back through `Dispensing.UaStart` to the client: `[TRUE, 0]`, or `[FALSE, <code>]` and nothing
   happens.
4. **The run begins.** `Dispensing.Control` sets `State` to Running (1), says +1 on
   `loc[Filling/activity]` (the module counts running skills), and fires `RUN`.
   `Dispensing.Volume` now holds 2.0 for the whole run; `Dispensing.PubParams` writes it to
   `Skills/Dispensing/Parameters/Volume`; and `Dispensing.Execute` (the sequence) starts.
5. **Step 1, `Dispensing.Execute.NeedleDown`** (a `MoveAxis` with the constant Position 40 mm):
   - its `Logic` checks the precondition: the axis is homed (it reads `Homed` from
     `loc[Filling/LinearAxis/state]`);
   - it waits until the axis is free or already held by `Dispensing`;
   - it sends "move to 40 mm, holder Dispensing" on `loc[Filling/LinearAxis/cmd]` (its `Driver`
     turns the command into the values, its `EqCmd` publishes them).
6. **The equipment moves.** The `LinearAxis` block hears the command (`SubCmd`). Its `Logic`
   checks the holder, switches the old outputs off first ("break before make"), works out the
   direction (40 mm is further down than 0) and switches Enable on, Down on and Step to 50 %. Its IO
   blocks write the pins: `Out_Enable` pulls GPIO17 low (the driver's enable is active low),
   `Out_Down` sets GPIO27 high, `Out_Step` puts 2 kHz pulses on GPIO18. The TB6600 turns the motor.
   `MoveT` times the move: 40 mm at 12.5 mm/s is 3.2 s.
7. **The equipment reports.** Every cycle `LinearAxis.Cycle` has `In_AtHome` read GPIO23, and the
   axis' `Logic` counts its position on. Changes go out on `loc[Filling/LinearAxis/state]`
   (`PubState`) and to `Equipment/LinearAxis/...` over OPC UA (`PubUa`).
8. **The step ends.** When `MoveT` runs out, the axis switches the outputs off, is no longer
   Moving and is at 40 mm. `NeedleDown` sees that on the state channel (its `EqState` and `EqView`):
   its end condition (not moving and at the position) holds, so it succeeds (State 3) and starts the
   next step. It keeps the axis held: within Dispensing, the steps share the equipment under the
   name `Dispensing`.
9. **Step 2, `Dispensing.Execute.Dispense`**, gets Dispensing's Volume (2.0) through a connection
   and has the constant FlowRate 1.0 mL/s: it sends `Run` to `Pump` and ends after Volume / FlowRate
   = 2 s (its `Timer`). The pump has no pins yet, so dispensing is only a time.
10. **Step 3, `Dispensing.Execute.Home`**: `Up` to the axis until `AtHome` (GPIO23) is on; the
    position is then 0 and known again.
11. **Step 4, `Dispensing.Execute.Weigh`**: `Measure` to the scale for 0.2 s; its result `Weight`
    (from `loc[Filling/Scale/state]`; simulated, 2.0 g) goes out of the sequence as Dispensing's
    result.
12. **The run ends.** `Dispensing.Execute.DONE` → `Dispensing.PubResults` writes
    `Skills/Dispensing/Results/Weight`, and `Dispensing.Control` sets Succeeded (3). It says on
    `loc[Filling/release]` that `Dispensing` gives up its equipment, so every equipment block it held
    switches off and is free; it says -1 on the activity channel; after 1.5 s it is Idle (0) again.

If a step fails (a timeout, the axis not homed, ...), the step's `FAILURE` goes through the
`Dispensing.Execute.Fail1` to `Fail3` blocks (which join the four steps' failures into one) to
`Dispensing.Control`: Dispensing is Failed (4) with that step's error code, and its equipment is
released.

### 4.4 A primitive on its own

`Skills/MoveAxis/Start(hmi-1, 30.0)` reaches the block `MoveAxis` (type `SK_MoveAxis`). Inside it
the same happens as for Dispensing, in one block: `UaStart` takes the call, `Par_Position` checks
30.0 against 0 to 60 mm, `Control` checks the session, the module state, that it is not running and
that the axis is free (`Logic.EquipmentFree`), answers, and starts `Logic`. `Logic` moves the axis as
in 4.3, steps 5 to 8, holding it under the name `MoveAxis`; when it is done, the axis is released
(`ReleaseAfter` is TRUE for a primitive on its own).

### 4.5 Stopping, aborting, releasing

- **`Skills/Dispensing/Stop`**: `Dispensing.Control` halts the running step (its `HALT`), goes to
  Stopping (2), runs the stop sequence `Dispensing.Stop` (Home: the needle back up), and ends Failed
  with error 7 Interrupted.
- **`Module/Stop`**: the module goes to Stopping (7). Every skill a client started stops as above;
  `Module` waits until no skill runs (the activity count is 0), then runs the Stopping procedure
  (`Stopping.Home`) and is Stopped (2). If the skills have not stopped after `StopTimeout` (10 s),
  the module aborts instead.
- **`Module/Abort`** or **`Skills/<skill>/Abort`**: everything stops where it is. The equipment
  blocks switch all outputs off at once (they watch the module state for Aborting), the skills go to
  Aborted (5). `Clear` then `Reset` brings the module back; `Skills/<skill>/Reset` brings an aborted
  skill back to Idle.
- **`Occupation/Release`**: the module is free again. It does not stop running skills: stop the
  module first.

### 4.6 Start-up

When FORTE starts (or the program is deployed), the resource's own `START` block fires and every
block initialises in a chain, each `INITO` to the next `INIT`: `Occupation`, `Module`, the equipment
(which set up their pins and start reading), the offered primitives, the procedures, then
Dispensing. Initialising is when the blocks create their OPC UA methods and variables. A skill added
while the program runs is appended to the end of this chain.

## 5. Every block of the application

The application `Filling_pi` (the one deployed to the Pi; `Filling` is the same for the PC, with its
IO on the Modbus simulator).

| Block | Type | What it does |
| --- | --- | --- |
| `Occupation` | `MOD_Occupation` | Who may command the module (4.1) |
| `Module` | `MOD_StateManager` | The PackML state; runs the procedures (4.2, 4.5) |
| `LinearAxis` | `EQ_LinearAxis` | The needle's axis: owns Enable (GPIO17), Down (GPIO27), Step (PWM on GPIO18) and AtHome (GPIO23); keeps the position by counting time |
| `Pump` | `EQ_Pump` | The filling pump: no pins yet; holds the command `Run` while a skill dispenses |
| `Scale` | `EQ_Scale` | The scale: its Weight is simulated (`'sim'`) |
| `Home` | `SK_Home` | Primitive: the needle up until the limit switch (`Up` until `AtHome`; timeout 60 s) |
| `MoveAxis` | `SK_MoveAxis` | Primitive: the needle to `Position` (0 to 60 mm); needs `Homed`; timeout 30 s |
| `Dispense` | `SK_Dispense` | Primitive: run the pump for `Volume` / `FlowRate` seconds |
| `Tare` | `SK_Tare` | Primitive: tare the scale (2 s) |
| `Weigh` | `SK_Weigh` | Primitive: read the weight (0.2 s); result `Weight` |
| `Resetting` (subapplication) | | The procedure run on Reset: `Resetting.Home`, `Resetting.Tare`, `Resetting.Fail1` |
| `Stopping` (subapplication) | | The procedure run on Stop: `Stopping.Home` |
| `Dispensing` (subapplication) | | The module level skill: |
| `Dispensing.Control` | `SKILL_Core` | Its state machine, Stop/Abort/Reset methods, State and ErrorID (4.3) |
| `Dispensing.UaStart` | `SERVER_2_2` | The method `Skills/Dispensing/Start(Session, Volume)` |
| `Dispensing.Volume` | `SKILL_Param_LREAL` | The parameter Volume: default 1.0, limits 0.5 to 10 mL |
| `Dispensing.PubParams` | `PUBLISH_1` | Writes `Parameters/Volume` |
| `Dispensing.PubResults` | `PUBLISH_1` | Writes `Results/Weight` |
| `Dispensing.Execute` (subapplication) | | The steps, in order: `NeedleDown` (MoveAxis, Position 40), `Dispense` (FlowRate 1.0, Volume from Dispensing), `Home`, `Weigh` (its Weight is Dispensing's result); `Fail1` to `Fail3` join their failures |
| `Dispensing.Stop` (subapplication) | | What Dispensing runs when it is stopped: `Home` |

The steps inside Dispensing and the procedures are blocks of the same primitive types as the
offered ones, each with its own name, OPC UA variables and constants: a primitive can be used in
several places at once.

## 6. Inside the block types

A block type is either **basic** (a state machine with small programs, in Structured Text) or
**composite** (a network of other blocks). The composites below are listed with the blocks inside
them. Types named `modlib::...` are the library's and the same in every module; `filling::...` are
the filling module's own.

### `MOD_Occupation` (composite): who may command

| Inside | Type | What it does |
| --- | --- | --- |
| `Ids` | `MOD_OccupationIds` | Builds the OPC UA addresses (`/Objects/Filling/Occupation/...`) and channel names from the module's name |
| `Occupy`, `Release` | `SERVER_2_1` | The two OPC UA methods (one input: the session; two answers: Accepted, ErrorID) |
| `Logic` | `MOD_OccupationLogic` | Decides: occupy when free or by the owner, release only by the owner |
| `PubOwner` | `PUBLISH_1` | Tells every block the owner on `loc[Filling/owner]` |
| `SubQuery` | `SUBSCRIBE_0` | Answers a block that asks for the owner at start-up |
| `PubUa` | `PUBLISH_1` | Writes `Occupation/Occupied` |

### `MOD_StateManager` (composite): the module's PackML state

| Inside | Type | What it does |
| --- | --- | --- |
| `Ids` | `MOD_StateIds` | The OPC UA addresses (`/Objects/Filling/Module/...`) and channel names |
| `Owner` | `MOD_OwnerView` | Knows the owner (only the owner may change the state) |
| `Reset`, `Start`, `Stop`, `Abort`, `Clear` | `SERVER_2_1` | The five OPC UA methods |
| `Logic` | `MOD_StateLogic` | The PackML state machine: which command is allowed in which state; starts the procedures and waits for them |
| `PubUa`, `PubState` | `PUBLISH_1` | Write the state to `Module/State` and to `loc[Filling/state]` |
| `SubQuery` | `SUBSCRIBE_0` | Answers a block that asks for the state at start-up |
| `SubAct`, `Count` | `SUBSCRIBE_1`, `MOD_ActivityCount` | Hear the skills' +1 and -1 and count how many run |
| `Wd` | `E_DELAY` | Gives up waiting for the skills after `StopTimeout`: the module aborts |

### `SKILL_Core` (composite): what every skill shares

Used in every primitive (as `Control`) and as `Control` of every module level skill.

| Inside | Type | What it does |
| --- | --- | --- |
| `Control` | `SKILL_Control` | The skill's state machine: what Start, Stop, Abort and Reset do in each state; the checks of a client's command; the answer |
| `Owner` | `MOD_OwnerView` | Knows the owner (from `loc[Filling/owner]`) |
| `Mode` | `MOD_StateView` | Knows the module state: start only in Execute; stop when the module stops |
| `UaStop`, `UaAbort`, `UaReset` | `SERVER_2_1` | The OPC UA methods Stop, Abort, Reset (the Start method is outside, because it carries the skill's own parameters) |
| `PubState` | `PUBLISH_2` | Writes `State` and `ErrorID` |
| `Act` | `PUBLISH_1` | Says +1 / -1 on the activity channel |
| `ToIdle` | `E_DELAY` | Returns a succeeded skill to Idle after 1.5 s |
| `PubRelease` | `PUBLISH_1` | Says on the release channel that the skill gives up its equipment, when a run ends |

### `SK_<Skill>` (composite): a skill primitive

`SK_Home`, `SK_MoveAxis`, `SK_Dispense`, `SK_Tare`, `SK_Weigh`. All are built alike; `SK_Dispense`
as the example:

| Inside | Type | What it does |
| --- | --- | --- |
| `Control` | `SKILL_Core` | The state machine and the Stop/Abort/Reset methods (above) |
| `UaStart` | `SERVER_2_3` | The OPC UA method `Start(Session, Volume, FlowRate)`; its size follows the number of parameters (`SERVER_2_1` for Home, which has none) |
| `Par_Volume`, `Par_FlowRate` | `SKILL_Param_LREAL` | One per parameter: the default (the block's input of that name), the range check, the value held for the run |
| `PubParams` | `PUBLISH_2` | Writes `Parameters/Volume` and `Parameters/FlowRate` |
| `Logic` | `SL_Dispense` | What this skill does (below) |
| `EqState`, `EqView` | `SUBSCRIBE_1`, `EV_Pump` | Hear the equipment's state channel and unpack it (inputs, holder) |
| `WaitT` | `E_DELAY` | Waits up to 0.5 s for the equipment to become free |
| `Driver` | `EC_Pump` | The equipment's command table: turns `Run` into output values |
| `PhaseT` | `E_DELAY` | Times a command made of phases |
| `EqCmd` | `PUBLISH_2` | Sends the holder and the output values on `loc[Filling/Pump/cmd]` |
| `Timer` | `E_DELAY` | Ends a timed skill (here: after Volume / FlowRate) or fails a skill after its timeout |
| `PubResults` (only `SK_Weigh`) | `PUBLISH_1` | Writes `Results/Weight` |

**The inputs of a primitive block** (what you set on an instance): `Module` (the module's name, for
the channel names), `UaRoot` and `UaPath` (where its OPC UA variables go), `UaEnable` (publish them
at all), `Methods` (offer Start/Stop/Abort/Reset over OPC UA: TRUE when offered on its own, FALSE as
a step), `Holder` (the name it holds the equipment under), `ReleaseAfter` (give the equipment up when
it ends: TRUE on its own, FALSE as a step), `Timeout` (for a skill a sensor ends), and one input per
parameter, whose value is the default.

### `SL_<Skill>` (basic): what a primitive does

The heart of a primitive. Its state machine, the same pattern for every primitive:

1. **Start**: check the precondition (Reject with 1 PreconditionViolated if it does not hold); if
   the end condition holds already, succeed at once without moving (AlreadyDone: Home when the needle
   is at the switch).
2. **Wait for the equipment**: if another holder has it, wait up to 0.5 s, then fail with 6 Busy.
3. **Run**: send the command (with its argument), start the timer (the time it ends after, or its
   timeout).
4. **Watch**: on every new state of the equipment, check the end condition (a sensor:
   `AtHome`; or "not moving and at the position"), the invariant (Unsafe: 2 InvariantViolated), and
   that nobody took the equipment away (Lost).
5. **End**: send the closing command (the equipment's safe command, or the skill's own `stop`
   command), then report done, failed or halted.

| Primitive | Precondition | Command (equipment) | Ends when | Timeout | Parameters | Results |
| --- | --- | --- | --- | --- | --- | --- |
| `Home` | – | `Up` (LinearAxis) | `AtHome` (sensor) | 60 s | – | – |
| `MoveAxis` | `Homed` | `MoveTo(Position)` (LinearAxis) | not `Moving` and at `Position` (sensor, the axis' own count) | 30 s | Position 0 to 60 mm | – |
| `Dispense` | – | `Run` (Pump) | after Volume / FlowRate s (time) | – | Volume 0.5 to 10 mL, FlowRate 0.1 to 5 mL/s | – |
| `Tare` | – | `Tare` (Scale) | after 2 s (time) | – | – | – |
| `Weigh` | – | `Measure` (Scale) | after 0.2 s (time) | – | – | Weight (the scale's input) |

### `EC_<Item>` (basic): the command table of a piece of equipment

Turns a command's name into the output values to switch. `EC_LinearAxis`: Stop = everything off;
Up = Enable on, Step 50 %; Down = Enable on, Down on, Step 50 %; MoveTo = "move to the position in
the argument" (the axis works out the direction itself). A command may have several timed phases
(the stoppering piston's `Back`: Retract on for 3 s, then off). It sits in each skill, not in the
equipment, so the equipment block stays the same whatever the outputs mean.

### `EV_<Item>` (basic): the equipment's state, unpacked

Turns what arrives on `loc[Filling/<Item>/state]` into named values for the skill's `Logic`
(`AtHome`, `ActualPosition`, `Homed`, `Moving`, `Weight`, and who holds it).

### `EQ_<Item>` (composite): a piece of equipment

`EQ_LinearAxis` as the example:

| Inside | Type | What it does |
| --- | --- | --- |
| `Logic` | `EL_LinearAxis` | One holder at a time; switches the outputs off before switching new ones on; all off on release or when the module aborts; keeps the position (counting the time it moves); reports input changes |
| `SubCmd` | `SUBSCRIBE_8` | Hears the commands on `loc[Filling/LinearAxis/cmd]` (holder, release, Enable, Down, Step, Step enabled, Move, Goal) |
| `SubRelease` | `SUBSCRIBE_1` | Hears `loc[Filling/release]` |
| `Mode` | `MOD_StateView` | Knows the module state (switches off on Aborting) |
| `Cycle` | `E_CYCLE` | Ticks every cycle: read the inputs |
| `MoveT` | `E_DELAY` | Times a move to a position |
| `In_AtHome` | `IO_DI` | The limit switch (GPIO23) |
| `Out_Enable`, `Out_Down` | `IO_DO` | The driver's enable (GPIO17) and direction (GPIO27) |
| `Out_Step` | `IO_AO` | The step pulses (PWM channel on GPIO18): 50 % while moving |
| `PubState` | `PUBLISH_5` | Writes AtHome, ActualPosition, Homed, Moving and the holder on `loc[Filling/LinearAxis/state]` |
| `PubUa` | `PUBLISH_4` | Writes them to `Equipment/LinearAxis/...` over OPC UA |

Its inputs: `Module`, `Name`, `UaRoot`, `UaEnable`, `CycleTime`, and one `<Pin>_Address` per pin
(see the IO blocks). `EQ_Pump` has no pins; `EQ_Scale` one input, `Weight`.

### `IO_DI`, `IO_DO`, `IO_AI`, `IO_AO` (composite): one pin

The address says where the signal is, so the same equipment type runs on every target:

| Address | Meaning |
| --- | --- |
| `gpio[0:23:pull_up:active_low]` | Raspberry Pi GPIO chip 0, line 23, with the pull-up on, read inverted |
| `gpio[0:17:active_low]` | line 17 as an output, written inverted |
| `pwm[0:2:500000:/hostsys/class/pwm]` | PWM chip 0, channel 2, period 500 000 ns (2 kHz), in the folder the container passes in |
| `modbus[...]` | a Modbus register (the PC target, with the simulator) |
| `sim` | simulated (the scale) |
| empty | not connected |

Inside: `Route` (`IO_Route...`) picks the way from the address; `Line` (`GPIOChip` or `PWMChip`)
sets up a Pi line or PWM channel; `Local` (`IX`, `QX`, `IW`, `QW`) reads or writes it; `Bus`
(`CLIENT`) reaches Modbus.

### The small blocks

| Type | What it does |
| --- | --- |
| `SKILL_Param_LREAL` (and `_BOOL`, `_INT`, `_DINT`, `_UINT`) | A parameter: its default, the range check of a client's value, the value held for the run |
| `SKILL_FailMerge` | Joins two failures into one (a data input can take only one wire) |
| `SKILL_Join2` to `4`, `SKILL_Merge`, `SKILL_Condition_LREAL` / `_BOOL` | For skills with steps side by side or decisions (rule set 2); the filling program does not use them yet |
| `SERVER_2_n` | An OPC UA method: 2 answers (Accepted, ErrorID), n inputs (the session and the parameters) |
| `PUBLISH_n`, `SUBSCRIBE_n` | Write or read n values: to OPC UA (`opc_ua[WRITE;...]`) or on a local channel (`loc[...]`) |
| `E_DELAY` | A timer: an event after a time |
| `E_CYCLE` | An event every cycle time |

## 7. Where the descriptions are in 4diac

- **A block in a network**: its comment is drawn with it, and shown in *Properties > Comment*.
  It says the block's role in this program: where its OPC UA nodes are, which channels it uses, what
  it is handed.
- **A block type**: its comment (in the type's *Properties*, and as the tooltip in the palette)
  begins with what it is for in plain words; after "Technical:" comes a short technical summary.
- **A pin**: every input and output of the generated types has a comment of its own.

To change a description, change `iec61499-skill-lib/modgen/explain.py` (the plain words) or the
spec (`cell/modules/filling.yaml`: an equipment's or a skill's `description`) and regenerate
(`python -m modgen`). A comment typed in the IDE is lost at the next generation.
