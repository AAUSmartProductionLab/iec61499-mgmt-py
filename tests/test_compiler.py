"""Tests for the BPMN sequence compiler."""
import json
from pathlib import Path

import pytest

from iec61499_mgmt.models import IECValue
from skill_compiler import compile_bpmn
from skill_compiler.bpmn import instance_name, sequence
from skill_compiler.models import RecipeBindings, TargetProfile

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def inputs():
    """Load the example BPMN, bindings, target and product values."""
    return ((EXAMPLES / "fill.bpmn").read_text(),
            RecipeBindings.model_validate_json((EXAMPLES / "bindings.json").read_text()),
            TargetProfile.model_validate_json((EXAMPLES / "target.json").read_text()),
            {k: IECValue.model_validate(v) for k, v in json.loads((EXAMPLES / "product.json").read_text()).items()})


def test_compile_example():
    """The example compiles with its parameter and network hash."""
    result = compile_bpmn(*inputs())
    assert result.procedure.calls[0].parameters["volume"].value == 0.5
    assert result.network.instances[0].parameters["P1"].type == "LREAL"
    assert result.skill.validation == "structure_only"
    assert result.skill.network_hash == result.network.digest()
    assert result.skill.product_parameters == ["FillVolume"]


def test_labels_do_not_change_runtime_identity():
    """Renaming a task does not change the network."""
    xml, bindings, target, product = inputs()
    a = compile_bpmn(xml, bindings, target, product)
    b = compile_bpmn(xml.replace("Dose liquid", "Operator renamed this"), bindings, target, product)
    assert a.network.digest() == b.network.digest()


def test_range_violation_identifies_task():
    """An out-of-range value names the task and parameter."""
    xml, bindings, target, _ = inputs()
    with pytest.raises(ValueError, match="Dose.volume.*maximum"):
        compile_bpmn(xml, bindings, target, {"FillVolume": IECValue(type="LREAL", value=3.0)})


@pytest.mark.parametrize("old,new", [
    ("serviceTask", "exclusiveGateway"),
    ('name="Dose liquid"/>', 'name="Dose liquid"><standardLoopCharacteristics/></serviceTask>'),
    ('<endEvent id="End"/>', '<endEvent id="End"><terminateEventDefinition/></endEvent>'),
    ('targetRef="Dose"', 'targetRef="Missing"'),
    ('id="f2"', 'id="f1"'),
    ('name="Dose liquid"', 'name="Dose liquid" isForCompensation="true"'),
])
def test_reject_unsupported_semantics(old, new):
    """Unsupported BPMN constructs are rejected."""
    xml, *_ = inputs()
    with pytest.raises(ValueError):
        sequence(xml.replace(old, new))


def test_id_encoding_is_collision_free():
    """Different BPMN IDs never map to the same instance name."""
    assert instance_name("PROC", "a-b") != instance_name("PROC", "a_b")
    assert instance_name("PROC", "b_612d62") != instance_name("PROC", "a-b")


def test_disconnected_cycle_is_rejected():
    """A detached cycle of tasks is rejected."""
    xml, *_ = inputs()
    extra = '<task id="A"/><task id="B"/><sequenceFlow id="f3" sourceRef="A" targetRef="B"/><sequenceFlow id="f4" sourceRef="B" targetRef="A"/>'
    with pytest.raises(ValueError, match="connected"):
        sequence(xml.replace("</process>", extra + "</process>"))


def test_repeated_skill_cannot_silently_share_data_inputs():
    """Two calls of one skill cannot drive the same inputs."""
    xml, bindings, target, product = inputs()
    xml = xml.replace('sourceRef="Dose" targetRef="End"', 'sourceRef="Dose" targetRef="DoseAgain"')
    xml = xml.replace('</process>', '<task id="DoseAgain"/><sequenceFlow id="f3" sourceRef="DoseAgain" targetRef="End"/></process>')
    bindings = RecipeBindings(procedure_id=bindings.procedure_id,
                              tasks={**bindings.tasks, "DoseAgain": bindings.tasks["Dose"]})
    with pytest.raises(ValueError, match="Multiple drivers"):
        compile_bpmn(xml, bindings, target, product)
