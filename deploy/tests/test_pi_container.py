"""The Pi's FORTE container (deploy/pi/compose.yaml): its entrypoint turns the stepper's PWM off when
FORTE ends, also when FORTE crashes as it stops (FORTE 3.3.0 segfaults on stop, so the pwmsysfs
module's own clean-up never runs), and before FORTE starts.

The entrypoint is run as compose.yaml has it, in an Alpine container (as the Pi's image is), against
a fake /sys/class/pwm tree and a fake FORTE that enables the channel at its start and segfaults
when it is told to stop. Needs Docker; skipped without it.
"""
from pathlib import Path
import shutil
import subprocess
import sys
import time

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bench import OFF  # noqa: E402

COMPOSE = Path(__file__).resolve().parents[1] / "pi" / "compose.yaml"
CONTAINER = "forte-entrypoint-test"

# Stands in for /usr/local/bin/forte: says what it found at its start, enables the channel as FORTE's
# PWMChip does, and dies of a segmentation fault on SIGTERM as FORTE 3.3.0 does.
FAKE_FORTE = """#!/bin/sh
c=/hostsys/class/pwm/pwmchip0/pwm2
echo "fake forte $* found enable=$(cat $c/enable) duty_cycle=$(cat $c/duty_cycle)"
echo 1 > $c/enable
echo 250000 > $c/duty_cycle
trap 'kill -SEGV $$' TERM
while :; do sleep 0.1; done
"""


def entrypoint() -> list[str]:
    """The forte service's entrypoint with compose's interpolation done: $$ is a literal $."""
    found = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))["services"]["forte"]["entrypoint"]
    script = found[-1]
    assert "$" not in script.replace("$$", ""), "a single $ would be interpolated by docker compose"
    return [part.replace("$$", "$") for part in found]


@pytest.fixture
def docker():
    if shutil.which("docker") is None or subprocess.run(["docker", "version"], capture_output=True).returncode:
        pytest.skip("Docker is needed")
    subprocess.run(["docker", "rm", "-f", CONTAINER], capture_output=True)
    yield
    subprocess.run(["docker", "rm", "-f", CONTAINER], capture_output=True)


def test_the_pwm_is_off_after_forte_crashes_on_stop_and_before_it_starts(docker, tmp_path):
    channel = tmp_path / "pwm/pwmchip0/pwm2"
    channel.mkdir(parents=True)
    for name, value in {"period": "500000", "duty_cycle": "250000", "enable": "1"}.items():
        (channel / name).write_text(value + "\n")          # left running by a FORTE that was killed
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin/forte").write_bytes(FAKE_FORTE.encode())       # LF line ends, for sh
    shell, flag, script = entrypoint()
    # The fake FORTE is installed executable first; the entrypoint's shell then takes over as PID 1.
    setup = f'install -m 755 /fake/forte /usr/local/bin/forte && exec {shell} {flag} "$ENTRYPOINT"'
    subprocess.run(["docker", "run", "-d", "--name", CONTAINER, "-v", f"{tmp_path / 'pwm'}:/hostsys/class/pwm",
                    "-v", f"{tmp_path / 'bin'}:/fake:ro", "-e", f"ENTRYPOINT={script}", "--entrypoint", shell,
                    "alpine:3.20", flag, setup], capture_output=True, check=True)
    deadline = time.monotonic() + 30
    while "fake forte" not in (log := logs()):
        assert time.monotonic() < deadline, f"FORTE did not start: {log}"
        time.sleep(0.2)
    assert "fake forte -c 0.0.0.0:61499 found enable=0 duty_cycle=0" in log      # off before it started
    assert read(channel, "enable") == "1"                                           # FORTE enabled it

    subprocess.run(["docker", "stop", "-t", "10", CONTAINER], capture_output=True, check=True)
    assert (read(channel, "enable"), read(channel, "duty_cycle")) == ("0", "0")
    exit_code = subprocess.run(["docker", "inspect", "-f", "{{.State.ExitCode}}", CONTAINER],
                               capture_output=True, text=True, check=True).stdout.strip()
    assert exit_code == "139"                                    # FORTE's own exit status is kept


def test_the_bench_check_turns_off_what_the_entrypoint_turns_off():
    assert OFF in entrypoint()[-1]                 # deploy/bench.py's watchdog, the same loop


def logs() -> str:
    found = subprocess.run(["docker", "logs", CONTAINER], capture_output=True, text=True)
    return found.stdout + found.stderr


def read(channel: Path, name: str) -> str:
    return (channel / name).read_text().strip()
