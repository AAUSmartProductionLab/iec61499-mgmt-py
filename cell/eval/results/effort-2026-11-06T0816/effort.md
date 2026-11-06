# Effort of a reconfiguration, in user inputs (2026-11-06 08:16, commit a9780ff1030a)

Inputs = pointer actions (clicks, drags) + typed entries (a value or name typed) + keys pressed alone. The editor and the planner counted in the browser, each change read back and compared with its target; the 4diac IDE counted from the program the module rules make of the target.

| Task | 4diac IDE, by hand | Skill editor | Planner |
| --- | --- | --- | --- |
| A value: Dispensing doses at 2.0 mL/s | 3 (2 pointer, 1 typed, 0 keys; 4 keystrokes) | 4 (3 pointer, 1 typed, 0 keys; 4 keystrokes) | – |
| A new skill made like one: DoubleDose, two doses | 55 (25 pointer, 24 typed, 6 keys; 536 keystrokes) | 14 (12 pointer, 2 typed, 0 keys; 15 keystrokes) | – |
| A new flow: BottomUpFilling, dosing while the needle rises | 60 (29 pointer, 25 typed, 6 keys; 627 keystrokes) | 25 (21 pointer, 4 typed, 0 keys; 26 keystrokes) | – |
| A product: 15 mL, weighed | 71 (37 pointer, 25 typed, 9 keys; 466 keystrokes) | 14 (11 pointer, 3 typed, 0 keys; 18 keystrokes) | 6 (4 pointer, 2 typed, 0 keys; 14 keystrokes) |

To the running module: 4diac 3 (2 pointer, 0 typed, 1 keys; 1 keystrokes), a new boot file and a restart; the AAS routes 1 (0 pointer, 1 typed, 0 keys; 77 keystrokes) (`modsync reconfigure`), online.

## The 4diac IDE, what is counted

- value: changed; blocks 0 added, 0 removed; connections 0 drawn, 0 deleted; values 1; subapplications 0 made, 2 entered; built new instead: 140 inputs
- double: made like Dispensing; blocks 2 added, 0 removed; connections 15 drawn, 4 deleted; values 23; subapplications 0 made, 3 entered; built new instead: 160 inputs
- bottomup: made like Dispensing; blocks 2 added, 0 removed; connections 19 drawn, 4 deleted; values 24; subapplications 0 made, 3 entered; built new instead: 164 inputs
- fifteen: made like Dispensing; blocks 3 added, 3 removed; connections 23 drawn, 4 deleted; values 24; subapplications 0 made, 3 entered; built new instead: 143 inputs

## The browser runs

- value, editor: saved Dispensing (Built), right: True ; click open Dispensing · click the Dispense step · type FlowRate: 2.0 · click Save
- double, editor: saved DoubleDose (Described), right: True ; click open Dispensing · click New skill from this · type its name: DoubleDose · click Create · click the Dispense step · click Add step · click Runs the skill · click Dispense (FillingPump) · click the new step again (choosing its skill renamed it) · click Volume from · click The skill's Volume · click Start (the skill itself) · type Volume default: 0.5 · click Save
- bottomup, editor: saved BottomUpFilling (Described), right: True ; click open Dispensing · click New skill from this · type its name: BottomUpFilling · click Create · click the NeedleDown step · type Position: 58 · click Add a block · click Parallel block · click Branch 1 · click Add step · click Runs the skill · click Dispense (FillingPump) · click the new step again (choosing its skill renamed it) · click Volume from · click The skill's Volume · type FlowRate: 0.7 · click Branch 2 · click Add step · click Runs the skill · click MoveAxis (FillingLinearAxis) · click the new step again (choosing its skill renamed it) · type Position: 40 · click the old Dispense step · click Remove selected · click Save
- fifteen, editor: saved Filling15 (Described), right: True ; click open Dispensing · click New skill from this · type its name: Filling15 · click Create · click the Dispense step · click Volume from · click A constant · type Volume: 7.5 · click Add step · click Runs the skill · click Dispense (FillingPump) · click the new step again (choosing its skill renamed it) · type Volume: 7.5 · click Save
- fifteen, planner: saved PlannedFilling (Described), right: True ; click Plan a skill · click Capability · click Filling · type FillVolume: 15 · type Results: FillWeight · click Plan and describe
