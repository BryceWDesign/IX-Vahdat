from datetime import UTC, datetime, timedelta

import pytest

from ix_vahdat.domain import DecisionStatus, EvidenceQuality, RiskLevel, SensorStatus
from ix_vahdat.infrastructure import (
    AssetHealthState,
    InfrastructureAssetType,
    InfrastructureHealthPolicy,
    InfrastructureObservation,
    InfrastructureSnapshot,
    evaluate_infrastructure_health,
)


EVALUATED_AT = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)


def _observation(**overrides: object) -> InfrastructureObservation:
    values = {
        "asset_id": "tank-1",
        "label": "emergency storage tank",
        "asset_type": InfrastructureAssetType.STORAGE_TANK,
        "health_state": AssetHealthState.NORMAL,
        "observed_at": EVALUATED_AT,
        "evidence_quality": EvidenceQuality.MEASURED,
        "sensor_status": SensorStatus.OK,
        "leak_detected": False,
        "deformation_fraction": 0.1,
        "vibration_fraction": 0.1,
        "corrosion_fraction": 0.1,
        "pressure_anomaly_fraction": 0.1,
        "contamination_pathway_risk_fraction": 0.1,
        "critical_to_water_safety": True,
        "notes": "field inspection recorded",
    }
    values.update(overrides)
    return InfrastructureObservation(**values)  # type: ignore[arg-type]


def _snapshot(*observations: InfrastructureObservation) -> InfrastructureSnapshot:
    return InfrastructureSnapshot(observations=observations or (_observation(),))


def test_observation_computes_max_condition_fraction() -> None:
    observation = _observation(
        deformation_fraction=0.2,
        vibration_fraction=0.7,
        corrosion_fraction=0.4,
    )

    assert observation.max_condition_fraction == 0.7
    assert observation.evidence_is_reliable is True


def test_observation_requires_timezone_aware_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _observation(observed_at=datetime(2026, 5, 14, 12, 0, 0))


@pytest.mark.parametrize(
    ("field", "value", "expected_message"),
    [
        ("asset_id", " ", "asset_id"),
        ("label", " ", "label"),
        ("deformation_fraction", -0.1, "deformation_fraction"),
        ("vibration_fraction", 1.1, "vibration_fraction"),
        ("corrosion_fraction", -0.1, "corrosion_fraction"),
        ("pressure_anomaly_fraction", 1.1, "pressure_anomaly_fraction"),
        ("contamination_pathway_risk_fraction", -0.1, "contamination_pathway"),
        ("notes", " ", "notes"),
    ],
)
def test_observation_rejects_invalid_values(
    field: str,
    value: object,
    expected_message: str,
) -> None:
    with pytest.raises(ValueError, match=expected_message):
        _observation(**{field: value})


def test_snapshot_rejects_empty_observations() -> None:
    with pytest.raises(ValueError, match="at least one infrastructure observation"):
        InfrastructureSnapshot(observations=())


def test_snapshot_rejects_duplicate_asset_ids() -> None:
    with pytest.raises(ValueError, match="unique"):
        InfrastructureSnapshot(
            observations=(
                _observation(asset_id="same"),
                _observation(asset_id="same"),
            )
        )


def test_policy_rejects_invalid_threshold_ordering() -> None:
    with pytest.raises(ValueError, match="watch_fraction"):
        InfrastructureHealthPolicy(
            watch_fraction=0.8,
            degraded_fraction=0.7,
            critical_fraction=0.9,
        )


def test_all_normal_assets_allow_review() -> None:
    result = evaluate_infrastructure_health(
        _snapshot(
            _observation(asset_id="tank-1"),
            _observation(
                asset_id="pipe-1",
                label="feed pipe",
                asset_type=InfrastructureAssetType.PIPE,
            ),
        ),
        evaluated_at=EVALUATED_AT,
    )

    assert result.decision_status is DecisionStatus.ALLOW_REVIEW
    assert result.risk_level is RiskLevel.LOW
    assert result.infrastructure_ready is True
    assert result.normal_assets == ("tank-1", "pipe-1")
    assert result.blocked_assets == ()
    assert "infrastructure-health evidence is reviewable and no blockers were found" in (
        result.reasons
    )


def test_watch_state_allows_review_with_moderate_risk() -> None:
    result = evaluate_infrastructure_health(
        _snapshot(
            _observation(
                asset_id="pump-1",
                label="transfer pump",
                asset_type=InfrastructureAssetType.PUMP,
                health_state=AssetHealthState.WATCH,
            )
        ),
        evaluated_at=EVALUATED_AT,
    )

    assert result.decision_status is DecisionStatus.ALLOW_REVIEW
    assert result.risk_level is RiskLevel.MODERATE
    assert result.infrastructure_ready is True
    assert result.watch_assets == ("pump-1",)
    assert "transfer pump health state is watch" in result.reasons


def test_degraded_condition_allows_review_with_watch_actions() -> None:
    result = evaluate_infrastructure_health(
        _snapshot(
            _observation(
                asset_id="mount-1",
                label="collector mount",
                asset_type=InfrastructureAssetType.STRUCTURAL_MOUNT,
                deformation_fraction=0.75,
                critical_to_water_safety=False,
            )
        ),
        evaluated_at=EVALUATED_AT,
    )

    assert result.decision_status is DecisionStatus.ALLOW_REVIEW
    assert result.risk_level is RiskLevel.MODERATE
    assert result.watch_assets == ("mount-1",)
    assert "collector mount condition indicator exceeds degraded threshold" in result.reasons
    assert "schedule qualified inspection for collector mount" in result.required_actions


def test_stale_observation_holds_for_testing() -> None:
    result = evaluate_infrastructure_health(
        _snapshot(
            _observation(
                asset_id="tank-1",
                observed_at=EVALUATED_AT - timedelta(hours=30),
            )
        ),
        evaluated_at=EVALUATED_AT,
    )

    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.risk_level is RiskLevel.HIGH
    assert result.infrastructure_ready is False
    assert "emergency storage tank observation is older than maximum allowed age" in (
        result.reasons
    )


def test_future_observation_holds_for_testing() -> None:
    result = evaluate_infrastructure_health(
        _snapshot(
            _observation(
                asset_id="tank-1",
                observed_at=EVALUATED_AT + timedelta(minutes=5),
            )
        ),
        evaluated_at=EVALUATED_AT,
    )

    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert "emergency storage tank observation timestamp is later than evaluation time" in (
        result.reasons
    )


def test_missing_evidence_holds_for_testing() -> None:
    result = evaluate_infrastructure_health(
        _snapshot(
            _observation(
                asset_id="sensor-mast-1",
                label="sensor mast",
                asset_type=InfrastructureAssetType.SENSOR_MAST,
                evidence_quality=EvidenceQuality.MISSING,
                critical_to_water_safety=False,
            )
        ),
        evaluated_at=EVALUATED_AT,
    )

    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.risk_level is RiskLevel.MODERATE
    assert "sensor mast evidence quality is missing" in result.reasons
    assert "inspect sensor mast alignment, mounting, and communications path" in (
        result.required_actions
    )


def test_unverified_sensor_holds_for_testing() -> None:
    result = evaluate_infrastructure_health(
        _snapshot(
            _observation(
                asset_id="pipe-1",
                label="feed pipe",
                asset_type=InfrastructureAssetType.PIPE,
                sensor_status=SensorStatus.UNVERIFIED,
            )
        ),
        evaluated_at=EVALUATED_AT,
    )

    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.risk_level is RiskLevel.HIGH
    assert "feed pipe sensor status is unverified" in result.reasons


def test_leak_on_safety_critical_asset_blocks() -> None:
    result = evaluate_infrastructure_health(
        _snapshot(
            _observation(
                asset_id="tank-1",
                label="emergency storage tank",
                asset_type=InfrastructureAssetType.STORAGE_TANK,
                leak_detected=True,
                critical_to_water_safety=True,
            )
        ),
        evaluated_at=EVALUATED_AT,
    )

    assert result.decision_status is DecisionStatus.BLOCK
    assert result.risk_level is RiskLevel.CRITICAL
    assert result.blocked_assets == ("tank-1",)
    assert "emergency storage tank leak detected on safety-critical asset" in result.reasons
    assert "safety-critical asset blocks dependent water-support decisions" in (
        result.required_actions
    )


def test_leak_on_noncritical_asset_is_watch_only() -> None:
    result = evaluate_infrastructure_health(
        _snapshot(
            _observation(
                asset_id="fog-frame-1",
                label="fog mesh frame",
                asset_type=InfrastructureAssetType.FOG_MESH_FRAME,
                leak_detected=True,
                critical_to_water_safety=False,
            )
        ),
        evaluated_at=EVALUATED_AT,
    )

    assert result.decision_status is DecisionStatus.ALLOW_REVIEW
    assert result.risk_level is RiskLevel.MODERATE
    assert result.watch_assets == ("fog-frame-1",)
    assert "fog mesh frame leak detected" in result.reasons


def test_critical_health_state_blocks() -> None:
    result = evaluate_infrastructure_health(
        _snapshot(
            _observation(
                asset_id="pipe-1",
                label="feed pipe",
                asset_type=InfrastructureAssetType.PIPE,
                health_state=AssetHealthState.CRITICAL,
                critical_to_water_safety=True,
            )
        ),
        evaluated_at=EVALUATED_AT,
    )

    assert result.decision_status is DecisionStatus.BLOCK
    assert result.risk_level is RiskLevel.CRITICAL
    assert "feed pipe health state is critical" in result.reasons


def test_critical_condition_indicator_blocks() -> None:
    result = evaluate_infrastructure_health(
        _snapshot(
            _observation(
                asset_id="pipe-1",
                label="feed pipe",
                asset_type=InfrastructureAssetType.PIPE,
                pressure_anomaly_fraction=0.95,
                critical_to_water_safety=True,
            )
        ),
        evaluated_at=EVALUATED_AT,
    )

    assert result.decision_status is DecisionStatus.BLOCK
    assert result.risk_level is RiskLevel.CRITICAL
    assert "feed pipe condition indicator exceeds critical threshold" in result.reasons


def test_naive_evaluation_time_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        evaluate_infrastructure_health(
            _snapshot(),
            evaluated_at=datetime(2026, 5, 14, 12, 0, 0),
        )
