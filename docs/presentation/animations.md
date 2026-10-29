# Animation briefs

Briefs for the slides' animations, in the format of the animation guidelines: one per animation,
for Claude in the Slides deck to build. The `online-change` animation (a new skill created while
Dispensing executes) is already built and is not repeated here.

- Slide titles are those of [presentation.md](presentation.md). Where the deck's title differs, the
  slide is the one with the same figure.
- Figures are the PNGs in [figures/](figures/). In a `slides-…png` figure (2400 × 1350) a pixel is the
  draw.io page's coordinate times 1.5. The other figures were trimmed on export; their regions below
  are measured on the exported PNG.
- Names are those of the program and the AAS: OPC UA nodes below `/Objects/FillingModule`
  (`Occupation/Occupy`, `Module/Reset`, `Skills/Dispensing/Start`), every method answering
  `[Accepted, ErrorID]` at once; skill states `Idle`, `Running`, `Stopping`, `Succeeded`, `Failed`,
  `Aborted`; error codes `4 NotReady`, `5 NotPermitted`, `6 Busy`, `8 OutOfRange`.
- Every animation is an illustration, not a recording: no durations, counts or measured values.

| Id | Mode | Slide | Shows |
| --- | --- | --- | --- |
| `skill-call` | autoplay | New slide after "Behaviour: every module follows the same rules in IEC 61499" | Inside a module: OPC UA calls, the PackML state machine, the skill's state machine, its steps driving the equipment |
| `first-deployment` | autoplay | "From a module spec to a running module" | The boot file building the function block network, then the INIT chain bringing it up |
| `pipeline-flow` | autoplay | "The reconfiguration pipeline" | One change from a product's need through the AAS into the running program and back to the plan |
| `pipeline-walk` | click | "The reconfiguration pipeline" (the deck: "The AAS drives the reconfiguration, in nine steps") | The nine steps of the full pipeline figure in five beats |
| `layers-walk` | click | "The production system in layers" | The five layers, from the line up |
| `verify-readback` | autoplay | "What a module's AAS holds" | `modsync` reading the program back, finding a difference, writing it, checking again |
| `filling-motion` | click or autoplay, in PowerPoint | New slide beside `skill-call` | The filling module itself moving (the vial arriving, the needle down and up, the vial filling) in step with PackML, the skill's states and its steps |

## skill-call

```yaml
animation:
  id: skill-call
  slide: "new slide after 'Behaviour: every module follows the same rules in IEC 61499'"
  title: "A skill call: OPC UA in, state machines inside"      # suggested title for the new slide
  mode: autoplay
  message: >
    A client occupies the module, brings it to Execute and starts a skill over OPC UA; the module's
    state machine, the skill's state machine and its steps do the rest.
  replaces: nothing
  fallback: slides-08-module-rules.png
  stage: full
  loop: loop
  hold_end_s: 4
  pace_s: 1.6

  elements:
    - {id: title, kind: label, label: "FillingModule · FORTE on its Pi", place: "top-left"}
    - {id: calls, kind: log, label: "HMI → OPC UA methods", place: "left column, 620 wide, top half"}
    - {id: server, kind: panel, label: "OPC UA · /Objects/FillingModule", role: opcua,
       place: "left column, under the log, 620 wide"}
    - {id: v_occ, kind: label, in: server, label: "Occupation/Occupied = false"}
    - {id: v_mod, kind: label, in: server, label: "Module/State = Stopped"}
    - {id: v_skill, kind: label, in: server, label: "Dispensing/State = Idle"}
    - {id: v_vol, kind: label, in: server, label: "Dispensing/Parameters/Volume"}
    - {id: v_res, kind: label, in: server, label: "Dispensing/Results/Weight"}
    - {id: module, kind: group, label: "Module · PackML", role: module,
       place: "right, top, about 1040 × 140"}
    - {id: packml, kind: block-row, in: module, labels: [Stopped, Resetting, Idle, Starting, Execute]}
    - {id: occ, kind: pill, label: "free", role: neutral, place: "in the module group's title row, right"}
    - {id: skill, kind: group, label: "Dispensing · a module level skill", role: neutral,
       place: "right, under the module, about 1040 × 300"}
    - {id: sstates, kind: block-row, in: skill, labels: [Idle, Running, Succeeded]}
    - {id: steps, kind: block-row, in: skill, labels: [NeedleDown, Dispense, Home, Weigh], connect: event}
    - {id: tok, kind: token, start: hidden}
    - {id: equip, kind: group, label: "Equipment", role: neutral, place: "right, bottom, about 1040 × 120"}
    - {id: eq, kind: block-row, in: equip, labels: [LinearAxis, Pump, Scale]}
    - {id: refused, kind: pill, label: "refused: not occupied", role: planned, place: "under the log",
       start: hidden}

  ambient:
    - "The current PackML state and the current skill state stay highlighted"

  steps:
    - say: "Dispensing/Start(s1, 2.0) → False, 5"
      do: [{appear: refused}, {flash: sstates.Idle, role: planned}]
    - say: "Occupation/Occupy(s1) → True, 0"
      do: [{disappear: refused}, {set: {occ: "occupied: s1"}}, {set: {v_occ: "Occupation/Occupied = true"}}]
    - say: "Module/Reset(s1) → True, 0"
      do: [{highlight: packml.Resetting, role: running}, {set: {v_mod: "Module/State = Resetting"}},
           {flash: eq.LinearAxis, role: module}]
    - say: "Resetting: the axis homes"
      do: [{highlight: packml.Idle, role: running}, {set: {v_mod: "Module/State = Idle"}}]
    - say: "Module/Start(s1) → True, 0"
      do: [{highlight: packml.Starting, role: running}, {wait: 0.6}, {highlight: packml.Execute, role: running},
           {set: {v_mod: "Module/State = Execute"}}]
    - say: "Dispensing/Start(s1, 2.0) → True, 0"
      do: [{set: {v_vol: "Dispensing/Parameters/Volume = 2.0"}}, {highlight: sstates.Running, role: running},
           {set: {v_skill: "Dispensing/State = Running"}}, {appear: tok}]
    - say: "NeedleDown: the axis moves"
      do: [{move: tok, along: [steps.NeedleDown]}, {flash: eq.LinearAxis, role: module}]
    - say: "Dispense: the pump runs"
      do: [{move: tok, along: [steps.NeedleDown, steps.Dispense]}, {flash: eq.Pump, role: module}]
    - say: "Home, Weigh"
      do: [{move: tok, along: [steps.Dispense, steps.Home, steps.Weigh]}, {flash: eq.LinearAxis, role: module},
           {flash: eq.Scale, role: module}]
    - say: "Succeeded; the weight is published"
      do: [{disappear: tok}, {highlight: sstates.Succeeded, role: running},
           {set: {v_skill: "Dispensing/State = Succeeded"}}, {set: {v_res: "Dispensing/Results/Weight ✓"}}]
    - say: "back to Idle by itself"
      do: [{highlight: sstates.Idle, role: running}, {set: {v_skill: "Dispensing/State = Idle"}}]
    - say: "Occupation/Release(s1) → True, 0"
      do: [{set: {occ: "free"}}, {set: {v_occ: "Occupation/Occupied = false"}}]

  facts:
    - "Every method answers [Accepted, ErrorID] at once; True, 0 is accepted. False, 5 is NotPermitted"
    - "A skill starts only for the session that holds the occupation, with the module in Execute"
    - "Module/Reset runs the Resetting procedure, which homes the axis to its limit switch; then Idle"
    - "The steps follow each other by events: each step's SUCCESS starts the next"
    - "Succeeded returns to Idle by itself; no Reset is needed"
    - "Volume = 2.0 is the parameter handed to Start, not a measurement; no result value is shown"
    - "The PackML state machine is the module's; each skill has its own small state machine"

  notes: >
    This is what the HMI or modlink does with a module, and all it needs is in the module's AAS:
    the interface description names each method and variable. The first call is refused because the
    client has not occupied the module. Occupy, Reset (the axis homes), Start brings the module to
    Execute; then the skill's Start with its parameter. Inside, Dispensing runs its steps one after
    another, each step a skill primitive driving one equipment item. The animation is an
    illustration of the order of things, not a recording.
```

## first-deployment

```yaml
animation:
  id: first-deployment
  slide: "From a module spec to a running module"
  mode: autoplay
  message: >
    At deployment the boot file builds the module's program block by block, with the same create,
    connect and write commands that later change it online.
  replaces: nothing
  fallback: slides-16-from-spec-to-module.png
  stage: full
  loop: loop
  hold_end_s: 4
  pace_s: 1.6

  elements:
    - {id: title, kind: label, label: "forte.fboot → FORTE on the Pi", place: "top-left"}
    - {id: log, kind: log, label: "boot file · management commands", place: "right column, 560 wide, full height"}
    - {id: app, kind: group, label: "FillingModule · the application", role: neutral,
       place: "left, about 1100 × 470"}
    - {id: start, kind: block, in: app, label: "START", note: "the resource's own start block", place: "top-left of app"}
    - {id: shell, kind: block-row, in: app, labels: [Occupation, Module], start: hidden}
    - {id: equip, kind: block-row, in: app, labels: [LinearAxis, Pump, Scale], start: hidden}
    - {id: disp, kind: group, in: app, label: "Dispensing", role: neutral, start: hidden}
    - {id: core, kind: block-row, in: disp, labels: [Control, UaStart, Volume], start: hidden}
    - {id: exec, kind: block-row, in: disp, labels: [NeedleDown, Dispense, Home, Weigh], start: hidden}
    - {id: init, kind: line, as: event, note: "the INIT chain: START, Occupation, Module, equipment, Dispensing",
       start: hidden}
    - {id: tok, kind: token, start: hidden}
    - {id: ua, kind: panel, label: "OPC UA · /Objects/FillingModule", role: opcua,
       place: "left, under the application, 1100 wide", start: hidden}
    - {id: ua_occ, kind: label, in: ua, label: "Occupation", start: hidden}
    - {id: ua_mod, kind: label, in: ua, label: "Module", start: hidden}
    - {id: ua_skill, kind: label, in: ua, label: "Skills/Dispensing", start: hidden}
    - {id: state, kind: pill, label: "Stopped, not occupied", role: neutral, place: "bottom-left", start: hidden}

  steps:
    - say: "CREATE Occupation, Module"
      do: [{appear: shell, from: below}, {flash: shell, role: management}]
    - say: "CREATE LinearAxis, Pump, Scale"
      do: [{appear: equip, from: below}, {flash: equip, role: management}]
    - say: "WRITE IO addresses: gpio[…], pwm[…]"
      do: [{flash: equip, role: management}]
    - say: "CREATE Dispensing: Control, UaStart"
      do: [{appear: disp}, {appear: core, from: below}, {flash: core, role: management}]
    - say: "CREATE NeedleDown, Dispense, Home, Weigh"
      do: [{appear: exec, from: below}, {flash: exec, role: management}]
    - say: "CONNECT events and data"
      do: [{connect: [core, exec], as: event}, {connect: exec, as: event}]
    - say: "CONNECT the INIT chain"
      do: [{appear: init}]
    - say: "START"
      do: [{appear: tok}, {appear: ua}, {move: tok, along: [start, shell.Occupation, shell.Module]},
           {appear: ua_occ}, {appear: ua_mod}]
    - say: "INIT: equipment, then the skill"
      do: [{move: tok, along: [equip.LinearAxis, equip.Pump, equip.Scale, core.Control]}, {appear: ua_skill}]
    - say: "Running: Stopped, not occupied"
      do: [{disappear: tok}, {appear: state}]

  facts:
    - "The boot file is a list of management protocol commands that FORTE runs at start"
    - "START belongs to the resource; the boot file creates the application's blocks, not START"
    - "Block types are compiled into FORTE; only instances, connections and values are created"
    - "Each block's INITO starts the next block's INIT; a block created online later joins the end of the chain"
    - "The OPC UA nodes appear when their blocks are initialised"
    - "The module starts Stopped and not occupied"

  notes: >
    A first deployment, the way modgen and the deployment script do it: the boot file is nothing but
    the commands of FORTE's management protocol, create this block, connect that, write a value. The
    online change later uses exactly these commands while the program runs. When the resource
    starts, the INIT chain brings the blocks up in order, and each publishes its OPC UA nodes. An
    illustration of the order, not a recording.
```

## pipeline-flow

```yaml
animation:
  id: pipeline-flow
  slide: "The reconfiguration pipeline"
  mode: autoplay
  message: >
    A product asks for something no module offers yet; the change runs through the AAS into the
    running program and back into the plan.
  replaces: nothing
  fallback: slides-13-the-pipeline.png
  stage: full
  loop: loop
  hold_end_s: 5
  pace_s: 1.8

  elements:
    - {id: plan, kind: group, label: "Product · process AAS", role: product, place: "top band, full width, 180 high"}
    - {id: step, kind: block, in: plan, label: "Fill 12 mL", role: product, place: "left"}
    - {id: cap, kind: pill, in: plan, label: "not offered", role: planned, place: "middle"}
    - {id: bind, kind: pill, in: plan, label: "→ DoubleDose", role: running, place: "right", start: hidden}
    - {id: aas, kind: group, label: "Resource AAS · FillingModule", role: neutral, place: "middle band, full width, 220 high"}
    - {id: skills, kind: panel, in: aas, label: "Skills", rows: ["Dispensing"], place: "left third"}
    - {id: s_dd, kind: label, in: skills, label: "DoubleDose", start: hidden}
    - {id: caps, kind: panel, in: aas, label: "Capabilities", rows: ["Filling_Dispensing"], place: "middle third"}
    - {id: c_dd, kind: label, in: caps, label: "Filling_DoubleDose", start: hidden}
    - {id: cc, kind: panel, in: aas, label: "Control Configuration", rows: ["Dispensing built"], place: "right third"}
    - {id: cc_dd, kind: label, in: cc, label: "DoubleDose built", start: hidden}
    - {id: mod, kind: group, label: "Module · FORTE", role: module, place: "bottom band, full width, 160 high"}
    - {id: p_disp, kind: block, in: mod, label: "Dispensing"}
    - {id: p_dd, kind: block, in: mod, label: "DoubleDose", role: new, start: hidden}
    - {id: actor, kind: pill, label: "Planner", role: neutral, place: "top-right corner, above the bands"}
    - {id: tok, kind: token, start: hidden}

  steps:
    - say: "Planner: match the step"
      do: [{highlight: step, role: product}, {set: {actor: "Planner"}}]
    - say: "Not offered: change a skill"
      do: [{flash: cap, role: planned}]
    - say: "Skill editor: DoubleDose from Dispensing"
      do: [{set: {actor: "Skill editor"}}, {appear: s_dd}, {flash: s_dd, role: new}]
    - say: "modreg: derive the capabilities"
      do: [{set: {actor: "modreg"}}, {appear: c_dd}, {state: cap, to: "after change", role: new}]
    - say: "modsync: compare with the program"
      do: [{set: {actor: "modsync"}}, {highlight: skills, role: opcua, for_s: 1}, {highlight: p_disp, role: opcua, for_s: 1}]
    - say: "modsync: create it online"
      do: [{appear: p_dd}, {connect: [s_dd, p_dd], as: management}, {flash: p_dd, role: management}]
    - say: "modsync: read back, verify"
      do: [{highlight: p_dd, role: opcua, for_s: 1}]
    - say: "modsync: record what was built"
      do: [{appear: cc_dd}, {flash: cc_dd, role: management}]
    - say: "Planner: match again"
      do: [{set: {actor: "Planner"}}, {state: cap, to: "offered now", role: running}]
    - say: "Bind the step in the process AAS"
      do: [{appear: bind}]
    - say: "Occupy, Start over OPC UA"
      do: [{appear: tok}, {move: tok, along: [bind, p_dd]}, {highlight: p_dd, role: running}]

  facts:
    - "The product AAS does not change; the resource AAS changes, and the process AAS gets the binding"
    - "Steps compare, create, verify and record are what the evaluation will time; no numbers here"
    - "Dispensing stays as it was and offers Filling up to 10 mL; DoubleDose is a new skill made from it that fills twice"
    - "Until DoubleDose is built, its capability is offered with Availability = AfterReconfiguration"
    - "The planner, the skill editor, modreg and modsync are separate tools; the actor pill names who acts"

  notes: >
    The whole pipeline in one loop. The planner finds that no module offers the step; the skill
    editor makes DoubleDose from Dispensing in the module's AAS; modreg derives the capability it
    offers once built; modsync compares the AAS with the running program, creates the skill online,
    reads it back and records what was built. Matching again, the step is offered now, it is bound in
    the process AAS and started over OPC UA. An illustration, not a recording.
```

## pipeline-walk

The regions are measured on `reconfiguration-pipeline-1-reconfiguration-pipeline.png` as exported
(3358 × 1920, title row included), with a margin of about 12 px around the cards.

```yaml
animation:
  id: pipeline-walk
  slide: "The reconfiguration pipeline"          # the deck: "The AAS drives the reconfiguration, in nine steps"
  mode: click
  message: The nine steps in five beats, at the speaker's pace.
  figure: reconfiguration-pipeline-1-reconfiguration-pipeline.png
  figure_size: [3358, 1920]
  fallback: reconfiguration-pipeline-1-reconfiguration-pipeline.png

  elements:
    - {id: s12, kind: spotlight, region: {x: 91, y: 284, w: 1044, h: 354}, role: product}
    - {id: s34, kind: spotlight, region: {x: 616, y: 756, w: 1044, h: 339}, role: neutral}
    - {id: s58, kind: spotlight, region: {x: 1186, y: 756, w: 1524, h: 834}, role: management}
    - {id: sb2, kind: spotlight, region: {x: 91, y: 1301, w: 1044, h: 249}, role: planned}
    - {id: s9, kind: spotlight, region: {x: 2236, y: 284, w: 999, h: 354}, role: opcua}
    - {id: srun, kind: spotlight, region: {x: 2761, y: 1236, w: 474, h: 459}, role: running}
    - {id: c12, kind: callout, label: "Not offered as it stands", near: s12}
    - {id: c34, kind: callout, label: "A changed skill", near: s34}
    - {id: c58, kind: callout, label: "Online, while it runs", near: s58}
    - {id: cb2, kind: callout, label: "Or redeploy: it stops", near: sb2}
    - {id: c9, kind: callout, label: "Offered now: run it", near: s9}

  steps:                             # one click each; earlier spotlights fade when the next appears
    - do: [{appear: s12}, {appear: c12}]
    - do: [{appear: s34}, {appear: c34}]
    - do: [{appear: s58}, {appear: c58}]
    - do: [{appear: sb2}, {appear: cb2}]
    - do: [{appear: s9}, {appear: srun}, {appear: c9}]

  facts:
    - "Steps 1–2 and 9 are the planner's (product and process AAS); 3–4 and 8 change the resource AAS"
    - "Steps 5–8 run on the module online; the baseline B2 is the same change by a new boot file"
    - "Step 9 runs over OPC UA; steps 5–8 against B2 are what the evaluation will time (no numbers yet)"

  notes: >
    Walk the figure: the product's step is not offered; a skill is changed and its capability
    derived; modsync checks, applies online, verifies and records; the alternative is a redeployment,
    which stops the module; matched again, the step is bound and run.
```

## layers-walk

Regions on `slides-06-the-layers.png` (2400 × 1350): band *i* from the top is the page's
(40, 30 + 172 *i*, 1520, 152), times 1.5, with a margin of 9 px.

```yaml
animation:
  id: layers-walk
  slide: "The production system in layers"
  mode: click
  message: The production system from the line up, one layer per click.
  figure: slides-06-the-layers.png
  figure_size: [2400, 1350]
  fallback: slides-06-the-layers.png

  elements:
    - {id: l_line, kind: spotlight, region: {x: 51, y: 1068, w: 2298, h: 246}, role: module}
    - {id: l_assets, kind: spotlight, region: {x: 51, y: 810, w: 2298, h: 246}, role: neutral}
    - {id: l_behaviour, kind: spotlight, region: {x: 51, y: 552, w: 2298, h: 246}, role: running}
    - {id: l_aas, kind: spotlight, region: {x: 51, y: 294, w: 2298, h: 246}, role: opcua}
    - {id: l_apps, kind: spotlight, region: {x: 51, y: 36, w: 2298, h: 246}, role: product}
    - {id: c_line, kind: callout, label: "Six modules, one table", near: l_line}
    - {id: c_assets, kind: callout, label: "Parts wired to a Pi", near: l_assets}
    - {id: c_behaviour, kind: callout, label: "Same rules everywhere", near: l_behaviour}
    - {id: c_aas, kind: callout, label: "Describe, coordinate", near: l_aas}
    - {id: c_apps, kind: callout, label: "Plan, change, operate", near: l_apps}

  steps:
    - do: [{appear: l_line}, {appear: c_line}]
    - do: [{appear: l_assets}, {appear: c_assets}]
    - do: [{appear: l_behaviour}, {appear: c_behaviour}]
    - do: [{appear: l_aas}, {appear: c_aas}]
    - do: [{appear: l_apps}, {appear: c_apps}]

  facts:
    - "Process AAS, MES and ERP, and the cameras are planned (dashed in the figure)"
    - "The next slides take the layers one by one"

  notes: >
    From the bottom: the line; its parts as digital assets, wired to each module's Pi; the modules'
    programs on FORTE; the AAS models and the tools that coordinate; the applications on top.
```

## verify-readback

```yaml
animation:
  id: verify-readback
  slide: "What a module's AAS holds"
  mode: autoplay
  message: >
    modsync reads the running program back and compares it with what the AAS says is wanted and
    was built; a difference is written online and checked again.
  replaces: nothing
  fallback: slides-10-a-module-s-aas.png
  stage: full
  loop: loop
  hold_end_s: 4
  pace_s: 1.6

  elements:
    - {id: wanted, kind: panel, label: "Skills · wanted", role: running, place: "left column, 520 wide, top"}
    - {id: w1, kind: label, in: wanted, label: "Dispensing: 4 steps"}
    - {id: w2, kind: label, in: wanted, label: "NeedleDown.Position 40.0"}
    - {id: built, kind: panel, label: "Control Configuration · built", role: running,
       place: "middle column, 520 wide, top"}
    - {id: b1, kind: label, in: built, label: "Dispensing: 4 instances"}
    - {id: b2, kind: label, in: built, label: "type hashes"}
    - {id: prog, kind: panel, label: "Running program · true", role: module, place: "right column, 520 wide, top"}
    - {id: r1, kind: label, in: prog, label: "Dispensing: 4 instances", start: hidden}
    - {id: r2, kind: label, in: prog, label: "type hashes", start: hidden}
    - {id: r3, kind: label, in: prog, label: "NeedleDown.Position 35.0", start: hidden}
    - {id: ok1, kind: chip, label: "✓", place: "right of r1", role: running, start: hidden}
    - {id: ok2, kind: chip, label: "✓", place: "right of r2", role: running, start: hidden}
    - {id: diff, kind: pill, label: "differs from the AAS", role: new, place: "under the right column", start: hidden}
    - {id: ok3, kind: chip, label: "✓", place: "right of r3", role: running, start: hidden}
    - {id: log, kind: log, label: "modsync → management protocol", place: "bottom, full width, 220 high"}
    - {id: status, kind: pill, label: "verified, recorded", role: running, place: "bottom-right", start: hidden}

  steps:
    - say: "QUERY Dispensing: FBs, connections"
      do: [{appear: r1}, {flash: prog, role: opcua}]
    - say: "compare the instances"
      do: [{highlight: w1, role: opcua, for_s: 1}, {highlight: b1, role: opcua, for_s: 1}, {appear: ok1}]
    - say: "QUERY type hashes"
      do: [{appear: r2}, {highlight: b2, role: opcua, for_s: 1}, {appear: ok2}]
    - say: "READ NeedleDown.Position"
      do: [{appear: r3}]
    - say: "the value differs from the AAS"
      do: [{highlight: w2, role: new}, {highlight: r3, role: new}, {appear: diff}]
    - say: "WRITE NeedleDown.Position 40.0"
      do: [{set: {r3: "NeedleDown.Position 40.0"}}, {flash: r3, role: management}]
    - say: "READ NeedleDown.Position"
      do: [{disappear: diff}, {appear: ok3}]
    - say: "RECORD Control Configuration"
      do: [{flash: built, role: management}, {appear: status}]

  facts:
    - "The AAS is the desired state; the running program is read back over the management protocol"
    - "Skills say what is wanted, the Control Configuration what was built, the program what is true"
    - "A value is written online; the module keeps running; the write is within the parameter's limits"
    - "Position values are a step's constant, not measurements"

  notes: >
    Verification without the files the module was generated from: modsync reads the program back,
    compares instances and type hashes with the Control Configuration, and values with the Skills.
    A step's constant differs, so it is written online to what the AAS says and read back again;
    then the record. An illustration, not a recording.
```

## filling-motion

The physical module moving with its state machines, for PowerPoint. Unlike the briefs above, it is
built from a draw.io figure cut into layers: `docs/figures/module-motion.drawio`, page "Filling
module in motion", a front view of the filling module beside its PackML and Dispensing state
machines. Each part that moves or switches is a layer of its own, and
`python docs/figures/export_layers.py docs/figures/module-motion.drawio docs/presentation/figures/filling-motion`
exports every layer as a PNG of the whole page (2400 × 1350, transparent). Stacked on a slide at the
same place and size, the layers line up; each gets its own animation. `00-still.png` is the figure
as one picture, for a slide without animation.

**How to set it up.** Insert all PNGs of `filling-motion/` except `00-still.png` at once, each at
position 0, 0 and the slide's full size (13.33 × 7.5 in). Keep the file order as the stacking order
(01 at the back). Layers 01, 03 and 10 are always shown; every other layer starts hidden and comes in
with its first animation (Appear, or the effect below). After an edit in draw.io, export again and use
*Change Picture* on each picture: its animations stay.

| Layers | What | PowerPoint |
| --- | --- | --- |
| `01-module` | Frame, lid, stepper motor, column, home switch, Pi, table, scale | Always shown |
| `02-shuttle-and-vial` | The vial on its shuttle | Fly In from the left; Fly Out to the right at the end |
| `03-carriage` | Carriage, arm, pump, needle, drawn at home | Motion path, a line straight down by **28.9 % of the slide's height** (40 mm, 260 of the page's 900 px), and the same line back up |
| `04-home-switch-pressed` | Green ring, `AtHome` | Appear while the carriage is at the switch |
| `05-step-pulses` | Pulse train, ring on the motor | Appear while the carriage moves |
| `06-travel-40-mm` | Dimension of NeedleDown's 40 mm | Appear with the move down |
| `07-pump-running` | Ring on the pump, the stream, drawn where the pump is when down | Appear during Dispense |
| `08-liquid` | 2 mL in the vial | Wipe from the bottom during Dispense; Fly Out to the right *with* the shuttle |
| `09-weight-2-0-g` | The scale reads 2.0 g | Appear at Weigh |
| `10-state-machines` | The OPC UA call box, PackML, Dispensing's states and steps, plain | Always shown |
| `11` to `15` | PackML Stopped, Resetting, Idle, Starting, Execute highlighted | Appear on entry, Disappear on exit |
| `16-occupied` | Occupation: `occupied · s1` over `free` | Appear at Occupy, Disappear at Release |
| `17` to `19` | Skill Idle, Running, Succeeded highlighted | Appear on entry, Disappear on exit |
| `20` to `23` | Step NeedleDown, Dispense, Home, Weigh highlighted | Appear when the step starts, Disappear when it ends |
| `24-call-01` to `34-call-11` | The line in the OPC UA call box | Each Appears and the one before Disappears (*With Previous*) |

**The beats** (one click each, or *After Previous* for autoplay; within a beat everything is *With
Previous* unless it says *after*). At the start: 01, 03, 10, `11-packml-stopped`, `17-skill-idle`.

| # | Call line | What moves or switches |
| --- | --- | --- |
| 1 | – | `02` flies in: the vial arrives under the needle |
| 2 | `24` Start refused, not occupied | – |
| 3 | `25` Occupy | `16` appears |
| 4 | `26` Reset, the axis homes | `11` off, `12` on; `05` on; *after* `04` on, `05` off; *after* `12` off, `13` on |
| 5 | `27` Module Start | `13` off, `14` on; *after* `14` off, `15` on |
| 6 | `28` Dispensing Start | `17` off, `18` on |
| 7 | `29` NeedleDown | `20` on, `04` off, `05` on, `06` on; `03` moves down; *after* `05` off |
| 8 | `30` Dispense | `20` off, `21` on, `07` on; `08` wipes up; *after* `07` off |
| 9 | `31` Home | `21` off, `22` on, `06` off, `05` on; `03` moves up; *after* `04` on, `05` off |
| 10 | `32` Weigh | `22` off, `23` on, `09` on |
| 11 | `33` Succeeded, then Idle | `23` off, `18` off, `19` on; *after* `19` off, `17` on |
| 12 | `34` Release | `16` off; `02` and `08` fly out to the right together; `09` off |

Facts, as for `skill-call`: every method answers `[Accepted, ErrorID]` at once (`True, 0` accepted,
`False, 5` NotPermitted); a skill starts only for the session that occupies the module, in Execute;
Reset homes the axis to its limit switch; the steps follow each other by events; Succeeded returns to
Idle by itself. The pump and the scale are not real hardware yet: the pump is a time at a flow rate,
the scale is simulated (dashed). No durations or measured values; an illustration, not a recording.
