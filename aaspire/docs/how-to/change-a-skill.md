# Change a skill online

A running module given a new composite skill, or a changed value, from its AAS, without stopping it.
The module here is the filling module [on this PC](simulation.md), its AAS on the
[local AAS server](register.md); on a Pi the same commands take its address.

## 1. Change the AAS

Any of these, as the situation asks:

- **Write** a skill in the Skill Editor (web UI, `http://localhost:3000`): a flow of the components'
  primitives, saved to the module's Skills submodel as `Described`.
- **Plan** one from the module's capabilities:
  `python -m modplan plan http://localhost:8081 --capability Filling --value FillVolume=2.0 --result FillWeight --write`.
- **Change a value**: a step's constant, a parameter's default or limits, in the Skills submodel.

## 2. See what would change

```powershell
python -m modsync verify http://localhost:8081 --shell FillingModuleAAS --host localhost
python -m modsync reconfigure http://localhost:8081 --shell FillingModuleAAS --host localhost --dry-run
```

`verify` says how the program differs from the AAS; `--dry-run` lists what would be created and
written online and what is refused (another order of steps needs a new boot file and a restart).

## 3. Change it

```powershell
python -m modsync reconfigure http://localhost:8081 --shell FillingModuleAAS --host localhost
```

The new skill is created online, verified by reading it back, appended to the boot file, marked `Built`
in the AAS with its interface, and recorded. A value is written only while the module is Stopped, Idle
or Aborted and free (`--force` overrides); a new skill is created in any state.

## 4. Run it

The new skill is at `/Objects/Filling/Skills/<Skill>` at once, and in the module's AAS: occupy the
module, bring it to Execute, start the skill, as for any other ([modlink](../integration/modlink.md)).
An agent does all of this by itself when a bid needs a skill that is only described.
