"""Keep Docker's own networks out of the lab network (172.20.0.0/15), on the lab server and every Pi.

    ssh <login>@<host> 'sudo python3 -' < deploy/docker_pools.py       # then: python deploy/pi.py ... as before
    python deploy/pi.py pools --spec cell/modules/capping.yaml          # the same, for a module's Pi

Docker takes 172.17.0.0/16 for its bridge and hands Compose networks 172.18 to 172.31, so on any host a
network can land on 172.20.x or 172.21.x, and that host then no longer reaches the lab network. This
sets the bridge (``bip``) and the pools (``default-address-pools``) to 10.250/10.251 in
/etc/docker/daemon.json, keeping its other keys (a GPU runtime, log options), saves the old file as
daemon.json.bak-aaspire and restarts Docker. Networks made before keep their subnets: the script names
those still in 172.16.0.0/12; recreate them (docker compose down, then up).

Python 3 standard library only: it runs on the host as it is.
"""
import ipaddress
import json
import pathlib
import shutil
import subprocess

DAEMON = pathlib.Path("/etc/docker/daemon.json")
WANTED = {"bip": "10.250.0.1/24", "default-address-pools": [{"base": "10.251.0.0/16", "size": 24}]}
PRIVATE_172 = ipaddress.ip_network("172.16.0.0/12")


def main():
    config = json.loads(DAEMON.read_text()) if DAEMON.exists() and DAEMON.read_text().strip() else {}
    if all(config.get(k) == v for k, v in WANTED.items()):
        print("daemon.json has the pools already")
    else:
        if DAEMON.exists():
            shutil.copy2(DAEMON, DAEMON.with_name("daemon.json.bak-aaspire"))
        config.update(WANTED)
        DAEMON.parent.mkdir(parents=True, exist_ok=True)
        DAEMON.write_text(json.dumps(config, indent=2) + "\n")
        subprocess.run(["systemctl", "restart", "docker"], check=True)
        print("daemon.json written, Docker restarted:", json.dumps(WANTED))
    ids = subprocess.run(["docker", "network", "ls", "-q"], capture_output=True, text=True, check=True).stdout.split()
    for net in ids:
        name, subnets = subprocess.run(
            ["docker", "network", "inspect", "-f", "{{.Name}} {{range .IPAM.Config}}{{.Subnet}} {{end}}", net],
            capture_output=True, text=True, check=True).stdout.split(" ", 1)
        for subnet in subnets.split():
            if ipaddress.ip_network(subnet, strict=False).overlaps(PRIVATE_172):
                print(f"still in 172.16.0.0/12: network {name} {subnet} (recreate it: docker compose down, then up)")


if __name__ == "__main__":
    main()
