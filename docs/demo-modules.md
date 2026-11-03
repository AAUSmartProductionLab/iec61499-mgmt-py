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
| Capping | A stepper axis on the Pi's pins, as filling's; the crimper simulated | A Pi (the spec and its program since 3 Nov) |
| Inspection | A USB camera and its evaluation, in Python on the Pi | Python beside FORTE (section 2); an image store on the server |
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

Your answers to the plan's first questions, later on 1 Nov:
- **Python beside FORTE:** the equipment service over Modbus (section 2), as the start to test with.
- **The robot runs one program and takes a job number** (section 3.1).
- **The gripper runs on the robot's own IO**, switched by the robot program inside its jobs.
- **A module stopped during a robot job:** the robot finishes the job.
- **The image store: SeaweedFS**, on the server that runs the AAS server (section 5.2).
- **The camera is a USB FPV camera** (section 5.1).
- **The robot controllers are KR C4s.** What they have installed is checked on Monday 2 Nov (step M0).

The rest is proposed; the open points are in section 8.

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

**Decided (1 Nov): the last, as the start to test with.** It needs no new block, no change to `modgen` and no change to the runtime:
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

**Decided (3 Nov, yours): the robot modules run in Python.** Each robot has a Raspberry Pi that runs
a Python process: an OPC UA server with the same occupation, module state and skills as every other
module, its skills selecting jobs of the robot program instead of being IEC 61499 blocks. Several
modules may share a Pi for a while (the planar controller and the robots), each on a port of its own
or together in one server.

**Built (3 Nov): `module-py/` (`modpy`).** It runs a module spec as the generated program runs it on
FORTE (the module rules' state machines, the primitives, flows and procedures with their semantics)
and serves it node for node as FORTE does (namespace 1, `RD_n`/`SD_n` arguments, steps and
procedures). The agents, the DMP, modlink and discovery drive it as any module; modreg describes it
from its spec (`modreg/pymodules.py`), without the rule set. The specs are in
`cell/modules/python/`; the robots are simulated until their interface is chosen (3.2):

    python -m modpy serve cell/modules/python/loading.yaml cell/modules/python/unloading.yaml --port 4840

This replaces FORTE plus an equipment service for the robots (section 2 stays for the cameras).

### 3.1 The robot's side: one program, a job number

The robot runs one program that waits for a job and runs it (decided 1 Nov; the second of the ways you
named: states in one program). A job is a number; each starts a routine of the program: pick from the tray, place on
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
| `JobDone` | from the robot | number | Which job ended with `Done`; cleared with it (3 Nov) |
| `Error` | from the robot | BOOL | The job failed, with `ErrorCode`; cleared when `Start` falls |
| `ErrorCode` | from the robot | number | Why the last job failed; kept until the next job starts |

**The handshake:**
1. The module sets `Job` with `Start` off (200 ms), then `Start`.
2. The robot answers `Busy`, then `Done` with `JobDone` (or `Error` with `ErrorCode`).
3. The module drops `Start`, and the robot clears `Done`, `JobDone` and `Error`.

`JobDone` (added 3 Nov): a skill's postcondition is checked before its command, and a skill whose
postcondition already holds is done at once (a move to where the axis is). A `Done` left from the
job before, read before the robot has cleared it, would so end the next job unstarted; `Done AND
JobDone = 3` holds only for job 3. The 200 ms with `Start` off give the robot a falling edge between
two jobs.

This is the usual handshake between a PLC and a robot, and it fits a primitive as `modgen` has them: a
command that sets `Job` and then `Start`, the postcondition `Done AND JobDone = <job>`, the
invariant `NOT Error` (a broken invariant ends the skill), a timeout. The robot keeps its own safety: the Pi starts jobs only in the
operating mode the operator chose, and moves nothing itself. A module stopped during a job lets the
robot finish it (decided 1 Nov); the robot's own stop stays for emergencies. In the specs that is
`AwaitJob` (the command `Await` sets nothing, until `NOT Busy`): the Stopping procedure and each
module level skill's stop flow, and Resetting before `Home`.

For the demo the robot program counts the tray's slots itself. A slot as a parameter of the job comes
later (the skill's `arg` written into a point).

### 3.2 How the Pi reaches the robot

The controllers are KR C4s. **On a KR C4 no interface for an outside program is guaranteed:** KUKA's
network interfaces (Ethernet KRL, OPC UA, DeviceConnector, PROFINET, EtherNet/IP) are option packages
under licence. Every KR C4 has these:
- the KLI Ethernet port (for WorkVisual);
- EtherCAT as its system bus;
- Automatic External in its base software.

Its user IO depends on the IO modules fitted. The gripper runs on the robot's own IO (decided 1 Nov),
so there will be an IO module. Spare channels on it can carry the contract, and that needs no licence.

What to check on Monday 2 Nov (step M0):
- the installed option packages: on the smartPAD, *Start-up > Additional software*;
- the KSS version: *Help > Info*;
- the IO modules in the cabinet and their free channels.

| The controller has | The equipment service talks | The robot program |
| --- | --- | --- |
| KUKA.Ethernet KRL (EKI) | XML over TCP; the robot is the server, the service connects | An EKI configuration with the contract's elements, and `EKI_` calls in the program |
| KUKA.OPC UA, or KUKA.DeviceConnector | OPC UA: the contract as global variables of the program | The variables in `$config.dat`, exposed by the option |
| Neither | KukaVarProxy (TCP 7000 over the KLI, global variables): not KUKA's, a program on the controller's Windows, which KUKA advises against | The variables in `$config.dat` |
| Neither, and KukaVarProxy not allowed | No service: the contract on digital IO, the Pi's pins through 24 V optocouplers to spare channels of the robot's IO module (`gpio` points, as filling's) | The signals mapped in WorkVisual; `Job` as a few bits |

**Proposed: EKI or OPC UA, whichever the controllers have.** If neither is installed, KukaVarProxy to
start with: no licence and no wiring. Digital IO is the fallback that always works, but it is the
wiring you want to avoid.

With modpy the interface is a driver of the module (a `Points` in `modpy/points.py`): the module's
skills and AAS do not change with it, only the driver does. `SimPoints` stands in for the robot until
then.

### 3.3 The two modules

| Module | Components | Primitives (one per job) | Composite |
| --- | --- | --- | --- |
| Loading | Robot (the gripper is on the robot's IO, switched inside its jobs) | `Home`, `PickFromTray`, `PlaceOnShuttle`; `AwaitJob` | `Loading`: pick, place, home |
| Unloading | Robot | `Home`, `PickFromShuttle`, `PlaceInTray`; `AwaitJob` | `Unloading`: pick, place, home |

Each spec (`cell/modules/python/loading.yaml`, `unloading.yaml`) names:
- the robot's points (their Modbus addresses unused so far);
- the jobs as commands (`PickFromTray: [{Job: 2, for: 200ms}, {Job: 2, Start: true}]`);
- the transfer point where a shuttle stands;
- the capability: picking up realizes Receiving, putting down Releasing (the vocabulary's skills 0.3).

Loading is where a product's custody begins ([agents.md](agents.md), section 6). The loading module
releases the vial to the shuttle (Releasing) and the shuttle receives it (Receiving); unloading is the
reverse.

### 3.4 In simulation

modpy's `SimPoints` answers the contract as the robot would: `Busy` for the job's time, then `Done`
with `JobDone` (`--speed` makes the jobs quicker). So the line runs with six modules on the PC before a
robot is connected. A stand-in controller (an EKI or OPC UA server in Python) tests a robot driver
without the robot.

## 4. Capping

**Like the filling module (decided):**
- the linear axis lowers the crimping head;
- it runs on a stepper through a TB6600, with a limit switch, and is homed the same way;
- the crimper's `Close` is simulated (`sim`) for now, its time given by `Duration`.

**Done (3 Nov):** the spec is `cell/modules/capping.yaml`, with a Pi target written as filling's
(pins, PWM channel, `board: pi5`). Its program is generated (`cell/control/CappingModule`) and runs on
FORTE against the simulator (`test_capping_module_homes_and_crimps`). The new primitive is `Crimp`:
the crimper's `Close` for `Duration`, with the head at `CrimpPosition` and kept there, as stoppering's
`PressStopper` needs the press at `PressPosition`. Next: its Pi.

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

**The camera is a USB FPV camera** (1 Nov): a UVC device, read with OpenCV (V4L2) on the Pi. An
analog FPV camera behind a USB grabber is read the same way, since the grabber is then the UVC device.
The service keeps the camera open and takes the newest frame on `Trigger`. Opening it for each
image, as AP2030-UNS did, costs time, and the first frames come dark while the exposure settles.

The spec plans two cameras, top and side. With one camera the module has one camera component and
one capture skill (section 8).

### 5.2 The images

The service sends the image to the store over HTTP, not through IEC 61499 or OPC UA:
- an S3 `PUT` of a JPEG, one object per image;
- named by module, camera and number: `inspection/<Module>/<Camera>/<ImageNo>.jpg`;
- the time and the skill call kept as the object's metadata.

IEC 61499 carries only the verdict and the number. AP2030-UNS sent each image base64 in an MQTT
message instead.

**The store: SeaweedFS** (decided 1 Nov): one node, the S3 API on port 8333, Apache 2.0. MinIO's
open-source edition has published no images since October 2025 and was archived in April 2026; Garage
(AGPL) was the other choice.

**It runs on the server that runs the AAS server**, as a container of its own in the same stack
(`deploy/aas`, later `deploy-server`), beside BaSyx, InfluxDB and the DMP. It is not part of BaSyx.
The AAS holds no image; it links to them by URL:
- **Where a camera's images are:** the camera's Asset Interfaces Description gets a second interface,
  HTTP, with the store's address and the image as a property at a URL template (`{ImageNo}`). A client
  finds the images from the AAS, as it finds the camera's OPC UA.
- **Which images belong to a product:** the product's batch record (its instance AAS, planned) gets a
  `File` element per image whose value is the image's URL. A `File` may name its file by URL, so the
  AAS points to the image without holding it.
- **When each image was taken:** a skill's results go into the time series as every result does (the
  DMP, InfluxDB), so each image's number is there with its skill call.
- **The web UI** shows an image from its URL.

This is instead of BaSyx's own attachments (a `File` element's content uploaded to the AAS server),
which would put the images into the AAS server's database. No image and no live value goes into the
AAS ([decisions.md](decisions.md), 28 Oct).

Proposed for access: the bucket readable by anyone in the lab network, so the web UI needs no key;
writing needs a key, which only the camera service has, from its environment and never from a file in
the repository.

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
| M0 | The KR C4s: option packages (Ethernet KRL, OPC UA, DeviceConnector), KSS version, IO modules and free channels (section 3.2) | You, at the robots, Monday 2 Nov | The interface of 3.2 is chosen |
| M1 | The equipment service: its base shared with the simulator, a container in `deploy/pi`; a Pi target with pins and a local Modbus server tried on a Pi | – | One program on a Pi has a point on the service and one on a pin |
| M2 | Capping: the spec moved to `cell/modules`, the program generated and run with the simulator (done 3 Nov); then on its Pi | A Pi 5, a TB6600, a stepper, a switch; you at the bench for the axis | `Capping` runs on the Pi with the axis moving and the crimper simulated |
| M3 | Loading and unloading: the contract with your program, the specs, the simulator's robot (done 3 Nov, in modpy); in the agents, loading as the step that starts custody ([agents.md](agents.md), A1) | Your robot program's job numbers | The line in simulation takes a vial from loading to unloading |
| M4 | The robot service over the chosen interface, with a stand-in controller in the tests; then on each robot | M0; you at the robot | `Loading` moves the robot, started by the agents |
| M5 | Inspection: the spec, the camera service, the store in the lab stack, the camera's HTTP interface in its AAS | The cameras | Each camera's image is in the store, with its number in the skill's results |
| M6 | The six modules in the line scenario with the agents (A1, A7) | M2 to M5 in simulation | The three products' orders run end to end in simulation |

## 8. Open

| # | Question | Recommendation |
| --- | --- | --- |
| 1 | ~~Python beside FORTE~~ | Decided 1 Nov: the service over Modbus, as the start |
| 2 | ~~The robot: one program with job numbers, or programs selected from outside~~ | Decided 1 Nov: one program |
| 3 | The robot's interface | After M0 (2 Nov): EKI or OPC UA, whichever the KR C4s have; else KukaVarProxy; else digital IO |
| 4 | ~~The image store~~ | Decided 1 Nov: SeaweedFS, beside the AAS server |
| 5 | ~~The gripper~~ | Decided 1 Nov: on the robot's own IO, inside its jobs |
| 6 | ~~A module stopped during a job~~ | Decided 1 Nov: the robot finishes the job |
| 7 | ~~Which cameras~~ One camera or two (the spec plans top and side) | Decided 1 Nov: a USB FPV camera; how many is open |
| 8 | Who may read the images | Anyone in the lab network; writing with a key only the camera service has (5.2) |
