"""Fail-closed sequence profile of BPMN 2.0 XML.

No label matching, expression evaluation, loop approximation or gateway flattening. A task
may repeat only as a sequential multi-instance activity; its count is a bound parameter.
"""
from defusedxml.ElementTree import fromstring

from iec61499_mgmt.models import Connection, IECValue, Instance, Network
from .models import (Call, Compilation, CompositeSkill, Constant, Procedure,
                     RecipeBindings, TargetProfile)

BPMN = "{http://www.omg.org/spec/BPMN/20100524/MODEL}"
XSI_TYPE = "{http://www.w3.org/2001/XMLSchema-instance}type"
DI_NAMESPACES = ("http://www.omg.org/spec/BPMN/20100524/DI",
                 "http://www.omg.org/spec/DD/20100524/DC",
                 "http://www.omg.org/spec/DD/20100524/DI")


def loop_cardinality(element, node_id: str) -> int | None:
    """Validate a sequential multi-instance marker; return its literal cardinality, if any."""
    if element.get("isSequential") != "true":
        raise ValueError(f"Parallel multi-instance is unsupported: {node_id}")
    if set(element.attrib) - {"id", "isSequential"}:
        raise ValueError(f"Unsupported loop attributes on {node_id}")
    cardinality = None
    for child in element:
        text = (child.text or "").strip()
        if child.tag != BPMN + "loopCardinality" or set(child.attrib) - {"id", XSI_TYPE} or not text.isdigit():
            raise ValueError(f"Loop of {node_id} needs only an integer loopCardinality")
        cardinality = int(text)
    return cardinality


def sequence(xml: str) -> list[tuple[str, str, bool, int | None]]:
    """Parse the BPMN and return its tasks in order as (id, label, looped, literal loop count)."""
    root = fromstring(xml)
    if root.tag != BPMN + "definitions":
        raise ValueError("Expected BPMN 2.0 definitions")
    # IDs are global within a BPMN document, even on flows and DI elements.
    ids = [el.get("id") for el in root.iter() if el.get("id")]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate BPMN ID")
    processes = root.findall(BPMN + "process")
    if len(processes) != 1:
        raise ValueError("sequence-v1 requires exactly one process")
    for element in root:
        if element.tag != BPMN + "process" and not any(element.tag.startswith("{" + ns + "}") for ns in DI_NAMESPACES):
            raise ValueError(f"Unsupported BPMN definition: {element.tag}")
    process = processes[0]
    if process.get("isClosed") == "false":
        raise ValueError("Open process semantics are unsupported")
    nodes, flows = {}, []
    for element in process:
        if element.tag in (BPMN + "documentation", BPMN + "laneSet"):
            continue
        kind = element.tag.removeprefix(BPMN)
        if kind not in ("startEvent", "endEvent", "task", "serviceTask", "sequenceFlow"):
            raise ValueError(f"Unsupported BPMN element {element.get('id')}: {kind}")
        node_id = element.get("id")
        if not node_id:
            raise ValueError(f"Missing BPMN ID on {kind}")
        for attr in element.attrib:
            allowed = {"id", "name", "sourceRef", "targetRef"} if kind == "sequenceFlow" else {"id", "name"}
            if attr not in allowed:
                raise ValueError(f"Unsupported BPMN attribute on {node_id}: {attr}")
        looped, cardinality = False, None
        for child in element:
            if child.tag == BPMN + "multiInstanceLoopCharacteristics" and kind in ("task", "serviceTask") and not looped:
                looped, cardinality = True, loop_cardinality(child, node_id)
                continue
            if child.tag not in (BPMN + "incoming", BPMN + "outgoing", BPMN + "documentation"):
                raise ValueError(f"Unsupported BPMN semantics on {node_id}: {child.tag}")
        if kind == "sequenceFlow":
            flows.append((element.get("sourceRef"), element.get("targetRef")))
        else:
            nodes[node_id] = (kind, element.get("name", node_id), looped, cardinality)
    starts = [n for n, (k, *_) in nodes.items() if k == "startEvent"]
    ends = [n for n, (k, *_) in nodes.items() if k == "endEvent"]
    if len(starts) != 1 or len(ends) != 1:
        raise ValueError("sequence-v1 requires one plain start and one plain end")
    incoming = {n: [] for n in nodes}
    outgoing = {n: [] for n in nodes}
    for src, dst in flows:
        if src not in nodes or dst not in nodes:
            raise ValueError("Sequence flow references an unknown node")
        outgoing[src].append(dst)
        incoming[dst].append(src)
    for n in nodes:
        if len(incoming[n]) != (0 if n == starts[0] else 1) or len(outgoing[n]) != (0 if n == ends[0] else 1):
            raise ValueError(f"Branch, merge or disconnected node is unsupported: {n}")
    visited, tasks = set(), []
    cursor = starts[0]
    while cursor not in visited:
        visited.add(cursor)
        kind, label, looped, cardinality = nodes[cursor]
        if kind in ("task", "serviceTask"):
            tasks.append((cursor, label, looped, cardinality))
        if cursor == ends[0]:
            break
        cursor = outgoing[cursor][0]
    if len(visited) != len(nodes) or cursor != ends[0] or not tasks:
        raise ValueError("Process must be one connected, nonempty, acyclic sequence")
    return tasks


def instance_name(scope: str, bpmn_id: str) -> str:
    # Reversible encoding is independent of order, labels, parameters and skill binding.
    # Encoding all IDs avoids collisions between a sanitized ID and a literal ID.
    """Stable, collision-free instance name for a BPMN element ID."""
    return f"{scope}.b_{bpmn_id.encode('utf-8').hex()}"


def repeat_count(node_id: str, looped: bool, cardinality: int | None, source, product) -> IECValue | None:
    """Loop count of a task as UINT: from its binding, else the BPMN literal; None if not looped."""
    if not looped:
        if source is not None:
            raise ValueError(f"{node_id}: repeat is bound but the task is not a sequential multi-instance")
        return None
    if source is None:
        value = None if cardinality is None else IECValue(type="UINT", value=cardinality)
    elif isinstance(source, Constant):
        value = source.value
    else:
        value = product.get(source.key)
    if value is None:
        raise ValueError(f"{node_id}: missing loop count")
    if value.type not in ("UINT", "UDINT", "INT", "DINT") or not 0 <= value.value <= 65535:
        raise ValueError(f"{node_id}: loop count must be an integer 0..65535")
    return IECValue(type="UINT", value=value.value)


def compile_bpmn(xml: str, bindings: RecipeBindings, target: TargetProfile,
                 product: dict[str, IECValue] | None = None) -> Compilation:
    """Compile a sequence BPMN and its bindings into a procedure and network."""
    tasks = sequence(xml)
    if {t[0] for t in tasks} != bindings.tasks.keys():
        raise ValueError("Task bindings must match BPMN task IDs exactly")
    product = product or {}
    calls, instances, connections = [], [], []
    call_type = target.library.types.get(target.call.fb_type)
    if call_type is None:
        raise ValueError("Call pattern is not in the runtime library")
    loop_type = target.library.types.get(target.loop.fb_type) if target.loop else None
    previous = target.facade_start
    for node_id, label, looped, cardinality in tasks:
        binding = bindings.tasks[node_id]
        skill = target.skills.get(binding.skill)
        if skill is None:
            raise ValueError(f"{node_id}: unknown skill {binding.skill}")
        runtime = target.runtime_bindings[binding.skill]
        if binding.parameters.keys() - skill.parameters.keys():
            raise ValueError(f"{node_id}: unknown skill parameter")
        parameters = {}
        for name, spec in skill.parameters.items():
            source = binding.parameters.get(name)
            if source is None:
                value = spec.default
            elif isinstance(source, Constant):
                value = source.value
            else:
                value = product.get(source.key)
            if value is None:
                raise ValueError(f"{node_id}.{name}: missing parameter value")
            try:
                spec.check(value)
            except ValueError as exc:
                raise ValueError(f"{node_id}.{name}: {exc}") from exc
            parameters[name] = value
        repeat = repeat_count(node_id, looped, cardinality, binding.repeat, product)
        calls.append(Call(id=node_id, label=label, skill=skill.id, parameters=parameters, repeat=repeat))
        fb_name = instance_name(target.scope, node_id)
        fb_parameters = {runtime.parameter_ports[n]: v for n, v in parameters.items()}
        if target.call.selector:
            fb_parameters[target.call.selector] = runtime.selector
        instances.append(Instance(name=fb_name, type=call_type.name, type_hash=call_type.type_hash,
                                  parameters=fb_parameters, origin=node_id))
        if repeat is not None:
            if loop_type is None:
                raise ValueError(f"{node_id}: the target profile has no loop pattern")
            loop_name, loop = fb_name + "_loop", target.loop
            instances.append(Instance(name=loop_name, type=loop_type.name, type_hash=loop_type.type_hash,
                                      parameters={loop.count: repeat}, origin=node_id))
            connections += [Connection(source=previous, destination=f"{loop_name}.{loop.enter}"),
                            Connection(source=f"{loop_name}.{loop.body}", destination=f"{fb_name}.{target.call.enter}"),
                            Connection(source=f"{fb_name}.{target.call.complete}", destination=f"{loop_name}.{loop.next}")]
            if target.facade_reset and loop.reset:
                connections.append(Connection(source=target.facade_reset, destination=f"{loop_name}.{loop.reset}"))
        else:
            connections.append(Connection(source=previous, destination=f"{fb_name}.{target.call.enter}"))
        connections.append(Connection(source=f"{fb_name}.{target.call.error}", destination=target.facade_error))
        if target.facade_reset and target.call.reset:
            connections.append(Connection(source=target.facade_reset, destination=f"{fb_name}.{target.call.reset}"))
        for wire in runtime.wires:
            connections.append(Connection(source=wire.source.replace("{instance}", fb_name),
                                          destination=wire.destination.replace("{instance}", fb_name), kind=wire.kind))
        previous = f"{fb_name}_loop.{target.loop.exit}" if repeat is not None else f"{fb_name}.{target.call.complete}"
    connections.append(Connection(source=previous, destination=target.facade_complete))
    network = Network(resource=target.resource, scope=target.scope, instances=instances, connections=connections)
    network.validate_library(target.library)
    used = sorted({c.skill for c in calls})
    profile = "sequence-v2" if any(c.repeat is not None for c in calls) else "sequence-v1"
    return Compilation(procedure=Procedure(id=bindings.procedure_id, profile=profile, calls=calls), network=network,
                       skill=CompositeSkill(id=bindings.procedure_id, uses=used,
                                            occupies=sorted({o for key in used for o in target.skills[key].occupies}),
                                            product_parameters=sorted({s.key for b in bindings.tasks.values()
                                                                       for s in b.parameters.values() if not isinstance(s, Constant)}),
                                            network_hash=network.digest()))
