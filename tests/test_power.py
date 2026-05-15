import pytest

from ix_vahdat.domain import DecisionStatus, RiskLevel
from ix_vahdat.power import (
    LoadPriority,
    PowerLoad,
    PowerMode,
    PowerPriorityPolicy,
    PowerSystemSnapshot,
    evaluate_power_priority,
)


def _load(
    name: str,
    priority: LoadPriority,
    power_w: float,
    *,
    enabled: bool = True,
    required_for_safe_hold: bool = False,
) -> PowerLoad:
    return PowerLoad(
        name=name,
        priority=priority,
        power_w=power_w,
        enabled=enabled,
        required_for_safe_hold=required_for_safe_hold,
    )


def _loads() -> tuple[PowerLoad, ...]:
    return (
        _load(
            "evidence_logger",
            LoadPriority.CRITICAL,
            20.0,
            required_for_safe_hold=True,
        ),
        _load(
            "water_quality_sensors",
            LoadPriority.CRITICAL,
            35.0,
            required_for_safe_hold=True,
        ),
        _load("telemetry_radio", LoadPriority.IMPORTANT, 15.0),
        _load("treatment_pump", LoadPriority.DEFERRABLE, 180.0),
        _load("active_condensation_awg", LoadPriority.NONESSENTIAL, 700.0),
    )


def _snapshot(**overrides: object) -> PowerSystemSnapshot:
    values = {
        "available_power_w": 1_200.0,
        "battery_state_fraction": 0.80,
        "reserve_battery_fraction": 0.20,
        "loads": _loads(),
    }
    values.update(overrides)
    return PowerSystemSnapshot(**values)  # type: ignore[arg-type]


def test_power_load_requires_safe_hold_loads_to_be_critical() -> None:
    with pytest.raises(ValueError, match="safe-hold loads"):
        _load(
            "noncritical_safe_hold",
            LoadPriority.IMPORTANT,
            10.0,
            required_for_safe_hold=True,
        )


def test_power_load_rejects_invalid_values() -> None:
    with pytest.raises(ValueError, match="load name"):
        _load(" ", LoadPriority.CRITICAL, 10.0)

    with pytest.raises(ValueError, match="power_w"):
        _load("sensor", LoadPriority.CRITICAL, -1.0)


def test_snapshot_computes_load_totals() -> None:
    snapshot = _snapshot()

    assert snapshot.total_enabled_load_w == 950.0
    assert snapshot.critical_enabled_load_w == 55.0
    assert snapshot.safe_hold_load_w == 55.0
    assert snapshot.power_margin_w == 250.0
    assert tuple(load.name for load in snapshot.safe_hold_loads) == (
        "evidence_logger",
        "water_quality_sensors",
    )


def test_snapshot_rejects_empty_load_set() -> None:
    with pytest.raises(ValueError, match="at least one power load"):
        _snapshot(loads=())


def test_snapshot_rejects_reserve_above_battery_state() -> None:
    with pytest.raises(ValueError, match="reserve_battery_fraction"):
        _snapshot(battery_state_fraction=0.20, reserve_battery_fraction=0.30)


def test_normal_operation_when_power_and_battery_are_sufficient() -> None:
    result = evaluate_power_priority(_snapshot())

    assert result.mode is PowerMode.NORMAL
    assert result.decision_status is DecisionStatus.ALLOW_REVIEW
    assert result.risk_level is RiskLevel.LOW
    assert result.is_normal_operation is True
    assert result.shed_loads == ()
    assert "active_condensation_awg" in result.allowed_loads


def test_service_required_when_no_safe_hold_loads_are_defined() -> None:
    loads = (
        _load("telemetry_radio", LoadPriority.IMPORTANT, 15.0),
        _load("treatment_pump", LoadPriority.DEFERRABLE, 180.0),
    )

    result = evaluate_power_priority(_snapshot(loads=loads))

    assert result.mode is PowerMode.SERVICE_REQUIRED
    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.risk_level is RiskLevel.HIGH
    assert "no safe-hold critical load set is defined" in result.reasons
    assert result.shed_loads == ("telemetry_radio", "treatment_pump")


def test_safe_hold_when_available_power_cannot_support_safe_hold_loads() -> None:
    result = evaluate_power_priority(_snapshot(available_power_w=40.0))

    assert result.mode is PowerMode.SAFE_HOLD
    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.risk_level is RiskLevel.CRITICAL
    assert result.allowed_loads == ("evidence_logger", "water_quality_sensors")
    assert "active_condensation_awg" in result.shed_loads
    assert "restore power before treatment, pumping, harvesting, or distribution review" in (
        result.required_actions
    )


def test_safe_hold_when_battery_reaches_protected_reserve() -> None:
    result = evaluate_power_priority(
        _snapshot(battery_state_fraction=0.20, reserve_battery_fraction=0.20)
    )

    assert result.mode is PowerMode.SAFE_HOLD
    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.risk_level is RiskLevel.CRITICAL
    assert result.allowed_loads == ("evidence_logger", "water_quality_sensors")
    assert "protect emergency reserve" in result.required_actions


def test_emergency_mode_keeps_only_critical_loads() -> None:
    result = evaluate_power_priority(
        _snapshot(battery_state_fraction=0.24, reserve_battery_fraction=0.20)
    )

    assert result.mode is PowerMode.EMERGENCY
    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.risk_level is RiskLevel.HIGH
    assert result.allowed_loads == ("evidence_logger", "water_quality_sensors")
    assert "telemetry_radio" in result.shed_loads
    assert "active_condensation_awg" in result.shed_loads


def test_conserve_mode_sheds_deferrable_and_nonessential_loads_on_low_battery() -> None:
    result = evaluate_power_priority(
        _snapshot(battery_state_fraction=0.35, reserve_battery_fraction=0.20)
    )

    assert result.mode is PowerMode.CONSERVE
    assert result.decision_status is DecisionStatus.ALLOW_REVIEW
    assert result.risk_level is RiskLevel.MODERATE
    assert result.allowed_loads == (
        "evidence_logger",
        "water_quality_sensors",
        "telemetry_radio",
    )
    assert result.shed_loads == ("treatment_pump", "active_condensation_awg")


def test_conserve_hold_when_enabled_loads_exceed_available_power() -> None:
    result = evaluate_power_priority(_snapshot(available_power_w=500.0))

    assert result.mode is PowerMode.CONSERVE
    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.risk_level is RiskLevel.HIGH
    assert "enabled loads exceed available power" in result.reasons
    assert "active_condensation_awg" in result.shed_loads


def test_conserve_review_when_power_margin_is_below_configured_minimum() -> None:
    result = evaluate_power_priority(_snapshot(available_power_w=990.0))

    assert result.mode is PowerMode.CONSERVE
    assert result.decision_status is DecisionStatus.ALLOW_REVIEW
    assert result.risk_level is RiskLevel.MODERATE
    assert "power margin is below configured minimum" in result.reasons
    assert "shed lower-priority loads or restore power margin" in result.required_actions


def test_policy_rejects_invalid_threshold_ordering() -> None:
    with pytest.raises(ValueError, match="emergency_battery_fraction"):
        PowerPriorityPolicy(
            emergency_battery_fraction=0.50,
            conserve_battery_fraction=0.40,
        )

    with pytest.raises(ValueError, match="min_operating_battery_fraction"):
        PowerPriorityPolicy(
            min_operating_battery_fraction=0.60,
            conserve_battery_fraction=0.40,
        )
