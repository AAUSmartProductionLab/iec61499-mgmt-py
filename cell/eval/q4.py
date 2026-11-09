"""Q4 of docs/cirp-evaluation.md: are the skills right for the product? The method's check on every
single mutant of three skills (Q4a), and its matching and planning on products and module variants
(Q4b), both against the process model of the filling station (cell/eval/process_model.py), which
knows none of the AAS's capability conditions.

    python cell/eval/q4.py            # writes cell/eval/results/q4-<when>.jsonl
    python cell/eval/q4.py --only a   # Q4a only (or b, or t)

No FORTE: the check and the match come before anything is built.

Since 6 Nov (the time model, vocabulary 0.10) the method knows what the product states: its container's
geometry (inner diameter, inner bottom and rim above the face it stands on in the nest) and, for one
filled from the bottom, the least immersion of the needle (2 mm above the liquid, as O5 says the
product needs). A skill is checked in time from that state, against the requirement (BottomUpFilling
keeps the needle no more than 2 mm above the liquid), and the module's nest is where its spec says (70
mm down the stroke, 75 on the raised station). The oracle is unchanged and knows none of it.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import platform
import statistics
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(Path(__file__).resolve().parent), str(ROOT / "aas61499-tools" / "tests")]
import scenarios as sc                                                       # noqa: E402
from modgen.spec import Composite, ModuleSpec, Parallel, Step               # noqa: E402
from modplan.check import check, simulate                                    # noqa: E402
from modplan.compose import planned, requiring                               # noqa: E402
from modplan.domain import PRODUCT, Var                                      # noqa: E402
from modplan.lift import composite as lifted                                 # noqa: E402
from modplan.plan import NoPlan, start_state                                 # noqa: E402
from modplan.read import read                                                # noqa: E402
from modreg.match import LAB, Capability, Property, evaluate, offered        # noqa: E402
from modreg.offer import capabilities, described_skill                       # noqa: E402
from modsync.described import described                                      # noqa: E402
from process_model import CONTAINERS, HOME_HEIGHT, NEST, Hardware, Product, run  # noqa: E402
from test_modsync import DOUBLE_DOSE                                         # noqa: E402
from test_modsync_desired import aas                                         # noqa: E402

CONTENT, WEIGHED = Var(PRODUCT, "ContentVolume"), Var(PRODUCT, "Weighed")
RESULTS = sc.RESULTS

# Q4a: the skills and the products they are written for (volume given to the skill's parameter).
SKILLS = {
    "Dispensing": ("Volume", Product("vial 2R", 1.0)),
    "DoubleDose": ("Dose", Product("vial 2R", 1.0)),        # two doses of 0.5 mL
    "BottomUpFilling": ("Volume", Product("syringe 1 mL", 1.0)),
}
GIVEN = {"Dispensing": {"Volume": 1.0}, "DoubleDose": {"Dose": 0.5}, "BottomUpFilling": {"Volume": 1.0}}
INSERTED = [("Home", {}), ("Tare", {}), ("Weigh", {}), ("MoveAxis", {"Position": 0.0}), ("MoveAxis", {"Position": 20.0}),
            ("MoveAxis", {"Position": 40.0}), ("MoveAxis", {"Position": 58.0}),
            ("Dispense", {"Volume": 1.0, "FlowRate": 1.0})]
EQUIPMENT = {"Home": "LinearAxis", "MoveAxis": "LinearAxis", "Dispense": "Pump", "Tare": "Scale", "Weigh": "Scale"}

# Q4b.
VOLUMES = {"vial 2R": (0.25, 0.5, 1.0, 2.0), "vial 10R": (2.0, 5.0, 10.0), "vial 20R": (15.0, 20.0, 25.0),
           "syringe 1 mL": (0.25, 0.5, 1.0)}
GRASP = {"vial 2R": 16.0, "vial 10R": 24.0, "vial 20R": 30.0, "syringe 1 mL": 8.15}   # outer diameter, mm
VARIANTS = ("full", "no scale", "small pump", "raised")
NEST_FACE = HOME_HEIGHT - NEST                            # mm down the stroke: the face a container stands on


def facts(product: Product) -> dict[str, float]:
    """What the product states of its container and, filled from the bottom, of how deep the needle may
    be (vocabulary 0.10): the geometry as heights above the nest's face, the least immersion O5's."""
    c = CONTAINERS[product.container]
    found = {"FillVolume": product.volume, "InnerDiameter": c.diameter, "InnerBottomHeight": round(NEST_FACE - c.bottom, 6),
             "RimHeight": round(NEST_FACE - c.rim, 6)}
    return {**found, "MinImmersion": -2.0} if c.from_bottom else found


def meaning_of(product: Product) -> str:
    return "BottomUpFilling" if CONTAINERS[product.container].from_bottom else "Filling"


def against(domain, product: Product) -> tuple:
    """The domain with the product's required capability, and how a skill is checked against it."""
    meaning, values = meaning_of(product), facts(product)
    domain = requiring(domain, meaning)
    return domain, {"start": start_state(domain, meaning, values), "task": domain.capabilities[meaning], "values": values}
RATES = [round(0.1 * i, 1) for i in range(1, 51)]         # the witness's flow rates for filling from the bottom


# The skills -----------------------------------------------------------------------------------------

def raw_spec() -> dict:
    return yaml.safe_load(sc.FILLING.read_text(encoding="utf-8"))


def originals() -> dict[str, Composite]:
    spec = ModuleSpec.model_validate(raw_spec())
    return {"Dispensing": spec.composites["Dispensing"], "DoubleDose": Composite(**DOUBLE_DOSE),
            "BottomUpFilling": sc.BOTTOM_UP}


def dump(skill: Composite) -> dict:
    return skill.model_dump(mode="json", exclude_none=True)


def canonical(nodes) -> tuple:
    """A flow without its step names: what it does."""
    out = []
    for n in nodes:
        if isinstance(n, Step):
            out.append((n.skill, tuple(sorted(n.bind.items()))))
        elif isinstance(n, Parallel):
            out.append(("parallel", tuple(canonical(b) for b in n.branches)))
    return tuple(out)


def names(nodes) -> set[str]:
    found = set()
    for n in nodes:
        found.add(n.name)
        if isinstance(n, Parallel):
            for b in n.branches:
                found |= names(b)
    return found


def sequences(nodes, path=()):
    """Every sequence of the flow: (path, list); a path is (index of the block, branch) pairs."""
    yield path, nodes
    for i, n in enumerate(nodes):
        if isinstance(n, Parallel):
            for b, branch in enumerate(n.branches):
                yield from sequences(branch, path + ((i, b),))


def at_path(execute: list, path: tuple) -> list:
    seq = execute
    for i, b in path:
        seq = seq[i].branches[b]
    return seq


def unique(name: str, taken: set[str]) -> str:
    k, new = 2, name
    while new in taken:
        new, k = f"{name}_{k}", k + 1
    taken.add(new)
    return new


def tidy(execute: list) -> list:
    """A parallel block left with one branch becomes that branch; an empty branch goes."""
    out = []
    for n in execute:
        if isinstance(n, Parallel):
            branches = [tidy(b) for b in n.branches if b]
            if len(branches) >= 2:
                out.append(n.model_copy(update={"branches": branches}))
            elif branches:
                out.extend(branches[0])
        else:
            out.append(n)
    return out


def limits(spec: dict) -> dict[tuple[str, str], tuple[float, float]]:
    return {(skill, p): (q["minimum"], q["maximum"]) for skill, s in spec["skills"].items()
            for p, q in (s.get("parameters") or {}).items() if "minimum" in q}


def mutants(skill: Composite, spec: dict):
    """(operator, the mutated step, what was done, the mutant) for every single mutant of ``skill``."""
    lim = limits(spec)

    def variant(change) -> Composite | None:
        execute = copy.deepcopy(skill.execute)
        taken = names(execute)
        if change(execute, taken) is False:
            return None
        return skill.model_copy(update={"execute": tidy(execute)}, deep=True)

    for path, seq in list(sequences(skill.execute)):
        for i, node in enumerate(seq):
            if isinstance(node, Step):
                yield "M1 delete", node.name, f"delete {node.name}", variant(lambda e, t, i=i: at_path(e, path).pop(i) and None)
                yield "M3 duplicate", node.name, f"repeat {node.name}", variant(
                    lambda e, t, i=i: at_path(e, path).insert(i + 1, at_path(e, path)[i].model_copy(
                        update={"name": unique(at_path(e, path)[i].name, t)})))
                for p, v in node.bind.items():
                    if isinstance(v, str) or (node.skill, p) not in lim:
                        continue
                    low, high = lim[(node.skill, p)]
                    span = high - low
                    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
                        new = round(low + frac * span, 3)
                        if new != v:
                            yield "M5 value", node.name, f"{node.name}.{p} = {new}", variant(
                                lambda e, t, i=i, p=p, new=new: at_path(e, path)[i].bind.__setitem__(p, new))
                    for new in (round(low - 0.1 * span, 3), round(high + 0.1 * span, 3)):
                        yield "M6 beyond", node.name, f"{node.name}.{p} = {new}", variant(
                            lambda e, t, i=i, p=p, new=new: at_path(e, path)[i].bind.__setitem__(p, new))
            if i + 1 < len(seq):
                a, b = seq[i], seq[i + 1]
                yield "M2 swap", a.name, f"swap {a.name} and {b.name}", variant(
                    lambda e, t, i=i: at_path(e, path).__setitem__(slice(i, i + 2), at_path(e, path)[i:i + 2][::-1]))
                if not path and isinstance(a, Step) and isinstance(b, Step):
                    yield "M7 parallel", a.name, f"{a.name} and {b.name} at once", variant(
                        lambda e, t, i=i: at_path(e, path).__setitem__(slice(i, i + 2), [Parallel(
                            name=unique("Both", t), branches=[[at_path(e, path)[i]], [at_path(e, path)[i + 1]]])]))
        for i in range(len(seq) + 1):
            for prim, bind in INSERTED:
                what = prim + (f"({', '.join(f'{k}={v}' for k, v in bind.items())})" if bind else "")
                yield "M4 insert", None, f"insert {what} at {i}" + (f" of branch {path}" if path else ""), variant(
                    lambda e, t, i=i, prim=prim, bind=bind: at_path(e, path).insert(
                        i, Step(skill=prim, name=unique(f"Ins{prim}", t), bind=dict(bind))))


# The method's check and the baselines -----------------------------------------------------------------

def spec_takes(spec: dict, name: str, skill: Composite) -> str | None:
    """None if the module spec takes ``skill``, else why not."""
    try:
        ModuleSpec.model_validate({**spec, "composites": {**spec["composites"], name: dump(skill)}})
        return None
    except Exception as e:                                     # a ValueError inside pydantic's
        text = str(e).split("\n")
        return next((line.strip() for line in text if "Value error" in line), text[0])[:300]


def method_check(spec: dict, domain, name: str, skill: Composite, product: Product, given: dict) -> list[str]:
    """The method's check: the spec, the capabilities' conditions, what the flow leaves against what
    the product requires. Each line a finding."""
    found = []
    refused = spec_takes(spec, name, skill)
    if refused:
        found.append(f"spec: {refused}")
    domain, how = against(domain, product)
    found += [f"check: {f}" for f in check(domain, skill, given, **how)]
    state = simulate(domain, skill, given, how["start"])
    content = state.get(CONTENT)
    if not isinstance(content, (int, float)) or abs(content - product.volume) > product.tolerance:
        found.append(f"match: leaves {content} mL, {product.volume} required")
    if product.weight and (state.get(WEIGHED) is not True or not skill.results):
        found.append("match: gives no weight after the last dose")
    return found


def structure_check(spec: dict, skill: Composite) -> list[str]:
    """What the 4diac IDE checks: the types exist, the connections join existing pins (a result of a
    step that is gone has no source)."""
    found, steps = [], {}

    def walk(nodes):
        for n in nodes:
            if isinstance(n, Step):
                steps[n.name] = n
                if n.skill not in spec["skills"]:
                    found.append(f"{n.name}: no type {n.skill}")
                for p in n.bind:
                    if p not in (spec["skills"].get(n.skill, {}).get("parameters") or {}):
                        found.append(f"{n.name}: no pin {p}")
            elif isinstance(n, Parallel):
                for b in n.branches:
                    walk(b)
    walk(skill.execute)
    for result, source in skill.results.items():
        if source.split(".")[0] not in steps:
            found.append(f"result {result}: no step {source.split('.')[0]}")
    return found


def rules_check(spec: dict, skill: Composite, given: dict) -> list[str]:
    """Hand-written sequence rules R1 to R6 (docs/cirp-evaluation.md, Q4a), as a tool expert writes them
    for a workflow engine, on top of the structure."""
    found = structure_check(spec, skill)
    lim = limits(spec)
    pos, dispensed, weighed_after = 0.0, False, False

    def arg(step, p, default):
        v = step.bind.get(p, default)
        return given.get(v) if isinstance(v, str) else v

    def visit(step: Step, before: float, in_parallel: bool) -> float:
        nonlocal dispensed, weighed_after
        for p, v in step.bind.items():                                     # R4
            v = given.get(v) if isinstance(v, str) else v
            if (step.skill, p) in lim and v is not None and not lim[(step.skill, p)][0] <= v <= lim[(step.skill, p)][1]:
                found.append(f"R4 {step.name}: {p} = {v} beyond its limits")
        if step.skill == "Dispense":
            if before < 40.0:                                              # R1
                found.append(f"R1 {step.name}: dispensing with the needle at {before} mm")
            dispensed, weighed_after = True, False
        if step.skill == "Weigh":
            if before != 0.0 or in_parallel:                               # R2
                found.append(f"R2 {step.name}: weighing with the needle at {before} mm or in a parallel block")
            weighed_after = weighed_after or dispensed
        if step.skill == "Home":
            return 0.0
        if step.skill == "MoveAxis":
            return arg(step, "Position", 0.0)
        return before

    for node in skill.execute:
        if isinstance(node, Step):
            pos = visit(node, pos, False)
        elif isinstance(node, Parallel):
            items = [{EQUIPMENT.get(s.skill) for s in b if isinstance(s, Step)} for b in node.branches]
            for a in range(len(items)):                                    # R5
                for b in range(a + 1, len(items)):
                    if items[a] & items[b]:
                        found.append(f"R5 {node.name}: two branches on {sorted(items[a] & items[b])}")
            ends = []
            for branch in node.branches:
                p = pos
                for s in branch:
                    if isinstance(s, Step):
                        p = visit(s, pos if s is branch[0] else p, True)
                ends.append(p)
            moved = [e for e, b in zip(ends, node.branches) if any(isinstance(s, Step) and s.skill in ("Home", "MoveAxis") for s in b)]
            pos = moved[-1] if moved else pos
    if pos != 0.0:                                                         # R3
        found.append(f"R3: ends with the needle at {pos} mm")
    if not dispensed:                                                      # R6
        found.append("R6: no Dispense")
    if skill.results and not weighed_after:
        found.append("R6: no Weigh after the last Dispense")
    return found


def q4a(spec: dict, domain) -> list[dict]:
    rows = []
    for name, skill in originals().items():
        param, product = SKILLS[name]
        given = GIVEN[name]
        seen = {canonical(skill.execute)}
        base = run(skill, product, Hardware(), given)
        assert base.right, f"{name} itself is not right in the oracle: {base.broken}"
        assert not method_check(spec, domain, name, skill, product, given), f"{name} itself is rejected"
        for operator, step, what, mutant in mutants(skill, spec):
            if mutant is None or not mutant.execute:
                continue
            key = canonical(mutant.execute)
            if key in seen:
                continue
            seen.add(key)
            t = time.perf_counter()
            found = method_check(spec, domain, f"{name}M", mutant, product, given)
            seconds = time.perf_counter() - t
            truth = run(mutant, product, Hardware(), given)
            rows.append({"part": "a", "skill": name, "product": product.container, "operator": operator, "mutated": step,
                         "what": what, "flow": dump(mutant)["execute"], "wrong": not truth.right, "oracle": truth.broken,
                         "content": truth.content, "method": found, "check_s": seconds,
                         "named": bool(step) and any(f.split(": ", 2)[1].startswith(step) for f in found
                                                     if f.startswith("check: ")),
                         "structure": structure_check(spec, mutant), "rules": rules_check(spec, mutant, given)})
    return rows


# Q4b ------------------------------------------------------------------------------------------------

def variant_spec(variant: str) -> tuple[dict, Composite, Hardware]:
    """The module spec of a variant, its BottomUpFilling (described, not built) and its hardware."""
    spec = raw_spec()
    bottom = dump(sc.BOTTOM_UP)
    disp = spec["composites"]["Dispensing"]
    if variant == "no scale":
        del spec["equipment"]["Scale"], spec["skills"]["Tare"], spec["skills"]["Weigh"]
        disp["execute"] = [s for s in disp["execute"] if s != "Weigh"]
        disp.pop("results", None)
        spec["procedures"]["Resetting"] = ["Home"]
        bottom["execute"] = [s for s in bottom["execute"] if not (isinstance(s, dict) and s.get("skill") == "Weigh")]
        bottom["results"] = {}
        hw = Hardware(scale=False)
    elif variant == "small pump":
        spec["skills"]["Dispense"]["parameters"]["Volume"]["maximum"] = 5.0
        disp["parameters"]["Volume"]["maximum"] = 5.0
        bottom["parameters"]["Volume"]["maximum"] = 5.0
        hw = Hardware(dose=(0.5, 5.0))
    elif variant == "raised":
        spec["skills"]["Dispense"]["capability"]["values"]["FillPosition"]["value"] = 45.0
        for skill in ("Dispense", "MoveAxis"):                 # the nest's face 5 mm further down the stroke
            spec["skills"][skill]["capability"]["values"]["NestPosition"]["value"] = NEST_FACE + 5.0
        disp["execute"][0]["MoveAxis"]["Position"] = 45.0
        for s in bottom["execute"]:
            if isinstance(s, dict) and s.get("name") == "NeedleDeep":
                s["bind"]["Position"] = 60.0
            if isinstance(s, dict) and "branches" in s:
                s["branches"][1][0]["bind"]["Position"] = 45.0
        hw = Hardware(lowered=5.0)
    else:
        hw = Hardware()
    return spec, Composite(**bottom), hw


def requirement(product: Product) -> Capability:
    """The capability the product requires, as its AAS states it: the filling its container takes,
    with its volume, container type and grasp diameter, each of its meaning, unit and type."""
    def prop(name: str, value, unit: str = "", value_type: str = "xs:double") -> Property:
        return Property(name, f"{LAB}{name}", unit, value_type, value=str(value))
    kind = "syringe" if product.container.startswith("syringe") else "vial"
    return Capability(meaning_of(product), [f"{LAB}{meaning_of(product)}"], role="Required", properties=[
        prop("FillVolume", product.volume, "mL"), prop("ContainerType", kind, value_type="xs:string"),
        prop("GraspDiameter", GRASP[product.container], "mm")])


def gives_weight(composites: dict, skill: str) -> bool:
    c = composites.get(skill)
    return c is not None and any(v.endswith(".Weight") for v in c.results.values())


def keeps(domain, composites: dict, skill: str, product: Product) -> list[str]:
    """What a skill that matches does not keep of the requirement, run in time from the product's
    state (Match and plan's check of a skill whose capability states constraints)."""
    if skill not in composites:
        return []
    found_domain, how = against(domain, product)
    given = {name: product.volume for name in list(composites[skill].parameters)[:1]}
    return [str(f) for f in check(found_domain, composites[skill], given, **how)]


def answer(module, components, domain, product: Product) -> dict:
    """The method's answer: offered, after a reconfiguration (a described skill, or a plan), not offered.
    An offered capability whose properties meet the product's (the lab's matcher, modreg.match) has a
    skill of it checked in time against the requirement first (6 Nov)."""
    req = requirement(product)
    composites = described(module, components).composites
    fits, refused = [], {}
    for found in evaluate(req, offered(module)):
        if not found.fits:
            continue
        skills = [r["keys"][-1]["value"] for r in found.capability.realized_by]
        if not product.weight or any(gives_weight(composites, s) for s in skills):
            broken = {s: keeps(domain, composites, s, product) for s in skills}
            if any(not b for b in broken.values()):
                fits.append((found.capability.availability != "Now", skills))
            else:
                refused.update(broken)
    if any(not after for after, _ in fits):
        return {"answer": "offered", "by": [s for after, skills in fits if not after for s in skills]}
    if fits:
        return {"answer": "after", "by": [s for _, skills in fits for s in skills], "route": "described"}
    results = ("FillWeight",) if product.weight else ()
    times, steps, planned_on = [], None, domain
    for _ in range(5):
        t = time.perf_counter()
        try:
            planned_on, steps = planned(domain, req.name, facts(product), results)
        except NoPlan as e:
            return {"answer": "not", "why": f"no plan: {e}"[:200], "plan_s": time.perf_counter() - t,
                    **({"refused": refused} if refused else {})}
        times.append(time.perf_counter() - t)
    return {"answer": "after", "route": "planned", "plan_s": statistics.median(times),
            "plan": [(p.capability, p.args) for p in steps], "along": [[str(a) for a in p.along] for p in steps], "steps": steps, "domain": planned_on,
            **({"refused": refused} if refused else {})}


def witness(product: Product, hw: Hardware) -> list[Composite]:
    """Flows built from the product and the hardware alone, any of which makes it right if the module
    can (the truth's after a reconfiguration)."""
    c = CONTAINERS[product.container].lowered(hw.lowered)
    low, high = hw.dose
    k = max(1, math.ceil(product.volume / high))
    if product.volume / k < low:
        return []                                       # the pump cannot dose so little
    dose = round(product.volume / k, 4)
    tail = (["Home"] + (["Weigh"] if product.weight and hw.scale else []))
    if not c.from_bottom:
        depth = min(c.rim + 5.0, hw.travel[1])
        doses = [{"Dispense": {"Volume": dose, "FlowRate": 1.0}, "as": f"Dose{i + 1}"} for i in range(k)]
        return [Composite(execute=[{"MoveAxis": {"Position": depth}, "as": "In"}, *doses, *tail])]
    flows = []
    start = min(c.bottom - 1.0, hw.travel[1])
    for rate in RATES:
        execute = [{"MoveAxis": {"Position": start}, "as": "Deep"}]
        content = 0.0
        for i in range(k):
            content += dose
            end = max(c.rim + 1.0, min(start, c.surface(content) + 1.0))
            execute.append({"parallel": [[{"Dispense": {"Volume": dose, "FlowRate": rate}, "as": f"Dose{i + 1}"}],
                                         [{"MoveAxis": {"Position": round(end, 2)}, "as": f"Rise{i + 1}"}]],
                            "as": f"Rising{i + 1}"})
        flows.append(Composite(execute=execute + tail))
    return flows


def truth(product: Product, hw: Hardware, built: dict[str, Composite]) -> dict:
    for name, skill in built.items():
        p = next(iter(skill.parameters.values()), None)
        if p is not None and p.minimum <= product.volume <= p.maximum:
            o = run(skill, product, hw, {next(iter(skill.parameters)): product.volume})
            if o.right:
                return {"truth": "offered", "by": name}
    for flow in witness(product, hw):
        o = run(flow, product, hw)
        if o.right:
            return {"truth": "after", "witness": dump(flow)["execute"]}
    return {"truth": "not"}


def q4b() -> list[dict]:
    rows = []
    for variant in VARIANTS:
        spec_data, bottom, hw = variant_spec(variant)
        spec = ModuleSpec.model_validate(spec_data)
        module, components = aas(spec, "pc")
        module = capabilities(described_skill(module, components, "BottomUpFilling", bottom), components)
        domain = read(module, components)
        built = {"Dispensing": spec.composites["Dispensing"]}
        for container, volumes in VOLUMES.items():
            for volume in volumes:
                for weight in (True, False):
                    product = Product(container, volume, weight)
                    got = answer(module, components, domain, product)
                    real = truth(product, hw, built)
                    row = {"part": "b", "variant": variant, "container": container, "volume": volume, "weight": weight,
                           **{k: v for k, v in got.items() if k not in ("steps", "domain")}, **real}
                    if got.get("route") == "planned":
                        skill = lifted(got["domain"], got["steps"], "planned")
                        o = run(skill, product, hw)
                        row["planned_flow"] = dump(skill)["execute"]
                        row["planned_right"], row["planned_broken"] = o.right, o.broken
                    rows.append(row)
    return rows


TRACKED_VOLUMES = (0.5, 0.75, 1.0)
MAX_IMMERSION = 3.0                                       # mm: the needle no deeper in the liquid


def q4t() -> list[dict]:
    """Added 6 Nov, outside the protocol's population: the syringe filled from the bottom with the needle
    kept within 2 mm above and 3 mm below the liquid, so that it has to rise with it (MaxImmersion, which no
    rule of the oracle checks), planned by tracking on each variant (no described skill) and run in the
    oracle; the truth as in Q4b."""
    rows = []
    for variant in VARIANTS:
        spec_data, _, hw = variant_spec(variant)
        spec = ModuleSpec.model_validate(spec_data)
        module, components = aas(spec, "pc")
        domain = read(module, components)
        for volume in TRACKED_VOLUMES:
            for weight in (True, False):
                product = Product("syringe 1 mL", volume, weight)
                values = {**facts(product), "MaxImmersion": MAX_IMMERSION}
                row = {"part": "t", "variant": variant, "container": product.container, "volume": volume, "weight": weight,
                       **truth(product, hw, {})}
                t = time.perf_counter()
                try:
                    planned_on, steps = planned(domain, "BottomUpFilling", values, ("FillWeight",) if weight else ())
                except NoPlan as e:
                    rows.append({**row, "answer": "not", "why": str(e)[:200], "plan_s": time.perf_counter() - t})
                    continue
                row["plan_s"] = time.perf_counter() - t
                skill = lifted(planned_on, steps, "planned")
                o = run(skill, product, hw)
                tracked = next((p for p in steps if p.along), None)
                rows.append({**row, "answer": "after", "planned_flow": dump(skill)["execute"], "planned_right": o.right,
                             "planned_broken": o.broken, "tracked": bool(tracked),
                             "flow_rate": tracked.args.get("FlowRate") if tracked else None,
                             "rise": [a.args for a in tracked.along] if tracked else None})
    return rows


def setup() -> dict:
    commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", "--untracked-files=no",
                                 "aas61499-tools", "iec61499-skill-lib", "cell/eval", "cell/modules"],
                                capture_output=True, text=True).stdout.strip())
    return {"machine": f"{platform.processor()} {platform.system()} {platform.release()}",
            "python": platform.python_version(), "commit": commit[:12], "tools_dirty": dirty}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=("a", "b", "t"))
    a = ap.parse_args()
    when = datetime.now().strftime("%Y-%m-%dT%H%M")
    out = RESULTS / f"q4-{when}.jsonl"
    info = setup()
    rows = []
    if a.only in (None, "a"):
        spec = raw_spec()
        module, components = aas(ModuleSpec.model_validate(spec), "pc")
        rows += q4a(spec, read(module, components))
    if a.only in (None, "b"):
        rows += q4b()
    if a.only in (None, "t"):
        rows += q4t()
    with out.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps({**r, **info}, default=str) + "\n")
    print(out, len(rows), "rows")


if __name__ == "__main__":
    main()
