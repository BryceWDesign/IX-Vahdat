from datetime import UTC, datetime

import pytest

from ix_vahdat.domain import DecisionStatus, EvidenceQuality, RiskLevel, SensorStatus
from ix_vahdat.failures import (
    FailureCategory,
    FailureEvaluationPolicy,
    FailureMode,
    FailureRegistry,
    FailureSeverity,
    evaluate_failure_modes,
)


def _failure(**overrides: object) -> FailureMode:
    values = {
        "failure_id": "filter-clog",
        "label": "filter clog warning",
        "category": FailureCategory.TREATMENT,
        "severity": FailureSeverity.HIGH,
        "active": True,
        "evidence_quality": EvidenceQuality.MEASURED,
        "sensor_status": SensorStatus.OK,
        "source_id": "pressure-delta-sensor-1",
        "required_actions": (
            "hold treatment-routing decision",
            "inspect or replace filter before continued treatment review",
        ),
        "detected_at": datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC),
        "notes": "pressure differential exceeded review threshold",
    }
    values.update(overrides)
    return FailureMode(**values)  # type: ignore[arg-type]


def _registry(*failures: FailureMode) -> FailureRegistry:
    return FailureRegistry(failures=failures or (_failure(),))


def test_failure_mode_requires_timezone_aware_detected_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _failure(detected_at=datetime(2026, 5, 14, 12, 0, 0))


@pytest.mark.parametrize(
    ("field", "value", "expected_message"),
    [
        ("failure_id", " ", "failure_id"),
        ("label", " ", "label"),
        ("source_id", " ", "source_id"),
        ("required_actions", (), "required_actions"),
        ("required_actions", (" ",), "required_actions"),
        ("notes", " ", "notes"),
    ],
)
def test_failure_mode_rejects_invalid_values(
    field: str,
    value: object,
    expected_message: str,
) -> None:
    with pytest.raises(ValueError, match=expected_message):
        _failure(**{field: value})


def test_failure_evidence_reliability_property() -> None:
    reliable = _failure()
    unreliable = _failure(evidence_quality=EvidenceQuality.CONFLICTING)

    assert reliable.evidence_is_reliable is True
    assert unreliable.evidence_is_reliable is False


def test_registry_requires_unique_failure_ids() -> None:
    with pytest.raises(ValueError, match="unique"):
        FailureRegistry(failures=(_failure(failure_id="same"), _failure(failure_id="same")))


def test_registry_requires_at_least_one_failure() -> None:
    with pytest.raises(ValueError, match="at least one failure"):
        FailureRegistry(failures=())


def test_no_active_failures_allow_review() -> None:
    result = evaluate_failure_modes(
        _registry(
            _failure(
                failure_id="filter-clog",
                active=False,
            ),
            _failure(
                failure_id="battery-low",
                label="battery low warning",
                category=FailureCategory.POWER,
                severity=FailureSeverity.MODERATE,
                active=False,
                source_id="battery-monitor",
            ),
        )
    )

    assert result.decision_status is DecisionStatus.ALLOW_REVIEW
    assert result.risk_level is RiskLevel.LOW
    assert result.has_active_failure is False
    assert result.fail_closed is False
    assert "no active blocking failure modes were found" in result.reasons


def test_active_critical_failure_blocks() -> None:
    result = evaluate_failure_modes(
        _registry(
            _failure(
                failure_id="pathogen-indicator",
                label="pathogen indicator present",
                category=FailureCategory.WATER_QUALITY,
                severity=FailureSeverity.CRITICAL,
                active=True,
                required_actions=(
                    "block release",
                    "route to treatment or disposal review",
                ),
            )
        )
    )

    assert result.decision_status is DecisionStatus.BLOCK
    assert result.risk_level is RiskLevel.CRITICAL
    assert result.has_active_failure is True
    assert result.fail_closed is True
    assert result.active_failures == ("pathogen-indicator",)
    assert result.blocked_failures == ("pathogen-indicator",)
    assert "pathogen indicator present is active with critical severity" in result.reasons
    assert "block release" in result.required_actions


def test_active_high_failure_holds_for_testing() -> None:
    result = evaluate_failure_modes(_registry())

    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.risk_level is RiskLevel.HIGH
    assert result.active_failures == ("filter-clog",)
    assert result.blocked_failures == ("filter-clog",)
    assert "filter clog warning is active with high severity" in result.reasons
    assert "hold affected water-support decisions until failure modes are resolved" in (
        result.required_actions
    )


def test_active_moderate_failure_allows_review_with_warning() -> None:
    result = evaluate_failure_modes(
        _registry(
            _failure(
                failure_id="dust-elevated",
                label="dust risk elevated",
                category=FailureCategory.ATMOSPHERIC_COLLECTION,
                severity=FailureSeverity.MODERATE,
                active=True,
                source_id="air-quality-station",
                required_actions=(
                    "inspect collection surfaces before atmospheric-water review",
                ),
            )
        )
    )

    assert result.decision_status is DecisionStatus.ALLOW_REVIEW
    assert result.risk_level is RiskLevel.MODERATE
    assert result.warning_failures == ("dust-elevated",)
    assert result.fail_closed is False
    assert "continue only with human review" in result.required_actions


def test_missing_failure_evidence_holds_for_testing() -> None:
    result = evaluate_failure_modes(
        _registry(
            _failure(
                failure_id="sensor-unknown",
                label="sensor status unknown",
                active=False,
                evidence_quality=EvidenceQuality.MISSING,
            )
        )
    )

    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.risk_level is RiskLevel.HIGH
    assert result.blocked_failures == ("sensor-unknown",)
    assert "sensor status unknown evidence quality is missing" in result.reasons
    assert "verify evidence source for sensor status unknown" in result.required_actions


def test_stale_failure_sensor_holds_for_testing() -> None:
    result = evaluate_failure_modes(
        _registry(
            _failure(
                failure_id="stale-pump-fault",
                label="pump fault evidence",
                category=FailureCategory.INFRASTRUCTURE,
                active=False,
                sensor_status=SensorStatus.STALE,
            )
        )
    )

    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.risk_level is RiskLevel.HIGH
    assert "pump fault evidence sensor status is stale" in result.reasons


def test_policy_can_allow_unreliable_evidence_to_be_ignored() -> None:
    policy = FailureEvaluationPolicy(require_reliable_evidence=False)

    result = evaluate_failure_modes(
        _registry(
            _failure(
                failure_id="missing-inactive",
                active=False,
                evidence_quality=EvidenceQuality.MISSING,
            )
        ),
        policy=policy,
    )

    assert result.decision_status is DecisionStatus.ALLOW_REVIEW
    assert result.risk_level is RiskLevel.LOW
    assert result.blocked_failures == ()


def test_policy_can_allow_active_critical_failure_to_degrade_to_warning() -> None:
    policy = FailureEvaluationPolicy(block_active_critical_failures=False)

    result = evaluate_failure_modes(
        _registry(
            _failure(
                failure_id="critical-test",
                label="critical test failure",
                severity=FailureSeverity.CRITICAL,
                active=True,
            )
        ),
        policy=policy,
    )

    assert result.decision_status is DecisionStatus.ALLOW_REVIEW
    assert result.risk_level is RiskLevel.CRITICAL
    assert result.warning_failures == ("critical-test",)


def test_mixed_failures_return_highest_blocking_risk() -> None:
    result = evaluate_failure_modes(
        _registry(
            _failure(
                failure_id="moderate-dust",
                label="moderate dust warning",
                severity=FailureSeverity.MODERATE,
                category=FailureCategory.ATMOSPHERIC_COLLECTION,
                active=True,
            ),
            _failure(
                failure_id="critical-storage",
                label="storage tank contamination",
                severity=FailureSeverity.CRITICAL,
                category=FailureCategory.STORAGE,
                active=True,
            ),
        )
    )

    assert result.decision_status is DecisionStatus.BLOCK
    assert result.risk_level is RiskLevel.CRITICAL
    assert result.active_failures == ("moderate-dust", "critical-storage")
    assert result.blocked_failures == ("critical-storage",)
    assert result.warning_failures == ("moderate-dust",)


def test_failure_severity_converts_to_risk_level() -> None:
    assert FailureSeverity.LOW.to_risk_level() is RiskLevel.LOW
    assert FailureSeverity.MODERATE.to_risk_level() is RiskLevel.MODERATE
    assert FailureSeverity.HIGH.to_risk_level() is RiskLevel.HIGH
    assert FailureSeverity.CRITICAL.to_risk_level() is RiskLevel.CRITICAL
