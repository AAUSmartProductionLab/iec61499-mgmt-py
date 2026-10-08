# Filling module: OPC UA interface for an HMI

This document describes everything an HMI needs to show and operate the **Filling module** over OPC UA: the address space, the two state machines (module and skill), every method with its arguments and answers, the error codes, and the rules for when a command is accepted. It is complete on its own.

Generated from the module specification and checked against the address space of the running controller (Eclipse 4diac FORTE 3.3, IEC 61499). If the module changes, regenerate this file.

> **Out of date since 8 Oct 2026 in sections 7, 8, 9 and 11.** The needle is now lifted by a stepper axis that is moved to a position. The equipment item is `LinearAxis` with `AtHome`, `ActualPosition` (mm), `Homed` and `Moving`; beside it there is `Pump` (no values) and `Scale`. The skill primitives are `Home`, `MoveAxis(Position: Double, 0 to 60 mm)`, `Dispense`, `Tare` and `Weigh`; `MoveNeedleUp`, `MoveNeedleDown` and `AttachNeedle` are gone. Dispensing's steps are `NeedleDown`, `Dispense`, `NeedleUp` and `Weigh`, its stop sequence is `Home`; Resetting runs `Home` then `Tare`, Stopping runs `Home`. Sections 1 to 6 and 10 (connection, rules, occupation, the two state machines, error codes, what an HMI offers) hold as written. What the module is now: [modules.md](../modules.md).

## 1. Connection

| | |
| --- | --- |
| Endpoint on the machine | `opc.tcp://192.168.0.191:4840` |
| Endpoint of the simulated module (development) | `opc.tcp://localhost:4840` |
| Security | None (security policy `None`, anonymous). There is no user authentication. |
| Root object | `/Objects/Filling` (browse path `0:Objects / 1:Filling`) |
| Namespace | Every node of the module is in namespace **index 1**. Its URI is `org.eclipse.4diac.forte_<number>` and the number differs between installations, so select the namespace by index 1, not by URI. |
| Node ids | Numeric (`ns=1;i=...`) and **different after every restart of the controller**. Never store them. Resolve each node by its browse path at connect time (TranslateBrowsePathsToNodeIds or browsing), and resolve again after a reconnect. |
| Access | Variables are read-only. Everything is changed through methods. |
| Updates | Use a subscription with data-change monitored items (sampling 100 to 250 ms). Do not poll with method calls. |

To develop without the machine, the simulated module runs on a PC: `python cell/sim/run_module.py cell/modules/filling.yaml`. It serves the same address space with simulated equipment (motion takes realistic time).

In this document a node is written as its path below the root, e.g. `Module/State` means `/Objects/Filling/Module/State`, browse path `0:Objects / 1:Filling / 1:Module / 1:State`.

## 2. Rules that apply to every method

- **Signature.** Every method takes the caller's session id as its first argument (String). `Start` of a skill takes the skill's parameters after it, in the order listed for that skill (each a Double unless stated). The server names the arguments generically (`RD_1`, `RD_2`, ... in; `SD_1`, `SD_2` out); only the position matters.
- **Answer.** Every method returns two values: `Accepted` (Boolean) and `ErrorID` (UInt16). `Accepted = true` comes with `ErrorID = 0`. `Accepted = false` means nothing happened, and `ErrorID` says why (section 6).
- **A method only accepts or refuses.** It answers at once. It does not wait for the action to finish. Progress and the result are read from the `State` and `ErrorID` variables.
- **The OPC UA status of the call is `Good` also when the command is refused.** Always evaluate `Accepted`.
- The controller handles one method call at a time. Do not send calls in parallel; wait for each answer.

## 3. Occupation: who may operate the module

A module is operated by one client at a time, its **occupant**. The HMI must occupy the module before any other command is accepted.

| Node | Kind | Type / arguments | Meaning |
| --- | --- | --- | --- |
| `Occupation/Occupy` | Method | `(Session: String)` -> `[Accepted, ErrorID]` | Take the module. Accepted when it is free, or when the same session already holds it. Refused with 5 when another session holds it, or when `Session` is empty. |
| `Occupation/Release` | Method | `(Session: String)` -> `[Accepted, ErrorID]` | Give the module up. Accepted only from the occupant; otherwise 5. |
| `Occupation/Occupied` | Variable | Boolean | True while some session holds the module. The session id itself is never published. |

Rules for the HMI:

- Create one session id when the HMI starts (a UUID string) and send it with every method call.
- **Keep the session id across page reloads and restarts** (for example in local storage). The occupation has no timeout: if the HMI loses its id while occupying, nobody can release the module until the controller is restarted.
- `Occupied = true` does not tell whether *this* HMI is the occupant. The HMI knows it from its own last accepted `Occupy` or `Release`. After a reconnect, call `Occupy` again with the stored id: `Accepted` means it is (still or again) the occupant; 5 means someone else is.
- Without the occupation the HMI can still read everything (monitoring only); all commands are refused with 5.
- Releasing does not stop anything. A running skill keeps running. Stop the module before releasing.

## 4. Module state machine (PackML)

`Module/State` (Byte) is the state of the whole module. It is the governing state: skills can only be started while the module is in Execute.

| Value | State | Kind | Meaning |
| --- | --- | --- | --- |
| 2 | Stopped | waits | Initial state after power-up. Nothing runs. |
| 15 | Resetting | acts | The Resetting procedure runs (homing, section 9). Ends in Idle, or Aborted if it fails. |
| 4 | Idle | waits | Homed and ready to be started. |
| 3 | Starting | acts | Passes at once to Execute (too short to be seen reliably). |
| 6 | Execute | waits | The occupant may start skills. The module stays here while skills run, succeed or fail. |
| 7 | Stopping | acts | Running skills are stopping; then the Stopping procedure runs (section 9). Ends in Stopped. |
| 8 | Aborting | acts | All skills abort and all outputs switch off. Passes at once to Aborted. |
| 9 | Aborted | waits | Everything is off. Only Clear is possible. |
| 1 | Clearing | acts | Passes at once to Stopped; aborted skills return to Idle. |

Commands (all `Module/<Command>(Session: String)` -> `[Accepted, ErrorID]`):

| Method | Accepted in state | Leads to | Refused |
| --- | --- | --- | --- |
| `Module/Reset` | Stopped | Resetting, then Idle | 4 in any other state |
| `Module/Start` | Idle | Execute | 4 in any other state |
| `Module/Stop` | Resetting, Idle, Execute | Stopping, then Stopped | 4 in Stopped, Stopping, Aborted |
| `Module/Abort` | Stopped, Resetting, Idle, Execute, Stopping | Aborted | 4 in Aborted |
| `Module/Clear` | Aborted | Stopped | 4 in any other state |

Every command is refused with 5 when the caller is not the occupant (checked first).

```mermaid
stateDiagram-v2
    [*] --> Stopped
    Stopped --> Resetting: Reset
    Resetting --> Idle: procedure done
    Resetting --> Aborting: procedure failed
    Idle --> Starting: Start
    Starting --> Execute
    Resetting --> Stopping: Stop
    Idle --> Stopping: Stop
    Execute --> Stopping: Stop
    Stopping --> Stopped: skills stopped, procedure done
    Stopping --> Aborting: procedure failed or timeout
    Stopped --> Aborting: Abort
    Resetting --> Aborting: Abort
    Idle --> Aborting: Abort
    Execute --> Aborting: Abort
    Stopping --> Aborting: Abort
    Aborting --> Aborted
    Aborted --> Clearing: Clear
    Clearing --> Stopped
```

What the states do to the skills:

- **Stop**: every skill the occupant started is halted and ends as Failed with ErrorID 7 (after its stop sequence, if it has one). When no skill is active any more, the Stopping procedure runs. If the skills do not end within 10s, the module aborts.
- **Abort**: every skill goes to Aborted and every output is switched off at once. Nothing is moved to a safe position.
- **Clear**: aborted skills return to Idle.
- A skill that fails does **not** change the module state; the module stays in Execute.
- This is a software stop, not a safety function. The emergency stop is hardware.

The usual way to bring the module into operation: `Occupy`, `Reset` (wait for Idle), `Start` (Execute). To shut down: `Stop` (wait for Stopped), `Release`. After a fault that ended in Aborted: `Clear`, `Reset`, `Start`.

## 5. Skill state machine

Every skill has the same nodes and the same state machine. `<Skill>` stands for the skill's name (section 8).

| Node | Kind | Type / arguments | Meaning |
| --- | --- | --- | --- |
| `Skills/<Skill>/Start` | Method | `(Session: String, <parameters>)` -> `[Accepted, ErrorID]` | Start one run with these parameter values. |
| `Skills/<Skill>/Stop` | Method | `(Session: String)` -> `[Accepted, ErrorID]` | Stop a running skill in an orderly way. |
| `Skills/<Skill>/Abort` | Method | `(Session: String)` -> `[Accepted, ErrorID]` | Switch the skill's outputs off at once. |
| `Skills/<Skill>/Reset` | Method | `(Session: String)` -> `[Accepted, ErrorID]` | Bring an aborted skill back to Idle. |
| `Skills/<Skill>/State` | Variable | Byte | The skill's state (table below). |
| `Skills/<Skill>/ErrorID` | Variable | UInt16 | Why the skill last failed (section 6); 0 while running and after a success. |
| `Skills/<Skill>/Parameters/<Name>` | Variable | see the skill | The value used by the current or last run. Before the first run: the default. |
| `Skills/<Skill>/Results/<Name>` | Variable | see the skill | A value the skill produced, updated when it succeeds. |

| Value | State | Meaning |
| --- | --- | --- |
| 0 | Idle | Never run, or reset. |
| 1 | Running | The run is in progress. |
| 2 | Stopping | Stop was requested; the equipment is being stopped and the stop sequence (if any) runs. Often too short to be seen. |
| 3 | Succeeded | The last run reached its goal. Shown for 1.5 s, then the skill returns to Idle by itself (a new Start is accepted in both). |
| 4 | Failed | The last run failed or was stopped; `ErrorID` says why. |
| 5 | Aborted | Aborted; outputs are off. Needs `Reset` (or the module's `Clear`) before it can start again. |

| Method | Accepted when | Leads to | Refused with |
| --- | --- | --- | --- |
| `Start` | the skill is Idle, Succeeded or Failed **and** the module is in Execute **and** the arguments are in range **and** the skill's equipment is free | Running, then Succeeded or Failed | see the order below |
| `Stop` | the skill is Running | Stopping, then Failed with ErrorID 7 | 4 otherwise |
| `Abort` | the skill is in any state except Aborted | Aborted | 4 when already Aborted |
| `Reset` | the skill is Aborted | Idle | 4 otherwise |

`Start` is checked in this order; the first failing check gives the ErrorID:

1. The caller is not the occupant -> 5 (NotPermitted).
2. The module is not in Execute -> 4 (NotReady).
3. The skill is Running or Stopping -> 6 (Busy).
4. The skill is Aborted -> 4 (NotReady).
5. An argument is out of range -> 8 (OutOfRange).
6. The skill's equipment is held by another skill -> 6 (Busy).

```mermaid
stateDiagram-v2
    [*] --> Idle
    Idle --> Running: Start
    Succeeded --> Running: Start
    Failed --> Running: Start
    Running --> Succeeded: goal reached
    Succeeded --> Idle: after 1.5 s
    Running --> Failed: fault (ErrorID 1, 2, 3, 6)
    Running --> Stopping: Stop, or module Stop
    Stopping --> Failed: stopped (ErrorID 7)
    Idle --> Aborted: Abort, or module Abort
    Running --> Aborted: Abort, or module Abort
    Stopping --> Aborted: Abort, or module Abort
    Succeeded --> Aborted: Abort, or module Abort
    Failed --> Aborted: Abort, or module Abort
    Aborted --> Idle: Reset, or module Clear
```

Notes:

- A skill can be started again directly from Succeeded or Failed; no Reset is needed.
- Succeeded is shown for 1.5 s, then the skill is Idle again; Failed stays until the next Start. So Idle with `ErrorID = 0` after Running means the run succeeded. Follow `State` with a subscription: a client that polls more slowly than that can miss Succeeded.
- A skill that is already at its goal (for example the axis is already at the end switch) succeeds at once without moving anything.
- Skills that use different equipment can run at the same time. Two skills on the same equipment cannot: the second is refused with 6.
- A *module level skill* runs several steps in sequence and holds its equipment from the first step that uses it until the end.

## 6. Error codes (`ErrorID`)

The same codes are used in method answers and in the `ErrorID` variable of a skill.

| Code | Name | Meaning |
| --- | --- | --- |
| 0 | None | No error. |
| 1 | PreconditionViolated | The skill's start condition does not hold (its `requires`). |
| 2 | InvariantViolated | A condition that must hold during the run was broken; the equipment was switched off. |
| 3 | Timeout | The end condition (a sensor) was not reached in time; the equipment was switched off. |
| 4 | NotReady | The command is not valid in the current state (module not in Execute, skill Aborted, ...). |
| 5 | NotPermitted | The caller's session does not occupy the module. |
| 6 | Busy | The skill is already running, or its equipment is held by another skill. |
| 7 | Interrupted | The skill was stopped (Stop, module Stop) or aborted while running. |
| 8 | OutOfRange | A Start argument is outside the parameter's range. |

## 7. Equipment: sensor values

Only the sensors (inputs) are published. The actuator outputs are not: show activity from the state of the skills.

| Node | Type | Unit | Equipment | Meaning |
| --- | --- | --- | --- | --- |
| `Equipment/NeedleAxis/AtTop` | Boolean | - | Needle lift, DC motor through an L298N (IN3 up, IN4 down, ENB speed), end switches top and bottom | True when the switch is reached |
| `Equipment/NeedleAxis/AtBottom` | Boolean | - | Needle lift, DC motor through an L298N (IN3 up, IN4 down, ENB speed), end switches top and bottom | True when the switch is reached |
| `Equipment/Scale/Weight` | Double | g | Scale; the hardware has none yet (the ESP32 publishes a random weight), so it is simulated | Measured value |

Values are published when they change (and repeated about once per second).

## 8. Skills

### 8.1 Skill primitives (one motion each)

#### `MoveNeedleUp`

Needle up to the top end switch.

- **Start:** `Skills/MoveNeedleUp/Start(Session: String)`
- **Uses equipment:** NeedleAxis
- **Ends:** sensor condition `AtTop`; fails with Timeout (3) after 8s
- **Must hold during the run:** `NOT (AtTop AND AtBottom)`, else it fails with 2

#### `MoveNeedleDown`

Needle down to the bottom end switch.

- **Start:** `Skills/MoveNeedleDown/Start(Session: String)`
- **Uses equipment:** NeedleAxis
- **Ends:** sensor condition `AtBottom`; fails with Timeout (3) after 8s
- **Must hold during the run:** `NOT (AtTop AND AtBottom)`, else it fails with 2

#### `AttachNeedle`

Needle down to the attachment position (bottom switch), without the start boost.

- **Start:** `Skills/AttachNeedle/Start(Session: String)`
- **Uses equipment:** NeedleAxis
- **Ends:** sensor condition `AtBottom`; fails with Timeout (3) after 8s

#### `Dispense`

Dispense a volume at the station's flow rate (open loop, by time, until there is a pump).

- **Start:** `Skills/Dispense/Start(Session: String, Volume: Double, FlowRate: Double)`
- **Ends:** after Volume / FlowRate seconds

| Parameter (argument order) | Type | Unit | Range | Default | Node with the value |
| --- | --- | --- | --- | --- | --- |
| Volume | Double | mL | 0.5 .. 10 | 1 | `Skills/Dispense/Parameters/Volume` |
| FlowRate | Double | mL/s | 0.1 .. 5 | 1 | `Skills/Dispense/Parameters/FlowRate` |

#### `Tare`

Tare the scale.

- **Start:** `Skills/Tare/Start(Session: String)`
- **Uses equipment:** Scale
- **Ends:** after 2 s

#### `Weigh`

Read the weight.

- **Start:** `Skills/Weigh/Start(Session: String)`
- **Uses equipment:** Scale
- **Ends:** after 0.2 s

| Result | Type | Node |
| --- | --- | --- |
| Weight | Double | `Skills/Weigh/Results/Weight` |

### 8.2 Module level skills (a sequence of steps)

#### `Dispensing`

Needle down, dispense the volume, needle up, weigh (runFillingCycle).

- **Start:** `Skills/Dispensing/Start(Session: String, Volume: Double)`
- **Uses equipment:** NeedleAxis, Scale
- **Fails** with the ErrorID of the step that failed; the remaining steps do not run.

| Parameter (argument order) | Type | Unit | Range | Default | Node with the value |
| --- | --- | --- | --- | --- | --- |
| Volume | Double | mL | 0.5 .. 10 | 1 | `Skills/Dispensing/Parameters/Volume` |

| Result | Type | Node |
| --- | --- | --- |
| Weight | Double | `Skills/Dispensing/Results/Weight` |

Steps, in order. Each step publishes its own `State` and `ErrorID` (read-only; steps have no methods), which lets the HMI show the progress through the sequence:

| # | Step | What it does | State node |
| --- | --- | --- | --- |
| 1 | `MoveNeedleDown`: MoveNeedleDown | Needle down to the bottom end switch | `Skills/Dispensing/Execute/MoveNeedleDown/State` |
| 2 | `Dispense`: Dispense with Volume=Volume (the skill's parameter), FlowRate=1.0 | Dispense a volume at the station's flow rate (open loop, by time, until there is a pump) | `Skills/Dispensing/Execute/Dispense/State` |
| 3 | `MoveNeedleUp`: MoveNeedleUp | Needle up to the top end switch | `Skills/Dispensing/Execute/MoveNeedleUp/State` |
| 4 | `Weigh`: Weigh | Read the weight | `Skills/Dispensing/Execute/Weigh/State` |

Stop sequence (runs when the skill is stopped while Running; the skill is in state Stopping meanwhile):

| # | Step | What it does | State node |
| --- | --- | --- | --- |
| 1 | `MoveNeedleUp`: MoveNeedleUp | Needle up to the top end switch | `Skills/Dispensing/Stopping/MoveNeedleUp/State` |

A step's state stays at its last value until the skill runs again (a step that was not reached stays Idle or shows the previous run).

## 9. Procedures of the module state machine

These run by themselves in the acting states of section 4. Their steps publish `State` and `ErrorID` like the steps of a module level skill.

**Resetting** (while `Module/State` = 15):

| # | Step | What it does | State node |
| --- | --- | --- | --- |
| 1 | `MoveNeedleUp`: MoveNeedleUp | Needle up to the top end switch | `Procedures/Resetting/MoveNeedleUp/State` |

**Stopping** (while `Module/State` = 7):

| # | Step | What it does | State node |
| --- | --- | --- | --- |
| 1 | `MoveNeedleUp`: MoveNeedleUp | Needle up to the top end switch | `Procedures/Stopping/MoveNeedleUp/State` |

## 10. What the HMI should offer

Suggested content; the layout is free.

- **Connection and occupation bar:** connected or not; `Occupation/Occupied`; whether this HMI is the occupant; buttons Occupy and Release.
- **Module state view:** the state machine of section 4 as a diagram with the current state highlighted, and the five command buttons.
- **Skill panel:** one card per skill of section 8 with its state (name and colour), ErrorID as text, parameter inputs with unit, range and default, results, and the buttons Start, Stop, Abort, Reset.
- **Sequence progress:** for a module level skill and for the procedures, the steps in order with each step's state.
- **Equipment view:** the sensor values of section 7 as indicators.
- **Message log:** every refused command with the method, the ErrorID and its text; every skill that ends as Failed with its ErrorID.

When a button should be enabled (the controller checks the same and refuses otherwise, so a disabled button is a convenience, not a safeguard):

| Button | Enabled when |
| --- | --- |
| Occupy | connected and this HMI is not the occupant |
| Release | this HMI is the occupant |
| Module Reset | occupant and `Module/State` = 2 |
| Module Start | occupant and `Module/State` = 4 |
| Module Stop | occupant and `Module/State` in 15, 4, 6 |
| Module Abort | occupant and `Module/State` not 9 (keep it reachable at all times) |
| Module Clear | occupant and `Module/State` = 9 |
| Skill Start | occupant, `Module/State` = 6, skill state in 0, 3, 4, all inputs within range |
| Skill Stop | occupant and skill state = 1 |
| Skill Abort | occupant and skill state not 5 |
| Skill Reset | occupant and skill state = 5 |

Behaviour to handle:

- After a call, do not assume the new state: wait for the `State` variable to change. Show the refusal reason when `Accepted` is false.
- States that pass at once (Starting, Aborting, Clearing, and often Resetting, Stopping and a skill's Stopping) may never arrive in a subscription. Do not wait for them.
- On connection loss, mark all values as stale, reconnect, resolve the node ids again, and call `Occupy` with the stored session id.
- If the controller restarted, the module is in Stopped, nobody occupies it, and all skills are Idle.
- There are no OPC UA alarms or events and no heartbeat variable; a lost connection is detected by the client session.

## 11. Complete node list

Every node of the module as browsed from the running controller (initial values after start-up). Paths are below `/Objects`.

| Path | Class | Type or arguments | Initial value |
| --- | --- | --- | --- |
| `/Filling/Occupation` | Object | | |
| `/Filling/Occupation/Occupy` | Method | (String) -> (Boolean, UInt16) | |
| `/Filling/Occupation/Release` | Method | (String) -> (Boolean, UInt16) | |
| `/Filling/Occupation/Occupied` | Variable | Boolean | False |
| `/Filling/Module` | Object | | |
| `/Filling/Module/Reset` | Method | (String) -> (Boolean, UInt16) | |
| `/Filling/Module/Start` | Method | (String) -> (Boolean, UInt16) | |
| `/Filling/Module/Stop` | Method | (String) -> (Boolean, UInt16) | |
| `/Filling/Module/Abort` | Method | (String) -> (Boolean, UInt16) | |
| `/Filling/Module/Clear` | Method | (String) -> (Boolean, UInt16) | |
| `/Filling/Module/State` | Variable | Byte | 2 |
| `/Filling/Equipment` | Object | | |
| `/Filling/Equipment/NeedleAxis` | Object | | |
| `/Filling/Equipment/NeedleAxis/AtTop` | Variable | Boolean | True |
| `/Filling/Equipment/NeedleAxis/AtBottom` | Variable | Boolean | False |
| `/Filling/Equipment/Scale` | Object | | |
| `/Filling/Equipment/Scale/Weight` | Variable | Double | 2.0 |
| `/Filling/Skills` | Object | | |
| `/Filling/Skills/MoveNeedleUp` | Object | | |
| `/Filling/Skills/MoveNeedleUp/Stop` | Method | (String) -> (Boolean, UInt16) | |
| `/Filling/Skills/MoveNeedleUp/Abort` | Method | (String) -> (Boolean, UInt16) | |
| `/Filling/Skills/MoveNeedleUp/Reset` | Method | (String) -> (Boolean, UInt16) | |
| `/Filling/Skills/MoveNeedleUp/State` | Variable | Byte | 0 |
| `/Filling/Skills/MoveNeedleUp/ErrorID` | Variable | UInt16 | 0 |
| `/Filling/Skills/MoveNeedleUp/Start` | Method | (String) -> (Boolean, UInt16) | |
| `/Filling/Skills/MoveNeedleDown` | Object | | |
| `/Filling/Skills/MoveNeedleDown/Stop` | Method | (String) -> (Boolean, UInt16) | |
| `/Filling/Skills/MoveNeedleDown/Abort` | Method | (String) -> (Boolean, UInt16) | |
| `/Filling/Skills/MoveNeedleDown/Reset` | Method | (String) -> (Boolean, UInt16) | |
| `/Filling/Skills/MoveNeedleDown/State` | Variable | Byte | 0 |
| `/Filling/Skills/MoveNeedleDown/ErrorID` | Variable | UInt16 | 0 |
| `/Filling/Skills/MoveNeedleDown/Start` | Method | (String) -> (Boolean, UInt16) | |
| `/Filling/Skills/AttachNeedle` | Object | | |
| `/Filling/Skills/AttachNeedle/Stop` | Method | (String) -> (Boolean, UInt16) | |
| `/Filling/Skills/AttachNeedle/Abort` | Method | (String) -> (Boolean, UInt16) | |
| `/Filling/Skills/AttachNeedle/Reset` | Method | (String) -> (Boolean, UInt16) | |
| `/Filling/Skills/AttachNeedle/State` | Variable | Byte | 0 |
| `/Filling/Skills/AttachNeedle/ErrorID` | Variable | UInt16 | 0 |
| `/Filling/Skills/AttachNeedle/Start` | Method | (String) -> (Boolean, UInt16) | |
| `/Filling/Skills/Dispense` | Object | | |
| `/Filling/Skills/Dispense/Stop` | Method | (String) -> (Boolean, UInt16) | |
| `/Filling/Skills/Dispense/Abort` | Method | (String) -> (Boolean, UInt16) | |
| `/Filling/Skills/Dispense/Reset` | Method | (String) -> (Boolean, UInt16) | |
| `/Filling/Skills/Dispense/State` | Variable | Byte | 0 |
| `/Filling/Skills/Dispense/ErrorID` | Variable | UInt16 | 0 |
| `/Filling/Skills/Dispense/Start` | Method | (String, Double, Double) -> (Boolean, UInt16) | |
| `/Filling/Skills/Dispense/Parameters` | Object | | |
| `/Filling/Skills/Dispense/Parameters/Volume` | Variable | Double | 1.0 |
| `/Filling/Skills/Dispense/Parameters/FlowRate` | Variable | Double | 1.0 |
| `/Filling/Skills/Tare` | Object | | |
| `/Filling/Skills/Tare/Stop` | Method | (String) -> (Boolean, UInt16) | |
| `/Filling/Skills/Tare/Abort` | Method | (String) -> (Boolean, UInt16) | |
| `/Filling/Skills/Tare/Reset` | Method | (String) -> (Boolean, UInt16) | |
| `/Filling/Skills/Tare/State` | Variable | Byte | 0 |
| `/Filling/Skills/Tare/ErrorID` | Variable | UInt16 | 0 |
| `/Filling/Skills/Tare/Start` | Method | (String) -> (Boolean, UInt16) | |
| `/Filling/Skills/Weigh` | Object | | |
| `/Filling/Skills/Weigh/Stop` | Method | (String) -> (Boolean, UInt16) | |
| `/Filling/Skills/Weigh/Abort` | Method | (String) -> (Boolean, UInt16) | |
| `/Filling/Skills/Weigh/Reset` | Method | (String) -> (Boolean, UInt16) | |
| `/Filling/Skills/Weigh/State` | Variable | Byte | 0 |
| `/Filling/Skills/Weigh/ErrorID` | Variable | UInt16 | 0 |
| `/Filling/Skills/Weigh/Start` | Method | (String) -> (Boolean, UInt16) | |
| `/Filling/Skills/Weigh/Results` | Object | | |
| `/Filling/Skills/Weigh/Results/Weight` | Variable | Double | 0.0 |
| `/Filling/Skills/Dispensing` | Object | | |
| `/Filling/Skills/Dispensing/Stop` | Method | (String) -> (Boolean, UInt16) | |
| `/Filling/Skills/Dispensing/Abort` | Method | (String) -> (Boolean, UInt16) | |
| `/Filling/Skills/Dispensing/Reset` | Method | (String) -> (Boolean, UInt16) | |
| `/Filling/Skills/Dispensing/State` | Variable | Byte | 0 |
| `/Filling/Skills/Dispensing/ErrorID` | Variable | UInt16 | 0 |
| `/Filling/Skills/Dispensing/Start` | Method | (String, Double) -> (Boolean, UInt16) | |
| `/Filling/Skills/Dispensing/Parameters` | Object | | |
| `/Filling/Skills/Dispensing/Parameters/Volume` | Variable | Double | 1.0 |
| `/Filling/Skills/Dispensing/Results` | Object | | |
| `/Filling/Skills/Dispensing/Results/Weight` | Variable | Double | 0.0 |
| `/Filling/Skills/Dispensing/Execute` | Object | | |
| `/Filling/Skills/Dispensing/Execute/MoveNeedleDown` | Object | | |
| `/Filling/Skills/Dispensing/Execute/MoveNeedleDown/State` | Variable | Byte | 0 |
| `/Filling/Skills/Dispensing/Execute/MoveNeedleDown/ErrorID` | Variable | UInt16 | 0 |
| `/Filling/Skills/Dispensing/Execute/Dispense` | Object | | |
| `/Filling/Skills/Dispensing/Execute/Dispense/State` | Variable | Byte | 0 |
| `/Filling/Skills/Dispensing/Execute/Dispense/ErrorID` | Variable | UInt16 | 0 |
| `/Filling/Skills/Dispensing/Execute/Dispense/Parameters` | Object | | |
| `/Filling/Skills/Dispensing/Execute/Dispense/Parameters/Volume` | Variable | Double | 1.0 |
| `/Filling/Skills/Dispensing/Execute/Dispense/Parameters/FlowRate` | Variable | Double | 1.0 |
| `/Filling/Skills/Dispensing/Execute/MoveNeedleUp` | Object | | |
| `/Filling/Skills/Dispensing/Execute/MoveNeedleUp/State` | Variable | Byte | 0 |
| `/Filling/Skills/Dispensing/Execute/MoveNeedleUp/ErrorID` | Variable | UInt16 | 0 |
| `/Filling/Skills/Dispensing/Execute/Weigh` | Object | | |
| `/Filling/Skills/Dispensing/Execute/Weigh/State` | Variable | Byte | 0 |
| `/Filling/Skills/Dispensing/Execute/Weigh/ErrorID` | Variable | UInt16 | 0 |
| `/Filling/Skills/Dispensing/Execute/Weigh/Results` | Object | | |
| `/Filling/Skills/Dispensing/Execute/Weigh/Results/Weight` | Variable | Double | 0.0 |
| `/Filling/Skills/Dispensing/Stopping` | Object | | |
| `/Filling/Skills/Dispensing/Stopping/MoveNeedleUp` | Object | | |
| `/Filling/Skills/Dispensing/Stopping/MoveNeedleUp/State` | Variable | Byte | 0 |
| `/Filling/Skills/Dispensing/Stopping/MoveNeedleUp/ErrorID` | Variable | UInt16 | 0 |
| `/Filling/Procedures` | Object | | |
| `/Filling/Procedures/Resetting` | Object | | |
| `/Filling/Procedures/Resetting/MoveNeedleUp` | Object | | |
| `/Filling/Procedures/Resetting/MoveNeedleUp/State` | Variable | Byte | 0 |
| `/Filling/Procedures/Resetting/MoveNeedleUp/ErrorID` | Variable | UInt16 | 0 |
| `/Filling/Procedures/Stopping` | Object | | |
| `/Filling/Procedures/Stopping/MoveNeedleUp` | Object | | |
| `/Filling/Procedures/Stopping/MoveNeedleUp/State` | Variable | Byte | 0 |
| `/Filling/Procedures/Stopping/MoveNeedleUp/ErrorID` | Variable | UInt16 | 0 |
