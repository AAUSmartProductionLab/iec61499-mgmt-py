"""Discovery: the registration service finds the modules on the network itself, and registers each
with the manifest it was delivered with.

A FORTE built with ``FORTE_COM_OPC_UA_MULTICAST`` (runtime/fbe/configurations) announces its OPC UA
server by mDNS, as OPC UA's multicast discovery (LDS-ME, Part 12) has it: the service
``_opcua-tcp._tcp``, the instance named after the server (``forte_<port>``) and the host, a TXT
``path``. The service browses for it, connects, and finds the modules the server offers: the objects
below Objects laid out as the module rules lay a module out (Occupation and Module side by side).

A module's **manifest** is what it was delivered with: the profiles of its AAS and of its
components' AASs, the pydantic dumps the registration service takes (``modreg manifest``). The
module serves it next to FORTE, at ``http://<host>:8088/manifest.json`` (deploy/pi/compose.yaml, the
service ``manifest``): ``{"module": ..., "profiles": [...]}``. The planar controller has none: its
AAS follows from what it shows (``modreg.planar.read``), so a server in its namespace is described
from that.

What was found is registered as a profile sent to the service is, once per announcement; a server
that leaves the network is marked gone, and its AASs stay.

    discovery = Discovery(registry)            # modreg serve --discover
    discovery.start()
    discovery.listing()                        # GET /discovered
    discovery.stop()
"""
from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import threading
import urllib.parse
import urllib.request

from . import planar

SERVICE = "_opcua-tcp._tcp.local."
MANIFEST_PORT = 8088
MANIFEST = "manifest.json"


@dataclass
class Found:
    """An OPC UA server that announced itself, and what came of it."""
    name: str                                   # its instance name on the network
    url: str                                    # opc.tcp://<host>:<port><path>
    modules: list[str] = field(default_factory=list)       # the modules it offers
    registered: list[str] = field(default_factory=list)    # the AASs registered from it (idShorts)
    present: bool = True                        # still announced
    error: str | None = None                    # why nothing was registered
    seen_at: str = ""


def server_url(host: str, port: int, path: str = "/") -> str:
    """The OPC UA URL of an announced server (TXT ``path``, "/" when empty)."""
    path = path or "/"
    return f"opc.tcp://{host}:{port}{path if path.startswith('/') else '/' + path}"


async def _offered(url: str, timeout: float) -> tuple[list[str], bool]:
    """The modules the server at ``url`` offers, and whether it is the planar controller."""
    from asyncua import Client
    async with Client(url=url, timeout=timeout) as client:
        if planar.NAMESPACE in await client.get_namespace_array():
            return [], True
        found = []
        for child in await client.nodes.objects.get_children():
            parts = {(await c.read_browse_name()).Name for c in await child.get_children()}
            if {"Occupation", "Module"} <= parts:
                found.append((await child.read_browse_name()).Name)
        return found, False


def offered(url: str, timeout: float = 10.0) -> tuple[list[str], bool]:
    """The modules the OPC UA server at ``url`` offers (by the module rules' layout), and whether it is
    the planar controller."""
    return asyncio.run(_offered(url, timeout))


def manifest(host: str, port: int = MANIFEST_PORT, timeout: float = 10.0) -> dict:
    """The manifest a module serves next to its FORTE."""
    with urllib.request.urlopen(f"http://{host}:{port}/{MANIFEST}", timeout=timeout) as answer:
        found = json.load(answer)
    if not isinstance(found, dict) or not isinstance(found.get("profiles"), list):
        raise ValueError(f"http://{host}:{port}/{MANIFEST} is not a manifest (no list of profiles)")
    return found


def profiles_of(url: str, modules: list[str], is_planar: bool, manifest_port: int = MANIFEST_PORT,
                timeout: float = 10.0) -> list[dict]:
    """The profiles to register for what the server at ``url`` offers (``offered``): the manifest its
    host serves, or, for the planar controller, the table and its shuttles as it shows them."""
    if is_planar:
        return planar.describe_all(planar.read(url, timeout))
    if not modules:
        return []
    found = manifest(urllib.parse.urlsplit(url).hostname, manifest_port, timeout)
    if found.get("module") not in (None, *modules):
        raise ValueError(f"the manifest is of {found['module']}, the server offers {', '.join(modules)}")
    return found["profiles"]


class Discovery:
    """Browses the network for OPC UA servers and registers what they offer with ``registry``."""

    def __init__(self, registry, manifest_port: int = MANIFEST_PORT, timeout: float = 10.0, interfaces=None):
        self.registry, self.manifest_port, self.timeout = registry, manifest_port, timeout
        self.interfaces = interfaces                # zeroconf's: all by default
        self.found: dict[str, Found] = {}           # by instance name
        self.busy: set[str] = set()                 # being registered now (an announcement comes several times)
        self.lock = threading.Lock()
        self.zeroconf = self.browser = None

    def start(self) -> None:
        from zeroconf import InterfaceChoice, ServiceBrowser, Zeroconf
        self.zeroconf = Zeroconf(interfaces=self.interfaces or InterfaceChoice.All)
        self.browser = ServiceBrowser(self.zeroconf, SERVICE, handlers=[self._changed])

    def stop(self) -> None:
        if self.browser is not None:
            self.browser.cancel()
        if self.zeroconf is not None:
            self.zeroconf.close()
        self.browser = self.zeroconf = None

    def listing(self) -> list[dict]:
        with self.lock:
            return [asdict(f) for f in self.found.values()]

    def _changed(self, zeroconf, service_type: str, name: str, state_change) -> None:
        """zeroconf's thread: what has to wait (resolving, connecting) goes to a thread of its own."""
        from zeroconf import ServiceStateChange
        if state_change is ServiceStateChange.Removed:
            with self.lock:
                if name in self.found:
                    self.found[name].present = False
            return
        threading.Thread(target=self._resolve, args=(zeroconf, service_type, name), daemon=True).start()

    def _resolve(self, zeroconf, service_type: str, name: str) -> None:
        from zeroconf import IPVersion
        info = zeroconf.get_service_info(service_type, name, timeout=int(self.timeout * 1000))
        if info is None or not info.parsed_addresses(IPVersion.V4Only):
            return
        path = ((info.properties or {}).get(b"path") or b"/").decode()
        # A host with several networks announces an address on each (and a link-local one): each is
        # tried, the link-local ones last.
        hosts = sorted(info.parsed_addresses(IPVersion.V4Only), key=lambda a: a.startswith("169.254."))
        self.take(name, [server_url(host, info.port, path) for host in hosts])

    def take(self, name: str, urls: str | list[str]) -> Found:
        """Register what the server at the first of ``urls`` that answers offers (also called
        directly, without mDNS)."""
        urls = [urls] if isinstance(urls, str) else urls
        found = Found(name, urls[0], seen_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
        with self.lock:
            known = self.found.get(name)
            if name in self.busy or (known is not None and known.present and known.registered):
                return known or found               # an announcement repeated: registered already, or now
            self.found[name] = found
            self.busy.add(name)
        try:
            from .service import mapped_last              # the AASs with mappings after those they refer to
            for url in urls:
                try:
                    found.modules, is_planar = offered(url, self.timeout)
                    found.url = url
                    break
                except (OSError, TimeoutError, asyncio.TimeoutError):
                    if url == urls[-1]:
                        raise
            profiles = profiles_of(found.url, found.modules, is_planar, self.manifest_port, self.timeout)
            if is_planar:
                found.modules = [p["id_short"] for p in profiles]
            found.registered = [self.registry.register(profile).id_short for profile in mapped_last(profiles)]
        except Exception as e:                      # noqa: BLE001 (any failure is the finding's)
            found.error = f"{type(e).__name__}: {e}"
        finally:
            with self.lock:
                self.busy.discard(name)
        print(f"discovered {name} at {found.url}: {', '.join(found.modules) or 'no module'}; "
              f"{'registered ' + ', '.join(found.registered) if found.registered else found.error or 'nothing to register'}",
              flush=True)
        return found
