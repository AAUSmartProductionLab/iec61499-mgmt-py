# Filling and stoppering modules: from the ESP32 code to generated modules

Source: `arduino_cpp_examples/Physical-Stations` (PlatformIO; `FillingModule.cpp` on an ESP32,
`StopperingModule.cpp` on an ESP32-S3; a local reference copy, not in the repository). The
specs are `cell/modules/filling.yaml` and `cell/modules/stoppering.yaml`, the generated 4diac
projects `cell/control/FillingModule` and `cell/control/StopperingModule`. Both run against the
simulator (`cell/sim/module_sim.py`) in `cell/tests/`, and on the lab Pi's FORTE with the
simulator as IO; the motors, switches and servo are not wired yet.

We call them **modules** (not stations or units). Each module runs on its own Raspberry Pi 4 and
is deployed on its own; it is orchestrated only through OPC UA methods and variables (MQTT may
come back later as an option). The structure of a generated module is in [work.md](work.md).

## What goes where

The ESP32 code has three layers. Only the bottom one is module-specific.

| ESP32 code | Becomes | Why |
| --- | --- | --- |
| `ESP32Module` (WiFi, MQTT, NTP, UUID, AAS registration from `data/config.yaml`), `PackMLStateMachine` (states, Occupy/Release, Halt, state publishing) | Nothing new: the generic module level (occupation, module state manager, skill state machine, OPC UA facade) | Same for every module; generated |
| The functions registered as MQTT actions (`runFillingCycle`, `attachNeedle`, `tareScale`, `runStopperingCycle`) and the homing in `initHardware` | Module level skills (composites) and module procedures | Sequences of motions |
| Each motion with its stop condition (`moveToBottom`, `moveDCDown`, `runServo`, ...), with its H-bridge direction bits, PWM duty, boost and brake pulses or servo angle | Skill primitives, each with the command table of its equipment (`EC_<Equipment>`) | One command on one equipment item until a sensor, a timer or a timeout |
| Pins | Equipment IO CFBs | They own the pins and write what their one holder sends; they know nothing about what the pins mean |

## Filling module ("Dispensing", filling Pi)

Since 8 Oct 2026 the module is built from the components every module of the line is built from
(a linear axis and one process component), no longer as the ESP32 station was: the needle is lifted
by a stepper motor with a limit switch, as on a 3D printer. The pins below are a proposal until the
driver is wired; the speed and the travel are placeholders until the axis is measured.

**Equipment IO** (each item is a component of the module, of a kind that other modules have too)

| Equipment (kind) | IO (Pi pin) | Commands |
| --- | --- | --- |
| `LinearAxis` (LinearAxis): stepper motor through a step and direction driver | out `Enable` (GPIO17, pin 11), `Down` (the driver's DIR, GPIO27, pin 13), `Step` (PWM0 on GPIO18, pin 12: 1 kHz, 50 % while it moves); in `AtHome` (limit switch at the top, GPIO23, pin 16) | `Stop`: all off. `Up`, `Down`: enabled and stepping, with the direction. `MoveTo(position)`: see below |
| `Pump` (FillingPump) | none yet | `Run`: nothing to switch, so dispensing is a time |
| `Scale` (Scale) | none: the weight is simulated | simulated equipment with a value `Weight` |

**The axis knows its position without measuring it.** A stepper moves a known distance per step,
so the controller keeps the position itself: at the limit switch it is 0 (`Homed`), and while the
axis is stepping it changes at the axis' speed (20 mm/s here). The equipment block publishes
`ActualPosition`, `Homed` and `Moving`. Told to move to a position, it compares that with where it
is, drives up or down, stops after the time the distance takes and is there. A move that is cut
short leaves the position the elapsed time gives (to about a millimetre); driving the axis any
other way (homing that is cut short) leaves the position unknown until it has been at the switch
again. A blocked axis is noticed only when it is to find the switch: nothing measures a move.

**Skill primitives**

| Primitive | Equipment, command | Ends when | Timeout |
| --- | --- | --- | --- |
| `Home` | LinearAxis `Up` | `AtHome` | 8 s |
| `MoveAxis(Position = 0..60 mm)` | LinearAxis `MoveTo`; needs `Homed` | it is there | 8 s |
| `Dispense(Volume, FlowRate = 1 mL/s)` | Pump `Run` | time: Volume / FlowRate | – |
| `Tare` | Scale | after 2 s | – |
| `Weigh` | Scale, publishes `Weight` | after 0.2 s | – |

**Module level skills and procedures**

| Skill | Sequence |
| --- | --- |
| `Dispensing(Volume = 1 mL)` | MoveAxis(40 mm) → Dispense(Volume) → MoveAxis(0 mm) → Weigh; when stopped: Home |
| Module procedure Resetting | Home → Tare |
| Module procedure Stopping | Home |

`MoveAxis` is used twice in Dispensing, as the steps `NeedleDown` and `NeedleUp`; where each goes
is a constant of the step that reconfiguration can change, like the flow rate of `Dispense`. The
Filling capability's FillVolume is set by Dispensing's Volume. Gone with the DC motor: the skills
`MoveNeedleUp`, `MoveNeedleDown` and `AttachNeedle`, and the start boost and brake pulses. A plain
wait (`Dwell`) was removed on 8 Oct 2026: no skill used it.

## Stoppering module (stoppering Pi)

**Equipment IO**

| Equipment | IO (ESP32-S3 pin) | Commands |
| --- | --- | --- |
| `Piston`: DC motor through an L298N | out `Up` (IN3, 39), `Down` (IN4, 40), `Speed` PWM 200/255 (ENB, 41); in `AtLimit` (4, limit switch at the working position) | `Stop`, `Up`, `Down` |
| `Plunger`: linear actuator through an L298N | out `Extend` (IN2, 16), `Retract` (IN1, 17), `Speed` PWM 200/255 (ENA, 18); no sensors | `Stop`, `Extend`, `Retract` |
| `StopperArm`: servo | out `Angle` 0–180° (pin 2, 50 Hz PWM); no feedback | `MoveTo(Angle)`, `Release` (detach, no holding torque) |

**Skill primitives**

| Primitive | Equipment, command | Ends when | Timeout |
| --- | --- | --- | --- |
| `LowerPiston` | Piston `Down` | `AtLimit` | 10 s |
| `RaisePiston(Duration = 2 s)` | Piston `Up` | time (open loop) | – |
| `ExtendPlunger(Duration = 10 s)` | Plunger `Extend` | time | – |
| `RetractPlunger(Duration = 6.5 s)` | Plunger `Retract` | time | – |
| `MoveArm(Angle, Settle = 2 s)` | StopperArm `MoveTo(Angle)` | time | – |

**Module level skills and procedures**

| Skill | Sequence | Today |
| --- | --- | --- |
| `Stoppering` | LowerPiston → MoveArm(1°) → MoveArm(121°) → ExtendPlunger(10 s) → RetractPlunger(6.5 s) → RaisePiston(2 s) | `/CMD/Stoppering` |
| Module procedure Resetting | MoveArm(90°) → MoveArm(120°) → RetractPlunger(6.5 s) → LowerPiston → RaisePiston(1.5 s) | `initHardware()` |

## IO on the Raspberry Pi

- **Digital in and out**: `GPIOChip` + `IX`/`QX` (one FB per line).
- **PWM** (motor speed, servo): FORTE 3.3 has none for Linux, so the runtime carries a small
  module for Linux sysfs PWM (`runtime/forte-patches/0002-pwmsysfs-module.patch`): one config FB
  `PWMChip` per channel, used with the standard `QW` output FB (duty 0..65535; the servo angle is
  converted by the generated IO block). It drives the Pi's two hardware channels
  (`dtoverlay=pwm-2chan`, PWM0 on GPIO18, PWM1 on GPIO19) and would drive a PCA9685 board through
  the kernel `pwm-pca9685` driver. Tested on the aarch64 binary under emulation and on the lab Pi.
- **Channel count** (one Pi per module): filling needs 1 PWM channel (needle speed); stoppering
  3 outputs (servo, piston and plunger enables), but both enables run at 200/255, so one channel
  drives both and the Pi's 2 hardware channels suffice.
- **Analog inputs**: none needed by these two modules (the weight is simulated). Later: an ADC
  with a Linux IIO driver (ADS1115, MCP3008) read by the same kind of module (`IW`).
- **Wiring**: L298N logic inputs accept 3.3 V. The end switches are wired as on the ESP32
  (to GND, internal pull-up, pressed = TRUE; `bias: pull_up` in the spec). The pin of every IO
  point is in the module spec, next to the ESP32 pin it replaces.

## Interface to the orchestrator

Decided: OPC UA methods and variables, as the generated modules have them (Occupy/Release,
module Reset/Start/Stop/Abort/Clear, skill Start/Stop/Abort/Reset with parameters, State and
ErrorID variables). The ESP32s' MQTT topics (`NN/Nybrovej/InnoLab/<Module>/CMD/<Action>` with
a JSON `Uuid`, answers on `/DATA/...`) are not carried over; an MQTT facade may be added later
as an option, since FORTE has MQTT.
