"""The paper's changes, online and by a restart, timed on FORTE with the simulated IO (B1 and B2 in
docs/next-steps.md).

    python cell/eval/scenarios.py --forte runtime/fbe/build/modules-win/forte/build/forte/forte.exe --runs 5
    python cell/eval/scenarios.py --forte ... --only written planned --runs 1

On the filling module (pc target), from its AAS:

  plug     the module as delivered: verify the program against its AAS, operate it (Dispensing)
  value    a step's constant changed in the AAS (Dispensing's FlowRate 1.0 -> 2.0)
  written  a new skill written in the AAS (DoubleDose, as the skill editor saved it)
  planned  a new skill planned from the AAS (modplan: Filling 2.0 mL with its weight)

Each change is made both ways. **online**: ``modsync reconfigure`` (management commands, the time,
the time to verify it again, and whether the module kept running: a skill started before a new skill
is created runs to its end; a value is written while the module is Idle). **restart**, the baseline:
the program with the change generated (modgen), a new boot file, FORTE stopped and started with it;
down from stopping FORTE until the module is back in Execute. Writes cell/eval/results/<when>.json
and prints a table of medians.
"""
from __future__ import annotations

import argparse
import copy
from contextlib import ExitStack, contextmanager
from datetime import datetime
import gzip
import json
from pathlib import Path
import statistics
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "cell" / "sim"), str(ROOT / "aas61499-tools" / "tests")]

from conftest import free_port, launch_forte                                  # noqa: E402
from iec61499_mgmt.bootfile import boot_file, deployment                    # noqa: E402
from iec61499_mgmt.protocol import Client                                   # noqa: E402
from modgen import SPECS, load                                               # noqa: E402
from modgen.library import SKILL_STATES, STATES                              # noqa: E402
from modsync.aasjson import at, children, submodel                          # noqa: E402
from modsync.compare import Candidate                                       # noqa: E402
from modsync.described import described                                     # noqa: E402
from modsync.desired import read, reconfigure                               # noqa: E402
from module_sim import separate                                              # noqa: E402
from module_ua import ModuleUa                                               # noqa: E402

FILLING = SPECS / "filling.yaml"
RESULTS = Path(__file__).resolve().parent / "results"
EDITED = ROOT / "aas61499-tools" / "tests" / "data" / "FillingSkills-edited.json.gz"
SESSION = "evaluation"
SCENARIOS = ("plug", "value", "written", "planned")


def delivered() -> tuple[dict, list[dict]]:
    """The filling module's AAS as it is delivered (modreg, from the spec)."""
    from test_modsync_desired import aas
    return aas(load(FILLING), "pc")


# The changes, in the AAS ----------------------------------------------------------------------------

def with_value(module: dict) -> dict:
    """Dispensing's step Dispense runs at FlowRate 2.0 instead of 1.0."""
    module = copy.deepcopy(module)
    steps = at(submodel(module, "Skills"), "Dispensing", "Start", "Steps")
    dispense = next(s for s in children(steps) if at(s, "NodeId")["value"] == "Dispense")
    binding = next(b for b in children(at(dispense, "Bindings")) if at(b, "Name")["value"] == "FlowRate")
    at(binding, "Value")["value"] = "2.0"
    return module


def with_written(module: dict) -> dict:
    """DoubleDose, as the skill editor saved it (its own test, tests/data)."""
    module = copy.deepcopy(module)
    edited = json.loads(gzip.decompress(EDITED.read_bytes()))
    module["submodels"] = [edited if s["idShort"] == "Skills" else s for s in module["submodels"]]
    return module


def with_planned(module: dict, components: list[dict]) -> tuple[dict, float]:
    """Filling 2.0 mL with its weight, planned (modplan); with the time it took."""
    from modplan.compose import compose
    started = time.perf_counter()
    composed = compose(module, components, "Filling", {"FillVolume": 2.0}, ("FillWeight",), name="PlannedFilling")
    return composed.module, time.perf_counter() - started


# Running the module --------------------------------------------------------------------------------

class Bench:
    """FORTE with the filling module and its simulator; a module started from a boot file."""

    def __init__(self, forte: Path, folder: Path):
        self.forte, self.folder, self.stack = forte, folder, ExitStack()
        self.cand = Candidate(FILLING, load(FILLING), "pc")
        self.modbus = free_port()
        endpoint = f"{self.cand.spec.modbus.host}:{self.cand.spec.modbus.port}:"
        self.overrides = {k: v.replace(endpoint, f"127.0.0.1:{self.modbus}:") for k, v in self.cand.app.parameters.items()
                          if v.startswith("'modbus[")}
        self.stack.enter_context(separate(FILLING, host="127.0.0.1", port=self.modbus))
        self.running: ExitStack | None = None

    def boot(self, spec=None) -> str:
        cand = self.cand if spec is None else Candidate(FILLING, spec, "pc")
        return boot_file(deployment(cand.app, overrides=self.overrides, container=cand.container))

    def start(self, boot: str) -> None:
        """FORTE with ``boot``; waits until the module is Stopped (its program loaded)."""
        self.running = ExitStack()
        folder = self.folder / f"forte{time.monotonic_ns()}"
        folder.mkdir(parents=True)
        (folder / "forte.fboot").write_text(boot, encoding="utf-8", newline="\n")
        self.ua_port = free_port()
        self.port = self.running.enter_context(launch_forte(
            self.forte, folder, None, ["-f", str(folder / "forte.fboot"), "-op", str(self.ua_port)]))
        self.client = self.running.enter_context(Client("127.0.0.1", self.port))
        self.ua = ModuleUa(self.ua_port, self.cand.spec.module)
        self.running.callback(self.ua.close)
        self.ua.expect("Module/State", STATES["Stopped"], timeout=20)

    def stop(self) -> None:
        if self.running is not None:
            self.running.close()
            self.running = None

    def execute(self) -> None:
        """Occupy, Reset and Start the module: it is in Execute."""
        self.ua.call("Occupation/Occupy", SESSION)
        self.ua.call("Module/Reset", SESSION)
        self.ua.expect("Module/State", STATES["Idle"], timeout=30)
        self.ua.call("Module/Start", SESSION)
        self.ua.expect("Module/State", STATES["Execute"], timeout=10)

    def idle(self) -> None:
        """Stop the module and release it, as a value is written (the guard)."""
        self.ua.call("Module/Stop", SESSION)
        self.ua.expect("Module/State", STATES["Stopped"], timeout=30)
        self.ua.call("Occupation/Release", SESSION)

    def run(self, skill: str, *args, timeout: float = 60.0) -> float:
        started = time.perf_counter()
        assert self.ua.call(f"Skills/{skill}/Start", SESSION, *args) == [True, 0], skill
        self.ua.expect(f"Skills/{skill}/State", SKILL_STATES["Succeeded"], timeout=timeout)
        return time.perf_counter() - started

    def close(self) -> None:
        self.stop()
        self.stack.close()


def commands(done: list[str]) -> int:
    return next(int(line.split()[0]) for line in done if line.endswith("management commands"))


# The scenarios ------------------------------------------------------------------------------------

def plug(bench: Bench, module: dict, components: list[dict]) -> dict:
    bench.start(bench.boot())
    started = time.perf_counter()
    found = read(bench.client, "127.0.0.1", bench.port, module, components)
    verify = time.perf_counter() - started
    assert found.differences.empty, found.differences.lines()
    bench.execute()
    ran = bench.run("Dispensing", 1.0)
    bench.stop()
    return {"verify_s": verify, "first_run_s": ran}


def change(bench: Bench, scenario: str, module: dict, components: list[dict]) -> dict:
    """One change online, then the same by a restart; both from the program as delivered."""
    plan_s = None
    if scenario == "value":
        wanted = with_value(module)
    elif scenario == "written":
        wanted = with_written(module)
    else:
        wanted, plan_s = with_planned(module, components)
    name = {"value": "Dispensing", "written": "DoubleDose", "planned": "PlannedFilling"}[scenario]

    # Online.
    bench.start(bench.boot())
    bench.execute()
    if scenario == "value":
        bench.idle()                                   # values are written while the module is Idle
        down_started = time.perf_counter()
    else:
        assert bench.ua.call("Skills/Dispensing/Start", SESSION, 1.0) == [True, 0]   # a run goes on meanwhile
    started = time.perf_counter()
    done, after = reconfigure(bench.client, "127.0.0.1", bench.port, wanted, components)
    change_s = time.perf_counter() - started
    assert after.differences.empty, done
    started = time.perf_counter()
    assert read(bench.client, "127.0.0.1", bench.port, wanted, components).differences.empty
    verify_s = time.perf_counter() - started
    if scenario == "value":
        bench.execute()
        down_s, kept = time.perf_counter() - down_started, False
    else:
        bench.ua.expect("Skills/Dispensing/State", SKILL_STATES["Succeeded"], timeout=60)
        down_s, kept = 0.0, True
    args = (1.0,) if scenario != "planned" else ()
    if scenario == "written":
        args = (0.5,)
    ran = bench.run(name, *args)
    bench.stop()
    online = {"commands": commands(done), "change_s": change_s, "verify_s": verify_s, "down_s": down_s,
              "kept_running": kept, "ran_s": ran, **({"plan_s": plan_s} if plan_s is not None else {})}

    # By a restart: the program with the change generated, FORTE started with it.
    spec = described(wanted, components) if scenario != "value" else None
    started = time.perf_counter()
    if scenario == "value":
        changed = load(FILLING)
        composites = dict(changed.composites)
        dispensing = composites["Dispensing"].model_copy(deep=True)
        changed = changed.model_copy(update={"composites": {**composites, "Dispensing": _with_flow_rate(dispensing, 2.0)}})
    else:
        changed = load(FILLING)
        changed = changed.model_copy(update={"composites": {**changed.composites, name: spec.composites[name]}})
    boot = bench.boot(changed)
    generate_s = time.perf_counter() - started
    bench.start(bench.boot())
    bench.execute()
    down_started = time.perf_counter()
    bench.stop()
    bench.start(boot)
    bench.execute()
    restart_down_s = time.perf_counter() - down_started
    ran = bench.run(name, *args)
    bench.stop()
    restart = {"boot_lines": len(boot.splitlines()), "generate_s": generate_s, "down_s": restart_down_s, "ran_s": ran}
    return {"online": online, "restart": restart}


def _with_flow_rate(dispensing, value: float):
    """Dispensing with its step Dispense at FlowRate ``value``."""
    from modgen.spec import Composite
    data = dispensing.model_dump()
    for step in data["execute"]:
        if step.get("skill") == "Dispense":
            step["bind"]["FlowRate"] = value
    return Composite.model_validate(data)


# Running and reporting -----------------------------------------------------------------------------

def median(values: list[float]) -> float:
    return statistics.median(values) if values else float("nan")


def table(results: dict) -> str:
    lines = ["| Scenario | Online: commands | Online: change (s) | Online: verify (s) | Online: down (s) | Kept running "
             "| Restart: boot file lines | Restart: down (s) |", "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for scenario, runs in results["scenarios"].items():
        if scenario == "plug":
            lines.append(f"| plug | – | – | {median([r['verify_s'] for r in runs]):.2f} | – | – | – | – |")
            continue
        on = [r["online"] for r in runs]
        off = [r["restart"] for r in runs]
        lines.append(f"| {scenario} | {on[0]['commands']} | {median([o['change_s'] for o in on]):.2f} "
                     f"| {median([o['verify_s'] for o in on]):.2f} | {median([o['down_s'] for o in on]):.2f} "
                     f"| {'yes' if all(o['kept_running'] for o in on) else 'no'} | {off[0]['boot_lines']} "
                     f"| {median([o['down_s'] for o in off]):.2f} |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--forte", required=True, help="A FORTE built with every module (runtime/build-modules.ps1)")
    parser.add_argument("--runs", type=int, default=3, help="Runs of each scenario")
    parser.add_argument("--only", nargs="*", choices=SCENARIOS, help="Only these scenarios")
    parser.add_argument("--out", default=str(RESULTS), help="Folder for the results")
    args = parser.parse_args(argv)
    module, components = delivered()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    when = datetime.now().strftime("%Y-%m-%dT%H%M")
    results = {"when": when, "forte": str(args.forte), "runs": args.runs, "scenarios": {}}
    work = Path(tempfile.mkdtemp(prefix="scenarios-"))          # FORTE's folders and logs
    bench = Bench(Path(args.forte).resolve(strict=True), work)
    try:
        for scenario in args.only or SCENARIOS:
            runs = []
            for i in range(args.runs):
                runs.append(plug(bench, module, components) if scenario == "plug" else change(bench, scenario, module, components))
                print(f"{scenario} {i + 1}/{args.runs}: {runs[-1]}", flush=True)
            results["scenarios"][scenario] = runs
    finally:
        bench.close()
    (out / f"{when}.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    summary = table(results)
    (out / f"{when}.md").write_text(f"# Scenarios of {when}, {args.runs} runs each, medians\n\n{summary}\n", encoding="utf-8")
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
