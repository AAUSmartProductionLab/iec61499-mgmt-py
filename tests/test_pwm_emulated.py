"""FORTE's pwmsysfs module (4diac/tools/forte-patches) on the Raspberry Pi binary, run under arm64
emulation in Docker against a fake /sys/class/pwm tree: a PWMChip configures the channel and a QW
sets the duty cycle.

    4diac/tools/build-modules.ps1 -Config pi/modules-pi -SkipValidate
    python -m pytest tests/test_pwm_emulated.py --pi-forte-exe 4diac/tools/fbe/build/modules-pi/output/bin/forte
"""
from pathlib import Path
import shutil
import socket
import subprocess
import time

import pytest

from conftest import free_port
from iec61499_mgmt.bootfile import boot_file
from iec61499_mgmt.protocol import Client, Command

CONTAINER = "forte-pwm-test"


@pytest.fixture
def pi_forte(request):
    exe = request.config.getoption("--pi-forte-exe")
    if not exe:
        pytest.skip("Pass --pi-forte-exe (the aarch64 build) to run the emulated PWM test")
    if shutil.which("docker") is None or subprocess.run(["docker", "version"], capture_output=True).returncode:
        pytest.skip("Docker with arm64 emulation is needed")
    return Path(exe).resolve(strict=True)


def test_pwmchip_and_qw_write_the_duty_cycle(pi_forte, tmp_path):
    channel = tmp_path / "fake/class/pwm/pwmchip0/pwm1"      # already exported: no udev in the fake tree
    channel.mkdir(parents=True)
    (tmp_path / "fake/class/pwm/pwmchip0/export").write_text("")
    for name in ["period", "duty_cycle", "enable", "polarity"]:
        (channel / name).write_text("0")
    (tmp_path / "bin").mkdir()
    shutil.copy(pi_forte, tmp_path / "bin/forte")
    res = lambda **k: Command(resource="RES", **k)
    program = [Command(op="create_fb", resource="", name="RES", type="iec61499::system::EMB_RES"),
               res(op="create_fb", name="Chip", type="eclipse4diac::io::pwmsysfs::PWMChip"),
               res(op="create_fb", name="Out", type="eclipse4diac::io::QW"),
               res(op="create_fb", name="Cycle", type="iec61499::events::E_CYCLE"),
               *[res(op="write", destination=d, value=v) for d, v in [
                   ("Chip.QI", "TRUE"), ("Chip.VALUE", '"Pwm"'), ("Chip.Channel", "1"), ("Chip.PeriodNs", "20000000"),
                   ("Chip.SysfsRoot", '"/work/fake/class/pwm"'), ("Out.QI", "TRUE"), ("Out.PARAMS", "'Pwm'"),
                   ("Cycle.DT", "T#100ms")]],
               *[res(op="connect", source=s, destination=d) for s, d in [
                   ("START.COLD", "Chip.INIT"), ("Chip.INITO", "Out.INIT"), ("Out.INITO", "Cycle.START"),
                   ("Cycle.EO", "Out.REQ")]],
               Command(op="start", resource="", name="RES")]
    (tmp_path / "bin/forte.fboot").write_bytes(boot_file(program).encode())
    port = free_port()
    subprocess.run(["docker", "rm", "-f", CONTAINER], capture_output=True)
    subprocess.run(["docker", "run", "-d", "--name", CONTAINER, "--platform", "linux/arm64", "-v", f"{tmp_path}:/work",
                    "-w", "/work/bin", "-p", f"{port}:61499", "alpine:3.20", "/work/bin/forte", "-c", "0.0.0.0:61499"],
                   capture_output=True, check=True)
    try:
        deadline = time.monotonic() + 30
        while (channel / "enable").read_text().strip() != "1":            # the controller configured the channel
            assert time.monotonic() < deadline, "PWM channel not enabled"
            time.sleep(0.2)
        assert (channel / "period").read_text().strip() == "20000000"
        time.sleep(1)                                                        # the Docker proxy accepts before FORTE listens
        with Client("127.0.0.1", port, timeout=10) as client:
            assert client.execute(res(op="read", source="Chip.QO")).read_value("Chip.QO") == "TRUE"
            # Compared as numbers: the fake tree is plain files, so a shorter write leaves the old
            # tail ("0" over "20000000" reads "00000000"); real sysfs parses each write.
            for value, duty in [("WORD#32768", 10000152), ("WORD#65535", 20000000), ("WORD#0", 0)]:
                client.execute(res(op="write", destination="Out.OUT", value=value))
                deadline = time.monotonic() + 3
                while int((channel / "duty_cycle").read_text().strip() or -1) != duty:
                    assert time.monotonic() < deadline, f"{value}: duty_cycle {(channel / 'duty_cycle').read_text()}"
                    time.sleep(0.1)
    finally:
        subprocess.run(["docker", "rm", "-f", CONTAINER], capture_output=True)
