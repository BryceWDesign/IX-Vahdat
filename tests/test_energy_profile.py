import pytest

from ix_vahdat.domain import DecisionStatus, EvidenceQuality, RiskLevel
from ix_vahdat.energy_profile import (
    EnergyPortfolioPolicy,
    WaterEnergyProfile,
    WaterSupportPath,
    evaluate_energy_portfolio,
)


def _profile(**overrides: object) -> WaterEnergyProfile:
    values = {
        "path": WaterSupportPath.REUSE_TREATMENT,
        "label": "greywater treatment trial",
        "produced_water_l": 100.0,
        "energy_input_wh": 25_000.0,
        "evidence_quality": EvidenceQuality.MEASURED,
        "safety_gate_passed": True,
        "maintenance_ready": True,
        "uses_passive_environmental_energy": False,
        "notes": "measured at treatment-skid boundary",
    }
    values.update(overrides)
    return WaterEnergyProfile(**values)  # type: ignore[arg-type]


def test_profile_computes_wh_per_liter_and_kwh_per_cubic_meter() -> None:
    profile = _profile(produced_water_l=100.0, energy_input_wh=25_000.0)

    assert profile.energy_per_liter_wh_l == 250.0
    assert profile.energy_per_cubic_meter_kwh_m3 == 250.0


def test_profile_returns_none_energy_per_liter_without_output() -> None:
    profile = _profile(produced_water_l=0.0)

    assert profile.energy_per_liter_wh_l is None
    assert profile.energy_per_cubic_meter_kwh_m3 is None


@pytest.mark.parametrize(
    ("field", "value", "expected_message"),
    [
        ("label", " ", "label"),
        ("produced_water_l", -1.0, "produced_water_l"),
        ("energy_input_wh", -1.0, "energy_input_wh"),
        ("notes", " ", "notes"),
    ],
)
def test_profile_rejects_invalid_values(
    field: str,
    value: object,
    expected_message: str,
) -> None:
    with pytest.raises(ValueError, match=expected_message):
        _profile(**{field: value})


def test_policy_thresholds_are_immutable() -> None:
    policy = EnergyPortfolioPolicy(
        path_thresholds_wh_l={WaterSupportPath.REUSE_TREATMENT: 800.0}
    )

    assert policy.threshold_for_path(WaterSupportPath.REUSE_TREATMENT) == 800.0

    with pytest.raises(TypeError):
        policy.path_thresholds_wh_l[WaterSupportPath.REUSE_TREATMENT] = 900.0  # type: ignore[index]


def test_policy_returns_path_specific_defaults() -> None:
    policy = EnergyPortfolioPolicy()

    assert policy.threshold_for_path(WaterSupportPath.ACTIVE_CONDENSATION_AWH) == 2_500.0
    assert policy.threshold_for_path(WaterSupportPath.DESALINATION) == 6_000.0
    assert policy.threshold_for_path(WaterSupportPath.TANKER_SUPPLY) == 8_000.0
    assert policy.threshold_for_path(WaterSupportPath.REUSE_TREATMENT) == 1_500.0


def test_empty_portfolio_holds_for_testing() -> None:
    result = evaluate_energy_portfolio(())

    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.risk_level is RiskLevel.HIGH
    assert result.assessments == ()
    assert result.has_reviewable_path is False
    assert "no water-support energy profiles were provided" in result.reasons


def test_reviewable_profiles_are_sorted_by_energy_per_liter() -> None:
    reuse = _profile(
        path=WaterSupportPath.REUSE_TREATMENT,
        label="reuse treatment",
        produced_water_l=100.0,
        energy_input_wh=20_000.0,
    )
    active_awh = _profile(
        path=WaterSupportPath.ACTIVE_CONDENSATION_AWH,
        label="active condensation",
        produced_water_l=10.0,
        energy_input_wh=12_000.0,
    )

    result = evaluate_energy_portfolio((active_awh, reuse))

    assert result.decision_status is DecisionStatus.ALLOW_REVIEW
    assert result.has_reviewable_path is True
    assert result.preferred_review_path is WaterSupportPath.REUSE_TREATMENT
    assert result.assessments[0].label == "reuse treatment"
    assert result.assessments[0].energy_per_liter_wh_l == 200.0
    assert result.assessments[1].label == "active condensation"
    assert result.assessments[1].energy_per_liter_wh_l == 1_200.0


def test_passive_zero_direct_energy_path_can_continue_with_warning() -> None:
    fog = _profile(
        path=WaterSupportPath.FOG_OR_DEW_CAPTURE,
        label="passive fog mesh trial",
        produced_water_l=5.0,
        energy_input_wh=0.0,
        uses_passive_environmental_energy=True,
    )

    result = evaluate_energy_portfolio((fog,))
    assessment = result.assessments[0]

    assert result.decision_status is DecisionStatus.ALLOW_REVIEW
    assert assessment.decision_status is DecisionStatus.ALLOW_REVIEW
    assert assessment.energy_per_liter_wh_l == 0.0
    assert "direct measured energy is zero because the path is passive" in assessment.reasons
    assert any("do not describe passive collection as free" in action for action in assessment.required_actions)


def test_estimated_energy_profile_allows_review_with_moderate_risk() -> None:
    result = evaluate_energy_portfolio(
        (_profile(evidence_quality=EvidenceQuality.ESTIMATED),)
    )
    assessment = result.assessments[0]

    assert result.decision_status is DecisionStatus.ALLOW_REVIEW
    assert assessment.risk_level is RiskLevel.MODERATE
    assert "energy evidence is estimated rather than measured" in assessment.reasons
    assert "replace estimate with measured data before procurement" in assessment.required_actions


def test_missing_energy_profile_evidence_holds_for_testing() -> None:
    result = evaluate_energy_portfolio(
        (_profile(evidence_quality=EvidenceQuality.MISSING),)
    )
    assessment = result.assessments[0]

    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert assessment.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert assessment.risk_level is RiskLevel.HIGH
    assert "energy evidence quality is missing" in assessment.reasons


def test_failed_safety_gate_holds_even_if_energy_is_efficient() -> None:
    result = evaluate_energy_portfolio(
        (_profile(safety_gate_passed=False, energy_input_wh=1_000.0),)
    )
    assessment = result.assessments[0]

    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert assessment.risk_level is RiskLevel.HIGH
    assert "safety gate has not passed for this path" in assessment.reasons
    assert "do not treat energy efficiency as permission to use water" in (
        assessment.required_actions
    )


def test_failed_maintenance_gate_holds_even_if_energy_is_efficient() -> None:
    result = evaluate_energy_portfolio(
        (_profile(maintenance_ready=False, energy_input_wh=1_000.0),)
    )
    assessment = result.assessments[0]

    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert assessment.risk_level is RiskLevel.HIGH
    assert "maintenance readiness has not passed for this path" in assessment.reasons


def test_low_output_holds_for_testing() -> None:
    result = evaluate_energy_portfolio(
        (_profile(produced_water_l=0.05, energy_input_wh=10.0),)
    )
    assessment = result.assessments[0]

    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert assessment.risk_level is RiskLevel.MODERATE
    assert "water output is below minimum comparison threshold" in assessment.reasons


def test_high_energy_per_liter_holds_for_redesign() -> None:
    result = evaluate_energy_portfolio(
        (
            _profile(
                path=WaterSupportPath.ACTIVE_CONDENSATION_AWH,
                label="inefficient active condensation",
                produced_water_l=1.0,
                energy_input_wh=4_000.0,
            ),
        )
    )
    assessment = result.assessments[0]

    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert assessment.risk_level is RiskLevel.HIGH
    assert assessment.energy_per_liter_wh_l == 4_000.0
    assert "energy per liter exceeds configured review threshold" in assessment.reasons
    assert "do not scale this path without redesign" in assessment.required_actions


def test_custom_threshold_can_allow_otherwise_high_energy_profile() -> None:
    policy = EnergyPortfolioPolicy(
        path_thresholds_wh_l={WaterSupportPath.ACTIVE_CONDENSATION_AWH: 5_000.0}
    )
    result = evaluate_energy_portfolio(
        (
            _profile(
                path=WaterSupportPath.ACTIVE_CONDENSATION_AWH,
                label="active condensation high-energy trial",
                produced_water_l=1.0,
                energy_input_wh=4_000.0,
            ),
        ),
        policy=policy,
    )

    assert result.decision_status is DecisionStatus.ALLOW_REVIEW
    assert result.assessments[0].threshold_wh_l == 5_000.0


def test_mixed_portfolio_allows_review_if_at_least_one_path_is_reviewable() -> None:
    reviewable = _profile(label="reviewable reuse path")
    held = _profile(
        label="held active condensation path",
        path=WaterSupportPath.ACTIVE_CONDENSATION_AWH,
        produced_water_l=1.0,
        energy_input_wh=4_000.0,
    )

    result = evaluate_energy_portfolio((held, reviewable))

    assert result.decision_status is DecisionStatus.ALLOW_REVIEW
    assert result.has_reviewable_path is True
    assert result.preferred_review_path is WaterSupportPath.REUSE_TREATMENT
    assert any(item.decision_status is DecisionStatus.HOLD_FOR_TESTING for item in result.assessments)
