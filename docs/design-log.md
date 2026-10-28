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
