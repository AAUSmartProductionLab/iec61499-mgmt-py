# States, measurements, events and parameters in the resource AAS: a plan

Plan of 21 Oct 2026, not built. How a resource AAS (line, module, component) tracks what happens
to the resource over time, using the structure of IDTA's Time Series Data template inside a
submodel of our own; how states, measurements and events are told apart; and what goes into the
Parameters submodel instead. The database behind the history is left out on purpose: the model
only says where history is and how to ask for it.

## 1. Where we are

| Today | Problem |
| --- | --- |
| Operational Data holds 45 flat Properties per filling module, all `xs:decimal`, value `0` (`modreg/profile.py`): PackML state, occupation, every skill's and step's State and ErrorID, skill parameters, results, the axis' and scale's signals | No time and no history; no kind (a state, a sensor value, a parameter's value and a result look the same); state codes explained only in a description text; the values are never written (nothing runs the mapping) |
| ARSO's `operational-data.ttl` and `parameters.ttl` are placeholders ("still under development") | Nothing to check against |
| aas-model has `Variables` (live values, a Property each) and `Parameters` (key-value, a Property each), and the IDTA Time Series 1.1 classes (`aas_pydantic/submodel_templates/time_series.py`), unused | Our resources leave Variables out (19 Oct) and have no Parameters; Time Series not used anywhere |
| Fixed facts and settings of the hardware (screw lead, microsteps, 2.8 A, 12.5 mm/s, timeouts) are only in the module spec (YAML) | A module without its spec does not say how it is set up |

## 2. Four kinds of values, and two that are not over time

The first question about any value is *who changes it, and when*:

| Kind | Answers | Changed by | When | Over time | Example (filling module) | Where |
| --- | --- | --- | --- | --- | --- | --- |
| **Technical data** | What the asset is | Manufacturer | Never | Fixed | Screw lead 5 mm, motor rated 3 A, travel 160 mm | Technical Data |
| **Parameter** | How it is set up | Engineer, a reconfiguration | Rarely, deliberately | Current value; every change logged | Microsteps 4, current 2.8 A, speed 12.5 mm/s, home timeout 60 s, stop timeout 10 s | **Parameters** |
| **Skill parameter** | What a call asks for | The caller, per call; its default and limits by the engineer | Per call | Per call (in the execution event) | Dispensing.Volume, 0.5 to 10 mL, default 0.5 | Skills (as now) |
| **State** | What condition it is in | The controller | When it changes | Series, a record per change | PackML Execute; Dispensing Running; occupied by session X; Homed; ErrorID 3 | **Operational Data: States** |
| **Measurement** | What it observes of the process | The physical process | Continuously | Series, sampled or on a change larger than a deadband | Actual position (estimated), weight (simulated), limit switch | **Operational Data: Measurements** |
| **Event** | What happened | Something occurring | At an instant | Log, a record per occurrence | Dispensing succeeded at t (Volume 2, Weight 2.0, session X); module occupied; DoubleDose created | **Operational Data: Events** |

**States and measurements are variables**: they have a value at every instant, and their history
is a time series. **Events are not**: they happen; their history is a log. **Parameters** have a
value at every instant too, but nobody needs their value per millisecond: what matters is the
current value and when, by whom and why it changed. So they are not a series; their changes are
events.

Rules for the cases in between:

| Value | Kind | Why |
| --- | --- | --- |
| A sensor's Boolean (limit switch) | Measurement | Observed from the process, even though discrete |
| A flag the controller derives (Homed, Moving) | State | Held by the controller's logic, not measured |
| A position the controller estimates from time | Measurement, origin Estimated | Stands in for a sensor; says that it is not one |
| A simulated weight | Measurement, origin Simulated | Same; honest about what it is |
| ErrorID | State (with the skill's State: they change together); a fault is also an event | The condition and the occurrence |
| A skill's result (Weight) | A field of the execution event | Belongs to one run, and through the session to one product |
| A skill parameter's value as the skill holds it now (today `Dispensing_Parameter_Volume`) | Not operational data: it is the skill's default, in Skills; a change of it is an event | It is set, not observed |
| A step's constant (FlowRate 1.0) | Skills (as now) | Part of what the skill is |
| Counters (vials filled, hours run) | Measurement (a counter) | Observed, monotone |

## 3. Operational Data as states, measurements and events

**Proposal:** Operational Data (ARSO's, version 2) holds three collections, `States`,
`Measurements` and `Events`. Each entry is one series: an SMC with the inside of IDTA 02008 Time
Series Data 1.1 (`Metadata` with its `Record` template, `Segments`), a kind, and where its values
come from.

```
OperationalData                                   .../ARSO/OperationalData/2/0/Submodel
├─ States                                         SMC
│    └─ PackMLState                               SMC   StateSeries   (shaped as IDTA TimeSeries 1.1)
│         ├─ Metadata                             IDTA  .../TimeSeries/Metadata/1/1
│         │    ├─ Name, Description
│         │    └─ Record                          the template of one record
│         │         ├─ Time        UtcTime        IDTA's UTC time (semantic id: see Time)
│         │         └─ State       xs:int         semanticId: the meaning (…/state/operational),
│         │                                       its codes in a ConceptDescription (value list)
│         ├─ Segments                             IDTA  .../TimeSeries/Segments/1/1
│         │    ├─ Latest          InternalSegment one Record: the current value and its time
│         │    │                                  (the mapping writes here)
│         │    └─ History         LinkedSegment   Endpoint + Query (filled by the database part)
│         ├─ Source              ReferenceElement the interface property it comes from (AID)
│         └─ Trigger             Property         OnChange
├─ Measurements
│    └─ LinearAxis_ActualPosition                 SMC   MeasurementSeries
│         ├─ Metadata / Record: Time, ActualPosition (xs:double, Unit mm, Min 0, Max 160)
│         ├─ Segments: Latest, History
│         ├─ Source, Trigger (Sampled 100 ms | Deadband 0.1 mm)
│         └─ Origin             Property         Sensor | Estimated | Simulated
└─ Events
     └─ SkillExecutions                           SMC   EventLog
          ├─ Metadata / Record: Time, Event (Started | Succeeded | Failed | Aborted),
          │                     Skill, Session, Parameters (JSON), Results (JSON), ErrorID
          └─ Segments: Latest (the last few), History
```

**Telling the kinds apart**, twice, so people and programs both see it:

1. **By the collection**: `States`, `Measurements`, `Events` (what a person sees in a viewer).
2. **By the series' own semantic id**: `.../ARSO/OperationalData/StateSeries/1/0`,
   `MeasurementSeries`, `EventLog`, with IDTA's `https://admin-shell.io/idta/TimeSeries/1/1` as a
   supplemental semantic id ("shaped as a time series"). The ontology check (SHACL) holds the two
   together: a series in `States` is a StateSeries, and so on.

The *meaning* of the value (PackML state, actual position) stays where IDTA puts it: on the value
Property in the `Record` template, as today's data points carry it.

**Grouping.** One series per value, except where values change together and are read together:
a skill's State and ErrorID make one state series (one record per change, both values). An
equipment item's measurements could also be one series (a record with position and switch), but
they are sampled differently; keep them apart.

**What each kind adds to IDTA's structure:**

| Kind | Record | Metadata beyond IDTA | Trigger |
| --- | --- | --- | --- |
| State | Time + the state (+ ErrorID) | The codes as a value list in a ConceptDescription (PackML, the skill states, the error codes) | On change |
| Measurement | Time + the value | Unit, range (Min, Max), resolution or accuracy, Origin (Sensor, Estimated, Simulated); names as in OPC UA's AnalogItem (EngineeringUnits, EURange) | Sampled (interval) or deadband |
| Event | Time + the event's fields | The event types and their fields | On occurrence |

**Why the IDTA structure inside an SMC, and not one Time Series submodel per value.** IDTA's
template is a submodel: one stream per submodel. The filling module would get some 40 submodels,
each without the kind, the interface reference or the origin. Inside Operational Data:

- **For it:** the series stay together with their kind, origin and source; one submodel per
  resource as today; the elements keep IDTA's semantic ids, so a tool that knows Time Series can
  read a series, and one can be handed out as a standalone Time Series submodel when needed (a
  copy with the series' Metadata and Segments).
- **Against it:** a client that looks for submodels with IDTA's Time Series semantic id does not
  find them. If that matters (a lab dashboard that reads only standard Time Series), a resource
  can also carry one standard Time Series submodel per kind whose Record holds all variables of
  that kind; that is the standard's own wide form, and it can be generated from ours.

**Segments.**

- `Latest`: an InternalSegment with one Record, the current value with its time. It replaces
  today's data point as the target of the interface mapping (AIMC), so a client without the
  database still reads the current value from the AAS. For an event log: the last few events.
- `History`: a LinkedSegment, its Endpoint and Query left for the database part. One query per
  series. In a time series database the series' idShort or semantic id is the measurement, the
  kind and the resource are tags, the Record's values the fields.
- `Runs` (later): an ExternalSegment with a file, e.g. the records of one evaluation run (the
  paper's runs, attached to the AAS of the module they ran on).

**Time.** IDTA allows UTC, TAI and relative times. Use `UtcTime` (`xs:dateTime`) everywhere. The
template file in aas-model shows only `RelativePointInTime` in its example record; the UTC
time's semantic id is to be taken from the specification (IDTA 02008-1-1) in S1. Who
stamps it (FORTE's OPC UA source timestamp, or the collector on receipt) belongs to the database
part, but a Pi without a battery clock starts in the past: the collector's clock is the safe one
until the Pis' clocks are synchronised.

**Which AAS a series lives in.** In the AAS of the asset it describes: the module's PackML state
and its skills' states in the module's AAS; the axis' position, switch, Homed and Moving in the
axis' component AAS; a component skill's state in the component's AAS (as its skill is there).
The Source reference crosses into the module's interface description, since the module is the
one that serves them. Today all data points are in the module's AAS.

## 4. The Parameters submodel

**Proposal:** Parameters (ARSO's, version 1 made real) holds how the asset is set up, one entry per
parameter:

```
Parameters                                        .../ARSO/Parameters/1/0/Submodel
└─ LinearAxis_Speed                               SMC   Parameter
     ├─ Value         Property  xs:double  12.5    semanticId: the meaning
     ├─ Unit          mm/s
     ├─ Min, Max      the limits the asset allows (optional)
     ├─ Default       the value it was delivered with (optional)
     ├─ ChangedBy     Online | Redeploy | Rebuild  how a change reaches the asset
     └─ Target        ReferenceElement  where the value lives: an interface property it is
                                        written to (Online), or the program's instance input
                                        (Control Configuration) it is deployed into
```

`ChangedBy` follows the module rules and is what an engineer or an agent needs before changing it:

| ChangedBy | Meaning | Example today |
| --- | --- | --- |
| Online | Written to the running program (an input of a block, a writable property) | A skill parameter's default, a step's constant (these stay in Skills) |
| Redeploy | Part of the program's values; a new boot file and a restart | The Modbus endpoint, an IO address |
| Rebuild | Compiled into a block type; a FORTE build and an install | The axis speed and the skills' timeouts (compiled into the types today) |

Changes of a parameter are events (`Events/ParameterChanges`, or the Control Configuration's change
log, which already records reconfigurations).

**What goes where, for a module and its components:**

| Submodel | Holds | Filling module |
| --- | --- | --- |
| Technical Data | Fixed facts of the asset | Axis: lead 5 mm, travel 160 mm, motor rated 3 A |
| Parameters | Its settings | Axis: 4 microsteps, 2.8 A, 160 pulses/mm, 2 kHz, 12.5 mm/s, home timeout 60 s, move timeout 30 s; module: stop timeout 10 s; scale: scale factor |
| Skills | Per-call parameters with default and limits; step constants | Dispensing.Volume; Dispense.FlowRate = 1.0 |
| Control Configuration | What was built from all that | Instances, types, hashes, change log |
| Operational Data | What happens | States, measurements, events |

aas-model's `Parameters` (a Property per parameter, nested groups) carries the value only. Ours
adds unit, limits, `ChangedBy` and `Target`; we keep aas-model's name and nesting so its stations'
Parameters still read, and add those as optional children (the same way Skills were added).

## 5. Ideas worth taking from elsewhere

| From | Idea | Use |
| --- | --- | --- |
| IDTA 02008 Time Series 1.1 | Metadata with a Record template; internal, linked and external segments; time kinds | The inside of every series (Section 3) |
| IEC 61360 ConceptDescriptions (value lists) | An enumeration's codes and their meaning in one place | PackML states, skill states, error codes, occupation, instead of description text |
| OPC UA DataItems (AnalogItem: EngineeringUnits, EURange; MultiStateDiscrete: EnumStrings) and Events | The same distinction on the interface the modules already speak | Metadata names for measurements and states; events as OPC UA events later |
| PackML (ISA-TR88.00.02) | State model, and its tag groups: Status, Admin (counters, alarms), Command | States and counters of a module; alarms as events |
| OPC UA for Machinery (OPC 40001-1) | MachineryItemState, operation mode, operation counters | A module's own state next to PackML; counters as measurements |
| Time series databases | Measurement, tags, fields | Series name, kind and resource as tags, Record values as fields (for the database part) |

## 6. The plan

| # | Step | Where | Done when |
| --- | --- | --- | --- |
| S0 | **Decide** the questions in Section 7 | – | Answered |
| S1 | **ARSO.** Operational Data 2.0 (StateSeries, MeasurementSeries, EventLog, their Records, Source, Trigger, Origin, IDTA's elements reused); Parameters 1.0 (Parameter with Value, Unit, Min, Max, Default, ChangedBy, Target); Technical Data as it is; SHACL shapes for each | `ontology/ARSO/Modules` | `modreg check` validates a hand-written example of each |
| S2 | **Templates and classes.** Submodel templates from ARSO (`modreg generate`), reusing aas_pydantic's Time Series element classes so the IDTA semantic ids are the same objects; the same into aas-model (`arso-submodels`) | `modreg/templates`, aas-model | Generated classes read and write the examples |
| S3 | **ConceptDescriptions** with value lists for the PackML states, the skill states, the error codes, occupation | `modreg` | The AASs carry them; the HMI's state names come from them |
| S4 | **The module's profile.** Sort today's 45 data points by kind (Section 2); skill parameters' values out of Operational Data; the axis' and scale's series into their component AASs; the mapping (AIMC) writes into each series' `Latest`; events: skill executions, occupation, reconfigurations; Parameters from the module spec (the axis' settings, timeouts) with `ChangedBy` | `modreg/profile.py`, `modsync` (reconfigurations as events) | The example line's AASs are built this way and pass the check; `modlink` and the HMI still work |
| S5 | **Write the Latest values.** A small collector that reads the OPC UA properties and writes each series' Latest record (no database): the AAS shows the current state | `modlink` or a service | The HMI's and the AAS server's values agree |
| S6 | **The database** (left out here): LinkedSegment endpoints and queries, the collector writing history | – | Later |

S1 to S4 change ARSO, the generated classes and every module's AAS, so they come after the
paper's evaluation (B in [next-steps.md](next-steps.md)) unless the paper needs the states over
time for a figure (the downtime of a reconfiguration is a state series, so B1 may want S5).

## 7. Decisions needed

1. **Series inside Operational Data (SMC per series, as proposed) or standard Time Series
   submodels** (one per kind, wide records)? Proposed: inside Operational Data, the standard form
   generated when a client needs it.
2. **One series per value, or grouped** (a skill's State and ErrorID together, as proposed)?
3. **Component data in the component's AAS** (as proposed), or all in the module's AAS as today?
4. **Skill results**: only in the execution events (as proposed), or also a measurement series?
5. **Parameters**: build on aas-model's `Parameters` (add unit, limits, ChangedBy, Target as
   optional children, as proposed), or ARSO's own form?
6. **Technical Data and Parameters from the module spec**: put the axis' facts and settings that
   are only in the YAML today into the AAS (as proposed), or leave the spec as their source?
7. **When**: after the paper's evaluation (as proposed), or the state series (S5) for B1 now?
