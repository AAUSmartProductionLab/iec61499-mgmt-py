"""Tests for the management protocol client."""
import socket
import struct
from concurrent.futures import ThreadPoolExecutor
from xml.etree import ElementTree as ET

import pytest

from iec61499_mgmt.protocol import Client, Command, ManagementError, ProtocolError, Response


def test_xml_attribute_escaping():
    """Values are escaped in request XML."""
    value = "'a&<\"b'"
    command = Command(op="write", resource="RES", destination="PROC.A.VALUE", value=value)
    assert ET.fromstring(command.xml(1)).find("Connection").get("Source") == value


@pytest.mark.parametrize("response", ['<Response ID="2"/>', '<Request ID="1"/>', 'garbage'])
def test_bad_responses(response):
    """Malformed or mismatched responses raise ProtocolError."""
    with pytest.raises(ProtocolError):
        Response.parse(response, 1)


def test_nested_management_error():
    """Error reasons on nested elements are reported."""
    assert Response.parse('<Response ID="1"><FB Reason="INVALID_STATE"/></Response>', 1).reason == "INVALID_STATE"


def receive(sock, size):
    """Read exactly ``size`` bytes from a socket."""
    result = b""
    while len(result) < size:
        part = sock.recv(size - len(result))
        if not part:
            raise RuntimeError("Peer closed")
        result += part
    return result


@pytest.mark.parametrize("payload,exception", [
    (b'<Response ID="1"><Connection Source="PROC.A.N" Destination="2"/></Response>', None),
    (b'<Response ID="1" Reason="INVALID_STATE"/>', ManagementError),
    (b'<Response ID="999"/>', ProtocolError),
])
def test_fragmented_wire_protocol(monkeypatch, payload, exception):
    """Byte-by-byte frames and error replies are handled."""
    client_socket, server_socket = socket.socketpair()
    client_socket.settimeout(2)
    server_socket.settimeout(2)
    monkeypatch.setattr(socket, "create_connection", lambda *args, **kwargs: client_socket)

    def server():
        with server_socket:
            parts = []
            for _ in range(2):
                marker, size = struct.unpack(">BH", receive(server_socket, 3))
                assert marker == 0x50
                parts.append(receive(server_socket, size))
            assert parts[0] == b"RES"
            assert ET.fromstring(parts[1]).get("Action") == "READ"
            frame = struct.pack(">BH", 0x50, len(payload)) + payload
            for byte in frame:
                server_socket.sendall(bytes([byte]))

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(server)
        with Client() as client:
            command = Command(op="read", resource="RES", source="PROC.A.N")
            if exception:
                with pytest.raises(exception):
                    client.execute(command)
            else:
                assert client.execute(command).connections[0]["Destination"] == "2"
        future.result(timeout=3)


@pytest.mark.parametrize("wire", [b"\x51\x00\x00", b"\x50\x00\x04x"])
def test_marker_and_eof(monkeypatch, wire):
    """A bad frame marker or early EOF raises and closes the socket."""
    class FakeSocket:
        def __init__(self):
            self.data = wire
            self.closed = False

        def sendall(self, data):
            pass

        def recv(self, size):
            part, self.data = self.data[:size], self.data[size:]
            return part

        def close(self):
            self.closed = True

    sock = FakeSocket()
    monkeypatch.setattr(socket, "create_connection", lambda *args, **kwargs: sock)
    with pytest.raises(ProtocolError):
        Client().execute(Command(op="query_fbs", resource="RES"))
    assert sock.closed


def test_timeout_is_not_retried(monkeypatch):
    """A timed-out request is not resent."""
    class FakeSocket:
        attempts = 0
        closed = False

        def sendall(self, data):
            self.attempts += 1

        def recv(self, size):
            raise TimeoutError("Reply lost after mutation may have succeeded")

        def close(self):
            self.closed = True

    sock = FakeSocket()
    monkeypatch.setattr(socket, "create_connection", lambda *args, **kwargs: sock)
    with pytest.raises(TimeoutError):
        Client().execute(Command(op="start", resource="RES", name="PROC.A"))
    assert sock.attempts == 1 and sock.closed


def test_recorded_forte3_responses():
    """Recorded FORTE 3 responses parse as expected."""
    import json
    from pathlib import Path
    records = json.loads((Path(__file__).parent / "fixtures" / "forte3-responses.json").read_text())
    for record in records:
        raw = record["response"]
        response = Response.parse(raw, int(ET.fromstring(raw).get("ID")))
        op = record["request"]["op"]
        if op == "read":
            assert response.read_value(record["request"]["source"]) == "1000"
            with pytest.raises(ProtocolError):
                response.read_value("Another.PORT")
        elif op == "query_type":
            assert response.types == [{"Name": "iec61499::events::E_SPLIT#"}]
        elif op == "query_fbs":
            assert any(fb["Name"] == "PROC.Split" for fb in response.fbs)
        elif op == "query_connections":
            assert any(c["Source"] == "Clock.EO" for c in response.connections)
        else:
            assert response.reason in ("INVALID_STATE", "UNSUPPORTED_TYPE")


@pytest.mark.parametrize("source", ["PROC.A.PV", "PROC.A.PV.PV"])
def test_read_value_accepts_exact_and_duplicated_leaf(source):
    """READ accepts the exact source or the duplicated leaf."""
    response = Response.parse(f'<Response ID="1"><Connection Source="{source}" Destination="42"/></Response>', 1)
    assert response.read_value("PROC.A.PV") == "42"
