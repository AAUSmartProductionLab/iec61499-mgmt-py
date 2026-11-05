# Keeping the filling guide up to date

For whoever maintains [../filling-program.md](../filling-program.md), not for its readers. The
guide is for students who make function blocks by hand in the 4diac IDE (with the FORTE kit,
[../../runtime/kit/README.md](../../runtime/kit/README.md)); it says nothing about the generator.
This note is left out of the students' zip.

## Where the program comes from

The lab's projects in `cell/control` are written by `modgen` from the module specs
(`cell/modules/*.yaml`); how is in [../building-skills.md](../building-skills.md) and
[../tooling.md](../tooling.md). The comments on every type, pin and block come from
`iec61499-skill-lib/modgen/explain.py` and the specs' `description`s. A type a student makes by
hand in `cell/control/<Module>` is removed by the next `python -m modgen`, so their work stays in
their own copy of the project (the kit's `projects/`, or the zip's). To bring a student's equipment
or primitive into the lab's program, write it into the spec, generate, and compare with theirs.

## Drawing the pictures again

The pictures are drawn from the program's files, so they go out of date when the program is
regenerated or its layout is changed in the IDE. From the repository's root:

```powershell
python docs/filling-program/draw_blocks.py
```

draws every `type-`, `inside-`, `ecc-` (the state machine of a basic type, as the IDE lays it out)
and `app-` picture of the filling module again, `legend.svg`, and the map of the local channels
(`channels-Filling_pi.svg`). The other modules' pictures are drawn into a folder of their own and
copied with a prefix:

```powershell
python docs/filling-program/draw_blocks.py --project cell/control/StopperingModule --app Stoppering_pi --out <folder>
python docs/filling-program/draw_blocks.py --project cell/control/CappingModule --app Capping_pi --out <folder>
```

`stoppering-` from the first (`app-Stoppering_pi`, `type-EQ_Piston`, `inside-EQ_Piston`,
`type-EC_Piston`, `type-SK_PressStopper`), `capping-` from the second (`app-Capping_pi`,
`type-EQ_Crimper`, `inside-EQ_Crimper`, `type-SK_Crimp`).

The `example-` pictures (section 10, the stopper feeder) come from a copy of the stoppering spec
with the feeder and its primitive, generated into a folder of its own with
`modgen.generate(modgen.load(<the copy>), root=<folder>, manifest=<folder>/types-manifest.json)`,
and drawn the same way with `--project <folder> --app Stoppering_pi`. The two entries, the
equipment at the end of `equipment:` and the primitive at the end of `skills:`:

```yaml
  Feeder:
    kind: StopperFeeder
    description: Small air cylinder that pushes the next stopper under the head, with a switch at its front end
    inputs:
      Advanced: {modbus: d1, gpio: {line: 24, bias: pull_up, active_low: true}}   # pin 18, reed switch at the front
    outputs:
      Advance: {modbus: c4, gpio: 22}                              # pin 15, valve coil: out
      Retract: {modbus: c5, gpio: 25}                              # pin 22, valve coil: in
    commands:
      Stop: {}
      Advance: [Advance]
      Retract: [Retract]
    sim: {axis: {forward: Advance, backward: Retract, travel_s: 0.5, start: 0.0, switches: {Advanced: 1.0}}}
```

```yaml
  FeedStopper:
    description: Push the next stopper under the head, until the cylinder's front switch closes
    equipment: Feeder
    command: Advance
    postcondition: Advanced
    timeout: 2s
```

The guide's section 10 describes these generated types block by block, pin by pin and line by
line: after a change to the generator's equipment or primitive types, check that section against
a new generation of this example.

## The templates

`templates/` holds a template of every type a student makes, one set per module students work on
(stoppering, capping), with `templates/README.md` for the students. They are generated, not written
by hand:

```powershell
python docs/filling-program/make_templates.py
```

It adds a neutral piece of equipment `Template` and two primitives on it (`TemplateUntil`,
`TemplateTimed`) to a copy of each module's spec, generates them into a scratch folder with `modgen`,
and marks every pin, block, algorithm line and size that is the student's own with *YOUR OWN*. Run
it again after a change to the generator's equipment or primitive types, and check the result: copy
each set into a copy of its project and run `runtime/check-project.ps1 -ProjectDir <copy>` (0 errors
and warnings when this was written, 5 Nov 2026).

## The PDF

```powershell
python docs/filling-program/make_pdf.py docs/filling-program.md <file>.pdf
```

pandoc (3.2 here) makes one HTML page with the pictures in it and the look of `pdf.css`; Chrome (else
Edge), headless, prints it. The browser returns before it has written the file, so the script waits
for it. The zip script makes the PDF itself.

## The contents, the version with screenshots, the zip

The contents at the top of the guide are made from its headings. After a heading changed, make
them again, and then the version with screenshots
([../filling-program-screenshots.md](../filling-program-screenshots.md)):

```powershell
python docs/filling-program/toc.py
python docs/filling-program/with_screenshots.py
```

The screenshots in `docs/figures/4diac_figs` are taken by hand in the IDE. After the program
changes, take them again under the same names (`with_screenshots.py` lists which are not used
because they are out of date).

The zip for students holds:
- the guide, its PDF, and the version with screenshots, with the pictures and screenshots;
- the templates;
- the module rules and the modules;
- the three module projects;
- the FORTE kit (`forte-kit.zip`) and its README;
- a README of its own.

Make the kit first, then the zip:

```powershell
runtime/make-kit.ps1
python docs/filling-program/student_zip.py filling-program-for-students.zip
```

`make-kit.ps1` takes the lab's exports from the last `build-modules.ps1` and the projects from the
last commit ([../forte-for-the-pi.md](../forte-for-the-pi.md)), so build and commit before.
