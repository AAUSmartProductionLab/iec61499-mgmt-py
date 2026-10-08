#!/usr/bin/env python3
"""Bench test of a stepper driver (Step, Dir, Enable) on a Raspberry Pi's header, without FORTE.

Run it on the Pi, to tell a wiring or hardware fault from a software one. Stop FORTE first, it
holds the pins:  cd ~/forte && docker compose stop

    python3 steptest.py hold 10                # driver on for 10 s, no steps: the shaft should be stiff
    python3 steptest.py steps 400              # 400 steps at 200 a second, pulsed by this script
    python3 steptest.py steps 400 --dir 1 --hz 500
    python3 steptest.py loopback               # do pulses leave the Step pin? (jumper Step -> the test input)
    sudo python3 steptest.py pwm 2             # 2 s of the hardware PWM that FORTE steps with (1 kHz)
    sudo python3 steptest.py pwm-loopback      # count that PWM's pulses (same jumper)

The pins are those of the module descriptions (cell/modules): Step GPIO18 (header pin 12), Dir
GPIO27 (pin 13), Enable GPIO17 (pin 11, low is on), test input GPIO23 (pin 16). Other pins:
--step, --dir-pin, --enable, --input; a driver whose enable is high for on: --enable-high.

Do the two pwm tests first after a boot: once this script has pulsed the Step pin itself, the pin
is an ordinary output and the hardware PWM no longer reaches it until the Pi is rebooted. Reboot
before FORTE is started again:  sudo reboot  (FORTE then starts by itself).

Needs gpiozero with lgpio (sudo apt install python3-gpiozero python3-lgpio) and access to
/dev/gpiochip0 (group dialout on Ubuntu, gpio on Raspberry Pi OS, or sudo).
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


def forte_runs() -> bool:
    """FORTE's container holds the lines: nothing here would work beside it."""
    try:
        found = subprocess.run(["docker", "ps", "--filter", "name=^forte$", "--format", "{{.Names}}"],
                               capture_output=True, text=True, timeout=10)
        return "forte" in found.stdout
    except (OSError, subprocess.SubprocessError):
        return False


def devices(args, step_by_gpio: bool):
    from gpiozero import Device, DigitalOutputDevice
    from gpiozero.pins.lgpio import LGPIOFactory
    # The header is chip 0 on a Pi 4 and on a Pi 5 with a current kernel (older ones: 4).
    chip = 0 if Path("/dev/gpiochip0").exists() and not Path("/dev/gpiochip4").exists() else (4 if pi5() else 0)
    Device.pin_factory = LGPIOFactory(chip=chip)
    # Off at first: for a driver that is on while its enable is low, the pin starts high.
    enable = DigitalOutputDevice(args.enable, active_high=args.enable_high, initial_value=False)
    direction = DigitalOutputDevice(args.dir_pin, initial_value=bool(args.dir))
    step = DigitalOutputDevice(args.step, initial_value=False) if step_by_gpio else None
    return enable, direction, step


def pulses(step, count: int, hz: float):
    half = 0.5 / hz
    for _ in range(count):
        step.on()
        time.sleep(half)
        step.off()
        time.sleep(half)


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
    from gpiozero import DigitalInputDevice
    seen = [0]
    listener = DigitalInputDevice(args.input, pull_up=False)

    def one():
        seen[0] += 1
    listener.when_activated = one
    make_pulses()
    time.sleep(0.2)
    listener.close()
    print(f"{seen[0]} pulses seen on GPIO{args.input}, about {expected} sent on GPIO{args.step}")
    if seen[0] == 0:
        print("none arrived: is the jumper between the Step pin and the test input in? Otherwise the pin gives no pulses.")
    elif seen[0] < 0.8 * expected:
        print("fewer than sent: some are missed by this script's counting at this rate; the pin does pulse.")
    else:
        print("the Step pin gives its pulses.")
    return 0 if seen[0] else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("what", choices=["hold", "steps", "loopback", "pwm", "pwm-loopback"])
    parser.add_argument("amount", nargs="?", type=float, help="hold, pwm: seconds; steps: how many")
    parser.add_argument("--hz", type=float, default=200.0, help="steps a second (steps, loopback)")
    parser.add_argument("--dir", type=int, choices=[0, 1], default=0, help="level of the Dir pin")
    parser.add_argument("--step", type=int, default=18)
    parser.add_argument("--dir-pin", type=int, default=27)
    parser.add_argument("--enable", type=int, default=17)
    parser.add_argument("--input", type=int, default=23)
    parser.add_argument("--enable-high", action="store_true", help="the driver is on while its enable is high")
    args = parser.parse_args(argv)
    if forte_runs():
        sys.exit("FORTE is running and holds the pins. Stop it first: cd ~/forte && docker compose stop")

    by_gpio = args.what in ("steps", "loopback")
    enable, direction, step = devices(args, by_gpio)
    level = "high" if args.enable_high else "low"
    try:
        if args.what == "hold":
            seconds = args.amount or 10
            enable.on()
            print(f"Enable (GPIO{args.enable}) is {level} for {seconds:g} s, no steps: the shaft should be stiff now")
            time.sleep(seconds)
        elif args.what == "steps":
            count = int(args.amount or 400)
            enable.on()
            time.sleep(0.05)
            print(f"{count} steps at {args.hz:g} a second, Dir (GPIO{args.dir_pin}) {'high' if args.dir else 'low'}, "
                  f"Enable {level}: {count / args.hz:.1f} s")
            pulses(step, count, args.hz)
        elif args.what == "loopback":
            hz = min(args.hz, 100.0)                      # slow enough to count every one here
            return counted(args, lambda: pulses(step, 200, hz), 200)
        else:
            if args.what == "pwm":
                seconds = args.amount or 2
                pwm = HardwarePwm(1_000_000)             # 1 kHz, as FORTE sets it
                enable.on()
                time.sleep(0.05)
                print(f"hardware PWM on GPIO{args.step}: 1000 steps a second for {seconds:g} s, Enable {level}")
                pwm.run(True)
                time.sleep(seconds)
                pwm.run(False)
            else:
                pwm = HardwarePwm(20_000_000)            # 50 a second: slow enough to count here

                def two_seconds():
                    pwm.run(True)
                    time.sleep(2.0)
                    pwm.run(False)
                return counted(args, two_seconds, 100)
    finally:
        enable.off()
        if by_gpio:
            print("The Step pin is an ordinary output now: reboot before FORTE or the pwm tests are used again.")
    print("done: Enable is off again")
    return 0


if __name__ == "__main__":
    sys.exit(main())
