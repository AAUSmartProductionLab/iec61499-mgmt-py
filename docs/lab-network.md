# The lab network (from 23 Nov 2026)

The lab moves to its own network on a MikroTik router and a MikroTik Cloud Smart Switch (24 ports):
172.20.0.0/15 (mask 255.254.0.0), of which the lab's machines use **172.20.100.x**. The router hands
out the addresses (DHCP) and has internet access. The lab server is **172.20.100.187**.

What has to hold for the line to work there, and what to do per machine.

## What the line needs from the network

1. **A fixed address and a name per machine.** FORTE listens on every interface, so it needs no
   static IP itself. But a module's address is in its spec (`cell/modules/*.yaml`, `targets.pi.host`),
   in its generated 4diac project, and in its published AAS (the OPC UA endpoint of its Asset
   Interfaces Description, which the DMP and modlink call). And a module registers and announces
   itself by its host name (`opc.tcp://capping-module:4840`). So each machine gets a static DHCP lease
   on the router and a DNS name the router resolves. The specs then name the module (`host:
   capping-module`), and the next move changes nothing in them.
2. **Docker's own networks outside 172.20.0.0/15.** Docker takes 172.17.0.0/16 for its bridge and
   hands Compose networks 172.18 to 172.31; one on 172.20 or 172.21 cuts its host off from the lab.
   Every Docker host (the server, every Pi, Docker Desktop on a PC) uses 10.250.0.0/24 and
   10.251.0.0/16 instead: `deploy/docker_pools.py` (`deploy/pi.py pools` on a Pi).
3. **Discovery by mDNS on one segment.** FORTE announces its OPC UA server by mDNS
   (`_opcua-tcp._tcp`, OPC UA's LDS-ME), and `modreg serve --discover` finds the modules so; mDNS
   does not cross a router, so the modules and the machine running the discovery stay on the
   switch's segment. FORTE registers at an OPC UA discovery server (LDS) only when asked to
   (`FORTE_LDS_REGISTER=1`, forte-patches/0008), and then with the LDS's name and address in the
   container (`deploy/pi.py install --lds HOST=IP`): it cannot resolve `.local` names, and before the
   patch each attempt froze its OPC UA server for 5 s every minute.
4. **One interface per module.** A Pi on both Ethernet and Wi-Fi announces on "the first suitable
   interface" and may answer from the other address. The module Pis use Ethernet only.

## On the MikroTik router (once)

In WinBox or the web interface (WebFig), or in the terminal:

1. **Static leases.** IP > DHCP Server > Leases: once a machine has a lease, *Make Static*, then set
   its address. In the terminal:
   `/ip dhcp-server lease make-static [find host-name="capping-module"]` and
   `/ip dhcp-server lease set [find host-name="capping-module"] address=172.20.100.24`.
2. **Names.** IP > DNS > Static: one entry per machine,
   `/ip dns static add name=capping-module address=172.20.100.24`. With IP > DNS *Allow Remote
   Requests* on, and the router as the DNS server the DHCP network hands out (IP > DHCP Server >
   Networks, *DNS Servers*), every machine resolves the names.
3. Optional: a domain (`lab`) in the DHCP network and the static entries as `capping-module.lab`.

Proposed addresses (change them as you like; then the specs follow):

| Machine | Name | Address |
| --- | --- | --- |
| Lab server (BaSyx, DMP, web UI, services) | `lab-server` | 172.20.100.187 |
| Filling module | `filling-module` | 172.20.100.21 |
| Filling module 2 | `filling-module-2` | 172.20.100.22 |
| Stoppering module | `stoppering-module` | 172.20.100.23 |
| Capping module | `capping-module` | 172.20.100.24 |
| Inspection (camera station) | `inspection-module` | 172.20.100.25 |
| KUKA infeed (loading) | `kuka-infeed` | 172.20.100.26 |
| KUKA outfeed (unloading) | `kuka-outfeed` | 172.20.100.27 |

## Per machine

**Every module Pi** (filling, filling 2, stoppering, capping; later the inspection and KUKA Pis):

1. Plug it into the switch, Wi-Fi off: `sudo nmcli radio wifi off` (Ubuntu with NetworkManager) or
   remove the Wi-Fi from `/etc/netplan/*.yaml` and `sudo netplan apply`.
2. Its host name as in the table: `sudo hostnamectl set-hostname capping-module`.
3. On the router: its static lease and DNS name (above).
4. Docker's networks out of the lab range:
   `PI_SUDO_PASSWORD=... python deploy/pi.py pools --spec cell/modules/<module>.yaml`.
5. In its spec, `targets.pi.host` becomes its name (`capping-module`); `python -m modgen`.
6. FORTE and its compose file again, with the LDS if there is one:
   `python deploy/pi.py install --spec cell/modules/<module>.yaml --forte runtime/bin/forte-aarch64
   [--lds <lds-host>.local=172.20.100.187]`, then `python deploy/pi.py module --spec ...` (the boot file and
   the manifest).
7. `python deploy/bench.py status --spec ...`: the module answers, nothing moves.

Module by module:

| Module | Spec | State (23 Nov) | Besides the steps above |
| --- | --- | --- | --- |
| Filling | `cell/modules/filling.yaml` | Runs on its Pi; positions to measure again | — |
| Filling 2 | `cell/modules/filling-2.yaml` (new) | Spec written; its Pi set up by hand | A fresh Pi first: Docker, `dtoverlay=pwm-2chan`, groups (as `docs/demo-modules.md` says for capping); its positions measured |
| Stoppering | `cell/modules/stoppering.yaml` | Runs on its Pi | — |
| Capping | `cell/modules/capping.yaml` | Pi set up, switch works; its stepper does not change direction | Check DIR+ on pin 13 (GPIO27) and DIR- on GND, then home and measure |
| Inspection | `cell/modules/planned/inspection.yaml` | Planned | Its equipment service (Python beside FORTE) to build first (`docs/demo-modules.md`, section 5) |
| KUKA infeed, outfeed | `cell/modules/python/loading.yaml`, `unloading.yaml` | Run in Python (`modpy`) | The same network steps for the Pi that runs `python -m modpy serve`; the robots' own addresses in their specs |

**The lab server (172.20.100.187):**

1. `ssh <login>@172.20.100.187 'sudo python3 -' < deploy/docker_pools.py`, then recreate the networks
   it names (`docker compose down` and `up`).
2. The lab stack (`deploy/aas/compose.yaml`) there; the web UI's and the services' addresses become
   the server's name.
3. The modules' AASs published again (their OPC UA endpoints changed), the DMP restarted (it keeps the
   routes of the AASs it saw first), and the registry's descriptors carry the server's address.
4. For discovery: `modreg serve --discover` needs the host's network (mDNS), so the skill service runs
   with `network_mode: host` there, or on the lab PC.

**A Windows PC with Docker Desktop:** Settings > Docker Engine: the same `bip` and
`default-address-pools` as `deploy/docker_pools.py` writes. And the OPC Foundation's discovery service
(`UALDS`, installed with UaExpert) set to start manually unless it is the LDS the modules register at.
