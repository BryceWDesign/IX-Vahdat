"""Human-review gate for IX-Vahdat.

This module makes the governance boundary explicit: IX-Vahdat may prepare
decision-support outputs, but it must not treat them as authorized field
actions without a human review record.

The gate is intentionally conservative. Missing reviewer identity, missing
authority basis, blocked upstream decisions, or unsafe decision categories
prevent approval.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from ix_vahdat.domain import DecisionStatus, RiskLevel


class ReviewStatus(str, Enum):
    """Human-review state for a decision-support output."""

    NOT_REVIEWED = "not_reviewed"
    APPROVED_FOR_LIMITED_USE = "approved_for_limited_use"
    REJECTED = "rejected"
    NEEDS_MORE_EVIDENCE = "needs_more_evidence"


class ReviewDecision(str, Enum):
    """Reviewer's explicit decision."""

    APPROVE_LIMITED_USE = "approve_limited_use"
    REJECT = "reject"
    REQUEST_MORE_EVIDENCE = "request_more_evidence"


@dataclass(frozen=True, slots=True)
class ReviewerRecord:
    """Human reviewer metadata required for action-gate evaluation."""

    reviewer_id: str
    reviewer_name: str
    role: str
    organization: str
    reviewed_at: datetime
    decision: ReviewDecision
    authority_basis: str
    notes: str

    def __post_init__(self) -> None:
        if not self.reviewer_id.strip():
            raise ValueError("reviewer_id is required")
        if not self.reviewer_name.strip():
            raise ValueError("reviewer_name is required")
        if not self.role.strip():
            raise ValueError("reviewer role is required")
        if not self.organization.strip():
            raise ValueError("reviewer organization is required")
        if self.reviewed_at.tzinfo is None or self.reviewed_at.utcoffset() is None:
            raise ValueError("reviewed_at must be timezone-aware")
        if not self.authority_basis.strip():
            raise ValueError("authority_basis is required")
        if not self.notes.strip():
            raise ValueError("review notes are required")


@dataclass(frozen=True, slots=True)
class ReviewGateResult:
    """Result of checking whether an action has human-review support."""

    status: ReviewStatus
    decision_status: DecisionStatus
    risk_level: RiskLevel
    reviewer: ReviewerRecord | None
    reasons: tuple[str, ...]
    required_actions: tuple[str, ...]

    @property
    def is_approved(self) -> bool:
        """Return True only for explicit limited-use human approval."""

        return (
            self.status is ReviewStatus.APPROVED_FOR_LIMITED_USE
            and self.decision_status is DecisionStatus.ALLOW_REVIEW
            and self.reviewer is not None
        )


def require_human_review(
    *,
    upstream_status: DecisionStatus,
    upstream_risk: RiskLevel,
    action_label: str,
    reviewer: ReviewerRecord | None = None,
) -> ReviewGateResult:
    """Require a human reviewer before treating an output as actionable.

    Parameters:
        upstream_status: Status from an upstream evidence gate.
        upstream_risk: Risk from an upstream evidence gate.
        action_label: Plain-language description of the proposed action.
        reviewer: Optional explicit human-review record.

    Returns:
        A conservative ReviewGateResult. Approval is possible only when the
        upstream gate allowed review and a human explicitly approved limited
        use. Approval does not certify safety or regulatory compliance.
    """

    if not action_label.strip():
        raise ValueError("action_label is required")

    if upstream_status is DecisionStatus.BLOCK:
        return ReviewGateResult(
            status=ReviewStatus.REJECTED,
            decision_status=DecisionStatus.BLOCK,
            risk_level=RiskLevel.CRITICAL,
            reviewer=reviewer,
            reasons=(f"upstream gate blocked proposed action: {action_label}",),
            required_actions=(
                "do not perform field action",
                "resolve upstream blocking condition",
                "collect qualified review before reconsideration",
            ),
        )

    if upstream_status is DecisionStatus.HOLD_FOR_TESTING:
        return ReviewGateResult(
            status=ReviewStatus.NEEDS_MORE_EVIDENCE,
            decision_status=DecisionStatus.HOLD_FOR_TESTING,
            risk_level=max_risk(upstream_risk, RiskLevel.HIGH),
            reviewer=reviewer,
            reasons=(f"upstream gate requires more testing before action: {action_label}",),
            required_actions=(
                "hold proposed action",
                "collect required measurements or inspections",
                "repeat review after evidence is complete",
            ),
        )

    if reviewer is None:
        return ReviewGateResult(
            status=ReviewStatus.NOT_REVIEWED,
            decision_status=DecisionStatus.HOLD_FOR_TESTING,
            risk_level=max_risk(upstream_risk, RiskLevel.HIGH),
            reviewer=None,
            reasons=(f"no human reviewer has approved proposed action: {action_label}",),
            required_actions=(
                "assign qualified human reviewer",
                "document authority basis",
                "record reviewer decision before field action",
            ),
        )

    if reviewer.decision is ReviewDecision.REQUEST_MORE_EVIDENCE:
        return ReviewGateResult(
            status=ReviewStatus.NEEDS_MORE_EVIDENCE,
            decision_status=DecisionStatus.HOLD_FOR_TESTING,
            risk_level=max_risk(upstream_risk, RiskLevel.HIGH),
            reviewer=reviewer,
            reasons=(f"human reviewer requested more evidence for: {action_label}",),
            required_actions=(
                "hold proposed action",
                "collect reviewer-requested evidence",
                "repeat human review",
            ),
        )

    if reviewer.decision is ReviewDecision.REJECT:
        return ReviewGateResult(
            status=ReviewStatus.REJECTED,
            decision_status=DecisionStatus.BLOCK,
            risk_level=max_risk(upstream_risk, RiskLevel.HIGH),
            reviewer=reviewer,
            reasons=(f"human reviewer rejected proposed action: {action_label}",),
            required_actions=(
                "do not perform field action",
                "preserve rejection record",
                "create a revised proposal only if evidence changes",
            ),
        )

    return ReviewGateResult(
        status=ReviewStatus.APPROVED_FOR_LIMITED_USE,
        decision_status=DecisionStatus.ALLOW_REVIEW,
        risk_level=upstream_risk,
        reviewer=reviewer,
        reasons=(f"human reviewer approved limited use for: {action_label}",),
        required_actions=(
            "follow reviewer limits and local requirements",
            "preserve evidence bundle",
            "monitor for changed conditions",
        ),
    )


def max_risk(left: RiskLevel, right: RiskLevel) -> RiskLevel:
    """Return the more severe of two risk levels."""

    order = {
        RiskLevel.LOW: 0,
        RiskLevel.MODERATE: 1,
        RiskLevel.HIGH: 2,
        RiskLevel.CRITICAL: 3,
    }
    return left if order[left] >= order[right] else right
