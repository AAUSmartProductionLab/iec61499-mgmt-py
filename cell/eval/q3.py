"""Q3 of docs/cirp-evaluation.md: does the program stay what its AAS says? Ten kinds of drift made on
the filling module with five skills; the reconciler asked to find and remove each; the generator's
program the oracle.

    python cell/eval/q3.py --forte runtime/fbe/build/modules-win-eval/output/bin/forte.exe
    python cell/eval/q3.py --forte ... --pilot -v          # three runs of each kind
    python cell/eval/q3.py --forte ... --only P1 P4 --resume cell/eval/results/q3-<when>.jsonl

Every run starts a fresh FORTE with the test program, the module Idle and free, and appends a JSON
line to cell/eval/results/q3-<when>.jsonl: the drift, what the reconciler read and did, the oracle
before and after, and the checks R1 to R3.
"""
from __future__ import annotations

import argparse
import copy
import html
import json
import random
import sys
import tempfile
import time
import traceback
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import q1                                                                    # noqa: E402
import scenarios as sc                                                       # noqa: E402
from iec61499_mgmt.protocol import Command, ManagementError                  # noqa: E402
from modgen import load                                                      # noqa: E402
from modgen.spec import Composite, ModuleSpec                               # noqa: E402
from modsync.desired import read, reconfigure                                # noqa: E402
from modsync.device import read_structure                                    # noqa: E402
from modsync.sources import instances                                        # noqa: E402
from modsync.sync import Refused                                             # noqa: E402
from test_modsync import DOUBLE_DOSE                                         # noqa: E402 (tests on the path: scenarios)

KINDS = ("P1", "P2", "P3", "P4", "P5", "A1", "A2", "A3", "A4", "clean")
EXPECTED = {"P1": "value", "P2": "restart", "P3": "restart", "P4": "create", "P5": "record",
            "A1": "value", "A2": "restart", "A3": "restart", "A4": "restart", "clean": "none"}
SAMPLED = {"P3": 30, "A2": 30}
CLEAN = 100
ADDED = "Added4"                         # P4: the new skill whose reconfiguration is cut
SKILLS = {"DoubleDose": Composite.model_validate(DOUBLE_DOSE), sc.WRITTEN: sc.BOTTOM_UP,
          "Sequence8": q1.synthetic(8, 1), "Parallel8": q1.synthetic(8, 2)}
PARAMETERLESS = ("Home", "Tare", "Weigh")  # the primitives A2 inserts
CONTAINER = "Filling"
VERBOSE = False


def log(*parts) -> None:
    if VERBOSE:
        print(f"  {datetime.now():%H:%M:%S}", *parts, file=sys.stderr, flush=True)


# The test program and the AAS ------------------------------------------------------------------------

def test_program() -> ModuleSpec:
    spec = load(sc.FILLING)
    return spec.model_copy(update={"composites": {**spec.composites, **SKILLS}})


def changed(spec: ModuleSpec, name: str, change) -> ModuleSpec:
    """``spec`` with its skill ``name`` changed by ``change`` (on the skill's data, as the editor saves it)."""
    data = spec.composites[name].model_dump()
    change(data)
    return spec.model_copy(update={"composites": {**spec.composites, name: Composite.model_validate(data)}})


def without_skill(spec: ModuleSpec, name: str) -> ModuleSpec:
    return spec.model_copy(update={"composites": {k: v for k, v in spec.composites.items() if k != name}})


def steps_of(sequence: list[dict], path: tuple = ()):
    """(path, step) of every step of a sequence, in the branches of its parallel blocks too."""
    for i, node in enumerate(sequence):
        if "branches" in node:
            for b, branch in enumerate(node["branches"]):
                yield from steps_of(branch, path + (i, b))
        else:
            yield path + (i,), node


def at_path(sequence: list[dict], path) -> dict:
    node = sequence[path[0]]
    for b, i in zip(path[1::2], path[2::2]):
        node = node["branches"][b][i]
    return node


def other(value):
    """Another valid value of a step's constant or a parameter's number: an integer plus one, a real
    nine tenths of it (one, if it is zero)."""
    if isinstance(value, int):
        return value + 1
    return 1.0 if value == 0 else round(value * 0.9, 3)


# The drifts ------------------------------------------------------------------------------------------

def drifts(spec: ModuleSpec, boot: str, record_: dict, rng: random.Random) -> list[dict]:
    """Every drift of every kind (P3 and A2 sampled), each a dict with its kind and target."""
    entries = q1.boot_set(boot)
    out = [{"kind": "P1", "port": b, "was": html.unescape(a)} for kind, a, b in entries if kind == "write"]
    out += [{"kind": "P2", "source": a, "destination": b} for kind, a, b in entries if kind == "connect"]
    types = sorted({t for kind, a, t in entries if kind == "fb" and a != "RES" and "::SERVER" not in t
                    and "::PUBLISH" not in t and "::SUBSCRIBE" not in t})
    inits = sorted(a for kind, a, b in entries if kind == "connect" and a.endswith(".INITO") and b.endswith(".INIT"))
    p3 = [(t, place, linked) for t in types for place in ("", *sorted(spec.composites)) for linked in (False, True)]
    out += [{"kind": "P3", "type": t, "place": place, "linked": rng.choice(inits) if linked else None,
             "name": f"Stray{i + 1:02d}"} for i, (t, place, linked) in enumerate(rng.sample(p3, min(SAMPLED["P3"], len(p3))))]
    out += [{"kind": "P4", "cut": i} for i in range(0, len(CUT) + 1)]
    out += [{"kind": "P5", "instance": path} for path, _, digest in instances(record_) if digest]
    for name, comp in spec.composites.items():
        data = comp.model_dump()
        for path, step in steps_of(data["execute"]):
            for p, v in step["bind"].items():
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    out.append({"kind": "A1", "skill": name, "path": list(path), "port": p, "was": v})
        for p, decl in data["parameters"].items():
            for key in ("default", "minimum", "maximum"):
                if isinstance(decl.get(key), (int, float)) and not isinstance(decl.get(key), bool):
                    out.append({"kind": "A1", "skill": name, "parameter": p, "key": key, "was": decl[key]})
    a2 = [{"kind": "A2", "skill": name, "at": p, "step": s} for name, comp in spec.composites.items()
          for p in range(len(comp.execute) + 1) for s in PARAMETERLESS]
    out += rng.sample(a2, min(SAMPLED["A2"], len(a2)))
    out += [{"kind": "A3", "skill": name, "at": p} for name, comp in spec.composites.items()
            for p in range(len(comp.execute) - 1)]
    out += [{"kind": "A4", "skill": name} for name in sorted(spec.composites)]
    out += [{"kind": "clean", "run": i} for i in range(CLEAN)]
    return out


def described(drift: dict, base: ModuleSpec) -> ModuleSpec:
    """The module spec the AAS describes after the drift (the A kinds change it; P4 adds a skill)."""
    kind = drift["kind"]
    if kind == "P4":
        return base.model_copy(update={"composites": {**base.composites, ADDED: q1.synthetic(4, 1)}})
    if kind == "A1":
        def change(data):
            if "parameter" in drift:
                decl = data["parameters"][drift["parameter"]]
                if drift["key"] == "default":
                    decl["default"] = round((drift["was"] + decl["maximum"]) / 2, 3) if decl.get("maximum") else other(drift["was"])
                elif drift["key"] == "minimum":
                    decl["minimum"] = other(drift["was"])
                else:
                    decl["maximum"] = max(other(drift["was"]), decl.get("default") or 0)
            else:
                at_path(data["execute"], drift["path"])["bind"][drift["port"]] = other(drift["was"])
        return changed(base, drift["skill"], change)
    if kind == "A2":
        return changed(base, drift["skill"], lambda d: d["execute"].insert(
            drift["at"], {"skill": drift["step"], "name": "Inserted", "bind": {}}))
    if kind == "A3":
        def swap(data):
            data["execute"][drift["at"]], data["execute"][drift["at"] + 1] = \
                data["execute"][drift["at"] + 1], data["execute"][drift["at"]]
        return changed(base, drift["skill"], swap)
    if kind == "A4":
        return without_skill(base, drift["skill"])
    return base


# Making a drift in the program ------------------------------------------------------------------------

def made(bench, drift: dict) -> None:
    """The drift made in the running program over the management protocol, as from the IDE or by hand."""
    run = lambda **kw: bench.client.execute(Command(resource="RES", **kw))           # noqa: E731
    if drift["kind"] == "P1":
        run(op="write", destination=drift["port"], value=another(drift["was"]))
    elif drift["kind"] == "P2":
        run(op="disconnect", source=drift["source"], destination=drift["destination"])
    elif drift["kind"] == "P3":
        name = ".".join(p for p in (CONTAINER, drift["place"], drift["name"]) if p)
        run(op="create_fb", name=name, type=drift["type"])
        if drift["linked"]:
            run(op="connect", source=drift["linked"], destination=f"{name}.INIT")
        run(op="start", name=name)


def another(literal_: str) -> str:
    """Another value of the type a boot file's literal has: a number plus one, a boolean negated, a
    time a millisecond longer, a string with a character more."""
    text = literal_.strip()
    if text in ("TRUE", "FALSE"):
        return "FALSE" if text == "TRUE" else "TRUE"
    if text.upper().startswith(("T#", "TIME#")):
        return f"T#{q1.literal(text)[1] + 1}ms"
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "'\"":
        return f"{text[:-1]}x{text[-1]}"
    prefix, _, bare = text.rpartition("#")
    try:
        number = int(bare)
        return f"{prefix}#{number + 1}" if prefix else str(number + 1)
    except ValueError:
        pass
    try:
        number = float(bare)
        return f"{prefix}#{number + 1}" if prefix else str(number + 1)
    except ValueError:
        return f"'{text}x'"


# The cut (P4) -----------------------------------------------------------------------------------------

CUT: list[Command] = []


def record_cut(bench, base: ModuleSpec) -> None:
    """The commands of adding ADDED online, recorded once on a fresh FORTE (P4 sends their first i)."""
    module, components = q1.delivered_spec(base)
    wanted = q1.with_composite(module, components, ADDED, q1.synthetic(4, 1))
    bench.start(bench.boot(base))
    q1.between_orders(bench)
    sent: list = []
    with q1.recording(bench.client, sent):
        reconfigure(bench.client, bench.host, bench.port, wanted, components)
    bench.stop()
    CUT[:] = [c for c in sent if c.op not in q1.READING]


# A run -------------------------------------------------------------------------------------------------

def classes(found) -> list[str]:
    out = [name for name, has in (("value", found.values), ("create", found.create), ("restart", found.restart),
                                  ("record", found.built)) if has]
    return out or ["none"]


def element(drift: dict) -> list[str]:
    """The names a report that locates the drift mentions: its instance or port, else its skill."""
    rel = lambda name: name[len(CONTAINER) + 1:] if name.startswith(CONTAINER + ".") else name  # noqa: E731
    kind = drift["kind"]
    if kind == "P1":
        return [rel(drift["port"]), rel(drift["port"]).rpartition(".")[0]]
    if kind == "P2":
        return [rel(drift["source"]).rpartition(".")[0], rel(drift["destination"]).rpartition(".")[0]]
    if kind == "P3":
        return [".".join(p for p in (drift["place"], drift["name"]) if p)]
    if kind == "P4":
        return [ADDED]
    if kind == "P5":
        return [drift["instance"]]
    if kind in ("A1", "A2", "A3", "A4"):
        return [drift["skill"]]
    return []


def located(lines: list[str], names: list[str]) -> bool:
    return any(n and n in line for n in names for line in lines)


def recorded(bench, base: ModuleSpec) -> dict:
    """The record of what was built, with the types' hashes FORTE reports (as the integrator records it)."""
    from modreg import profile
    snap = read_structure(bench.client, bench.host, bench.port)
    describer = profile.Describer(base, "pc", snap, None, None, None)
    describer.derive = False
    built = describer.build()
    return profile.record(describer, built[0][0])


def with_other_hash(record_: dict, instance: str) -> dict:
    """The record with another hash for the type of ``instance`` (FORTE runs another version)."""
    record_ = copy.deepcopy(record_)
    for element_ in walk_elements(record_):
        values = {e.get("idShort"): e for e in element_.get("value", []) if isinstance(e, dict)}
        if values.get("InstancePath", {}).get("value") == instance and "TypeHash" in values:
            digest = values["TypeHash"]["value"]
            values["TypeHash"]["value"] = digest[:-1] + ("0" if digest[-1] != "0" else "1")
            return record_
    raise KeyError(f"{instance}: no type hash in the record")


def walk_elements(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from walk_elements(v)
    elif isinstance(node, list):
        for v in node:
            yield from walk_elements(v)


def run_one(bench, drift: dict, base: ModuleSpec, boots: dict, record_: dict) -> dict:
    kind = drift["kind"]
    spec = described(drift, base)
    module, components = q1.delivered_spec(base)
    if kind == "P4":
        module = q1.with_composite(module, components, ADDED, q1.synthetic(4, 1))
    elif spec is not base:
        module, components = q1.delivered_spec(spec)
    key = spec.model_dump_json()
    if key not in boots:
        boots[key] = bench.boot(spec)
    generated = boots[key]
    out, checks = {"drift": drift}, {}
    bench.start(boots["base"])
    q1.between_orders(bench)
    # R1: the program before the drift is the generator's, and the reconciler reads nothing.
    base_module, base_components = q1.delivered_spec(base)
    before = q1.program_is(bench, boots["base"], running=True)
    checks["R1"] = q1.same(before) and read(bench.client, bench.host, bench.port, base_module, base_components,
                                            record_=record_).differences.empty
    # R2: the drift is made.
    try:
        if kind == "P4":
            for c in CUT[:drift["cut"]]:
                bench.client.execute(c)
        else:
            made(bench, drift)
        checks["R2"] = True
    except ManagementError as exc:
        checks["R2"], out["made_error"] = False, str(exc)
    reading_record = record_
    if kind == "P5":
        reading_record = with_other_hash(record_, drift["instance"])
    # The oracle: does the program differ from what the AAS describes?
    oracle = q1.program_is(bench, generated, running=True)
    out["oracle_differs"] = not q1.same(oracle) or kind == "P5"
    out["oracle"] = {k: v for k, v in oracle.items() if v and k != "compared"}
    # What the reconciler reads.
    try:
        found = read(bench.client, bench.host, bench.port, module, components, record_=reading_record).differences
        out["read"] = {"classes": classes(found), "lines": found.lines()[:12], "partial": found.partial}
        out["detected"] = not found.empty
        out["located"] = located(found.lines(), element(drift))
    except Exception as exc:                                    # noqa: BLE001 (the reading failed: recorded)
        out["read"] = {"classes": ["error"], "error": f"{type(exc).__name__}: {exc}"[:300]}
        out["detected"], out["located"] = None, False
    # The baseline: the AAS against the boot file that was deployed, not the running program.
    out["baseline_detects"] = q1.boot_set(boots["base"]) != q1.boot_set(generated)
    # What the reconciler does with it.
    try:
        done, after = reconfigure(bench.client, bench.host, bench.port, module, components, record_=reading_record)
        out["done"] = done[:8]
        again = q1.program_is(bench, generated, running=True)
        out["removed"] = after.differences.empty and q1.same(again) and kind != "P5"
        out["outcome"] = "nothing to do" if done[0].startswith("the program is what") else (
            "removed" if out["removed"] else "applied, still differs")
        out["after"] = {k: v for k, v in again.items() if v and k != "compared"}
    except Refused as exc:
        out["outcome"], out["refused"], out["removed"] = "refused", str(exc)[:300], False
    except Exception as exc:                                    # noqa: BLE001
        out["outcome"], out["error"], out["removed"] = "failed", f"{type(exc).__name__}: {exc}"[:300], False
    if kind == "P4" and out["outcome"] == "removed":
        out["new_skill_ran"], out["dispensing_ran"] = runs(bench, drift["cut"] % 10 == 0)
    bench.stop()
    q1.logged(out, checks, bench.forte_dir)
    checks["R3"] = checks.pop("V10")
    return {"out": out, "checks": checks}


def runs(bench, dispensing: bool) -> tuple[bool, bool | None]:
    """The added skill run (V5), and Dispensing if ``dispensing``: does the module still run what it ran?"""
    bench.ua.call("Occupation/Occupy", sc.SESSION)
    bench.ua.call("Module/Start", sc.SESSION)
    try:
        bench.ua.expect("Module/State", q1.STATES["Execute"], timeout=10)
        bench.run(ADDED, 1.0, timeout=120)
        new = True
    except Exception:                                           # noqa: BLE001
        new = False
    old = None
    if dispensing:
        try:
            bench.run("Dispensing", 1.0, timeout=120)
            old = True
        except Exception:                                       # noqa: BLE001
            old = False
    return new, old


# The session ------------------------------------------------------------------------------------------

def main() -> None:
    global VERBOSE
    ap = argparse.ArgumentParser()
    ap.add_argument("--forte", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=20261104)
    ap.add_argument("--only", nargs="*", help="kinds (P1 ... A4, clean)")
    ap.add_argument("--pilot", action="store_true", help="three runs of each kind")
    ap.add_argument("--resume", type=Path)
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    VERBOSE = a.verbose
    rng = random.Random(a.seed)
    base = test_program()
    out_path = a.resume or sc.RESULTS / f"q3-{datetime.now():%Y-%m-%dT%H%M}.jsonl"
    done_ids = set()
    if a.resume and a.resume.exists():
        done_ids = {json.dumps(json.loads(line)["out"]["drift"], sort_keys=True)
                    for line in a.resume.read_text(encoding="utf-8").splitlines() if line.strip()}
    env = q1.setup(a.forte, a.seed)
    with tempfile.TemporaryDirectory() as tmp:
        bench = sc.Bench(a.forte, Path(tmp))
        try:
            boots = {"base": bench.boot(base)}
            log("the AAS of the test program")
            q1.delivered_spec(base)
            log("the cut change")
            record_cut(bench, base)
            log(f"the cut change has {len(CUT)} commands")
            bench.start(boots["base"])
            q1.between_orders(bench)
            record_ = recorded(bench, base)
            bench.stop()
            order = [d for d in drifts(base, boots["base"], record_, rng) if not a.only or d["kind"] in a.only]
            if a.pilot:
                order = [d for k in KINDS for d in [x for x in order if x["kind"] == k][:3]]
            rng.shuffle(order)
            log(f"{len(order)} runs; building the AASs of the A kinds")
            for d in order:
                if d["kind"].startswith("A"):
                    q1.delivered_spec(described(d, base))
            for i, drift in enumerate(order):
                if json.dumps(drift, sort_keys=True) in done_ids:
                    continue
                started = time.perf_counter()
                row = {"index": i, "time": datetime.now().isoformat(), **env}
                try:
                    row.update(run_one(bench, drift, base, boots, record_))
                    row["ok"] = all(row["checks"].values())
                    if not row["ok"]:
                        row["failure"] = "check"
                except Exception as exc:                        # noqa: BLE001 (recorded, then the next run)
                    bench.stop()
                    row.update({"out": {"drift": drift}, "ok": False, "failure": "harness",
                                "error": f"{type(exc).__name__}: {exc}"[:500], "trace": traceback.format_exc()[-1500:]})
                row["run_s"] = time.perf_counter() - started
                with out_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(row, default=str) + "\n")
                o = row["out"]
                print(f"{i + 1}/{len(order)} {drift['kind']}: {'ok' if row['ok'] else row.get('failure')} "
                      f"detected={o.get('detected')} class={o.get('read', {}).get('classes')} outcome={o.get('outcome')} "
                      f"run={row['run_s']:.1f}s{' ' + row['error'][:100] if row.get('error') else ''}", flush=True)
        finally:
            bench.stop()
            bench.close()
    print(out_path)


if __name__ == "__main__":
    main()
