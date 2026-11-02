# Skill library

<span class="pillar reconfiguration">Reconfiguration</span> `iec61499-skill-lib`: ModLib, the library
every module is built from (occupation, the PackML state manager, the skill state machine, parameter
latches, flow blocks, IO blocks), and `modgen`, which generates a module's 4diac project from its
module spec. Folder `iec61499-skill-lib/`.

<figure markdown="span">
  [![A module spec on the left, what modgen writes in the middle (ModLib and the module's project), and
  the application as FORTE runs it on the right: the INIT chain from START down to the composite skill
  Dispensing](../figures/skill-lib.png)](../figures/skill-lib.png)
  <figcaption>From the spec, modgen writes the library and the module's project; the application is one
  INIT chain from the resource's START: the module level, equipment, primitives, procedures, then the
  composite skills, each a subapplication.</figcaption>
</figure>

## The module spec

A module spec (YAML, `cell/modules/<module>.yaml`) is the vendor-side description a module is
generated from:

- **targets**: where it runs; `pc` with its IO simulated over Modbus, `pi` with GPIO and PWM;
- **equipment**: each item's IO points, an address per target, and its commands;
- **skill primitives**: one equipment command until a sensor condition or a time;
- **module level skills**: parameters and a flow of primitives;
- **procedures**: what Resetting and Stopping run.

The spec is checked before anything is written: every name an expression uses is a signal or a
parameter, a constant lies within the limits it is bound to, two parallel branches use different
equipment.

## What modgen writes

| Generated | What it is |
| --- | --- |
| ModLib (`iec61499-skill-lib/ModLib`, package `modlib`) | `MOD_Occupation`, `MOD_StateManager` (PackML), `SKILL_Core` (a skill's state machine and OPC UA methods), `SKILL_Param_*` (a parameter's value and range), `SKILL_FailMerge`, the flow blocks `SKILL_Join2` to `4`, `SKILL_Condition_*`, `SKILL_Merge`, and the IO blocks `IO_DI`, `IO_DO`, `IO_AI`, `IO_AO` |
| `EQ_<Item>` per equipment item | Owns its IO points; writes what its one holder commands; publishes its inputs |
| `SK_<Skill>` per primitive | `SKILL_Core`, a latch per parameter, the contract, its equipment's command table |
| The system, an application per target | Occupation, Module, the equipment with that target's IO addresses, the offered primitives, the procedures, each module level skill as a subapplication; one INIT chain from the resource's START |

Generation is deterministic: the same spec gives the same files. A module level skill is made by one
function, `module_skill`, which modsync also calls to create a skill online, so a skill created online
and the same skill generated from a spec are the same program; a test compares them for every shape of
flow.

The library's types are compiled into FORTE once, from ModLib; each module's project declares them so
the IDE can open it on its own. The generated projects are opened in the 4diac IDE from the repository
without copying them: positions arranged in the IDE are kept when the projects are generated again, and
only what overlaps is spread.

## Use it

```powershell
cd iec61499-skill-lib
python -m modgen                                  # ModLib and every module's project
cd ..
runtime/check-project.ps1 -ProjectDir cell/control/FillingModule   # the 4diac IDE's own checks, headless
python -m pytest -q iec61499-skill-lib/tests      # the generator against the committed projects
```

A change to the generator is committed with the regenerated projects; a test generates every project
again and compares. A new or changed block type needs a new [FORTE](runtime.md).

Read further: [module-rules.md](https://github.com/AAUSmartProductionLab/iec61499-mgmt-py/blob/main/docs/module-rules.md),
[building-skills.md](https://github.com/AAUSmartProductionLab/iec61499-mgmt-py/blob/main/docs/building-skills.md)
(a new skill, primitive or piece of equipment), [filling-program.md](https://github.com/AAUSmartProductionLab/iec61499-mgmt-py/blob/main/docs/filling-program.md)
(the filling program block by block).
