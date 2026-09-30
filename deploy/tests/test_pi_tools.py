"""Offline tests of the Raspberry Pi helper (deploy/pi.py)."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pi import ONBOARD_LED, blink_commands  # noqa: E402


def test_blink_toggles_one_gpio_line_after_it_is_claimed():
    commands = blink_commands(line=17, period_ms=250)
    assert (commands[0].op, commands[0].resource, commands[0].name) == ("create_fb", "", "RES")
    assert (commands[-1].op, commands[-1].name) == ("start", "RES")
    created = {c.name: c.type for c in commands[1:] if c.op == "create_fb"}
    assert created == {"Led": "eclipse4diac::io::gpiochip::GPIOChip", "Out": "eclipse4diac::io::QX",
                       "Cycle": "iec61499::events::E_CYCLE", "Toggle": "iec61499::events::E_T_FF"}
    written = {c.destination: c.value for c in commands if c.op == "write"}
    assert (written["Led.LineNumber"], written["Led.ReadWriteMode"], written["Cycle.DT"]) == ("17", "1", "T#250ms")
    assert written["Led.VALUE"] == '"Led"' and written["Out.PARAMS"] == "'Led'"   # same handle name
    wired = [(c.source, c.destination) for c in commands if c.op == "connect"]
    # The line is claimed before QX binds to it, and the cycle starts only after both.
    assert wired.index(("START.COLD", "Led.INIT")) < wired.index(("Led.INITO", "Out.INIT"))
    assert ("Out.INITO", "Cycle.START") in wired and ("Toggle.Q", "Out.OUT") in wired


def test_default_led_is_the_onboard_act_led():
    assert ONBOARD_LED == 42
