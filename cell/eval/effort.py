"""The engineering effort of a reconfiguration, in user inputs: by hand in the 4diac IDE, in the skill
editor on the AAS, and with the skill planner (E1; the protocol in docs/cirp-evaluation.md).

    python cell/eval/effort.py                   # the 4diac counts only (no server needed)
    python cell/eval/effort.py --ui              # and the editor and the planner, driven in a browser

``--ui`` needs an AAS server it may empty (``--repo``, default http://localhost:18081), the skill
service (``modreg serve --basyx <repo>``, ``--service``), the web UI's dev server (``--web``) and Chrome.
Before each task and route the server is emptied and the module's AAS as delivered is posted; the
browser (cell/eval/ui/effort-ui.cjs) makes the change and counts every input; the skill then saved
on the server is read back (modsync) and compared with the task's target, so a count stands only
for a change that was made right.

The 4diac IDE cannot be driven so; its count is what the module rules make of the target (modsync's
fragment, the generator's own pattern), an input per element at the least a person makes:
- a block dragged from the type library: 1 pointer (names left as the IDE gives them);
- a connection drawn: 1 pointer; deleted: a click and Del;
- a value typed on a pin: 1 typed (its characters and Enter as keystrokes); cleared: 1 typed;
- a subapplication made: a frame drawn round its blocks, a right click, New subapplication (3 pointer)
  and its name (1 typed); entered to change what is in it: a double click (1 pointer);
- a skill made like another: the subapplication selected, Ctrl+C, Ctrl+V and renamed, then the
  difference to the target as above; the cheaper of that and building it new is taken.
To the running module: 4diac saves (Ctrl+S) and deploys (a right click on the device, Deploy), a new
boot file and a restart; the AAS routes run ``modsync reconfigure`` (one typed command), online.
"""
from __future__ import annotations

import argparse
import base64
import copy
from datetime import datetime
import itertools
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "aas61499-tools"), str(ROOT / "aas61499-tools" / "tests"), str(Path(__file__).parent)]

import scenarios as sc                                                        # noqa: E402
from modgen.spec import Composite, Parallel, Step                             # noqa: E402
from modplan.compose import compose                                           # noqa: E402
from modreg.offer import described_skill                                      # noqa: E402
from modsync.described import described                                       # noqa: E402
from modsync.desired import fragment                                          # noqa: E402
from modsync.sources import load                                              # noqa: E402

RESULTS = Path(__file__).parent / "results"
UI = Path(__file__).parent / "ui" / "effort-ui.cjs"
WEB = ROOT / "basyx-aas-web-ui" / "aas-web-ui"
SHELL = "FillingModuleAAS"
RECONFIGURE = "python -m modsync reconfigure http://localhost:8081 --shell FillingModuleAAS"

# The tasks: what is changed, the targets ------------------------------------------------------------

DISPENSING = sc.load(sc.FILLING).composites["Dispensing"].model_dump(mode="json", exclude_none=True)


def double_dose() -> dict:
    """Dispensing with a second dose of the same volume after the first, 0.5 mL by default."""
    skill = copy.deepcopy(DISPENSING)
    skill["description"] = "Needle down, two doses, home, weigh"
    skill["parameters"]["Volume"]["default"] = 0.5
    skill["execute"].insert(2, {"Dispense": {"Volume": "Volume", "FlowRate": 1.0}, "as": "Dispense_2"})
    return skill


TASKS = {
    "value": {"title": "A value: Dispensing doses at 2.0 mL/s", "skill": "Dispensing", "routes": ("editor",),
              "compare": ("flow", "results", "parameters")},
    "double": {"title": "A new skill made like one: DoubleDose, two doses", "skill": "DoubleDose", "routes": ("editor",),
               "compare": ("flow", "results", "parameters")},
    "bottomup": {"title": "A new flow: BottomUpFilling, dosing while the needle rises", "skill": "BottomUpFilling",
                 "routes": ("editor",), "compare": ("flow", "results", "parameters")},
    "fifteen": {"title": "A product: 15 mL, weighed", "skill": "Filling15", "routes": ("editor", "planner"),
                "compare": ("flow", "results")},
}


def target(task: str, module: dict, components: list[dict]) -> tuple[dict, str]:
    """The module's AAS with the task's target in it, and the target skill's name."""
    if task == "value":
        return sc.with_value(module), "Dispensing"
    if task == "double":
        return described_skill(module, components, "DoubleDose", Composite(**double_dose())), "DoubleDose"
    if task == "bottomup":
        return described_skill(module, components, "BottomUpFilling", sc.BOTTOM_UP), "BottomUpFilling"
    planned = compose(module, components, "Filling", {"FillVolume": 15.0}, ("FillWeight",), name="Filling15")
    return planned.module, "Filling15"


# Comparing a saved skill with its target ------------------------------------------------------------

def canonical(nodes) -> tuple:
    """A flow without its step names: what each step runs and is handed, and the blocks."""
    out = []
    for n in nodes:
        if isinstance(n, Step):
            out.append((n.skill, tuple(sorted((k, float(v) if isinstance(v, (int, float)) else v) for k, v in n.bind.items()))))
        elif isinstance(n, Parallel):
            out.append(("parallel", tuple(sorted(canonical(b) for b in n.branches))))
    return tuple(out)


def differences(made: Composite, wanted: Composite, compare: tuple[str, ...]) -> list[str]:
    found = []
    if "flow" in compare:
        for flow in ("execute", "stop"):
            if canonical(getattr(made, flow) or []) != canonical(getattr(wanted, flow) or []):
                found.append(f"{flow}: {canonical(getattr(made, flow) or [])} against {canonical(getattr(wanted, flow) or [])}")
    if "results" in compare and sorted((made.results or {}).values()) != sorted((wanted.results or {}).values()):
        found.append(f"results: {made.results} against {wanted.results}")
    if "parameters" in compare:
        def limits(skill):
            return {k: (p.minimum, p.maximum, p.default) for k, p in (skill.parameters or {}).items()}
        if limits(made) != limits(wanted):
            found.append(f"parameters: {limits(made)} against {limits(wanted)}")
    return found


# The 4diac IDE ---------------------------------------------------------------------------------------

def subapps(names) -> set[str]:
    return {".".join(n.split(".")[:i]) for n in names for i in range(1, n.count(".") + 1)}


def program(spec, name: str) -> dict:
    flat, links = fragment(spec, [name], "Tail.INITO")
    return {"fbs": dict(flat.fbs), "links": set(links), "values": dict(flat.parameters)}


def tally(**counts) -> dict:
    out = {"pointer": 0, "typed": 0, "keys": 0, "keystrokes": 0, **counts}
    out["inputs"] = out["pointer"] + out["typed"] + out["keys"]
    return out


def new_in_4diac(made: dict) -> dict:
    """The skill built new: every block, connection, value and subapplication."""
    groups = subapps(made["fbs"])
    chars = sum(len(str(v)) + 1 for v in made["values"].values()) + sum(len(g.split(".")[-1]) + 1 for g in groups)
    return tally(pointer=len(made["fbs"]) + len(made["links"]) + 3 * len(groups), typed=len(made["values"]) + len(groups),
                 keystrokes=chars, route="new", blocks=len(made["fbs"]), connections=len(made["links"]),
                 values=len(made["values"]), subapplications=len(groups))


def renaming(before: dict, mapping: dict[str, str]) -> dict:
    """``before`` with its instances renamed (``mapping``: old name to new; a pin is instance.pin)."""
    def renamed(text: str) -> str:
        instance, _, pin = text.rpartition(".")
        return f"{mapping.get(instance, instance)}.{pin}" if instance else text
    return {"fbs": {mapping.get(k, k): v for k, v in before["fbs"].items()},
            "links": {(renamed(a), renamed(z)) for a, z in before["links"]},
            "values": {renamed(k): v for k, v in before["values"].items()}}


def matchings(before: dict, after: dict):
    """Every way to take a block of ``before`` as one of ``after``: of the same type in the same
    subapplication, each at most once; a block left unmatched is deleted, one of ``after`` unmatched
    is added. The IDE's blocks keep the names they have; the names are only how the two are matched."""
    groups: dict[tuple, tuple[list, list]] = {}
    for side, fbs in ((0, before["fbs"]), (1, after["fbs"])):
        for name, kind in fbs.items():
            groups.setdefault((name.rpartition(".")[0], kind), ([], []))[side].append(name)
    choices = []
    for old, new in groups.values():
        options = []
        if len(old) <= len(new):
            for chosen in itertools.permutations(new, len(old)):
                options.append(dict(zip(old, chosen)))
        else:
            for kept in itertools.permutations(old, len(new)):
                options.append({**dict(zip(kept, new)), **{o: f"{o}#deleted" for o in old if o not in kept}})
        choices.append(options or [{}])
    for picked in itertools.product(*choices):
        yield {k: v for part in picked for k, v in part.items()}


def changed_in_4diac(before: dict, after: dict, copied: str | None = None) -> dict:
    """``before`` made into ``after`` with the fewest inputs: the difference, element by element;
    ``copied``: ``before`` is a copy of the skill of that name, pasted and renamed (its connection into
    the INIT chain is not pasted with it)."""
    name = next(iter(after["fbs"])).split(".")[0]
    if copied:
        before = renaming({**before, "links": {(a, z) for a, z in before["links"] if not a.startswith("Tail.")}},
                          {k: name + k[len(copied):] for k in before["fbs"]})
    return min((difference(renaming(before, mapping), after, name, copied) for mapping in matchings(before, after)),
               key=lambda c: c["inputs"])


def difference(before: dict, after: dict, name: str, copied: str | None) -> dict:
    fbs_added = [k for k, v in after["fbs"].items() if before["fbs"].get(k) != v]
    fbs_removed = [k for k, v in before["fbs"].items() if after["fbs"].get(k) != v]
    # A deleted block takes its connections with it.
    links_added = after["links"] - before["links"]
    links_removed = {link for link in before["links"] - after["links"]
                     if not any(end.rpartition(".")[0] in fbs_removed for end in link)}
    values_set = {k: v for k, v in after["values"].items() if before["values"].get(k) != v}
    values_cleared = [k for k in before["values"] if k not in after["values"] and k.rsplit(".", 1)[0] not in fbs_removed]
    groups_added = subapps(after["fbs"]) - subapps(before["fbs"])
    groups_removed = subapps(before["fbs"]) - subapps(after["fbs"])
    touched = fbs_added + fbs_removed + [k.rsplit(".", 1)[0] for k in [*values_set, *values_cleared]] \
        + [e.rsplit(".", 1)[0] for link in links_added | links_removed for e in link]
    entered = (subapps(t for t in touched if not t.startswith("Tail")) | groups_added) - groups_added
    copy_cost = {"pointer": 1, "keys": 2, "typed": 1, "keystrokes": 2 + len(name) + 1} if copied else {}
    return tally(pointer=len(fbs_added) + len(links_added) + len(fbs_removed) + len(links_removed) + 3 * len(groups_added)
                 + len(groups_removed) + len(entered) + copy_cost.get("pointer", 0),
                 typed=len(values_set) + len(values_cleared) + len(groups_added) + copy_cost.get("typed", 0),
                 keys=len(fbs_removed) + len(links_removed) + len(groups_removed) + copy_cost.get("keys", 0),
                 keystrokes=sum(len(str(v)) + 1 for v in values_set.values()) + len(values_cleared)
                 + sum(len(g.split(".")[-1]) + 1 for g in groups_added) + copy_cost.get("keystrokes", 0)
                 + len(fbs_removed) + len(links_removed) + len(groups_removed),
                 route=f"made like {copied}" if copied else "changed", blocks=len(fbs_added), blocks_removed=len(fbs_removed),
                 connections=len(links_added), connections_removed=len(links_removed), values=len(values_set) + len(values_cleared),
                 subapplications=len(groups_added), entered=len(entered))


def in_4diac(task: str, module: dict, components: list[dict]) -> dict:
    changed, name = target(task, module, components)
    spec_before, spec_after = described(module, components), described(changed, components)
    after = program(spec_after, name)
    built = new_in_4diac(after)
    if task == "value":
        found = changed_in_4diac(program(spec_before, name), after)
    else:
        found = min(built, changed_in_4diac(program(spec_after, "Dispensing"), after, "Dispensing"), key=lambda c: c["inputs"])
    deploy = tally(pointer=2, keys=1, keystrokes=1)
    return {**found, "built_new": built["inputs"], "deploy": deploy}


# The editor and the planner, in a browser -------------------------------------------------------------

def b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


def call(url: str, method: str = "GET", body=None):
    request = urllib.request.Request(url, None if body is None else json.dumps(body).encode(), method=method,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=60) as response:
        text = response.read()
    return json.loads(text) if text else None


def reset(repo: str, module: dict, components: list[dict]) -> None:
    """The server emptied, and the module's AAS as delivered posted."""
    for kind in ("shells", "submodels"):
        for item in call(f"{repo}/{kind}?limit=1000")["result"]:
            call(f"{repo}/{kind}/{b64(item['id'])}", "DELETE")
    for env in [module, *components]:
        for item in env["submodels"]:
            call(f"{repo}/submodels", "POST", item)
        for item in env["assetAdministrationShells"]:
            call(f"{repo}/shells", "POST", item)


def in_browser(task: str, route: str, args, module: dict, components: list[dict], folder: Path) -> dict:
    reset(args.repo, module, components)
    before = set(described(*load(args.repo, SHELL)).composites)
    out = folder / f"{task}-{route}.json"
    env = {**os.environ, "NODE_PATH": str(WEB / "node_modules"), "EFFORT_REPO": args.repo,
           "EFFORT_SERVICE": args.service, "EFFORT_UI": args.web}
    run = subprocess.run(["node", str(UI), task, route, str(out), str(folder)], env=env, capture_output=True, text=True, timeout=600)
    if run.returncode != 0:
        return {"error": (run.stderr or run.stdout)[-1500:]}
    counted = json.loads(out.read_text(encoding="utf-8"))
    loaded, comps = load(args.repo, SHELL)
    made = described(loaded, comps).composites
    name = TASKS[task]["skill"] if task != "fifteen" or route == "editor" else next(iter(set(made) - before), None)
    changed, wanted_name = target(task, module, components)
    wanted = described(changed, components).composites[wanted_name]
    found = differences(made[name], wanted, TASKS[task]["compare"]) if name in made else [f"no skill {name} saved"]
    skills = next(s for s in loaded["submodels"] if s["idShort"] == "Skills")
    element = next((e for e in skills.get("submodelElements") or [] if e.get("idShort") == name), {})
    deployment = next((e.get("value") for e in element.get("value") or [] if e.get("idShort") == "Deployment"), None)
    deploy = tally(typed=1, keystrokes=len(RECONFIGURE) + 1)
    return {**tally(pointer=counted["pointer"], typed=counted["typed"], keys=counted["keys"], keystrokes=counted["keystrokes"]),
            "saved": name, "deployment": deployment, "right": not found, "differences": found, "log": counted["log"],
            "deploy": deploy}


# The report -------------------------------------------------------------------------------------------

def cell(count: dict | None) -> str:
    if not count:
        return "–"
    if "error" in count:
        return "failed"
    return f"{count['inputs']} ({count['pointer']} pointer, {count['typed']} typed, {count['keys']} keys; {count['keystrokes']} keystrokes)"


SHORT = {"value": "A value changed", "double": "A skill made like one (DoubleDose)",
         "bottomup": "A new flow (BottomUpFilling)", "fifteen": "A product, 15 mL weighed"}


def latex(rows: list[dict]) -> str:
    """The table for the paper: inputs, keystrokes in brackets."""
    def entry(count):
        return "--" if not count or "error" in count else f"{count['inputs']} ({count['keystrokes']})"
    lines = [r"\begin{table}[t]", r"\centering",
             r"\caption{Effort of a reconfiguration of the filling module in user inputs (clicks and drags, typed entries, "
             r"keys pressed alone; keystrokes in brackets). Skill editor and planner counted in the browser, each result read "
             r"back from the AAS and compared with its target; the 4diac IDE counted from the program the module rules "
             r"generate, one input per element at the least.}",
             r"\label{tab:effort}", r"\small", r"\begin{tabular}{@{}lrrr@{}}", r"\hline",
             r"Change & 4diac IDE & Skill editor & Planner \\", r"\hline"]
    for r in rows:
        lines.append(f"{SHORT[r['task']]} & {entry(r['4diac'])} & {entry(r['editor'])} & {entry(r['planner'])} " + r"\\")
    lines += [r"\hline", r"To the running module & 3, restart & 1, online & 1, online \\", r"\hline", r"\end{tabular}",
              r"\end{table}"]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--ui", action="store_true", help="also drive the skill editor and the planner in a browser")
    parser.add_argument("--repo", default="http://localhost:18081")
    parser.add_argument("--service", default="http://127.0.0.1:18090")
    parser.add_argument("--web", default="http://127.0.0.1:4173")
    parser.add_argument("--only", choices=list(TASKS), help="one task only")
    args = parser.parse_args()
    module, components = sc.delivered()
    when = datetime.now()
    folder = RESULTS / f"effort-{when:%Y-%m-%dT%H%M}"
    folder.mkdir(parents=True, exist_ok=True)
    commit = subprocess.run(["git", "rev-parse", "--short=12", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    rows = []
    for task, about in TASKS.items():
        if args.only and task != args.only:
            continue
        row = {"task": task, "title": about["title"], "commit": commit, "machine": platform.platform(),
               "4diac": in_4diac(task, module, components)}
        for route in ("editor", "planner"):
            row[route] = in_browser(task, route, args, module, components, folder) if args.ui and route in about["routes"] else None
        rows.append(row)
        print(task, {k: (v.get("inputs"), v.get("right")) if isinstance(v, dict) else v for k, v in row.items() if k in ("4diac", "editor", "planner")})
    (folder / "effort.jsonl").write_text("".join(json.dumps(r, default=list) + "\n" for r in rows), encoding="utf-8")
    md = [f"# Effort of a reconfiguration, in user inputs ({when:%Y-%m-%d %H:%M}, commit {commit})", "",
          "Inputs = pointer actions (clicks, drags) + typed entries (a value or name typed) + keys pressed alone. "
          "The editor and the planner counted in the browser, each change read back and compared with its target; "
          "the 4diac IDE counted from the program the module rules make of the target.", "",
          "| Task | 4diac IDE, by hand | Skill editor | Planner |", "| --- | --- | --- | --- |"]
    for r in rows:
        md.append(f"| {r['title']} | {cell(r['4diac'])} | {cell(r['editor'])} | {cell(r['planner'])} |")
    md += ["", "To the running module: 4diac " + cell(rows[0]["4diac"]["deploy"]) + ", a new boot file and a restart; "
           "the AAS routes " + cell(tally(typed=1, keystrokes=len(RECONFIGURE) + 1)) + " (`modsync reconfigure`), online.", "",
           "## The 4diac IDE, what is counted", ""]
    for r in rows:
        c = r["4diac"]
        md.append(f"- {r['task']}: {c['route']}; blocks {c.get('blocks')} added, {c.get('blocks_removed', 0)} removed; connections "
                  f"{c.get('connections')} drawn, {c.get('connections_removed', 0)} deleted; values {c.get('values')}; "
                  f"subapplications {c.get('subapplications')} made, {c.get('entered', 0)} entered; built new instead: "
                  f"{c['built_new']} inputs")
    md += ["", "## The browser runs", ""]
    for r in rows:
        for route in ("editor", "planner"):
            c = r[route]
            if c:
                md.append(f"- {r['task']}, {route}: " + ("FAILED " + c["error"].splitlines()[0] if "error" in c else
                          f"saved {c['saved']} ({c['deployment']}), right: {c['right']} {'; '.join(c['differences'])}; " + " · ".join(c["log"])))
    text = "\n".join(md) + "\n"
    (folder / "effort.md").write_text(text, encoding="utf-8")
    (folder / "effort.tex").write_text(latex(rows), encoding="utf-8")
    print(text)
    print(folder)
    return 0 if all("error" not in (r[k] or {}) and (r[k] or {}).get("right", True) for r in rows for k in ("editor", "planner")) else 1


if __name__ == "__main__":
    sys.exit(main())
