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

## 29 Oct 2026

- **In an isometric figure the AAS shell is an isometric solid.** *Journal* (figures).
  - What: the shell's outline, with the logo's rounded corners, extruded and drawn on the figure's own
    30° axes, shaded like the stations, its name on the band; it stands on the AAS plane, and the lines
    from the tools end on its top.
  - Why: a flat logo in an isometric drawing reads as pasted on; the solid belongs to the scene.
  - Instead of: the flat shell, kept for flat diagrams.

- **An agent is drawn as the active part of an AAS, in our parts.** *Journal* (agents, future work).
  - What: a module's agent is a SPADE agent; its messenger is XMPP, carrying VDI/VDE 2193 messages; an interaction manager with the
    service provider's state machine, bidding (capability, availability, time), reconfiguration (the
    planner composes, modsync builds online) and execution (modlink over OPC UA, or an Operation of the
    AAS over HTTP that the DMP turns into the OPC UA call); its passive part is the module's AAS. A
    product agent is the same build as the service requester, writing the process AAS.
  - Why: it places the tools that exist (planner, modsync, modlink, DMP) inside the agent, so the
    agents are a role around them, not a new system.
  - Instead of: agents as one box beside the tools.

- **The talk shows modsync as the commands it sends, and agents in the I4.0 language.** *Journal*
  (how the method is shown to people who did not build it).
  - What: the slide from the AAS to function blocks has a console beside the network: per step the
    operations of the management API that build it (create_fb, connect, write, start) and, last, those
    that verify it (query_fbs, query_connections, query_type, read) before the skill is recorded as
    Built. The agents are shown on the line, the vial's product agent calling for proposals and the
    modules' agents proposing or refusing, as VDI/VDE 2193 messages; replanning is one slide: match,
    the missing effect (12 mL), a composite from the module's primitives, matched again.
  - Why: the network alone shows the result, not that it is built step by step online and read back;
    the commands are the method's evidence. Interaction protocols make the agents' part concrete
    without claiming more than is planned.
  - Instead of: a pipeline of six boxes for modsync; agents as boxes beside a picture; two slides
    for the change from recipe to running program.

- **The DMP rides out a module that restarts: two more changes on its `lab-modules` branch.**
  *Journal* (what an AAS-driven connection needs from its runtime when modules come and go).
  - What: a route's OPC UA subscription is deleted without waiting for the server's answer, and a
    method call or a signature read that finds the shared connection reconnecting waits for it (a
    call a third of its timeout, a read 10 s) instead of failing; a read that meets a stale session
    is made once more.
  - Why: a module that restarts (FORTE, a Pi rebooting) is normal on a reconfigurable line. Before,
    the first call after a restart failed for about 13 s (`Device transport failed`, HTTP 424 at the
    AAS server), and removing the routes of a module that had gone away waited out a request timeout
    per consumer: the DMP took 71 to 213 s to converge after a republish, 47 s with the delete sent
    and not waited for. A server that is gone drops the subscription with its session anyway.
  - Instead of: retrying the call itself (a method is not idempotent: Dispensing must not start
    twice), so only what has not been sent waits, and only the read is made again.
  - Checked: the DMP's OPC UA tests (37), and `test_dmp_live.py` three runs in a row against the
    same DMP, where the second run had failed before. Left as found: a mapping blocked on a submodel
    published after its AIMC is not resolved when the submodel arrives (publishing order avoids it).

- **The planner's bindings make the process AAS: the registration service writes it after a save.**
  *Journal, CIRP* (ISA-88's master recipe, apart from the general recipe).
  - What: `POST /process/<product>` (`modreg/process.py`) reads the product's recipe as the planner
    saved it, with a module, a skill and input bindings per step, finds the line that holds every
    bound module (its Hierarchical Structures), and writes the process AAS: Process Information,
    a step binding per bound step (the recipe's step, the module, the skill, each input's source or
    constant and the Operation variable it is handed to), and the plan check's result as its
    Validation. The planner asks for it after saving a recipe with a bound step. The plan check
    moved into `modreg` (`modreg.plancheck`) for it.
  - Why the service and not the planner: the process AAS is built with aas-model's classes and
    checked by the same plan check as the reference processes, so the hand-written ones and the
    planner's are one structure; the planner has no notion of a line, and the service finds it.
    Instead of: the planner writing the process AAS's JSON itself (a second copy of the structure in
    TypeScript), or asking the engineer for the line.
  - First step: the bindings stay in the product's recipe as well, since the planner and the HMI
    read them there. Taking them out is the next step, once every reader reads the process AAS.

- **The skill editor asks the checker and the planner.** *Journal* (the engineer's side of planning).
  - What: in the skill editor, Check sends the skill as it is on screen (not saved) to `modreg
    serve`'s `/check` and shows each finding at its step, with the skills that would fix it; a
    changed flow clears the result. In the skills overview, Plan a skill takes a capability the
    module offers, its range properties as the values and what it should report as results, shows
    the planner's steps, and on "Plan and describe" has the skill described on the AAS server and
    opens it in the editor; `modsync reconfigure` builds it.
  - Why the check before saving: a finding is cheapest while the flow is being drawn; saving
    first would put a skill on the server the module cannot run. Instead of: checking on save only.
  - The values come from the Capability Description the editor already reads (its ranges), so the
    dialog asks for no names: what a module can be planned for is what it offers.

- **Every call of a module's command is logged, as a time series in `Variables/Log`.** *Journal.*
  - What: per command an Operation invokes (`Dispensing_Start`, `Occupy`, ...), a series
    `Log/<action>` (aas-model's `operation_log`): how the call ended (`Outcome`), how long it took
    (`DurationMs`), and the Operation itself, referenced, so its variables are fields (the session,
    the parameters, Accepted and ErrorID). The DMP writes the row from the bridge mapping's response
    half, also for a call that failed (then the log row only).
  - Why: who called which skill with what, and what the module answered, was in no record; the
    module's own state series show what it did, not who asked. With the session in the row, a
    module's history can be read per client (an agent, the HMI, the planner).
  - A reference, not copies of the variables: the record follows the Operation when its parameters
    change, as aas-model's stations do. Instead of: one log per skill with a command field (a
    record refers to one Operation), or a log in FORTE (it has no clock or storage to keep it in).

## 28 Oct 2026

- **The lab's AAS stack runs the DMP beside BaSyx, with InfluxDB behind the Variables and MQTT
  for BaSyx's submodel events.** *Journal* (the architecture: an AAS that is the configuration of
  its own connection). Asked for by the user.
  - What: `deploy/aas/compose.yaml` (`python deploy/aas.py up`): the BaSyx AAS environment with
    operation delegation and its MQTT feature, registries, discovery, the web UI, Mosquitto,
    InfluxDB 2 (org and bucket `ap2030`, as aas-model's segments name them) and the DMP built from
    the `aas-camel-dmp` submodule, named `dmp` because the delegation URLs name `http://dmp:8080`.
  - Why MQTT for the events, not Kafka: the DMP takes either; Mosquitto is one small container and
    the lab's stations speak MQTT already. Kafka needs a broker and its coordination for one
    consumer. The modules' values do not go through the broker: the DMP observes them over OPC UA
    and writes them to InfluxDB.
  - The secrets (InfluxDB's password and token) are made up on the first `up` and kept in
    `deploy/aas/.env`, which is not committed: the repository is public.
  - The DMP did not run our modules out of the box. Four changes, on a branch of the DMP fork
    (`lab-modules`), each with a test:
    - it refused aas-model's AIDs: since 24 Oct aas-model has every interface select its `nosec_sc`
      (AID 1.1 requires a selection), and the DMP (23 Oct) refused any selection, since it holds no
      credentials. A `nosec` scheme needs none: a selection of `nosec` schemes only is accepted now.
      Instead of: leaving the selection out of our AID (no longer AID, and aas-model adds it back);
    - it bound an Operation to the action named like the Operation's parent (aas-model's
      `Skills/<skill>/operation` and action `<skill>`). ARSO has `Skills/<skill>/<command>/<command>`
      and an action per command of every skill (`Dispensing_Start`), which cannot all be named
      `Start`. Now, where the names differ, the one action all the mapping's Sinks address: the
      AIMC states the binding. Instead of: changing ARSO's skill structure for a naming rule;
    - it could not call a method whose owning object is named by a browse path (it read the
      signature only with a NodeId owner, and resolved a missing one at the call). FORTE numbers its
      nodes anew at every start, so we name them by browse path; aas-model's stations have fixed
      NodeIds, so this had not come up;
    - it connected to the host a server names in its endpoints (FORTE: the computer's hostname,
      `MartinPC`, the Pi's name), which does not resolve in the DMP's container. It now reaches a
      server at the AID's base (Camel Milo's `overrideHost`), as the AID says.
  - Found, not changed (the first is fixed on 29 Oct, see there): removing or replacing a route
    whose OPC UA server has gone away waits out a shutdown timeout per route, and leaves the mapping
    stale and the DMP degraded until it is restarted; and a mapping whose referenced submodel is published after the AIMC stays blocked
    (not resolved when the submodel arrives). So the components' AASs are published before the
    module's (`modreg.service.mapped_last`), and within an AAS its AIMC after its other submodels
    (`AasServer.publish`); a module keeps its OPC UA address across restarts.
  - Checked end to end (`cell/tests/test_dmp_live.py`): the filling module simulated on FORTE;
    Occupy, Reset, Start and Dispensing invoked at the AAS environment, answered by the module
    through the DMP (and a refusal for another session), and the rows of the module's state and of
    the Dispensing run, with its volume and weight, in InfluxDB. And a shuttle of the planar table
    (the planar controller, a Python OPC UA server, which names a method's arguments by meaning:
    the describer says how a server names them): the table to Execute, the shuttle occupied and
    moved, its run, its pose and the call log in InfluxDB.

- **A module's AAS is what the DMP (aas-camel-dmp) runs: a skill's Operation calls the module's
  OPC UA method through it, and its values reach InfluxDB through it.** *Journal.* Asked for by
  the user.
  - What changed in the generated AAS:
    - each Operation's delegation URL is filled in: the DMP's origin and the path where the AAS API
      invokes that Operation (`/submodels/{base64url(id)}/submodel-elements/{idShortPath}/invoke`),
      as aas-model now writes it. Before, the `{operation_path}` placeholder was left in it;
    - an action's arguments are named as FORTE names them: `RD_1, RD_2, …` in, `SD_1, SD_2` out.
      FORTE's OPC UA server names a method's arguments after the data ports of the SERVER block
      that serves it, and the DMP calls a method with its arguments by name. What each argument is
      (Session, Volume; Accepted, ErrorID) is its title;
    - a mapping that invokes an action writes into the action's `input`, and has a response half:
      the method's answer (`SD_1, SD_2`) becomes the Operation's Accepted and ErrorID. A skill's
      results are marked Optional (aas-model's qualifier): the method answers at once, the results
      come when the skill is done, and the DMP requires every output not marked so;
    - a Boolean (the occupation) goes into its decimal field as 0 or 1: the DMP writes a field as
      its type and refuses a Boolean for a float;
    - aas_pydantic's `temp_id_short_attribute_*` Properties (it keeps a list item's idShort in them
      to read the model back) are stripped before publishing, as aas-model does. The DMP refuses a
      mapping with elements it does not know, and every mapping had them.
  - Why the AID names FORTE's argument names: the AID describes the device as it is, and the DMP
    checks it against the server. Instead of: renaming FORTE's arguments (its server takes them
    from the block's port names) or a mapping by position (the DMP matches by name on purpose,
    so that a reordered method cannot be called with the wrong values).
  - Nothing else needed: the DMP already resolves browse paths (`uav_browsePath`, and
    `uav_componentOf` as one), which FORTE's changing numeric node ids require.

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
