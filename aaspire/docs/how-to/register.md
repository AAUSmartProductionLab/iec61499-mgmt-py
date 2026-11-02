# Register a module, publish a line

The AASs on an AAS server, where the apps, the agents and the DMP find them. Everything here runs
on your own PC.

!!! warning "Not the lab's server"
    Publish to the lab's shared AAS server only with the lab's agreement: it holds the live shells of
    the lab's stations, and an AAS with the same id overwrites them.

## 1. The stack

```powershell
python deploy/aas.py up       # BaSyx (:8081), the web UI (:3000), the DMP, InfluxDB, Mosquitto, Prosody
```

The AAS environment keeps the AASs in memory: publish them again after a restart.

## 2. The registration service

```powershell
python -m modreg serve --ontology ontology/ARSO --basyx http://localhost:8081 --discover
```

It listens on port 8090. With `--discover` it finds every module on the network whose FORTE announces
itself and registers it from the profiles the module serves.

## 3. A module by hand

```powershell
python -m modreg register filling --target pi --service http://localhost:8090 --check   # only check it
python -m modreg register filling --target pi --service http://localhost:8090           # register it
python -m modsync pull --host 192.168.0.203 --register http://localhost:8090            # what runs, registered
```

A profile that breaks a restriction of ARSO is refused, with the reasons.

## 4. The whole line

```powershell
python cell/examples/example_line.py --out aas --publish http://localhost:8081
```

Every AAS of the example line: the line, the planar table and its shuttles, the modules and their
components, three products, the process of each, every process checked first. Open
`http://localhost:3000` to see them in the web UI, and the Planner to bind a recipe.
