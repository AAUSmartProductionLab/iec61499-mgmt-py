# Locations, points and the planar table's layout

Design of 27 Oct 2026, a proposal. Every resource AAS says where its parts are relative to itself, so
that any point of interest (where a shuttle stands for the vial to be filled, where a robot picks or
places) is known in any frame, in particular in the planar table's, which is what a shuttle is moved
in. And the planar table is described like any module, with its flyway layout in its AAS.

## 1. Frames along the hierarchy

Each AAS lists its parts in its Hierarchical Structures (IDTA 02011, in ARSO): a line its modules and
the planar table, a module its components. On a part's entity goes its **Frame**: the pose of the
part's frame in the parent's frame, as AutomationML's Frame attribute (IEC 62714), which IDTA 02075
(Factory Automation Data for Plant Planning) publishes as `xframe`, `yframe`, `zframe`, `rxframe`,
`ryframe`, `rzframe`. A pose in the line is then the composition along the tree:

```
line  ←  FillingModule  ←  FillPoint            the point in the line's frame
line  ←  PlanarTable                            the table in the line's frame
=> FillPoint in the table's frame = (line ← PlanarTable)⁻¹ ∘ (line ← FillingModule) ∘ (FillingModule ← FillPoint)
```

The building is the root: its AAS (or the line's) gets IDTA 02045 Asset Location (address, a
coordinate system with ground control points, the hall as an area), and everything inside is frames.

## 2. Points

A point of interest is a frame in a module that is no part of it: a **CoManagedEntity** (an entity
without an AAS of its own) in the module's Hierarchical Structures, with its Frame and its meaning as a
supplemental semantic id:

| Meaning | Where | Used by |
| --- | --- | --- |
| `lab:TransferPoint` | Where a shuttle stands for the module to work on what it carries (the vial under the needle) | The product agent: the shuttle's `MoveToPosition` target |
| `lab:ProcessingPoint` | Where the process acts (the needle tip at the fill position) | Checks, figures |
| `lab:PickPoint`, `lab:PlacePoint` | Where a robot picks or places | The loading and unloading robots |

The stations of `planar-controller/tests/line_scenario.py` (Infeed, Filling, Stoppering, Capping,
Outfeed, hard-coded in table millimetres) then come from the AAS: the transfer point of each module in
the table's frame.

## 3. The planar table as a module

The planar controller (`planar-controller/`, Python) already offers the table like a generated module:
`PlanarTable` and one `PlanarShuttle<N>` per xbot, each with occupation, module state and, for a
shuttle, the skill `MoveToPosition(X, Y, Rz)` (mm, degrees), under `/Objects/<Module>` in its own
namespace. So:

| AAS | Holds |
| --- | --- |
| `PlanarTable` (a module) | Nameplate; Hierarchical Structures: its shuttles (self-managed, each an AAS) and its **flyways** (co-managed, each with its Frame: the layout); the interface description and mapping of the controller's OPC UA; Skills: the module's own commands (occupy, release, reset, start, stop, abort, clear); Operational Data; Capability Description: transport |
| `PlanarShuttle<N>` (a component) | Skills: `MoveToPosition` with its parameters and results, and its own occupation and commands (in the controller each shuttle is a module of its own) |

The layout in the standard form is the flyways' frames: a configurator draws the table from them, and
a hole is a flyway that is not there. It stays current because the controller knows it: it reads the
layout from the PMC (`planar/layout.py`) and the xbots it finds. Proposal: the controller shows both
over OPC UA (`PlanarTable/Layout`: columns, rows, the flyways present, the flyway size), and `modreg`
describes the table from a small spec plus what runs (as `modreg profile --host` does for a FORTE
module), registering it again when they change. The controller does not write AASs itself.

## 4. What changes where

| Where | Change |
| --- | --- |
| ARSO (`hierarchical-structures.ttl`) | A `Frame` on an entity (the six values, their units); point entities with a meaning; Asset Location (IDTA 02045) as an optional submodel of a line or a building |
| Vocabulary | The point meanings; a transport capability with the target as its properties |
| `modreg` | Frames and points from the specs (`location` of a module in the line, of a component in the module; `points` of a module); the planar table's AAS from its spec and the controller |
| `planar-controller` | The layout over OPC UA |
| A small library | Compose frames, a point in another frame (for agents, the configurator, the line scenario) |

## 5. Open

| Point | Proposal |
| --- | --- |
| Units of a frame | AutomationML's, checked against IEC 62714 before building; the interfaces stay in mm and degrees |
| A building AAS, or Asset Location on the line | The line, until there is more than one line |
| Which configurator reads the layout | To be named |
| Transport as a capability for the agents | With the agents, after the paper |
