# Deployment

<span class="pillar deployment">Deployment</span> Two halves: the server stack that holds the AASs and
the services around them, started on one computer with Docker Compose (`deploy/aas`, the future
`deploy-server`), and a Raspberry Pi turned into an IEC 61499 module (`deploy/pi`, `deploy/pi.py` and
`runtime/install.sh`, the future `deploy-module`).

<figure markdown="span">
  [![The server stack's containers on the left with the processes beside it; the Raspberry Pi with its
  FORTE container, ports and manifest server on the right, reached from the PC over SSH](../figures/deploy.png)](../figures/deploy.png)
  <figcaption>The stack runs the AAS server, the DMP, the time series, the brokers and the web UI; a Pi
  runs FORTE in a container and serves its module's profiles; the registration service finds it.</figcaption>
</figure>

## The server stack

| Container | Port | Does |
| --- | --- | --- |
| AAS environment (BaSyx) | 8081 | The shells and submodels; in memory, so the AASs are published again after a restart |
| AAS and submodel registries, discovery (BaSyx) | | Where each AAS and submodel is |
| web UI | 3000 | The [apps](../interfaces/web-ui.md) |
| DMP | 8085 | AAS Operations to OPC UA, values to the time series ([DMP](../integration/dmp.md)) |
| InfluxDB | 8086 | The time series; its data kept in a volume |
| Mosquitto | 1883 | The AAS server's events (a shell or submodel created, changed, deleted) |
| Prosody | 5222 | XMPP for the [agents](../execution/agents.md) |

```powershell
python deploy/aas.py up                 # writes the secrets to deploy/aas/.env if there are none, starts it all
python deploy/aas.py status             # the containers, and what the DMP made of the mappings
python deploy/aas.py rows FillingModuleAAS   # a module's latest values
python deploy/aas.py logs dmp
python deploy/aas.py down
```

Beside the stack run, as processes: the registration service (`python -m modreg serve --ontology
ontology/ARSO --basyx http://localhost:8081 --discover`, port 8090) and the agents (`python -m lineagents
--aas http://localhost:8081 --mqtt localhost:1883`). The secrets are in `deploy/aas/.env`, never
committed.

## A Raspberry Pi as a module

A Raspberry Pi 4 or 5 with a 64-bit Linux becomes an IEC 61499 module with one command, run on the Pi
by a user with sudo:

```bash
curl -fsSL https://raw.githubusercontent.com/AAUSmartProductionLab/iec61499-mgmt-py/main/runtime/install.sh | bash
```

It installs Docker if it is missing, starts FORTE (with every module's block types) in a container that
comes back after a reboot, gives it the GPIO lines of the 40-pin header and the two hardware PWM
channels (reboot once for them), and keeps the clock across restarts (`fake-hwclock`: a Pi has no
battery-backed clock). Running it again updates FORTE and keeps the program.

| On the Pi | |
| --- | --- |
| `~/forte` | The container (`docker compose ps`, `logs -f`): host network, `/dev/gpiochip0`, the PWM channels |
| `~/forte/boot/forte.fboot` | The module's program, loaded at every start |
| port 61499 | FORTE's management protocol: no login, the lab's network only |
| port 4840 | The module's OPC UA server, announced by mDNS |
| port 8088 | The manifest: the profiles of the module's AASs, for discovery |

From the PC, over SSH (the Pi's address and login from the module spec's `pi` target, or `--host` and
`--user`):

```powershell
python deploy/pi.py install --spec cell/modules/stoppering.yaml --forte runtime/bin/forte-aarch64
python deploy/pi.py module --spec cell/modules/stoppering.yaml    # the program as the boot file, FORTE restarted
python deploy/pi.py status --spec cell/modules/stoppering.yaml
python deploy/pi.py log --spec cell/modules/stoppering.yaml
```

Without `--spec` it uses the filling module. On a Raspberry Pi 5 the PWM channels are numbered
differently (GPIO18 is channel 2), which the spec's `board: pi5` takes care of. Step by step:
[a module on a Raspberry Pi](../how-to/raspberry-pi.md).
