from datetime import UTC, datetime

import pytest

from ix_vahdat.domain import DecisionStatus, RiskLevel
from ix_vahdat.review import (
    ReviewDecision,
    ReviewerRecord,
    ReviewStatus,
    require_human_review,
)


def _reviewer(decision: ReviewDecision = ReviewDecision.APPROVE_LIMITED_USE) -> ReviewerRecord:
    return ReviewerRecord(
        reviewer_id="reviewer-001",
        reviewer_name="Field Reviewer",
        role="water-quality lead",
        organization="local response team",
        reviewed_at=datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC),
        decision=decision,
        authority_basis="local operator review for proof-of-concept testing",
        notes="reviewed evidence bundle and approved limited non-autonomous field use",
    )


def test_reviewer_record_requires_timezone_aware_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        ReviewerRecord(
            reviewer_id="reviewer-001",
            reviewer_name="Field Reviewer",
            role="water-quality lead",
            organization="local response team",
            reviewed_at=datetime(2026, 5, 14, 12, 0, 0),
            decision=ReviewDecision.APPROVE_LIMITED_USE,
            authority_basis="local operator review",
            notes="reviewed evidence",
        )


def test_reviewer_record_requires_authority_basis() -> None:
    with pytest.raises(ValueError, match="authority_basis"):
        ReviewerRecord(
            reviewer_id="reviewer-001",
            reviewer_name="Field Reviewer",
            role="water-quality lead",
            organization="local response team",
            reviewed_at=datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC),
            decision=ReviewDecision.APPROVE_LIMITED_USE,
            authority_basis=" ",
            notes="reviewed evidence",
        )


def test_blocked_upstream_status_cannot_be_approved_even_with_reviewer() -> None:
    result = require_human_review(
        upstream_status=DecisionStatus.BLOCK,
        upstream_risk=RiskLevel.CRITICAL,
        action_label="release water for public use",
        reviewer=_reviewer(),
    )

    assert result.status is ReviewStatus.REJECTED
    assert result.decision_status is DecisionStatus.BLOCK
    assert result.risk_level is RiskLevel.CRITICAL
    assert result.is_approved is False
    assert "do not perform field action" in result.required_actions


def test_hold_for_testing_upstream_status_requires_more_evidence() -> None:
    result = require_human_review(
        upstream_status=DecisionStatus.HOLD_FOR_TESTING,
        upstream_risk=RiskLevel.MODERATE,
        action_label="route water to treatment skid",
        reviewer=_reviewer(),
    )

    assert result.status is ReviewStatus.NEEDS_MORE_EVIDENCE
    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.risk_level is RiskLevel.HIGH
    assert result.is_approved is False


def test_missing_reviewer_prevents_action() -> None:
    result = require_human_review(
        upstream_status=DecisionStatus.ALLOW_REVIEW,
        upstream_risk=RiskLevel.LOW,
        action_label="classify batch as hygiene candidate",
        reviewer=None,
    )

    assert result.status is ReviewStatus.NOT_REVIEWED
    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.risk_level is RiskLevel.HIGH
    assert result.is_approved is False
    assert "assign qualified human reviewer" in result.required_actions


def test_reviewer_can_request_more_evidence() -> None:
    result = require_human_review(
        upstream_status=DecisionStatus.ALLOW_REVIEW,
        upstream_risk=RiskLevel.MODERATE,
        action_label="send treated water to storage",
        reviewer=_reviewer(ReviewDecision.REQUEST_MORE_EVIDENCE),
    )

    assert result.status is ReviewStatus.NEEDS_MORE_EVIDENCE
    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.risk_level is RiskLevel.HIGH
    assert result.is_approved is False


def test_reviewer_can_reject_action() -> None:
    result = require_human_review(
        upstream_status=DecisionStatus.ALLOW_REVIEW,
        upstream_risk=RiskLevel.MODERATE,
        action_label="use water for irrigation trial",
        reviewer=_reviewer(ReviewDecision.REJECT),
    )

    assert result.status is ReviewStatus.REJECTED
    assert result.decision_status is DecisionStatus.BLOCK
    assert result.risk_level is RiskLevel.HIGH
    assert result.is_approved is False


def test_reviewer_can_approve_limited_use_after_upstream_allow_review() -> None:
    result = require_human_review(
        upstream_status=DecisionStatus.ALLOW_REVIEW,
        upstream_risk=RiskLevel.LOW,
        action_label="hold treated water as drinking candidate pending local approval",
        reviewer=_reviewer(),
    )

    assert result.status is ReviewStatus.APPROVED_FOR_LIMITED_USE
    assert result.decision_status is DecisionStatus.ALLOW_REVIEW
    assert result.risk_level is RiskLevel.LOW
    assert result.is_approved is True
    assert "follow reviewer limits and local requirements" in result.required_actions


def test_action_label_is_required() -> None:
    with pytest.raises(ValueError, match="action_label"):
        require_human_review(
            upstream_status=DecisionStatus.ALLOW_REVIEW,
            upstream_risk=RiskLevel.LOW,
            action_label=" ",
            reviewer=_reviewer(),
        )
