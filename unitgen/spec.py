"""Unit specification: the single source from which a unit's 4diac types and system are generated.

A unit has equipment (the only owners of IO points), skills (behaviour-tree nodes that command
one equipment item and are parameterised per instance) and a procedure per PackML state.
Validation is fail-closed: every name an expression uses must be a signal of the skill's
equipment or one of its parameters.
"""
from __future__ import annotations

from pathlib import Path
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
import yaml

IDENT = r"^[A-Za-z][A-Za-z0-9_]*$"
Ident = Field(pattern=IDENT)
# ST words allowed in contract expressions besides signals and parameters.
ST_WORDS = {"AND", "OR", "XOR", "NOT", "TRUE", "FALSE", "MOD", "ABS"}
NUMERIC = {"LREAL", "REAL", "INT", "DINT", "UINT", "UDINT", "USINT"}
# PackML acting states that may run a procedure (iteration 1 dispatches Execute only).
ACTING = Literal["Execute"]


class Model(BaseModel):
    """Strict base model: unknown keys are errors."""
    model_config = ConfigDict(extra="forbid", frozen=True)


class Input(Model):
    """Sensor of an equipment item: a digital (BOOL) or analog (LREAL) input."""
    type: Literal["BOOL", "LREAL"]
    modbus: str = Field(pattern=r"^[di]\d+$")        # d<n> discrete input, i<n> input register
    gpio: int | None = None                           # BCM line on a Raspberry Pi
    scale: float = 1.0                                # analog: engineering value per raw count
    unit: str | None = None

    @model_validator(mode="after")
    def kinds(self):
        """Digital inputs read discrete inputs, analog inputs read registers."""
        if (self.type == "BOOL") != self.modbus.startswith("d"):
            raise ValueError("BOOL inputs use d<n>, LREAL inputs i<n>")
        return self


class Output(Model):
    """Digital actuator output (coil) of an equipment item."""
    modbus: str = Field(pattern=r"^c\d+$")
    gpio: int | None = None


class Equipment(Model):
    """Physical equipment item: sole owner of its IO points and of the command -> output table."""
    description: str = ""
    inputs: dict[str, Input]
    outputs: dict[str, Output]
    # Command name -> outputs switched on; the first command is the safe state (all off).
    commands: dict[str, list[str]]

    @model_validator(mode="after")
    def check(self):
        """Names are identifiers; commands only switch declared outputs; the first is all-off."""
        for name in [*self.inputs, *self.outputs, *self.commands]:
            if not re.match(IDENT, name):
                raise ValueError(f"Not an identifier: {name}")
        if set(self.inputs) & set(self.outputs):
            raise ValueError("Input and output names overlap")
        if not self.commands or next(iter(self.commands.values())):
            raise ValueError("The first command must be the safe state with no outputs on")
        for command, outputs in self.commands.items():
            if unknown := set(outputs) - set(self.outputs):
                raise ValueError(f"Command {command} switches unknown outputs {sorted(unknown)}")
        return self

    def code(self, command: str) -> int:
        """USINT code of a command (its position in the table)."""
        return list(self.commands).index(command)


class Parameter(Model):
    """Skill parameter: type, unit, range and the default an instance starts with."""
    type: Literal["LREAL", "INT", "DINT", "UINT", "BOOL"]
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
    """Primitive skill: while running it holds one command of its equipment until Ensures holds."""
    description: str = ""
    equipment: str
    command: str
    parameters: dict[str, Parameter] = Field(default_factory=dict)
    # ST expressions over the equipment's input signals and the skill's parameters.
    requires: str = "TRUE"
    ensures: str
    invariant: str = "TRUE"
    timeout: str = Field(default="T#10s", pattern=r"^T#\d+(ms|s)$")


class Modbus(Model):
    """Modbus TCP endpoint of the cell IO."""
    host: str = "127.0.0.1"
    port: int = 1502
    unit: int = 1
    # FORTE's Modbus client reads in a background poll at this period and delivers cached
    # values, so it bounds how old a sample can be when a skill decides (stop position error).
    poll_ms: int = Field(default=10, ge=1)


class UnitSpec(Model):
    """One unit: equipment, skills and the procedure run in each PackML acting state."""
    unit: str = Ident
    project: str = Ident                 # 4diac project folder under 4diac/
    package: str = Ident                 # 4diac package of the unit's own types
    opcua_root: str = Field(pattern=r"^(/[A-Za-z][A-Za-z0-9_]*)+$")
    modbus: Modbus = Modbus()
    equipment: dict[str, Equipment]
    skills: dict[str, Skill]
    procedures: dict[ACTING, list[str]]

    @model_validator(mode="after")
    def check(self):
        """Skills reference existing equipment, commands and names; procedures existing skills."""
        for name in [*self.equipment, *self.skills]:
            if not re.match(IDENT, name):
                raise ValueError(f"Not an identifier: {name}")
        for name, skill in self.skills.items():
            eq = self.equipment.get(skill.equipment)
            if eq is None:
                raise ValueError(f"{name}: unknown equipment {skill.equipment}")
            if skill.command not in eq.commands or eq.code(skill.command) == 0:
                raise ValueError(f"{name}: {skill.command} is not a driving command of {skill.equipment}")
            if clash := set(skill.parameters) & set(eq.inputs):
                raise ValueError(f"{name}: parameters shadow equipment signals {sorted(clash)}")
            known = set(eq.inputs) | set(skill.parameters) | ST_WORDS
            for field in ("requires", "ensures", "invariant"):
                words = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", getattr(skill, field)))
                if unknown := words - known:
                    raise ValueError(f"{name}.{field}: unknown names {sorted(unknown)}")
        for state, steps in self.procedures.items():
            if not steps:
                raise ValueError(f"{state}: empty procedure")
            if unknown := set(steps) - set(self.skills):
                raise ValueError(f"{state}: unknown skills {sorted(unknown)}")
            if len(steps) != len(set(steps)):
                raise ValueError(f"{state}: a skill appears twice (instance names are not supported yet)")
        return self

    def modbus_id(self, address: str, write: bool) -> str:
        """FORTE Modbus CLIENT ID polling (read) or writing one address."""
        endpoint = f"{self.modbus.host}:{self.modbus.port}:{self.modbus.unit}"
        return f"modbus[{endpoint}:0::{address}]" if write else f"modbus[{endpoint}:{self.modbus.poll_ms}:{address}:]"


def load(path: Path) -> UnitSpec:
    """Read and validate a unit specification (YAML)."""
    return UnitSpec.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))
