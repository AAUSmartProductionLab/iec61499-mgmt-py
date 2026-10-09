"""Raspberry Pi 4 helper: install the cross-built FORTE, blink an LED, run a module, read the log.

    python deploy/pi.py install                  # copy FORTE to the Pi, build and start its container
    python deploy/pi.py stop | start | status    # the FORTE container
    python deploy/pi.py blink                    # blink the green on-board LED (ACT)
    python deploy/pi.py blink --line 17          # blink an LED on header pin 11 (GPIO17)
    python deploy/pi.py module                   # run the module (cell/modules/filling.yaml) on its Pi
    python deploy/pi.py module --spec cell/modules/stoppering.yaml --print   # show the boot file
    python deploy/pi.py log

The Pi's address and login are the ``pi`` target's ``host`` and ``user`` in the module spec
(cell/modules/filling.yaml), or ``--host``/``--user``. Any 64-bit Linux on the Pi works (Raspberry
Pi OS, Ubuntu); the login needs SSH key access and read/write access to /dev/gpiochip0 (group
``gpio`` on Raspberry Pi OS, ``dialout`` on Ubuntu). Build FORTE first:
``runtime/build-modules.ps1 -Config pi/modules-pi -SkipValidate``.

FORTE runs in a Docker container (deploy/pi/compose.yaml, copied to ~/forte on the Pi) with
host networking and /dev/gpiochip0; it restarts after a reboot unless stopped. The login needs
to be in group ``docker``. On the Pi: ``cd ~/forte && docker compose ps | logs -f | stop | start``.
sudo is needed only for the on-board LED; it asks on the terminal or reads ``PI_SUDO_PASSWORD``.

A program is deployed as FORTE's boot file and the container is restarted, so every run starts
from a fresh process and the last program also runs after a reboot. Deleting a running resource
over the management protocol is avoided on purpose: FORTE 3.3.0 crashed deleting a resource
with a GPIOChip, and it shuts itself down on a KILL of a resource that does not exist.

On-board LED: the green ACT LED is GPIO42 of gpiochip0, but the kernel's LED driver holds it.
``blink`` without ``--line`` unbinds that driver (both on-board LEDs stop showing SD card and
power activity until the next reboot) so FORTE can take the line. An external LED needs a
resistor: GPIO17 (pin 11) -> 330 ohm -> LED anode, LED cathode -> GND (pin 9).
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

from iec61499_mgmt.bootfile import boot_file, deployment
from iec61499_mgmt.protocol import Client, Command, ProtocolError
from iec61499_mgmt.sysfile import load_application
from modgen import SPECS, load, system_file
from modgen.module import app_name

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
SPEC = SPECS / "filling.yaml"
FORTE = ROOT / "runtime" / "fbe" / "build" / "modules-pi" / "output" / "bin" / "forte"
DOCKER = TOOLS / "pi"          # Dockerfile, compose.yaml, .dockerignore
GPIOCHIP = "eclipse4diac::io::gpiochip::GPIOChip"
PWMCHIP = "eclipse4diac::io::pwmsysfs::PWMChip"
ONBOARD_LED = 42  # Pi 4: ACT LED on gpiochip0
LEDS_DRIVER = "/sys/bus/platform/drivers/leds-gpio"

def ssh(args, command, stdin=None):
    """Run a shell command on the Pi; ``stdin`` is sent as UTF-8 bytes with LF line ends.

    A text-mode pipe on Windows would turn LF into CRLF, and FORTE's boot-file loader only ends
    a command at "/>\n" or "</Request>\n".
    """
    print(f"[{args.host}] {command.splitlines()[0]}")
    data = stdin.encode("utf-8") if stdin is not None else None
    subprocess.run(["ssh", f"{args.user}@{args.host}", command], input=data, check=True)


def sudo(args, command):
    """Run ``command`` as root on the Pi: password from PI_SUDO_PASSWORD, else asked on the terminal."""
    password = os.environ.get("PI_SUDO_PASSWORD")
    if password is None:
        print(f"[{args.host}] sudo {command}")
        subprocess.run(["ssh", "-t", f"{args.user}@{args.host}", f"sudo sh -c '{command}'"], check=True)
    else:
        ssh(args, f"sudo -S -p '' sh -c '{command}'", stdin=password + "\n")


def compose(args, command):
    """Run ``docker compose <command>`` in ~/forte on the Pi."""
    ssh(args, f"cd ~/forte && docker compose {command}")


def install(args):
    """Copy FORTE and its container definition to ~/forte on the Pi, build the image and start it."""
    forte = Path(args.forte)
    if not forte.is_file():
        sys.exit(f"{forte} not found; build it with build-modules.ps1 -Config pi/modules-pi first")
    # Earlier installs ran FORTE as a systemd user service; it would hold the ports.
    ssh(args, "systemctl --user disable --now forte 2>/dev/null; rm -f ~/.config/systemd/user/forte.service; "
              "mkdir -p ~/forte/boot && touch ~/forte/boot/forte.fboot")
    # The image takes the binary as "forte", whatever the file is called here (runtime/bin/forte-aarch64).
    subprocess.run(["scp", "-q", str(forte), f"{args.user}@{args.host}:forte/forte"], check=True)
    files = [DOCKER / f for f in ("Dockerfile", "compose.yaml", ".dockerignore")]
    subprocess.run(["scp", "-q", *map(str, files), f"{args.user}@{args.host}:forte/"], check=True)
    compose(args, "up -d --build --force-recreate && docker compose ps")


def blink_commands(line: int, chip: int = 0, period_ms: int = 500, resource: str = "RES") -> list[Command]:
    """Resource with one GPIO output toggled every ``period_ms``: GPIOChip line -> QX <- E_T_FF <- E_CYCLE."""
    fbs = {"Led": GPIOCHIP, "Out": "eclipse4diac::io::QX",
           "Cycle": "iec61499::events::E_CYCLE", "Toggle": "iec61499::events::E_T_FF"}
    # The GPIOChip handle name (VALUE, WSTRING) is what QX.PARAMS (STRING) refers to.
    # ReadWriteMode 1 = push-pull output.
    values = {"Led.QI": "TRUE", "Led.VALUE": '"Led"', "Led.ChipNumber": str(chip), "Led.LineNumber": str(line),
              "Led.ReadWriteMode": "1", "Out.QI": "TRUE", "Out.PARAMS": "'Led'", "Cycle.DT": f"T#{period_ms}ms"}
    # The line must exist before QX binds to it: GPIOChip INITO -> QX INIT -> start the cycle.
    events = [("START.COLD", "Led.INIT"), ("START.WARM", "Led.INIT"), ("Led.INITO", "Out.INIT"),
              ("Out.INITO", "Cycle.START"), ("Cycle.EO", "Toggle.CLK"), ("Toggle.EO", "Out.REQ")]
    data = [("Toggle.Q", "Out.OUT")]
    commands = [Command(op="create_fb", resource="", name=resource, type="iec61499::system::EMB_RES")]
    commands += [Command(op="create_fb", resource=resource, name=n, type=t) for n, t in fbs.items()]
    commands += [Command(op="write", resource=resource, destination=d, value=v) for d, v in values.items()]
    commands += [Command(op="connect", resource=resource, source=s, destination=d) for s, d in events + data]
    commands.append(Command(op="start", resource="", name=resource))
    return commands


def wait_port(host: str, port: int, timeout: float = 20):
    """Wait until FORTE accepts management connections again."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            with socket.create_connection((host, port), timeout=1):
                return
        except OSError:
            if time.monotonic() > deadline:
                raise TimeoutError(f"FORTE on {host}:{port} did not come back")
            time.sleep(0.5)


def gpio_report(host: str, port: int, commands: list[Command], settle_s: float = 2.0):
    """Print QO and STATUS of every GPIOChip line and PWMChip channel: whether FORTE got it."""
    time.sleep(settle_s)
    lines = [c.name for c in commands if c.op == "create_fb" and c.type in (GPIOCHIP, PWMCHIP)]
    resource = commands[0].name
    ok = True
    with Client(host, port) as client:
        for line in lines:
            try:
                qo, status = (client.execute(Command(op="read", resource=resource, source=f"{line}.{p}"))
                              .read_value(f"{line}.{p}") for p in ("QO", "STATUS"))
            except ProtocolError:          # empty STATUS: INIT has not reached this line yet
                qo, status = "?", "not initialised yet"
            ok &= qo == "TRUE"
            print(f"  {line}: QO={qo} {status}")
    if not ok:
        # A line that fails is retried 5 times (1+2+3+4 s) before the INIT chain moves on.
        print("  A line was not acquired: see 'pi.py log' (busy line, wrong chip, or FORTE not in group gpio)")


def run(args, commands: list[Command]):
    """Make ``commands`` FORTE's boot file on the Pi, restart the service and report the GPIO lines."""
    ssh(args, "cat > ~/forte/boot/forte.fboot && cd ~/forte && docker compose restart", stdin=boot_file(commands))
    wait_port(args.host, args.port)
    gpio_report(args.host, args.port, commands)


def blink(args):
    """Blink one GPIO line."""
    line = ONBOARD_LED if args.line is None else args.line
    commands = blink_commands(line, args.chip, args.period_ms)
    if args.print:
        sys.stdout.buffer.write(boot_file(commands).encode("utf-8"))
        return
    if args.line is None:
        # Free GPIO42 from the kernel's LED driver (bound as "leds"); skipped once unbound.
        sudo(args, f"[ ! -e {LEDS_DRIVER}/leds ] || echo leds > {LEDS_DRIVER}/unbind")
    run(args, commands)
    print(f"Blinking gpiochip{args.chip} line {line} every {args.period_ms} ms on {args.host}")


def module(args):
    """Run the module's application for the target (replaces whatever runs on the Pi)."""
    spec = load(args.spec)
    app = load_application(system_file(spec.project), app_name(spec, args.target))
    commands = deployment(app)
    if args.print:
        sys.stdout.buffer.write(boot_file(commands).encode("utf-8"))
        return
    run(args, commands)
    print(f"{spec.module} ({args.target}) runs on {args.host}: OPC UA opc.tcp://{args.host}:4840{spec.opcua_root}")


def log(args):
    """Show the FORTE container log."""
    compose(args, f"logs --no-color --tail {args.lines}")


def stop(args):
    """Stop the FORTE container (it stays stopped after a reboot)."""
    compose(args, "stop")


def start(args):
    """Start the FORTE container again."""
    compose(args, "start")


def status(args):
    """Show the FORTE container."""
    compose(args, "ps")


def main():
    """Parse arguments and run one subcommand."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    for name, fn in [("install", install), ("blink", blink), ("module", module), ("log", log),
                     ("stop", stop), ("start", start), ("status", status)]:
        sub = commands.add_parser(name)
        sub.set_defaults(fn=fn)
        sub.add_argument("--spec", default=str(SPEC), help="Module spec (its target names the Pi)")
        sub.add_argument("--target", default="pi", help="Target in the module spec")
        sub.add_argument("--host", help="Default: the target's host in the module spec")
        sub.add_argument("--user", help="SSH login; default: the target's user in the module spec")
        sub.add_argument("--port", type=int, default=61499, help="FORTE management port")
        if name == "install":
            sub.add_argument("--forte", default=str(FORTE))
        if name == "blink":
            sub.add_argument("--line", type=int, help=f"GPIO (BCM) line; default: on-board ACT LED ({ONBOARD_LED})")
            sub.add_argument("--chip", type=int, default=0)
            sub.add_argument("--period-ms", type=int, default=500)
        if name in ("blink", "module"):
            sub.add_argument("--print", action="store_true", help="Print the boot file, send nothing")
        if name == "log":
            sub.add_argument("--lines", type=int, default=50)
    args = parser.parse_args()
    target = load(args.spec).targets[args.target]
    args.host, args.user = args.host or target.host, args.user or target.user or "pi"
    args.fn(args)


if __name__ == "__main__":
    main()
