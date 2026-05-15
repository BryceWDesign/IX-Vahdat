from datetime import UTC, datetime

import pytest

from ix_vahdat.asset_checks import (
    CollectionPanelKind,
    PanelHealthInput,
    PipeHealthInput,
    PumpHealthInput,
    TankHealthInput,
    build_panel_observation,
    build_pipe_observation,
    build_pump_observation,
    build_tank_observation,
)
from ix_vahdat.domain import DecisionStatus, EvidenceQuality, RiskLevel, SensorStatus
from ix_vahdat.infrastructure import (
    AssetHealthState,
    InfrastructureAssetType,
    InfrastructureSnapshot,
    evaluate_infrastructure_health,
)


OBSERVED_AT = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)


def _tank(**overrides: object) -> TankHealthInput:
    values = {
        "asset_id": "tank-1",
        "label": "emergency storage tank",
        "observed_at": OBSERVED_AT,
        "evidence_quality": EvidenceQuality.MEASURED,
        "sensor_status": SensorStatus.OK,
        "leak_detected": False,
        "storage_clean": True,
        "tank_integrity_verified": True,
        "deformation_fraction": 0.1,
        "corrosion_fraction": 0.1,
        "contamination_pathway_risk_fraction": 0.1,
        "critical_to_water_safety": True,
        "notes": "field inspection recorded",
    }
    values.update(overrides)
    return TankHealthInput(**values)  # type: ignore[arg-type]


def _pipe(**overrides: object) -> PipeHealthInput:
    values = {
        "asset_id": "pipe-1",
        "label": "feed pipe",
        "observed_at": OBSERVED_AT,
        "evidence_quality": EvidenceQuality.MEASURED,
        "sensor_status": SensorStatus.OK,
        "leak_detected": False,
        "deformation_fraction": 0.1,
        "vibration_fraction": 0.1,
        "corrosion_fraction": 0.1,
        "pressure_anomaly_fraction": 0.1,
        "contamination_pathway_risk_fraction": 0.1,
        "critical_to_water_safety": True,
        "notes": "pressure and visual inspection recorded",
    }
    values.update(overrides)
    return PipeHealthInput(**values)  # type: ignore[arg-type]


def _pump(**overrides: object) -> PumpHealthInput:
    values = {
        "asset_id": "pump-1",
        "label": "transfer pump",
        "observed_at": OBSERVED_AT,
        "evidence_quality": EvidenceQuality.MEASURED,
        "sensor_status": SensorStatus.OK,
        "operational": True,
        "leak_detected": False,
        "vibration_fraction": 0.1,
        "flow_anomaly_fraction": 0.1,
        "mount_deformation_fraction": 0.1,
        "corrosion_fraction": 0.1,
        "critical_to_water_safety": True,
        "notes": "pump run check recorded",
    }
    values.update(overrides)
    return PumpHealthInput(**values)  # type: ignore[arg-type]


def _panel(**overrides: object) -> PanelHealthInput:
    values = {
        "asset_id": "panel-1",
        "label": "AWH collector panel",
        "panel_kind": CollectionPanelKind.AWH_PANEL,
        "observed_at": OBSERVED_AT,
        "evidence_quality": EvidenceQuality.MEASURED,
        "sensor_status": SensorStatus.OK,
        "mounted_securely": True,
        "collection_surface_clean": True,
        "electrical_or_collection_fault_detected": False,
        "mount_deformation_fraction": 0.1,
        "surface_contamination_fraction": 0.1,
        "corrosion_fraction": 0.1,
        "vibration_fraction": 0.1,
        "critical_to_water_safety": False,
        "notes": "surface and mount inspection recorded",
    }
    values.update(overrides)
    return PanelHealthInput(**values)  # type: ignore[arg-type]


def test_tank_builder_creates_normal_storage_tank_observation() -> None:
    observation = build_tank_observation(_tank())

    assert observation.asset_type is InfrastructureAssetType.STORAGE_TANK
    assert observation.health_state is AssetHealthState.NORMAL
    assert observation.critical_to_water_safety is True
    assert observation.contamination_pathway_risk_fraction == 0.1


def test_dirty_tank_raises_contamination_risk_and_degraded_state() -> None:
    observation = build_tank_observation(_tank(storage_clean=False))

    assert observation.health_state is AssetHealthState.DEGRADED
    assert observation.contamination_pathway_risk_fraction == 0.75


def test_tank_integrity_failure_creates_critical_observation() -> None:
    observation = build_tank_observation(_tank(tank_integrity_verified=False))

    assert observation.health_state is AssetHealthState.CRITICAL


def test_pipe_builder_maps_pressure_anomaly_and_leak_state() -> None:
    observation = build_pipe_observation(
        _pipe(leak_detected=True, pressure_anomaly_fraction=0.6)
    )

    assert observation.asset_type is InfrastructureAssetType.PIPE
    assert observation.leak_detected is True
    assert observation.pressure_anomaly_fraction == 0.6
    assert observation.health_state is AssetHealthState.CRITICAL


def test_noncritical_pipe_leak_is_degraded_not_critical() -> None:
    observation = build_pipe_observation(
        _pipe(leak_detected=True, critical_to_water_safety=False)
    )

    assert observation.health_state is AssetHealthState.DEGRADED


def test_pump_builder_maps_flow_anomaly_to_pressure_anomaly() -> None:
    observation = build_pump_observation(
        _pump(vibration_fraction=0.8, flow_anomaly_fraction=0.65)
    )

    assert observation.asset_type is InfrastructureAssetType.PUMP
    assert observation.vibration_fraction == 0.8
    assert observation.pressure_anomaly_fraction == 0.65
    assert observation.health_state is AssetHealthState.DEGRADED


def test_nonoperational_critical_pump_creates_critical_observation() -> None:
    observation = build_pump_observation(_pump(operational=False))

    assert observation.health_state is AssetHealthState.CRITICAL


@pytest.mark.parametrize(
    ("panel_kind", "expected_asset_type"),
    [
        (CollectionPanelKind.SOLAR_PANEL, InfrastructureAssetType.SOLAR_PANEL),
        (CollectionPanelKind.AWH_PANEL, InfrastructureAssetType.AWH_PANEL),
        (CollectionPanelKind.FOG_MESH_FRAME, InfrastructureAssetType.FOG_MESH_FRAME),
    ],
)
def test_panel_builder_maps_panel_kind_to_asset_type(
    panel_kind: CollectionPanelKind,
    expected_asset_type: InfrastructureAssetType,
) -> None:
    observation = build_panel_observation(_panel(panel_kind=panel_kind))

    assert observation.asset_type is expected_asset_type


def test_dirty_panel_raises_contamination_risk_and_degraded_state() -> None:
    observation = build_panel_observation(_panel(collection_surface_clean=False))

    assert observation.health_state is AssetHealthState.DEGRADED
    assert observation.contamination_pathway_risk_fraction == 0.70


def test_panel_fault_on_safety_critical_asset_creates_critical_observation() -> None:
    observation = build_panel_observation(
        _panel(
            electrical_or_collection_fault_detected=True,
            critical_to_water_safety=True,
        )
    )

    assert observation.health_state is AssetHealthState.CRITICAL


def test_asset_specific_observations_feed_infrastructure_gate() -> None:
    snapshot = InfrastructureSnapshot(
        observations=(
            build_tank_observation(_tank()),
            build_pipe_observation(_pipe()),
            build_pump_observation(_pump()),
            build_panel_observation(_panel()),
        )
    )

    result = evaluate_infrastructure_health(snapshot, evaluated_at=OBSERVED_AT)

    assert result.decision_status is DecisionStatus.ALLOW_REVIEW
    assert result.risk_level is RiskLevel.LOW
    assert result.infrastructure_ready is True
    assert result.normal_assets == ("tank-1", "pipe-1", "pump-1", "panel-1")


def test_asset_specific_critical_observation_blocks_infrastructure_gate() -> None:
    snapshot = InfrastructureSnapshot(
        observations=(
            build_tank_observation(_tank(leak_detected=True)),
            build_pipe_observation(_pipe()),
        )
    )

    result = evaluate_infrastructure_health(snapshot, evaluated_at=OBSERVED_AT)

    assert result.decision_status is DecisionStatus.BLOCK
    assert result.risk_level is RiskLevel.CRITICAL
    assert result.infrastructure_ready is False
    assert result.blocked_assets == ("tank-1",)


@pytest.mark.parametrize(
    ("input_factory", "field", "value", "expected_message"),
    [
        (_tank, "asset_id", " ", "asset_id"),
        (_tank, "label", " ", "label"),
        (_tank, "deformation_fraction", -0.1, "deformation_fraction"),
        (_pipe, "pressure_anomaly_fraction", 1.1, "pressure_anomaly_fraction"),
        (_pump, "flow_anomaly_fraction", -0.1, "flow_anomaly_fraction"),
        (_panel, "surface_contamination_fraction", 1.1, "surface_contamination_fraction"),
        (_panel, "notes", " ", "notes"),
    ],
)
def test_asset_inputs_reject_invalid_values(
    input_factory,
    field: str,
    value: object,
    expected_message: str,
) -> None:
    with pytest.raises(ValueError, match=expected_message):
        input_factory(**{field: value})
