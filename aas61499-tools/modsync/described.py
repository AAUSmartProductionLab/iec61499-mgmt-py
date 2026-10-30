"""What a module's AAS describes, as a module spec without wiring (``described``): the components
are the equipment, a component's skills the skill primitives, a skill of the module of the kind
Composite a module level skill with its flow, the steps of the module's own Reset and Stop the
procedures. What the module could not carry out is refused while reading (``NotDescribed``), by the
rules a module spec is checked by."""
from __future__ import annotations

from modgen.spec import (AllOf, AnyOf, Comparison, Composite, Decision, Equipment, Input, ModuleSpec, Parallel, Parameter,
                         Skill, Step)

from .aasjson import BASE, also, at, children, parts, qualifier, skills_in, submodel, target, variables

PRIMITIVE, COMPOSITE, CONTROL = (f"{BASE}/skill/{kind}" for kind in ("Primitive", "Composite", "ModuleControl"))
# The kinds of step a module built by the module rules can run (rule set 2: parallel blocks and decisions).
RUNS = ("step", "parallel", "decision", "conditional")
IEC = {"xs:double": "LREAL", "xs:boolean": "BOOL", "xs:short": "INT", "xs:int": "DINT", "xs:unsignedShort": "UINT"}


class NotDescribed(ValueError):
    """The AAS does not describe a module in the way the module rules need."""


def value_of(text, typ: str):
    """A value as the AAS writes it, as a Python value of the IEC type ``typ``."""
    if text is None:
        return None
    if typ == "BOOL":
        return str(text).strip().lower() == "true"
    return float(text) if typ == "LREAL" else int(float(text))


def parameter(variable: dict) -> Parameter:
    """A skill's parameter from the input variable of its Start operation."""
    typ = IEC[variable["valueType"]]
    default = qualifier(variable, "Default")
    return Parameter(type=typ, unit=qualifier(variable, "Unit"), minimum=value_of(qualifier(variable, "Minimum"), typ),
                     maximum=value_of(qualifier(variable, "Maximum"), typ),
                     default=value_of(variable.get("value") if default is None else default, typ),
                     meaning=next(iter(also(variable)), None))


def inside(inner: Parameter, outer: Parameter) -> bool:
    """Every value ``inner`` allows is one ``outer`` allows: a skill may not offer more than the
    component it hands the value to can do."""
    return ((outer.minimum is None or (inner.minimum is not None and inner.minimum >= outer.minimum))
            and (outer.maximum is None or (inner.maximum is not None and inner.maximum <= outer.maximum)))


def deployment(skill: dict) -> str | None:
    """What a skill's Deployment says: Built, Described, or None (not stated: built)."""
    return (at(skill, "Deployment") or {}).get("value")


def described(module: dict, components: list[dict], name: str = "Module", package: str = "module",
              opcua_root: str = "/Objects/Module") -> ModuleSpec:
    """The module its AAS (``module``) and the AASs of its ``components`` describe, as a module spec
    without wiring: equipment by name, skill primitives, module level skills and procedures.

    ``name``, ``package`` and ``opcua_root`` are what the program says about itself; the AAS is not
    asked for them.
    """
    structure_, skills_ = (submodel(module, n) for n in ("HierarchicalStructures", "Skills"))
    if skills_ is None:
        raise NotDescribed("the module's AAS has no Skills submodel")
    items = {node.get("globalAssetId"): node["idShort"] for node in parts(structure_)}
    equipment = {item: Equipment.model_construct(inputs={}) for item in items.values()}

    skills: dict[str, Skill] = {}
    for env in components:
        shell = env["assetAdministrationShells"][0]
        item = items.get(shell["assetInformation"].get("globalAssetId"))
        if item is None:
            raise NotDescribed(f"{shell['idShort']} is no component the module's Hierarchical Structures name")
        for skill in skills_in(submodel(env, "Skills")):
            start = at(skill, "Start", "Start")
            results = {v["idShort"]: v for v in variables(start, "outputVariables")}
            equipment[item].inputs.update({r: Input.model_construct(type=IEC[v["valueType"]], unit=qualifier(v, "Unit"))
                                           for r, v in results.items()})
            # What ends a primitive: its Conditions and Completion (ARSO 0.11), in an older AAS its Contract.
            term = lambda *path: (at(skill, *path) or {}).get("value")  # noqa: E731
            skills[skill["idShort"]] = Skill.model_construct(
                equipment=item, parameters={v["idShort"]: parameter(v) for v in variables(start, "inputVariables")},
                results={r: r for r in results}, offered=at(skill, "Start", "InterfaceReference") is not None,
                postcondition=term("Conditions", "Postcondition") or term("Contract", "Ensures"),
                timeout=term("Completion", "Timeout") or term("Contract", "Timeout") or "10s")

    def condition(element: dict, where: str):
        """A decision's condition: a comparison of a parameter of the skill (OperandType parameter:
        SourceElement) or a result of a step (output: StepId, OutputId) with a value, or a group."""
        get = lambda element_, name_: (at(element_, name_) or {}).get("value")  # noqa: E731
        kind = get(element, "ConditionType")
        if kind in ("all", "any"):
            parts = [condition(c, where) for c in sorted(children(at(element, "Conditions")), key=lambda c: int(get(c, "Order") or 0))]
            if not parts:
                raise NotDescribed(f"{where}: an empty group of conditions")
            return AllOf.model_construct(all=parts) if kind == "all" else AnyOf.model_construct(any=parts)
        if kind != "comparison":
            raise NotDescribed(f"{where}: a condition of the kind {kind} (the control compares values only)")
        operand, expected = at(element, "Operand"), at(element, "Expected")
        if get(operand, "OperandType") == "output":
            what = f"{get(operand, 'StepId')}.{get(operand, 'OutputId')}"
        else:
            what = (target(at(operand, "SourceElement")) or [""])[-1]
        raw = get(expected, "Value")
        value = str(raw).strip().lower() == "true" if get(expected, "DataType") == "boolean" else float(raw)
        return Comparison.model_construct(operand=what, op=get(element, "Operator"), value=value)

    def sequence(steps_: dict | None, operation: dict | None, results: dict[str, str] | None = None) -> list:
        """The steps below ``steps_`` in their Order. A step's Bindings hand each input of its skill
        a constant (Value) or a parameter of the skill it is a step of (SourceElement: an input
        variable of ``operation``); its Outputs say which results of the command it gives. A step of
        the kind parallel holds Branches, a decision a Condition and two Branches, a conditional a
        Condition and its own Steps."""
        inputs = {v["idShort"]: parameter(v) for v in variables(operation, "inputVariables")}
        get = lambda element, name_: (at(element, name_) or {}).get("value")  # noqa: E731
        found = []
        for step in sorted(children(steps_), key=lambda s: int(get(s, "Order") or 0)):
            name_, kind = get(step, "NodeId") or step["idShort"], get(step, "Kind") or "step"
            if kind not in RUNS:
                raise NotDescribed(f"step {name_} is of the kind {kind}, which the control of this module cannot run")
            branches = [sequence(at(b, "Steps"), operation, results)
                        for b in sorted(children(at(step, "Branches")), key=lambda b: int(get(b, "Order") or 0))]
            if kind == "parallel":
                found.append(Parallel.model_construct(name=name_, branches=branches))
                continue
            if kind in ("decision", "conditional"):
                if kind == "decision" and len(branches) != 2:
                    raise NotDescribed(f"step {name_}: a decision has two branches, not {len(branches)}")
                then, otherwise = (branches[0], branches[1]) if kind == "decision" else (sequence(at(step, "Steps"), operation, results), [])
                found.append(Decision.model_construct(name=name_, condition=condition(at(step, "Condition"), f"step {name_}"),
                                                      then=then, otherwise=otherwise))
                continue
            skill = (target(at(step, "Skill")) or [None])[-1]
            if skill not in skills:
                raise NotDescribed(f"step {name_} runs {skill}, which no component of the module has")
            bind = {}
            for given in children(at(step, "Bindings")):
                key = get(given, "Name")
                if key not in skills[skill].parameters:
                    raise NotDescribed(f"step {name_}: {skill} has no parameter {key}")
                declared_ = skills[skill].parameters[key]
                handed = (target(at(given, "SourceElement")) or [None])[-1]
                if handed is not None and handed not in inputs:
                    raise NotDescribed(f"step {name_}: {key} is handed {handed}, which the skill does not take")
                if handed is None and str(get(given, "Value") or "").strip() == "":
                    raise NotDescribed(f"step {name_}: {key} is handed nothing (neither a value nor a parameter of the skill)")
                constant = None if handed is not None else value_of(get(given, "Value"), declared_.type)
                if constant is not None and not isinstance(constant, bool) and (
                        (declared_.minimum is not None and constant < declared_.minimum)
                        or (declared_.maximum is not None and constant > declared_.maximum)):
                    raise NotDescribed(f"step {name_}: {key} = {constant} is outside what {skill} takes "
                                       f"({declared_.minimum} to {declared_.maximum})")
                if handed is not None and not inside(inputs[handed], declared_):
                    raise NotDescribed(f"step {name_}: {key} is handed {handed} ({inputs[handed].minimum} to "
                                       f"{inputs[handed].maximum}), more than {skill} takes ({declared_.minimum} "
                                       f"to {declared_.maximum})")
                bind[key] = handed if handed is not None else constant
            for given in children(at(step, "Outputs")):
                inner = (target(at(given, "ResultReference")) or [None])[-1]
                if inner not in skills[skill].results:
                    raise NotDescribed(f"step {name_}: {skill} has no result {inner}")
                if results is not None:
                    results[get(given, "OutputId")] = f"{name_}.{inner}"
            found.append(Step(skill=skill, name=name_, bind=bind))
        return found

    composites, procedures = {}, {}
    for skill in skills_in(skills_):
        kinds, steps_ = also(skill), at(skill, "Start", "Steps")
        if CONTROL in kinds:
            # What the module runs itself while resetting or stopping; a step is called <procedure>/<step>.
            if children(steps_):
                procedures[next(a for a in also(children(steps_)[0]) if "/procedures/" in a).split("/")[-2]] = sequence(steps_, None)
            continue
        if steps_ is None and COMPOSITE not in kinds:
            continue
        start, results = at(skill, "Start", "Start"), {}
        execute = sequence(steps_, start, results)
        declared_ = [v["idShort"] for v in variables(start, "outputVariables")]
        composites[skill["idShort"]] = Composite(
            description=next((d["text"] for d in skill.get("description") or []), ""),
            parameters={v["idShort"]: parameter(v) for v in variables(start, "inputVariables")},
            execute=execute, stop=sequence(at(skill, "Stop", "Steps"), None),
            results={r: results[r] for r in declared_ if r in results},
            # A skill that is described and not built yet has no action that calls it; it gets one
            # when it is built. One that is built is offered if a command of it names its action.
            offered=at(skill, "Start", "InterfaceReference") is not None or deployment(skill) != "Built",
            capability=next((k.rsplit("/", 1)[-1] for k in kinds if k.startswith(f"{BASE}/semantics/")), None))
    spec = ModuleSpec.model_construct(module=name, package=package, opcua_root=opcua_root, equipment=equipment,
                                      skills=skills, composites=composites, procedures=procedures)
    # A flow is checked by the rules a module spec is: names, equipment of parallel branches, what a
    # condition compares.
    for skill_name, comp in composites.items():
        try:
            spec.check_flow(skill_name, comp.execute, comp.parameters)
            spec.check_flow(skill_name, comp.stop, comp.parameters)
        except ValueError as exc:
            raise NotDescribed(str(exc)) from exc
    return spec
