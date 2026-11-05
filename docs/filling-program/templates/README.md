# Templates for your new equipment and primitives

Every new type you make (section 10 of [the guide](../../filling-program.md)) starts as a copy of a
type that is nearly the same. These templates are such types, with neutral names. In each one,
everything that is your own says **YOUR OWN** and how much of it there is: one per input pin, one
per output pin, one per command, a size. Everything else is the same in every type of its kind:
keep it as it is.

There is one set per module, because a type belongs to its module's package:

- `StopperingModule/` for the stoppering module (`stoppering::`);
- `CappingModule/` for the capping module (`capping::`).

## What is in a set

| Template | What it is | You copy it as | Guide |
| --- | --- | --- | --- |
| `EC_Template` | The equipment's command table | `EC_<Equipment>` | 10.3 |
| `EL_Template` | The equipment's rules | `EL_<Equipment>` | 10.4 |
| `EV_Template` | The equipment's report form | `EV_<Equipment>` | 10.5 |
| `EQ_Template` | The equipment block, with the pins | `EQ_<Equipment>` | 10.6 |
| `EP_Template` | The equipment's port, inside every primitive of it | `EP_<Equipment>` | 10.7 |
| `SC_TemplateUntil`, `SK_TemplateUntil` | A primitive that runs until an input says it is done, with a timeout (as `Home`) | `SC_<Primitive>`, `SK_<Primitive>` | 10.8, 10.9 |
| `SC_TemplateTimed`, `SK_TemplateTimed` | A primitive that runs for a time given as a parameter (as `Crimp`) | `SC_<Primitive>`, `SK_<Primitive>` | 10.8, 10.9 |

The template equipment has one input, `MyInput`, and one output, `MyOutput`. It has two commands:
`Stop` (0, everything off) and `MyCommand` (1, `MyOutput` on).
- `SK_TemplateUntil` sends `MyCommand` until `MyInput` is TRUE, and fails after 2 s.
- `SK_TemplateTimed` sends `MyCommand` for `MyParameter` seconds (0 to 5, default 1).

Both use `EP_Template`.

The folder `Type Library/Generic` has the sizes of `PUBLISH` and `SUBSCRIBE` that the templates use
and the module's project does not declare yet: for the stoppering module `SUBSCRIBE_2`,
`SUBSCRIBE_3` and `PUBLISH_3`; for the capping module `SUBSCRIBE_2`.

## Where it says YOUR OWN

| Where | How you see it |
| --- | --- |
| A pin (an input, output or event) | Its comment starts with *YOUR OWN*: hover over it in the *Interface* tab, or see *Properties* |
| A block inside a composite | Its comment starts with *YOUR OWN*: hover over the block. It says either *Change Type* to your own type, or the size to give it, or one block per pin or parameter |
| A line of an algorithm | It ends with a comment `(* YOUR OWN: ... *)` |
| A connection | Connections have no comment. Yours are the ones to and from a pin or block that says *YOUR OWN* |

When there is more than one of a thing, repeat what the template has once. For example:
- **More pins:** each pin, each line of an algorithm and each IO block marked *one per input pin*
  comes once per input pin.
- **More commands:** each command but `Stop` gets an `ELSIF` in `EC_`'s `Alg_Send`.
- **More parameters:** each parameter gets a pin and a `Par_` block.

After that, take the *YOUR OWN* off the comments, and say there what the thing is.

## How to use them

1. **Copy the set into your project.** In Windows Explorer:
   - open the set of your module, e.g. `templates/StopperingModule`;
   - copy its folder `Type Library` into your project's folder, the one with `StopperingModule.sys`
     in it. To find that folder in the IDE: right-click the project, *Properties*, *Resource*,
     *Location*.

   Windows asks whether to merge the folders: yes. No file of yours is replaced: the templates are
   new types. Only if you made one of the `Generic` sizes yourself already does Windows ask about
   that file: skip it.
2. **In the IDE, refresh the project:** select it and press F5. Each template is then in its folder
   of the *Type Library*:
   - `EC_Template` in `Equipment/Commands`, `EL_Template` and `EV_Template` in `Equipment/Base`;
   - `EP_Template` in `Equipment/Ports`, `EQ_Template` in `Equipment`;
   - the `SC_` in `Skills/Contract`, the `SK_` in `Skills`.
3. **Copy, then change**, as section 10.2 of the guide says, with a template instead of the lab's
   type:
   - select the template, *Copy* (Ctrl+C), select the same folder, *Paste* (Ctrl+V);
   - give the new name, e.g. `EC_Feeder`;
   - change what says *YOUR OWN*;
   - in a composite, right-click each block that says *Change Type*, and choose your type.

   Go from the bottom up: `EC_`, `EL_`, `EV_`, `EQ_`, `EP_`, then `SC_` and `SK_`. A type can only
   use types that are already there.
4. **Rename the placeholders:** `MyInput`, `MyOutput`, `MyCommand`, `MyParameter` and the item's
   name `Template`, everywhere: in the pins, in the algorithms' text, and in the blocks' names.
   An algorithm does not follow a renamed pin, so you must change the name in its text.
5. **When your types are done, delete the templates you copied** (keep the `Generic` sizes). Then
   check the project (section 11.2 of the guide). A block of yours that still has a template's type
   is now an error, so the check finds it.

A primitive on equipment that is already there (the piston, the crimper, the axis) needs only the
`SC_` and `SK_` templates. In `SK_`, *Change Type* of `Port` to that equipment's `EP_` (e.g.
`EP_Piston`), and connect its outputs to your contract's inputs.

The templates pass the 4diac IDE's check of the project with no errors or warnings, and FORTE builds
with them through the kit (`build-project.ps1`).
