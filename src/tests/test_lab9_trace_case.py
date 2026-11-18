"""Regression for the C-002 trace case: ticket delay must not override the order row."""
import pytest

pytestmark = pytest.mark.student


def _grade(trial, label):
    from pydantic_evals.evaluators import EvaluatorContext

    from lab9.graders import RefundAmountCorrect

    ctx = EvaluatorContext(
        name="t", inputs={}, metadata=None, expected_output=label, output=trial,
        duration=0.0, _span_tree=None, attributes={}, metrics={},
    )
    return RefundAmountCorrect().evaluate(ctx)


def test_c002_seed11_override_fails_and_fixed_shape_passes():
    from lab9.trace_case import investigate

    broken = investigate("seeded_regression", "C-002", 11)
    trial, label = broken["trial"], broken["label"]
    assert trial["lab8_pass"] is False
    override = next(event for event in trial["events"] if event.get("kind") == "model_override")
    assert override["payload"]["delay_days"] == 5
    assert trial["events"][1]["payload"]["lookup_order"]["order"]["delay_days"] == 2
    assert _grade(trial, label).value is False

    fixed = investigate("fixed", "C-002", 11)
    fixed_trial = fixed["trial"]
    assert fixed_trial["lab8_pass"] is True
    assert not any(event.get("kind") == "model_override" for event in fixed_trial["events"])
    assert fixed_trial["snapshot"]["refund_vnd"] == 0
    assert _grade(fixed_trial, fixed["label"]).value is True
