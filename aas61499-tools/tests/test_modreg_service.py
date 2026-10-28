"""modreg.service: registering a profile validates it, builds its AAS, checks it against the
ontology and publishes it.

Needs the ``registration`` extra (aas-model, rdflib); skipped without it. The AAS server is a
stand-in that records what is published; nothing here talks to the lab's.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import gzip
from pathlib import Path
import threading
import urllib.error
import urllib.parse
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

            def do_GET(self):                               # noqa: N802
                url = urllib.parse.urlsplit(self.path)
                kind, _, encoded = url.path.strip("/").partition("/")
                if encoded:
                    found = fake.items.get((kind, encoded))
                else:
                    found = {"result": [v for (k, _), v in fake.items.items() if k == kind], "paging_metadata": {}}
                data = json.dumps(found).encode()
                self.send_response(200 if found is not None else 404)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

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
    assert len(answer["submodels"]) == 7      # with the Capability Description, without what was built
    # Created on the AAS server: every submodel, then the shell.
    assert aas_server.calls.count("POST submodels") == 7 and aas_server.calls[-1] == "POST shells"
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
    # The record of what was built on the module is kept beside it, not in its AAS.
    record = {"idShort": "ControlConfiguration", "modelType": "Submodel", "id": f"{answer['id']}/submodels/ControlConfiguration",
              "submodelElements": [{"idShort": "ReadAt", "modelType": "Property", "valueType": "xs:string",
                                    "value": "2026-10-02T12:00:00+00:00"}]}
    with pytest.raises(urllib.error.HTTPError):
        get(f"{url}/build/StopperingModuleAAS")
    request = urllib.request.Request(f"{url}/build/StopperingModuleAAS", json.dumps(record).encode(), method="PUT",
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        assert json.loads(response.read()) == {"kept": "StopperingModuleAAS"}
    assert get(f"{url}/build/StopperingModuleAAS") == record and len(aas_server.calls) == before

    # A changed profile replaces the AAS.
    changed = json.loads(json.dumps(profile))
    changed["nameplate"] = {"SerialNumber": {"value": "STOP-0002"}}
    status, renewed = send(url, changed)
    assert status == 201 and renewed["digest"] != answer["digest"]
    assert aas_server.calls[before:].count("PUT submodels") == 7 and "POST submodels" not in aas_server.calls[before:]

    request = urllib.request.Request(f"{url}/profiles/StopperingModuleAAS", method="DELETE")
    with urllib.request.urlopen(request, timeout=30) as response:
        assert len(json.loads(response.read())["published"]) == 8
    assert aas_server.items == {} and get(f"{url}/profiles") == []
    with pytest.raises(urllib.error.HTTPError):                    # the record goes with it
        get(f"{url}/build/StopperingModuleAAS")


def test_the_skill_editor_has_the_capabilities_derived_anew(service, aas_server):
    """After the skill editor saved the Skills submodel, it asks the service to derive the module's
    capabilities anew: the service reads the module and its components from the AAS server and
    puts the Capability Description back."""
    url, _ = service
    for profile in profiles.describe_all(load(SPECS / "filling.yaml"), "pi"):
        assert send(url, profile)[0] == 201

    def derive() -> dict:
        request = urllib.request.Request(f"{url}/capabilities/FillingModuleAAS", b"", method="POST")
        with urllib.request.urlopen(request, timeout=60) as response:
            assert response.headers["Access-Control-Allow-Origin"] == "*"         # the web UI is another origin
            return json.loads(response.read())

    answer = derive()
    assert [(c["idShort"], c["skill"], c.get("Availability")) for c in answer["capabilities"]] == [("Filling", "Dispensing", None)]
    assert answer["stored"].endswith(": ")                                     # nothing changed, nothing put
    edited = json.loads(gzip.decompress((Path(__file__).parent / "data" / "FillingSkills-edited.json.gz").read_bytes()))
    aas_server.items[("submodels", b64(edited["id"]))] = edited                 # as the skill editor saves it
    answer = derive()
    assert [(c["idShort"], c["skill"], c.get("Availability")) for c in answer["capabilities"]] == \
           [("Filling", "Dispensing", None), ("Filling_DoubleDose", "DoubleDose", "AfterReconfiguration")]
    assert answer["stored"].endswith(": CapabilityDescription") and aas_server.calls[-1] == "PUT submodels"
    stored = aas_server.items[("submodels", b64(f"{profiles.identity(load(SPECS / 'filling.yaml'))[1]}/submodels/CapabilityDescription"))]
    assert [box["idShort"] for box in stored["submodelElements"][0]["value"]] == ["Filling", "Filling_DoubleDose"]


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
    assert len(registration.unknown) == len(registration.submodels) == 6       # the tiny ontology knows none of them
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
    assert len(json.loads((tmp_path / "aas" / "StopperingModuleAAS.json").read_text(encoding="utf-8"))["submodels"]) == 7
    assert main(["register", str(written), "--service", url]) == 0
    assert "registered: StopperingModuleAAS" in capsys.readouterr().out
    assert main(["register", str(written), "--service", url]) == 0
    assert "unchanged: StopperingModuleAAS" in capsys.readouterr().out


def test_modsync_registers_the_module_it_describes(service, aas_server, tmp_path, monkeypatch, capsys):
    from modsync.__main__ import main as modsync

    url, registry = service
    monkeypatch.setattr("sys.argv", ["modsync", "describe", "stoppering", "--target", "pi", "--out", str(tmp_path / "aas"),
                                     "--register", url])
    modsync()
    assert f"registration: registered StopperingModuleAAS at {url}" in capsys.readouterr().out
    # The module and, with it, the components whose skills it carries out.
    assert sorted(r["id_short"] for r in registry.registrations()) == [
        "StopperingLinearAxisAAS", "StopperingModuleAAS", "StopperingPistonAAS"]
    assert aas_server.calls[-1] == "POST shells"


def post(url: str, body: dict | None = None):
    request = urllib.request.Request(url, json.dumps(body).encode() if body is not None else b"", method="POST",
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def test_the_skill_editor_has_a_flow_checked_and_a_skill_planned(service, aas_server):
    """The editor's two questions (G7): what does not hold in a flow it holds, saved or not, and
    which skill carries out a capability, described on the AAS server when asked to."""
    pytest.importorskip("gtpyhop")
    url, _ = service
    for profile in profiles.describe_all(load(SPECS / "filling.yaml"), "pi"):
        assert send(url, profile)[0] == 201
    status, answer = post(f"{url}/check/FillingModuleAAS")
    assert status == 200 and answer["skills"] == {"Dispensing": []}
    # Dispensing as the editor holds it, without its first step (the needle down): dispensing then
    # happens with the needle up, which the checker says, with what would fix it.
    skills_id = f"{profiles.identity(load(SPECS / 'filling.yaml'))[1]}/submodels/Skills"
    dispensing = next(e for e in aas_server.items[("submodels", b64(skills_id))]["submodelElements"]
                      if e["idShort"] == "Dispensing")
    edited = json.loads(json.dumps(dispensing))
    steps = next(c for c in next(c for c in edited["value"] if c["idShort"] == "Start")["value"] if c["idShort"] == "Steps")
    steps["value"] = [s for s in steps["value"]
                      if not any(c["idShort"] == "Name" and c.get("value") == "NeedleDown" for c in s["value"])]
    assert post(f"{url}/check/FillingModuleAAS", {"skill": {"value": []}})[0] == 400
    status, answer = post(f"{url}/check/FillingModuleAAS", {"skill": edited})
    assert status == 200 and list(answer["skills"]) == ["Dispensing"]
    [finding] = answer["skills"]["Dispensing"]
    assert finding["step"] == "Dispense" and finding["what"] == "needs LinearAxis_ActualPosition.Position = 40.0, but it is 0.0"
    assert finding["fix"] == ["MoveAxis(Position=40.0)"]
    # A skill planned and described on the server, then checked there with the others.
    status, answer = post(f"{url}/plan/FillingModuleAAS", {"capability": "Filling", "values": {"FillVolume": 2.0},
                                                          "results": ["FillWeight"], "name": "FillTwo", "write": True})
    assert status == 200 and [s["skill"] for s in answer["steps"]] == ["MoveAxis", "Dispense", "Home", "Weigh"]
    assert answer["name"] == "FillTwo" and answer["stored"].endswith("Skills")
    status, answer = post(f"{url}/check/FillingModuleAAS")
    assert answer["skills"] == {"Dispensing": [], "FillTwo": []}
    assert post(f"{url}/plan/FillingModuleAAS", {"capability": "Filling", "values": {"FillVolume": 2.0},
                                                 "results": ["Nothing"]})[0] == 422
