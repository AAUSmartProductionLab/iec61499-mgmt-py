# Locations, points and the planar table's layout

Design of 27 Oct 2026, changed on 28 Oct from frames on Hierarchical Structures nodes to
coordinates in Operational Data (ARSO 0.13, vocabulary 0.5, `modreg/frames.py`; the reasons in
[design-log.md](design-log.md)). The planar table's AAS (section 3, `modreg/planar.py`) is built too.
Every resource AAS says where it and its points are, relative to another coordinate, so that any
point of interest (where a shuttle stands for the vial to be filled, where a robot picks or places)
is known in the planar table's frame, which is what a shuttle is moved in.

## 1. Coordinates, a tree of transforms

A **coordinate** is an element of a resource's Operational Data (`Measurements/Coordinates/<name>`):
a pose relative to another coordinate, which `RelativeTo` names by reference, in the same AAS or
another. The references make a tree, as ROS's tf does. Its root is the planar table's base: nothing
above the table is modelled (no building, no hall, no IDTA 02045).

```
PlanarTableAAS   TableBase                                   the root
                 Flyway_<c>_<r>       relative to TableBase
FillingModuleAAS ModuleBase           relative to TableBase (where the module stands)
                 LinearAxisMount      relative to ModuleBase (fixed: Z along the stroke)
                 LinearAxis           relative to LinearAxisMount; Z follows LinearAxis_ActualPosition
                 Transfer, Fill       relative to ModuleBase
PlanarShuttle1AAS Xbot                relative to TableBase; X, Y, Yaw follow Xbot_X, Xbot_Y, Xbot_Rz
FillingLineAAS   Infeed, Outfeed      relative to TableBase
```

- **Values:** X, Y, Z in mm and Roll, Pitch, Yaw in degrees, about the parent's fixed X, then Y, then
  Z axis: R = Rz(Yaw) Ry(Pitch) Rx(Roll), as ROS's RPY. The six values carry IDTA 02075's ids
  (AutomationML's frame attributes); the coordinate's meaning is a supplemental semantic id of the
  vocabulary: TableBase, ModuleBase, Mount, EndEffector, Mover, Flyway, and the points below.
- **Moving coordinates:** a moving part is a fixed mount and, relative to it, a coordinate whose
  moving values each follow a data point (`XSource` … `YawSource`). Its values in the AAS are the
  latest known. A product riding a shuttle is relative to the xbot (or a fixture on it): only the
  xbot's values change, and where the product was at any time is composed, never stored. When it is
  handed over, its `RelativeTo` changes.
- **Measured, not configured:** a module reports where it is put on the table (later by RFID), so even
  a module's base is a measurement. Each coordinate is the latest value of a series, as every
  measurement of Operational Data is to be ([state-and-parameters.md](state-and-parameters.md),
  section 3); the series in the time-series database comes with that part.
- **Where it lives:** in the AAS of the asset it belongs to; a module may hold several (ours hold a
  base, a mount and an end effector per axis, and their points), components hold none.
- **Hierarchical Structures** stays a bill of material: parts only, no frames, no point nodes.

```python
from modreg.frames import place, relative, where
where(envs, "FillingModuleAAS", "Transfer")                             # in the root's frame
relative(envs, ("PlanarTableAAS", "TableBase"), ("FillingModuleAAS", "Transfer"))
place(env, "ModuleBase", (table_aas_id, "TableBase"), Location(x=240.0, y=720.0, rz=180.0))
```

`chain` gives the coordinates up to the root and refuses a circle. A module described from its spec
alone is not placed: its base is the root of its own small tree until `place` puts it on the table.
A module's base has its origin at the middle of its front, at the table's height, Y out of the front,
Z up.

## 2. Points

A point of interest is a coordinate of a module with one of these meanings:

| Meaning | Where | Used by |
| --- | --- | --- |
| `lab:TransferPoint` | Where a shuttle stands for the module to work on what it carries (the vial under the needle) | The product agent: the shuttle's `MoveToPosition` target |
| `lab:ProcessingPoint` | Where the process acts (the needle tip at the fill position) | Checks, figures |
| `lab:PickPoint`, `lab:PlacePoint` | Where a robot picks or places | The loading and unloading robots |

A module spec's `points` (filling: `Transfer`, `Fill`; stoppering: `Transfer`, `Press`) become such
coordinates, and an item's `location` its mount. With the placeholder layout (`example_line.LAYOUT`),
the transfer points are the simulated table's stations, Filling (240, 660, 0) and Stoppering (600,
660, 90), and the needle at 40 mm is at the fill point (`test_modreg_frames.py`).

**The stations from the AAS (H5).** The line has points of its own where its loading and unloading
robots place and pick (Infeed, a PlacePoint; Outfeed, a PickPoint), and the planned capping module a
transfer point. `example_line.stations` gives all five in the table's frame; they are the scenario's
stations, and the scenario runs to them when it is handed them (`run_line(places=...)`).

## 3. The planar table as a module

The planar controller (`planar-controller/`, Python) already offers the table like a generated module:
`PlanarTable` and one `PlanarShuttle<N>` per xbot, each with occupation, module state and, for a
shuttle, the skill `MoveToPosition(X, Y, Rz)` (mm, degrees), under `/Objects/<Module>` in its own
namespace. So:

| AAS | Holds |
| --- | --- |
| `PlanarTable` (a module) | Nameplate; Hierarchical Structures: its shuttles (self-managed, each an AAS) and its **flyways** (co-managed); its coordinates: the table's base (the root) and each flyway's centre, the layout; the interface description and mapping of the controller's OPC UA; Skills: the module's own commands (occupy, release, reset, start, stop, abort, clear); Operational Data; Capability Description: transport |
| `PlanarShuttle<N>` (a component) | Skills: `MoveToPosition` with its parameters and results, and its own occupation and commands (in the controller each shuttle is a module of its own) |

The layout in the standard form is the flyways' frames: a configurator draws the table from them, and
a hole is a flyway that is not there. It stays current because the controller knows it: it reads the
layout from the PMC (`planar/layout.py`) and the xbots it finds. Proposal: the controller shows both
over OPC UA (`PlanarTable/Layout`: columns, rows, the flyways present, the flyway size), and `modreg`
describes the table from a small spec plus what runs (as `modreg profile --host` does for a FORTE
module), registering it again when they change. The controller does not write AASs itself.

**As built (28 Oct).** The controller lays out every module like a generated one, so
`modreg/planar.py` describes each with the Describer that describes a FORTE module, from a module spec
it makes in code. It departs from the table above in one point: in the controller every xbot is a
module of its own (its root, occupation and state), and a client such as `modlink` reaches one root
per AAS. So each shuttle's AAS is a module's, `PlanarShuttle<N>AAS`, whose one component, the xbot
(`PlanarShuttle<N>XbotAAS`, kind PlanarXbot), holds `MoveToPosition`; the table's AAS,
`PlanarTableAAS`, has the PMC as a part, the shuttles as parts found by their asset ids, and the
flyways (`Flyway_<column>_<row>`, co-managed, meaning `lab:Flyway`), each with a coordinate at its
centre relative to the table's base. What differs from a FORTE module: the browse paths are in the controller's namespace (index
2), there is no rule set, the errors include the controller's own (20 to 30), a skill has no
Conditions or Completion (the controller decides when a move has ended), and the results are
`ReachedX`, `ReachedY`, `ReachedRz` in the AAS, because an Operation's variables need idShorts of
their own (AASd-022) and the controller calls parameters and results both X, Y, Rz; they show the
controller's `Results/X` all the same.

The controller shows its layout since 28 Oct (`Equipment/PMC/Columns`, `Rows`, `FlywaySize`, `Holes`,
known once the PMC is connected; a commit in the submodule, not pushed yet). `modreg profile planar
--host <controller>` reads it with the shuttles, and `modreg register planar ... --every 10`
registers the AASs again whenever they change. `test_modreg_planar.py` runs the controller on its
simulated driver: the table brought to Execute and a shuttle moved with `modlink`, from the AASs alone.

## 4. What changes where

| Where | Change |
| --- | --- |
| ARSO (`operational-data.ttl`, 0.13) | `Measurements/Coordinates`: a coordinate with `RelativeTo`, the six values with their units, and the sources of its moving values |
| Vocabulary | The point meanings; a transport capability with the target as its properties |
| `modreg` | Coordinates from the specs (a module's base; an item's `location` as its mount, with the end effector of an axis; `points` of a module); the planar table's AAS from its spec and the controller, with the table's and the shuttles' coordinates |
| `planar-controller` | The layout over OPC UA |
| A small library | Compose frames, a point in another frame (for agents, the configurator, the line scenario) |

## 5. Open

| Point | Proposal |
| --- | --- |
| Units of a frame | AutomationML's, checked against IEC 62714 before building; the interfaces stay in mm and degrees |
| A building AAS, or Asset Location on the line | Neither (28 Oct): the line is the root. IDTA 02045-1-0 was read; it is for tracking and tracing, without orientation or parent-relative frames ([design-log.md](design-log.md)) |
| The frame as an extension of 02011 | Gone (28 Oct): coordinates in Operational Data instead, and Hierarchical Structures is a bill of material again |
| Which configurator reads the layout | To be named |
| Transport as a capability for the agents | With the agents, after the paper |
