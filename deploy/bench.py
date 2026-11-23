"""Bench check of a module's linear axis on its Raspberry Pi: the home switch, homing and moves, every
motion under a watchdog. Only with someone at the bench: Reset and Home drive the axis to its switch.

    python deploy/bench.py status                     # no motion: the module, the axis and the PWM channels
    python deploy/bench.py switch                     # no motion: the home switch while you press it by hand
    python deploy/bench.py home                       # Reset, which homes the axis; stopped if not home in time
    python deploy/bench.py move --to 10               # MoveAxis 10 mm away from the switch, then Home
    python deploy/bench.py move --to 40 --stay        # ... and stay there, e.g. to measure a position
    python deploy/bench.py run --skill Capping --spec cell/modules/capping.yaml   # a module level skill
    python deploy/bench.py home --spec cell/modules/stoppering.yaml --limit 12

The module, its Pi, its axis (the equipment with a position), the axis's home switch and its speed
come from the module spec (default cell/modules/filling.yaml, target pi). A motion's watchdog is a
timer started before the motion is called: past its limit, or when an OPC UA call or read fails, it
turns every PWM channel off on the Pi over SSH (no OPC UA needed, so it works while the server
stalls) and then aborts the module. The motor then gets no step pulses until FORTE starts again
(cd ~/forte && docker compose restart), which enables its channels itself.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cell" / "sim"))
from modgen import SPECS, load                        # noqa: E402
from modgen.library import SKILL_STATES, STATES      # noqa: E402

SESSION = "bench"
PORT = 4840
# Every exported channel to duty 0 and disabled, as the container's entrypoint does when FORTE ends
# (deploy/pi/compose.yaml); through the running container, else through a new one.
OFF = ('for c in /hostsys/class/pwm/pwmchip*/pwm[0-9]*; do [ -d "$c" ] && '
       '{ echo 0 > "$c/duty_cycle"; echo 0 > "$c/enable"; }; done 2>/dev/null')
PWM_OFF = (f"docker exec forte sh -c '{OFF}' || docker run --rm -v /sys/class/pwm:/hostsys/class/pwm "
           f"-v /sys/devices/platform:/hostsys/devices/platform busybox:1.36 sh -c '{OFF}'")
PWM_STATE = ('for c in /sys/class/pwm/pwmchip*/pwm[0-9]*; do [ -d "$c" ] && '
             'echo "$c enable=$(cat $c/enable) duty_cycle=$(cat $c/duty_cycle) period=$(cat $c/period)"; done; true')


class Axis:
    """The module's linear axis as its spec describes it."""

    def __init__(self, spec):
        found = [(name, item.position) for name, item in spec.equipment.items() if getattr(item, "position", None)]
        if len(found) != 1:
            sys.exit(f"{spec.module} has {len(found)} axes with a position; this check takes one")
        self.name, position = found[0]
        self.home, self.speed, self.maximum = position.home, position.speed, position.maximum

    def seconds(self, distance: float) -> float:
        """How long a move over ``distance`` mm may take: at the axis's speed, plus 1.5 s."""
        return abs(distance) / self.speed + 1.5


class Bench:
    def __init__(self, args):
        from module_ua import ModuleUa
        self.spec = load(args.spec)
        target = self.spec.targets[args.target]
        self.host, self.user = args.host or target.host, args.user or target.user or "admin"
        self.axis = Axis(self.spec)
        self.ua = ModuleUa(PORT, self.spec.module, host=self.host)

    def value(self, item: str):
        return self.ua.value(f"Equipment/{self.axis.name}/{item}")

    def referenced(self):
        """Refuse a move when the axis was moved without the program: it counts its position by time (no
        encoder), so a carriage moved by hand off the switch still reads 0 mm, and a move to 40 mm would
        start from wherever it is. At 0 mm the switch must be pressed."""
        if not self.value("Homed"):
            sys.exit("Not referenced: home it first (python deploy/bench.py home)")
        if abs(self.value("ActualPosition")) < 0.5 and not self.value(self.axis.home):
            sys.exit(f"The axis reads 0 mm but {self.axis.home} is free: it was moved by hand. Home it first "
                     "(python deploy/bench.py home)")

    def show(self) -> str:
        home, homed, position = (self.value(i) for i in (self.axis.home, "Homed", "ActualPosition"))
        return f"{self.axis.home}={home!s:5} Homed={homed!s:5} Position={position:.1f} mm"

    def ssh(self, command: str) -> subprocess.CompletedProcess:
        return subprocess.run(["ssh", "-o", "BatchMode=yes", f"{self.user}@{self.host}", command],
                              capture_output=True, text=True, timeout=30)

    def pwm_off(self, why: str):
        print(f"\n!!! {why}: every PWM channel off over SSH", flush=True)
        done = self.ssh(PWM_OFF)
        print(f"    PWM off (exit {done.returncode}) {done.stderr.strip()}", flush=True)
        print("    No step pulses until FORTE starts again: cd ~/forte && docker compose restart", flush=True)

    def abort(self):
        try:
            print("    Abort ->", self.ua.call("Module/Abort", SESSION), flush=True)
        except Exception as e:
            print("    Abort failed:", e, flush=True)

    def guarded(self, limit: float, start, done, what: str) -> bool:
        """``start`` a motion under a timer started first; True once ``done()``. Past ``limit`` s, or
        when a call or a read fails, the PWM goes off over SSH and the module is aborted."""
        fired = threading.Event()
        timer = threading.Timer(limit, lambda: (fired.set(), self.pwm_off(f"{what} not done in {limit:.1f} s")))
        timer.start()
        t0 = time.monotonic()
        try:
            answer = start()
            print(f"{what} ->", answer, flush=True)
            if answer and answer[0] is False:           # refused: nothing moves
                timer.cancel()
                return False
            while not fired.is_set():
                print(f"  {time.monotonic() - t0:4.1f} s  {self.show()}", flush=True)
                if done():
                    timer.cancel()
                    print(f"OK: {what} after {time.monotonic() - t0:.1f} s | {self.show()}", flush=True)
                    return True
                time.sleep(0.1)
        except Exception as e:
            timer.cancel()
            if not fired.is_set():
                self.pwm_off(f"OPC UA failed during {what} ({e!r})")
            return False
        timer.join()
        self.abort()
        return False


def status(bench, args):
    print(f"{bench.spec.module} on {bench.host}: state {bench.ua.value('Module/State')} | {bench.show()}")
    print(bench.ssh(PWM_STATE).stdout.strip() or "no PWM channel exported")


def switch(bench, args):
    """No motion: print the home switch at every change, for up to 10 presses or 300 s."""
    print(f"No motion. Press and release {bench.axis.home} up to 10 times (300 s): free FALSE, pressed TRUE.",
          flush=True)
    last, presses, t0 = None, 0, time.monotonic()
    while time.monotonic() - t0 < 300 and presses < 10:
        try:
            now = bench.value(bench.axis.home)
        except Exception as e:                      # e.g. the OPC UA server stalled: connect again
            print(f"  {time.monotonic() - t0:5.1f} s  connection lost ({type(e).__name__}), connecting again",
                  flush=True)
            from module_ua import ModuleUa
            bench.ua = ModuleUa(PORT, bench.spec.module, host=bench.host)
            continue
        if now != last:
            presses += last is True and now is False
            print(f"  {time.monotonic() - t0:5.1f} s  {bench.axis.home} = {now}"
                  + (f"   (press {presses})" if now is False and presses else ""), flush=True)
            last = now
        time.sleep(0.02)
    print(f"{presses} presses and releases seen")


def home(bench, args):
    """Home the axis: by the Home skill in Execute, else by Reset (its Resetting procedure homes it)."""
    if bench.value(bench.axis.home):
        sys.exit(f"{bench.axis.home} is TRUE already: move the carriage off the switch first (or a wire is open)")
    limit = args.limit or bench.axis.seconds(bench.axis.maximum) + 1
    running = bench.ua.value("Module/State") == STATES["Execute"]
    how, what = ("Skills/Home/Start", "Home") if running else ("Module/Reset", "Reset")
    if not bench.guarded(limit, lambda: bench.ua.call(how, SESSION), lambda: bench.value(bench.axis.home),
                         f"{what} (the switch reached within {limit:.1f} s)"):
        print(f"    Farther than {bench.axis.speed * (limit - 2.5):.0f} mm from the switch? "
              "Run again with a longer --limit.")
        return
    if not running:
        bench.ua.expect("Module/State", STATES["Idle"], timeout=15)
        print("Module Idle |", bench.show())


def move(bench, args):
    """MoveAxis to ``--to`` mm from the switch, then Home unless ``--stay``."""
    bench.referenced()
    if bench.ua.value("Module/State") != STATES["Execute"]:
        print("Start ->", bench.ua.call("Module/Start", SESSION))
        bench.ua.expect("Module/State", STATES["Execute"], timeout=10)
    there = lambda: (abs(bench.value("ActualPosition") - args.to) < 0.5                  # noqa: E731
                     and bench.ua.value("Skills/MoveAxis/State") == SKILL_STATES["Succeeded"])
    limit = bench.axis.seconds(args.to - bench.value("ActualPosition"))
    if not bench.guarded(limit, lambda: bench.ua.call("Skills/MoveAxis/Start", SESSION, args.to), there,
                         f"MoveAxis {args.to} mm"):
        return
    if args.stay:
        print(f"Staying at {args.to} mm. Home it afterwards: python deploy/bench.py home")
        return
    bench.guarded(bench.axis.seconds(args.to), lambda: bench.ua.call("Skills/Home/Start", SESSION),
                  lambda: bench.value(bench.axis.home), "Home (the switch reached)")


def run(bench, args):
    """A module level skill (``--skill``) once, with its parameters' defaults, until it succeeds."""
    if args.skill not in bench.spec.composites:
        sys.exit(f"{bench.spec.module} has no module level skill {args.skill}: {', '.join(bench.spec.composites)}")
    bench.referenced()
    if bench.ua.value("Module/State") != STATES["Execute"]:
        print("Start ->", bench.ua.call("Module/Start", SESSION))
        bench.ua.expect("Module/State", STATES["Execute"], timeout=10)
    params = [p.default for p in bench.spec.composites[args.skill].parameters.values()]
    state = f"Skills/{args.skill}/State"
    succeeded = lambda: bench.ua.value(state) == SKILL_STATES["Succeeded"]      # noqa: E731
    # Down the whole travel and back, plus what the skill waits for (a crimp, a dose).
    limit = args.limit or 2 * bench.axis.seconds(bench.axis.maximum) + 10
    bench.guarded(limit, lambda: bench.ua.call(f"Skills/{args.skill}/Start", SESSION, *params), succeeded,
                  f"{args.skill} (done within {limit:.1f} s)")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("stage", choices=["status", "switch", "home", "move", "run"])
    parser.add_argument("--spec", default=str(SPECS / "filling.yaml"), help="module spec (its target names the Pi)")
    parser.add_argument("--target", default="pi")
    parser.add_argument("--host", help="default: the target's host in the spec")
    parser.add_argument("--user", help="SSH login; default: the target's user in the spec")
    parser.add_argument("--limit", type=float, help="home: seconds before the watchdog stops the axis "
                                                    "(default: the axis's whole travel at its speed, plus 2.5 s)")
    parser.add_argument("--to", type=float, default=10.0, help="move: the position in mm from the switch")
    parser.add_argument("--stay", action="store_true", help="move: do not home afterwards")
    parser.add_argument("--skill", help="run: the module level skill to run (its parameters at their defaults)")
    args = parser.parse_args()
    bench = Bench(args)
    stage = {"status": status, "switch": switch, "home": home, "move": move, "run": run}[args.stage]
    occupy = args.stage in ("home", "move", "run")
    try:
        if occupy:
            print("Occupy ->", bench.ua.call("Occupation/Occupy", SESSION))
        stage(bench, args)
    finally:
        if occupy:
            try:
                print("Release ->", bench.ua.call("Occupation/Release", SESSION))
            except Exception as e:
                print("Release failed:", e)
        bench.ua.close()


if __name__ == "__main__":
    main()
