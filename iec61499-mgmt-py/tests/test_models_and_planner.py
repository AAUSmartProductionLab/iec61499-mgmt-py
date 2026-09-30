"""Tests for the network models, patches and planner."""
import pytest

from iec61499_mgmt import Network, NetworkPatch, TypeLibrary, plan
from iec61499_mgmt.models import IECValue


@pytest.fixture
def library():
    """Type library with Split and Merge types and two boundary ports."""
    return TypeLibrary.model_validate({
        "build_id": "test", "types": {
            "Split": {"name": "Split", "type_hash": "aa", "ports": {
                "EI": {"kind": "event", "direction": "input"},
                "EO": {"kind": "event", "direction": "output"},
                "N": {"kind": "data", "direction": "input", "data_type": "UINT", "writable": True}}},
            "Merge": {"name": "Merge", "type_hash": "bb", "ports": {
                "EI": {"kind": "event", "direction": "input"},
                "EO": {"kind": "event", "direction": "output"}}}},
        "boundary_ports": {"Clock.EO": {"kind": "event", "direction": "output"},
                           "Count.CU": {"kind": "event", "direction": "input"}}})


@pytest.fixture
def current():
    """Network with one PROC.A instance between the boundary ports."""
    return Network.model_validate({"resource": "RES", "instances": [
        {"name": "PROC.A", "type": "Split", "type_hash": "aa", "parameters": {"N": {"type": "UINT", "value": 1}}}],
        "connections": [{"source": "Clock.EO", "destination": "PROC.A.EI"},
                        {"source": "PROC.A.EO", "destination": "Count.CU"}]})


def test_parameter_patch_only_writes(current, library):
    """A parameter patch plans a single WRITE."""
    patch = NetworkPatch.model_validate({"base_hash": current.digest(), "operations": [
        {"op": "set_parameter", "instance": "PROC.A", "parameter": "N", "value": {"type": "UINT", "value": 2}}]})
    desired = patch.apply(current)
    result = plan(current, desired, library)
    assert result.change_class == "parameter"
    assert [(c.op, c.destination, c.value) for c in result.commands] == [("write", "PROC.A.N", "2")]
    assert current.instances[0].parameters["N"].value == 1
    assert result.verification[-1].op == "read"
    assert not plan(desired, desired, library).commands


def test_stale_patch(current):
    """A patch with the wrong base hash is refused."""
    with pytest.raises(ValueError, match="Stale"):
        NetworkPatch(base_hash="0" * 64, operations=[]).apply(current)


def test_structural_order_and_boundary_isolation(current, library):
    """Structural changes are ordered and touch only PROC."""
    data = current.model_dump()
    data["instances"].append({"name": "PROC.B", "type": "Merge", "type_hash": "bb"})
    data["connections"][-1] = {"source": "PROC.A.EO", "destination": "PROC.B.EI"}
    data["connections"].append({"source": "PROC.B.EO", "destination": "Count.CU"})
    result = plan(current, Network.model_validate(data), library)
    assert result.change_class == "structural"
    assert [c.op for c in result.commands] == ["stop", "disconnect", "create_fb", "connect", "connect", "start", "start"]
    assert all(c.name.startswith("PROC.") for c in result.commands if c.name)


def test_replacement_reconnects_even_identical_edges(current, library):
    """A replaced instance gets all its edges reconnected."""
    data = current.model_dump()
    data["instances"][0].update(type="Merge", type_hash="bb", parameters={})
    result = plan(current, Network.model_validate(data), library)
    assert [c.op for c in result.commands] == ["stop", "disconnect", "disconnect", "delete_fb", "create_fb", "connect", "connect", "start"]


def test_flow_keeps_instances(current, library):
    """A flow change only rewires connections."""
    data = current.model_dump()
    data["connections"].pop()
    result = plan(current, Network.model_validate(data), library)
    assert result.change_class == "flow"
    assert [c.op for c in result.commands] == ["stop", "disconnect", "start"]


def test_remove_cleans_edges(current, library):
    """Removing an instance also removes its connections."""
    patch = NetworkPatch.model_validate({"base_hash": current.digest(), "operations": [{"op": "remove_instance", "name": "PROC.A"}]})
    desired = patch.apply(current)
    assert not desired.instances and not desired.connections
    assert [c.op for c in plan(current, desired, library).commands] == ["stop", "disconnect", "disconnect", "delete_fb"]


@pytest.mark.parametrize("mutation,match", [
    (lambda d: d["instances"][0].update(name="Fixed.A"), "owned scope"),
    (lambda d: d["connections"][0].update(destination="PROC.Missing.EI"), "Dangling"),
    (lambda d: d["instances"].append(d["instances"][0]), "Duplicate"),
])
def test_invalid_graph(current, mutation, match):
    """Invalid networks fail validation."""
    data = current.model_dump()
    mutation(data)
    with pytest.raises(ValueError, match=match):
        Network.model_validate(data)


@pytest.mark.parametrize("mutation,match", [
    (lambda d: d["instances"][0].update(type_hash="deadbeef"), "Unavailable"),
    (lambda d: d["connections"][0].update(source="Unknown.EO"), "Unknown connection"),
    (lambda d: d["connections"][0].update(destination="PROC.A.EO"), "direction"),
    (lambda d: d["instances"][0]["parameters"].update(N={"type": "INT", "value": 1}), "parameter binding"),
])
def test_invalid_library_bindings(current, library, mutation, match):
    """Networks that do not fit the type library are refused."""
    data = current.model_dump()
    mutation(data)
    with pytest.raises(ValueError, match=match):
        Network.model_validate(data).validate_library(library)


def test_omitting_parameter_is_not_a_reset(current, library):
    """Dropping a parameter needs an explicit reset value."""
    data = current.model_dump()
    data["instances"][0]["parameters"] = {}
    with pytest.raises(ValueError, match="explicit reset"):
        plan(current, Network.model_validate(data), library)


def test_canonical_hash_ignores_order_and_provenance(current):
    """The digest ignores order and origin metadata."""
    data = current.model_dump()
    data["connections"].reverse()
    data["instances"][0]["origin"] = "Different display metadata"
    assert Network.model_validate(data).digest() == current.digest()


@pytest.mark.parametrize("typ,value", [("BOOL", 1), ("UINT", -1), ("UINT", 65536), ("INT", True),
                                        ("LREAL", "1.0"), ("LREAL", float("nan")), ("TIME", -1), ("STRING", "a\n")])
def test_invalid_values(typ, value):
    """Invalid IEC values are rejected."""
    with pytest.raises(ValueError):
        IECValue(type=typ, value=value)


def test_iec_string_escaping():
    """STRING literals escape $ and quotes."""
    assert IECValue(type="STRING", value="a'$b").literal() == "'a$'$$b'"


def test_lreal_canonicalization():
    """LREAL 1 and 1.0 serialise the same."""
    assert IECValue(type="LREAL", value=1).model_dump_json() == IECValue(type="LREAL", value=1.0).model_dump_json()


def test_empty_type_hash_requires_verified_build(tmp_path):
    """Empty type hashes need a pinned, verified runtime binary."""
    import hashlib
    binary = tmp_path / "runtime.bin"
    binary.write_bytes(b"test runtime build")
    digest = hashlib.sha256(binary.read_bytes()).hexdigest()
    data = {"build_id": "test", "types": {"T": {"name": "T", "type_hash": "", "ports": {}}}}
    with pytest.raises(ValueError, match="build pinning"):
        TypeLibrary.model_validate(data)
    library = TypeLibrary.model_validate({**data, "runtime_binary_sha256": digest})
    library.verify_executable(binary)
    desired = Network.model_validate({"resource": "RES", "instances": [{"name": "PROC.A", "type": "T", "type_hash": ""}]})
    result = plan(Network(resource="RES"), desired, library)
    assert result.commands[0].type == "T"
    assert result.required_runtime_binary_sha256 == digest
    binary.write_bytes(b"different build")
    with pytest.raises(ValueError, match="does not match"):
        library.verify_executable(binary)
