"""Build the example AASs of the Production Sequence 4.0 (proposed, docs/precedence-graphs.md) and
check them:

    python cell/examples/precedence/build.py --out <folder> [--against <folder of AAS JSON>]

Two cases, each written to ``<folder>/<case>/<idShort>.json`` and, all of them in one file, to
``<folder>/<case>/<case>-environment.json`` (to load into an AAS server at once):

- battery: the pack (``battery_pack.py``), its four modules (``battery_module.py``), the cell type
  (``battery_cell.py``) and the process AAS in the simulated disassembly cell;
- pharma: the 2 mL vial (``vial_2ml.py``), its flip-off seal and the seal's aluminium part, and the
  process AAS on the filling line.

What is checked, and printed:
- every reference in these AASs: found, found in ``--against`` (the line's AASs, e.g. a copy of the
  server), or not found (the battery cell's stations are not modelled yet);
- every partial block: After names only siblings, no cycle, Order respects After;
- every joint: first and second are entities of the bill of material of the AAS holding the step,
  each joint is defined once in its AAS, a joint referred to from another archetype exists;
- every step of a recipe (and of the sequences it calls) has a binding in the process AAS.

Nothing is sent to a server.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from basyx.aas.adapter.json import AASToJsonEncoder     # noqa: E402
from aas_model.id_injector import inject_ids            # noqa: E402
from modreg import model                                # noqa: E402

import aluminium_seal                                   # noqa: E402
import battery_cell                                     # noqa: E402
import battery_module                                   # noqa: E402
import battery_pack                                     # noqa: E402
import battery_pack_on_disassembly_cell                 # noqa: E402
import flip_off_seal                                    # noqa: E402
import vial_2ml                                         # noqa: E402
import vial_2ml_on_filling_line                         # noqa: E402


def aas(asset, asset_id: str, kind: str = "Type") -> dict:
    """An AAS environment of an aas-model instance, its submodels given ids as the example line does
    (``{aas id}/submodels/{idShort}``). aas-model's Product adds an empty bill of material and Process
    Parameters where an instance sets none (a part); they are left out. ``kind``: Instance for the
    pack and its modules, which come back used, each with its serial number."""
    inject_ids(asset)
    env = model.environment(asset, asset_id)
    unset = {"HierarchicalStructures": "hierarchical_structures", "ProcessParameters": "process_parameters"}
    dropped = {sm["id"] for sm in env["submodels"]
               if sm["idShort"] in unset and unset[sm["idShort"]] not in asset.model_fields_set}
    env["submodels"] = [sm for sm in env["submodels"] if sm["id"] not in dropped]
    shell = env["assetAdministrationShells"][0]
    shell["submodels"] = [r for r in shell.get("submodels", []) if r["keys"][0]["value"] not in dropped]
    shell["assetInformation"]["assetKind"] = kind
    return env


def with_sequences(env: dict, sequences) -> dict:
    """An AAS environment with Production Sequences 4.0 added to its shell."""
    for sm in sequences:
        found = json.loads(json.dumps(sm, cls=AASToJsonEncoder))
        env["submodels"].append(found)
        env["assetAdministrationShells"][0].setdefault("submodels", []).append(
            {"type": "ModelReference", "keys": [{"type": "Submodel", "value": found["id"]}]})
    env.setdefault("conceptDescriptions", [])
    return env


def battery() -> list[dict]:
    envs = [with_sequences(aas(battery_pack.battery_pack(), battery_pack.ASSET_ID, "Instance"),
                           battery_pack.battery_pack_sequences())]
    for n in (1, 2, 3, 4):
        envs.append(with_sequences(aas(battery_module.battery_module(n), battery_module.ids(n)["asset"], "Instance"),
                                   [battery_module.battery_module_sequence(n)]))
    envs.append(with_sequences(aas(battery_cell.battery_cell(), battery_cell.ASSET_ID), []))
    envs.append(with_sequences(aas(battery_pack_on_disassembly_cell.battery_pack_on_disassembly_cell(),
                                                 battery_pack_on_disassembly_cell.ASSET_ID), []))
    return envs


def pharma() -> list[dict]:
    return [
        with_sequences(aas(vial_2ml.vial_2ml(), vial_2ml.ASSET_ID), [vial_2ml.vial_2ml_sequence()]),
        with_sequences(aas(flip_off_seal.flip_off_seal(), flip_off_seal.ASSET_ID), []),
        with_sequences(aas(aluminium_seal.aluminium_seal(), aluminium_seal.ASSET_ID), []),
        with_sequences(aas(vial_2ml_on_filling_line.vial_2ml_on_filling_line(),
                                         vial_2ml_on_filling_line.ASSET_ID), []),
    ]


# ---- the checks --------------------------------------------------------------------------------------
SEQUENCE = "https://smartproductionlab.aau.dk/SubmodelTemplate/ProductionSequence/4/0"


def semantic(element: dict) -> str:
    return ((element.get("semanticId") or {}).get("keys") or [{}])[0].get("value", "")


def child(element: dict, id_short: str) -> dict | None:
    for c in element.get("value") or element.get("submodelElements") or element.get("statements") or []:
        if isinstance(c, dict) and c.get("idShort") == id_short:
            return c
    return None


def value(element: dict, id_short: str) -> str:
    found = child(element, id_short)
    return str(found.get("value")) if found else ""


class Index:
    def __init__(self, envs: list[dict]):
        self.shells = {s["id"]: s for e in envs for s in e["assetAdministrationShells"]}
        self.submodels = {s["id"]: s for e in envs for s in e["submodels"]}

    def resolve(self, ref: dict) -> dict | None:
        keys = ref.get("keys") or []
        if not keys:
            return None
        if keys[0]["type"] == "AssetAdministrationShell":
            return self.shells.get(keys[0]["value"])
        at = self.submodels.get(keys[0]["value"])
        for key in keys[1:]:
            if at is None:
                return None
            items = at.get("value") or at.get("submodelElements") or at.get("statements") or []
            if at.get("modelType") == "SubmodelElementList" and key["value"].isdigit():
                k = int(key["value"])
                at = items[k] if k < len(items) else None
            elif at.get("modelType") == "Operation":
                at = next((v["value"] for side in ("inputVariables", "outputVariables", "inoutputVariables")
                           for v in at.get(side) or [] if v["value"].get("idShort") == key["value"]), None)
            else:
                at = next((c for c in items if isinstance(c, dict) and c.get("idShort") == key["value"]), None)
        return at


def references(element, path=""):
    """Every model reference in an element, with where it is."""
    if isinstance(element, dict):
        if element.get("type") == "ModelReference" and "keys" in element:
            yield path, element
            return
        for k, v in element.items():
            if k in ("semanticId", "supplementalSemanticIds"):
                continue
            yield from references(v, f"{path}/{element.get('idShort', k)}" if k in ("value", "submodelElements") else path)
    elif isinstance(element, list):
        for v in element:
            yield from references(v, path)


def check(case: str, envs: list[dict], against: list[dict]) -> list[str]:
    mine, line = Index(envs), Index(against + envs)      # these AASs over the copies
    lines, missing = [], set()
    n = 0
    for env in envs:
        for sm in env["submodels"]:
            for where, ref in references(sm):
                n += 1
                if mine.resolve(ref) is not None:
                    continue
                if line.resolve(ref) is not None:
                    continue
                first = ref["keys"][0]["value"]
                owner = first.split("/submodels/")[0]
                if first not in line.submodels and first not in line.shells and owner not in line.shells:
                    missing.add(owner)
                else:
                    lines.append(f"  BROKEN {sm['idShort']}{where}: {[k['value'] for k in ref['keys']]}")
    lines.insert(0, f"  references: {n}, of which into AASs not modelled: "
                    + (", ".join(sorted(m.rsplit('/', 1)[-1] for m in missing)) or "none"))

    # the sequences
    bound = set()
    for env in envs:
        for sm in env["submodels"]:
            if sm.get("idShort") == "Bindings":
                for b in sm.get("submodelElements", []):
                    step = child(b, "Step")
                    if step:
                        bound.add(json.dumps([k["value"] for k in step["value"]["keys"]]))
    # the sequences a process AAS runs: its Recipe, and what the Recipe calls
    run, todo = set(), [child(sm, "Recipe")["value"]["keys"][0]["value"] for env in envs for sm in env["submodels"]
                        if sm.get("idShort") == "ProcessInformation"]
    while todo:
        sid = todo.pop()
        if sid in run or sid not in mine.submodels:
            continue
        run.add(sid)
        for _, r in references(mine.submodels[sid]):
            if r["keys"][0]["value"] in mine.submodels and semantic(mine.submodels[r["keys"][0]["value"]]) == SEQUENCE:
                todo.append(r["keys"][0]["value"])
    idle = [sm["idShort"] + " of " + env["assetAdministrationShells"][0]["idShort"] for env in envs
            for sm in env["submodels"] if semantic(sm) == SEQUENCE and sm["id"] not in run]
    if idle:
        lines.append("  not run by a process AAS here, so not checked for bindings: " + ", ".join(idle))
    steps_total = 0
    for env in envs:
        shell = env["assetAdministrationShells"][0]
        bill = next((s for s in env["submodels"] if s["idShort"] == "HierarchicalStructures"), None)
        entities = set()
        if bill:
            entry = child(bill, "EntryNode")
            entities = {s["idShort"] for s in (entry or {}).get("statements", []) if s.get("modelType") == "Entity"}
        defined = set()
        for sm in env["submodels"]:
            if semantic(sm) != SEQUENCE:
                continue
            arche = value(sm, "ArcheType")

            def walk(steps: dict, prefix: list[str]):
                """``steps``: a Steps collection; ``prefix``: the keys to it, from the submodel's id."""
                nonlocal steps_total
                items = [s for s in steps.get("value", []) if s.get("modelType") == "SubmodelElementCollection"]
                for s in items:
                    kind, keys = value(s, "Kind"), prefix + [s["idShort"]]
                    if kind == "step" and sm["id"] in run:
                        steps_total += 1
                        if json.dumps(keys) not in bound:
                            lines.append(f"  UNBOUND {shell['idShort']}/{sm['idShort']}: {value(s, 'NodeId')}")
                    for j in (child(s, "Joints") or {}).get("value", []):
                        if j["modelType"] == "AnnotatedRelationshipElement":
                            if j["idShort"] in defined:
                                lines.append(f"  TWICE joint {j['idShort']} in {shell['idShort']}")
                            defined.add(j["idShort"])
                            for side in ("first", "second"):
                                target = j[side]["keys"]
                                if not (target[0]["value"] == (bill or {}).get("id") and target[-1]["value"] in entities):
                                    lines.append(f"  JOINT {j['idShort']}.{side} is not a part of {shell['idShort']}")
                        elif j["modelType"] == "ReferenceElement":
                            found = mine.resolve(j["value"])
                            if found is None or found.get("modelType") != "AnnotatedRelationshipElement":
                                lines.append(f"  JOINT reference {j['idShort']} not found")
                    if kind == "partial":
                        inner = child(s, "Steps")
                        sib = {c["idShort"]: c for c in inner.get("value", [])}
                        after = {}
                        for name, c in sib.items():
                            after[name] = []
                            for r in (child(c, "After") or {}).get("value", []):
                                k = [x["value"] for x in r["value"]["keys"]]
                                if k[:-1] != keys + ["Steps"] or k[-1] not in sib:
                                    lines.append(f"  AFTER {value(c, 'NodeId')} names a step outside its block")
                                else:
                                    after[name].append(k[-1])
                        layers, done = [], set()
                        while len(done) < len(sib):
                            ready = [x for x in sib if x not in done and set(after[x]) <= done]
                            if not ready:
                                lines.append(f"  CYCLE among {sorted(set(sib) - done)}")
                                break
                            layers.append(", ".join(value(sib[x], "NodeId") for x in ready))
                            done |= set(ready)
                        for x, before in after.items():
                            for y in before:
                                if int(value(sib[y], "Order")) >= int(value(sib[x], "Order")):
                                    lines.append(f"  ORDER {value(sib[x], 'NodeId')} is not after {value(sib[y], 'NodeId')}")
                        lines.append(f"  {shell['idShort']}/{sm['idShort']} ({arche}), ready in turn: "
                                     + " | ".join(f"[{layer}]" for layer in layers))
                        walk(inner, keys + ["Steps"])
                    for br in (child(s, "Branches") or {}).get("value", []):
                        walk(child(br, "Steps"), keys + ["Branches", br["idShort"], "Steps"])
            walk(child(sm, "Steps"), [sm["id"], "Steps"])
    lines.append(f"  steps run by the process AAS: {steps_total}, each bound")
    return lines


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--against", type=Path, help="a folder of AAS JSON environments the references may point into")
    args = ap.parse_args(argv)
    against = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(args.against.glob("*.json"))] if args.against else []
    for case, envs in (("battery", battery()), ("pharma", pharma())):
        folder = args.out / case
        folder.mkdir(parents=True, exist_ok=True)
        for env in envs:
            name = env["assetAdministrationShells"][0]["idShort"]
            (folder / f"{name}.json").write_text(json.dumps(env, indent=2, ensure_ascii=False), encoding="utf-8")
        whole = {"assetAdministrationShells": [s for e in envs for s in e["assetAdministrationShells"]],
                 "submodels": [s for e in envs for s in e["submodels"]], "conceptDescriptions": []}
        (folder / f"{case}-environment.json").write_text(json.dumps(whole, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"{case}: {len(envs)} AASs, {len(whole['submodels'])} submodels -> {folder}")
        for line in check(case, envs, against if case == "pharma" else []):
            print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
