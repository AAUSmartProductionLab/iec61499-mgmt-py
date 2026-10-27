"""The registration service: a resource sends its profile, the service makes its AAS known.

A registration runs in four steps, and stops at the first that fails:

1. **Read** the profile into the lab's shared AAS model (pydantic): it has to be a valid AAS of
   its type.
2. **Build** the AAS from the model (shell and submodels).
3. **Check** the AAS against the ontology, if one is given: every restriction the ontology states
   has to hold. What the ontology does not describe is reported, and refuses the registration only
   in strict mode.
4. **Publish**: keep the profile and the AAS in the service's folder and, if an AAS server is
   given, create or replace the shell and its submodels there.

A profile that is registered again unchanged is answered from what is kept, without publishing.

HTTP (JSON):

    POST   /profiles            register a profile; ?check=1 runs steps 1 to 3 only
    GET    /profiles            the registered resources
    GET    /profiles/<idShort>  one registration; /profile the profile, /aas the AAS
    DELETE /profiles/<idShort>  forget a resource (and remove its AAS from the server)
    POST   /capabilities/<shell>  derive a module's offered capabilities anew from its skills, on the
                                  AAS server, and put them back (the skill editor, after saving)
    GET    /build/<idShort>     the record of what was built on a module (a Control Configuration
    PUT    /build/<idShort>     submodel, kept here and not in the AAS: ARSO 0.10); modsync writes it
    GET    /health
"""
from __future__ import annotations

import base64
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import urllib.error
import urllib.parse
import urllib.request

from modsync import desired

from . import model
from .offer import at as offer_at, capabilities, children as offer_children
from .ontology import Blueprint, check
from .profile import OFFERED_SET


class Refused(Exception):
    """A registration that did not go through, with the HTTP status that says why."""

    def __init__(self, status: int, step: str, reasons: list[str]):
        super().__init__(f"{step}: {reasons[0] if reasons else ''}")
        self.status, self.step, self.reasons = status, step, reasons


@dataclass
class Registration:
    id_short: str
    id: str
    aas_type: str
    digest: str                     # SHA-256 of the profile
    registered_at: str
    submodels: list[str]
    published: list[str] = field(default_factory=list)       # what was done on the AAS server
    unknown: list[str] = field(default_factory=list)         # elements the ontology does not describe
    summary: str = ""                                         # of the ontology check
    unchanged: bool = False                                   # the same profile was registered already

    def body(self) -> dict:
        return asdict(self)


def digest(profile: dict) -> str:
    """SHA-256 of what a profile says."""
    return hashlib.sha256(json.dumps(profile, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def b64(identifier: str) -> str:
    """Identifier as the AAS HTTP API expects it in a path (base64url, no padding)."""
    return base64.urlsafe_b64encode(identifier.encode()).decode().rstrip("=")


class AasServer:
    """An AAS repository with the HTTP API of the AAS specification part 2 (BaSyx AAS environment)."""

    def __init__(self, url: str, timeout: float = 10):
        self.url, self.timeout = url.rstrip("/"), timeout

    def call(self, method: str, path: str, body: dict | None = None) -> int:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(f"{self.url}/{path}", data, method=method,
                                         headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.status
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return 404
            raise RuntimeError(f"{method} {self.url}/{path}: HTTP {e.code} {e.read()[:300]!r}") from e
        except OSError as e:
            raise RuntimeError(f"{method} {self.url}/{path}: {e}") from e

    def put(self, kind: str, item: dict) -> str:
        """Replace the item, or create it if the server does not have it."""
        if self.call("PUT", f"{kind}/{b64(item['id'])}", item) != 404:
            return f"PUT {kind} {item['id']}"
        self.call("POST", kind, item)
        return f"POST {kind} {item['id']}"

    def publish(self, env: dict) -> list[str]:
        # Submodels first: a shell that is visible has its submodels.
        return [*[self.put("submodels", sm) for sm in env.get("submodels", [])],
                *[self.put("shells", shell) for shell in env.get("assetAdministrationShells", [])]]

    def remove(self, env: dict) -> list[str]:
        done = []
        for kind, items in (("shells", env.get("assetAdministrationShells", [])), ("submodels", env.get("submodels", []))):
            for item in items:
                if self.call("DELETE", f"{kind}/{b64(item['id'])}") != 404:
                    done.append(f"DELETE {kind} {item['id']}")
        return done


class Registry:
    """What the service knows: one folder with, per resource, its profile, its AAS and the record
    of its registration. The folder is the state, so a restarted service knows the same."""

    def __init__(self, folder: Path | str, blueprint: Blueprint | None = None, server: AasServer | None = None,
                 strict: bool = False):
        self.folder, self.blueprint, self.server, self.strict = Path(folder), blueprint, server, strict
        self.folder.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()

    def file(self, id_short: str, kind: str) -> Path:
        if not id_short.replace("_", "").isalnum():
            raise Refused(400, "read", [f"not an idShort: {id_short!r}"])
        return self.folder / f"{id_short}.{kind}.json"

    def read(self, id_short: str, kind: str) -> dict | None:
        path = self.file(id_short, kind)
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def examine(self, profile: dict) -> tuple[dict, Registration]:
        """Steps 1 to 3: the AAS of a profile and its registration, or Refused."""
        if not isinstance(profile, dict):
            raise Refused(400, "read", ["a profile is a JSON object"])
        try:
            asset = model.asset(profile)
        except model.ProfileError as e:
            raise Refused(400, "read", str(e).splitlines()) from e
        try:
            env = model.environment(asset, profile.get("global_asset_id"))
        except Exception as e:                              # noqa: BLE001 (whatever the conversion trips over)
            raise Refused(400, "build", [f"{type(e).__name__}: {e}"]) from e
        registration = Registration(
            asset.id_short, asset.id, profile.get("aas_type", "ResourceTypeAAS"), digest(profile),
            datetime.now(timezone.utc).isoformat(timespec="seconds"), [sm["idShort"] for sm in env["submodels"]])
        if self.blueprint is not None:
            report = check(env, self.blueprint)
            registration.summary = report.summary()
            registration.unknown = [str(f) for f in report.unknown]
            broken = [str(f) for f in report.errors] + (registration.unknown if self.strict else [])
            if broken:
                raise Refused(422, "check", broken)
        return env, registration

    def register(self, profile: dict) -> Registration:
        env, registration = self.examine(profile)
        with self.lock:
            kept = self.read(registration.id_short, "registration")
            if kept and kept["digest"] == registration.digest:
                return Registration(**{**kept, "unchanged": True})
            if self.server is not None:
                try:
                    registration.published = self.server.publish(env)
                except RuntimeError as e:
                    raise Refused(502, "publish", [str(e)]) from e
            for kind, content in (("profile", profile), ("aas", env), ("registration", registration.body())):
                self.file(registration.id_short, kind).write_text(json.dumps(content, indent=1), encoding="utf-8")
        return registration

    def derive(self, shell: str) -> dict:
        """The offered capabilities of a module on the AAS server derived anew from its skills and
        those of its components (``modreg.offer.capabilities``), and put back: after the skill
        editor saved the Skills submodel, or a skill was built."""
        if self.server is None:
            raise Refused(400, "derive", ["the service has no AAS server (--basyx) to read the module from"])
        try:
            module, components = desired.load(self.server.url, shell)
        except desired.NotDescribed as e:
            raise Refused(404, "derive", [str(e)]) from e
        derived = capabilities(module, components)
        stored = desired.store(self.server.url, derived, module)
        found = []
        for box in offer_children(offer_at(desired.submodel(derived, "CapabilityDescription"), OFFERED_SET)):
            capability = offer_at(box, "Capability")
            relation = next(iter(offer_children(offer_at(box, "CapabilityRelations"))), {})
            found.append({"idShort": box["idShort"],
                          "capability": capability["supplementalSemanticIds"][0]["keys"][0]["value"],
                          "skill": (relation.get("second") or {}).get("keys", [{}])[-1].get("value"),
                          **{q["type"]: q["value"] for q in capability.get("qualifiers", [])
                             if q["type"] in ("Derived", "Availability")}})
        return {"shell": derived["assetAdministrationShells"][0]["idShort"], "stored": stored, "capabilities": found}

    def keep_build(self, id_short: str, record: dict) -> None:
        """Keep the record of what was built on a module (``modsync``'s record)."""
        if not isinstance(record, dict) or record.get("modelType") != "Submodel":
            raise Refused(400, "read", ["a record of what was built is a Control Configuration submodel"])
        with self.lock:
            self.file(id_short, "build").write_text(json.dumps(record, indent=1), encoding="utf-8")

    def registrations(self) -> list[dict]:
        return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(self.folder.glob("*.registration.json"))]

    def remove(self, id_short: str) -> list[str]:
        with self.lock:
            env = self.read(id_short, "aas")
            if env is None:
                raise Refused(404, "read", [f"{id_short} is not registered"])
            try:
                done = self.server.remove(env) if self.server is not None else []
            except RuntimeError as e:
                raise Refused(502, "publish", [str(e)]) from e
            for kind in ("profile", "aas", "registration", "build"):
                self.file(id_short, kind).unlink(missing_ok=True)
        return done


class Handler(BaseHTTPRequestHandler):
    registry: Registry
    server_version = "modreg"

    def answer(self, status: int, body):
        data = json.dumps(body, indent=1).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        # The web UI (another origin) calls it from the browser: the lab network, no credentials.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def body(self):
        length = int(self.headers.get("Content-Length") or 0)
        try:
            return json.loads(self.rfile.read(length))
        except ValueError as e:
            raise Refused(400, "read", [f"not JSON: {e}"]) from e

    def route(self, method: str):
        url = urllib.parse.urlsplit(self.path)
        parts = [p for p in url.path.split("/") if p]
        query = urllib.parse.parse_qs(url.query)
        try:
            if method == "GET" and parts == ["health"]:
                r = self.registry
                return self.answer(200, {"status": "ok", "types": list(model.TYPES), "strict": r.strict,
                                         "ontology": str(r.blueprint.folder) if r.blueprint else None,
                                         "aas_server": r.server.url if r.server else None})
            if method == "POST" and parts[:1] == ["capabilities"] and len(parts) == 2:
                return self.answer(200, self.registry.derive(urllib.parse.unquote(parts[1])))
            if parts[:1] == ["build"] and len(parts) == 2:
                if method == "GET":
                    found = self.registry.read(parts[1], "build")
                    return self.answer(200, found) if found is not None else self.answer(404, {"error": f"no record of {parts[1]}"})
                if method == "PUT":
                    self.registry.keep_build(parts[1], self.body())
                    return self.answer(200, {"kept": parts[1]})
            if parts[:1] != ["profiles"] or len(parts) > 3:
                return self.answer(404, {"error": f"no {url.path}"})
            if method == "POST" and len(parts) == 1:
                profile = self.body()
                if query.get("check", ["0"])[0] not in ("0", "false", ""):
                    return self.answer(200, {**self.registry.examine(profile)[1].body(), "checked_only": True})
                registration = self.registry.register(profile)
                return self.answer(200 if registration.unchanged else 201, registration.body())
            if method == "GET" and len(parts) == 1:
                return self.answer(200, self.registry.registrations())
            if method == "GET":
                kind = parts[2] if len(parts) == 3 else "registration"
                found = self.registry.read(parts[1], kind) if kind in ("registration", "profile", "aas") else None
                return self.answer(200, found) if found is not None else self.answer(404, {"error": f"no {url.path}"})
            if method == "DELETE" and len(parts) == 2:
                return self.answer(200, {"removed": parts[1], "published": self.registry.remove(parts[1])})
            return self.answer(405, {"error": f"{method} {url.path} is not possible"})
        except Refused as e:
            self.answer(e.status, {"error": str(e), "step": e.step, "reasons": e.reasons})

    def do_GET(self):          # noqa: N802 (http.server's naming)
        self.route("GET")

    def do_POST(self):         # noqa: N802
        self.route("POST")

    def do_PUT(self):          # noqa: N802
        self.route("PUT")

    def do_DELETE(self):       # noqa: N802
        self.route("DELETE")

    def do_OPTIONS(self):      # noqa: N802 (a browser asks before it posts JSON to another origin)
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):       # noqa: A002
        print(f"{self.address_string()} {format % args}", flush=True)


def serve(registry: Registry, host: str = "0.0.0.0", port: int = 8090) -> ThreadingHTTPServer:
    """The HTTP server of a registry; ``serve_forever`` runs it."""
    handler = type("RegistryHandler", (Handler,), {"registry": registry})
    return ThreadingHTTPServer((host, port), handler)


def send(service: str, profile: dict, check_only: bool = False, timeout: float = 120) -> tuple[int, dict]:
    """Register a profile with a service; the HTTP status and the answer."""
    url = f"{service.rstrip('/')}/profiles" + ("?check=1" if check_only else "")
    request = urllib.request.Request(url, json.dumps(profile).encode(), method="POST",
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")
