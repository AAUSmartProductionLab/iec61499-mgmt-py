# Design log

A running log of design considerations made while building, for writing the papers afterwards.

**What each entry holds:**
- what was chosen;
- why;
- what it was chosen instead of;
- which paper it serves: *CIRP* ([paper-outline.md](paper-outline.md)), *Journal*
  ([journal-paper.md](journal-paper.md)), or both.

**Rules:**
- Newest entries first, dated.
- Add an entry whenever code or a design changes for a reason a reader of the paper would want to
  know.
- What was decided, without the reasons, still goes into [decisions.md](decisions.md). The method's
  settled decisions are in [design-decisions.md](design-decisions.md).

## 28 Oct 2026

- **Every block of a generated program explains itself in plain words, in 4diac and in the docs.**
  *Journal.* Asked for by the user.
  - What: the generator (`modgen/explain.py`) writes a type comment on every type ("what it does,
    for whom", then "Technical:" the detail) and an instance comment on every block of the
    application and of every composite: where its calls come from and where its data goes (a
    parameter "from Dispensing's Volume", a result "is Dispensing's result"). The same is written
    out once by hand in [filling-program.md](filling-program.md), with each OPC UA call followed to
    the pins, and [building-skills.md](building-skills.md) says how to add a skill, a primitive or
    equipment.
  - Why: an engineer opening the program in the 4diac IDE sees dozens of blocks and their wires; without
    the comments it takes reading the generator to know what a channel carries or why a block is
    there. Written by the generator, the comments follow every regeneration and never go stale.
  - Comments are not part of a type's hash (checked with the 4diac IDE 3.3 export), so they need
    no FORTE rebuild and a running module keeps matching its program.
  - Instead of: a separate manual only (goes stale and is not where the engineer looks), or
    comments written in the IDE by hand (lost on the next `modgen`).
  - The guide states the rule the architecture gives: a module level skill is blocks of types FORTE
    has and is added while the module runs; a primitive or equipment is new types and needs a new
    FORTE. That is the split between reconfiguring a module and changing it.

- **A module keeps no live value in its AAS: its values are time series in the database, and the
  AAS says where.** *Journal.* Decided by the user.
  - Why: the values change fast (a position while the axis moves, a weight while it fills). Pushing
    each change into the AAS server loads it with writes nobody reads there, and keeps no history.
    A time series database keeps every row; a reader asks it for the latest or for a span.
  - The Variables of a module hold aas-model's time series SMCs (IDTA 02008 as SMCs): `State/Module`
    (PackML state, occupation), `State/<Skill>` (one skill's run: its state, error, parameters and
    results and its steps'), `State/Procedures`, `Measurements/<Item>` (an item of equipment's
    inputs). A series groups what changes together, as aas-model asks, not one value each. Each field
    is a decimal with its meaning as supplemental id; each series has a segment naming its InfluxDB
    measurement (`state_dispensing`, `measurements_linearaxis`), tagged with the module's AAS.
  - Instead of: a Property per value that the mapping keeps current (45 for the filling module), and
    instead of aas-model's stations' both (a Property and a series).
  - One mapping per series writes a row: each interface property is the field its SourceId names.
    modlink finds what a skill's state shows through that (the field's meaning); a capability's
    `SameAs` and a coordinate's `ZSource` refer to a record field. `Log` (the calls of skills) is
    not written yet.
- **A shuttle is its xbot: no AAS of the xbot apart from the shuttle's.** *Journal.* The shuttle's
  `MoveToPosition` is its own skill. Until now the xbot was a component (`PlanarShuttle<N>XbotAAS`)
  because it is the shuttle spec's equipment that the skill moves; but there is no part to tell
  apart from the shuttle. Decided by the user. The table's PMC was never a component (no skills).
- **Three products and their process AASs, written out in Python.** *Journal.*
  - A 2 mL vial, a prefilled syringe of 1 mL and a cartridge of 3 mL (`cell/examples/products`),
    with the values of the planner's pharma example. One process AAS each on the filling line
    (`cell/examples/processes`).
  - **Long files, every element constructed with its class,** instead of helpers that build
    elements. They are the reference a reader looks up ("this is how this part looks"), so nothing
    is hidden. Decided by the user.
  - **The recipe names no equipment; the process AAS holds the bindings** (the model of 26 Oct,
    `ppr-model.md`). The planner still writes bindings into the product's recipe (F6); `plan_check`
    reads both (`check_process`, `check`).
  - **The plan check guards the reference:** a process AAS whose Validation says something else than
    the check finds is refused by `example_line.py`.
  - **The syringe accepts a fill error of 0.05 mL,** where the planner's example asks 0.01 mL: the
    line's filling module fills to 0.05 mL. A product asks for its fill error as a range (0 to the
    most it accepts); the check now compares an offered value against a required range.
- **A capability property may list the values a module takes** (IDTA 02020's `SubmodelElementList`
  property). *Journal.*
  - Filling, stoppering and inspection take vials, syringes and cartridges (`ContainerType`); capping
    takes vials. The spec says `values: [vial, syringe, cartridge]`.
  - Why: one capability with the set of containers it takes, instead of one capability per container
    as the planner's example has it (Filling_vial, Filling_syringe, ...), which multiplies offers and
    skills that are the same.
  - Read by the plan check, modlink and `modreg offer`. The planner's matching is not checked yet.
- **The table's three shuttles are part of the example line**, so the line's resources are complete.
  Loading and unloading are still named only (each a Kuka robot and a Pi; no spec yet).
- **The reference models: the library in aas-model, the instances here.** *Journal.*
  - aas-model (branch `lab-ppr-models`) holds the lab's own submodel templates (ARSO's Skills,
    Parameters, Control Configuration; the product's Process Parameters and Production Sequence; the
    process AAS's Process Information, Bindings, Validation), the classes generated from them
    (`scripts/lab_generate.py`), and the types `Module`, `Component`, `ProductionSystem`, `Product`,
    `Process`.
  - This repository builds the instances with them: the modules from their specs (`modreg`), the
    products and the processes as Python.
  - Why: the module spec stays the one source of a module's program and its AAS (a module's AAS is
    4 to 7 MB, about 1,200 interface and 600 mapping elements, all derived). The types and
    templates are shared with the lab's stations. Instead of: the instances in aas-model as well,
    which would duplicate the specs.
  - modreg's own generated classes and templates are gone; `modreg generate` writes the ARSO
    templates into aas-model and has it make the classes.
- **aas-model's Variables replace ARSO's Operational Data.** *Journal.*
  - Variables has the shape decided for the operational data: live values as Properties, and
    `State`, `Measurements` and `Log` holding time series (IDTA 02008 as SMCs, an InfluxDB segment
    each). One model for the lab's stations and the modules.
  - A data point is a `VariableProp`: the semantic id says it is a variable, its meaning (what it
    shows) is its supplemental id. modlink reads the meaning there, and still the semantic id of
    the older AASs.
  - The coordinates are in `Variables/Measurements/Coordinates`, with their own semantic ids
    (`.../variables/Coordinate/1/0`). Their classes have names of their own (`RelativeCoordinate`,
    `CoordinateX`): aas_pydantic reads an element back as the class its dump names, among all
    classes, and aas-model already has a `Coordinate`.
  - ARSO follows (0.14).
- **The skill protocol's variables keep their id.** *Journal.* Session, Accepted and ErrorID carry
  `.../ControlComponent/Skill/OperationVariable/1/0`, stated where it holds. aas-model used to give
  it to every Operation variable; its variables are plain Properties now. The planner, the skill
  editor and the projection tell protocol from parameter by it.
- **The process AAS's templates are written by hand, not from an ontology.** *Journal.* AProSO is
  not remade yet. The templates follow the draft of 26 Oct (`process_aas.py`). Their classes are
  named apart from the skills' and the recipe's (`ProcessStepBinding`, `InputBinding`), which have
  the same idShorts but other fields.
- **Coordinates built (ARSO 0.13, vocabulary 0.5).** *Journal.*
  - What exists: modules (base, a mount and an end effector per axis, points), the table (base and
    flyways), the shuttles (the xbot, following the controller's X, Y, Rz) and the line's points.
    The example line places each module's base on the table, as a module will report it.
  - **A moving part is a fixed mount plus the moving coordinate.** Then every moving value is a plain
    data point (the end effector's Z is the axis' actual position), not an offset plus a signal, and
    a time-series record of it is just that value.
  - **The source of a moving value is a reference to the existing data point,** not a second
    mapping in AIMC. A client needs nothing new to follow it.
  - **No `History` segment yet:** it would be an empty container until the database exists.
  - **Operational Data may now hold no data points:** the line's has only its points. The rule
    requiring one was dropped.
  - **A module described from its spec alone is not placed:** its base is the root of its own small
    tree until `place` puts it on the table.
  - **Products are not done.** A product's coordinate (relative to the xbot, or a fixture on it) is
    instance data that changes at each handover. The product AAS (APSO) has no Operational Data
    yet; it comes with the product instances.
- **Coordinates: settled with the user.** *Journal.*
  - **One measurement series per coordinate,** in Operational Data's `Measurements`. It is shaped
    like every series of the plan of 26 Oct ([state-and-parameters.md](state-and-parameters.md),
    section 3): records in a time-series database, a `Latest` in the AAS. Positions will be
    reported by the modules themselves (RFID), so even fixed ones are measured.
  - **The parent is part of the record.** A record holds the time, the coordinate it is relative
    to, and x, y, z, roll, pitch, yaw.
    - A product on a shuttle: the xbot's series gets a record per move (the controller); the
      fixture is fixed relative to the xbot; the product's series gets a record only when it is put
      somewhere else, with the new parent and offset.
    - Where the product was at time t is composed from these. It is never stored.
  - **Rotation:** R = Rz(yaw)·Ry(pitch)·Rx(roll), about the parent's fixed axes (ROS's RPY;
    `modreg/frames.py` already composes so). Units mm and degrees.
  - **Granularity:** a module may hold several coordinates. Ours hold two: the module base, and the
    sled or end effector relative to it. No coordinate per component.
  - **Root:** the table.
- **Proposed (the user's whiteboard): coordinates as a transform tree in the operational data,
  instead of frames on Hierarchical Structures nodes.** *Journal.* Under evaluation, not built.
  - **Structure:**
    - a `Measurements` collection holding `Coordinates`;
    - each coordinate holds a reference to the coordinate it is relative to, and x, y, z, roll,
      pitch, yaw;
    - the semantic id says *Coordinate*; a supplemental id gives its meaning (end effector, top of
      vial).
  - **Why better than frames on nodes:**
    - The parent is a reference, not the part-of tree, so a product can sit on a fixture on a
      shuttle without being part of it, and be re-parented as it moves.
    - Coordinates that move (the needle, a shuttle) live with the other live data.
    - IDTA 02011 is no longer extended.
  - **Pitfalls to settle:**
    - Live values are not streamed into the AAS: a moving coordinate names the signal it follows,
      as data points do through the mapping.
    - A moving coordinate should change only in its joint: a fixed mount, then the moving part
      relative to it.
    - The rotation order and the units must be stated (roll, pitch, yaw about fixed axes,
      Rz·Ry·Rx, as ROS and `modreg/frames.py` already take it).
    - Each coordinate lives in the AAS of the asset it belongs to; references across AASs must
      resolve.
    - The tree must have one root (the table) and no cycles: a check.
    - Fixed poses under "Measurements" mislabel configuration as measurement.
    - "Variables" (aas-model) or Operational Data (ours) must be chosen.

- **No building, no hall, no IDTA 02045: the line is the root of all locations.** *Journal.*
  Decided by the user, overriding the entry below: the site level is not needed.
- **The frame on a Hierarchical Structures node extends IDTA 02011.** *Journal.*
  - What it adds: a statement the template does not define.
  - Why it is acceptable: 02011 (1.1, section 1.6) is meant to be "extended upon … specified
    further". The frame sits beside the template's elements and changes none, and its six properties
    carry IDTA 02075's ids. A reader of the bill of material is not affected.
  - The difference from extending 02045: there, a missing concept (orientation) would have been
    pushed into elements that mean something else (time-stamped records). Here a new, separately
    identified element is added. Both are extensions; this one is milder.
  - Open: the six properties straight on the node, without the `Frame` collection (fewer wrappers);
    or the placement in the part's own AAS, if IDTA 02075 has a submodel for it.
- **Locations: IDTA 02045 Asset Location for the site, frames for the line.** *Journal.* (Superseded
  above.)
  - 02045 holds the site and hall level: the address, the hall's coordinate system (local, with
    ground control points to WGS84), the hall as an area, and time-stamped records of where an asset
    was.
  - The line's geometry stays as frames on Hierarchical Structures nodes (AutomationML Frame, IDTA
    02075 ids): a module in the line, a component and its transfer points in the module.
  - The two meet at one place: the line's origin is a location record in the hall's coordinate
    system.
  - Why not 02045 alone: it has no orientation (it says so: no 6DoF "for now"), no frames relative
    to a parent, and positions only as event records with a time, not as a static pose.
  - Why not extend 02045: an extended template no longer conforms to the standard, and its readers
    would not understand the additions; frames on 02011 nodes are already standard elements.
  - A use for 02045 that fits it exactly: each station as a fence (an area in the line's coordinate
    system), and the product AAS recording entry and exit events as it passes. That is a location
    trace for the batch record.
  - Needs the lab's address and a measured origin of the hall; not built.
- **The CIRP paper's scope is narrowed to restructuring a module through its AAS.** *CIRP, Journal.*
  - Why: four contributions and three planners in six pages left each half-shown.
  - Instead of: models, planning, architecture and updating as equal contributions.
  - The capability model, the planner comparison, discovery, agents and locations move to the
    journal paper.
- **Effort is counted as user actions, as Dorofeev et al. (ETFA 2021) count them** (`cell/eval/effort.py`).
  *CIRP.*
  - Three ways of making the same skill: by hand in 4diac, in the skill editor, planned.
  - Why: the method is published and is the closest work's own measure, so the numbers compare.
  - Instead of: timing engineers (needs a study), or counting AAS elements (no counterpart in the IDE).
  - By hand counts every instance, subapplication, connection and value the rules build. The editor
    counts each element entered: 2 for a parameter or a step, 1 per field or binding. Planned counts
    the requirement.
  - First numbers: 131 to 151 by hand, 19 to 26 in the editor, 3 planned.
- **The argument for composites as instances rests on the standard, not on FORTE's limits.** *CIRP.*
  - FORTE can load basic and composite types online with its optional Lua loader, though never
    service interface blocks.
  - Why it still holds: creating instances and connections is what every IEC 61499 runtime does
    through management commands. Instances keep each step readable and monitorable.
  - Instead of: "FORTE cannot load types", which is not true.
- **Dorofeev et al. (ETFA 2021) generate one basic function block per composite, from a given
  sequence.** *CIRP.*
  - Their parallel steps grow as 2ⁿ states. Their future work is to keep the skill description in
    the AAS.
  - This is what our instance-only composites, join block and AAS-as-desired-state answer, and is
    why the paper cites them as the closest work.
- **The three planners' plans differ.** *Journal.*
  - GTPyhop follows the module's convention (home after every operation).
  - Aries returns by MoveAxis(0).
  - ENHSP adds a weighing of the empty vial.
  - Why it matters: it is the case for HTN methods carrying the integrator's way.
- **Scaling probe** (1 to 20 doses). *Journal.*
  - Aries grows from 0.08 s to 6.8 s on our HDDL encoding, whose value objects and sum facts grow
    with the doses.
  - GTPyhop and ENHSP stay flat.
  - To report as a property of the encoding, not of Aries alone.
