import pytest

from ix_vahdat.domain import DecisionStatus, EvidenceQuality, RiskLevel, SensorStatus
from ix_vahdat.recharge import (
    MARReadinessClass,
    MARReadinessPolicy,
    MARSiteObservation,
    MARWaterSource,
    RechargeMethod,
    evaluate_mar_readiness,
)
from ix_vahdat.water_use import WaterUseClass


def _source(**overrides: object) -> MARWaterSource:
    values = {
        "source_id": "treated-source-1",
        "label": "treated reclaimed water batch",
        "water_use_class": WaterUseClass.UTILITY_WATER,
        "available_volume_l": 5_000.0,
        "quality_gate_passed": True,
        "treatment_route_reviewed": True,
        "evidence_quality": EvidenceQuality.MEASURED,
        "sensor_status": SensorStatus.OK,
        "salinity_risk_fraction": 0.2,
        "contamination_risk_fraction": 0.1,
        "notes": "review-only recharge source screen",
    }
    values.update(overrides)
    return MARWaterSource(**values)  # type: ignore[arg-type]


def _site(**overrides: object) -> MARSiteObservation:
    values = {
        "site_id": "mar-site-1",
        "label": "pilot infiltration basin candidate",
        "method": RechargeMethod.SPREADING_BASIN,
        "evidence_quality": EvidenceQuality.MEASURED,
        "sensor_status": SensorStatus.OK,
        "infiltration_capacity_fraction": 0.75,
        "groundwater_vulnerability_fraction": 0.2,
        "geotechnical_stability_fraction": 0.8,
        "subsidence_risk_fraction": 0.3,
        "contamination_source_distance_m": 500.0,
        "monitoring_well_available": True,
        "local_authority_review_available": True,
        "environmental_review_available": True,
        "community_review_available": True,
        "notes": "screening only; no authorization",
    }
    values.update(overrides)
    return MARSiteObservation(**values)  # type: ignore[arg-type]


def test_reviewable_pilot_when_source_and_site_evidence_pass() -> None:
    result = evaluate_mar_readiness(source=_source(), site=_site())

    assert result.readiness_class is MARReadinessClass.REVIEWABLE_PILOT
    assert result.decision_status is DecisionStatus.ALLOW_REVIEW
    assert result.risk_level is RiskLevel.LOW
    assert result.may_continue_to_human_review is True
    assert "do not treat this result as recharge authorization" in result.required_actions


@pytest.mark.parametrize(
    ("field", "value", "expected_message"),
    [
        ("source_id", " ", "source_id"),
        ("label", " ", "label"),
        ("available_volume_l", -1.0, "available_volume_l"),
        ("salinity_risk_fraction", 1.1, "salinity_risk_fraction"),
        ("contamination_risk_fraction", -0.1, "contamination_risk_fraction"),
        ("notes", " ", "notes"),
    ],
)
def test_source_rejects_invalid_values(
    field: str,
    value: object,
    expected_message: str,
) -> None:
    with pytest.raises(ValueError, match=expected_message):
        _source(**{field: value})


@pytest.mark.parametrize(
    ("field", "value", "expected_message"),
    [
        ("site_id", " ", "site_id"),
        ("label", " ", "label"),
        ("infiltration_capacity_fraction", -0.1, "infiltration_capacity_fraction"),
        ("groundwater_vulnerability_fraction", 1.1, "groundwater_vulnerability"),
        ("geotechnical_stability_fraction", -0.1, "geotechnical_stability"),
        ("subsidence_risk_fraction", 1.1, "subsidence_risk_fraction"),
        ("contamination_source_distance_m", -1.0, "contamination_source_distance_m"),
        ("notes", " ", "notes"),
    ],
)
def test_site_rejects_invalid_values(
    field: str,
    value: object,
    expected_message: str,
) -> None:
    with pytest.raises(ValueError, match=expected_message):
        _site(**{field: value})


def test_policy_rejects_invalid_values() -> None:
    with pytest.raises(ValueError, match="min_source_volume_l"):
        MARReadinessPolicy(min_source_volume_l=0.0)

    with pytest.raises(ValueError, match="max_salinity_risk_fraction"):
        MARReadinessPolicy(max_salinity_risk_fraction=1.1)


def test_unsafe_hold_source_blocks_recharge() -> None:
    result = evaluate_mar_readiness(
        source=_source(water_use_class=WaterUseClass.UNSAFE_HOLD),
        site=_site(),
    )

    assert result.readiness_class is MARReadinessClass.NOT_READY
    assert result.decision_status is DecisionStatus.BLOCK
    assert result.risk_level is RiskLevel.CRITICAL
    assert "source water is classified as unsafe hold" in result.reasons


def test_source_quality_gate_failure_blocks_recharge() -> None:
    result = evaluate_mar_readiness(
        source=_source(quality_gate_passed=False),
        site=_site(),
    )

    assert result.decision_status is DecisionStatus.BLOCK
    assert "source-water quality gate has not passed" in result.reasons


def test_unreviewed_treatment_route_blocks_recharge() -> None:
    result = evaluate_mar_readiness(
        source=_source(treatment_route_reviewed=False),
        site=_site(),
    )

    assert result.decision_status is DecisionStatus.BLOCK
    assert "source-water treatment route has not been reviewed" in result.reasons


def test_source_salinity_risk_blocks_recharge() -> None:
    result = evaluate_mar_readiness(
        source=_source(salinity_risk_fraction=0.8),
        site=_site(),
    )

    assert result.decision_status is DecisionStatus.BLOCK
    assert "source-water salinity risk exceeds recharge threshold" in result.reasons


def test_source_contamination_risk_blocks_recharge() -> None:
    result = evaluate_mar_readiness(
        source=_source(contamination_risk_fraction=0.8),
        site=_site(),
    )

    assert result.decision_status is DecisionStatus.BLOCK
    assert "source-water contamination risk exceeds recharge threshold" in result.reasons


def test_missing_source_evidence_blocks_recharge() -> None:
    result = evaluate_mar_readiness(
        source=_source(evidence_quality=EvidenceQuality.MISSING),
        site=_site(),
    )

    assert result.decision_status is DecisionStatus.BLOCK
    assert "treated reclaimed water batch evidence quality is missing" in result.reasons


def test_unknown_recharge_method_blocks_by_default() -> None:
    result = evaluate_mar_readiness(
        source=_source(),
        site=_site(method=RechargeMethod.UNKNOWN),
    )

    assert result.decision_status is DecisionStatus.BLOCK
    assert "recharge method is unknown" in result.reasons


def test_injection_well_blocks_by_default() -> None:
    result = evaluate_mar_readiness(
        source=_source(),
        site=_site(method=RechargeMethod.INJECTION_WELL),
    )

    assert result.decision_status is DecisionStatus.BLOCK
    assert "injection well concept requires specialist design and approval" in result.reasons


def test_groundwater_vulnerability_blocks_recharge() -> None:
    result = evaluate_mar_readiness(
        source=_source(),
        site=_site(groundwater_vulnerability_fraction=0.8),
    )

    assert result.decision_status is DecisionStatus.BLOCK
    assert "groundwater vulnerability exceeds configured recharge limit" in result.reasons


def test_nearby_contamination_source_blocks_recharge() -> None:
    result = evaluate_mar_readiness(
        source=_source(),
        site=_site(contamination_source_distance_m=25.0),
    )

    assert result.decision_status is DecisionStatus.BLOCK
    assert "site is too close to a known contamination source" in result.reasons


@pytest.mark.parametrize(
    ("field", "expected_reason"),
    [
        ("local_authority_review_available", "local authority review is not available"),
        ("environmental_review_available", "environmental review is not available"),
        ("community_review_available", "community review is not available"),
    ],
)
def test_missing_required_review_blocks_recharge(
    field: str,
    expected_reason: str,
) -> None:
    result = evaluate_mar_readiness(source=_source(), site=_site(**{field: False}))

    assert result.decision_status is DecisionStatus.BLOCK
    assert expected_reason in result.reasons


def test_low_source_volume_requires_investigation() -> None:
    result = evaluate_mar_readiness(
        source=_source(available_volume_l=500.0),
        site=_site(),
    )

    assert result.readiness_class is MARReadinessClass.INVESTIGATION_REQUIRED
    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.risk_level is RiskLevel.HIGH
    assert "available source-water volume is below pilot review threshold" in result.reasons


def test_low_infiltration_capacity_requires_investigation() -> None:
    result = evaluate_mar_readiness(
        source=_source(),
        site=_site(infiltration_capacity_fraction=0.2),
    )

    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert "site infiltration capacity is below pilot review threshold" in result.reasons


def test_low_geotechnical_stability_requires_investigation() -> None:
    result = evaluate_mar_readiness(
        source=_source(),
        site=_site(geotechnical_stability_fraction=0.4),
    )

    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert "site geotechnical stability is below pilot review threshold" in result.reasons


def test_missing_monitoring_well_requires_investigation() -> None:
    result = evaluate_mar_readiness(
        source=_source(),
        site=_site(monitoring_well_available=False),
    )

    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert "monitoring well or equivalent groundwater observation is unavailable" in (
        result.reasons
    )


def test_high_subsidence_risk_returns_monitoring_only() -> None:
    result = evaluate_mar_readiness(
        source=_source(),
        site=_site(subsidence_risk_fraction=0.8),
    )

    assert result.readiness_class is MARReadinessClass.MONITORING_ONLY
    assert result.decision_status is DecisionStatus.ALLOW_REVIEW
    assert result.risk_level is RiskLevel.MODERATE
    assert "subsidence risk supports monitoring-only posture before pilot recharge" in (
        result.reasons
    )


def test_policy_can_allow_injection_well_for_specialist_workflow() -> None:
    policy = MARReadinessPolicy(block_injection_well_without_specialist_review=False)

    result = evaluate_mar_readiness(
        source=_source(),
        site=_site(method=RechargeMethod.INJECTION_WELL),
        policy=policy,
    )

    assert result.decision_status is DecisionStatus.ALLOW_REVIEW
    assert result.readiness_class is MARReadinessClass.REVIEWABLE_PILOT
