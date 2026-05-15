import pytest

from ix_vahdat.domain import DecisionStatus, RiskLevel
from ix_vahdat.reserve import (
    EmergencyReservePolicy,
    EmergencyReserveSnapshot,
    ReserveStatus,
    evaluate_emergency_reserve,
)
from ix_vahdat.water_use import WaterUseClass


def _snapshot(**overrides: object) -> EmergencyReserveSnapshot:
    values = {
        "stored_water_l": 500.0,
        "protected_reserve_l": 150.0,
        "daily_priority_demand_l": 100.0,
        "requested_release_l": 50.0,
        "requested_use_label": "clinic hygiene reserve",
        "water_use_class": WaterUseClass.HYGIENE_CANDIDATE,
        "quality_gate_passed": True,
        "treatment_route_reviewed": True,
        "storage_clean": True,
        "tank_integrity_verified": True,
        "storage_age_hours": 12.0,
        "emergency_request_declared": False,
        "notes": "reviewable reserve inventory snapshot",
    }
    values.update(overrides)
    return EmergencyReserveSnapshot(**values)  # type: ignore[arg-type]


def test_snapshot_computes_post_release_and_coverage() -> None:
    snapshot = _snapshot(
        stored_water_l=500.0,
        protected_reserve_l=150.0,
        daily_priority_demand_l=100.0,
        requested_release_l=50.0,
    )

    assert snapshot.post_release_storage_l == 450.0
    assert snapshot.would_breach_protected_reserve is False
    assert snapshot.current_demand_coverage_days == 5.0
    assert snapshot.post_release_demand_coverage_days == 4.5


def test_snapshot_accepts_unknown_daily_demand_without_coverage_value() -> None:
    snapshot = _snapshot(daily_priority_demand_l=0.0)

    assert snapshot.current_demand_coverage_days is None
    assert snapshot.post_release_demand_coverage_days is None


@pytest.mark.parametrize(
    ("field", "value", "expected_message"),
    [
        ("stored_water_l", -1.0, "stored_water_l"),
        ("protected_reserve_l", -1.0, "protected_reserve_l"),
        ("daily_priority_demand_l", -1.0, "daily_priority_demand_l"),
        ("requested_release_l", -1.0, "requested_release_l"),
        ("storage_age_hours", -1.0, "storage_age_hours"),
        ("requested_use_label", " ", "requested_use_label"),
        ("notes", " ", "notes"),
    ],
)
def test_snapshot_rejects_invalid_values(
    field: str,
    value: object,
    expected_message: str,
) -> None:
    with pytest.raises(ValueError, match=expected_message):
        _snapshot(**{field: value})


def test_snapshot_rejects_protected_reserve_above_stored_water() -> None:
    with pytest.raises(ValueError, match="protected_reserve_l"):
        _snapshot(stored_water_l=100.0, protected_reserve_l=150.0)


def test_policy_rejects_invalid_values() -> None:
    with pytest.raises(ValueError, match="max_storage_age_hours_for_review"):
        EmergencyReservePolicy(max_storage_age_hours_for_review=0.0)

    with pytest.raises(ValueError, match="min_post_release_coverage_days"):
        EmergencyReservePolicy(min_post_release_coverage_days=-1.0)


def test_reviewable_release_preserves_reserve() -> None:
    result = evaluate_emergency_reserve(_snapshot())

    assert result.status is ReserveStatus.NORMAL
    assert result.decision_status is DecisionStatus.ALLOW_REVIEW
    assert result.risk_level is RiskLevel.LOW
    assert result.allowed_release_l == 50.0
    assert result.post_release_storage_l == 450.0
    assert "human review required before release" in result.required_actions


@pytest.mark.parametrize(
    ("field", "expected_reason"),
    [
        ("storage_clean", "storage cleanliness is not verified"),
        ("tank_integrity_verified", "tank integrity is not verified"),
        ("quality_gate_passed", "water-quality gate has not passed"),
        ("treatment_route_reviewed", "treatment route has not been reviewed"),
    ],
)
def test_service_blockers_hold_reserve(
    field: str,
    expected_reason: str,
) -> None:
    result = evaluate_emergency_reserve(_snapshot(**{field: False}))

    assert result.status is ReserveStatus.SERVICE_REQUIRED
    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.risk_level is RiskLevel.HIGH
    assert result.allowed_release_l == 0.0
    assert expected_reason in result.reasons


def test_old_storage_age_holds_reserve_for_review() -> None:
    result = evaluate_emergency_reserve(_snapshot(storage_age_hours=100.0))

    assert result.status is ReserveStatus.SERVICE_REQUIRED
    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert "storage age exceeds configured review threshold" in result.reasons


def test_empty_reserve_blocks_availability_claim() -> None:
    result = evaluate_emergency_reserve(
        _snapshot(stored_water_l=0.0, protected_reserve_l=0.0, requested_release_l=0.0)
    )

    assert result.status is ReserveStatus.SAFE_HOLD
    assert result.decision_status is DecisionStatus.BLOCK
    assert result.risk_level is RiskLevel.CRITICAL
    assert "no stored water is available" in result.reasons
    assert "do not report reserve availability" in result.required_actions


def test_release_above_stored_water_blocks() -> None:
    result = evaluate_emergency_reserve(_snapshot(requested_release_l=600.0))

    assert result.status is ReserveStatus.SAFE_HOLD
    assert result.decision_status is DecisionStatus.BLOCK
    assert result.allowed_release_l == 0.0
    assert "requested release exceeds stored water volume" in result.reasons


def test_unsafe_hold_water_class_blocks_release() -> None:
    result = evaluate_emergency_reserve(
        _snapshot(water_use_class=WaterUseClass.UNSAFE_HOLD)
    )

    assert result.status is ReserveStatus.SAFE_HOLD
    assert result.decision_status is DecisionStatus.BLOCK
    assert result.risk_level is RiskLevel.CRITICAL
    assert "reserve water is classified as unsafe hold" in result.reasons


def test_routine_release_that_breaches_reserve_is_blocked() -> None:
    result = evaluate_emergency_reserve(
        _snapshot(requested_release_l=400.0, emergency_request_declared=False)
    )

    assert result.status is ReserveStatus.SAFE_HOLD
    assert result.decision_status is DecisionStatus.BLOCK
    assert result.allowed_release_l == 0.0
    assert "requested release would breach protected emergency reserve" in result.reasons


def test_declared_emergency_release_below_reserve_can_continue_to_high_risk_review() -> None:
    result = evaluate_emergency_reserve(
        _snapshot(requested_release_l=400.0, emergency_request_declared=True)
    )

    assert result.status is ReserveStatus.EMERGENCY_REVIEW
    assert result.decision_status is DecisionStatus.ALLOW_REVIEW
    assert result.risk_level is RiskLevel.HIGH
    assert result.allowed_release_l == 400.0
    assert "require explicit emergency human authorization" in result.required_actions


def test_declared_emergency_release_below_reserve_can_be_disabled_by_policy() -> None:
    policy = EmergencyReservePolicy(allow_emergency_review_below_reserve=False)

    result = evaluate_emergency_reserve(
        _snapshot(requested_release_l=400.0, emergency_request_declared=True),
        policy=policy,
    )

    assert result.status is ReserveStatus.SAFE_HOLD
    assert result.decision_status is DecisionStatus.BLOCK
    assert result.allowed_release_l == 0.0


def test_low_post_release_coverage_enters_conserve_review() -> None:
    result = evaluate_emergency_reserve(
        _snapshot(
            stored_water_l=220.0,
            protected_reserve_l=100.0,
            daily_priority_demand_l=200.0,
            requested_release_l=20.0,
        )
    )

    assert result.status is ReserveStatus.CONSERVE
    assert result.decision_status is DecisionStatus.ALLOW_REVIEW
    assert result.risk_level is RiskLevel.MODERATE
    assert "post-release demand coverage is below configured minimum" in result.reasons


def test_low_routine_margin_enters_conserve_review() -> None:
    result = evaluate_emergency_reserve(
        _snapshot(
            stored_water_l=200.0,
            protected_reserve_l=150.0,
            daily_priority_demand_l=50.0,
            requested_release_l=48.0,
        )
    )

    assert result.status is ReserveStatus.CONSERVE
    assert result.decision_status is DecisionStatus.ALLOW_REVIEW
    assert "post-release reserve margin is below configured routine-use margin" in result.reasons


def test_no_release_requested_preserves_reserve_state() -> None:
    result = evaluate_emergency_reserve(_snapshot(requested_release_l=0.0))

    assert result.status is ReserveStatus.NORMAL
    assert result.decision_status is DecisionStatus.ALLOW_REVIEW
    assert result.allowed_release_l == 0.0
    assert "no release requested and reserve evidence is reviewable" in result.reasons


def test_no_release_requested_with_low_coverage_enters_conserve_state() -> None:
    result = evaluate_emergency_reserve(
        _snapshot(
            stored_water_l=50.0,
            protected_reserve_l=25.0,
            daily_priority_demand_l=100.0,
            requested_release_l=0.0,
        )
    )

    assert result.status is ReserveStatus.CONSERVE
    assert result.decision_status is DecisionStatus.ALLOW_REVIEW
    assert result.risk_level is RiskLevel.MODERATE
    assert "current reserve coverage is below configured minimum" in result.reasons
