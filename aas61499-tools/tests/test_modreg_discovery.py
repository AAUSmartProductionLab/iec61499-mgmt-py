"""modreg.discovery: the registration service finds an OPC UA server that announces itself, sees the
module it offers, fetches the manifest the module serves and registers its profiles.

A stand-in for a module: an OPC UA server laid out as the module rules lay one out (Objects/Filling
with Occupation and Module), and the filling module's manifest served over HTTP on this computer.
Needs the ``registration`` and ``opcua`` extras and zeroconf; the mDNS cases also need multicast on
this computer's network. The last case is FORTE's own announcement: a FORTE built with
FORTE_COM_OPC_UA_MULTICAST runs the filling module (``--module-forte-exe``).
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import asyncio
import json
import socket
import threading
import time

import pytest

pytest.importorskip("aas_model")
pytest.importorskip("asyncua")

from modgen import SPECS, load                                              # noqa: E402
from modreg import profile as profiles                                      # noqa: E402
from modreg.discovery import SERVICE, Discovery, offered, server_url       # noqa: E402
from modreg.service import Registry                                         # noqa: E402
from test_modsync_live import module                                         # noqa: E402, F401  (the fixture)

MODULE = "Filling"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def module_server():
    """An OPC UA server with one module laid out as the module rules have it, and an object that is
    not a module; its URL."""
    from asyncua import Server
    port, ready, stop = free_port(), threading.Event(), threading.Event()

    async def run():
        server = Server()
        await server.init()
        server.set_endpoint(f"opc.tcp://127.0.0.1:{port}/")
        idx = await server.register_namespace("urn:test:module")
        module = await server.nodes.objects.add_object(idx, MODULE)
        for part in ("Occupation", "Module", "Skills", "Equipment"):
            await module.add_object(idx, part)
        await server.nodes.objects.add_object(idx, "Something")
        async with server:
            ready.set()
            while not stop.is_set():
                await asyncio.sleep(0.1)

    thread = threading.Thread(target=lambda: asyncio.run(run()), daemon=True)
    thread.start()
    assert ready.wait(20)
    yield f"opc.tcp://127.0.0.1:{port}/"
    stop.set()
    thread.join(10)


@pytest.fixture(scope="module")
def manifest():
    """The filling module's manifest, served on this computer as a module serves it; its port."""
    spec = load(SPECS / "filling.yaml")
    body = json.dumps({"module": MODULE, "profiles": profiles.describe_all(spec, "pc")}).encode()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):          # noqa: N802
            if self.path != "/manifest.json":
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("0.0.0.0", 0), Handler)     # fetched at the address FORTE announces
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server.server_address[1]
    server.shutdown()


def test_the_modules_a_server_offers_are_those_laid_out_as_a_module(module_server):
    assert offered(module_server) == ([MODULE], False)


def test_a_found_server_has_its_module_registered_from_its_manifest(tmp_path, module_server, manifest):
    found = Discovery(Registry(tmp_path / "registry"), manifest).take("forte_4840-test", module_server)
    assert found.error is None and found.modules == [MODULE]
    assert found.registered[-1] == "FillingModuleAAS"            # the module after its components
    assert {"FillingModuleAAS", "FillingLinearAxisAAS", "FillingPumpAAS", "FillingScaleAAS"} <= set(found.registered)
    assert (tmp_path / "registry").is_dir()


def test_a_server_without_a_manifest_is_reported_not_registered(tmp_path, module_server):
    found = Discovery(Registry(tmp_path / "registry"), free_port(), timeout=2).take("forte_4840-test", module_server)
    assert found.modules == [MODULE] and found.registered == [] and found.error.startswith("URLError")


def test_an_announced_server_is_found_and_registered(tmp_path, module_server, manifest):
    """The OPC UA server announced by mDNS as FORTE's LDS-ME announces it."""
    from zeroconf import ServiceInfo, Zeroconf
    port = int(module_server.rsplit(":", 1)[1].strip("/"))
    info = ServiceInfo(SERVICE, f"forte_{port}-test.{SERVICE}", port=port, properties={"path": "/", "caps": "NA"},
                       addresses=[socket.inet_aton("127.0.0.1")], server="discovery-test.local.")
    announcer = Zeroconf()
    discovery = Discovery(Registry(tmp_path / "registry"), manifest, timeout=5)
    try:
        announcer.register_service(info)
        discovery.start()
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            done = [f for f in discovery.listing() if f["url"] == server_url("127.0.0.1", port) and f["registered"]]
            if done:
                break
            time.sleep(0.5)
        else:
            pytest.skip(f"no mDNS announcement seen on this computer's network: {discovery.listing()}")
        assert "FillingModuleAAS" in done[0]["registered"]
    finally:
        discovery.stop()
        announcer.unregister_service(info)
        announcer.close()


def test_forte_announces_the_module_and_it_is_registered(tmp_path, module, manifest):         # noqa: F811
    """FORTE's LDS-ME: its OPC UA server announced by mDNS (forte_<port>-<host>), found, the module
    on it seen, its manifest fetched and its AASs registered."""
    discovery = Discovery(Registry(tmp_path / "registry"), manifest, timeout=5)
    discovery.start()
    try:
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            done = [f for f in discovery.listing() if f["name"].startswith("forte_") and f["registered"]]
            if done:
                break
            time.sleep(0.5)
        else:
            pytest.fail(f"FORTE was not found and registered (is it built with FORTE_COM_OPC_UA_MULTICAST?): "
                        f"{discovery.listing()}")
        assert done[0]["modules"] == [MODULE] and done[0]["registered"][-1] == "FillingModuleAAS"
    finally:
        discovery.stop()
