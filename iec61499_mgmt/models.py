"""Versioned JSON contracts. Network state contains only owned PROC instances.

Boundary port declarations belong to the trusted runtime library, not the recipe.
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Name = Annotated[str, Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")]
Path = Annotated[str, Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")]
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
# FORTE 3.x reports e.g. "v2:SHA3-512:<base64url>"; older examples use plain hex.
TypeHash = Annotated[str, Field(pattern=r"^[A-Za-z0-9:_=+/-]*$")]


class Model(BaseModel):
    """Strict, immutable base for all JSON contracts."""
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class IECValue(Model):
    """Small explicit scalar subset; unsupported IEC types are rejected."""
    type: Literal["BOOL", "INT", "DINT", "UINT", "UDINT", "LREAL", "STRING", "TIME"]
    value: bool | int | float | str

    @model_validator(mode="after")
    def check_value(self):
        """Check the value against its IEC type and range; canonicalise LREAL."""
        v = self.value
        if self.type == "BOOL":
            valid = type(v) is bool
        elif self.type in ("INT", "DINT", "UINT", "UDINT"):
            lo, hi = {"INT": (-32768, 32767), "DINT": (-2**31, 2**31 - 1),
                      "UINT": (0, 65535), "UDINT": (0, 2**32 - 1)}[self.type]
            valid = type(v) is int and lo <= v <= hi
        elif self.type == "LREAL":
            valid = type(v) in (int, float)
            if valid:
                try:
                    canonical = float(v)
                    valid = math.isfinite(canonical)
                except OverflowError:
                    valid = False
                if valid:
                    object.__setattr__(self, "value", canonical)
        elif self.type == "TIME":
            # JSON duration is integer milliseconds, never an arbitrary expression.
            valid = type(v) is int and 0 <= v <= 2**31 - 1
        else:
            valid = type(v) is str and all(ord(c) >= 32 for c in v)
        if not valid:
            raise ValueError(f"Invalid {self.type} value: {v!r}")
        return self

    def literal(self) -> str:
        """Render the value as an IEC literal for a management WRITE."""
        if self.type == "BOOL":
            return "TRUE" if self.value else "FALSE"
        if self.type == "TIME":
            return f"T#{self.value}ms"
        if self.type == "STRING":
            return "'" + self.value.replace("$", "$$").replace("'", "$'") + "'"
        return str(self.value)


class Port(Model):
    """One FB interface port as declared in the type library."""
    kind: Literal["event", "data", "adapter"]
    direction: Literal["input", "output"]
    data_type: str | None = None
    writable: bool = False

    @model_validator(mode="after")
    def check_port(self):
        """Reject typed event ports and writable non-inputs."""
        if (self.kind == "event") != (self.data_type is None):
            raise ValueError("Data/adapter ports need a type; event ports have no type")
        if self.writable and (self.kind != "data" or self.direction != "input"):
            raise ValueError("Only data inputs can be writable")
        return self


class FBType(Model):
    """An FB type in the runtime, with its hash and ports."""
    name: Annotated[str, Field(pattern=r"^[A-Za-z_][A-Za-z0-9_:]*$")]
    type_hash: TypeHash
    ports: dict[Name, Port]


class TypeLibrary(Model):
    """Types, hashes and boundary ports of one FORTE build."""
    schema_version: Literal["1"] = "1"
    build_id: str
    runtime_binary_sha256: Digest | None = None
    types: dict[str, FBType]
    boundary_ports: dict[Path, Port] = Field(default_factory=dict)
    adapter_connections_verified: bool = False

    @model_validator(mode="after")
    def check_keys(self):
        """Require matching keys, and build pinning for empty hashes."""
        if any(key != typ.name for key, typ in self.types.items()):
            raise ValueError("Type library keys must equal the type names")
        if any(not typ.type_hash for typ in self.types.values()) and not self.runtime_binary_sha256:
            raise ValueError("Empty type hashes require runtime_binary_sha256 build pinning")
        return self

    def verify_executable(self, path):
        """Verify a local, statically linked runtime before launching it.

        Remote managers need equivalent trusted build attestation. This does not
        attest already running processes, external DLLs or dynamically loaded FBs.
        """
        if self.runtime_binary_sha256 is None:
            raise ValueError("No runtime binary digest declared")
        with open(path, "rb") as binary:
            actual = hashlib.file_digest(binary, "sha256").hexdigest()
        if actual != self.runtime_binary_sha256:
            raise ValueError("Runtime executable does not match the pinned build")


class Instance(Model):
    """One owned FB instance with type, hash and parameter values."""
    name: Path
    type: str
    type_hash: TypeHash
    parameters: dict[Name, IECValue] = Field(default_factory=dict)
    origin: str | None = None


class Connection(Model):
    """One event, data or adapter connection."""
    source: Path
    destination: Path
    kind: Literal["event", "data", "adapter"] = "event"

    def key(self):
        """Identity of the connection for diffs and duplicate checks."""
        return self.kind, self.source, self.destination


class Network(Model):
    """Owned instances and connections of one resource scope."""
    schema_version: Literal["1"] = "1"
    resource: Name
    scope: Path = "PROC"
    instances: list[Instance] = Field(default_factory=list)
    connections: list[Connection] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_graph(self):
        """Validate names, ownership scope and connection endpoints."""
        names = [fb.name for fb in self.instances]
        if len(set(names)) != len(names):
            raise ValueError("Duplicate FB instance")
        if any(not n.startswith(self.scope + ".") for n in names):
            raise ValueError("All instances must be inside the owned scope")
        if any(a != b and b.startswith(a + ".") for a in names for b in names):
            raise ValueError("An FB instance cannot also be a namespace container")
        keys = [c.key() for c in self.connections]
        if len(set(keys)) != len(keys):
            raise ValueError("Duplicate connection")
        for c in self.connections:
            owners = [p.rsplit(".", 1)[0] for p in (c.source, c.destination)]
            for n in owners:
                if n.startswith(self.scope + ".") and n not in names:
                    raise ValueError(f"Dangling endpoint: {n}")
            if not any(n in names for n in owners):
                raise ValueError("Connections must touch an owned instance")
        return self

    def digest(self) -> str:
        """SHA-256 of the canonical network, ignoring order and origin."""
        data = self.model_dump(exclude={"instances": {"__all__": {"origin"}}})
        data["instances"].sort(key=lambda fb: fb["name"])
        data["connections"].sort(key=lambda c: (c["kind"], c["source"], c["destination"]))
        return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def validate_library(self, library: TypeLibrary):
        """Check types, parameters and connections against the library."""
        ports = dict(library.boundary_ports)
        for endpoint in ports:
            if endpoint.startswith(self.scope + "."):
                raise ValueError("Boundary declarations cannot be inside the owned scope")
        for fb in self.instances:
            typ = library.types.get(fb.type)
            if typ is None or typ.type_hash != fb.type_hash:
                raise ValueError(f"Unavailable type/hash for {fb.name}: {fb.type}#{fb.type_hash}")
            ports.update({f"{fb.name}.{name}": p for name, p in typ.ports.items()})
            for name, value in fb.parameters.items():
                port = typ.ports.get(name)
                if port is None or not port.writable or port.data_type != value.type:
                    raise ValueError(f"Invalid parameter binding: {fb.name}.{name}")
        destinations = set()
        for c in self.connections:
            src, dst = ports.get(c.source), ports.get(c.destination)
            if src is None or dst is None:
                raise ValueError(f"Unknown connection port: {c.source} -> {c.destination}")
            if (src.direction, dst.direction) != ("output", "input"):
                raise ValueError(f"Connection direction mismatch: {c}")
            if src.kind != c.kind or dst.kind != c.kind or src.data_type != dst.data_type:
                raise ValueError(f"Connection type mismatch: {c}")
            if c.kind == "adapter" and not library.adapter_connections_verified:
                raise ValueError("Adapter deployment has not been verified for this build")
            if c.kind != "event" and c.destination in destinations:
                raise ValueError(f"Multiple drivers: {c.destination}")
            destinations.add(c.destination)
            owner, _, port = c.destination.rpartition(".")
            if any(fb.name == owner and port in fb.parameters for fb in self.instances):
                raise ValueError(f"Connected input also has a literal parameter: {c.destination}")
        return self


class PutInstance(Model):
    """Patch operation: add or replace an instance."""
    op: Literal["put_instance"]
    instance: Instance


class RemoveInstance(Model):
    """Patch operation: remove an instance and its connections."""
    op: Literal["remove_instance"]
    name: Path


class SetParameter(Model):
    """Patch operation: set one parameter value."""
    op: Literal["set_parameter"]
    instance: Path
    parameter: Name
    value: IECValue


class ChangeConnection(Model):
    """Patch operation: add or remove one connection."""
    op: Literal["connect", "disconnect"]
    connection: Connection


Operation = Annotated[PutInstance | RemoveInstance | SetParameter | ChangeConnection,
                      Field(discriminator="op")]


class NetworkPatch(Model):
    """Ordered operations on the network with hash ``base_hash``."""
    schema_version: Literal["1"] = "1"
    base_hash: Digest
    operations: list[Operation]

    def apply(self, current: Network) -> Network:
        """Apply the operations to ``current`` and return the new network."""
        if current.digest() != self.base_hash:
            raise ValueError("Stale patch: base_hash does not match the current network")
        instances = {fb.name: fb.model_dump() for fb in current.instances}
        connections = {c.key(): c for c in current.connections}
        for op in self.operations:
            if isinstance(op, PutInstance):
                instances[op.instance.name] = op.instance.model_dump()
            elif isinstance(op, RemoveInstance):
                if op.name not in instances:
                    raise ValueError(f"Unknown instance: {op.name}")
                del instances[op.name]
                # Explicitly remove incident edges; never match prefix siblings.
                connections = {k: c for k, c in connections.items()
                               if op.name not in (c.source.rsplit(".", 1)[0], c.destination.rsplit(".", 1)[0])}
            elif isinstance(op, SetParameter):
                if op.instance not in instances:
                    raise ValueError(f"Unknown instance: {op.instance}")
                instances[op.instance]["parameters"][op.parameter] = op.value.model_dump()
            elif op.op == "connect":
                if op.connection.key() in connections:
                    raise ValueError("Connection already exists")
                connections[op.connection.key()] = op.connection
            else:
                if op.connection.key() not in connections:
                    raise ValueError("Connection does not exist")
                del connections[op.connection.key()]
        return Network(resource=current.resource, scope=current.scope,
                       instances=list(instances.values()), connections=list(connections.values()))
