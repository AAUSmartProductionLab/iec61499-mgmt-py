# The deck's figures: how they are built and how to animate them

For whoever designs the slides (a person or an LLM) from **[deck.drawio](deck.drawio)**: every figure of
the talk in one draw.io file, one page per slide, in the order of the story. This guide says what each
page is for, how its layers and groups are made, and how to turn the layers into PowerPoint
animations. The facts behind the figures are in [presentation.md](presentation.md) (terms, facts to get
right) and [animations.md](animations.md) (the filling module's animation, beat by beat).

## Files

| What | Where |
| --- | --- |
| The figures, editable | `docs/presentation/deck.drawio` (open in draw.io or the VS Code draw.io extension) |
| Every page as one picture, and every layer as its own picture | `docs/presentation/figures/deck/<page>/00-still.png` and `<nn>-<layer>.png` |
| The exporter | `python docs/figures/export_layers.py docs/presentation/deck.drawio <out-dir> --page <n>` (n from 0) |

A page of 1600 × 900 exports at 2400 × 1350 (a slide at 16:9; a pixel is the page's coordinate × 1.5).
Every layer's PNG is the size of the whole page and transparent outside what it draws, so the layers of
a page stacked at the same place and size line up exactly. `00-still.png` is the page as it looks with
the layers that are visible in the file: use it where a slide has no animation.

## Conventions

- **An AAS is always the shell**: an arch with rounded corners in green `#2A918B`, its name on the band,
  nothing inside (the PPR page puts a picture of the product, process or resource inside). It is a
  draw.io stencil, so it scales to any size and takes its colour from the fill (Format panel). To reuse
  it, copy a group whose name ends in "AAS" (e.g. "Filling module AAS"), or the 20 px shells in the
  tree pages. A submodel is a grey bar (`#A7ACB6`, white bold text) under or beside its shell.
- **Colours carry meaning** (as in [presentation.md](presentation.md)): orange `#F07D2E` the modules,
  purple `#9080B7` the product, green `#5B963B` IEC 61499 events and a Pi running its program, blue
  `#6C91B2` resources and OPC UA, gold `#B88A1C` modsync and the management protocol, teal `#2A918B` an
  AAS. A dashed outline is planned, not built (agents, the pump and the scale's hardware).
- **Arial** everywhere; dark text `#252B2D`, secondary `#6E777B`.
- **A layer is a unit of animation; a group is a unit of moving and editing.** Each thing that appears,
  disappears or moves on its own is a layer; the parts of one thing are a group, nested where a part has
  parts (the vial inside "Shuttle with vial", the pump and the needle inside "Carriage"). A group's name
  is its tooltip (hover in draw.io; Edit › Edit Tooltip). Select a group to move it whole; double-click
  into it to change one part.
- **Layers stack in the order listed**: the first at the back. Layers hidden in the file are the ones an
  animation brings in; text that overlaps in a page with all layers on (calls, messages, highlights) is
  meant to be shown one at a time.
- **No titles in the new pages**: the slide has its own title. The copied pages keep their old title in a
  layer of its own, "page title (the slide has its own)": hide it or crop it away.

## How to animate a page in PowerPoint

1. Insert all `<nn>-<layer>.png` of the page at once, each at position 0, 0 and the slide's full size
   (13.33 × 7.5 in). Keep the file order as the stacking order (`01` at the back).
2. Layers visible in the file are shown from the start; every other layer gets its first effect
   (Appear, Fade, Wipe, Fly In) and later a Disappear.
3. A move is a Motion Path (a straight line). Lengths are given below in page pixels; as a share of the
   slide, divide by 900 for up and down, by 1600 for left and right (40 mm on the filling module is
   260 px: 28.9 % of the slide's height).
4. After an edit in draw.io, export again and use *Change Picture* on each picture: its animations stay.

Morph works too for a move: duplicate the slide, move the layer's picture, set the transition to Morph.

## The story, page by page

The pages follow the talk: the line; one module pulled out, physical and digital; how its program is
structured; the filling module running; the AAS models; skills in the AAS; from the AAS to function
blocks; the rules. A suggested slide title (the message) is given per page.

### 01 The line

*"Six modules around a maglev table; the filling module is one of them."*

| Layer | What | Animation |
| --- | --- | --- |
| `line` | The table, the robots, the stations (the slide figure of the line) | Shown |
| `filling module (to pull out)` | Group "Filling module: station, arm, name tag" | The pull-out: a Motion Path up and to the left (about 200 px up) with Grow/Shrink 150 %, then the next slide |
| `labels` | Six groups, "Label …": a label with its leader line and dot | Fade out before the pull-out |

The pulled-out station leads into page 03, whose physical tree starts with the same station picture.

### 02 Digital assets: line, modules, components (kept as it was)

*"Every asset has its own AAS: the line, each module, each component."* One layer; a group per module
column ("Filling module and its components", …) and "The line". For a reveal, animate the pictures of
the still, or copy the groups to layers in draw.io.

### 03 The filling module: physical and digital

*"A module ships with its parts, an AAS for each, and its IEC 61499 program."* Three parallel trees,
one row per part: the module, the linear axis, the pump, the scale, the Pi.

| Layer | What | Animation |
| --- | --- | --- |
| `physical` | The station and its parts as a tree (pictures from page 02), the Pi | Shown |
| `AAS` | The module's shell with its seven submodels; a shell per component with its Skills | Wipe from the left |
| `IEC 61499 program` | The boot file's application (Occupation, Module, Dispensing, procedures, OPC UA server, START); per component its equipment block and primitive types; FORTE with the types compiled in | Wipe from the left |
| `same part (links)` | Dashed lines joining one part across the three trees | Fade |

Facts: the pump is not wired (dispensing is a time) and the scale is simulated; the Pi has no AAS of its
own; a component's AAS holds its Skills.

### 04 The IEC 61499 program: the module rules

*"Every module's program is built by the same rules."* One layer per band, so the bands can come in one
by one (`OPC UA server` to `Equipment IO`), then the two brackets ("the same in every module",
"the module's own"). `frame` holds the program's frame and title.

### 05 The filling module in motion: an orchestrator

*"Inside the filling module: commands in, states change, the needle moves."* The same figure as
`docs/figures/module-motion.drawio`; its 29 layers and the 12 beats are in
[animations.md](animations.md#filling-motion) (the layer numbers there are this page's).

### 06 The filling module in motion: agents bid (planned)

*"Later: the product's agent asks, the module's agent bids and then runs its skill."* Page 05 with the
orchestrator replaced by agents, all dashed (planned, the paper's future work).

| Layer | What |
| --- | --- |
| `agents` | Product agent (the vial, purple), Resource agent (the filling module, blue), Transport agent (the shuttle, blue); each with a dashed arrow to the asset it stands for |
| `message 01` to `07` | Call for proposals (product → resource), Proposal, Accept, Move me to Filling (product → transport), Arrived, Done (resource → product), Move me on |
| `command 01` to `05` | The resource agent's OPC UA commands: Occupy, Reset, Start, the skill's Start, Release |
| The rest | As on page 05 (module, shuttle, carriage, highlights, liquid, weight) |

Beats: messages 01, 02, 03 (each replaces the one before); message 04 and the shuttle flies in; message
05; then the commands and the module's run as in beats 3 to 11 of
[animations.md](animations.md#filling-motion) (here without the refused Start: the agent occupies
first); message 06; command 05 (Release); message 07 and the shuttle with the liquid flies out.

### 07 Product, process and resource AAS

*"Three AASs refer to each other: the product's recipe, the process's bindings, the resource's skills."*

| Layer | What | Animation |
| --- | --- | --- |
| `Product AAS`, `Process AAS`, `Resource AAS` | Each a group: the shell with its picture, and a group of its submodels | One per click |
| `link: recipe steps` | Production Sequence → Step Bindings | Wipe from the left |
| `link: each step bound to a skill` | Step Bindings → Skills | Wipe from the left |
| `link: required matches offered` | Required Capabilities ⇢ Offered Capabilities (dashed) | Wipe from the left |
| `link: offered realized by a skill` | Offered Capabilities → Skills | Wipe from the bottom |

The submodels are the real ones, named plainly: Bill of Material is Hierarchical Structures, Required and
Offered Capabilities are each AAS's Capability Description, Asset Interfaces are the interface
description and its mapping.

### 08 Equipment and skill hierarchies in the AAS (copied)

*"The AASs nest: the line names its modules, a module its components; a module's skill runs theirs."*
The figure of `docs/figures/skill-hierarchies.drawio`, AAS icons changed to shells. One group per AAS
panel ("Panel FillingModuleAAS module", …). It dates from ARSO 0.9: Operational Data is renamed
Variables here; the module's tree still shows a Control Configuration, which since 27 Oct is kept
outside the AAS (hide the row or leave it).

### 09 Primitive and composite skills in the AAS

*"A primitive is one command on one component; a composite is steps that run primitives."*

| Layer | What | Animation |
| --- | --- | --- |
| `module AAS: a composite skill` | The module's shell; Skills · Dispensing with its Start, its result and its four steps (a group per step) | Shown |
| `component AASs: primitive skills` | Three component shells with their primitives (Home, MoveAxis; Dispense; Tare, Weigh) | Fade |
| `runs 1` to `runs 4` | A green arrow from each step to the primitive it runs | One per click, Wipe from the left |

### 10 From the AAS to function blocks: modsync

*"modsync turns a skill in the AAS into function blocks, while the module runs."* Left the
FillingModuleAAS panel of page 08, in the middle modsync's six stages, right the subapplication
Dispensing as FORTE has it, drawn like "What the rules draw" (`docs/figures/skill-blocks.drawio`):
blocks with their event pins (green) and data pins (grey), the type in the block's neck.

| Layer | What |
| --- | --- |
| `AAS: FillingModuleAAS (from the hierarchy page)` | The panel as one group |
| `legend` | The four kinds of line |
| `FORTE: the subapplication Dispensing` | The outer frame |
| `created 1 · the skill: Control, Execute` | Control (`SKILL_Core`), the frame of Execute with its interface, the rules' wiring between them |
| `created 2 · the Start Operation: UaStart, the latch Volume` | UaStart (`SERVER_2_2`), the latch with the limits 0.5 and 10.0 as values, their wiring to Control |
| `created 3.1` to `3.4` | One step each: its instance (`SK_MoveAxis`, `SK_Dispense`, `SK_Home`, `SK_Weigh`), the green order chain into it, its binding (40.0; Volume from the latch; 1.0), the rules' INIT, HALT, ABORT, RESET |
| `created 4 · drawn by the rules` | The three `SKILL_FailMerge` blocks, failures and error codes merged pairwise (faded) |
| `created 5 · the result` | `PubResults` and Weigh's Weight published |
| `arrow 1` to `arrow 6` | A gold arrow from a row of the AAS panel (Dispensing, Start, Step_0000 to Step_0003), under modsync, to what it creates, and a ring on the row |
| `modsync` | The six stages, on top: the arrows run under it, so the entries go *through* modsync |

The lines: thick green an event connection the AAS gives (the order of the steps), thick grey a data
connection the AAS gives (a binding), light green and light grey what the rules draw.

Beats: start with the AAS panel, modsync, the legend and the empty outer frame (hide the `created`
layers at first). Then `arrow 1` wipes in, `created 1` fades in, the arrow disappears; the same for
`arrow 2` with `created 2`, and `arrow 3` to `6` with `created 3.1` to `3.4`. Last `created 4` (the rules
fill in the failures) and `created 5`. The point to make: the AAS gives the steps, their order and their
bindings; everything faint is drawn by the module rules, so it needs nothing in the AAS.

### 11 The mapping rules

*"Fixed rules map every element of the AAS to the program, and back."* `rules` holds the two column
heads; `rule 1` to `rule 8` one row each (AAS on the left, IEC 61499 on the right), for one per click;
`keys and limits` the two notes: names are the keys, and what changes online versus by a restart.

### 03b The production system, layer by layer

The illustrated layers of `docs/figures/module-tools.drawio` ("Layers (illustrated)"), without its title,
side boxes and legend: one layer per plane (the line, digital assets, behaviour, AAS models and
orchestration, HMI and planning), each plane one group. Beats: the line, then one plane per click, from
the bottom up.

### 03c The production system in layers (on the slide)

The page "Layers (illustrated)" of `docs/figures/module-tools.drawio` with less in it: its planes, its
isometric things and its lines, without the detailed panels (the function block network, PackML, the
skill's state machine, the AAS tree, product and process AAS, agents), the schedule and HMI panels, the
stacks of documents and the people. On the AAS plane three AAS shells as isometric solids (`iso_shell`
in `drawlib.py`: the logo's outline extruded, on the figure's 30° axes, the name on the band), standing
where the stacks stood; the AAS server's, the skill editor's and the planner's lines end on their tops
(to Product, Resource, Process). One draw.io layer per plane; each line is in the layer of its upper end.

### 03d The production system: a layered architecture (flat; on the slide in place of 03c)

The systems we have as a flat diagram in four bands, as the automation pyramid has them: applications
(MES / MOM: the AAS web UI with the process planner and the skill editor, the HMI, the orders; MES and
ERP later), the line level (CPPS: registration service, AAS server, MQTT broker, DMP, modsync, the line
agents, the XMPP server, InfluxDB), the module level (CPPM: the filling and stoppering modules on their
Pis, capping and inspection planned, the planar controller, the Kuka robots without an AAS yet) and the
device level (CPS: each module's parts, the planar table, the robots). A colour per protocol (the
legend): HTTP for the AAS API, OPC UA, FORTE's management protocol, XMPP, MQTT, discovery, IO, time
series. Between the line and the modules OPC UA, management and discovery run as buses that each module
drops onto. Dashed is planned. One draw.io layer per band (`device level`, `module level`, `protocols`,
`line level`, `applications`) and the legend; each connection is in the layer of its upper end, so on
the slide every band appears with its lines, bottom up. `architecture.pptx` holds the slide alone.

### 12b, 12c Inside the agent of a module, of a product (planned)

After the I4.0 language demonstrator: the agent as the active part of an AAS, the AAS on the server as
its passive part. A SPADE agent: a messenger (XMPP, VDI/VDE 2193), an interaction manager with the role's state machine
(service provider; service requester), then the agent's functions: for a module bidding, reconfiguration
(the planner composes, modsync builds) and execution (modlink over OPC UA, or over HTTP as an Operation of
the AAS that the DMP turns into the OPC UA call); for a product requesting, recording and moving. Layers:
the passive part first, then the agent, then each function with its links.

### 10 From the AAS to function blocks: the console

Right of the subapplication, a console: what modsync sends, one layer per step (`commands 1` to
`commands 9`): the operations of `iec61499_mgmt`'s `Command` (create_fb, connect, write, start; and to
verify query_fbs, query_connections, query_type, read), the AAS read (GET) and the record (PUT). Show one
step's layer at a time, with that step's arrow and blocks.

### 12 Matching, a missing effect, replanning

The prefilled syringe's recipe (Fill 1.0 mL from the bottom, Stopper, Inspect) against what the modules
offer, the paper's changeover. Layers: `match` (the dashed lines, Stopper and Inspect offered), `missing`
(Dispensing doses with the needle still; a tall barrel needs the needle to rise as the liquid does, and no
parameter gives that), `replan` (BottomUpFilling: NeedleDeep, then Dispense and NeedleRise at the same
time, a parallel block, then Home and Weigh), `check` (matched again: the needle stays in the container
while it rises). One click each.

### 13 Agents on the line: modules and shuttles bid (built 30 Oct, simulated)

One step at a time: the vial's product agent (P) calls for proposals for its next step, Fill 2.0 mL; only
Filling proposes (with its station), the other modules refuse; its proposal holds Filling. Then the
transport: every shuttle has a resource agent (R) like a module; the vial's shuttle is asked to carry it to
Filling's station, proposes MoveToPosition, is accepted and reports it there (the vial moves); only then
the product agent accepts Filling's proposal, the way into page 06. Each message has a `card` layer (it
stays) and an `arrows` layer (it goes with the next message); "arrived" has no arrows. As the code does
(`line-agents`, `test_transport.py`): the first time every free shuttle is asked, and the one chosen
carries the vial to the end. `agents-and-shuttles.pptx` holds this slide and page 12c. The deck now uses
page 13b in its place; this page stays as the later steps' picture (only the vial's own shuttle asked).

### 13b Agents on the line: every agent is asked (built 30 Oct, simulated)

Page 13's line, agents and vial, as the product agent does it since custody (vocabulary 0.7): every
call goes to every resource agent, the four modules and the five shuttles, and the constraints in each
resource's AAS decide who proposes. Ten messages: Fill 2.0 mL (only Filling proposes, the others
refuse with ✗; Filling is held); Receiving, since nobody holds the vial (the five empty shuttles
propose, room for one; the modules refuse); shuttle 3 accepted and holding the vial, the others
rejected (grey dashed arrows); Transporting to Filling's station (only shuttle 3, Holding = true,
proposes; the other eight refuse); accepted; arrived (the vial moves); Filling's proposal accepted.
The cards are smaller than page 13's (ten of them); a module's ✗ is on its left, clear of the held
mark. The refusals belong to the `arrows` layer, so they go with the next message. In the deck as the
slide "Agents on the line: every agent is asked"; `agents-every-agent-asked.pptx` holds it between
page 12c and the agents at the filling module.

### Backup pages (copied)

- **From recipe to process** (`skill-hierarchies.drawio`): the planner joins the product's recipe, the
  line and the modules' skills into the process AAS. A group per panel.
- **A skill in the AAS and the blocks it is** (`mapping.drawio`): the Skills submodel next to the
  subapplication it is, element by element, and the OPC UA nodes. The detailed version of pages 10
  and 11.

## The animated deck

`modular-production-animated-v4.pptx` is the user's `modular-production.pptx` with these figures added as
animated slides in its own style (title, section label, speaker notes). Only the two walks through the
filling module (with an orchestrator, with its agent) and "From the AAS to function blocks" keep the click
timeline with a caption per step; the user's own slides lose theirs (`strip_timeline`: the shapes below
the figure, their effects and the clicks left empty go; the rest is scaled and centred). Slides 13 and 14
of the original become page 12, slides 15 and 16 pages 12b, 12c and 13, followed by the agents at the filling module. Slide 6's illustration is page 03c.
The line and the tools pictures (slides 1, 3 and 11) are new exports of `docs/figures/slides.drawio`, in
`figures/pictures`. Each figure is its layer PNGs, cropped and stacked; the animations are PowerPoint's
own (fade, wipe, fly in, motion paths), so they can be changed in the Animation Pane.

`python docs/presentation/source/build_pptx.py . <out.pptx>` builds it from `modular-production.pptx` and
the exports in `figures/deck` (`slides_spec.py` says what each new slide shows and how it animates, and
what changes on the user's slides; the skill's `add_slide.py`, `clean.py` and `validate.py` do the package
work). `export_slides.vbs` renders every slide with PowerPoint and `video_slide.vbs` one slide as a video,
to check an animation frame by frame. A motion path in PowerPoint starts from where the shape is laid out,
not where the last path ended: a way back is the path from the moved place to 0. A wipe's filter names
the side it starts from, as its subtype does (From Left: 8 and `wipe(left)`; From Bottom: 4 and
`wipe(down)`); another pair shows one direction in the Animation Pane and plays the other.

## Facts to keep

- Agents do not exist yet: page 06 is planned (dashed), the paper's future work.
- The filling and stoppering modules are built; capping and inspection are planned. The filling
  module's pump is not wired (dispensing is a time at a flow rate) and its scale is simulated.
- No durations, counts or measured values in an animation: they illustrate the order of things.
- Online: a value, a new composite skill. Not online: a new primitive or IO (a FORTE build), removing or
  reordering what runs (a restart).

`replanning-and-agents.pptx` holds the replanning slide of 29 Oct (TaredDispensing) and the
agents-on-the-line slide; `reconfiguration-syringe.pptx` the replanning slide as it is now (the syringe):
`keep_slides.py <deck> <out> "<title text>" ...` keeps the slides whose titles contain the texts.
