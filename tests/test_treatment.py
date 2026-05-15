import pytest

from ix_vahdat.domain import DecisionStatus, RiskLevel
from ix_vahdat.quality import WaterQualityGateResult
from ix_vahdat.treatment import (
    TreatmentRoute,
    TreatmentRoutingPolicy,
    TreatmentSystemSnapshot,
    route_treatment_batch,
)


def _system(**overrides: object) -> TreatmentSystemSnapshot:
    values = {
        "pretreatment_available": True,
        "filtration_available": True,
        "disinfection_available": True,
        "storage_clean": True,
        "recirculation_available": True,
        "waste_hold_available": True,
        "filter_pressure_delta_kpa": 40.0,
        "flow_rate_l_min": 2.0,
        "tank_capacity_remaining_fraction": 0.5,
    }
    values.update(overrides)
    return TreatmentSystemSnapshot(**values)  # type: ignore[arg-type]


def _quality(
    status: DecisionStatus = DecisionStatus.ALLOW_REVIEW,
    risk: RiskLevel = RiskLevel.LOW,
    reasons: tuple[str, ...] = ("quality gate passed",),
) -> WaterQualityGateResult:
    return WaterQualityGateResult(
        decision_status=status,
        risk_level=risk,
        reasons=reasons,
        required_actions=("preserve evidence",),
    )


def test_ready_system_with_allowed_quality_passes_only_to_review() -> None:
    result = route_treatment_batch(
        quality_gate=_quality(),
        system=_system(),
    )

    assert result.route is TreatmentRoute.PASS_TO_REVIEW
    assert result.decision_status is DecisionStatus.ALLOW_REVIEW
    assert result.risk_level is RiskLevel.LOW
    assert result.requires_human_review is True
    assert "do not claim potable water from software output alone" in result.required_actions


@pytest.mark.parametrize(
    ("field", "value", "expected_reason"),
    [
        ("pretreatment_available", False, "pretreatment path is unavailable"),
        ("filtration_available", False, "filtration path is unavailable"),
        ("disinfection_available", False, "disinfection path is unavailable"),
        ("storage_clean", False, "storage cleanliness is not verified"),
        (
            "filter_pressure_delta_kpa",
            200.0,
            "filter pressure differential exceeds configured threshold",
        ),
        (
            "flow_rate_l_min",
            0.05,
            "flow rate is below configured minimum for reliable routing",
        ),
        (
            "tank_capacity_remaining_fraction",
            0.01,
            "tank capacity remaining is below configured minimum",
        ),
    ],
)
def test_readiness_blockers_hold_batch(
    field: str,
    value: object,
    expected_reason: str,
) -> None:
    result = route_treatment_batch(
        quality_gate=_quality(),
        system=_system(**{field: value}),
    )

    assert result.route is TreatmentRoute.HOLD_FOR_TESTING
    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.risk_level is RiskLevel.HIGH
    assert expected_reason in result.reasons


def test_blocked_chemical_quality_rejects_to_waste_review_when_possible() -> None:
    result = route_treatment_batch(
        quality_gate=_quality(
            status=DecisionStatus.BLOCK,
            risk=RiskLevel.CRITICAL,
            reasons=("chemical screen failed",),
        ),
        system=_system(),
    )

    assert result.route is TreatmentRoute.REJECT_TO_WASTE_REVIEW
    assert result.decision_status is DecisionStatus.BLOCK
    assert result.risk_level is RiskLevel.CRITICAL
    assert "hold for qualified chemical or disposal review" in result.required_actions


def test_blocked_chemical_quality_holds_when_waste_hold_is_unavailable() -> None:
    result = route_treatment_batch(
        quality_gate=_quality(
            status=DecisionStatus.BLOCK,
            risk=RiskLevel.CRITICAL,
            reasons=("chemical screen failed",),
        ),
        system=_system(waste_hold_available=False),
    )

    assert result.route is TreatmentRoute.HOLD_FOR_TESTING
    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.risk_level is RiskLevel.CRITICAL
    assert "create safe containment plan" in result.required_actions


def test_blocked_pathogen_quality_can_recirc_only_without_release() -> None:
    result = route_treatment_batch(
        quality_gate=_quality(
            status=DecisionStatus.BLOCK,
            risk=RiskLevel.CRITICAL,
            reasons=("pathogen indicator present",),
        ),
        system=_system(),
    )

    assert result.route is TreatmentRoute.RECIRCULATE
    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.risk_level is RiskLevel.CRITICAL
    assert "do not release or distribute water" in result.required_actions


def test_blocked_pathogen_quality_holds_when_recirc_disabled() -> None:
    policy = TreatmentRoutingPolicy(allow_recirc_on_critical_pathogen=False)

    result = route_treatment_batch(
        quality_gate=_quality(
            status=DecisionStatus.BLOCK,
            risk=RiskLevel.CRITICAL,
            reasons=("pathogen indicator present",),
        ),
        system=_system(),
        policy=policy,
    )

    assert result.route is TreatmentRoute.HOLD_FOR_TESTING
    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.risk_level is RiskLevel.CRITICAL


def test_hold_quality_recirc_when_available() -> None:
    result = route_treatment_batch(
        quality_gate=_quality(
            status=DecisionStatus.HOLD_FOR_TESTING,
            risk=RiskLevel.HIGH,
            reasons=("missing turbidity measurement",),
        ),
        system=_system(),
    )

    assert result.route is TreatmentRoute.RECIRCULATE
    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.risk_level is RiskLevel.HIGH
    assert "repeat quality gate before classification" in result.required_actions


def test_hold_quality_holds_when_recirc_unavailable() -> None:
    result = route_treatment_batch(
        quality_gate=_quality(
            status=DecisionStatus.HOLD_FOR_TESTING,
            risk=RiskLevel.MODERATE,
            reasons=("disinfection evidence missing or unverified",),
        ),
        system=_system(recirculation_available=False),
    )

    assert result.route is TreatmentRoute.HOLD_FOR_TESTING
    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.risk_level is RiskLevel.HIGH
    assert "recirculation is unavailable or disabled by policy" in result.reasons


def test_system_snapshot_rejects_invalid_values() -> None:
    with pytest.raises(ValueError, match="filter_pressure_delta"):
        _system(filter_pressure_delta_kpa=-1.0)

    with pytest.raises(ValueError, match="flow_rate"):
        _system(flow_rate_l_min=-1.0)

    with pytest.raises(ValueError, match="tank_capacity"):
        _system(tank_capacity_remaining_fraction=1.2)
