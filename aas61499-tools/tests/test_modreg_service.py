"""modreg.service: registering a profile validates it, builds its AAS, checks it against the
ontology and publishes it.

Needs the ``registration`` extra (aas-model, rdflib); skipped without it. The AAS server is a
stand-in that records what is published; nothing here talks to the lab's.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import urllib.request

import pytest

pytest.importorskip("aas_model")
pytest.importorskip("rdflib")

from modgen import SPECS, load                                              # noqa: E402
from modreg import profile as profiles                                      # noqa: E402
from modreg.__main__ import main                                            # noqa: E402
from modreg.ontology import Blueprint                                       # noqa: E402
from modreg.service import AasServer, Refused, Registry, b64, send, serve   # noqa: E402
from test_modreg_ontology import SHELL, TINY                                # noqa: E402


@pytest.fixture(scope="module")
def stoppering():
    return profiles.describe(load(SPECS / "stoppering.yaml"), "pi", spec_path="cell/modules/stoppering.yaml")


def blueprint(folder, text: str) -> Blueprint:
    (folder / "tiny.ttl").write_text(text, encoding="utf-8")
    return Blueprint(folder)


@pytest.fixture(scope="module")
def tiny(tmp_path_factory):
    """Asks every resource AAS for a submodel that no module has."""
    return blueprint(tmp_path_factory.mktemp("ontology"), TINY + SHELL)


@pytest.fixture(scope="module")
def loose(tmp_path_factory):
    """Knows none of a module's submodels, and asks nothing of the shell."""
    return blueprint(tmp_path_factory.mktemp("ontology"), TINY)


class FakeAasServer:
    """Keeps what is PUT, POSTed and DELETEd, with the status codes of a BaSyx AAS environment."""

    def __init__(self):
        fake = self
        self.items: dict[tuple[str, str], dict] = {}
        self.calls: list[str] = []

        class Handler(BaseHTTPRequestHandler):
            def handle_one(self):
                kind, _, encoded = self.path.strip("/").partition("/")
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"null")
                key = (kind, encoded or b64(body["id"]))
                fake.calls.append(f"{self.command} {kind}")
                if self.command == "POST":
                    status = 409 if key in fake.items else 201
                else:
                    status = 204 if key in fake.items else 404
                if status in (201, 204):
                    fake.items.pop(key, None) if self.command == "DELETE" else fake.items.__setitem__(key, body)
                self.send_response(status)
                self.send_header("Content-Length", "0")
                self.end_headers()

            do_PUT = do_POST = do_DELETE = handle_one       # noqa: N815

            def log_message(self, *args):
                pass

        self.http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.http.server_address[1]}"
        threading.Thread(target=self.http.serve_forever, daemon=True).start()

    def close(self):
        self.http.shutdown()
        self.http.server_close()


@pytest.fixture
def aas_server():
    fake = FakeAasServer()
    yield fake
    fake.close()


@pytest.fixture
def service(tmp_path, aas_server):
    """A running registration service that publishes to the stand-in server; no ontology."""
    registry = Registry(tmp_path / "registry", server=AasServer(aas_server.url))
    http = serve(registry, "127.0.0.1", 0)
    threading.Thread(target=http.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{http.server_address[1]}", registry
    http.shutdown()
    http.server_close()


def get(url: str):
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.loads(response.read())


def test_registering_a_module_publishes_its_aas(service, aas_server, stoppering):
    url, registry = service
    profile = stoppering
    status, answer = send(url, profile)
    assert status == 201 and answer["id_short"] == "StopperingModuleAAS" and not answer["unchanged"]
    assert len(answer["submodels"]) == 8
    # Created on the AAS server: every submodel, then the shell.
    assert aas_server.calls.count("POST submodels") == 8 and aas_server.calls[-1] == "POST shells"
    shell = aas_server.items[("shells", b64(answer["id"]))]
    assert shell["assetInformation"]["globalAssetId"] == profile["global_asset_id"]
    # Kept by the service: the profile as sent and the AAS built from it.
    assert get(f"{url}/profiles/StopperingModuleAAS/profile") == profile
    assert [r["id_short"] for r in get(f"{url}/profiles")] == ["StopperingModuleAAS"]
    assert get(f"{url}/profiles/StopperingModuleAAS/aas")["assetAdministrationShells"][0]["id"] == answer["id"]

    # The same profile again: answered from what is kept, nothing published.
    before = len(aas_server.calls)
    status, again = send(url, profile)
    assert status == 200 and again["unchanged"] and again["registered_at"] == answer["registered_at"]
    assert len(aas_server.calls) == before

    # A changed profile replaces the AAS.
    changed = json.loads(json.dumps(profile))
    changed["nameplate"] = {"SerialNumber": {"value": "STOP-0002"}}
    status, renewed = send(url, changed)
    assert status == 201 and renewed["digest"] != answer["digest"]
    assert aas_server.calls[before:].count("PUT submodels") == 8 and "POST submodels" not in aas_server.calls[before:]

    request = urllib.request.Request(f"{url}/profiles/StopperingModuleAAS", method="DELETE")
    with urllib.request.urlopen(request, timeout=30) as response:
        assert len(json.loads(response.read())["published"]) == 9
    assert aas_server.items == {} and get(f"{url}/profiles") == []


def test_checking_registers_nothing(service, aas_server):
    url, _ = service
    status, answer = send(url, {"aas_type": "ModuleTypeAAS", "id_short": "EmptyModuleAAS"}, check_only=True)
    assert status == 200 and answer["checked_only"] and aas_server.calls == [] and get(f"{url}/profiles") == []


def test_an_invalid_profile_is_refused(service, aas_server):
    url, _ = service
    status, answer = send(url, {"aas_type": "ModuleTypeAAS", "id_short": "BadModuleAAS", "nameplate": {"Colour": {"value": "red"}}})
    assert status == 400 and answer["step"] == "read" and "Colour" in "\n".join(answer["reasons"])
    assert aas_server.calls == [] and get(f"{url}/profiles") == []


def test_an_aas_that_breaks_the_ontology_is_refused(tmp_path, tiny, aas_server):
    registry = Registry(tmp_path / "registry", tiny, AasServer(aas_server.url))
    with pytest.raises(Refused) as refused:
        registry.register({"aas_type": "ModuleTypeAAS", "id_short": "EmptyModuleAAS"})
    assert refused.value.status == 422 and refused.value.step == "check"
    assert "ResourceAAS needs exactly 1 Plate" in refused.value.reasons[0]
    assert aas_server.calls == [] and registry.registrations() == []


def test_strict_refuses_what_the_ontology_does_not_describe(tmp_path, loose):
    profile = {"aas_type": "ModuleTypeAAS", "id_short": "EmptyModuleAAS"}
    registration = Registry(tmp_path / "lenient", loose).register(profile)
    assert len(registration.unknown) == len(registration.submodels) == 8       # the tiny ontology knows none of them
    with pytest.raises(Refused, match="is not in the ontology") as refused:
        Registry(tmp_path / "strict", loose, strict=True).register(profile)
    assert refused.value.status == 422


def test_an_unreachable_aas_server_refuses_the_registration(tmp_path):
    registry = Registry(tmp_path / "registry", server=AasServer("http://127.0.0.1:9", timeout=2))
    with pytest.raises(Refused) as refused:
        registry.register({"aas_type": "ModuleTypeAAS", "id_short": "EmptyModuleAAS"})
    assert refused.value.status == 502 and registry.registrations() == []


def test_the_command_line(service, tmp_path, capsys):
    url, _ = service
    assert main(["profile", "stoppering", "--target", "pi", "--out", str(tmp_path / "profiles")]) == 0
    written = tmp_path / "profiles" / "StopperingModuleAAS.json"
    assert json.loads(written.read_text(encoding="utf-8"))["aas_type"] == "ModuleTypeAAS"
    assert main(["build", str(written), "--out", str(tmp_path / "aas")]) == 0
    assert len(json.loads((tmp_path / "aas" / "StopperingModuleAAS.json").read_text(encoding="utf-8"))["submodels"]) == 8
    assert main(["register", str(written), "--service", url]) == 0
    assert "registered: StopperingModuleAAS" in capsys.readouterr().out
    assert main(["register", str(written), "--service", url]) == 0
    assert "unchanged: StopperingModuleAAS" in capsys.readouterr().out
