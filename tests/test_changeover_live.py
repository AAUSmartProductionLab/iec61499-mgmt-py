"""Plan scenarios as guarded changeovers on the live cell (opt-in: --forte-exe).

BPMN + bindings + product values are compiled against the runtime's type library and applied
with `changeover()`: occupation and quiescence over OPC UA, drift check, apply, read-back.
"""
import json

import pytest

from conftest import free_port, launch_forte
from iec61499_mgmt import Network, verify
from iec61499_mgmt.changeover import changeover
from iec61499_mgmt.models import IECValue
from iec61499_mgmt.opcua_unit import OpcUaUnit
from iec61499_mgmt.protocol import Client, Command
from iec61499_mgmt.sysfile import load_application
from livecell import COMPLETE, IDLE, ROOT, SYS, Cell, CellServer, Resource, Ua, modbus_overrides, start
from skill_compiler import compile_bpmn
from skill_compiler.contracts import check_procedure
from skill_compiler.models import RecipeBindings
from skill_compiler.targets import bind_library

CELL = ROOT / "examples" / "cell"
MANAGER, OPERATOR = 99, 1


def compiled(target, version, product):
    """Network of process version ``version`` for product ``product``, after the contract check."""
    values = {k: IECValue.model_validate(v) for k, v in json.loads((CELL / f"product-{product}.json").read_text()).items()}
    bindings = RecipeBindings.model_validate_json((CELL / f"bindings-{version}.json").read_text())
    compilation = compile_bpmn((CELL / f"fill-{version}.bpmn").read_text(), bindings, target, values)
    report = check_procedure(compilation.procedure, target, bindings.assumes)
    assert report.status == "Passed", report.violations
    return compilation.network


def produce(ua, cell):
    """One production run by the operator on a new vial: occupy, reset, start, complete, release."""
    cell.new_vial()
    assert ua.call("Occupation/Occupy", OPERATOR) == [True, 0]
    assert ua.call("Unit/Reset", OPERATOR, 0) == [True, 0]
    ua.expect("Unit/State", IDLE)
    assert ua.call("Unit/Start", OPERATOR) == [True, 0]
    ua.expect("Unit/State", COMPLETE, timeout=15)
    assert ua.call("Occupation/Release", OPERATOR) == [True, 0]


@pytest.fixture
def cell_runtime(request, forte_exe, tmp_path, library):
    """Simulator, FORTE with the fixed application (Modbus backend), operator and manager clients."""
    sim_port, ua_port = free_port(), free_port()
    cell = Cell(travel_s=0.2, actuation_s=0.2, fill_rate=1.0)
    with CellServer(cell, port=sim_port), \
            launch_forte(forte_exe, tmp_path, request.config.getoption("--forte-runtime-dir"),
                         ["-op", str(ua_port)]) as port, Client("127.0.0.1", port) as client:
        client.execute(Command(op="create_fb", resource="", name="RES", type="iec61499::system::EMB_RES"))
        for command in load_application(SYS, "FillingCell").commands("RES", modbus_overrides(sim_port)):
            client.execute(command)
        res = Resource(client)
        start(res)
        operator = Ua(ua_port)
        manager = OpcUaUnit(f"opc.tcp://127.0.0.1:{ua_port}", MANAGER)
        try:
            operator.expect("State/NeedleUp", True)
            target = bind_library(json.loads((CELL / "target-template.json").read_text()), library)
            yield res, cell, operator, manager, target
        finally:
            manager.close()
            operator.close()


def test_product_changeovers(cell_runtime, library):
    """A -> B (parameter), B -> C (loop count), C -> D (structural), each checked by read-back."""
    res, cell, operator, manager, target = cell_runtime
    active = Network(resource="RES")
    expected = {"A": ("structural", None), "B": ("parameter", 1), "C": ("parameter", 1), "D": ("structural", None)}
    for product, version in [("A", "v2"), ("B", "v2"), ("C", "v2"), ("D", "v3")]:
        desired = compiled(target, version, product)
        record = changeover(res.client, manager, active, desired, library)
        change_class, commands = expected[product]
        assert (record.result, record.change_class, record.released) == ("Applied", change_class, True), record
        if commands is not None:
            assert record.commands == commands
        active = desired
        if product == "A":
            res.write("Facade.Installed", True)
            res.fire("Facade.CONFIG")
        produce(operator, cell)
        volume, cycles = {"A": (0.5, 1), "B": (1.0, 1), "C": (1.0, 2), "D": (1.0, 2)}[product]
        assert volume * cycles <= cell.filled_ml < volume * cycles + 0.2 * cycles, product
        assert cell.inputs["Stoppered"] and cell.inputs["Checked"] == (product == "D")
    assert cell.shoot_through == 0


def test_changeover_guards(cell_runtime, library):
    """Occupied unit, runtime drift and out-of-range product values all prevent deployment."""
    res, cell, operator, manager, target = cell_runtime
    a = compiled(target, "v2", "A")
    assert changeover(res.client, manager, Network(resource="RES"), a, library).result == "Applied"
    b = compiled(target, "v2", "B")
    assert operator.call("Occupation/Occupy", OPERATOR) == [True, 0]
    record = changeover(res.client, manager, a, b, library)
    assert (record.result, record.problems) == ("Rejected", ["unit occupation refused"])
    assert operator.call("Occupation/Release", OPERATOR) == [True, 0]
    edge = next(c for c in a.connections if c.source == "Facade.START")
    res.send("disconnect", source=edge.source, destination=edge.destination)
    record = changeover(res.client, manager, a, b, library)
    assert record.result == "Rejected" and record.released
    assert record.problems == [f"drift: missing connection {edge.source} -> {edge.destination}"]
    assert verify(res.client, a) != []                           # nothing was applied
    with pytest.raises(ValueError, match="maximum"):
        compiled(target, "v2", "E")                             # 3.0 mL is outside 0.1..2.0
