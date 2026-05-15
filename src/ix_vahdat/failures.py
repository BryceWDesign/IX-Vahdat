"""Failure-mode registry for IX-Vahdat.

The registry provides a consistent fail-closed layer for known water-node
failure modes: stale sensors, contamination indicators, filter clogging,
storage faults, pump faults, low power, damaged atmospheric-water collection
surfaces, communications loss, and infrastructure-health warnings.

This module does not repair equipment, certify safety, or authorize field
action. It produces decision-support output for human review.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from ix_vahdat.domain import DecisionStatus, EvidenceQuality, RiskLevel, SensorStatus


class FailureCategory(str, Enum):
    """Category for a water-node failure mode."""

    WATER_QUALITY = "water_quality"
    TREATMENT = "treatment"
    STORAGE = "storage"
    ENERGY = "energy"
    POWER = "power"
    MAINTENANCE = "maintenance"
    INFRASTRUCTURE = "infrastructure"
    ATMOSPHERIC_COLLECTION = "atmospheric_collection"
    COMMUNICATIONS = "communications"
    GOVERNANCE = "governance"
    OTHER = "other"


class FailureSeverity(str, Enum):
    """Severity class for a failure mode."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"

    def to_risk_level(self) -> RiskLevel:
        """Convert failure severity to project risk level."""

        mapping = {
            FailureSeverity.LOW: RiskLevel.LOW,
            FailureSeverity.MODERATE: RiskLevel.MODERATE,
            FailureSeverity.HIGH: RiskLevel.HIGH,
            FailureSeverity.CRITICAL: RiskLevel.CRITICAL,
        }
        return mapping[self]


@dataclass(frozen=True, slots=True)
class FailureMode:
    """One known or observed water-node failure mode."""

    failure_id: str
    label: str
    category: FailureCategory
    severity: FailureSeverity
    active: bool
    evidence_quality: EvidenceQuality
    sensor_status: SensorStatus
    source_id: str
    required_actions: tuple[str, ...]
    detected_at: datetime | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        if not self.failure_id.strip():
            raise ValueError("failure_id is required")
        if not self.label.strip():
            raise ValueError("failure label is required")
        if not self.source_id.strip():
            raise ValueError("failure source_id is required")
        if not self.required_actions:
            raise ValueError("failure required_actions must contain at least one action")
        if any(not action.strip() for action in self.required_actions):
            raise ValueError("failure required_actions cannot contain blank values")
        if self.detected_at is not None:
            if self.detected_at.tzinfo is None or self.detected_at.utcoffset() is None:
                raise ValueError("detected_at must be timezone-aware when provided")
        if self.notes is not None and not self.notes.strip():
            raise ValueError("failure notes cannot be blank when provided")

    @property
    def evidence_is_reliable(self) -> bool:
        """Return whether this failure mode has usable evidence."""

        return (
            self.evidence_quality
            not in {
                EvidenceQuality.MISSING,
                EvidenceQuality.CONFLICTING,
            }
            and self.sensor_status
            not in {
                SensorStatus.STALE,
                SensorStatus.FAILED,
                SensorStatus.UNVERIFIED,
            }
        )

    @property
    def fail_closed_reason(self) -> str:
        """Return a plain-language reason for active failure handling."""

        return f"{self.label} is active with {self.severity.value} severity"


@dataclass(frozen=True, slots=True)
class FailureRegistry:
    """Collection of known or observed failure modes."""

    failures: tuple[FailureMode, ...]

    def __post_init__(self) -> None:
        if not self.failures:
            raise ValueError("at least one failure mode is required")

        failure_ids = [failure.failure_id for failure in self.failures]
        if len(failure_ids) != len(set(failure_ids)):
            raise ValueError("failure_id values must be unique")


@dataclass(frozen=True, slots=True)
class FailureEvaluationPolicy:
    """Fail-closed behavior for failure-mode evaluation."""

    block_active_critical_failures: bool = True
    hold_active_high_failures: bool = True
    require_reliable_evidence: bool = True
    hold_on_unverified_governance: bool = True


@dataclass(frozen=True, slots=True)
class FailureEvaluationResult:
    """Decision-support output for failure-mode evaluation."""

    decision_status: DecisionStatus
    risk_level: RiskLevel
    active_failures: tuple[str, ...]
    blocked_failures: tuple[str, ...]
    warning_failures: tuple[str, ...]
    reasons: tuple[str, ...]
    required_actions: tuple[str, ...]

    @property
    def has_active_failure(self) -> bool:
        """Return True when at least one failure mode is active."""

        return bool(self.active_failures)

    @property
    def fail_closed(self) -> bool:
        """Return True when the result blocks or holds due to failures."""

        return self.decision_status in {DecisionStatus.BLOCK, DecisionStatus.HOLD_FOR_TESTING}


def evaluate_failure_modes(
    registry: FailureRegistry,
    *,
    policy: FailureEvaluationPolicy | None = None,
) -> FailureEvaluationResult:
    """Evaluate a failure registry with conservative fail-closed behavior."""

    active_policy = policy or FailureEvaluationPolicy()

    active_failures: list[str] = []
    blocked_failures: list[str] = []
    warning_failures: list[str] = []
    reasons: list[str] = []
    required_actions: list[str] = []

    for failure in registry.failures:
        unreliable_reasons = _unreliable_evidence_reasons(failure, active_policy)
        if unreliable_reasons:
            blocked_failures.append(failure.failure_id)
            reasons.extend(unreliable_reasons)
            required_actions.extend(
                (
                    f"verify evidence source for {failure.label}",
                    "repeat failure evaluation with reliable evidence",
                )
            )
            continue

        if not failure.active:
            continue

        active_failures.append(failure.failure_id)
        reasons.append(failure.fail_closed_reason)
        required_actions.extend(failure.required_actions)

        if _blocks(failure, active_policy):
            blocked_failures.append(failure.failure_id)
        elif _holds(failure, active_policy):
            blocked_failures.append(failure.failure_id)
        else:
            warning_failures.append(failure.failure_id)

    if blocked_failures:
        risk = _max_risk_for_failures(registry, tuple(blocked_failures))
        decision_status = DecisionStatus.BLOCK if risk is RiskLevel.CRITICAL else DecisionStatus.HOLD_FOR_TESTING
        return FailureEvaluationResult(
            decision_status=decision_status,
            risk_level=risk,
            active_failures=tuple(active_failures),
            blocked_failures=tuple(_dedupe(blocked_failures)),
            warning_failures=tuple(_dedupe(warning_failures)),
            reasons=tuple(_dedupe(reasons)),
            required_actions=tuple(
                _dedupe(
                    required_actions
                    + [
                        "hold affected water-support decisions until failure modes are resolved",
                        "preserve failure-mode evidence for human review",
                    ]
                )
            ),
        )

    if warning_failures:
        return FailureEvaluationResult(
            decision_status=DecisionStatus.ALLOW_REVIEW,
            risk_level=_max_risk_for_failures(registry, tuple(warning_failures)),
            active_failures=tuple(active_failures),
            blocked_failures=(),
            warning_failures=tuple(_dedupe(warning_failures)),
            reasons=tuple(_dedupe(reasons)),
            required_actions=tuple(
                _dedupe(
                    required_actions
                    + [
                        "continue only with human review",
                        "monitor warning failure modes for escalation",
                    ]
                )
            ),
        )

    return FailureEvaluationResult(
        decision_status=DecisionStatus.ALLOW_REVIEW,
        risk_level=RiskLevel.LOW,
        active_failures=(),
        blocked_failures=(),
        warning_failures=(),
        reasons=("no active blocking failure modes were found",),
        required_actions=(
            "continue monitoring failure registry",
            "preserve failure-mode evidence for review",
            "repeat evaluation when sensor, maintenance, or site conditions change",
        ),
    )


def _unreliable_evidence_reasons(
    failure: FailureMode,
    policy: FailureEvaluationPolicy,
) -> tuple[str, ...]:
    if not policy.require_reliable_evidence:
        return ()

    reasons: list[str] = []
    if failure.evidence_quality in {
        EvidenceQuality.MISSING,
        EvidenceQuality.CONFLICTING,
    }:
        reasons.append(f"{failure.label} evidence quality is {failure.evidence_quality.value}")
    if failure.sensor_status in {
        SensorStatus.STALE,
        SensorStatus.FAILED,
        SensorStatus.UNVERIFIED,
    }:
        reasons.append(f"{failure.label} sensor status is {failure.sensor_status.value}")

    if (
        policy.hold_on_unverified_governance
        and failure.category is FailureCategory.GOVERNANCE
        and failure.sensor_status is SensorStatus.UNVERIFIED
    ):
        reasons.append(f"{failure.label} governance evidence is unverified")

    return tuple(reasons)


def _blocks(failure: FailureMode, policy: FailureEvaluationPolicy) -> bool:
    return failure.severity is FailureSeverity.CRITICAL and policy.block_active_critical_failures


def _holds(failure: FailureMode, policy: FailureEvaluationPolicy) -> bool:
    return failure.severity is FailureSeverity.HIGH and policy.hold_active_high_failures


def _max_risk_for_failures(
    registry: FailureRegistry,
    failure_ids: tuple[str, ...],
) -> RiskLevel:
    by_id = {failure.failure_id: failure for failure in registry.failures}
    risks = [by_id[failure_id].severity.to_risk_level() for failure_id in failure_ids]
    order = {
        RiskLevel.LOW: 0,
        RiskLevel.MODERATE: 1,
        RiskLevel.HIGH: 2,
        RiskLevel.CRITICAL: 3,
    }
    return max(risks, key=lambda risk: order[risk])


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        cleaned.append(value)
    return cleaned
