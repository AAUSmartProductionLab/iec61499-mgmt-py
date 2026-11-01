# The demo's other modules: capping, inspection, loading and unloading

Plan of 1 Nov 2026 for the demo in January ([framework-plan.md](framework-plan.md), section 7.2).
Two modules run now, filling and stoppering ([modules.md](modules.md)); the line has six. This file
says how the other four are built.

Each is built as the filling module is: a Raspberry Pi 5 with FORTE and ModLib, the program and the
AAS generated from the module's spec, occupation, the PackML module state and the skills over OPC UA,
announced by mDNS. Either orchestrator runs them as it runs the filling module. What differs is what
stands behind the equipment's IO points:

| Module | Behind its points | New for it |
| --- | --- | --- |
| Capping | A stepper axis on the Pi's pins, as filling's; the crimper simulated | A spec and a Pi |
| Inspection | Two cameras and their evaluation, in Python on the Pi | Python beside FORTE (section 2); an image store on the server |
| Loading, Unloading | A KUKA robot each, running a program written by hand | Python beside FORTE, talking to the robot controller over the network |

## 1. Decided (1 Nov, yours)

- **Capping works as the filling module:** a linear axis on a stepper. A second actuator crimps; for now
  it is simulated.
- **Loading and unloading:** a Raspberry Pi per KUKA robot, set up as a module like the others. It
  talks to the robot over a network protocol, not GPIO. The robot programs are written by hand; the
  module only says what the robot is to do, starts it and waits for it.
- **Inspection is triggered over OPC UA** like every module. The images go from the module straight to
  a store made for them, not through OPC UA.
- **The centralized orchestrator is not built here** (section 6).

What follows is proposed; the open points are in section 8.

## 2. Python beside FORTE

The cameras need Python (capture, evaluation, upload), and a robot's protocol is quicker written in
Python than in IEC 61499 blocks. [python61499](https://github.com/suppress-unileon/python61499)
(Universidad de León) does this for EcoStruxure Automation Expert: a block sends a request over TCP to
a Python server, which runs a task and answers. For FORTE there are four ways:

| Way | How | Against |
| --- | --- | --- |
| [DINASORE](https://github.com/DIGI2-FEUP/dinasore) (FEUP) | A runtime of its own that runs blocks written in Python, with the 4diac IDE as its editor | A second runtime: it cannot run ModLib's C++ blocks, so a module would be split across two; no licence stated |
| Python inside FORTE | A block type in C++ that embeds CPython | A Python interpreter cross-built into the static aarch64 binary; a fault in Python stops the module's control |
| python61499's way on FORTE | FORTE's own `CLIENT_n_m` sends the request over TCP, in the typed ASN.1 encoding of its `fbdk` layer, to a Python server and waits for the answer | No Python library speaks that encoding (a small one to write); a new kind of primitive in `modgen`: a call, not a command on points |
| **A Python service that serves the equipment's points** (proposed) | The service is a Modbus TCP server on the Pi; FORTE reaches its points as it reaches the simulator's on the PC (`modbus[...]`) | Numbers and booleans only; the points are polled (every 10 ms) |

**Proposed: the last.** It needs no new block, no change to `modgen` and no change to the runtime:
- FORTE for the Pi is already built with Modbus, and with raw TCP, HTTP, MQTT and OPC UA
  (`FORTE_COM_*` in the build of `pi/modules-pi`).
- A Pi target with `io: gpio` and a `modbus` server already puts the points that have a pin on the
  pins and the others on that server (`Target.backend` in `modgen/spec.py`). So a module's axis stays
  on the pins while its camera's points go to the service.
- On the PC the simulator (`cell/sim/module_sim.py`) serves the same points. The program is the same
  in simulation and on the Pi; only what answers differs.

An **equipment service** is a Python process in a container beside FORTE's (host network,
`deploy/pi`), one per module. It reads its points from the module's spec, as the simulator does, and
runs a handler when an output changes: a camera's `Trigger`, a robot's `Start`. Its base is shared with
the simulator and goes with `modgen` (`iec61499-skill-lib`). Points are `BOOL` or `LREAL` in `modgen`:
a job number or an image number is an `LREAL` point on a register, as the scale's weight is.

When a call needs text or structures, python61499's way comes next, answered by the same service. The
demo does not need it.

## 3. Loading and unloading: the robot modules

### 3.1 The robot's side: one program, a job number

The robot runs one program that waits for a job and runs it (the second of the ways you named: states
in one program). A job is a number; each starts a routine of the program: pick from the tray, place on
the shuttle, home. This is instead of selecting programs from outside. KUKA's way to select a program
from outside is Automatic External, by program number on digital inputs (`PGNO`, `PGNO_VALID`,
`EXT_START`). The network interfaces below write variables; they do not select programs. One program
stays running, so a job starts at once.

The contract between the module and the robot program, the same whatever carries it:

| Point | Direction | Type | Meaning |
| --- | --- | --- | --- |
| `Job` | to the robot | number | Which routine; 0 none |
| `Start` | to the robot | BOOL | Run `Job`; the robot takes it on the rising edge |
| `Ready` | from the robot | BOOL | The program runs and waits for a job, and the robot may move (mode, drives) |
| `Busy` | from the robot | BOOL | A job runs |
| `Done` | from the robot | BOOL | The job ended well; cleared when `Start` falls |
| `Error` | from the robot | BOOL | The job failed, with `ErrorCode` (a number) |

**The handshake:**
1. The module sets `Job`, then `Start`.
2. The robot answers `Busy`, then `Done` (or `Error`).
3. The module drops `Start`, and the robot clears `Done`.

This is the usual handshake between a PLC and a robot, and it fits a primitive as `modgen` has them: a
command that sets `Job` and `Start`, the postcondition `Done`, the invariant `NOT Error` (a broken
invariant ends the skill), a timeout. The robot keeps its own safety: the Pi starts jobs only in the
operating mode the operator chose, and moves nothing itself.

For the demo the robot program counts the tray's slots itself. A slot as a parameter of the job comes
later (the skill's `arg` written into a point).

### 3.2 How the Pi reaches the robot

Which interface depends on what the robot controllers have. That is checked first (step M0):
- the controller: KR C4, KR C4 compact, KR C5, or Sunrise for an LBR iiwa;
- its KSS version;
- its option packages;
- whether it has free digital IO.

| The controller has | The equipment service talks | The robot program |
| --- | --- | --- |
| KUKA.Ethernet KRL (EKI) | XML over TCP; the robot is the server, the service connects | An EKI configuration with the contract's elements, and `EKI_` calls in the program |
| KUKA.OPC UA, or KUKA.DeviceConnector (installed on a KR C5) | OPC UA: the contract as global variables of the program | The variables in `$config.dat`, exposed by the option |
| Neither | KukaVarProxy (TCP 7000, global variables): not KUKA's, a program on the controller's Windows, which KUKA advises against | The variables in `$config.dat` |
| An LBR iiwa (Sunrise) | TCP to a socket the robot application opens | A Java application |

**Proposed: EKI or OPC UA, whichever the controllers have** (both are option packages under licence).
KukaVarProxy only to start with if neither is there. Without any network option the fallback is
digital IO with Automatic External: the Pi's pins through 24 V optocouplers. The generator already does
pins, but that is the wiring you want to avoid.

With the service in between, the module's program and AAS do not change with the interface; only the
service does. If the controller speaks OPC UA, FORTE could later reach it directly (an `opc_ua[...]`
backend for IO points in `modgen.library`) and the service would go. The demo does not need that.

### 3.3 The two modules

| Module | Components | Primitives (one per job) | Composite |
| --- | --- | --- | --- |
| Loading | Robot (the gripper is part of the robot's jobs) | `Home`, `PickFromTray`, `PlaceOnShuttle` | `Loading`: pick, place, home |
| Unloading | Robot | `Home`, `PickFromShuttle`, `PlaceInTray` | `Unloading`: pick, place, home |

Each spec (`cell/modules/loading.yaml`, `unloading.yaml`) names:
- the robot's points, with a Modbus address for the service and the simulator;
- the jobs as commands (`PickFromTray: {Job: 2, Start: true}`);
- the transfer point where a shuttle stands;
- the capability.

Loading is where a product's custody begins ([agents.md](agents.md), section 6). The loading module
releases the vial to the shuttle (Releasing) and the shuttle receives it (Receiving); unloading is the
reverse.

### 3.4 In simulation

The simulator answers the contract as the robot would: `Busy` for the job's time, then `Done`. So the
line runs with six modules on the PC before a robot is connected. A stand-in controller (an EKI or OPC
UA server in Python) tests the robot service without the robot.

## 4. Capping

**Like the filling module (decided):**
- the linear axis lowers the crimping head;
- it runs on a stepper through a TB6600, with a limit switch, and is homed the same way;
- the crimper's `Close` is simulated (`sim`) for now, its time given by `Duration`.

`cell/modules/planned/capping.yaml` already has these components and skills. It moves to
`cell/modules` with a Pi target written as filling's (pins, PWM channel, `board: pi5`).

The hardware: a Pi 5, a TB6600, a stepper on a stage and a limit switch. A real crimper later is an
output on a pin (a valve or a relay) or a servo; the skill stays.

## 5. Inspection

### 5.1 The module

Triggered over OPC UA like every module (decided), with the skills of
`cell/modules/planned/inspection.yaml`: `CaptureTop`, `CaptureSide` and the composite `Inspection`.
Each camera's points are served by the module's equipment service: `Trigger` to it; `Done`, `Passed`
and `ImageNo` from it.

On `Trigger` the service:
1. takes the image;
2. evaluates it (a simple check first; the evaluation is the service's, not the program's);
3. sends the image to the store;
4. sets `ImageNo`, `Passed` and `Done`.

The skill's results are `Passed` and `ImageNo`.

A Pi 5 takes two cameras on its own camera ports (picamera2), or USB cameras (OpenCV). Which cameras
is open.

### 5.2 The images

The service sends the image to the store over HTTP, not through IEC 61499 or OPC UA:
- an S3 `PUT` of a JPEG, one object per image;
- named by module, camera and number: `inspection/<Module>/<Camera>/<ImageNo>.jpg`;
- the time and the skill call kept as the object's metadata.

IEC 61499 carries only the verdict and the number. AP2030-UNS sent each image base64 in an MQTT
message instead.

**The store, proposed: SeaweedFS** in the lab stack (`deploy/aas`): one node, the S3 API on port 8333,
Apache 2.0. MinIO's open-source edition has published no images since October 2025 and was archived
in April 2026. Garage (AGPL) is the other choice.

**The AAS says where the images are, not what they are:**
- The camera's Asset Interfaces Description gets a second interface, HTTP, with the image as a
  property at a URL template (`{ImageNo}`).
- A skill's results go into the time series as every result does (the DMP, InfluxDB), so each image's
  number is there with its skill call.
- No image and no live value goes into the AAS ([decisions.md](decisions.md), 28 Oct).
- The product's batch record (its instance AAS, planned) refers to its images.

A live view of the cameras for the demo is a separate thing: MJPEG over HTTP from the service, or RTSP
through MediaMTX. The inspection itself does not need it.

## 6. The centralized orchestrator

**Not built here (1 Nov): the colleagues build it.** Our part is to keep what both orchestrators share
as it is:
- a module is run only through its skills over OPC UA: occupy, Execute, start, wait, release;
- its AAS describes it;
- nothing of the four modules above can be reached another way. A robot, a camera or a crimper is
  never commanded by an orchestrator directly; it is behind its module.

So the new modules need nothing for the BT controller that the filling module does not.

## 7. Steps

| # | Step | Needs | Done when |
| --- | --- | --- | --- |
| M0 | The robot controllers: model, KSS version, option packages (Ethernet KRL, OPC UA, DeviceConnector), free digital IO | You, at the robots | The interface of 3.2 is chosen |
| M1 | The equipment service: its base shared with the simulator, a container in `deploy/pi`; a Pi target with pins and a local Modbus server tried on a Pi | – | One program on a Pi has a point on the service and one on a pin |
| M2 | Capping: the spec moved to `cell/modules`, the program generated and run with the simulator; then on its Pi | A Pi 5, a TB6600, a stepper, a switch; you at the bench for the axis | `Capping` runs on the Pi with the axis moving and the crimper simulated |
| M3 | Loading and unloading: the contract with your program, the specs, the simulator's robot; in the agents, loading as the step that starts custody ([agents.md](agents.md), A1) | Your robot program's job numbers | The line in simulation takes a vial from loading to unloading |
| M4 | The robot service over the chosen interface, with a stand-in controller in the tests; then on each robot | M0; you at the robot | `Loading` moves the robot, started by the agents |
| M5 | Inspection: the spec, the camera service, the store in the lab stack, the camera's HTTP interface in its AAS | The cameras | Each camera's image is in the store, with its number in the skill's results |
| M6 | The six modules in the line scenario with the agents (A1, A7) | M2 to M5 in simulation | The three products' orders run end to end in simulation |

## 8. Open

| # | Question | Recommendation |
| --- | --- | --- |
| 1 | Python beside FORTE: a service that serves the equipment's points over Modbus (section 2), or python61499's request and answer over FORTE's `CLIENT` | The service now; the request and answer when a call needs text |
| 2 | The robot: one program with job numbers, or programs selected from outside | One program (3.1) |
| 3 | The robot's interface | After M0: EKI or OPC UA, whichever the controllers have |
| 4 | The image store | SeaweedFS |
| 5 | The gripper: inside the robot's jobs, or a component of the module with an AAS of its own | Inside the jobs for the demo |
| 6 | A module stopped during a job: the robot finishes the job, or the program also takes an abort | It finishes the job; the robot's own stop stays for emergencies |
| 7 | Which cameras: Pi camera modules or USB, and their lenses | – |
