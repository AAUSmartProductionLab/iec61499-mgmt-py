"""The lab's AAS stack on this computer (deploy/aas/compose.yaml): BaSyx, the DMP, InfluxDB.

    python deploy/aas.py up          # write the secrets to deploy/aas/.env if there are none, start it all
    python deploy/aas.py status      # the containers, and what the DMP made of the AIMCs
    python deploy/aas.py status FillingModuleAAS    # ... and why each of its mappings that does not run does not
    python deploy/aas.py rows FillingModuleAAS      # the latest row of each of a module's time series
    python deploy/aas.py logs dmp
    python deploy/aas.py down        # stop it (InfluxDB keeps its data in a volume)

Web UI http://localhost:3000, AAS environment http://localhost:8081, DMP http://localhost:8085,
InfluxDB http://localhost:8086 (user admin; password and token in deploy/aas/.env, never committed).

The DMP builds its routes from the AIMCs in the AAS environment and follows its submodel events, so
an AAS published there (modreg serve --basyx http://localhost:8081, or cell/examples/example_line.py)
is running a moment later: its Operations call the module's methods, its properties fill the series.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import secrets
import subprocess
import sys
import urllib.parse
import urllib.request

BASE_URL = "https://smartproductionlab.aau.dk"     # aas-model's: the ids of the lab's AASs start with it
STACK = Path(__file__).resolve().parent / "aas"
ENV = STACK / ".env"
DMP = "http://localhost:8085"
INFLUX = "http://localhost:8086"
BUCKET = "ap2030"


def compose(*args: str) -> None:
    subprocess.run(["docker", "compose", "-f", str(STACK / "compose.yaml"), *args], check=True)


def secret(name: str) -> str:
    for line in ENV.read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition("=")
        if key == name:
            return value
    sys.exit(f"{name} is not in {ENV}: run deploy/aas.py up")


def up(args) -> None:
    """Start the stack; the first time, make up InfluxDB's password and token."""
    if not ENV.exists():
        ENV.write_text(f"INFLUX_PASSWORD={secrets.token_urlsafe(18)}\nINFLUX_TOKEN={secrets.token_urlsafe(32)}\n",
                       encoding="utf-8")
        print(f"Wrote new secrets to {ENV}")
    compose("up", "-d", "--build")


def down(args) -> None:
    compose("down")


def logs(args) -> None:
    compose("logs", "--tail", str(args.lines), *([args.service] if args.service else []))


def dmp(path: str) -> dict:
    try:
        with urllib.request.urlopen(f"{DMP}{path}", timeout=5) as answer:
            return json.load(answer)
    except OSError as e:
        sys.exit(f"The DMP does not answer at {DMP}: {e}")


def status(args) -> None:
    """The containers, how many mappings the DMP runs (installed) and does not; with an AAS, why
    each of its mappings that does not run does not."""
    compose("ps")
    found = dmp("/management/status")
    states: dict[str, int] = {}
    for m in found.get("mappings") or []:
        key = m.get("state", "?") + (f" ({m['category']})" if m.get("category") else "")
        states[key] = states.get(key, 0) + 1
    print(f"DMP: converged {found.get('converged')}, mappings {dict(sorted(states.items()))}")
    if args.asset:
        aimc = args.asset if "://" in args.asset else f"{BASE_URL}/aas/{args.asset}/submodels/AssetInterfacesMappingConfiguration"
        mine = dmp(f"/management/mappings?aimc={urllib.parse.quote(aimc, safe='')}").get("mappings") or []
        print(f"{args.asset}: {len(mine)} mappings, {sum(m['state'] == 'installed' for m in mine)} installed")
        for m in mine:
            if m["state"] != "installed":
                print(f"  [{m['listIndex']}] {m['state']} {m['category']}")
                for d in m.get("diagnostics") or []:
                    print(f"      {d['path']}: {d['message']}")


def rows(args) -> None:
    """The latest value of every field of an asset's series, by measurement."""
    flux = (f'from(bucket: "{BUCKET}") |> range(start: -{args.since}) |> filter(fn: (r) => r["asset"] == "{args.asset}")'
            ' |> last() |> keep(columns: ["_time", "_measurement", "_field", "_value"])')
    request = urllib.request.Request(f"{INFLUX}/api/v2/query?org=ap2030", data=json.dumps({"query": flux}).encode(),
                                     headers={"Authorization": f"Token {secret('INFLUX_TOKEN')}",
                                              "Content-Type": "application/json", "Accept": "application/csv"})
    with urllib.request.urlopen(request, timeout=10) as answer:
        table = [row for row in csv.reader(answer.read().decode("utf-8").splitlines()) if row]
    header = next((row for row in table if "_field" in row), [])
    found = sorted((r[header.index("_measurement")], r[header.index("_field")], r[header.index("_time")], r[header.index("_value")])
                   for r in table if r is not header and r != header and len(r) == len(header))
    for measurement, field, time, value in found:
        print(f"{measurement:28} {field:48} {value:>12}  {time}")
    if not found:
        print(f"No rows of {args.asset} in the last {args.since}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    for name, fn in [("up", up), ("down", down), ("status", status), ("logs", logs), ("rows", rows)]:
        sub = commands.add_parser(name)
        sub.set_defaults(fn=fn)
        if name == "status":
            sub.add_argument("asset", nargs="?", help="an AAS idShort (or its AIMC's id): why its mappings do not run")
        if name == "logs":
            sub.add_argument("service", nargs="?")
            sub.add_argument("--lines", type=int, default=100)
        if name == "rows":
            sub.add_argument("asset", help="the AAS idShort the series are tagged with, e.g. FillingModuleAAS")
            sub.add_argument("--since", default="1h", help="how far back, a Flux duration (default 1h)")
    args = parser.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
