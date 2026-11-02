# Planar controller

<span class="pillar execution">Execution</span> `planar-controller`: controls a Planar Motor table and
offers it over OPC UA, built like the generated IEC 61499 modules, so the orchestrators treat the table
and each shuttle as modules. Python in Docker. Submodule `planar-controller/`.

<figure markdown="span">
  [![The table with its xbots on a grid of flyways, the controller and its modules over OPC UA, and its
  clients: the agents, the Configurator, any OPC UA client](../figures/planar-controller.png)](../figures/planar-controller.png)
  <figcaption>The controller moves every xbot as one plan and offers the table and each shuttle as a
  module with occupation, PackML states and the skill MoveToPosition.</figcaption>
</figure>

## The modules

The table (`PlanarTable`) and one module per xbot (`PlanarShuttle<N>`), in the namespace
`urn:aau:smartproductionlab:planar`:

| Below `/Objects/<Module>` | |
| --- | --- |
| `Occupation/Occupy(Session)`, `Release(Session)`, `Occupied` | the session is an id the client picks |
| `Module/Reset`, `Start`, `Stop`, `Abort`, `Clear` `(Session)`; `State`, `ErrorID` | PackML: Stopped, Resetting, Idle, Execute, Stopping, Aborted |
| `Skills/MoveToPosition/Start(Session, X, Y, Rz)`, `Stop`, `Abort`, `Reset` | shuttles only; millimetres and degrees |
| `Skills/MoveToPosition/State`, `ErrorID`, `Parameters`, `Results` | the skill's state machine is ModLib's |
| `Equipment/Xbot/X`, `Y`, `Rz`, `XbotState` | a shuttle's live pose |
| `Equipment/PMC/Connected`, `Columns`, `Rows`, `FlywaySize`, `Holes` | the table's layout as the PMC reports it |

Every method answers `[Accepted, ErrorID]` at once; an accepted move ends when the xbot has arrived.
The table's Reset connects to the PMC, takes mastership and levitates the xbots; its Stop and Abort
reach every shuttle, so one Reset and one Start of the table bring everything up.

All xbots move as one plan, so they pass each other in narrow places, and requests for the same place
are served in the order they came. In line mode, the shuttles follow a routing (lanes, turn spots, an
idle area) that the [Configurator](../interfaces/web-ui.md) keeps in the line's AAS and the controller
reads at every Reset.

## Its AAS and its clients

`modreg profile planar` describes the table and each shuttle as modules, with the table's frame
(Columns, Rows, FlywaySize) and the flyways' coordinates. Each shuttle gets a resource agent that
receives a product, carries it to a module's station and releases it ([line agents](agents.md)).

## Use it

```bash
./install.sh --pmc-ip 192.168.10.100 --autostart     # on a Linux machine that reaches the PMC
docker compose up -d --build                          # or from a clone; settings in .env
PMC_IP=127.0.0.1 AUTOSTART=1 python -m planar         # without Docker, against the PMC's simulator
```

The controller's own README in the submodule lists every setting and error id.
