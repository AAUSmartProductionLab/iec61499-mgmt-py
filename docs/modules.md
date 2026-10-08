# Filling and stoppering modules

The specs are `cell/modules/filling.yaml` and `cell/modules/stoppering.yaml`, the generated 4diac
projects `cell/control/FillingModule` and `cell/control/StopperingModule`. Both run against the
simulator (`cell/sim/module_sim.py`) in `cell/tests/`; the motors and switches are not wired yet.

Both began as ports of ESP32 stations (`arduino_cpp_examples/Physical-Stations`: `FillingModule.cpp`,
`StopperingModule.cpp`; a local reference copy, not in the repository). Since 8 Oct 2026 they are
built from the components every module of the line is built from: a **linear axis** (a stepper
motor with a limit switch, moved to a position, with the same two skills in every module) and one
process component (the filling pump, the stoppering piston). The line is six modules:

| Module | Components | State |
| --- | --- | --- |
| Loading | Kuka robot, gripper | not described yet; the robot has its own Raspberry Pi |
| Filling | filling pump, linear axis (and a simulated scale) | generated, runs on FORTE with the simulator |
| Stoppering | stoppering piston, linear axis | generated, runs on FORTE with the simulator |
| Capping | cap crimper, linear axis | planned: `cell/modules/planned/capping.yaml`, no program |
| Inspection | top camera, side camera | planned: `cell/modules/planned/inspection.yaml`, no program |
| Unloading | Kuka robot, gripper | not described yet; the robot has its own Raspberry Pi |

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
by a stepper motor with a limit switch, as on a 3D printer. It runs on a Raspberry Pi 5
(192.168.0.134), the stoppering module on the Raspberry Pi 4 (192.168.0.191). The Pi pins below
are a proposal until the driver is wired; the speed and the travel are placeholders until the axis
is measured.

**The stepper driver** is a RepRap Stepper Motor Driver v2.3 with an Allegro A3982
([reprap.org](https://reprap.org/wiki/Stepper_Motor_Driver_2.3)). Its 10-pin interface, and what
the module's equipment item connects to it:

| Board pin | Signal | Equipment signal | Note |
| --- | --- | --- | --- |
| 2, 8–10 | GND | – | common ground with the Pi |
| 3 | Step | `Step` | one step per pulse: the Pi's PWM at 1 kHz while the axis moves |
| 4 | Dir | `Down` | high is "forward"; which way that is depends on how the motor is connected |
| 5 | !Enable | `Enable` | inverted and pulled high on the board: the motor is on while the line is low, so the Pi's line is set active low |
| 6, 7 | Min, Max | not used | the board only passes the signals of its own endstop sockets through to these pins; it does not act on them |

The home switch is an ordinary limit switch at the top, wired straight to the Pi: between GPIO23
(Pi pin 16) and GND, closing when pressed. The Pi's pull-up holds the line high otherwise, and the
line is set active low, so `AtHome` is true while the switch is pressed. The trimpot on the board
sets the motor current, not the step size.

To check before wiring (not stated on that page; from the A3982's data sheet as I remember it, so
verify): the board feeds its logic and the endstops with 5 V from its own regulator. A high input
then needs 3.5 V, more than the Pi's 3.3 V gives for certain, and the endstop signal is 5 V, more
than a Pi input tolerates. A level shifter between the Pi and the board solves both. The A3982 does
full or half steps (its MS1 input); which one the board is set to decides the steps per millimetre
together with the screw.

**Equipment IO** (each item is a component of the module, of a kind that other modules have too)

| Equipment (kind) | IO (Pi pin) | Commands |
| --- | --- | --- |
| `LinearAxis` (LinearAxis): stepper motor through the driver board above | out `Enable` (GPIO17, Pi pin 11, active low), `Down` (GPIO27, Pi pin 13), `Step` (PWM0 on GPIO18, Pi pin 12: 1 kHz, 50 % while it moves); in `AtHome` (GPIO23, Pi pin 16) | `Stop`: all off. `Up`, `Down`: enabled and stepping, with the direction. `MoveTo(position)`: see below |
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
| `Dispensing(Volume = 1 mL)` | MoveAxis(40 mm) → Dispense(Volume) → Home → Weigh; when stopped: Home |
| Module procedure Resetting | Home → Tare |
| Module procedure Stopping | Home |

The needle goes back up by homing, after every operation: a position that is counted, not
measured, drifts a little with every move, and the switch takes that out again. Where `MoveAxis`
goes (the step `NeedleDown`) is a constant of the step that reconfiguration can change, like the
flow rate of `Dispense`. The speed in the description (20 mm/s) assumes a screw of 8 mm per turn
and half steps at 1 kHz; measure a move and correct it. The
Filling capability's FillVolume is set by Dispensing's Volume. Gone with the DC motor: the skills
`MoveNeedleUp`, `MoveNeedleDown` and `AttachNeedle`, and the start boost and brake pulses. A plain
wait (`Dwell`) was removed on 8 Oct 2026: no skill used it.

## Stoppering module (stoppering Pi)

Built like the filling module since 8 Oct 2026: the head is brought down onto the vial by a linear
axis, and one small linear actuator presses the stopper in. The ESP32 station's three drives (a
piston on a DC motor, a servo arm, a plunger) are gone. Pins, speed, travel and stroke times are
placeholders until the hardware is wired and measured.

**Equipment IO**

| Equipment (kind) | IO (Pi pin) | Commands |
| --- | --- | --- |
| `LinearAxis` (LinearAxis): stepper motor through a step and direction driver | as the filling module's axis: out `Enable` (GPIO17), `Down` (GPIO27), `Step` (PWM0, GPIO18); in `AtHome` (GPIO23) | `Stop`, `Up`, `Down`, `MoveTo(position)` |
| `Piston` (StopperingPiston): small linear actuator through an L298N | out `Retract` (IN1, GPIO5, pin 29), `Extend` (IN2, GPIO6, pin 31); no sensors | `Stop`, `Extend`, `Retract`, `Back`: in for the stroke (3 s), then off |

**Skill primitives**

| Primitive | Equipment, command | Ends when | Timeout |
| --- | --- | --- | --- |
| `Home` | LinearAxis `Up` | `AtHome` | 8 s |
| `MoveAxis(Position = 0..60 mm)` | LinearAxis `MoveTo`; needs `Homed` | it is there | 8 s |
| `PressStopper` | Piston `Extend`, then `Back` | time: 3 s out, 3 s back in | – |
| `RetractPiston` | Piston `Retract` | time: 3 s | – |

`PressStopper` ends with the command `Back` whether it finishes or is stopped, so a press that is
cut short still draws the piston in. An abort switches everything off where it is; `RetractPiston`
is for that case and runs first when the module resets.

**Module level skills and procedures**

| Skill | Sequence |
| --- | --- |
| `Stoppering` | MoveAxis(40 mm) → PressStopper → Home; when stopped: Home |
| Module procedure Resetting | RetractPiston → Home |
| Module procedure Stopping | Home |

## IO on the Raspberry Pi

- **Digital in and out**: `GPIOChip` + `IX`/`QX` (one FB per line).
- **PWM** (motor speed, servo): FORTE 3.3 has none for Linux, so the runtime carries a small
  module for Linux sysfs PWM (`runtime/forte-patches/0002-pwmsysfs-module.patch`): one config FB
  `PWMChip` per channel, used with the standard `QW` output FB (duty 0..65535; the servo angle is
  converted by the generated IO block). It drives the Pi's two hardware channels
  (`dtoverlay=pwm-2chan`, PWM0 on GPIO18, PWM1 on GPIO19) and would drive a PCA9685 board through
  the kernel `pwm-pca9685` driver. Tested on the aarch64 binary under emulation and on the lab Pi.
- **Channel count** (one Pi per module): each module needs 1 PWM channel, for the step pulses of
  its linear axis (PWM0 at 1 kHz, one step per period, 50 % duty while it moves). The piston's
  L298N enable is tied high. A pump on a stepper would take the Pi's second hardware channel.
- **Step pulses by PWM**: the controller does not count pulses, it counts the time the PWM is on.
  A step rate of 1 kHz and the 1 ms it takes to switch give a position to a few steps; how many
  millimetres that is depends on the driver's microstepping and the screw, which are not known yet.
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
