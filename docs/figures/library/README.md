# The figures' shape pack

The shapes drawn for the figures, as draw.io libraries: one library per category, each shape one piece
(a part and its shadow, a monitor and its window are grouped). [catalogue.drawio](catalogue.drawio)
shows every shape with its name, a page per category.

| Library | What is in it |
| --- | --- |
| [iso-line.xml](iso-line.xml) | The line: floor, maglev table, stations (plain and with each process's tool), station arms, robots, vial trays, shuttles and pucks with an empty, filled, stoppered or capped vial, name tags, shadows |
| [iso-parts.xml](iso-parts.xml) | A module's parts: Raspberry Pi 5, linear axis, pump, scale, piston, gripper, cameras, the maglev segment with two xbots; the module tiles that lie on a plane |
| [iso-computers.xml](iso-computers.xml) | Computers in seven colours, a server rack, databases, monitors, the applications' windows (FORTE, AAS server, modsync, modreg, time series, orchestrator, scheduling, skill editor, planner, MES, ERP, HMI), people |
| [iso-aas.xml](iso-aas.xml) | The AAS shell as an isometric solid, standing or lying flat on a plane, blank or named (Product, Process, Resource, Module, Component, Line); AASs drawn as stacks of documents |
| [iso-planes.xml](iso-planes.xml) | The layers' planes, their labels, and the sketches that lie on a plane (a function block network, PackML, a skill's state machine, a module's AAS, product and process AAS, agents, a schedule, the HMI) |
| [flat.xml](flat.xml) | For flat figures: the AAS shell (blank and named), a submodel bar, the agents' badges, the icons of the layers |

## Using them

- **VS Code** (the draw.io extension): the libraries are set in `.vscode/settings.json`
  (`hediet.vscode-drawio.customLibraries`); open any `.drawio` file and they are in the shape panel.
- **draw.io desktop or app.diagrams.net**: *File > Open Library from > Device* and pick a `.xml` here.

The isometric shapes are drawn on 30° axes: a shape stands on a plane when its foot sits on the plane's
surface, and things that belong together stand straight above each other. Resize with the aspect kept.

## Building them

`python docs/presentation/source/build_library.py .` takes each shape from the figure pages it was drawn
on (`docs/figures/module-tools.drawio`, `slides.drawio`), by cell id, and draws the AAS shells
(`iso_shell` and `iso_shell_flat` in `drawlib.py`). Add a shape by adding a line to its category there.
