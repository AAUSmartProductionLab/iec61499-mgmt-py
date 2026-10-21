# PubSubDemo: two publishers, one subscriber

One application, `CountAndAdd`, distributed over three FORTEs on one computer:

| Device | Port | Blocks | What it does |
| --- | --- | --- | --- |
| `FORTE_1` | 61501 | `Boot1`, `Clock1`, `Count1`, `Pub1` | counts every second, publishes (1, count) |
| `FORTE_2` | 61502 | `Boot2`, `Clock2`, `Count2`, `Pub2` | counts every two seconds, publishes (2, count) |
| `FORTE_3` | 61503 | `Boot3`, `Subscriber`, `BySource`, `Count1In`, `Count2In`, `Sum`, `Blink` | one subscriber for both: the source number (`RD_1`) picks which count to keep, `Sum.OUT` is their sum, `Blink.Q` toggles with every new sum |

Both publishers send to the same UDP address, `127.0.0.1:61550`, where the one subscriber
listens. A PUBLISH/SUBSCRIBE `ID` without brackets is FORTE's default `fbdk[].ip[<address>]`;
written as `fbdk[127.0.0.1:61550]` it would lack the IP layer and never open a socket.
Across computers, the publishers send to the subscriber's IP address instead.

## Run it

```powershell
python runtime/demos/PubSubDemo/run.py            # starts the three FORTEs; leave it running
```

In the 4diac IDE: import `runtime/demos/PubSubDemo` (File > Import > Existing Projects, without
copying), open `PubSubDemo.sys`, right-click the system > Deploy (all three devices), then
Monitor System and Watch `Count1In.OUT`, `Count2In.OUT`, `Sum.OUT` and `Blink.Q` on FORTE_3, and
`Count1.CV` and `Count2.CV` on the counters. Ctrl+C in the terminal stops the FORTEs.

Without the IDE, `run.py --deploy` deploys the application itself (inside its container, as the
IDE does, so the IDE can still monitor it), and `run.py --deploy --check` checks for 6 s that the
sum is the two counts added, then stops.

`run.py` uses the FORTE built by `runtime/build-modules.ps1`; any FORTE with the standard
blocks works (`--forte <path>`). The standard types are copied into the project
(`Type Library/Std`, from the IDE's 3.0.0 libraries) so the headless IDE check finds them.
