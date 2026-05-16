import pytest

from ix_vahdat.bom import DeploymentTier
from ix_vahdat.domain import DecisionStatus, RiskLevel
from ix_vahdat.runbooks import (
    RunbookStep,
    RunbookStepKind,
    RunbookStepResult,
    RunbookStepStatus,
    WaterNodeRunbook,
    evaluate_runbook,
)


def _step(**overrides: object) -> RunbookStep:
    values = {
        "step_id": "safety-brief",
        "title": "Complete safety briefing",
        "kind": RunbookStepKind.SAFETY_BRIEF,
        "instructions": (
            "review non-claims and local approval requirements",
            "confirm no autonomous physical control is enabled",
        ),
        "required_evidence": ("signed safety checklist",),
        "requires_human_review": True,
        "hold_point": True,
        "safety_critical": True,
        "notes": "review-only proof-of-concept step",
    }
    values.update(overrides)
    return RunbookStep(**values)  # type: ignore[arg-type]


def _runbook(*steps: RunbookStep) -> WaterNodeRunbook:
    return WaterNodeRunbook(
        runbook_id="demo-node-commissioning",
        title="Demo Node Commissioning Runbook",
        deployment_tier=DeploymentTier.DEMO_NODE,
        steps=steps or (_step(),),
    )


def _result(**overrides: object) -> RunbookStepResult:
    values = {
        "step_id": "safety-brief",
        "status": RunbookStepStatus.PASSED,
        "evidence_refs": ("receipt:safety-checklist",),
        "reviewer_id": "reviewer-001",
        "notes": "reviewed by local operator",
    }
    values.update(overrides)
    return RunbookStepResult(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("field", "value", "expected_message"),
    [
        ("step_id", " ", "step_id"),
        ("title", " ", "step title"),
        ("instructions", (), "instructions"),
        ("instructions", (" ",), "instructions"),
        ("required_evidence", (" ",), "required_evidence"),
        ("notes", " ", "notes"),
    ],
)
def test_runbook_step_rejects_invalid_values(
    field: str,
    value: object,
    expected_message: str,
) -> None:
    with pytest.raises(ValueError, match=expected_message):
        _step(**{field: value})


@pytest.mark.parametrize(
    ("field", "value", "expected_message"),
    [
        ("step_id", " ", "step_id"),
        ("evidence_refs", (" ",), "evidence_refs"),
        ("reviewer_id", " ", "reviewer_id"),
        ("notes", " ", "notes"),
    ],
)
def test_runbook_step_result_rejects_invalid_values(
    field: str,
    value: object,
    expected_message: str,
) -> None:
    with pytest.raises(ValueError, match=expected_message):
        _result(**{field: value})


def test_runbook_rejects_empty_steps() -> None:
    with pytest.raises(ValueError, match="at least one step"):
        WaterNodeRunbook(
            runbook_id="empty",
            title="Empty Runbook",
            deployment_tier=DeploymentTier.DEMO_NODE,
            steps=(),
        )


def test_runbook_rejects_duplicate_step_ids() -> None:
    with pytest.raises(ValueError, match="unique"):
        _runbook(_step(step_id="same"), _step(step_id="same"))


def test_runbook_exposes_hold_point_and_safety_critical_step_ids() -> None:
    runbook = _runbook(
        _step(step_id="safety-brief"),
        _step(
            step_id="inventory",
            title="Inventory components",
            kind=RunbookStepKind.INVENTORY_CHECK,
            hold_point=False,
            safety_critical=False,
            requires_human_review=False,
        ),
    )

    assert runbook.hold_point_step_ids == ("safety-brief",)
    assert runbook.safety_critical_step_ids == ("safety-brief",)


def test_complete_runbook_allows_review_only() -> None:
    result = evaluate_runbook(runbook=_runbook(), results=(_result(),))

    assert result.decision_status is DecisionStatus.ALLOW_REVIEW
    assert result.risk_level is RiskLevel.LOW
    assert result.runbook_ready_for_review is True
    assert result.completed_steps == ("safety-brief",)
    assert result.incomplete_steps == ()
    assert result.blocked_steps == ()
    assert "runbook steps are complete and evidence is reviewable" in result.reasons
    assert "do not claim certification, public-health approval, or deployment authorization" in (
        result.required_actions
    )


def test_missing_step_result_holds_for_testing() -> None:
    result = evaluate_runbook(runbook=_runbook(), results=())

    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.risk_level is RiskLevel.HIGH
    assert result.runbook_ready_for_review is False
    assert result.incomplete_steps == ("safety-brief",)
    assert "Complete safety briefing has no recorded result" in result.reasons


def test_not_started_step_holds_for_testing() -> None:
    result = evaluate_runbook(
        runbook=_runbook(),
        results=(_result(status=RunbookStepStatus.NOT_STARTED),),
    )

    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.risk_level is RiskLevel.HIGH
    assert result.incomplete_steps == ("safety-brief",)
    assert "Complete safety briefing is not started" in result.reasons


def test_passed_step_without_required_evidence_holds_for_testing() -> None:
    result = evaluate_runbook(
        runbook=_runbook(),
        results=(_result(evidence_refs=()),),
    )

    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.risk_level is RiskLevel.HIGH
    assert result.incomplete_steps == ("safety-brief",)
    assert "Complete safety briefing passed without required evidence references" in (
        result.reasons
    )


def test_human_review_step_without_reviewer_holds_for_testing() -> None:
    result = evaluate_runbook(
        runbook=_runbook(),
        results=(_result(reviewer_id=None),),
    )

    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.risk_level is RiskLevel.HIGH
    assert result.incomplete_steps == ("safety-brief",)
    assert "Complete safety briefing requires human reviewer identity" in result.reasons


def test_failed_safety_critical_hold_point_blocks() -> None:
    result = evaluate_runbook(
        runbook=_runbook(),
        results=(_result(status=RunbookStepStatus.FAILED),),
    )

    assert result.decision_status is DecisionStatus.BLOCK
    assert result.risk_level is RiskLevel.CRITICAL
    assert result.runbook_ready_for_review is False
    assert result.blocked_steps == ("safety-brief",)
    assert "Complete safety briefing result is failed" in result.reasons
    assert "safety-critical step blocks dependent water-support decisions" in (
        result.required_actions
    )
    assert "hold point must be resolved before continuing" in result.required_actions


def test_failed_noncritical_step_holds_instead_of_blocks() -> None:
    runbook = _runbook(
        _step(
            step_id="inventory",
            title="Inventory components",
            kind=RunbookStepKind.INVENTORY_CHECK,
            required_evidence=("inventory photo",),
            requires_human_review=False,
            hold_point=False,
            safety_critical=False,
        )
    )
    result = evaluate_runbook(
        runbook=runbook,
        results=(
            RunbookStepResult(
                step_id="inventory",
                status=RunbookStepStatus.FAILED,
                evidence_refs=("receipt:inventory",),
            ),
        ),
    )

    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.risk_level is RiskLevel.HIGH
    assert result.blocked_steps == ("inventory",)


def test_not_applicable_step_counts_as_completed() -> None:
    runbook = _runbook(
        _step(
            step_id="optional-awh-panel",
            title="Install optional AWH panel",
            kind=RunbookStepKind.ASSEMBLY,
            required_evidence=(),
            requires_human_review=False,
            hold_point=False,
            safety_critical=False,
        )
    )
    result = evaluate_runbook(
        runbook=runbook,
        results=(
            RunbookStepResult(
                step_id="optional-awh-panel",
                status=RunbookStepStatus.NOT_APPLICABLE,
            ),
        ),
    )

    assert result.decision_status is DecisionStatus.ALLOW_REVIEW
    assert result.completed_steps == ("optional-awh-panel",)


def test_unknown_result_step_id_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown runbook step result ids"):
        evaluate_runbook(
            runbook=_runbook(),
            results=(_result(step_id="unknown-step"),),
        )


def test_duplicate_result_step_ids_are_rejected() -> None:
    with pytest.raises(ValueError, match="unique"):
        evaluate_runbook(
            runbook=_runbook(),
            results=(_result(), _result()),
        )
