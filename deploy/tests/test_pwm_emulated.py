"""FORTE's pwmsysfs module (runtime/forte-patches) on the Raspberry Pi binary, run under arm64
emulation in Docker against a fake /sys/class/pwm tree: a PWMChip configures the channel and a QW
sets the duty cycle; so does an IO_AO whose address is the channel's handle.

    runtime/build-modules.ps1 -Config pi/modules-pi -SkipValidate
    python -m pytest deploy/tests/test_pwm_emulated.py --pi-forte-exe runtime/fbe/build/modules-pi/output/bin/forte
"""
from contextlib import contextmanager
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


def res(**k) -> Command:
    return Command(resource="RES", **k)


@contextmanager
def emulated(pi_forte, tmp_path, fbs: dict[str, str], values: dict[str, str], events: list[tuple[str, str]]):
    """The Pi's FORTE in an arm64 container, booting a PWMChip ("Chip", handle "Pwm" on channel 1 of
    a fake sysfs tree, initialised from START.COLD) and ``fbs``; yields the channel's folder and a
    management client once the channel is configured."""
    channel = tmp_path / "fake/class/pwm/pwmchip0/pwm1"      # already exported: no udev in the fake tree
    channel.mkdir(parents=True)
    (tmp_path / "fake/class/pwm/pwmchip0/export").write_text("")
    for name in ["period", "duty_cycle", "enable", "polarity"]:
        (channel / name).write_text("0")
    (tmp_path / "bin").mkdir()
    shutil.copy(pi_forte, tmp_path / "bin/forte")
    chip = {"Chip.QI": "TRUE", "Chip.VALUE": '"Pwm"', "Chip.Channel": "1", "Chip.PeriodNs": "20000000",
            "Chip.SysfsRoot": '"/work/fake/class/pwm"'}
    program = [Command(op="create_fb", resource="", name="RES", type="iec61499::system::EMB_RES"),
               res(op="create_fb", name="Chip", type="eclipse4diac::io::pwmsysfs::PWMChip"),
               *[res(op="create_fb", name=n, type=t) for n, t in fbs.items()],
               *[res(op="write", destination=d, value=v) for d, v in {**chip, **values}.items()],
               *[res(op="connect", source=s, destination=d) for s, d in [("START.COLD", "Chip.INIT"), *events]],
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
            yield channel, client
    finally:
        subprocess.run(["docker", "rm", "-f", CONTAINER], capture_output=True)


def duty_becomes(channel: Path, duty: int, what: str):
    # Compared as numbers: the fake tree is plain files, so a shorter write leaves the old
    # tail ("0" over "20000000" reads "00000000"); real sysfs parses each write.
    deadline = time.monotonic() + 3
    while int((channel / "duty_cycle").read_text().strip() or -1) != duty:
        assert time.monotonic() < deadline, f"{what}: duty_cycle {(channel / 'duty_cycle').read_text()}"
        time.sleep(0.1)


def test_pwmchip_and_qw_write_the_duty_cycle(pi_forte, tmp_path):
    fbs = {"Out": "eclipse4diac::io::QW", "Cycle": "iec61499::events::E_CYCLE"}
    values = {"Out.QI": "TRUE", "Out.PARAMS": "'Pwm'", "Cycle.DT": "T#100ms"}
    events = [("Chip.INITO", "Out.INIT"), ("Out.INITO", "Cycle.START"), ("Cycle.EO", "Out.REQ")]
    with emulated(pi_forte, tmp_path, fbs, values, events) as (channel, client):
        for value, duty in [("WORD#32768", 10000152), ("WORD#65535", 20000000), ("WORD#0", 0)]:
            client.execute(res(op="write", destination="Out.OUT", value=value))
            duty_becomes(channel, duty, value)


def test_io_blocks_reach_the_point_their_address_names(pi_forte, tmp_path):
    """An IO_AO at the channel's handle drives it; an empty address is not connected; 'sim' is simulated."""
    fbs = {"Out": "modlib::IO_AO", "Off": "modlib::IO_DO", "Simulated": "modlib::IO_DI",
           "Cycle": "iec61499::events::E_CYCLE"}
    values = {"Out.Address": "'Pwm'", "Out.EN": "TRUE", "Off.Address": "''", "Simulated.Address": "'sim'",
              "Simulated.SimValue": "TRUE", "Cycle.DT": "T#100ms"}
    events = [("Chip.INITO", "Out.INIT"), ("Out.INITO", "Off.INIT"), ("Off.INITO", "Simulated.INIT"),
              ("Simulated.INITO", "Cycle.START"), ("Cycle.EO", "Out.REQ"), ("Cycle.EO", "Off.REQ"),
              ("Cycle.EO", "Simulated.REQ")]
    with emulated(pi_forte, tmp_path, fbs, values, events) as (channel, client):
        def read(port):
            return client.execute(res(op="read", source=port)).read_value(port)
        for value, duty in [("32768.0", 10000152), ("65535.0", 20000000), ("0.0", 0)]:
            client.execute(res(op="write", destination="Out.OUT", value=value))
            duty_becomes(channel, duty, value)
        assert (read("Out.QO"), read("Off.QO")) == ("TRUE", "FALSE")
        assert (read("Simulated.QO"), read("Simulated.IN")) == ("TRUE", "TRUE")
