"""Maintenance readiness and blocker model for IX-Vahdat.

Maintenance is treated as a safety gate. Filters, UV systems, tanks, sensors,
pumps, batteries, sorbent cartridges, collection surfaces, and structural
mounts can all invalidate a water-support recommendation when they are failed,
overdue, unverified, dirty, stale, or missing evidence.

This module does not perform maintenance or certify equipment. It produces
decision-support output for qualified human review.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite

from ix_vahdat.domain import DecisionStatus, EvidenceQuality, RiskLevel, SensorStatus


class MaintenanceCategory(str, Enum):
    """Maintenance category for a water-node component."""

    FILTER = "filter"
    UV_DISINFECTION = "uv_disinfection"
    STORAGE_TANK = "storage_tank"
    WATER_QUALITY_SENSOR = "water_quality_sensor"
    PUMP = "pump"
    BATTERY = "battery"
    SOLAR_INPUT = "solar_input"
    FOG_MESH = "fog_mesh"
    SORBENT_CARTRIDGE = "sorbent_cartridge"
    STRUCTURAL_MOUNT = "structural_mount"
    COMMUNICATIONS = "communications"
    OTHER = "other"


class MaintenanceState(str, Enum):
    """Observed maintenance state for a component."""

    OK = "ok"
    DUE_SOON = "due_soon"
    OVERDUE = "overdue"
    FAILED = "failed"
    UNVERIFIED = "unverified"


@dataclass(frozen=True, slots=True)
class MaintenanceItem:
    """Maintenance evidence for one water-node component."""

    item_id: str
    label: str
    category: MaintenanceCategory
    state: MaintenanceState
    critical: bool
    evidence_quality: EvidenceQuality
    sensor_status: SensorStatus = SensorStatus.OK
    hours_since_service: float | None = None
    service_interval_hours: float | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        if not self.item_id.strip():
            raise ValueError("item_id is required")
        if not self.label.strip():
            raise ValueError("label is required")
        if self.hours_since_service is not None:
            _require_nonnegative_finite("hours_since_service", self.hours_since_service)
        if self.service_interval_hours is not None:
            _require_positive_finite("service_interval_hours", self.service_interval_hours)
        if self.notes is not None and not self.notes.strip():
            raise ValueError("notes cannot be blank when provided")

    @property
    def service_fraction_used(self) -> float | None:
        """Return fraction of configured service interval consumed."""

        if self.hours_since_service is None or self.service_interval_hours is None:
            return None
        return self.hours_since_service / self.service_interval_hours

    @property
    def is_due_by_hours(self) -> bool:
        """Return whether hours since service exceed service interval."""

        service_fraction = self.service_fraction_used
        return service_fraction is not None and service_fraction >= 1.0

    @property
    def is_due_soon_by_hours(self) -> bool:
        """Return whether hours since service are approaching interval."""

        service_fraction = self.service_fraction_used
        return service_fraction is not None and 0.8 <= service_fraction < 1.0


@dataclass(frozen=True, slots=True)
class MaintenanceSnapshot:
    """Maintenance evidence package for a water node."""

    items: tuple[MaintenanceItem, ...]

    def __post_init__(self) -> None:
        if not self.items:
            raise ValueError("at least one maintenance item is required")

        item_ids = [item.item_id for item in self.items]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("maintenance item_id values must be unique")


@dataclass(frozen=True, slots=True)
class MaintenancePolicy:
    """Proof-of-concept maintenance gate settings."""

    require_measured_or_estimated_evidence: bool = True
    due_soon_fraction: float = 0.80
    block_failed_critical_items: bool = True

    def __post_init__(self) -> None:
        if not 0.0 <= self.due_soon_fraction <= 1.0:
            raise ValueError("due_soon_fraction must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class MaintenanceResult:
    """Decision-support output for maintenance readiness."""

    decision_status: DecisionStatus
    risk_level: RiskLevel
    ready_items: tuple[str, ...]
    due_soon_items: tuple[str, ...]
    blocked_items: tuple[str, ...]
    reasons: tuple[str, ...]
    required_actions: tuple[str, ...]

    @property
    def maintenance_ready(self) -> bool:
        """Return True only when no maintenance blockers remain."""

        return self.decision_status is DecisionStatus.ALLOW_REVIEW and not self.blocked_items


def evaluate_maintenance(
    snapshot: MaintenanceSnapshot,
    *,
    policy: MaintenancePolicy | None = None,
) -> MaintenanceResult:
    """Evaluate maintenance readiness for a water node.

    A passing result means maintenance evidence may continue to broader human
    review. It does not certify that the node is safe, legal, clean, or ready
    for public use.
    """

    active_policy = policy or MaintenancePolicy()

    ready_items: list[str] = []
    due_soon_items: list[str] = []
    blocked_items: list[str] = []
    reasons: list[str] = []
    required_actions: list[str] = []

    for item in snapshot.items:
        item_reasons = _item_blockers(item, active_policy)
        if item_reasons:
            blocked_items.append(item.item_id)
            reasons.extend(item_reasons)
            required_actions.extend(_required_actions_for_blocker(item))
            continue

        due_reason = _item_due_soon_reason(item, active_policy)
        if due_reason:
            due_soon_items.append(item.item_id)
            reasons.append(due_reason)
            required_actions.append(f"schedule maintenance for {item.label}")
            continue

        ready_items.append(item.item_id)

    if blocked_items:
        highest_risk = _blocked_risk(snapshot, tuple(blocked_items), active_policy)
        decision_status = (
            DecisionStatus.BLOCK if highest_risk is RiskLevel.CRITICAL else DecisionStatus.HOLD_FOR_TESTING
        )
        return MaintenanceResult(
            decision_status=decision_status,
            risk_level=highest_risk,
            ready_items=tuple(ready_items),
            due_soon_items=tuple(due_soon_items),
            blocked_items=tuple(blocked_items),
            reasons=tuple(_dedupe(reasons)),
            required_actions=tuple(
                _dedupe(
                    required_actions
                    + [
                        "hold affected water-support decision until maintenance is resolved",
                        "preserve maintenance evidence for human review",
                    ]
                )
            ),
        )

    if due_soon_items:
        return MaintenanceResult(
            decision_status=DecisionStatus.ALLOW_REVIEW,
            risk_level=RiskLevel.MODERATE,
            ready_items=tuple(ready_items),
            due_soon_items=tuple(due_soon_items),
            blocked_items=(),
            reasons=tuple(_dedupe(reasons)),
            required_actions=tuple(
                _dedupe(
                    required_actions
                    + [
                        "continue only with human review",
                        "do not defer safety-critical maintenance beyond interval",
                    ]
                )
            ),
        )

    return MaintenanceResult(
        decision_status=DecisionStatus.ALLOW_REVIEW,
        risk_level=RiskLevel.LOW,
        ready_items=tuple(ready_items),
        due_soon_items=(),
        blocked_items=(),
        reasons=("maintenance evidence is reviewable and no blockers were found",),
        required_actions=(
            "continue monitoring maintenance intervals",
            "preserve maintenance evidence for review",
            "human review required before deployment or water-use claims",
        ),
    )


def _item_blockers(item: MaintenanceItem, policy: MaintenancePolicy) -> tuple[str, ...]:
    reasons: list[str] = []

    if policy.require_measured_or_estimated_evidence and item.evidence_quality in {
        EvidenceQuality.MISSING,
        EvidenceQuality.CONFLICTING,
    }:
        reasons.append(f"{item.label} evidence quality is {item.evidence_quality.value}")

    if item.sensor_status in {
        SensorStatus.STALE,
        SensorStatus.FAILED,
        SensorStatus.UNVERIFIED,
    }:
        reasons.append(f"{item.label} sensor status is {item.sensor_status.value}")

    if item.state is MaintenanceState.FAILED:
        reasons.append(f"{item.label} maintenance state is failed")

    if item.state is MaintenanceState.UNVERIFIED:
        reasons.append(f"{item.label} maintenance state is unverified")

    if item.state is MaintenanceState.OVERDUE:
        reasons.append(f"{item.label} maintenance state is overdue")

    if item.is_due_by_hours:
        reasons.append(f"{item.label} service interval is exceeded")

    return tuple(reasons)


def _item_due_soon_reason(
    item: MaintenanceItem,
    policy: MaintenancePolicy,
) -> str | None:
    if item.state is MaintenanceState.DUE_SOON:
        return f"{item.label} maintenance state is due soon"

    service_fraction = item.service_fraction_used
    if service_fraction is not None and policy.due_soon_fraction <= service_fraction < 1.0:
        return f"{item.label} service interval is approaching configured limit"

    return None


def _required_actions_for_blocker(item: MaintenanceItem) -> tuple[str, ...]:
    common = [f"service or inspect {item.label} before relying on this component"]

    if item.category is MaintenanceCategory.FILTER:
        common.append("replace or verify filter before treatment-routing review")
    elif item.category is MaintenanceCategory.UV_DISINFECTION:
        common.append("verify UV lamp, ballast, sleeve cleanliness, and runtime evidence")
    elif item.category is MaintenanceCategory.STORAGE_TANK:
        common.append("inspect tank cleanliness and integrity before release review")
    elif item.category is MaintenanceCategory.WATER_QUALITY_SENSOR:
        common.append("calibrate or replace water-quality sensor before classification")
    elif item.category is MaintenanceCategory.PUMP:
        common.append("inspect pump operation before routing or distribution review")
    elif item.category is MaintenanceCategory.BATTERY:
        common.append("restore battery readiness before critical-load review")
    elif item.category is MaintenanceCategory.SOLAR_INPUT:
        common.append("inspect solar input before energy-readiness review")
    elif item.category is MaintenanceCategory.FOG_MESH:
        common.append("clean or replace collection mesh before atmospheric-water review")
    elif item.category is MaintenanceCategory.SORBENT_CARTRIDGE:
        common.append("replace or verify sorbent cartridge before collection review")
    elif item.category is MaintenanceCategory.STRUCTURAL_MOUNT:
        common.append("inspect mounting hardware before field operation review")
    elif item.category is MaintenanceCategory.COMMUNICATIONS:
        common.append("restore communications or local logging before remote review")

    if item.critical:
        common.append("critical item blocks dependent water-support decisions")

    return tuple(common)


def _blocked_risk(
    snapshot: MaintenanceSnapshot,
    blocked_items: tuple[str, ...],
    policy: MaintenancePolicy,
) -> RiskLevel:
    by_id = {item.item_id: item for item in snapshot.items}

    for item_id in blocked_items:
        item = by_id[item_id]
        if item.critical and item.state is MaintenanceState.FAILED and policy.block_failed_critical_items:
            return RiskLevel.CRITICAL

    if any(by_id[item_id].critical for item_id in blocked_items):
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


def _require_nonnegative_finite(name: str, value: float) -> None:
    if not isfinite(value):
        raise ValueError(f"{name} must be finite")
    if value < 0.0:
        raise ValueError(f"{name} cannot be negative")


def _require_positive_finite(name: str, value: float) -> None:
    if not isfinite(value):
        raise ValueError(f"{name} must be finite")
    if value <= 0.0:
        raise ValueError(f"{name} must be positive")
