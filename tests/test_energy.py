import pytest

from ix_vahdat.domain import DecisionStatus, EvidenceQuality, RiskLevel
from ix_vahdat.energy import (
    EnergyAccountingPolicy,
    EnergySource,
    EnergySnapshot,
    calculate_energy_accounting,
)


def _snapshot(**overrides: object) -> EnergySnapshot:
    values = {
        "source": EnergySource.SOLAR,
        "evidence_quality": EvidenceQuality.MEASURED,
        "runtime_hours": 2.0,
        "average_power_w": 500.0,
        "water_output_l": 2.0,
        "critical_load_power_w": 100.0,
        "available_power_w": 800.0,
        "battery_state_fraction": 0.75,
        "reserve_battery_fraction": 0.25,
        "measurement_notes": "measured at the water-node boundary",
    }
    values.update(overrides)
    return EnergySnapshot(**values)  # type: ignore[arg-type]


def test_snapshot_computes_energy_input_and_energy_per_liter() -> None:
    snapshot = _snapshot(runtime_hours=2.0, average_power_w=500.0, water_output_l=2.0)

    assert snapshot.energy_input_wh == 1_000.0
    assert snapshot.energy_per_liter_wh_l == 500.0
    assert snapshot.has_power_margin_for_critical_loads is True
    assert snapshot.battery_reserve_is_protected is True


def test_snapshot_returns_none_energy_per_liter_without_water_output() -> None:
    snapshot = _snapshot(water_output_l=0.0)

    assert snapshot.energy_per_liter_wh_l is None


@pytest.mark.parametrize(
    ("field", "value", "expected_message"),
    [
        ("runtime_hours", -1.0, "runtime_hours"),
        ("average_power_w", -1.0, "average_power_w"),
        ("water_output_l", -1.0, "water_output_l"),
        ("critical_load_power_w", -1.0, "critical_load_power_w"),
        ("available_power_w", -1.0, "available_power_w"),
        ("battery_state_fraction", 1.2, "battery_state_fraction"),
        ("reserve_battery_fraction", -0.1, "reserve_battery_fraction"),
    ],
)
def test_snapshot_rejects_invalid_values(
    field: str,
    value: float,
    expected_message: str,
) -> None:
    with pytest.raises(ValueError, match=expected_message):
        _snapshot(**{field: value})


def test_snapshot_rejects_reserve_above_battery_state() -> None:
    with pytest.raises(ValueError, match="reserve_battery_fraction"):
        _snapshot(battery_state_fraction=0.2, reserve_battery_fraction=0.3)


def test_calculator_allows_review_when_energy_evidence_is_within_threshold() -> None:
    result = calculate_energy_accounting(
        _snapshot(runtime_hours=2.0, average_power_w=500.0, water_output_l=2.0),
        operation_label="active condensation trial",
        is_atmospheric_water_operation=True,
    )

    assert result.decision_status is DecisionStatus.ALLOW_REVIEW
    assert result.risk_level is RiskLevel.LOW
    assert result.energy_input_wh == 1_000.0
    assert result.energy_per_liter_wh_l == 500.0
    assert result.has_claim_support is True
    assert "human review required before performance or deployment claims" in result.required_actions


def test_estimated_energy_evidence_allows_review_with_moderate_risk() -> None:
    result = calculate_energy_accounting(
        _snapshot(evidence_quality=EvidenceQuality.ESTIMATED),
        operation_label="solar desorption trial",
    )

    assert result.decision_status is DecisionStatus.ALLOW_REVIEW
    assert result.risk_level is RiskLevel.MODERATE
    assert "energy evidence is estimated rather than directly measured" in result.reasons
    assert "replace estimate with measured evidence before procurement" in result.required_actions


def test_missing_energy_evidence_holds_for_testing() -> None:
    result = calculate_energy_accounting(
        _snapshot(evidence_quality=EvidenceQuality.MISSING),
        operation_label="treatment skid run",
    )

    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.risk_level is RiskLevel.HIGH
    assert "energy evidence quality is missing" in result.reasons
    assert result.has_claim_support is False


def test_short_runtime_holds_for_testing() -> None:
    result = calculate_energy_accounting(
        _snapshot(runtime_hours=0.1),
        operation_label="short AWG run",
    )

    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert "runtime is below minimum duration for a water-output claim" in result.reasons


def test_unknown_energy_source_holds_when_policy_requires_traceability() -> None:
    result = calculate_energy_accounting(
        _snapshot(source=EnergySource.UNKNOWN),
        operation_label="unknown source run",
    )

    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.risk_level is RiskLevel.HIGH
    assert "energy source is unknown" in result.reasons
    assert "do not claim water output without energy traceability" in result.required_actions


def test_unknown_energy_source_can_pass_when_policy_allows_it() -> None:
    policy = EnergyAccountingPolicy(block_unknown_energy_source=False)

    result = calculate_energy_accounting(
        _snapshot(source=EnergySource.UNKNOWN),
        policy=policy,
        operation_label="temporary source run",
    )

    assert result.decision_status is DecisionStatus.ALLOW_REVIEW


def test_low_water_output_holds_for_testing() -> None:
    result = calculate_energy_accounting(
        _snapshot(water_output_l=0.05),
        operation_label="low-output run",
    )

    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.risk_level is RiskLevel.MODERATE
    assert "water output is below minimum measurable claim threshold" in result.reasons


def test_high_energy_per_liter_holds_for_redesign() -> None:
    result = calculate_energy_accounting(
        _snapshot(runtime_hours=4.0, average_power_w=1_000.0, water_output_l=1.0),
        operation_label="active condensation run",
        is_atmospheric_water_operation=True,
    )

    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.risk_level is RiskLevel.HIGH
    assert result.energy_per_liter_wh_l == 4_000.0
    assert "active condensation run energy per liter exceeds configured review threshold" in (
        result.reasons
    )


def test_low_available_power_holds_for_testing() -> None:
    result = calculate_energy_accounting(
        _snapshot(available_power_w=80.0, critical_load_power_w=100.0),
        operation_label="treatment run",
    )

    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert "available power is below critical load demand" in result.reasons


def test_low_power_margin_holds_for_testing() -> None:
    result = calculate_energy_accounting(
        _snapshot(available_power_w=130.0, critical_load_power_w=100.0),
        operation_label="treatment run",
    )

    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert "power margin above critical loads is below configured minimum" in result.reasons


def test_low_battery_state_holds_for_testing() -> None:
    result = calculate_energy_accounting(
        _snapshot(battery_state_fraction=0.1, reserve_battery_fraction=0.05),
        operation_label="battery-backed treatment run",
    )

    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert "battery state is below configured minimum" in result.reasons


def test_operation_label_is_required() -> None:
    with pytest.raises(ValueError, match="operation_label"):
        calculate_energy_accounting(_snapshot(), operation_label=" ")
