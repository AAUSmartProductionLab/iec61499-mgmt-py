"""Module specification: the single source from which a module's 4diac types and system are generated.

A module has
- equipment IO: the only owners of IO points, each with a command table (commands may run in
  timed phases, e.g. a start boost or a brake pulse, and may take an argument such as an angle);
- skill primitives: one equipment command until a sensor condition (``ensures``) or a time
  (``after``) says done, with parameters, contract and timeout;
- module level skills (composites): a sequence of skill instances with its own parameters, and
  an optional stop sequence;
- procedures the module state manager runs while Resetting and Stopping.

Validation is fail-closed: every name an expression uses must be a signal of the skill's
equipment or one of its parameters, and every step must name a known skill.
"""
from __future__ import annotations

from pathlib import Path
import re
from typing import Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
import yaml

IDENT = r"^[A-Za-z][A-Za-z0-9_]*$"
Ident = Field(pattern=IDENT)
# ST words allowed in contract expressions besides signals and parameters.
ST_WORDS = {"AND", "OR", "XOR", "NOT", "TRUE", "FALSE", "MOD", "ABS"}
NUMERIC = {"LREAL", "REAL", "INT", "DINT", "UINT", "UDINT", "USINT"}
DURATION = r"^\d+(ms|s)$"
# Procedures the module state manager runs (the acting states of PackML it uses).
PROCEDURES = Literal["Resetting", "Stopping"]
# IO backends of the IO primitives (IO_DI, IO_DO, IO_AI, IO_AO): 1 is a local IO handle (GPIO line or PWM channel).
BACKENDS = {"sim": 0, "gpio": 1, "pwm": 1, "modbus": 2}
# Command code that changes no outputs (used to release an equipment item).
KEEP = 255


class Model(BaseModel):
    """Strict base model: unknown keys are errors."""
    model_config = ConfigDict(extra="forbid", frozen=True)


def names(expr: str) -> set[str]:
    """Identifiers used in an ST expression."""
    return set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", expr))


def ms(duration: str) -> int:
    """Milliseconds of ``200ms`` or ``2s``."""
    value = int(re.match(r"\d+", duration).group())
    return value if duration.endswith("ms") else value * 1000


class Gpio(Model):
    """One line of a Linux GPIO chip (/dev/gpiochip<chip>); on a Raspberry Pi 4 chip 0, BCM numbering."""
    line: int = Field(ge=0)
    chip: int = Field(default=0, ge=0)
    bias: Literal["none", "pull_up", "pull_down"] = "none"
    active_low: bool = False      # e.g. a switch to GND with pull-up: closed reads TRUE


class Pwm(Model):
    """One Linux PWM channel (/sys/class/pwm/pwmchip<chip>/pwm<channel>)."""
    channel: int = Field(ge=0)
    chip: int = Field(default=0, ge=0)
    period_ns: int = Field(default=1_000_000, gt=0)   # 1 kHz for motor drivers; 20 ms for servos


def line_only(value):
    """``gpio: 17`` is short for ``gpio: {line: 17}``."""
    return {"line": value} if isinstance(value, int) else value


class Input(Model):
    """Sensor of an equipment item: a digital (BOOL) or analog (LREAL) input."""
    type: Literal["BOOL", "LREAL"] = "BOOL"
    modbus: str | None = Field(default=None, pattern=r"^[di]\d+$")   # d<n> discrete input, i<n> input register
    gpio: Gpio | None = None                                          # digital inputs only
    scale: float = 1.0                                                # analog: engineering value per raw count
    sim: float | bool = 0                                             # value when simulated (backend sim)
    unit: str | None = None

    short_gpio = field_validator("gpio", mode="before")(line_only)

    @model_validator(mode="after")
    def kinds(self):
        """Digital inputs read discrete inputs, analog inputs read registers; GPIO lines are digital."""
        if self.modbus and (self.type == "BOOL") != self.modbus.startswith("d"):
            raise ValueError("BOOL inputs use d<n>, LREAL inputs i<n>")
        if self.gpio and self.type != "BOOL":
            raise ValueError("A GPIO line is digital: only BOOL inputs can use one")
        return self


class Output(Model):
    """Actuator output: digital (coil or GPIO line) or analog (holding register or PWM channel).

    Analog outputs are written as a raw word: ``raw = bias + value * gain``, clamped to 0..65535
    (PWM: the fraction of the period; e.g. duty 0..255 with gain 257).
    """
    type: Literal["BOOL", "LREAL"] = "BOOL"
    modbus: str | None = Field(default=None, pattern=r"^[ch]\d+$")  # c<n> coil, h<n> holding register
    gpio: Gpio | None = None
    pwm: Pwm | None = None
    gain: float = 1.0
    bias: float = 0.0
    minimum: float | None = None
    maximum: float | None = None
    unit: str | None = None

    short_gpio = field_validator("gpio", mode="before")(line_only)

    @model_validator(mode="after")
    def kinds(self):
        """Digital outputs use coils and GPIO lines, analog ones holding registers and PWM channels."""
        if self.modbus and (self.type == "BOOL") != self.modbus.startswith("c"):
            raise ValueError("BOOL outputs use c<n>, LREAL outputs h<n>")
        if self.gpio and self.type != "BOOL":
            raise ValueError("A GPIO line is digital: only BOOL outputs can use one")
        if self.pwm and self.type != "LREAL":
            raise ValueError("A PWM channel is analog: only LREAL outputs can use one")
        return self


class Phase(Model):
    """Output values of one command phase; outputs not listed are off (0). ``for``: phase duration."""
    model_config = ConfigDict(extra="allow", frozen=True, populate_by_name=True)
    duration: str | None = Field(default=None, alias="for", pattern=DURATION)

    def values(self) -> dict[str, bool | float | str]:
        """Output name -> value (bool, number or ``Arg``, the command's argument)."""
        return dict(self.model_extra or {})


def phases(value):
    """A command is a phase, a list of phases, or (short) a list of the BOOL outputs switched on."""
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return [{v: True for v in value}]
    return value


class Equipment(Model):
    """Physical equipment item: sole owner of its IO points and of the command table."""
    description: str = ""
    inputs: dict[str, Input] = Field(default_factory=dict)
    outputs: dict[str, Output] = Field(default_factory=dict)
    # Command name -> phases; the first command is the safe state (all off).
    commands: dict[str, list[Phase]]
    sim: dict = Field(default_factory=dict)   # kinematics for 4diac/tools/module_sim.py (not used by the generator)

    short_commands = field_validator("commands", mode="before")(
        classmethod(lambda cls, v: {k: phases(c) for k, c in v.items()}))

    @model_validator(mode="after")
    def check(self):
        """Names are identifiers; commands only set declared outputs with fitting values; the first is all-off."""
        for name in [*self.inputs, *self.outputs, *self.commands]:
            if not re.match(IDENT, name):
                raise ValueError(f"Not an identifier: {name}")
        if set(self.inputs) & set(self.outputs):
            raise ValueError("Input and output names overlap")
        if not self.commands:
            raise ValueError("An equipment item needs at least its safe command")
        first = next(iter(self.commands.values()))
        if len(first) != 1 or any(first[0].values().values()) or first[0].duration:
            raise ValueError("The first command must be the safe state with no outputs on")
        if len(self.commands) > 200:
            raise ValueError("Too many commands")
        for command, steps in self.commands.items():
            if not steps:
                raise ValueError(f"Command {command} has no phase")
            if steps[-1].duration:
                raise ValueError(f"Command {command}: the last phase holds and has no duration")
            for phase in steps:
                for output, value in phase.values().items():
                    if output not in self.outputs:
                        raise ValueError(f"Command {command} sets unknown output {output}")
                    kind = self.outputs[output].type
                    if kind == "BOOL" and not isinstance(value, bool):
                        raise ValueError(f"Command {command}: {output} is BOOL")
                    if kind == "LREAL" and not (isinstance(value, (int, float)) and not isinstance(value, bool)
                                                or value == "Arg"):
                        raise ValueError(f"Command {command}: {output} takes a number or Arg")
        return self

    def code(self, command: str) -> int:
        """USINT code of a command (its position in the table)."""
        return list(self.commands).index(command)


class Parameter(Model):
    """Skill parameter: type, unit, range and the default an instance starts with."""
    type: Literal["LREAL", "INT", "DINT", "UINT", "BOOL"] = "LREAL"
    unit: str | None = None
    minimum: float | None = None
    maximum: float | None = None
    default: float | int | bool
    description: str = ""

    @model_validator(mode="after")
    def bounds(self):
        """Range only on numbers, consistent, and containing the default."""
        if self.type not in NUMERIC and (self.minimum is not None or self.maximum is not None):
            raise ValueError("Only numeric parameters have a range")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("minimum exceeds maximum")
        if self.type in NUMERIC and not (
                (self.minimum is None or self.default >= self.minimum)
                and (self.maximum is None or self.default <= self.maximum)):
            raise ValueError("default outside the range")
        return self

    def literal(self, value=None) -> str:
        """IEC literal of ``value`` (default: the default)."""
        value = self.default if value is None else value
        if self.type == "BOOL":
            return "TRUE" if value else "FALSE"
        return repr(float(value)) if self.type == "LREAL" else str(int(value))


class Skill(Model):
    """Skill primitive: one equipment command until ``ensures`` holds or ``after`` has passed.

    Without equipment it only waits (``after``). ``stop`` is the command sent at the end (default:
    the safe command); an abort always sends the safe command.
    """
    description: str = ""
    equipment: str | None = None
    command: str | None = None
    arg: str | float | None = None             # ST expression over parameters -> the command's argument
    stop: str | None = None
    parameters: dict[str, Parameter] = Field(default_factory=dict)
    requires: str = "TRUE"
    ensures: str | None = None                 # sensor condition (ST over equipment inputs and parameters)
    after: str | float | None = None           # open loop: a parameter (seconds) or a number of seconds
    invariant: str = "TRUE"
    timeout: str = Field(default="10s", pattern=DURATION)
    results: dict[str, str] = Field(default_factory=dict)   # result name -> equipment input
    offered: bool = True                       # OPC UA methods for the orchestrator

    @model_validator(mode="after")
    def ends(self):
        """Exactly one end condition; no equipment means no command."""
        if (self.ensures is None) == (self.after is None):
            raise ValueError("A skill ends either by ensures (a sensor) or by after (a time)")
        if self.equipment is None and (self.command or self.ensures or self.results):
            raise ValueError("A skill without equipment only waits (after)")
        if self.equipment is not None and self.command is None:
            raise ValueError("A skill with equipment needs a command")
        return self


class Step(Model):
    """One skill instance in a sequence: its skill, instance name and parameter bindings."""
    skill: str
    name: str
    bind: dict[str, float | bool | str] = Field(default_factory=dict)   # constant or parent parameter name


def steps(value):
    """``[Skill, {Skill: {Param: value}}, {Skill: {...}, as: Name}]`` -> Step dicts with unique names."""
    out, seen = [], {}
    for item in value or []:
        if isinstance(item, str):
            skill, bind, name = item, {}, None
        elif isinstance(item, dict):
            item = dict(item)
            name = item.pop("as", None)
            if len(item) != 1:
                raise ValueError(f"A step names one skill: {item}")
            skill, bind = next(iter(item.items()))
            bind = bind or {}
        else:
            return value
        seen[skill] = seen.get(skill, 0) + 1
        out.append({"skill": skill, "name": name or (skill if seen[skill] == 1 else f"{skill}_{seen[skill]}"),
                    "bind": bind})
    return out


class Composite(Model):
    """Module level skill: a sequence of private skill instances, optionally a stop sequence."""
    description: str = ""
    parameters: dict[str, Parameter] = Field(default_factory=dict)
    execute: list[Step]
    stop: list[Step] = Field(default_factory=list)
    results: dict[str, str] = Field(default_factory=dict)   # result name -> <step>.<result>
    offered: bool = True

    short_steps = field_validator("execute", "stop", mode="before")(classmethod(lambda cls, v: steps(v)))


class Modbus(Model):
    """Modbus TCP endpoint of the module's IO."""
    host: str = "127.0.0.1"
    port: int = 1502
    unit: int = 1
    # FORTE's Modbus client reads in a background poll at this period and delivers cached
    # values, so it bounds how old a sample can be when a skill decides (stop position error).
    poll_ms: int = Field(default=10, ge=1)


class Target(Model):
    """A FORTE device the module can run on, and how its IO points are reached there.

    ``io: modbus``: every point over Modbus. ``io: gpio``: points with a GPIO line or PWM channel
    use it; the others use the target's ``modbus`` server if it names one, else they are
    simulated (a constant: the Raspberry Pi has no analog inputs).
    """
    host: str = "localhost"
    port: int = 61499                    # FORTE management port
    user: str | None = None              # SSH login (4diac/tools/pi.py)
    io: Literal["modbus", "gpio"] = "modbus"
    modbus: Modbus | None = None         # default: the module's Modbus server
    # Where FORTE finds the PWM channels; FORTE in Docker (4diac/tools/pi/compose.yaml) sees the
    # host's /sys/class/pwm at /hostsys/class/pwm.
    pwm_root: str = "/sys/class/pwm"


class Aas(Model):
    """Identity of the module's asset administration shell (modsync), in the lab's conventions
    (AP2030-UNS AASDescriptions): ids below https://smartproductionlab.aau.dk. To keep the identity
    of an asset described before (e.g. the ESP32 station's syntegonStopperingSystemAAS), give its
    ``id_short``, ``id`` and ``global_asset_id``."""
    id_short: str | None = Field(default=None, pattern=IDENT)   # default <Module>ModuleAAS
    id: str | None = None                                       # default <base>/aas/<id_short>
    global_asset_id: str | None = None                          # default <base>/assets/<Module>Module
    asset_type: str | None = None
    serial_number: str | None = None
    location: str | None = None


class ModuleSpec(Model):
    """One module: equipment, skill primitives, module level skills and procedures."""
    module: str = Ident
    project: str = Ident                 # 4diac project folder under 4diac/
    package: str = Ident                 # 4diac package of the module's own types
    opcua_root: str = Field(pattern=r"^(/[A-Za-z][A-Za-z0-9_]*)+$")
    modbus: Modbus = Modbus()
    # The first target is the default one (run_module.py, the live tests).
    targets: dict[str, Target] = Field(default_factory=lambda: {"pc": Target()})
    equipment: dict[str, Equipment] = Field(default_factory=dict)
    skills: dict[str, Skill] = Field(default_factory=dict)
    composites: dict[str, Composite] = Field(default_factory=dict)
    procedures: dict[PROCEDURES, list[Step]] = Field(default_factory=dict)
    stop_timeout: str = Field(default="10s", pattern=DURATION)   # Stopping waits this long for running skills
    aas: Aas = Aas()

    short_steps = field_validator("procedures", mode="before")(
        classmethod(lambda cls, v: {k: steps(s) for k, s in (v or {}).items()}))

    @model_validator(mode="after")
    def check(self):
        """References resolve, names are unique and expressions use only known names."""
        for name in [*self.equipment, *self.skills, *self.composites]:
            if not re.match(IDENT, name):
                raise ValueError(f"Not an identifier: {name}")
        if clash := (set(self.skills) & set(self.composites)) | (set(self.equipment) & (set(self.skills) | set(self.composites))):
            raise ValueError(f"Names used twice: {sorted(clash)}")
        for name, skill in self.skills.items():
            self.check_skill(name, skill)
        for name, comp in self.composites.items():
            if not comp.execute:
                raise ValueError(f"{name}: empty execute sequence")
            self.check_steps(name, comp.execute, set(comp.parameters))
            self.check_steps(name, comp.stop, set(comp.parameters))
            for result, source in comp.results.items():
                step, _, res = source.partition(".")
                found = next((s for s in comp.execute if s.name == step), None)
                if found is None or res not in self.skills[found.skill].results:
                    raise ValueError(f"{name}.results.{result}: {source} is not a result of an execute step")
        for proc, seq in self.procedures.items():
            if not seq:
                raise ValueError(f"{proc}: empty procedure")
            self.check_steps(proc, seq, set())
        if not self.targets:
            raise ValueError("At least one target is needed")
        for name, target in self.targets.items():
            if not re.match(IDENT, name):
                raise ValueError(f"Not an identifier: target {name}")
            lines = {}
            for point, io in self.points():
                backend = self.backend(name, io)
                if backend == "modbus" and io.modbus is None:
                    raise ValueError(f"Target {name}: {point} has no Modbus address")
                if backend in ("gpio", "pwm"):
                    key = (backend, io.gpio.chip, io.gpio.line) if backend == "gpio" else (backend, io.pwm.chip, io.pwm.channel)
                    if key in lines:
                        raise ValueError(f"Target {name}: {point} and {lines[key]} share {backend} {key[1]}/{key[2]}")
                    lines[key] = point
        return self

    def check_skill(self, name, skill: Skill):
        """A primitive's equipment, commands and expressions."""
        known = set(skill.parameters) | ST_WORDS
        if skill.equipment is not None:
            eq = self.equipment.get(skill.equipment)
            if eq is None:
                raise ValueError(f"{name}: unknown equipment {skill.equipment}")
            if skill.command not in eq.commands or eq.code(skill.command) == 0:
                raise ValueError(f"{name}: {skill.command} is not a driving command of {skill.equipment}")
            if skill.stop is not None and skill.stop not in eq.commands:
                raise ValueError(f"{name}: unknown stop command {skill.stop}")
            if clash := set(skill.parameters) & set(eq.inputs):
                raise ValueError(f"{name}: parameters shadow equipment signals {sorted(clash)}")
            if unknown := set(skill.results.values()) - set(eq.inputs):
                raise ValueError(f"{name}: results from unknown inputs {sorted(unknown)}")
            known |= set(eq.inputs)
        for field in ("requires", "ensures", "invariant", "arg"):
            value = getattr(skill, field)
            if isinstance(value, str) and (unknown := names(value) - known):
                raise ValueError(f"{name}.{field}: unknown names {sorted(unknown)}")
        if isinstance(skill.after, str):
            p = skill.parameters.get(skill.after)
            if p is None or p.type != "LREAL":
                raise ValueError(f"{name}.after: {skill.after} is not an LREAL parameter (seconds)")

    def check_steps(self, owner, seq: list[Step], parent_params: set[str]):
        """Steps name skill primitives (composites of composites come later), bind known parameters, are unique."""
        seen = set()
        for step in seq:
            target = self.skills.get(step.skill)
            if target is None:
                raise ValueError(f"{owner}: {step.skill} is not a skill primitive")
            if step.name in seen:
                raise ValueError(f"{owner}: step name {step.name} used twice")
            seen.add(step.name)
            for param, value in step.bind.items():
                if param not in target.parameters:
                    raise ValueError(f"{owner}.{step.name}: {step.skill} has no parameter {param}")
                if isinstance(value, str) and value not in parent_params:
                    raise ValueError(f"{owner}.{step.name}.{param}: {value} is not a parameter of {owner}")

    def points(self):
        """(``<Equipment>.<Signal>``, Input or Output) for every IO point."""
        for eq_name, eq in self.equipment.items():
            for s, io in [*eq.inputs.items(), *eq.outputs.items()]:
                yield f"{eq_name}.{s}", io

    def backend(self, target: str, io: Input | Output) -> str:
        """``sim``, ``gpio``, ``pwm`` or ``modbus``: how ``io`` is reached on ``target``."""
        t = self.targets[target]
        if t.io == "modbus":
            return "modbus"
        if io.gpio is not None:
            return "gpio"
        if isinstance(io, Output) and io.pwm is not None:
            return "pwm"
        return "modbus" if t.modbus is not None and io.modbus is not None else "sim"

    def modbus_id(self, address: str, write: bool, target: str | None = None) -> str:
        """FORTE Modbus CLIENT ID polling (read) or writing one address, on ``target``'s server."""
        m = (self.targets[target].modbus if target else None) or self.modbus
        endpoint = f"{m.host}:{m.port}:{m.unit}"
        return f"modbus[{endpoint}:0::{address}]" if write else f"modbus[{endpoint}:{m.poll_ms}:{address}:]"

    def uses(self, skill: str) -> list[str]:
        """Equipment a skill (primitive or composite) commands, in order of first use."""
        if skill in self.skills:
            eq = self.skills[skill].equipment
            return [eq] if eq else []
        comp = self.composites[skill]
        return list(dict.fromkeys(e for s in comp.execute + comp.stop for e in self.uses(s.skill)))


def load(path: Path) -> ModuleSpec:
    """Read and validate a module specification (YAML)."""
    return ModuleSpec.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))
