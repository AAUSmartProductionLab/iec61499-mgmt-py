"""The structure of a module, read from its program by the module rules (docs/module-rules.md).

A module's program says what the module is made of: its equipment, the skill primitives it has
and offers, its module level skills with their parameters and sequences, and its procedures. The
rules fix how each of these looks in a program, so the structure can be read back from one
without the module spec it may have been generated from:

- what runs (instances, connections and values, as FORTE reports them or a system file states
  them) gives the equipment, the offered primitives, the module level skills and the procedures;
- what a skill primitive is (its type file) gives its parameters, results and equipment. A
  primitive the module does not offer has no instance, so only its type tells of it.

``structure`` reads it, ``stated`` gives the same of a module spec. Both return the dictionary
below, with numbers as numbers and durations in milliseconds, so the two compare with ``==``::

    module, package, opcua_root
    equipment:  [item]
    skills:     {skill: offered, equipment, parameters {p: type, default, minimum, maximum},
                 results [r], timeout}
    composites: {skill: offered, parameters, execute [node], stop [node], results {r: step.result}}
    procedures: {name: [step]}
    node:       a step, or (rule set 2) a parallel block or a decision:
    step:       skill, name, bind {parameter: constant or the composite's parameter}
    parallel:   kind "parallel", name (its SKILL_Join), branches [[node]]
    decision:   kind "decision", name (its SKILL_Merge), condition, then [node], otherwise [node]
    condition:  {operand, op, value} (operand: a parameter of the skill or <step>.<result}), {all: [...]}
                or {any: [...]}, groups of one kind not nested in their own kind (``canonical``)

A step's ``bind`` holds every parameter of its skill: what a running program reports does not
tell a constant that was bound from a default that was left.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from defusedxml.ElementTree import parse

from modgen.library import PARAM_RANGE, q
from modgen.module import tlit
from modgen.spec import AllOf, AnyOf, Decision, ModuleSpec, Parallel, Parameter, Step

from .device import BOOT, literal

CORE = q("SKILL_Core")
LATCH = q("SKILL_Param_")
JOIN, CONDITION, MERGE = q("SKILL_Join"), q("SKILL_Condition_"), q("SKILL_Merge")
# Where a block of a flow goes on when it is done, or a condition has been evaluated.
ONWARD = (".SUCCESS", ".DONE", ".EO", ".YES", ".NO")
# The inputs every skill primitive has (rule 2.3); its other inputs are its parameters.
STANDARD = ("Module", "UaRoot", "UaPath", "UaEnable", "Methods", "Holder", "ReleaseAfter", "Timeout")
PROCEDURES = ("Resetting", "Stopping")


def bound(value: str | None, typ: str, which: int):
    """A limit as declared; the limit of the type itself (what an undeclared one reads as) is none."""
    limits = PARAM_RANGE.get(typ)
    if value is None or (limits and literal(value) == literal(limits[which])):
        return None
    return literal(value)


def declared(typ: str, default: str | None, lower: str | None, upper: str | None) -> dict:
    """A parameter as the structure holds it."""
    return {"type": typ, "default": literal(default), "minimum": bound(lower, typ, 0), "maximum": bound(upper, typ, 1)}


def read_primitives(folder: str | Path) -> dict[str, dict]:
    """The skill primitive types (``SK_<Skill>.fbt``) below a type library folder, by skill: the
    package, and what rule 2 lets a type tell: equipment, parameters, results and timeout."""
    found = {}
    for path in sorted(Path(folder).rglob("SK_*.fbt")):
        root = parse(str(path)).getroot()
        info = root.find("CompilerInfo")
        written = {(fb.get("Name"), p.get("Name")): p.get("Value")
                   for fb in root.findall("FBNetwork/FB") for p in fb.findall("Parameter")}
        inputs = {v.get("Name"): v for v in root.findall("InterfaceList/InputVars/VarDeclaration")}
        outputs = [v.get("Name") for v in root.findall("InterfaceList/OutputVars/VarDeclaration")]
        timeout = inputs["Timeout"].get("InitialValue") if "Timeout" in inputs else None
        found[root.get("Name")[len("SK_"):]] = {
            "package": info.get("packageName") if info is not None else "",
            "equipment": literal(written.get(("Logic", "Equipment"))),
            "parameters": {n: declared(v.get("Type"), v.get("InitialValue"), written.get((f"Par_{n}", "Lower")),
                                       written.get((f"Par_{n}", "Upper")))
                           for n, v in inputs.items() if n not in STANDARD},
            "results": [n[len("R_"):] for n in outputs if n.startswith("R_")],
            "timeout": literal(timeout)[1] if timeout else None,
        }
    return found


def structure(fbs: dict[str, str], connections, value: Callable[[str], str | None],
              primitives: dict[str, dict]) -> dict:
    """The structure of the program with the instances ``fbs`` (name -> type), the ``connections``
    (source, destination) and the input values ``value(port)`` gives (None: not written).
    ``primitives`` are its skill primitive types (``read_primitives``)."""
    package = next(t.partition("::")[0] for t in fbs.values() if "::EQ_" in t or "::SK_" in t)
    primitive = f"{package}::SK_"
    driven = {d: s for s, d in connections}

    # Rule 1.5: one INIT chain from the boot event; it gives the order things were declared in.
    order, at = [], driven_by(connections, BOOT)
    while at:
        top = at.partition(".")[0]
        if top not in order:
            order.append(top)
        at = driven_by(connections, at[:-len(".INIT")] + ".INITO", ".INIT")

    def step(name: str) -> dict:
        skill = fbs[name][len(primitive):]
        bind = {}
        for p, decl in primitives[skill]["parameters"].items():
            source = driven.get(f"{name}.{p}")
            # Rule 3: a parameter of the skill reaches a step from its latch's P.
            bind[p] = source.split(".")[-2] if source else (
                decl["default"] if value(f"{name}.{p}") is None else literal(value(f"{name}.{p}")))
        return {"skill": skill, "name": name.rpartition(".")[2], "bind": bind}

    def flow(prefix: str) -> list[dict]:
        """The flow of the sequence ``prefix`` (rule set 2): from the event inputs started from outside it,
        steps one after the other, parallel blocks (a SKILL_Join and the branches whose ends reach its
        DONE_<i>) and decisions (SKILL_Condition_ blocks choosing a branch, both ending in a SKILL_Merge)."""
        inside = lambda port: port.startswith(prefix + ".") and port.count(".") == prefix.count(".") + 2  # noqa: E731
        targets: dict[str, list[str]] = {}
        for s_, d in connections:
            targets.setdefault(s_, []).append(d)
        kind = lambda port: fbs.get(port.rpartition(".")[0], "")                                           # noqa: E731
        begins = lambda port: inside(port) and (port.endswith(".START") and (kind(port).startswith((primitive, JOIN)))  # noqa: E731
                                                or port.endswith(".EVAL") and kind(port).startswith(CONDITION))
        entry = list(dict.fromkeys(d for s_, d in connections if begins(d) and not s_.startswith(prefix + ".")))

        def onward(instance: str) -> list[str]:
            return [d for out in ONWARD for d in targets.get(instance + out, [])]

        def reaches(port: str, ends: set[str]) -> str | None:
            """The port of ``ends`` the success edges from ``port`` lead to."""
            seen, todo = set(), [port]
            while todo:
                at_ = todo.pop()
                if at_ in ends:
                    return at_
                instance = at_.rpartition(".")[0]
                if instance in seen or not inside(at_):
                    continue
                seen.add(instance)
                todo += onward(instance)
            return None

        def condition(c: str, yes: set[str], no: set[str]) -> dict:
            """The condition evaluated by the block ``c``: YES leads into ``yes``, NO into ``no``."""
            ys, ns = set(targets.get(f"{c}.YES", [])), set(targets.get(f"{c}.NO", []))
            leaf = {"operand": operand(c), "op": literal(value(f"{c}.Operator")) or "eq", "value": literal(value(f"{c}.Expected"))}
            def nxt(found: set[str]) -> str:
                instances = {port.rpartition(".")[0] for port in found}
                if len(instances) != 1 or not all(port.endswith(".EVAL") for port in found):
                    raise ValueError(f"{c}: its outcomes do not lead to one condition")
                return instances.pop()

            if not ys or not ns:
                raise ValueError(f"{c}: an outcome leads nowhere")
            if ys <= yes and ns <= no:
                return leaf
            if ns <= no:
                return canonical({"all": [leaf, condition(nxt(ys), yes, no)]})
            if ys <= yes:
                return canonical({"any": [leaf, condition(nxt(ns), yes, no)]})
            # Both go to other conditions: a group inside a group of the other kind.
            try:
                return canonical({"any": [condition(c, yes, ns), condition(nxt(ns), yes, no)]})
            except ValueError:
                return canonical({"all": [condition(c, ys, no), condition(nxt(ys), yes, no)]})

        def operand(c: str) -> str:
            source = driven.get(f"{c}.Operand") or ""
            parts = source.split(".")
            return f"{parts[-2]}.{parts[-1][len('R_'):]}" if parts[-1].startswith("R_") else parts[-2]

        def lane(starts: list[str], ends: set[str]) -> list[dict]:
            nodes: list[dict] = []
            while starts and not set(starts) <= ends:
                joins = [p_ for p_ in starts if kind(p_).startswith(JOIN) and p_.endswith(".START")]
                if joins:
                    join = joins[0].rpartition(".")[0]
                    done = {f"{join}.DONE_{i}" for i in range(1, int(kind(joins[0])[len(JOIN):]) + 1)}
                    groups: dict[str, list[str]] = {}
                    for p_ in starts:
                        if p_ != joins[0]:
                            groups.setdefault(reaches(p_, done), []).append(p_)
                    if None in groups:
                        raise ValueError(f"{join}: a branch does not end in it")
                    branches = [lane(groups[d], {d}) for d in sorted(groups, key=lambda d: int(d.rpartition("_")[2]))]
                    nodes.append({"kind": "parallel", "name": join.rpartition(".")[2], "branches": branches})
                    starts = targets.get(f"{join}.DONE", [])
                elif len(starts) == 1 and kind(starts[0]).startswith(CONDITION):
                    first = starts[0].rpartition(".")[0]
                    merges = [i for i in fbs if i.startswith(prefix + ".") and fbs[i] == MERGE
                              and i.rpartition(".")[2] == first.rpartition(".")[2].rpartition("_C")[0]]
                    if not merges:
                        raise ValueError(f"{first}: no SKILL_Merge where its branches meet")
                    meet = merges[0]
                    one, two = f"{meet}.EI1", f"{meet}.EI2"
                    # The ports the conditions lead to: a branch's start, or the merge itself.
                    conds = [i for i in fbs if i.startswith(f"{meet}_C") and fbs[i].startswith(CONDITION)]
                    outs = {d for c in conds for d in targets.get(f"{c}.YES", []) + targets.get(f"{c}.NO", [])
                            if not d.rpartition(".")[0] in conds}
                    yes = {d for d in outs if reaches(d, {one, two}) == one}
                    no = outs - yes
                    nodes.append({"kind": "decision", "name": meet.rpartition(".")[2], "condition": condition(first, yes, no),
                                  "then": lane(sorted(yes), {one}), "otherwise": lane(sorted(no - {two}), {two})})
                    starts = targets.get(f"{meet}.EO", [])
                elif len(starts) == 1 and kind(starts[0]).startswith(primitive):
                    name = starts[0].rpartition(".")[0]
                    nodes.append(step(name))
                    starts = targets.get(f"{name}.SUCCESS", [])
                else:
                    break
                starts = [p_ for p_ in starts if begins(p_) or p_ in ends]
            return nodes

        return lane(entry, set())

    def steps(prefix: str) -> list[dict]:
        """The steps of the sequence ``prefix``, in the order their SUCCESS starts the next; a flow
        with parallel blocks or decisions (rule set 2) is read by ``flow``."""
        if any(n.startswith(prefix + ".") and t.startswith((JOIN, CONDITION, MERGE)) for n, t in fbs.items()):
            return flow(prefix)
        depth = prefix.count(".") + 1
        names = [n for n, t in fbs.items() if n.startswith(prefix + ".") and n.count(".") == depth and t.startswith(primitive)]
        follows = {s[:-len(".SUCCESS")]: d[:-len(".START")] for s, d in connections
                   if s.endswith(".SUCCESS") and d.endswith(".START") and s in {n + ".SUCCESS" for n in names}}
        found = [n for n in names if n not in follows.values()][:1]
        while found and found[-1] in follows:
            found.append(follows[found[-1]])
        return [step(name) for name in found]

    composites = {}
    for name in [n for n in order if fbs.get(f"{n}.Control") == CORE]:
        # Rule 3: the Start method hands argument k + 1 to the latch of parameter k.
        latches = sorted((int(s.rpartition("_")[2]), d.split(".")[-2]) for s, d in connections
                         if s.startswith(f"{name}.UaStart.RD_") and d.endswith(".Requested"))
        parameters = {p: declared(fbs[f"{name}.{p}"][len(LATCH):], value(f"{name}.{p}.Default"),
                                  value(f"{name}.{p}.Lower"), value(f"{name}.{p}.Upper")) for _, p in latches}
        # The results are published in the order the ID names them.
        published = [path.rpartition("/")[2] for path in (literal(value(f"{name}.PubResults.ID")) or "").strip("]").split(";")[1:]]
        results = {published[int(d.rpartition("_")[2]) - 1]: ".".join(s.split(".")[-2:]).replace(".R_", ".")
                   for s, d in connections if d.startswith(f"{name}.PubResults.SD_")}
        composites[name] = {"offered": literal(value(f"{name}.Control.Methods")) is True, "parameters": parameters,
                            "execute": steps(f"{name}.Execute"), "stop": steps(f"{name}.Stop"),
                            "results": {r: results[r] for r in published}}

    offered = [n for n in order if fbs.get(n) == f"{primitive}{n}"]
    return {
        "module": literal(value("Occupation.Module")), "package": package,
        "opcua_root": literal(value("Occupation.UaRoot")),
        "equipment": [n for n in order if fbs.get(n) == f"{package}::EQ_{n}"],
        "skills": {n: {"offered": n in offered, **{k: v for k, v in p.items() if k != "package"}}
                   for n, p in primitives.items() if p["package"] == package},
        "composites": composites,
        "procedures": {n: steps(n) for n in order if n in PROCEDURES and n not in composites},
    }


def canonical(condition: dict) -> dict:
    """A condition with every group of one element replaced by it and every group inside a group of
    its own kind merged into it, so two that hold alike compare equal."""
    for kind in ("all", "any"):
        if kind in condition:
            parts = []
            for part in (canonical(c) for c in condition[kind]):
                parts += part[kind] if kind in part else [part]
            return parts[0] if len(parts) == 1 else {kind: parts}
    return condition


def walk(nodes: list[dict]):
    """The steps of a flow as ``structure`` holds it, in the order they are written."""
    for node in nodes:
        if node.get("kind") == "parallel":
            for branch in node["branches"]:
                yield from walk(branch)
        elif node.get("kind") == "decision":
            yield from walk(node["then"])
            yield from walk(node["otherwise"])
        else:
            yield node


def shape(nodes: list[dict]) -> list:
    """A flow without the values its steps are handed: what is the same when only values differ."""
    found = []
    for node in nodes:
        if node.get("kind") == "parallel":
            found.append(("parallel", node["name"], [shape(b) for b in node["branches"]]))
        elif node.get("kind") == "decision":
            found.append(("decision", node["name"], node["condition"], shape(node["then"]), shape(node["otherwise"])))
        else:
            found.append((node["skill"], node["name"]))
    return found


def driven_by(connections, source: str, ending: str = "") -> str | None:
    """The destination ``source`` is connected to (the one with ``ending``)."""
    return next((d for s, d in connections if s == source and d.endswith(ending)), None)


def stated(spec: ModuleSpec) -> dict:
    """The structure a module spec states, as ``structure`` reads it from the program it generates."""
    def parameters(declared_: dict[str, Parameter]) -> dict:
        return {n: declared(p.type, p.literal(), None if p.minimum is None else p.literal(p.minimum),
                            None if p.maximum is None else p.literal(p.maximum)) for n, p in declared_.items()}

    def condition(c) -> dict:
        if isinstance(c, (AllOf, AnyOf)):
            kind = "all" if isinstance(c, AllOf) else "any"
            return canonical({kind: [condition(inner) for inner in getattr(c, kind)]})
        return {"operand": c.operand, "op": c.op, "value": literal(str(c.value).upper()) if isinstance(c.value, bool)
                else literal(repr(float(c.value)))}

    def steps(sequence) -> list[dict]:
        result = []
        for node in sequence:
            if isinstance(node, Parallel):
                result.append({"kind": "parallel", "name": node.name, "branches": [steps(b) for b in node.branches]})
                continue
            if isinstance(node, Decision):
                result.append({"kind": "decision", "name": node.name, "condition": condition(node.condition),
                               "then": steps(node.then), "otherwise": steps(node.otherwise)})
                continue
            typ = spec.skills[node.skill].parameters
            result.append({"skill": node.skill, "name": node.name, "bind": {
                p: node.bind[p] if isinstance(node.bind.get(p), str) else literal(decl.literal(node.bind.get(p)))
                for p, decl in typ.items()}})
        return result

    return {
        "module": spec.module, "package": spec.package, "opcua_root": spec.opcua_root,
        "equipment": list(spec.equipment),
        "skills": {n: {"offered": s.offered, "equipment": s.equipment, "parameters": parameters(s.parameters),
                       "results": list(s.results),
                       "timeout": literal(tlit(s.timeout))[1] if s.ensures is not None else None}
                   for n, s in spec.skills.items()},
        "composites": {n: {"offered": c.offered, "parameters": parameters(c.parameters), "execute": steps(c.execute),
                           "stop": steps(c.stop), "results": dict(c.results)} for n, c in spec.composites.items()},
        "procedures": {n: steps(s) for n, s in spec.procedures.items()},
    }
