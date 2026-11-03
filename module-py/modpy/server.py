"""The OPC UA server of modules run in Python, laid out node for node as a generated module's on
FORTE, so that whatever drives a FORTE module (the agents, the DMP, modlink, the HMI) drives these the
same way and the module's AAS, made by modreg's Describer, describes them:

  /Objects/<Module>/Occupation       Occupy(RD_1 Session), Release(RD_1); Occupied (Boolean)
  /Objects/<Module>/Module           Reset, Start, Stop, Abort, Clear (RD_1 Session); State (Byte)
  /Objects/<Module>/Skills/<Skill>   Start(RD_1 Session, RD_2.. the parameters), Stop, Abort, Reset
                                     (RD_1); State (Byte), ErrorID (UInt16), Parameters/<p>, Results/<r>;
                                     a module level skill's steps below Execute/<step> and Stopping/<step>
  /Objects/<Module>/Procedures/<Procedure>/<step>   State, ErrorID, Parameters/<p>, Results/<r>
  /Objects/<Module>/Equipment/<Item>/<input>

Every node is in namespace 1, as FORTE's are. Every method answers [SD_1 Accepted (Boolean), SD_2
ErrorID (UInt16)] at once; what it started shows in State. Several modules may share one server,
each below /Objects/<Module>, as several modules share one FORTE.

Methods run the module's code in a worker thread with its lock held, and the variables are refreshed
every 20 ms and once more before a method answers: a client that reads State after Start sees
Running, never the Succeeded of the run before.
"""
from __future__ import annotations

import asyncio
import logging
import math

from asyncua import Server, ua

from modgen.spec import ModuleSpec

from .machines import E, Skill
from .run import Runtime

log = logging.getLogger(__name__)

NAMESPACE = "urn:aau:smartproductionlab:modpy"
TYPES = {"BOOL": (ua.VariantType.Boolean, ua.ObjectIds.Boolean, bool),
         "LREAL": (ua.VariantType.Double, ua.ObjectIds.Double, float),
         "INT": (ua.VariantType.Int16, ua.ObjectIds.Int16, int),
         "DINT": (ua.VariantType.Int32, ua.ObjectIds.Int32, int),
         "UINT": (ua.VariantType.UInt16, ua.ObjectIds.UInt16, int)}


def argument(name: str, type_id: int, description: str = "") -> ua.Argument:
    made = ua.Argument()
    made.Name, made.DataType, made.ValueRank = name, ua.NodeId(type_id), -1
    made.ArrayDimensions, made.Description = [], ua.LocalizedText(description)
    return made


# As FORTE names them: after the data ports of the SERVER block that serves the method.
SESSION = argument("RD_1", ua.ObjectIds.String, "Session: the occupation's session ID (a UUID the client chose)")
ANSWER = [argument("SD_1", ua.ObjectIds.Boolean, "Accepted"),
          argument("SD_2", ua.ObjectIds.UInt16, "ErrorID: 4 NotReady, 5 NotPermitted, 6 Busy, 8 OutOfRange, ...")]


def result_types(spec: ModuleSpec) -> dict[str, str]:
    """The type of every skill's results, by "<skill>.<result>": the type of the input it is read from."""
    found = {}
    for name, decl in spec.skills.items():
        for result, source in decl.results.items():
            found[f"{name}.{result}"] = spec.equipment[decl.equipment].inputs[source].type
    return found


class ModuleServer:
    """One OPC UA server for the runtimes it is handed."""

    def __init__(self, runtimes: list[Runtime], port: int = 4840, host: str = "0.0.0.0", name: str | None = None):
        self.runtimes, self.port = runtimes, port
        self.endpoint = f"opc.tcp://{host}:{port}/"
        self.name = name or "modpy " + ", ".join(rt.spec.module for rt in runtimes)
        self.server: Server | None = None
        self.idx = 1
        self._published: list[tuple[Runtime, object, object, ua.VariantType]] = []   # (runtime, node, read, type)
        self._last: dict = {}
        self._refreshing = asyncio.Lock()

    async def init(self) -> None:
        self.server = Server()
        await self.server.init()
        self.server.set_endpoint(self.endpoint)
        self.server.set_server_name(self.name)
        self.server.set_security_policy([ua.SecurityPolicyType.NoSecurity])
        # The modules' nodes in namespace 1, as FORTE has them: the server's own URI is index 1.
        await self.server.set_application_uri(NAMESPACE)
        self.idx = await self.server.register_namespace(NAMESPACE)
        if self.idx != 1:
            raise RuntimeError(f"the modules' namespace is {self.idx}, not 1")
        for rt in self.runtimes:
            await self._module(rt)

    async def serve(self, stop: asyncio.Event | None = None) -> None:
        """Serve until ``stop`` is set (or cancelled)."""
        if self.server is None:
            await self.init()
        async with self.server:
            log.info("OPC UA server on %s: %s", self.endpoint, ", ".join(rt.spec.module for rt in self.runtimes))
            while stop is None or not stop.is_set():
                await self._refresh()
                await asyncio.sleep(0.02)

    # The address space ---------------------------------------------------------------------------

    async def _module(self, rt: Runtime) -> None:
        root = self.server.nodes.objects
        for part in [p for p in rt.spec.opcua_root.split("/") if p][1:]:     # below /Objects
            root = await root.add_object(self.idx, part)
        occupation = await root.add_object(self.idx, "Occupation")
        module = rt.module
        await self._method(rt, occupation, "Occupy", [SESSION], lambda s: module.occupation.occupy(s))
        await self._method(rt, occupation, "Release", [SESSION], lambda s: module.occupation.release(s))
        await self._variable(rt, occupation, "Occupied", lambda: module.occupation.occupied, ua.VariantType.Boolean)
        control = await root.add_object(self.idx, "Module")
        for command in ("Reset", "Start", "Stop", "Abort", "Clear"):
            await self._method(rt, control, command, [SESSION], lambda s, c=command: module.command(c, s))
        await self._variable(rt, control, "State", lambda: module.state, ua.VariantType.Byte)

        objects = {"": root}

        async def at(path: str):
            if path not in objects:
                parent, _, name = path.rpartition("/")
                objects[path] = await (await at(parent)).add_object(self.idx, name)
            return objects[path]

        types = result_types(rt.spec)
        offered = set(map(id, rt.offered.values()))
        for path, skill in rt.skills.items():
            await self._skill(rt, await at(path), skill, id(skill) in offered, types)
        for name, item in rt.equipment.items():
            node = await at(f"Equipment/{name}")
            for signal, decl in item.eq.inputs.items():
                await self._variable(rt, node, signal, lambda i=name, s=signal: rt.points.read(i, s),
                                     TYPES[decl.type][0])

    async def _skill(self, rt: Runtime, node, skill: Skill, methods: bool, types: dict[str, str]) -> None:
        if methods:
            names = list(skill.parameters)
            inputs = [SESSION] + [argument(f"RD_{i}", TYPES[pr.type][1], f"{p}: {pr.minimum}..{pr.maximum} {pr.unit or ''}".strip())
                                  for i, (p, pr) in enumerate(skill.parameters.items(), 2)]

            def start(session, *values):
                given = {p: TYPES[skill.parameters[p].type][2](v) for p, v in zip(names, values) if v not in (None, "")}
                return skill.start(session or "", given)

            await self._method(rt, node, "Start", inputs, start)
            await self._method(rt, node, "Stop", [SESSION], skill.stop)
            await self._method(rt, node, "Abort", [SESSION], skill.abort)
            await self._method(rt, node, "Reset", [SESSION], skill.reset)
        await self._variable(rt, node, "State", lambda: skill.state, ua.VariantType.Byte)
        await self._variable(rt, node, "ErrorID", lambda: skill.error, ua.VariantType.UInt16)
        if skill.parameters:
            folder = await node.add_object(self.idx, "Parameters")
            for p, pr in skill.parameters.items():
                await self._variable(rt, folder, p, lambda p=p, kind=TYPES[pr.type][2]: kind(skill.values[p]),
                                     TYPES[pr.type][0])
        if skill.result_names:
            folder = await node.add_object(self.idx, "Results")
            decl = composite_or_skill(rt.spec, skill.path)
            for r in skill.result_names:
                kind = types.get(f"{decl}.{r}") or result_of_composite(rt.spec, decl, r, types)
                await self._variable(rt, folder, r, lambda r=r, k=TYPES[kind][2]: k(skill.results.get(r, 0)),
                                     TYPES[kind][0])

    async def _method(self, rt: Runtime, parent, name: str, inputs: list[ua.Argument], fn) -> None:
        def call(*values):
            with rt.lock:
                return fn(*values)

        async def handler(_parent, *args):
            values = [a.Value for a in args]
            try:
                accepted, error = await asyncio.to_thread(call, *values)
            except Exception:                    # noqa: BLE001 (answered as refused)
                log.exception("%s/%s", rt.spec.module, name)
                accepted, error = False, E["NotReady"]
            await self._refresh()
            return [ua.Variant(bool(accepted), ua.VariantType.Boolean), ua.Variant(int(error), ua.VariantType.UInt16)]

        await parent.add_method(self.idx, name, handler, inputs, ANSWER)

    async def _variable(self, rt: Runtime, parent, name: str, read, vtype: ua.VariantType) -> None:
        with rt.lock:
            value = read()
        node = await parent.add_variable(self.idx, name, ua.Variant(value, vtype))
        self._published.append((rt, node, read, vtype))
        self._last[node.nodeid] = value

    # Keeping the variables current -------------------------------------------------------------

    def _snapshot(self) -> list:
        values = []
        for rt in self.runtimes:
            with rt.lock:
                values += [read() for runtime, _, read, _ in self._published if runtime is rt]
        return values

    async def _refresh(self) -> None:
        async with self._refreshing:             # one at a time: an older snapshot never overwrites a newer
            values = await asyncio.to_thread(self._snapshot)
            ordered = [entry for rt in self.runtimes for entry in self._published if entry[0] is rt]
            for (_, node, _, vtype), value in zip(ordered, values):
                if not same(self._last.get(node.nodeid), value):
                    self._last[node.nodeid] = value
                    await node.write_value(ua.Variant(value, vtype))


def composite_or_skill(spec: ModuleSpec, path: str) -> str:
    """The skill or module level skill a path's instance is of: Skills/<s>, or a step's skill."""
    parts = path.split("/")
    if parts[0] == "Skills" and len(parts) == 2:
        return parts[1]
    composite = spec.composites.get(parts[1]) if parts[0] == "Skills" else None
    steps = (composite.execute if parts[2] == "Execute" else composite.stop) if composite else spec.procedures[parts[1]]
    return next(step.skill for step in steps if step.name == parts[-1])


def result_of_composite(spec: ModuleSpec, name: str, result: str, types: dict[str, str]) -> str:
    """The type of a module level skill's result: that of the step's result it is."""
    step, _, res = spec.composites[name].results[result].partition(".")
    skill = next(s.skill for s in spec.composites[name].execute if getattr(s, "name", None) == step)
    return types[f"{skill}.{res}"]


def same(a, b) -> bool:
    return a == b and type(a) is type(b) or (isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b))
