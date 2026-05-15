"""Infrastructure-health monitoring for IX-Vahdat.

This module evaluates physical asset health for water-resilience nodes:
pipes, tanks, pumps, mounts, panels, channels, valves, skids, and storage
structures. It is intended to surface evidence-backed hold/block conditions
before physical failures contaminate, interrupt, or misroute water.

It does not certify structural safety, replace licensed inspection, or operate
hardware. It produces conservative decision-support output for human review.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from math import isfinite

from ix_vahdat.domain import DecisionStatus, EvidenceQuality, RiskLevel, SensorStatus


class InfrastructureAssetType(str, Enum):
    """Physical asset type monitored by IX-Vahdat."""

    PIPE = "pipe"
    STORAGE_TANK = "storage_tank"
    PUMP = "pump"
    VALVE = "valve"
    FILTER_SKID = "filter_skid"
    SOLAR_PANEL = "solar_panel"
    AWH_PANEL = "awh_panel"
    FOG_MESH_FRAME = "fog_mesh_frame"
    STRUCTURAL_MOUNT = "structural_mount"
    CHANNEL_OR_DRAIN = "channel_or_drain"
    SENSOR_MAST = "sensor_mast"
    OTHER = "other"


class AssetHealthState(str, Enum):
    """Conservative health state for a physical asset."""

    NORMAL = "normal"
    WATCH = "watch"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNVERIFIED = "unverified"


@dataclass(frozen=True, slots=True)
class InfrastructureObservation:
    """Health observation for one physical asset.

    The numeric fields are normalized proof-of-concept indicators. They should
    be derived from inspection, sensors, or qualified site observations.
    """

    asset_id: str
    label: str
    asset_type: InfrastructureAssetType
    health_state: AssetHealthState
    observed_at: datetime
    evidence_quality: EvidenceQuality
    sensor_status: SensorStatus
    leak_detected: bool = False
    deformation_fraction: float = 0.0
    vibration_fraction: float = 0.0
    corrosion_fraction: float = 0.0
    pressure_anomaly_fraction: float = 0.0
    contamination_pathway_risk_fraction: float = 0.0
    critical_to_water_safety: bool = False
    notes: str | None = None

    def __post_init__(self) -> None:
        if not self.asset_id.strip():
            raise ValueError("asset_id is required")
        if not self.label.strip():
            raise ValueError("label is required")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")

        _require_fraction("deformation_fraction", self.deformation_fraction)
        _require_fraction("vibration_fraction", self.vibration_fraction)
        _require_fraction("corrosion_fraction", self.corrosion_fraction)
        _require_fraction("pressure_anomaly_fraction", self.pressure_anomaly_fraction)
        _require_fraction(
            "contamination_pathway_risk_fraction",
            self.contamination_pathway_risk_fraction,
        )

        if self.notes is not None and not self.notes.strip():
            raise ValueError("notes cannot be blank when provided")

    @property
    def max_condition_fraction(self) -> float:
        """Return the highest normalized condition indicator."""

        return max(
            self.deformation_fraction,
            self.vibration_fraction,
            self.corrosion_fraction,
            self.pressure_anomaly_fraction,
            self.contamination_pathway_risk_fraction,
        )

    @property
    def evidence_is_reliable(self) -> bool:
        """Return whether health evidence can be used for review."""

        return (
            self.evidence_quality
            not in {
                EvidenceQuality.MISSING,
                EvidenceQuality.CONFLICTING,
            }
            and self.sensor_status
            not in {
                SensorStatus.STALE,
                SensorStatus.FAILED,
                SensorStatus.UNVERIFIED,
            }
        )


@dataclass(frozen=True, slots=True)
class InfrastructureSnapshot:
    """Infrastructure observations for a water-resilience node."""

    observations: tuple[InfrastructureObservation, ...]

    def __post_init__(self) -> None:
        if not self.observations:
            raise ValueError("at least one infrastructure observation is required")

        asset_ids = [observation.asset_id for observation in self.observations]
        if len(asset_ids) != len(set(asset_ids)):
            raise ValueError("asset_id values must be unique")


@dataclass(frozen=True, slots=True)
class InfrastructureHealthPolicy:
    """Proof-of-concept thresholds for asset-health review."""

    maximum_observation_age: timedelta = timedelta(hours=24)
    watch_fraction: float = 0.50
    degraded_fraction: float = 0.70
    critical_fraction: float = 0.90
    block_leak_on_safety_critical_asset: bool = True
    block_critical_health_state: bool = True

    def __post_init__(self) -> None:
        if self.maximum_observation_age <= timedelta(0):
            raise ValueError("maximum_observation_age must be positive")
        _require_fraction("watch_fraction", self.watch_fraction)
        _require_fraction("degraded_fraction", self.degraded_fraction)
        _require_fraction("critical_fraction", self.critical_fraction)
        if not self.watch_fraction <= self.degraded_fraction <= self.critical_fraction:
            raise ValueError(
                "watch_fraction must be <= degraded_fraction <= critical_fraction"
            )


@dataclass(frozen=True, slots=True)
class InfrastructureHealthResult:
    """Decision-support output for infrastructure-health review."""

    decision_status: DecisionStatus
    risk_level: RiskLevel
    normal_assets: tuple[str, ...]
    watch_assets: tuple[str, ...]
    blocked_assets: tuple[str, ...]
    reasons: tuple[str, ...]
    required_actions: tuple[str, ...]

    @property
    def infrastructure_ready(self) -> bool:
        """Return True only when no asset-health blockers remain."""

        return self.decision_status is DecisionStatus.ALLOW_REVIEW and not self.blocked_assets


def evaluate_infrastructure_health(
    snapshot: InfrastructureSnapshot,
    *,
    evaluated_at: datetime,
    policy: InfrastructureHealthPolicy | None = None,
) -> InfrastructureHealthResult:
    """Evaluate infrastructure health for water-node decision support."""

    if evaluated_at.tzinfo is None or evaluated_at.utcoffset() is None:
        raise ValueError("evaluated_at must be timezone-aware")

    active_policy = policy or InfrastructureHealthPolicy()

    normal_assets: list[str] = []
    watch_assets: list[str] = []
    blocked_assets: list[str] = []
    reasons: list[str] = []
    required_actions: list[str] = []

    for observation in snapshot.observations:
        observation_reasons = _observation_blockers(
            observation,
            evaluated_at,
            active_policy,
        )
        if observation_reasons:
            blocked_assets.append(observation.asset_id)
            reasons.extend(observation_reasons)
            required_actions.extend(_required_actions_for_blocker(observation))
            continue

        watch_reason = _observation_watch_reason(observation, active_policy)
        if watch_reason:
            watch_assets.append(observation.asset_id)
            reasons.append(watch_reason)
            required_actions.append(f"schedule qualified inspection for {observation.label}")
            continue

        normal_assets.append(observation.asset_id)

    if blocked_assets:
        risk = _blocked_risk(snapshot, tuple(blocked_assets))
        decision_status = DecisionStatus.BLOCK if risk is RiskLevel.CRITICAL else DecisionStatus.HOLD_FOR_TESTING
        return InfrastructureHealthResult(
            decision_status=decision_status,
            risk_level=risk,
            normal_assets=tuple(normal_assets),
            watch_assets=tuple(watch_assets),
            blocked_assets=tuple(_dedupe(blocked_assets)),
            reasons=tuple(_dedupe(reasons)),
            required_actions=tuple(
                _dedupe(
                    required_actions
                    + [
                        "hold dependent water-support decision until asset health is resolved",
                        "preserve infrastructure-health evidence for human review",
                    ]
                )
            ),
        )

    if watch_assets:
        return InfrastructureHealthResult(
            decision_status=DecisionStatus.ALLOW_REVIEW,
            risk_level=RiskLevel.MODERATE,
            normal_assets=tuple(normal_assets),
            watch_assets=tuple(watch_assets),
            blocked_assets=(),
            reasons=tuple(_dedupe(reasons)),
            required_actions=tuple(
                _dedupe(
                    required_actions
                    + [
                        "continue only with human review",
                        "monitor watch assets for escalation",
                    ]
                )
            ),
        )

    return InfrastructureHealthResult(
        decision_status=DecisionStatus.ALLOW_REVIEW,
        risk_level=RiskLevel.LOW,
        normal_assets=tuple(normal_assets),
        watch_assets=(),
        blocked_assets=(),
        reasons=("infrastructure-health evidence is reviewable and no blockers were found",),
        required_actions=(
            "continue infrastructure monitoring",
            "preserve asset-health evidence for review",
            "human review required before deployment or water-use claims",
        ),
    )


def _observation_blockers(
    observation: InfrastructureObservation,
    evaluated_at: datetime,
    policy: InfrastructureHealthPolicy,
) -> tuple[str, ...]:
    reasons: list[str] = []

    if observation.observed_at > evaluated_at:
        reasons.append(f"{observation.label} observation timestamp is later than evaluation time")
    elif evaluated_at - observation.observed_at > policy.maximum_observation_age:
        reasons.append(f"{observation.label} observation is older than maximum allowed age")

    if not observation.evidence_is_reliable:
        if observation.evidence_quality in {
            EvidenceQuality.MISSING,
            EvidenceQuality.CONFLICTING,
        }:
            reasons.append(
                f"{observation.label} evidence quality is {observation.evidence_quality.value}"
            )
        if observation.sensor_status in {
            SensorStatus.STALE,
            SensorStatus.FAILED,
            SensorStatus.UNVERIFIED,
        }:
            reasons.append(f"{observation.label} sensor status is {observation.sensor_status.value}")

    if (
        observation.leak_detected
        and observation.critical_to_water_safety
        and policy.block_leak_on_safety_critical_asset
    ):
        reasons.append(f"{observation.label} leak detected on safety-critical asset")

    if observation.health_state is AssetHealthState.UNVERIFIED:
        reasons.append(f"{observation.label} health state is unverified")

    if observation.health_state is AssetHealthState.CRITICAL and policy.block_critical_health_state:
        reasons.append(f"{observation.label} health state is critical")

    if observation.max_condition_fraction >= policy.critical_fraction:
        reasons.append(f"{observation.label} condition indicator exceeds critical threshold")

    return tuple(reasons)


def _observation_watch_reason(
    observation: InfrastructureObservation,
    policy: InfrastructureHealthPolicy,
) -> str | None:
    if observation.health_state is AssetHealthState.WATCH:
        return f"{observation.label} health state is watch"

    if observation.health_state is AssetHealthState.DEGRADED:
        return f"{observation.label} health state is degraded"

    if observation.leak_detected:
        return f"{observation.label} leak detected"

    if observation.max_condition_fraction >= policy.degraded_fraction:
        return f"{observation.label} condition indicator exceeds degraded threshold"

    if observation.max_condition_fraction >= policy.watch_fraction:
        return f"{observation.label} condition indicator exceeds watch threshold"

    return None


def _required_actions_for_blocker(
    observation: InfrastructureObservation,
) -> tuple[str, ...]:
    actions = [f"inspect {observation.label} before relying on this asset"]

    if observation.asset_type is InfrastructureAssetType.PIPE:
        actions.append("isolate or pressure-test pipe before routing review")
    elif observation.asset_type is InfrastructureAssetType.STORAGE_TANK:
        actions.append("inspect tank integrity and cleanliness before release review")
    elif observation.asset_type is InfrastructureAssetType.PUMP:
        actions.append("inspect pump mounts, vibration, and flow evidence")
    elif observation.asset_type is InfrastructureAssetType.VALVE:
        actions.append("verify valve position and leak state before routing review")
    elif observation.asset_type is InfrastructureAssetType.FILTER_SKID:
        actions.append("inspect skid frame, connections, pressure, and bypass risk")
    elif observation.asset_type is InfrastructureAssetType.SOLAR_PANEL:
        actions.append("inspect panel mount and electrical safety before energy review")
    elif observation.asset_type is InfrastructureAssetType.AWH_PANEL:
        actions.append("inspect panel mount, collection surfaces, and condensate path")
    elif observation.asset_type is InfrastructureAssetType.FOG_MESH_FRAME:
        actions.append("inspect mesh frame, anchoring, and contamination pathway")
    elif observation.asset_type is InfrastructureAssetType.STRUCTURAL_MOUNT:
        actions.append("inspect mounting hardware before operating attached equipment")
    elif observation.asset_type is InfrastructureAssetType.CHANNEL_OR_DRAIN:
        actions.append("inspect blockage, erosion, leakage, and contamination pathway")
    elif observation.asset_type is InfrastructureAssetType.SENSOR_MAST:
        actions.append("inspect sensor mast alignment, mounting, and communications path")

    if observation.critical_to_water_safety:
        actions.append("safety-critical asset blocks dependent water-support decisions")

    return tuple(actions)


def _blocked_risk(
    snapshot: InfrastructureSnapshot,
    blocked_assets: tuple[str, ...],
) -> RiskLevel:
    by_id = {observation.asset_id: observation for observation in snapshot.observations}

    for asset_id in blocked_assets:
        observation = by_id[asset_id]
        if observation.critical_to_water_safety:
            if (
                observation.health_state is AssetHealthState.CRITICAL
                or observation.leak_detected
                or observation.max_condition_fraction >= 0.90
            ):
                return RiskLevel.CRITICAL

    if any(by_id[asset_id].critical_to_water_safety for asset_id in blocked_assets):
        return RiskLevel.HIGH

    return RiskLevel.MODERATE


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        cleaned.append(value)
    return cleaned


def _require_fraction(name: str, value: float) -> None:
    if not isfinite(value):
        raise ValueError(f"{name} must be finite")
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1")
