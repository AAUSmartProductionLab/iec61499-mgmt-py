# Filling and stoppering modules: from the ESP32 code to generated modules

Source: `arduino_cpp_examples/Physical-Stations` (PlatformIO; `FillingModule.cpp` on an ESP32,
`StopperingModule.cpp` on an ESP32-S3). Drafted and implemented 29 Sep 2026: the specs are
`modules/filling.yaml` and `modules/stoppering.yaml`, the generated 4diac projects
`4diac/FillingModule` and `4diac/StopperingModule`; both run against `4diac/tools/module_sim.py`
in `tests/test_module_live.py`. Not yet on the Pis (wiring, PWM overlay).

Decided 29 Sep 2026: we call them **modules** (not stations or units); each module runs on its
own Raspberry Pi 4 and is deployed on its own; orchestration only through OPC UA methods and
variables (MQTT may come back later as an option); PWM through a small FORTE module (plan M.2 in
[work.md](work.md#modules-on-the-two-pis-plan)).

## What goes where

The ESP32 code has three layers. Only the bottom one is module-specific.

| ESP32 code | Becomes | Why |
| --- | --- | --- |
| `ESP32Module` (WiFi, MQTT, NTP, UUID, AAS registration from `data/config.yaml`), `PackMLStateMachine` (states, Occupy/Release, Halt, state publishing) | Nothing new: the generic module level (occupation, module state manager, skill state machine, OPC UA facade) | Same for every module; generated |
| The functions registered as MQTT actions (`runFillingCycle`, `attachNeedle`, `tareScale`, `runStopperingCycle`) and the homing in `initHardware` | Module level skills (composites) and module procedures | Sequences of motions |
| Each motion with its stop condition (`moveToBottom`, `moveDCDown`, `runServo`, ...) | Skill primitives | One command on one equipment item until a sensor, a timer or a timeout |
| Pins, H-bridge direction bits, PWM duty, boost and brake pulses, servo angle | Equipment IO CFBs | They own the pins; skills only send commands |

## Filling module ("Dispensing", filling Pi)

**Equipment IO**

| Equipment | IO (ESP32 pin) | Commands |
| --- | --- | --- |
| `NeedleAxis`: DC motor through an L298N | out `Up` (IN3, 18), `Down` (IN4, 5), `Speed` PWM duty 0–255 (ENB, 19); in `AtTop` (39), `AtBottom` (36), both HIGH when pressed | `Stop`: all off. `Up`, `Down`: direction bit and `Speed` (140), starting with a boost (+50 for 200 ms). Stopping after a move: 100 ms reverse pulse, then off (brake) |
| `Scale` | none: the code draws a random weight (1.8–2.2 g) and fakes tare with a 2 s wait | simulated equipment with an output `Weight` |

**Skill primitives**

| Primitive | Equipment, command | Ends when | Timeout |
| --- | --- | --- | --- |
| `MoveNeedleUp` | NeedleAxis `Up` | `AtTop` | 8 s |
| `MoveNeedleDown` | NeedleAxis `Down` | `AtBottom` | 8 s |
| `Dwell(Duration = 1 s)` | none | time | – |
| `Tare` | Scale | done | 3 s |
| `Weigh` | Scale, publishes `Weight` | done | 3 s |

**Module level skills and procedures**

| Skill | Sequence | Today (MQTT action) |
| --- | --- | --- |
| `Dispensing` | MoveNeedleDown → Dwell(1 s) → MoveNeedleUp → Weigh | `/CMD/Dispensing` |
| `AttachNeedle` | MoveNeedleDown (the code does it without boost) | `/CMD/Needle` |
| `Tare` | the primitive itself | `/CMD/Tare` |
| Module procedure Resetting | MoveNeedleUp | `initHardware()` |

`Dwell` stands in for real dispensing. With a pump it becomes `Dispense(Volume)` on a pump item.

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

## What the generator needs for this

Iteration 1 covers only on/off outputs, sensor-ended primitives and one procedure. Needed, roughly in order:

1. **Valued outputs and commands with values**: a PWM duty or servo angle as an output (`LREAL`,
   range) and commands that set it (`Up: {Up: true, Speed: 140}`), including an argument passed
   by the skill (`MoveTo(Angle)`).
2. **Open-loop primitives**: `ends: after Duration` (a timer instead of a sensor), with
   `Duration` a parameter.
3. **Command profiles in the equipment**: start boost and brake pulse are equipment behaviour
   (`Up: [{Speed: 190, for: 200ms}, {Speed: 140}]`, `brake: {reverse: 100ms}`), so skills stay simple.
4. **Skills without equipment** (`Dwell`) and **simulated equipment** (`Scale`).
5. **Composites and module procedures** (iteration 2, steps 2.4 and 2.5), with parameters passed
   from composite to child (`MoveArm(Angle = 1)`).
6. **A PWM backend on the Pi** (below).

## IO on the Raspberry Pi

- **Digital in and out**: `GPIOChip` + `IX`/`QX`, verified on the lab Pi (blink).
- **PWM** (motor speed, servo): FORTE 3.3 has no PWM for Linux. Decided: a small FORTE module
  for Linux sysfs PWM (`/sys/class/pwm/pwmchipN`), one config FB `PWMChip` per channel like
  `GPIOChip`, used with the standard `QW` output FB (duty 0..65535; the servo angle is converted
  in the equipment IO CFB). It drives the Pi's two hardware channels (`dtoverlay=pwm-2chan`,
  GPIO12/13 or 18/19) and a PCA9685 16-channel board through the kernel `pwm-pca9685` driver.
  The servo needs a hardware channel or the PCA9685 (software PWM jitters). Effort and steps:
  plan M.2 in work.md.
- **Channel count** (one Pi per module): filling needs 1 PWM channel (needle speed); stoppering
  3 outputs (servo, piston and plunger enables), but both enables run at 200/255, so one channel
  drives both and the Pi's 2 hardware channels suffice. More: a PCA9685 board, same module.
- **Analog inputs**: none needed by these two modules (the weight is simulated). Later: an ADC
  with a Linux IIO driver (ADS1115, MCP3008) read by the same kind of module (`IW`).
- **Wiring**: L298N logic inputs accept 3.3 V; the end switches read HIGH when pressed (wired to
  3.3 V, pull-down on the Pi instead of the ESP32's pull-up).

## Interface to the orchestrator

Decided: OPC UA methods and variables, as the generated modules have them (Occupy/Release,
module Reset/Start/Stop/Abort/Clear, skill Start/Stop/Abort/Reset with parameters, State and
ErrorID variables). The ESP32s' MQTT topics (`NN/Nybrovej/InnoLab/<Module>/CMD/<Action>` with
a JSON `Uuid`, answers on `/DATA/...`) are not carried over; an MQTT facade may be added later
as an option, since FORTE has MQTT.
