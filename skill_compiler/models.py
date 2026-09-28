"""Author intent and deployment bindings are different contracts."""
from typing import Annotated, Literal

from pydantic import Field, model_validator

from iec61499_mgmt.models import IECValue, Model, Name, Network, Path, TypeLibrary

from .contracts import Condition, Contract


class Constant(Model):
    """Parameter value given as a constant."""
    source: Literal["constant"]
    value: IECValue


class ProductParameter(Model):
    """Parameter value taken from the product."""
    source: Literal["product"]
    key: str


ValueSource = Annotated[Constant | ProductParameter, Field(discriminator="source")]


class TaskBinding(Model):
    """Skill and parameter sources for one BPMN task; ``repeat`` gives the loop count of a looped task."""
    skill: str
    parameters: dict[str, ValueSource] = Field(default_factory=dict)
    repeat: ValueSource | None = None


class RecipeBindings(Model):
    """Task bindings of one procedure."""
    schema_version: Literal["1"] = "1"
    procedure_id: str
    tasks: dict[str, TaskBinding]
    assumes: list[Condition] = Field(default_factory=list)


class Parameter(Model):
    """Declared skill parameter: type, unit, range and default."""
    type: Literal["BOOL", "INT", "DINT", "UINT", "UDINT", "LREAL", "STRING", "TIME"]
    unit: str | None = None
    minimum: float | None = None
    maximum: float | None = None
    default: IECValue | None = None

    @model_validator(mode="after")
    def bounds(self):
        """Check that the range is consistent and the default valid."""
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("Parameter minimum exceeds maximum")
        if self.default is not None:
            self.check(self.default)
        return self

    def check(self, value: IECValue):
        """Raise if ``value`` has the wrong type or is out of range."""
        if value.type != self.type:
            raise ValueError(f"Expected {self.type}, got {value.type}")
        if self.minimum is not None or self.maximum is not None:
            if type(value.value) not in (float, int):
                raise ValueError("Only numeric parameters can have numeric ranges")
            if self.minimum is not None and value.value < self.minimum:
                raise ValueError(f"Value below minimum {self.minimum}")
            if self.maximum is not None and value.value > self.maximum:
                raise ValueError(f"Value above maximum {self.maximum}")


class Skill(Model):
    """Semantic skill: parameters and occupied equipment."""
    id: str
    parameters: dict[str, Parameter] = Field(default_factory=dict)
    occupies: list[str] = Field(default_factory=list)
    contract: Contract | None = None


class Wire(Model):
    """Integrator-owned endpoints; {instance} is the sole template substitution."""
    source: str
    destination: str
    kind: Literal["event", "data", "adapter"] = "event"


class SkillRuntimeBinding(Model):
    """Where a skill lives in the runtime and how calls are wired."""
    fixed_instance: Path
    fb_type: str
    type_hash: str
    selector: IECValue | None = None
    parameter_ports: dict[str, Name] = Field(default_factory=dict)
    wires: list[Wire]


class CallPattern(Model):
    """Call FB type and its event and selector port names."""
    fb_type: str
    enter: Name
    complete: Name
    error: Name
    selector: Name | None = None
    reset: Name | None = None


class LoopPattern(Model):
    """Loop FB type: enter, body start, body end, exit, count parameter and reset ports."""
    fb_type: str
    enter: Name = "EI"
    body: Name = "BODY"
    next: Name = "NEXT"
    exit: Name = "EO"
    count: Name = "Count"
    reset: Name | None = "RESET"


class TargetProfile(Model):
    """Runtime integration profile: facade, call pattern, library and skills."""
    schema_version: Literal["1"] = "1"
    resource: Name
    scope: Path = "PROC"
    facade_start: Path
    facade_complete: Path
    facade_error: Path
    facade_reset: Path | None = None
    call: CallPattern
    loop: LoopPattern | None = None
    library: TypeLibrary
    skills: dict[str, Skill]
    runtime_bindings: dict[str, SkillRuntimeBinding]

    @model_validator(mode="after")
    def check_bindings(self):
        """Check that every skill has a consistent runtime binding."""
        if self.skills.keys() != self.runtime_bindings.keys():
            raise ValueError("Every skill needs exactly one runtime binding")
        for key, skill in self.skills.items():
            if key != skill.id:
                raise ValueError("Skill catalog key must equal semantic skill ID")
            binding = self.runtime_bindings[key]
            if binding.fixed_instance.startswith(self.scope + "."):
                raise ValueError("Atomic skills must be outside the procedure scope")
            typ = self.library.types.get(binding.fb_type)
            if typ is None or typ.type_hash != binding.type_hash:
                raise ValueError(f"Atomic skill type/hash unavailable: {key}")
            if binding.parameter_ports.keys() != skill.parameters.keys():
                raise ValueError(f"Parameter port mapping incomplete for {key}")
            if (self.call.selector is None) != (binding.selector is None):
                raise ValueError(f"Selector given on only one of call pattern and binding for {key}")
            ports = list(binding.parameter_ports.values()) + ([self.call.selector] if self.call.selector else [])
            if len(ports) != len(set(ports)):
                raise ValueError(f"Overlapping parameter/selector ports for {key}")
            if not binding.wires:
                raise ValueError(f"Missing call wiring for {key}")
        if self.loop is not None and self.loop.fb_type not in self.library.types:
            raise ValueError("Loop pattern is not in the runtime library")
        return self


class Call(Model):
    """One skill call in a compiled procedure; ``repeat`` is set for looped tasks."""
    id: str
    label: str
    skill: str
    parameters: dict[str, IECValue]
    repeat: IECValue | None = None


class Procedure(Model):
    """Compiled procedure as an ordered list of calls."""
    schema_version: Literal["1"] = "1"
    profile: Literal["sequence-v1", "sequence-v2"] = "sequence-v1"  # v2: tasks may repeat
    id: str
    calls: list[Call]


class CompositeSkill(Model):
    """Draft descriptor, not an approved AAS submodel or a proven contract."""
    id: str
    kind: Literal["Composite"] = "Composite"
    uses: list[str]
    occupies: list[str]
    product_parameters: list[str]
    network_hash: str
    validation: Literal["structure_only"] = "structure_only"


class Compilation(Model):
    """Compiler result: procedure, composite skill and network."""
    procedure: Procedure
    skill: CompositeSkill
    network: Network
