"""python -m modplan: plan new module level skills from a module's AAS, and check the ones it has.

    modplan domain aas/                                    # what the planner reads: capabilities, constraints, rest
    modplan check aas/ [--skill Dispensing]                # run each module level skill through the states
    modplan discover aas/                                  # what the module can carry out, skill or no skill
    modplan plan aas/ --capability Filling --value FillVolume=2.0 [--result FillWeight] [--name PlannedFilling] [--write]

``aas`` is a folder of AAS files or an AAS server (http://<host>:8081), as for modsync; ``--shell``
names the module when it holds several. ``plan --write`` describes the planned skill in the module's
AAS where it came from (not built: ``modsync reconfigure`` builds it).
"""
from __future__ import annotations

import argparse
import sys

from modsync.described import NotDescribed, described
from modsync.sources import load, store

from .check import check
from .compose import compose
from .discover import discover
from .domain import Domain
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
    for name in ("domain", "check", "discover", "plan"):
        p = sub.add_parser(name)
        p.add_argument("aas", help="A folder of AAS files, or an AAS server (http://<host>:8081)")
        p.add_argument("--shell", help="The module's AAS (idShort), when there are several")
        if name == "check":
            p.add_argument("--skill", help="Only this module level skill")
        if name == "plan":
            p.add_argument("--capability", required=True, help="The capability to carry out (Filling)")
            p.add_argument("--value", action="append", default=[], type=value, help="A property's value, e.g. FillVolume=2.0")
            p.add_argument("--result", action="append", default=[], help="A result asked for, e.g. FillWeight")
            p.add_argument("--name", help="The new skill's name (default Planned<capability>)")
            p.add_argument("--write", action="store_true", help="Describe the skill in the module's AAS where it came from")
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
    except (NoPlan, NotDescribed, ValueError) as e:
        print(f"modplan: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
