"""Asset-specific health-check builders for IX-Vahdat.

This module converts tank, pipe, pump, solar-panel, atmospheric-water-panel,
and fog-mesh observations into the generic InfrastructureObservation model.

It does not certify structural safety or operate equipment. It prepares
normalized evidence for the infrastructure-health gate and qualified human
review.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from math import isfinite

from ix_vahdat.domain import EvidenceQuality, SensorStatus
from ix_vahdat.infrastructure import (
    AssetHealthState,
    InfrastructureAssetType,
    InfrastructureObservation,
)


class CollectionPanelKind(str, Enum):
    """Collection or energy-panel category for asset-specific checks."""

    SOLAR_PANEL = "solar_panel"
    AWH_PANEL = "awh_panel"
    FOG_MESH_FRAME = "fog_mesh_frame"


@dataclass(frozen=True, slots=True)
class TankHealthInput:
    """Observed health evidence for a water storage tank."""

    asset_id: str
    label: str
    observed_at: datetime
    evidence_quality: EvidenceQuality
    sensor_status: SensorStatus
    leak_detected: bool
    storage_clean: bool
    tank_integrity_verified: bool
    deformation_fraction: float = 0.0
    corrosion_fraction: float = 0.0
    contamination_pathway_risk_fraction: float = 0.0
    critical_to_water_safety: bool = True
    notes: str | None = None

    def __post_init__(self) -> None:
        _validate_common_asset_fields(
            asset_id=self.asset_id,
            label=self.label,
            observed_at=self.observed_at,
            notes=self.notes,
        )
        _require_fraction("deformation_fraction", self.deformation_fraction)
        _require_fraction("corrosion_fraction", self.corrosion_fraction)
        _require_fraction(
            "contamination_pathway_risk_fraction",
            self.contamination_pathway_risk_fraction,
        )


@dataclass(frozen=True, slots=True)
class PipeHealthInput:
    """Observed health evidence for a pipe or water line."""

    asset_id: str
    label: str
    observed_at: datetime
    evidence_quality: EvidenceQuality
    sensor_status: SensorStatus
    leak_detected: bool
    deformation_fraction: float = 0.0
    vibration_fraction: float = 0.0
    corrosion_fraction: float = 0.0
    pressure_anomaly_fraction: float = 0.0
    contamination_pathway_risk_fraction: float = 0.0
    critical_to_water_safety: bool = True
    notes: str | None = None

    def __post_init__(self) -> None:
        _validate_common_asset_fields(
            asset_id=self.asset_id,
            label=self.label,
            observed_at=self.observed_at,
            notes=self.notes,
        )
        _require_fraction("deformation_fraction", self.deformation_fraction)
        _require_fraction("vibration_fraction", self.vibration_fraction)
        _require_fraction("corrosion_fraction", self.corrosion_fraction)
        _require_fraction("pressure_anomaly_fraction", self.pressure_anomaly_fraction)
        _require_fraction(
            "contamination_pathway_risk_fraction",
            self.contamination_pathway_risk_fraction,
        )


@dataclass(frozen=True, slots=True)
class PumpHealthInput:
    """Observed health evidence for a pump and its local mounting."""

    asset_id: str
    label: str
    observed_at: datetime
    evidence_quality: EvidenceQuality
    sensor_status: SensorStatus
    operational: bool
    leak_detected: bool
    vibration_fraction: float = 0.0
    flow_anomaly_fraction: float = 0.0
    mount_deformation_fraction: float = 0.0
    corrosion_fraction: float = 0.0
    critical_to_water_safety: bool = True
    notes: str | None = None

    def __post_init__(self) -> None:
        _validate_common_asset_fields(
            asset_id=self.asset_id,
            label=self.label,
            observed_at=self.observed_at,
            notes=self.notes,
        )
        _require_fraction("vibration_fraction", self.vibration_fraction)
        _require_fraction("flow_anomaly_fraction", self.flow_anomaly_fraction)
        _require_fraction("mount_deformation_fraction", self.mount_deformation_fraction)
        _require_fraction("corrosion_fraction", self.corrosion_fraction)


@dataclass(frozen=True, slots=True)
class PanelHealthInput:
    """Observed health evidence for solar, AWH, or fog-mesh panel assets."""

    asset_id: str
    label: str
    panel_kind: CollectionPanelKind
    observed_at: datetime
    evidence_quality: EvidenceQuality
    sensor_status: SensorStatus
    mounted_securely: bool
    collection_surface_clean: bool
    electrical_or_collection_fault_detected: bool
    mount_deformation_fraction: float = 0.0
    surface_contamination_fraction: float = 0.0
    corrosion_fraction: float = 0.0
    vibration_fraction: float = 0.0
    critical_to_water_safety: bool = False
    notes: str | None = None

    def __post_init__(self) -> None:
        _validate_common_asset_fields(
            asset_id=self.asset_id,
            label=self.label,
            observed_at=self.observed_at,
            notes=self.notes,
        )
        _require_fraction("mount_deformation_fraction", self.mount_deformation_fraction)
        _require_fraction("surface_contamination_fraction", self.surface_contamination_fraction)
        _require_fraction("corrosion_fraction", self.corrosion_fraction)
        _require_fraction("vibration_fraction", self.vibration_fraction)


def build_tank_observation(input_data: TankHealthInput) -> InfrastructureObservation:
    """Build a normalized infrastructure observation for a storage tank."""

    contamination_risk = input_data.contamination_pathway_risk_fraction
    if not input_data.storage_clean:
        contamination_risk = max(contamination_risk, 0.75)

    health_state = _state_from_conditions(
        critical_flag=(
            input_data.leak_detected and input_data.critical_to_water_safety
        )
        or not input_data.tank_integrity_verified,
        degraded_flag=not input_data.storage_clean,
        condition_fractions=(
            input_data.deformation_fraction,
            input_data.corrosion_fraction,
            contamination_risk,
        ),
    )

    return InfrastructureObservation(
        asset_id=input_data.asset_id,
        label=input_data.label,
        asset_type=InfrastructureAssetType.STORAGE_TANK,
        health_state=health_state,
        observed_at=input_data.observed_at,
        evidence_quality=input_data.evidence_quality,
        sensor_status=input_data.sensor_status,
        leak_detected=input_data.leak_detected,
        deformation_fraction=input_data.deformation_fraction,
        vibration_fraction=0.0,
        corrosion_fraction=input_data.corrosion_fraction,
        pressure_anomaly_fraction=0.0,
        contamination_pathway_risk_fraction=contamination_risk,
        critical_to_water_safety=input_data.critical_to_water_safety,
        notes=input_data.notes,
    )


def build_pipe_observation(input_data: PipeHealthInput) -> InfrastructureObservation:
    """Build a normalized infrastructure observation for a pipe or line."""

    health_state = _state_from_conditions(
        critical_flag=input_data.leak_detected and input_data.critical_to_water_safety,
        degraded_flag=input_data.leak_detected,
        condition_fractions=(
            input_data.deformation_fraction,
            input_data.vibration_fraction,
            input_data.corrosion_fraction,
            input_data.pressure_anomaly_fraction,
            input_data.contamination_pathway_risk_fraction,
        ),
    )

    return InfrastructureObservation(
        asset_id=input_data.asset_id,
        label=input_data.label,
        asset_type=InfrastructureAssetType.PIPE,
        health_state=health_state,
        observed_at=input_data.observed_at,
        evidence_quality=input_data.evidence_quality,
        sensor_status=input_data.sensor_status,
        leak_detected=input_data.leak_detected,
        deformation_fraction=input_data.deformation_fraction,
        vibration_fraction=input_data.vibration_fraction,
        corrosion_fraction=input_data.corrosion_fraction,
        pressure_anomaly_fraction=input_data.pressure_anomaly_fraction,
        contamination_pathway_risk_fraction=input_data.contamination_pathway_risk_fraction,
        critical_to_water_safety=input_data.critical_to_water_safety,
        notes=input_data.notes,
    )


def build_pump_observation(input_data: PumpHealthInput) -> InfrastructureObservation:
    """Build a normalized infrastructure observation for a pump."""

    health_state = _state_from_conditions(
        critical_flag=not input_data.operational and input_data.critical_to_water_safety,
        degraded_flag=not input_data.operational or input_data.leak_detected,
        condition_fractions=(
            input_data.vibration_fraction,
            input_data.flow_anomaly_fraction,
            input_data.mount_deformation_fraction,
            input_data.corrosion_fraction,
        ),
    )

    return InfrastructureObservation(
        asset_id=input_data.asset_id,
        label=input_data.label,
        asset_type=InfrastructureAssetType.PUMP,
        health_state=health_state,
        observed_at=input_data.observed_at,
        evidence_quality=input_data.evidence_quality,
        sensor_status=input_data.sensor_status,
        leak_detected=input_data.leak_detected,
        deformation_fraction=input_data.mount_deformation_fraction,
        vibration_fraction=input_data.vibration_fraction,
        corrosion_fraction=input_data.corrosion_fraction,
        pressure_anomaly_fraction=input_data.flow_anomaly_fraction,
        contamination_pathway_risk_fraction=0.0,
        critical_to_water_safety=input_data.critical_to_water_safety,
        notes=input_data.notes,
    )


def build_panel_observation(input_data: PanelHealthInput) -> InfrastructureObservation:
    """Build a normalized infrastructure observation for a collection or energy panel."""

    contamination_risk = input_data.surface_contamination_fraction
    if not input_data.collection_surface_clean:
        contamination_risk = max(contamination_risk, 0.70)

    health_state = _state_from_conditions(
        critical_flag=(
            input_data.electrical_or_collection_fault_detected
            and input_data.critical_to_water_safety
        ),
        degraded_flag=(
            input_data.electrical_or_collection_fault_detected
            or not input_data.mounted_securely
            or not input_data.collection_surface_clean
        ),
        condition_fractions=(
            input_data.mount_deformation_fraction,
            contamination_risk,
            input_data.corrosion_fraction,
            input_data.vibration_fraction,
        ),
    )

    return InfrastructureObservation(
        asset_id=input_data.asset_id,
        label=input_data.label,
        asset_type=_panel_asset_type(input_data.panel_kind),
        health_state=health_state,
        observed_at=input_data.observed_at,
        evidence_quality=input_data.evidence_quality,
        sensor_status=input_data.sensor_status,
        leak_detected=False,
        deformation_fraction=input_data.mount_deformation_fraction,
        vibration_fraction=input_data.vibration_fraction,
        corrosion_fraction=input_data.corrosion_fraction,
        pressure_anomaly_fraction=0.0,
        contamination_pathway_risk_fraction=contamination_risk,
        critical_to_water_safety=input_data.critical_to_water_safety,
        notes=input_data.notes,
    )


def _panel_asset_type(panel_kind: CollectionPanelKind) -> InfrastructureAssetType:
    if panel_kind is CollectionPanelKind.SOLAR_PANEL:
        return InfrastructureAssetType.SOLAR_PANEL
    if panel_kind is CollectionPanelKind.AWH_PANEL:
        return InfrastructureAssetType.AWH_PANEL
    return InfrastructureAssetType.FOG_MESH_FRAME


def _state_from_conditions(
    *,
    critical_flag: bool,
    degraded_flag: bool,
    condition_fractions: tuple[float, ...],
) -> AssetHealthState:
    max_condition = max(condition_fractions) if condition_fractions else 0.0

    if critical_flag or max_condition >= 0.90:
        return AssetHealthState.CRITICAL
    if degraded_flag or max_condition >= 0.70:
        return AssetHealthState.DEGRADED
    if max_condition >= 0.50:
        return AssetHealthState.WATCH
    return AssetHealthState.NORMAL


def _validate_common_asset_fields(
    *,
    asset_id: str,
    label: str,
    observed_at: datetime,
    notes: str | None,
) -> None:
    if not asset_id.strip():
        raise ValueError("asset_id is required")
    if not label.strip():
        raise ValueError("label is required")
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("observed_at must be timezone-aware")
    if notes is not None and not notes.strip():
        raise ValueError("notes cannot be blank when provided")


def _require_fraction(name: str, value: float) -> None:
    if not isfinite(value):
        raise ValueError(f"{name} must be finite")
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1")
