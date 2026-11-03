"""Serve modules from their specs in Python.

    python -m modpy serve <spec.yaml> [<spec.yaml> ...] [--port 4840] [--speed 1]
                          [--announce] [--manifest <manifest.json> [--manifest-port 8088]]

Every module is below /Objects/<Module> of one OPC UA server, its devices simulated (``SimPoints``)
until a driver for them is chosen. ``--announce`` announces the server by mDNS as FORTE does
(``_opcua-tcp._tcp``), so that the registration service finds it (modreg serve --discover);
``--manifest`` serves the modules' profiles where the service fetches them
(http://<host>:8088/manifest.json, ``modreg manifest``).
"""
from __future__ import annotations

import argparse
import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import logging
from pathlib import Path
import socket
import threading

from modgen import load

from .points import SimPoints
from .run import Runtime
from .server import ModuleServer

log = logging.getLogger("modpy")
SERVICE = "_opcua-tcp._tcp.local."


def addresses() -> list[str]:
    """This host's IPv4 addresses, without the loopback."""
    import ifaddr
    return [ip.ip for adapter in ifaddr.get_adapters() for ip in adapter.ips
            if isinstance(ip.ip, str) and not ip.ip.startswith("127.")]


def announce(name: str, port: int):
    """Announce the OPC UA server by mDNS, as OPC UA's multicast discovery (LDS-ME) has it."""
    from zeroconf import ServiceInfo, Zeroconf
    info = ServiceInfo(SERVICE, f"{name}.{SERVICE}", port=port, properties={"path": "/"},
                       addresses=[socket.inet_aton(a) for a in addresses()], server=f"{socket.gethostname()}.local.")
    zeroconf = Zeroconf()
    zeroconf.register_service(info)
    return zeroconf, info


def serve_manifest(path: Path, port: int) -> ThreadingHTTPServer:
    """``path`` at http://<host>:<port>/manifest.json, read again at every request."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.split("?")[0] != "/manifest.json":
                return self.send_error(404)
            body = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="modpy", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("serve", help="serve modules over OPC UA, their devices simulated")
    p.add_argument("specs", nargs="+", type=Path)
    p.add_argument("--port", type=int, default=4840)
    p.add_argument("--speed", type=float, default=1.0, help="simulated jobs that much quicker")
    p.add_argument("--announce", action="store_true", help="announce the server by mDNS")
    p.add_argument("--manifest", type=Path, help="serve this manifest at /manifest.json")
    p.add_argument("--manifest-port", type=int, default=8088)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

    runtimes = []
    for path in args.specs:
        spec = load(path)
        runtimes.append(Runtime(spec, SimPoints(spec, args.speed)))
    stop = threading.Event()
    for rt in runtimes:
        threading.Thread(target=rt.loop, args=(stop,), name=rt.spec.module, daemon=True).start()
    announced = announce(f"modpy_{args.port}", args.port) if args.announce else None
    manifest = serve_manifest(args.manifest, args.manifest_port) if args.manifest else None
    try:
        asyncio.run(ModuleServer(runtimes, args.port).serve())
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        if announced:
            announced[0].unregister_service(announced[1])
            announced[0].close()
        if manifest:
            manifest.shutdown()


if __name__ == "__main__":
    main()
