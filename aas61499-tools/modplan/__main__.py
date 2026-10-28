"""python -m modplan: plan new module level skills from a module's AAS, and check the ones it has.

    modplan domain aas/                                    # what the planner reads: capabilities, constraints, rest
    modplan check aas/ [--skill Dispensing]                # run each module level skill through the states
    modplan discover aas/                                  # what the module can carry out, skill or no skill
    modplan plan aas/ --capability Filling --value FillVolume=2.0 [--result FillWeight] [--name PlannedFilling] [--write]
    modplan export aas/ --capability Filling --value FillVolume=2.0 [--result FillWeight] --as hddl --out planning/

``aas`` is a folder of AAS files or an AAS server (http://<host>:8081), as for modsync; ``--shell``
names the module when it holds several. ``plan --write`` describes the planned skill in the module's
AAS where it came from (not built: ``modsync reconfigure`` builds it). ``export`` writes the same
problem for a standard planner: ``domain.pddl`` and ``problem.pddl`` (PDDL 2.1 with numbers), or
``domain.hddl`` and ``problem.hddl``.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from modsync.described import NotDescribed, described
from modsync.sources import load, store

from .check import check
from .compose import compose
from .discover import discover
from .domain import Domain
from .export import NotExpressible, hddl, pddl
from .lift import flow
from .plan import NoPlan, plan
from .read import read


def value(text: str):
    name, _, given = text.partition("=")
    if given.lower() in ("true", "false"):
        return name, given.lower() == "true"
    try:
        return name, float(given)
    except ValueError:
        return name, given


def show_domain(domain: Domain) -> None:
    print(f"{domain.module}: at rest {', '.join(f'{v} = {x}' for v, x in domain.rest.items())}")
    for cap in domain.capabilities.values():
        where = f"{cap.component}, by {cap.skill}" if cap.action else f"offered, by {cap.skill or 'no skill yet'}"
        print(f"  {cap.name} ({where})")
        for kind, constraints in (("Pre", cap.pre), ("Post", cap.post), ("Invariant", cap.invariant)):
            for c in constraints:
                print(f"    {kind:9} {c.var} {c.expression}")
        for name, p in cap.parameters.items():
            print(f"    given     {name} {p.minimum} to {p.maximum}" + (f", default {p.default}" if p.default is not None else ""))
        for name, x in cap.values.items():
            print(f"    value     {name} = {x}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("domain", "check", "discover", "plan", "export"):
        p = sub.add_parser(name)
        p.add_argument("aas", help="A folder of AAS files, or an AAS server (http://<host>:8081)")
        p.add_argument("--shell", help="The module's AAS (idShort), when there are several")
        if name == "check":
            p.add_argument("--skill", help="Only this module level skill")
        if name in ("plan", "export"):
            p.add_argument("--capability", required=True, help="The capability to carry out (Filling)")
            p.add_argument("--value", action="append", default=[], type=value, help="A property's value, e.g. FillVolume=2.0")
            p.add_argument("--result", action="append", default=[], help="A result asked for, e.g. FillWeight")
        if name == "plan":
            p.add_argument("--name", help="The new skill's name (default Planned<capability>)")
            p.add_argument("--write", action="store_true", help="Describe the skill in the module's AAS where it came from")
        if name == "export":
            p.add_argument("--as", dest="language", choices=("pddl", "hddl"), default="pddl")
            p.add_argument("--out", default=".", help="The folder to write the domain and the problem to")
    args = parser.parse_args(argv)
    try:
        module, components = load(args.aas, args.shell)
        domain = read(module, components)
        if args.command == "domain":
            show_domain(domain)
        elif args.command == "check":
            skills = described(module, components).composites
            found_any = False
            for name, skill in skills.items():
                if args.skill and name != args.skill:
                    continue
                found = check(domain, skill)
                found_any |= bool(found)
                print(f"{name}: " + ("nothing that does not hold" if not found else f"{len(found)} findings"))
                for finding in found:
                    print(f"  {finding}")
            return 1 if found_any else 0
        elif args.command == "discover":
            for d in discover(domain):
                ranges = ", ".join(f"{k} {lo} to {hi}" for k, (lo, hi) in d.ranges.items())
                print(f"{d.capability}" + (f" ({ranges})" if ranges else "") + ": " + " -> ".join(
                    domain.capabilities[s.capability].skill for s in d.steps))
        elif args.command == "export":
            write = pddl if args.language == "pddl" else hddl
            texts = write(domain, args.capability, dict(args.value), tuple(args.result))
            out = Path(args.out)
            out.mkdir(parents=True, exist_ok=True)
            for kind, text in zip(("domain", "problem"), texts):
                (out / f"{kind}.{args.language}").write_text(text, encoding="utf-8")
                print(out / f"{kind}.{args.language}")
        else:
            values = dict(args.value)
            steps = plan(domain, args.capability, values, tuple(args.result))
            for step in steps:
                cap = domain.capabilities[step.capability]
                print(f"  {cap.skill}({', '.join(f'{k}={v}' for k, v in step.args.items())})  [{cap.name} of {cap.component}]")
            print(f"  as a flow: {flow(domain, steps)}")
            if args.write:
                composed = compose(module, components, args.capability, values, tuple(args.result), args.name)
                print(f"{composed.name} described: {store(args.aas, composed.module, module)}")
    except (NoPlan, NotDescribed, NotExpressible, ValueError) as e:
        print(f"modplan: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
