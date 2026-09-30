"""Typed commands and XML responses; no text interpolation into XML."""
from __future__ import annotations

from typing import Literal
from xml.etree import ElementTree as ET

from defusedxml.ElementTree import fromstring
from pydantic import model_validator

from .models import Model


class Command(Model):
    """One typed management request."""
    op: Literal["create_fb", "delete_fb", "connect", "disconnect", "write", "read",
                "start", "stop", "kill", "query_fbs", "query_connections", "query_type"]
    resource: str
    name: str | None = None
    type: str | None = None
    source: str | None = None
    destination: str | None = None
    value: str | None = None

    @model_validator(mode="after")
    def check_fields(self):
        """Ensure exactly the fields the operation needs are set."""
        required = {
            "create_fb": {"name", "type"}, "delete_fb": {"name"},
            "connect": {"source", "destination"}, "disconnect": {"source", "destination"},
            "write": {"destination", "value"}, "read": {"source"},
            "start": {"name"}, "stop": {"name"}, "kill": {"name"}, "query_fbs": set(),
            "query_connections": set(), "query_type": {"type"},
        }[self.op]
        present = {k for k in ("name", "type", "source", "destination", "value")
                   if getattr(self, k) is not None}
        if present != required:
            raise ValueError(f"{self.op} requires exactly {sorted(required)}")
        return self

    def xml(self, request_id: int) -> str:
        """Serialise the request to FORTE management XML."""
        action = {"create_fb": "CREATE", "delete_fb": "DELETE", "connect": "CREATE",
                  "disconnect": "DELETE", "query_fbs": "QUERY", "query_connections": "QUERY",
                  "query_type": "QUERY"}.get(self.op, self.op.upper())
        root = ET.Element("Request", ID=str(request_id), Action=action)
        if self.op in ("create_fb", "delete_fb", "start", "stop", "kill"):
            ET.SubElement(root, "FB", Name=self.name, Type=self.type or "")
        elif self.op in ("connect", "disconnect"):
            ET.SubElement(root, "Connection", Source=self.source, Destination=self.destination)
        elif self.op == "write":
            ET.SubElement(root, "Connection", Source=self.value, Destination=self.destination)
        elif self.op == "read":
            ET.SubElement(root, "Connection", Source=self.source, Destination="*")
        elif self.op == "query_fbs":
            ET.SubElement(root, "FB", Name="*", Type="*")
        elif self.op == "query_connections":
            ET.SubElement(root, "Connection", Source="*", Destination="*")
        else:
            ET.SubElement(root, "FBType", Name=self.type)
        return ET.tostring(root, encoding="unicode")


class ProtocolError(RuntimeError):
    """The response frame or XML is malformed or unexpected."""
    pass


class ManagementError(RuntimeError):
    """FORTE answered the request with an error reason."""
    def __init__(self, response):
        self.response = response
        super().__init__(f"FORTE request {response.request_id}: {response.reason}")


class Response(Model):
    """Parsed management response."""
    request_id: str
    reason: str | None
    fbs: list[dict[str, str]]
    connections: list[dict[str, str]]
    types: list[dict[str, str]]
    raw: str

    def read_value(self, source: str) -> str:
        """Extract one READ result, accepting FORTE 3.0's duplicated leaf name.

        Some builds echo ``FB.PORT.PORT`` for a request for ``FB.PORT``.
        Keep raw XML/attributes intact; only accept this exact known variation.
        """
        if self.reason:
            raise ManagementError(self)
        accepted = {source, source + "." + source.rsplit(".", 1)[-1]}
        if (len(self.connections) != 1 or self.connections[0].get("Source") not in accepted
                or "Destination" not in self.connections[0]):
            raise ProtocolError(f"Unexpected READ response for {source}")
        return self.connections[0]["Destination"]

    @classmethod
    def parse(cls, xml: str, expected_id: int):
        """Parse response XML and check it answers ``expected_id``."""
        try:
            root = fromstring(xml)
        except Exception as exc:
            raise ProtocolError("Invalid management response XML") from exc
        if root.tag != "Response" or root.get("ID") != str(expected_id):
            raise ProtocolError("Unexpected response root or request ID")
        reasons = [e.get("Reason") for e in root.iter() if e.get("Reason")]
        reason = next((r for r in reasons if r != "OK"), None)
        return cls(request_id=root.get("ID"), reason=reason, raw=xml,
                   fbs=[dict(e.attrib) for e in root.iter("FB")],
                   connections=[dict(e.attrib) for e in root.iter("Connection")],
                   types=[dict(e.attrib) for e in root.iter("FBType")])


class Client:
    """Synchronous single-owner connection. A failed request is never retried.

    Management STOP/START controls FB lifecycle, not PackML skill commands.
    The caller owns occupation, process guards and post-deployment verification.
    """

    def __init__(self, host="localhost", port=61499, timeout=5.0):
        self.address = (host, port)
        self.timeout = timeout
        self._socket = None
        self._request_id = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        """Close the TCP connection."""
        if self._socket is not None:
            self._socket.close()
            self._socket = None

    def _recv(self, size):
        """Read exactly ``size`` bytes from the socket."""
        data = bytearray()
        while len(data) < size:
            chunk = self._socket.recv(size - len(data))
            if not chunk:
                raise ProtocolError("FORTE closed the connection before the frame completed")
            data.extend(chunk)
        return bytes(data)

    def execute(self, command: Command) -> Response:
        """Send one command and return its parsed response."""
        import socket
        import struct

        self._request_id += 1
        parts = [p.encode("utf-8") for p in (command.resource, command.xml(self._request_id))]
        if any(len(p) > 65535 for p in parts):
            raise ValueError("Management frame exceeds the 16-bit length limit")
        try:
            if self._socket is None:
                self._socket = socket.create_connection(self.address, timeout=self.timeout)
            self._socket.sendall(b"".join(struct.pack(">BH", 0x50, len(p)) + p for p in parts))
            marker, size = struct.unpack(">BH", self._recv(3))
            if marker != 0x50:
                raise ProtocolError(f"Unexpected frame marker: {marker:#x}")
            response = Response.parse(self._recv(size).decode("utf-8"), self._request_id)
        except Exception:
            self.close()
            raise
        if response.reason:
            raise ManagementError(response)
        return response
