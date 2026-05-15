import pytest

from ix_vahdat.domain import DecisionStatus, EvidenceQuality, RiskLevel, SensorStatus
from ix_vahdat.maintenance import (
    MaintenanceCategory,
    MaintenanceItem,
    MaintenancePolicy,
    MaintenanceSnapshot,
    MaintenanceState,
    evaluate_maintenance,
)


def _item(**overrides: object) -> MaintenanceItem:
    values = {
        "item_id": "filter-1",
        "label": "cartridge filter",
        "category": MaintenanceCategory.FILTER,
        "state": MaintenanceState.OK,
        "critical": True,
        "evidence_quality": EvidenceQuality.MEASURED,
        "sensor_status": SensorStatus.OK,
        "hours_since_service": 10.0,
        "service_interval_hours": 100.0,
        "notes": "field inspection recorded",
    }
    values.update(overrides)
    return MaintenanceItem(**values)  # type: ignore[arg-type]


def _snapshot(*items: MaintenanceItem) -> MaintenanceSnapshot:
    return MaintenanceSnapshot(items=items or (_item(),))


def test_item_computes_service_fraction_and_due_states() -> None:
    item = _item(hours_since_service=80.0, service_interval_hours=100.0)

    assert item.service_fraction_used == 0.8
    assert item.is_due_soon_by_hours is True
    assert item.is_due_by_hours is False


def test_item_detects_exceeded_service_interval() -> None:
    item = _item(hours_since_service=100.0, service_interval_hours=100.0)

    assert item.is_due_by_hours is True


@pytest.mark.parametrize(
    ("field", "value", "expected_message"),
    [
        ("item_id", " ", "item_id"),
        ("label", " ", "label"),
        ("hours_since_service", -1.0, "hours_since_service"),
        ("service_interval_hours", 0.0, "service_interval_hours"),
        ("notes", " ", "notes"),
    ],
)
def test_item_rejects_invalid_values(
    field: str,
    value: object,
    expected_message: str,
) -> None:
    with pytest.raises(ValueError, match=expected_message):
        _item(**{field: value})


def test_snapshot_rejects_empty_items() -> None:
    with pytest.raises(ValueError, match="at least one maintenance item"):
        MaintenanceSnapshot(items=())


def test_snapshot_rejects_duplicate_item_ids() -> None:
    with pytest.raises(ValueError, match="unique"):
        MaintenanceSnapshot(items=(_item(item_id="same"), _item(item_id="same")))


def test_policy_rejects_invalid_due_soon_fraction() -> None:
    with pytest.raises(ValueError, match="due_soon_fraction"):
        MaintenancePolicy(due_soon_fraction=1.5)


def test_all_ready_items_allow_review() -> None:
    result = evaluate_maintenance(
        _snapshot(
            _item(item_id="filter-1", label="cartridge filter"),
            _item(
                item_id="tank-1",
                label="storage tank",
                category=MaintenanceCategory.STORAGE_TANK,
                critical=True,
            ),
        )
    )

    assert result.decision_status is DecisionStatus.ALLOW_REVIEW
    assert result.risk_level is RiskLevel.LOW
    assert result.maintenance_ready is True
    assert result.ready_items == ("filter-1", "tank-1")
    assert result.blocked_items == ()
    assert "maintenance evidence is reviewable and no blockers were found" in result.reasons


def test_due_soon_item_allows_review_with_moderate_risk() -> None:
    result = evaluate_maintenance(
        _snapshot(
            _item(
                item_id="filter-1",
                label="cartridge filter",
                state=MaintenanceState.DUE_SOON,
            )
        )
    )

    assert result.decision_status is DecisionStatus.ALLOW_REVIEW
    assert result.risk_level is RiskLevel.MODERATE
    assert result.maintenance_ready is True
    assert result.due_soon_items == ("filter-1",)
    assert "cartridge filter maintenance state is due soon" in result.reasons


def test_service_fraction_due_soon_allows_review_with_warning() -> None:
    result = evaluate_maintenance(
        _snapshot(
            _item(
                item_id="uv-1",
                label="UV disinfection lamp",
                category=MaintenanceCategory.UV_DISINFECTION,
                hours_since_service=85.0,
                service_interval_hours=100.0,
            )
        )
    )

    assert result.decision_status is DecisionStatus.ALLOW_REVIEW
    assert result.risk_level is RiskLevel.MODERATE
    assert result.due_soon_items == ("uv-1",)
    assert "UV disinfection lamp service interval is approaching configured limit" in result.reasons


def test_missing_evidence_holds_for_testing() -> None:
    result = evaluate_maintenance(
        _snapshot(
            _item(
                item_id="sensor-1",
                label="pH sensor",
                category=MaintenanceCategory.WATER_QUALITY_SENSOR,
                evidence_quality=EvidenceQuality.MISSING,
            )
        )
    )

    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.risk_level is RiskLevel.HIGH
    assert result.maintenance_ready is False
    assert result.blocked_items == ("sensor-1",)
    assert "pH sensor evidence quality is missing" in result.reasons
    assert "calibrate or replace water-quality sensor before classification" in (
        result.required_actions
    )


def test_stale_sensor_holds_for_testing() -> None:
    result = evaluate_maintenance(
        _snapshot(
            _item(
                item_id="conductivity-sensor-1",
                label="conductivity sensor",
                category=MaintenanceCategory.WATER_QUALITY_SENSOR,
                sensor_status=SensorStatus.STALE,
            )
        )
    )

    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.risk_level is RiskLevel.HIGH
    assert "conductivity sensor sensor status is stale" in result.reasons


def test_overdue_critical_item_holds_for_testing() -> None:
    result = evaluate_maintenance(
        _snapshot(
            _item(
                item_id="tank-1",
                label="storage tank",
                category=MaintenanceCategory.STORAGE_TANK,
                state=MaintenanceState.OVERDUE,
                critical=True,
            )
        )
    )

    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.risk_level is RiskLevel.HIGH
    assert "storage tank maintenance state is overdue" in result.reasons
    assert "inspect tank cleanliness and integrity before release review" in (
        result.required_actions
    )


def test_exceeded_service_interval_holds_for_testing() -> None:
    result = evaluate_maintenance(
        _snapshot(
            _item(
                item_id="sorbent-1",
                label="sorbent cartridge",
                category=MaintenanceCategory.SORBENT_CARTRIDGE,
                hours_since_service=120.0,
                service_interval_hours=100.0,
                critical=True,
            )
        )
    )

    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.risk_level is RiskLevel.HIGH
    assert "sorbent cartridge service interval is exceeded" in result.reasons
    assert "replace or verify sorbent cartridge before collection review" in (
        result.required_actions
    )


def test_failed_critical_item_blocks() -> None:
    result = evaluate_maintenance(
        _snapshot(
            _item(
                item_id="uv-1",
                label="UV disinfection lamp",
                category=MaintenanceCategory.UV_DISINFECTION,
                state=MaintenanceState.FAILED,
                critical=True,
            )
        )
    )

    assert result.decision_status is DecisionStatus.BLOCK
    assert result.risk_level is RiskLevel.CRITICAL
    assert result.maintenance_ready is False
    assert "UV disinfection lamp maintenance state is failed" in result.reasons
    assert "critical item blocks dependent water-support decisions" in result.required_actions


def test_failed_noncritical_item_holds_with_moderate_risk() -> None:
    result = evaluate_maintenance(
        _snapshot(
            _item(
                item_id="fog-mesh-1",
                label="fog mesh",
                category=MaintenanceCategory.FOG_MESH,
                state=MaintenanceState.FAILED,
                critical=False,
            )
        )
    )

    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.risk_level is RiskLevel.MODERATE
    assert "fog mesh maintenance state is failed" in result.reasons
    assert "clean or replace collection mesh before atmospheric-water review" in (
        result.required_actions
    )


def test_policy_can_prevent_failed_critical_item_from_blocking_hard() -> None:
    policy = MaintenancePolicy(block_failed_critical_items=False)

    result = evaluate_maintenance(
        _snapshot(
            _item(
                item_id="pump-1",
                label="transfer pump",
                category=MaintenanceCategory.PUMP,
                state=MaintenanceState.FAILED,
                critical=True,
            )
        ),
        policy=policy,
    )

    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.risk_level is RiskLevel.HIGH
    assert "transfer pump maintenance state is failed" in result.reasons


def test_multiple_reasons_are_deduplicated_in_required_actions() -> None:
    result = evaluate_maintenance(
        _snapshot(
            _item(
                item_id="battery-1",
                label="battery pack",
                category=MaintenanceCategory.BATTERY,
                state=MaintenanceState.OVERDUE,
                critical=True,
                hours_since_service=120.0,
                service_interval_hours=100.0,
            )
        )
    )

    assert result.required_actions.count(
        "hold affected water-support decision until maintenance is resolved"
    ) == 1
    assert "restore battery readiness before critical-load review" in result.required_actions
