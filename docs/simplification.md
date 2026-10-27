# Can modsync, modlink and modgen be simpler?

Analysis of 27 Oct 2026, **for your decision**. How the tools work is [tools.md](tools.md).

## The short answer

modgen and modlink are about as simple as their jobs. No function is dead (each top-level function
is used outside the tests), and the features of the spec are used by the modules (timed command
phases by the stoppering piston, `move_to` by every axis, the Modbus path by the PC simulator). The
one exception in modgen is the unused `Struct` type writer.

modsync carries the most that could go. It grew in two steps: first against the module spec (8 Oct
and before), then against the AAS. Both modes are still there, each with its own model of a
difference. The paper describes only the second. On top of that, today's rule set 2 added a second
way of building and reading a sequence, beside the old one.

In order of value for the paper and the work:

| # | Change | Tool | Saves | Risk | Recommendation |
| --- | --- | --- | --- | --- | --- |
| 1 | One pattern for a sequence: every sequence is a flow | modgen, modsync, rules | ~80 lines, one rule, one of two readers | Every program changes once (redeploy) | **Yes, before the Pis get their new runtime** |
| 2 | One desired state: fold the spec mode into the AAS mode | modsync | ~350 to 400 lines (a sixth of modsync), one of two comparison models | Medium: the spec mode's tests | **Yes**, after B1 and B2 or as soon as time allows |
| 3 | Split `desired.py` by job | modsync | none; clearer | Low | **Yes, now** (an hour) |
| 4 | One set of AAS JSON helpers | modsync, modreg, examples | ~40 lines, five copies to one | Low | **Yes, now** |
| 5 | Drop reading AASs older than ARSO 0.8 | modlink | ~50 lines | The HMI's old fixtures | With the HMI's move into the web UI (C5) |
| 6 | The HMI reads the AAS with modlink | HMI | its own reader (`hmi/aas.py`) | Part of C1/C5 | With C5 |
| 7 | The structure read back as a module spec | modsync | ~80 lines (`stated`, the project's conversion) | Medium: tests use the dictionary | Not now |
| 8 | Remove `Struct` | modgen | ~15 lines | None | Yes, with 4 |

## 1. One pattern for a sequence

Rule set 2 added `flow` beside the old `sequence` in the generator, and `flow` beside `steps` in
modsync's reader. A plain list of steps is still built and read the old way, so existing programs do
not change. Building and reading every sequence as a flow (a list of steps is a flow without blocks)
removes:

- in the module rules: "`ReleaseAfter = TRUE` only on the last step that uses its item". Every step
  of a module level skill keeps the equipment; `Control` gives up everything at the end of a run
  (it does so since 22 Oct). A procedure's steps still give up their own (no `Control` there);
- in modgen: the linear `sequence` (~60 lines);
- in modsync: the linear reader (~20 lines), and the question of which reader applies.

**What changes in behaviour:** an item a skill no longer needs is held until the skill's run ends,
not released after its last step (the pump during Home and Weigh). Another skill of the same client
that wants it meanwhile is refused with Busy instead of running. No skill of the line does that.

**Cost:** every module's program changes (instance values and the order of a few connections), so
both Pis get a new boot file. They need one anyway with the runtime of 27 Oct, which waits for your
go: doing this first means they are installed once.

## 2. One desired state

modsync compares a running program with what it should be in two ways:

| | Against the spec (`pull`, `push`, `watch`) | Against the AAS (`verify`, `reconfigure`) |
| --- | --- | --- |
| What it should be | The program modgen generates for one target, instance by instance | The structure the AAS describes |
| Which module runs | The candidate (spec and target) whose program is closest to what runs | The module the AAS names |
| A difference | `Drift`: missing, unexpected and retyped instances and connections, other values | `Differences`: create, write, restart, record |
| What it does | Values and new skills online, everything else by a new boot file and a restart | Values and new skills online, the rest refused |
| Code | `compare.py`, `sync.inspect`, `push`, `watch`, most of `__main__` | `desired.py`, `structure.py` |

Since `described` turns an AAS into a module spec, and a spec file is a module spec, one path does
for both: **the desired state is a module spec, from the AAS or from a file**; it is compared with
the structure read back by the rules (one model of a difference), and applied online by the same
code. What the spec mode does besides is a full redeployment, which `deploy/pi.py module` already
does from a spec. Which module runs is not a search: the program names itself (`Occupation.Module`),
and its IO addresses (`gpio[...]` or `modbus[...]`) tell the target.

**Given up:** the instance-by-instance drift against the spec (an IO address or an equipment setting
changed by hand on the module would no longer show as drift, since the structure does not read them;
a redeployment from the spec still puts them right). `modsync describe` and `--register` go to
modreg, which already does both (`modreg profile`, `build`, `register`).

**Kept:** `modsync project` (it needs the spec for the equipment and primitives and takes it by the
module's name), the deployers, the guard, the online commands.

## 3. Split `desired.py`

757 lines doing four jobs: reading and writing AASs (a folder or a server) and the integrator's
record; turning an AAS into a module spec (`described`, 144 lines); reading and comparing (`read`,
`differences`); changing and recording (`reconfigure`, `record`). Four modules, each a section of
[tools.md](tools.md): `aasfiles.py`, `described.py`, `compare` (into `structure.py`) and
`reconfigure.py`. No change of behaviour.

## 4. One set of AAS JSON helpers

`children`, `at`, `submodel`, `meaning`, `qualifier` are written five times: `modsync/desired.py`,
`modreg/offer.py`, `cell/examples/plan_check.py`, `cell/examples/describe.py`, and `modlink/aas.py`.
The first four can share one module of `aas61499-tools`. modlink keeps its own copy on purpose: it is
in another repository and depends on nothing but `asyncua`.

## 5 and 6. modlink and the HMI

modlink still reads three older forms of an AAS: ARSO 0.8 (skills in a collection Skills), 0.7 (the
module's commands in a Module submodel) and the form before (skills with Methods and StateReference).
Every AAS made today is 0.10, and the example line on the local server can be published again.
What keeps the old forms alive is the HMI: its stand-in module and built-in descriptions are older, and
it has a second AAS reader of its own (`hmi/aas.py`, the 0.8 rewrite, not committed). Both go when the
HMI moves into the web UI (C5); until then removing them breaks the HMI's tests for nothing the paper
needs.

## 7. The structure as a module spec

There are four converters between three descriptions: spec to AAS (modreg), AAS to spec
(`described`), program to structure (`structure`), spec to structure (`stated`), and the project's
structure to spec (`running_spec`, `nodes_of`). If `structure` gave a module spec directly, `stated`
and the project's conversion would go and every comparison would be between two module specs. It is
the cleaner model ("the same description from three sources: the spec, the AAS, the program"), but the
tests are written against the dictionary and the gain is small. Not now; it is a good sentence for
the paper either way.

## What I would do

Now: 3, 4 and 8 (an hour, no change of behaviour), then 1 before the runtime goes onto the Pis. Then
2, once B1 and B2 run, since the scenario runner will use the AAS mode only and 2 makes it the only
mode. 5 and 6 with C5.
