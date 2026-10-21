#!/usr/bin/env python3
"""Bench test of a stepper driver (Step, Dir, Enable) on a Raspberry Pi's header, without FORTE.

Run it on the Pi, to tell a wiring or hardware fault from a software one. Stop FORTE first, it
holds the pins:  cd ~/forte && docker compose stop

    python steptest.py hold 10                 # driver on for 10 s, no steps: the shaft should be stiff
    python steptest.py steps 400               # 400 steps at 500 a second, pulsed by this script
    python steptest.py steps 1200 --dir 1 --hz 1000
    python steptest.py loopback                # do pulses leave the Step pin? (jumper Step -> the test input)
    sudo python steptest.py pwm 2              # 2 s of the hardware PWM that FORTE steps with (2 kHz)
    sudo python steptest.py pwm-loopback       # count that PWM's pulses (same jumper)

The pins are those of the module descriptions (cell/modules): Step GPIO18 (header pin 12), Dir
GPIO27 (pin 13), Enable GPIO17 (pin 11, low is on, as on a TB6600 with ENA- on GND), test input
GPIO23 (pin 16, the limit switch's). Other pins: --step, --dir-pin, --enable, --input; a driver
whose enable is high for on: --enable-high. On the filling axis (TB6600 at 4 microsteps, 5 mm ball
screw) 160 steps are 1 mm, so 400 steps are 2.5 mm.

Do the two pwm tests first after a boot: once this script has pulsed the Step pin itself, the pin
is an ordinary output and the hardware PWM no longer reaches it until the Pi is rebooted. Reboot
before FORTE is started again:  sudo reboot  (FORTE then starts by itself).

Needs the gpiod bindings, which install without sudo into a venv:

    python3 -m venv --without-pip ~/iotest && curl -sS https://bootstrap.pypa.io/get-pip.py | ~/iotest/bin/python
    ~/iotest/bin/pip install gpiod                     # then: ~/iotest/bin/python steptest.py ...

and access to /dev/gpiochip0 (group dialout on Ubuntu, gpio on Raspberry Pi OS, or sudo).
"""
import argparse
from pathlib import Path
import subprocess
import sys
import time

PWM = Path("/sys/class/pwm/pwmchip0")


def pi5() -> bool:
    try:
        return "Raspberry Pi 5" in Path("/proc/device-tree/model").read_text()
    except OSError:
        return False


def chip() -> str:
    """The header's GPIO chip: 0 on a Pi 4 and on a Pi 5 with a current kernel (older ones: 4)."""
    return "/dev/gpiochip4" if pi5() and Path("/dev/gpiochip4").exists() and not Path("/dev/gpiochip0").exists() \
        else "/dev/gpiochip0"


def forte_runs() -> bool:
    """FORTE's container holds the lines: nothing here would work beside it."""
    try:
        found = subprocess.run(["docker", "ps", "--filter", "name=^forte$", "--format", "{{.Names}}"],
                               capture_output=True, text=True, timeout=10)
        return "forte" in found.stdout
    except (OSError, subprocess.SubprocessError):
        return False


class Pins:
    """Enable, Dir and (when this script pulses it) Step as outputs; Enable starts off."""

    def __init__(self, args, step_by_gpio: bool):
        import gpiod
        from gpiod.line import Direction, Value
        self.on, self.off = Value.ACTIVE, Value.INACTIVE
        self.args = args
        self.enable_on = self.on if args.enable_high else self.off
        self.enable_off = self.off if args.enable_high else self.on
        config = {args.enable: gpiod.LineSettings(direction=Direction.OUTPUT, output_value=self.enable_off),
                  args.dir_pin: gpiod.LineSettings(direction=Direction.OUTPUT,
                                                   output_value=self.on if args.dir else self.off)}
        if step_by_gpio:
            config[args.step] = gpiod.LineSettings(direction=Direction.OUTPUT, output_value=self.off)
        self.request = gpiod.request_lines(chip(), consumer="steptest", config=config)
        self.step_by_gpio = step_by_gpio

    def enable(self, on: bool):
        self.request.set_value(self.args.enable, self.enable_on if on else self.enable_off)

    def pulses(self, count: int, hz: float):
        half = 0.5 / hz
        for _ in range(count):
            self.request.set_value(self.args.step, self.on)
            time.sleep(half)
            self.request.set_value(self.args.step, self.off)
            time.sleep(half)

    def release(self):
        self.enable(False)
        if self.step_by_gpio:
            self.request.set_value(self.args.step, self.off)
        self.request.release()


class HardwarePwm:
    """The PWM channel of the Step pin through sysfs (root), as FORTE uses it."""

    def __init__(self, period_ns: int):
        self.channel = PWM / f"pwm{2 if pi5() else 0}"       # GPIO18: channel 2 on a Pi 5, 0 on a Pi 4
        if not PWM.exists():
            sys.exit("no PWM chip: is 'dtoverlay=pwm-2chan' in /boot/firmware/config.txt, and the Pi rebooted since?")
        if not self.channel.exists():
            (PWM / "export").write_text(self.channel.name[3:])
            time.sleep(0.2)
        (self.channel / "enable").write_text("0") if (self.channel / "enable").read_text().strip() == "1" else None
        (self.channel / "duty_cycle").write_text("0")
        (self.channel / "period").write_text(str(period_ns))

    def run(self, on: bool):
        period = int((self.channel / "period").read_text())
        (self.channel / "duty_cycle").write_text(str(period // 2 if on else 0))
        (self.channel / "enable").write_text("1")


def counted(args, make_pulses, expected: int) -> int:
    """Count rising edges on the test input while ``make_pulses`` runs."""
    import gpiod
    from gpiod.line import Direction, Edge
    settings = gpiod.LineSettings(direction=Direction.INPUT, edge_detection=Edge.RISING)
    seen = 0
    with gpiod.request_lines(chip(), consumer="steptest-count", config={args.input: settings}) as listener:
        make_pulses()
        time.sleep(0.2)
        while listener.wait_edge_events(0):
            seen += len(listener.read_edge_events())
    print(f"{seen} pulses seen on GPIO{args.input}, about {expected} sent on GPIO{args.step}")
    if seen == 0:
        print("none arrived: is the jumper between the Step pin and the test input in? Otherwise the pin gives no pulses.")
    elif seen < 0.8 * expected:
        print("fewer than sent: the input missed some at this rate; the pin does pulse.")
    else:
        print("the Step pin gives its pulses.")
    return 0 if seen else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("what", choices=["hold", "steps", "loopback", "pwm", "pwm-loopback"])
    parser.add_argument("amount", nargs="?", type=float, help="hold, pwm: seconds; steps: how many")
    parser.add_argument("--hz", type=float, default=500.0, help="steps a second (steps, loopback; pwm: default 2000)")
    parser.add_argument("--dir", type=int, choices=[0, 1], default=0, help="level of the Dir pin")
    parser.add_argument("--step", type=int, default=18)
    parser.add_argument("--dir-pin", type=int, default=27)
    parser.add_argument("--enable", type=int, default=17)
    parser.add_argument("--input", type=int, default=23)
    parser.add_argument("--enable-high", action="store_true", help="the driver is on while its enable is high")
    args = parser.parse_args(argv)
    if args.what == "steps" and not 0 < (args.amount or 400) <= 10_000:
        parser.error("at most 10000 steps in one move")
    if forte_runs():
        sys.exit("FORTE is running and holds the pins. Stop it first: cd ~/forte && docker compose stop")

    by_gpio = args.what in ("steps", "loopback")
    pins = Pins(args, by_gpio)
    level = "high" if args.enable_high else "low"
    try:
        if args.what == "hold":
            seconds = args.amount or 10
            pins.enable(True)
            print(f"Enable (GPIO{args.enable}) is {level} for {seconds:g} s, no steps: the shaft should be stiff now")
            time.sleep(seconds)
        elif args.what == "steps":
            count = int(args.amount or 400)
            pins.enable(True)
            time.sleep(0.05)                              # the driver: enable and Dir settle before a step
            print(f"{count} steps at {args.hz:g} a second, Dir (GPIO{args.dir_pin}) {'high' if args.dir else 'low'}, "
                  f"Enable {level}: {count / args.hz:.1f} s")
            pins.pulses(count, args.hz)
        elif args.what == "loopback":
            hz = min(args.hz, 100.0)                      # slow enough to count every one here
            return counted(args, lambda: pins.pulses(200, hz), 200)
        elif args.what == "pwm":
            seconds = args.amount or 2
            hz = args.hz if args.hz != parser.get_default("hz") else 2000.0      # FORTE's rate on the filling axis
            pwm = HardwarePwm(round(1e9 / hz))
            pins.enable(True)
            time.sleep(0.05)
            print(f"hardware PWM on GPIO{args.step}: {hz:g} steps a second for {seconds:g} s, Enable {level}")
            pwm.run(True)
            time.sleep(seconds)
            pwm.run(False)
        else:
            pwm = HardwarePwm(20_000_000)                # 50 a second: slow enough to count here

            def two_seconds():
                pwm.run(True)
                time.sleep(2.0)
                pwm.run(False)
            return counted(args, two_seconds, 100)
    finally:
        pins.release()
        if by_gpio:
            print("The Step pin is an ordinary output now: reboot before FORTE or the pwm tests are used again.")
    print("done: Enable is off again")
    return 0


if __name__ == "__main__":
    sys.exit(main())
