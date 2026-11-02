# Reconfiguration: changing a running module from its AAS

<span class="pillar reconfiguration">Reconfiguration</span> A module's AAS is its desired state. A
reconfiguration is a change to that AAS, which the tools then carry into the running IEC 61499
program, online where the rules allow it. Who made the change (an engineer in the Skill Editor, a
planner, an agent) is a separate matter.

## The module rules: the contract

The tools rely on rules, not on the generator: a program that follows them can be verified, operated
and given a new skill from its AAS and its running program alone, whether it was generated or written
by hand in the 4diac IDE. A module names the rule set it follows in its AAS (`RuleSet`).

1. **The shell**, fixed for every module: one application on one FORTE resource, published below
   `/Objects/<Module>` on its OPC UA server; `Occupation` (who may command it) and `Module` (its PackML
   state); one block per equipment item, each owning its IO points, set by one address per point
   (`gpio[...]`, `pwm[...]`, `modbus[...]`, `sim`); blocks reach equipment over FORTE's local channels,
   not connections; one INIT chain started by the resource's own START block.
2. **A skill primitive** is a block type (`SK_<Skill>`) with a fixed interface: events `START`, `HALT`,
   `ABORT`, `RESET` in, `SUCCESS` and `FAILURE` out; its parameters as inputs; the OPC UA methods Start,
   Stop, Abort, Reset; one skill state machine for all (`SKILL_Core`).
3. **A composite skill** (module level skill) is a subapplication of library and primitive instances
   only, wired in a fixed pattern: `Control`, the Start method, a latch per parameter, the publishers,
   and the `Execute` and `Stop` sequences.
4. **A flow** (rule set 2): parallel blocks and decisions, made of three library block types.

## What can change online

| Change | Example | How |
| --- | --- | --- |
| **create** | A composite skill the AAS describes that the program lacks | created online, verified, recorded |
| **write** | A step's constant, a parameter's default or limits | written online while the module is idle and free |
| **restart** | Another flow or order of steps, a skill the AAS no longer describes, other equipment | refused online: a new boot file and a restart |
| **new FORTE** | A new block type, new IO | a new FORTE build, then a new deployment |

A value is the cheapest change: a few management commands and no downtime. A new skill touches nothing
that runs, so it is created in any state, even while another skill executes.

## The parts

| Part | What | Page |
| --- | --- | --- |
| modsync | The running program against its AAS: verify, change online, record, the IDE project of what runs | [modsync](modsync.md) |
| iec61499-skill-lib | ModLib (the module library), modgen (spec to 4diac project), the module rules | [Skill library](skill-lib.md) |
| iec61499-mgmt-py | FORTE's management protocol in Python, boot files, `.sys` flattening, read-back | [Management library](mgmt.md) |
| forte-runtime | FORTE built with every module's block types, for the PC and the Raspberry Pi | [FORTE runtime](runtime.md) |
| Skill Editor | A composite skill written as a flow, in the web UI | [Web UI](../interfaces/web-ui.md) |

Read further: [module-rules.md](https://github.com/AAUSmartProductionLab/iec61499-mgmt-py/blob/main/docs/module-rules.md),
[pipeline.md](https://github.com/AAUSmartProductionLab/iec61499-mgmt-py/blob/main/docs/pipeline.md),
[mapping.md](https://github.com/AAUSmartProductionLab/iec61499-mgmt-py/blob/main/docs/mapping.md) (an AAS skill as blocks).
