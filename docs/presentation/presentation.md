# Presentation brief: modules driven by their AAS

A brief for a design session that builds a PowerPoint deck (16:9) on this work. It gives the story,
the slides one by one, the figures to use and the facts to get right. The figures are PNG files in
[figures/](figures/), exported from the draw.io files in [../figures/](../figures/); the animations
for some slides are described in [animations.md](animations.md). State of the work: 27 Oct 2026.

## The talk

- **Who presents:** the person doing the work, at Aalborg University's Smart Production Lab. Put
  `[Presenter name]` on the title slide; the presenter fills it in.
- **To whom:** researchers and engineers in manufacturing automation (the lab, project partners, a
  conference audience). They know PLCs and Industry 4.0 terms; they may not know IEC 61499 or the
  Asset Administration Shell (AAS) in detail.
- **Length:** about 20 minutes, 19 main slides and a few backup slides.
- **The one thing to remember:** a module that arrives with its IEC 61499 program and its AAS can be
  checked, operated and changed while it runs, from those two alone.

The story runs in four parts:

1. **Why.** A pharmaceutical filling line has to change often; its modules come from vendors.
2. **What we want.** Modules that can be verified, operated and changed online from their program
   and their AAS alone.
3. **How, layer by layer.** The line, its digital assets, its behaviour in IEC 61499, the AAS models
   and the tools that work on them, the applications on top; then the pipeline from a product's
   need to a changed program.
4. **What runs today, and what comes next.** The lab's line with Raspberry Pis running FORTE, the
   tools, what is built and what is missing, the evaluation for the paper.

## Style

- White background, Arial (the figures use Arial), dark text `#252B2D`, secondary text `#6E777B`.
- The figures' colours carry meaning; reuse them for accents and never recolour the figures:

  | Colour | Hex | Means |
  | --- | --- | --- |
  | Orange | `#F07D2E` | The modules of the line (station lids, HMI module panels) |
  | Purple | `#9080B7` | The product and its recipe, product agents |
  | Green | `#5B963B` | The process, the bindings; IEC 61499 events; a Pi running its program |
  | Blue | `#6C91B2` | The resources and their AASs; OPC UA |
  | Gold | `#B88A1C` | The FORTE management protocol (online changes by `modsync`) |
  | Dashed outline | | Planned, not built yet |

- One message per slide, written as the slide title (a full short sentence). Little text on the
  slide: the figure carries it, the speaker notes hold the rest.
- Figures large. Many figure PNGs carry their own title row at the top; crop it away when the slide
  has its own title. The tall layer figures fit beside a text column or cropped to a part.
- Tool names stay in code style as written: `modgen`, `modreg`, `modsync`, `modlink`.

## The figures

**One figure per slide.** `slides-01-…png` to `slides-19-…png` are made for the slides: 16:9, 2400 ×
1350, big type, few elements, no title of their own (the slide has it). Each matches the slide of
the same number below. `slides-01-title-the-line.png` is the line alone, for the title slide. In
these PNGs a pixel is the draw.io page's coordinate times 1.5 (the page is 1600 × 900), which is what
a click animation's regions are given in.

**Detailed figures**, as alternatives, for backup slides or for questions:

| File | What it shows | Shape |
| --- | --- | --- |
| `module-tools-8-layers-slide.png` | The production system in five layers above the line, few words, big names on the right | Tall (3545×4462) |
| `module-tools-7-layers-illustrated.png` | The same layers in full: stations reaching over the vial, the asset tiles, the function block network and state machines, the AAS models, agents, servers, planner and HMI | Tall (3785×5037) |
| `module-tools-6-layers-programs.png`, `module-tools-5-layers-computers.png` | Earlier versions of the layers (programs as windows, or as computers) | Tall; backup only |
| `module-tools-4-concept-isometric.png` | Four layers: assets, control, information, applications | Square; backup |
| `module-tools-3-production-system.png` | The line as it stands, the inside of the filling module, the server with its applications | Wide |
| `module-tools-1-tools-and-forte.png` | The tools above the filling module's program as its function block network: create, read, update, delete on it | Wide |
| `module-tools-2-tools-and-forte-paper.png` | The same, small: the tools and the online change in Dispensing's network | Wide, compact |
| `ppr-models-1-models-and-ontologies.png` | Product, process and resource AAS with their submodels, and the ontologies their ids point into | Wide |
| `ppr-models-2-applications.png` | Which application reads and writes which AAS, and which acts on the running module | Wide |
| `reconfiguration-pipeline-1-reconfiguration-pipeline.png` | Nine steps from a product's recipe to a changed program and back; the redeployment baseline | Wide |
| `skill-hierarchies-3-hierarchies-paper.png` | Line, module, component, and a skill's steps running the components' primitives, as AAS trees | Wide, compact |
| `skill-hierarchies-4-recipe-to-process-paper.png` | The product's recipe bound to the modules' skills: the process AAS | Compact |
| `skill-hierarchies-1-hierarchies.png`, `skill-hierarchies-2-recipe-to-process.png` | The full versions of the two above | Backup |

## The slides

Each slide: its title (the message), what goes on it, the figure, and notes for the speaker.

### 1. Title

- **Figure:** `slides-01-title-the-line.png`.
- **Title:** Modules that describe themselves: IEC 61499 control driven by the Asset Administration
  Shell
- **Subtitle:** Verify, operate and change a running module from its program and its AAS
- `[Presenter name]`, Aalborg University, Smart Production Lab; date.
- **Detailed alternative:** `module-tools-8-layers-slide.png`, cropped to the line at the bottom.

### 2. A filling line has to change often

- **Figure:** `slides-02-change-often.png`.
- Pharmaceutical filling: small batches, many products, frequent changeovers.
- The line is built from modules: filling, stoppering, capping, inspection; robots load and unload.
- The modules come from vendors. Changing what one does today means engineering and a redeployment:
  the module stops.
- **Detailed alternative:** `module-tools-3-production-system.png`, the isometric line on the left of it.
- **Notes:** The question is not how to program one module, but how a line integrates and changes
  modules it did not build.

### 3. Our line: six modules around a maglev table

- **Figure:** `slides-03-our-line.png`.
- Transport: a B&R ACOPOS 6D maglev table with shuttles that carry the vials.
- Loading and unloading: Kuka robots with grippers. Filling, stoppering, capping, inspection
  stations.
- Each module runs on its own Raspberry Pi 5. Filling and stoppering are built; capping and
  inspection are specified, not built.
- **Detailed alternative:** `module-tools-3-production-system.png` (whole).
- **Notes:** The vial is filled, stoppered, capped and inspected on its way. The modules began as
  ESP32 stations and are now generated IEC 61499 programs.

### 4. What we want: a module is enough with its program and its AAS

- **Figure:** `slides-04-the-claim.png`.
- Large quote: *A module that is delivered with an IEC 61499 program and an AAS can be verified,
  operated and changed online from those two alone, without the files it was generated from.*
- Below it, small: it has to work for a vendor's module that comes with nothing else.
- **Notes:** This is the claim of the CIRP CMS paper (due 18 Nov 2026). Our own generator is one
  way to build such a module, not something an integrator has.

### 5. Three things to specify

- **Figure:** `slides-05-three-things-to-specify.png`.
- Three cards with icons:
  1. **How a module is built:** its control structure and interface (the module rules).
  2. **What its AAS holds:** the information model (the resource ontology ARSO).
  3. **How the AAS drives it:** register, verify, operate, change online, record.
- A fourth, dashed card: **the evaluation**: the same changes online and by redeployment, timed.
- **Notes:** The first three are built; the evaluation is being built now.

### 6. The production system in layers

- **Figure:** `slides-06-the-layers.png`.
- **Animation:** `layers-walk` (click); see [animations.md](animations.md).
- **Detailed alternative:** `module-tools-8-layers-slide.png` (tall), its own cards name the layers.
- Bottom to top: the line; digital assets (parts, IO, identity); behaviour (IEC 61499 programs on
  FORTE); AAS models and orchestration; applications (plan, change, operate).
- **Notes:** The next slides walk up the layers. Lines between layers: a station and its parts; a
  Pi runs the module's program; OPC UA from the orchestrator; the applications write the AAS models.

### 7. Digital assets: line, module, component

- **Figure:** `slides-07-digital-assets.png`.
- Every module is a linear axis (a stepper with a limit switch) plus one process component (the
  filling pump, the stoppering piston, the cap crimper, the cameras).
- The parts are wired to the module's Pi (GPIO, PWM); each has an AAS with its asset id.
- The line's AAS names its modules; a module's AAS names its components.
- **Detailed alternative:** `skill-hierarchies-3-hierarchies-paper.png`; optionally beside it a crop of the asset
  tiles (second layer) from `module-tools-7-layers-illustrated.png`.
- **Notes:** The same components and the same two axis skills recur in every module, which is what
  makes generation and checking possible.

### 8. Behaviour: every module follows the same rules in IEC 61499

- **Figure:** `slides-08-module-rules.png`.
- **Animation:** `skill-call` (autoplay), on a new slide after this one; see [animations.md](animations.md).
- Each module runs one IEC 61499 program on Eclipse 4diac FORTE.
- Fixed for every module: occupation (one client at a time), the module state machine (PackML), one
  state machine every skill shares, an OPC UA server.
- A skill primitive runs one command on one equipment item until a sensor, timer or timeout; a
  module level skill is a sequence of steps over the primitives.
- **Detailed alternative:** `module-tools-2-tools-and-forte-paper.png`, or the behaviour layer cropped from
  `module-tools-7-layers-illustrated.png` (function blocks, PackML, a skill's state machine).
- **Notes:** Because every module follows these rules, a tool can read a program back and know what
  each block is, and can add a skill online in a known pattern.

### 9. The information model: three kinds of AAS

- **Figure:** `slides-09-three-kinds-of-aas.png`.
- Following ISA-88: **product AAS** (the general recipe: what the product needs), **process AAS**
  (the master recipe: the recipe bound to one line), **resource AAS** (line, module, component: what
  it offers and how it is called).
- Each element's `semanticId` points into an ontology (ARSO for resources), its
  `supplementalSemanticId` into a domain vocabulary (what it means).
- **Detailed alternative:** `ppr-models-1-models-and-ontologies.png`.
- **Notes:** A reconfiguration changes the resource AAS and at most the process AAS; the product AAS
  is not touched. One owner per AAS: product designer, line engineer, vendor. The process AAS is a
  draft today.

### 10. What a module's AAS holds

- **Figure:** `slides-10-a-module-s-aas.png`.
- **Animation:** `verify-readback` (autoplay); see [animations.md](animations.md).
- Skills: each skill's commands, parameters with limits, and for a composite its steps.
- Capability Description: what it offers, derived from its skills.
- Interface description and mapping: the OPC UA endpoint and every action and variable.
- Control Configuration: what was built (instances, block types, type hashes, the change log).
- **Detailed alternative:** the Resource AAS box cropped from `ppr-models-1-models-and-ontologies.png`, or a list.
- **Notes:** Skills say what is wanted; the Control Configuration says what was built. Comparing the
  two with the running program is what verification and online change stand on.

### 11. From a product's recipe to the modules' skills

- **Figure:** `slides-11-from-recipe-to-skills.png`.
- The planner takes the product's recipe and matches each step's required capability against the
  capabilities the modules offer.
- Each step is bound to a module's skill with its parameters: the process AAS.
- Three answers: offered now, offered after a reconfiguration, not offered.
- **Detailed alternative:** `skill-hierarchies-4-recipe-to-process-paper.png`.
- **Notes:** "Offered after a reconfiguration" is what makes changing a module part of planning.

### 12. The tools around the AAS

- **Figure:** `slides-12-the-tools.png`.
- `modreg`: builds, checks and registers the AASs; derives capabilities from skills.
- Process sequence planner and skill editor: modules of the BaSyx web UI.
- `modsync`: compares the AAS with the running program, changes it online, verifies, records.
- `modlink` and the HMI: operate a module over OPC UA from its AAS.
- Agents: planned, after the paper.
- **Detailed alternative:** `ppr-models-2-applications.png`.

### 13. The reconfiguration pipeline

- **Figure:** `slides-13-the-pipeline.png`.
- **Animation:** `pipeline-flow` (autoplay) or `pipeline-walk` (click); see [animations.md](animations.md).
- Nine steps: recipe, match, change a skill, derive capabilities, compare and check, apply online,
  verify, record, bind and run.
- The baseline it is measured against: a new boot file and a restart.
- **Detailed alternative:** `reconfiguration-pipeline-1-reconfiguration-pipeline.png`.
- **Notes:** Steps 5 to 8 against the baseline are what the evaluation times. Example: the filling
  module gets a new skill, DoubleDose, made from Dispensing.

### 14. Changing a running program, block by block

- **Figure:** `slides-14-online-change.png`.
- **Animation:** `online-change` (autoplay, already built in the deck); see [animations.md](animations.md).
- Over FORTE's management protocol: create blocks, write values, connect, start; read the program
  back to verify.
- Online: a new skill, a step's constant, a parameter's limits. Removing needs a new boot file.
- **Detailed alternative:** `module-tools-1-tools-and-forte.png` (crop to the function block network if needed).
- **Notes:** The module keeps running while a skill is added. The new blocks join the program's INIT
  chain, and the record amends the boot file, so the change survives a restart.

### 15. What runs today

- **Figure:** `slides-15-what-runs-today.png`.
- Every module on its own Raspberry Pi 5; FORTE in Docker; the program as a boot file.
- The filling module's axis moves on its Pi under FORTE, started from the HMI.
- A BaSyx AAS server and web UI hold the example line's AASs: the line, its modules, their
  components, the product.
- Python tools: `modreg`, `modsync`, `modlink`; the web UI fork with the planner and the skill editor.
- **Detailed alternative:** `module-tools-7-layers-illustrated.png` (whole, beside a short text column).
- **Notes:** Verify, change a value, create a skill and record work online on the PC and on the
  Pi 5.

### 16. From a module spec to a running module

- **Figure:** `slides-16-from-spec-to-module.png`.
- **Animation:** `first-deployment` (autoplay); see [animations.md](animations.md).
- Our own route for building a conforming module: a module spec (YAML), `modgen` generates the 4diac
  project, the 4diac IDE checks and exports it, FORTE is built for the PC and the Pi, the program is
  deployed.
- `modreg` builds the module's AAS from the same spec; `modsync project` writes the 4diac project of
  what runs, so the IDE stays usable.
- **Detailed alternative:** `module-tools-1-tools-and-forte.png`, upper part (the tools); or a simple flow drawn on
  the slide: spec → modgen → 4diac IDE → FORTE build → Pi.
- **Notes:** The spec is ours; a vendor's module has none. After delivery the AAS and the running
  program are enough.

### 17. Built and missing

- **Figure:** `slides-17-built-and-missing.png`.
A two-column table (built / missing):

| Part | Built | Missing |
| --- | --- | --- |
| Spec to running module | Generation, IDE check, FORTE for PC and Pi, deployment | – |
| Module AAS | Resource AASs in ARSO 0.9, checked against the ontology | Registration on the lab's server; live values |
| Operate from the AAS | `modlink`, the HMI | – |
| Change from the AAS | Skill editor; verify, new skill, new value, record; on PC and Pi | Reordering or removing steps online |
| Change from a product | Matching, binding a step to a skill, capabilities derived from skills | The process AAS in use; "after a reconfiguration" in the planner; agents |

### 18. Next: the evaluation and the paper

- **Figure:** `slides-18-the-evaluation.png`.
- Scenario runner: plug a module in (register, verify, operate), change a constant, create a new
  skill; each timed (downtime, commands sent, time to verify), unattended.
- Baseline: the same changes by a new boot file and a restart, side by side.
- First with simulated IO on the PC, then on the Pis with the axis moving.
- CIRP CMS full paper, due 18 Nov 2026.
- **Notes:** No numbers yet; do not put any on the slide.

### 19. After the paper, and summary

- **Figure:** `slides-19-after-the-paper.png`.
- After the paper: the process AAS written by the planner; agents (a product agent per order and a
  resource agent per module bid for the steps); time series in the operational data; the HMI inside
  the web UI.
- Summary in three lines: modules built by fixed rules; described by their AAS; verified, operated
  and changed online from program and AAS alone.
- **Detailed alternative:** `module-tools-8-layers-slide.png` again, small, or the agents crop from
  `module-tools-7-layers-illustrated.png` (a vial and miniature modules).
- Thanks and contact.

### Backup slides

- `module-tools-4-concept-isometric.png`: the idea in four layers.
- `module-tools-5-layers-computers.png` and `module-tools-6-layers-programs.png`: the layers with the
  programs as computers or as windows.
- `skill-hierarchies-1-hierarchies.png` and `skill-hierarchies-2-recipe-to-process.png`: the full
  hierarchies and the full recipe-to-process figure.

## Terms, for the slides and the notes

| Term | Meaning here |
| --- | --- |
| AAS | Asset Administration Shell: the standard digital description of an asset, made of submodels |
| Submodel | One aspect of an AAS (Nameplate, Skills, Capability Description, ...) |
| IEC 61499 | The standard for distributed control applications built from function blocks |
| 4diac, FORTE | Eclipse 4diac: the IDE, and FORTE, the runtime that runs the program on the Pi |
| Management protocol | FORTE's protocol to create, connect, write and query blocks in a running program |
| OPC UA | How clients occupy a module, call its skills and follow its state |
| PackML | The state machine of a module (Stopped, Idle, Execute, ...) |
| Skill | Something a module can be asked to do: a primitive (one command on one equipment item) or a module level skill (a sequence of steps) |
| Capability | What a module can do for a product (Filling 0.5 to 10 mL), realized by a skill |
| ARSO | Our resource ontology: what each element of a resource AAS is |
| ISA-88 | The batch control standard whose recipe levels the three kinds of AAS follow |
| BaSyx | The Eclipse AAS server and web UI the lab uses |

## Facts to get right

- Built: filling and stoppering modules; capping and inspection are specified, not built. The
  stoppering module's program is not yet running on its Pi.
- Agents, the process AAS in use, and the evaluation numbers do not exist yet: say "planned" or
  "next", never show them as results.
- Online changes add skills and change values; removing blocks needs a new boot file.
- The lab's shared AAS server is not used yet; the AASs run on a local BaSyx server.
- There are no timing results yet; no slide shows numbers for downtime or speed.
