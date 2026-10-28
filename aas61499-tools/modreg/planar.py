"""The planar table's AASs (H3; docs/locations-and-layout.md section 3).

The planar controller (``planar-controller/``) offers the table and every xbot over OPC UA the way
the lab's generated modules are laid out (``/Objects/<Module>``: Occupation, Module, Skills,
Equipment), in a namespace of its own. So each is described as a module, by the Describer that
describes a FORTE module, from a module spec made here:

- ``PlanarShuttle<N>AAS`` per xbot, a module of its own as in the controller (it is occupied, reset
  and started on its own). The shuttle is the xbot: the skill MoveToPosition(X, Y, Rz) in mm and
  degrees is its own, not a component's (no AAS of the xbot apart from the shuttle's); where the
  xbot is, is data (Equipment/Xbot/X, Y, Rz).
- ``PlanarTableAAS``, the table: its own commands (its Reset, Start, Stop, Abort and Clear reach the
  shuttles), whether the PMC is connected, and in its Hierarchical Structures the shuttles (each
  found by its asset id) and the flyways (co-managed, meaning Flyway). Its coordinates (ARSO 0.13)
  are the root of a line's: the table's base, and each flyway's centre relative to it (the layout a
  configurator draws). A shuttle's coordinate, its xbot, is relative to the table's base and follows
  the pose the controller measures (Equipment/Xbot/X, Y, Rz).

Nothing of it is FORTE's: no rule set and no record of a program. The errors are the module
rules' and the controller's own (planar/statemachines.py).

    profiles = describe_all(Table(columns=4, rows=3, holes=frozenset({(2, 1)}), shuttles=(1, 2, 3)))
    profiles = describe_all(read("opc.tcp://<controller>:4840/"))   # as the running controller shows it

``read`` takes the shuttles and the layout from the controller (its PMC's Columns, Rows, FlywaySize
and Holes, known once the PMC is connected), so the AAS follows the table when it changes.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import re

from aas_model.constants import BASE_URL
from aas_model.resource_template._helpers import put
from aas_pydantic.submodel_templates.nameplate import ManufacturerProductDesignation

from modgen.spec import Location, ModuleSpec, Parameter, Skill

from . import model
from aas_model.submodel_templates.arso import skills as arso
from aas_model.submodel_templates.coordinates import Coordinates
from aas_model.submodel_templates.variables import MeasurementsGroup
from .profile import Describer, coordinate, coordinate_ref, meaning, prop

NAMESPACE = "urn:aau:smartproductionlab:planar"
TABLE = "PlanarTable"
FLYWAY = 240.0                     # mm, a flyway's side
# The controller's own reasons beside the module rules' (planar/statemachines.py, ErrorID).
ERRORS = {"Blocked": 20, "XbotFault": 21, "PmcError": 22, "MotionTimeout": 23, "ProcedureFailed": 24,
          "NotOnTable": 25, "AngleNotAllowed": 26, "PmcNotConnected": 27, "XbotNotDetected": 28,
          "XbotCrooked": 29, "MotionDeviated": 30}
POSE = {"X": ("mm", 0.0, 10000.0, "Where to go along the table's X axis"),
        "Y": ("mm", 0.0, 10000.0, "Where to go along the table's Y axis"),
        "Rz": ("deg", -180.0, 180.0, "How the shuttle is to be turned about Z")}


@dataclass(frozen=True)
class Table:
    """What the controller says about the table: its flyways (columns by rows, without the holes),
    the xbots it offers, and where its OPC UA server is."""
    columns: int
    rows: int
    shuttles: tuple[int, ...]
    holes: frozenset = frozenset()
    endpoint: str = "opc.tcp://localhost:4840/"
    namespace: int = 2                     # the index of NAMESPACE on that server
    flyway: float = FLYWAY                 # mm, a flyway's side

    @property
    def flyways(self) -> list[tuple[int, int]]:
        return [(c, r) for r in range(self.rows) for c in range(self.columns) if (c, r) not in self.holes]


def shuttle(n: int) -> str:
    return f"PlanarShuttle{n}"


def asset(name: str) -> str:
    return f"{BASE_URL}/assets/{name}"


def spec(module: str, equipment: dict, skills: dict[str, Skill] | None = None) -> ModuleSpec:
    """A module spec of one of the controller's modules, for describing it only (nothing is
    generated from it): its AAS is ``<module>AAS``, its asset ``<module>``."""
    made = ModuleSpec.model_validate({
        "module": module, "project": module, "package": module.lower(), "opcua_root": f"/Objects/{module}",
        "targets": {"controller": {"io": "gpio"}}, "equipment": equipment,
        "aas": {"id_short": f"{module}AAS", "global_asset_id": asset(module)}})
    # The controller names a skill's parameters like the xbot's pose (X, Y, Rz), which the
    # generator's rules forbid for a program it writes: given here past them.
    return made.model_copy(update={"skills": skills}) if skills else made


def shuttle_spec(n: int) -> ModuleSpec:
    pose = {name: {"type": "LREAL", "unit": unit} for name, (unit, *_) in POSE.items()}
    # The controller decides when a move has ended, not a condition or a time of the generator's:
    # the skill is made past the rule that it says one.
    move = Skill.model_construct(
        description="Move the shuttle to a pose on the table (in the table's frame); the controller finds the way "
                    "past the other shuttles, and the skill succeeds when the xbot has arrived",
        equipment="Xbot", command="Move",
        parameters={name: Parameter(unit=unit, minimum=low, maximum=high, default=0.0, description=about)
                    for name, (unit, low, high, about) in POSE.items()},
        results={name: name for name in POSE})
    return spec(shuttle(n), {"Xbot": {"kind": "PlanarXbot", "description": f"Xbot {n}: a mover of the planar table",
                                      "inputs": pose, "commands": {"Stop": {}, "Move": {}}}},
                {"MoveToPosition": move})


def table_spec() -> ModuleSpec:
    return spec(TABLE, {"PMC": {"kind": "PlanarMotorController", "description": "The Planar Motor controller of the table",
                                "inputs": {"Connected": {"type": "BOOL"}}, "commands": {"Idle": {}}}})


class PlanarDescriber(Describer):
    """The Describer, for a module of the planar controller."""

    def __init__(self, spec: ModuleSpec, table: Table, designation: str):
        super().__init__(spec, "controller", None, None, None, table.endpoint)
        # The shuttle is its xbot, and the table its PMC: their skills are their own, not a component's.
        self.components = []
        self.namespace = table.namespace
        self.derive = False                    # no capabilities derived from a program
        self.designation = designation

    def skill(self, name: str) -> model.ModuleSkill:
        made = super().skill(name)
        made.Conditions = made.Completion = None          # the controller decides when a move has ended
        # An Operation's variables need names of their own (AASd-022): the results, where the move
        # ended, are Reached<X>; they show the controller's Results/<X> all the same (their meaning).
        for operation in made.Start.SkillOperation.values():
            for variable in operation.output_variable:
                if variable.id_short in POSE:
                    variable.id_short = f"Reached{variable.id_short}"
        return made

    def errors(self, held: arso.Errors) -> None:
        super().errors(held)
        for name, code in ERRORS.items():
            put(held.SkillError, name, arso.SkillError(**prop(code, "xs:integer")))

    def build(self):
        built = super().build()
        module = built[0][0]
        module.skills.RuleSet = None
        module.nameplate.ManufacturerProductDesignation = ManufacturerProductDesignation(value={"en": self.designation})
        return built


def flyway(column: int, row: int) -> model.LocatedNode:
    """A flyway, a part of the table (its coordinate is in the table's Operational Data)."""
    return model.LocatedNode(id_short=f"Flyway_{column}_{row}", entity_type="CoManagedEntity", global_asset_id="",
                             supplemental_semantic_ids=[meaning("Flyway")],
                             description=f"Flyway in column {column}, row {row}")


def table_coordinates(table: Table) -> MeasurementsGroup:
    """The table's base, the root of a line's coordinates, and each flyway's centre
    relative to it."""
    base = coordinate_ref("TableBase")
    found = {"TableBase": coordinate("TableBase", "TableBase",
                                     description="The corner of the table the shuttles' positions are measured from")}
    for column, row in table.flyways:
        name = f"Flyway_{column}_{row}"
        found[name] = coordinate(name, "Flyway", Location(x=(column + 0.5) * table.flyway, y=(row + 0.5) * table.flyway),
                                 base, description=f"The centre of the flyway in column {column}, row {row}")
    return MeasurementsGroup(value={"Coordinates": Coordinates(coordinate=found)})


def shuttle_coordinates(table_aas: str) -> MeasurementsGroup:
    """The xbot, relative to the table's base (``table_aas``: the table's AAS id): its X, Y and
    Yaw follow the pose the controller measures."""
    return MeasurementsGroup(value={"Coordinates": Coordinates(coordinate={"Xbot": coordinate(
        "Xbot", "Mover", None, coordinate_ref("TableBase", table_aas),
        {"X": "Xbot_X", "Y": "Xbot_Y", "Yaw": "Xbot_Rz"}, description="Where the xbot is on the table")})})


def describe_all(table: Table) -> list[dict]:
    """The profiles of the table (the first), then of each shuttle and its xbot."""
    built = PlanarDescriber(table_spec(), table, "Planar table (Planar Motor), through the planar controller").build()
    module = built[0][0]
    module.variables.Measurements = table_coordinates(table)
    nodes = module.hierarchical_structures.EntryNode.Node
    for n in table.shuttles:
        nodes[shuttle(n)] = model.LocatedNode(id_short=shuttle(n), entity_type="SelfManagedEntity",
                                              global_asset_id=asset(shuttle(n)),
                                              description=f"Shuttle {n}: an xbot, occupied and moved on its own")
    for column, row in table.flyways:
        nodes[f"Flyway_{column}_{row}"] = flyway(column, row)
    for n in table.shuttles:
        made = PlanarDescriber(shuttle_spec(n), table, f"Shuttle {n} of the planar table (an xbot)").build()
        made[0][0].variables.Measurements = shuttle_coordinates(module.id)
        built += made
    return [model.profile(found, global_asset_id=asset_id) for found, asset_id in built]


def holes(text: str) -> frozenset:
    """Flyways as the controller lists them: "<column>,<row>" apart by spaces."""
    return frozenset(tuple(int(v) for v in pair.split(",")) for pair in text.split())


class NotShown(RuntimeError):
    """The controller does not show what the table's AAS needs."""


async def _read(endpoint: str, timeout: float) -> Table:
    from asyncua import Client, ua
    async with Client(url=endpoint, timeout=timeout) as client:
        ns = await client.get_namespace_index(NAMESPACE)
        names = [(await child.read_browse_name()).Name for child in await client.nodes.objects.get_children()]
        shuttles = tuple(sorted(int(n[len("PlanarShuttle"):]) for n in names if re.fullmatch(r"PlanarShuttle\d+", n)))
        found = {}
        for name in ("Columns", "Rows", "FlywaySize", "Holes"):
            try:
                node = await client.nodes.objects.get_child([f"{ns}:{TABLE}", f"{ns}:Equipment", f"{ns}:PMC", f"{ns}:{name}"])
                found[name] = await node.read_value()
            except ua.UaError:
                raise NotShown(f"{endpoint} shows no {name} of the table's layout (a planar controller from before 28 Oct)") from None
    if not found["Columns"]:
        raise NotShown(f"{endpoint} knows no layout yet: its PMC has not been connected (Reset the table)")
    return Table(found["Columns"], found["Rows"], shuttles, holes(found["Holes"]), endpoint, ns, found["FlywaySize"])


def read(endpoint: str, timeout: float = 10.0) -> Table:
    """The table as the controller at ``endpoint`` shows it: its layout and the shuttles it offers."""
    return asyncio.run(_read(endpoint, timeout))
