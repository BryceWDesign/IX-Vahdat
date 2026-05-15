"""Power-priority state machine for IX-Vahdat.

A humanitarian water node should protect safety-critical sensing, evidence
logging, water-quality review, and communications before running optional
loads such as active atmospheric condensation, convenience pumps, or auxiliary
comfort systems.

This module does not operate relays, breakers, pumps, UV systems, batteries,
inverters, generators, or charge controllers. It produces conservative
decision-support output for human review and local engineering implementation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite

from ix_vahdat.domain import DecisionStatus, RiskLevel


class LoadPriority(str, Enum):
    """Priority class for a water-node electrical load."""

    CRITICAL = "critical"
    IMPORTANT = "important"
    DEFERRABLE = "deferrable"
    NONESSENTIAL = "nonessential"


class PowerMode(str, Enum):
    """Recommended power posture for a water node."""

    NORMAL = "normal"
    CONSERVE = "conserve"
    EMERGENCY = "emergency"
    SAFE_HOLD = "safe_hold"
    SERVICE_REQUIRED = "service_required"


@dataclass(frozen=True, slots=True)
class PowerLoad:
    """One load in the water-node power budget."""

    name: str
    priority: LoadPriority
    power_w: float
    enabled: bool = True
    required_for_safe_hold: bool = False
    notes: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("load name is required")
        _require_nonnegative_finite("power_w", self.power_w)
        if self.required_for_safe_hold and self.priority is not LoadPriority.CRITICAL:
            raise ValueError("safe-hold loads must have critical priority")
        if self.notes is not None and not self.notes.strip():
            raise ValueError("load notes cannot be blank when provided")


@dataclass(frozen=True, slots=True)
class PowerSystemSnapshot:
    """Observed power state for an IX-Vahdat node."""

    available_power_w: float
    battery_state_fraction: float
    reserve_battery_fraction: float
    loads: tuple[PowerLoad, ...]

    def __post_init__(self) -> None:
        _require_nonnegative_finite("available_power_w", self.available_power_w)
        if not 0.0 <= self.battery_state_fraction <= 1.0:
            raise ValueError("battery_state_fraction must be between 0 and 1")
        if not 0.0 <= self.reserve_battery_fraction <= 1.0:
            raise ValueError("reserve_battery_fraction must be between 0 and 1")
        if self.reserve_battery_fraction > self.battery_state_fraction:
            raise ValueError("reserve_battery_fraction cannot exceed battery_state_fraction")
        if not self.loads:
            raise ValueError("at least one power load is required")

    @property
    def enabled_loads(self) -> tuple[PowerLoad, ...]:
        """Return currently enabled loads."""

        return tuple(load for load in self.loads if load.enabled)

    @property
    def total_enabled_load_w(self) -> float:
        """Return total power draw for enabled loads."""

        return sum(load.power_w for load in self.enabled_loads)

    @property
    def critical_enabled_load_w(self) -> float:
        """Return enabled critical load demand."""

        return sum(load.power_w for load in self.enabled_loads if load.priority is LoadPriority.CRITICAL)

    @property
    def safe_hold_loads(self) -> tuple[PowerLoad, ...]:
        """Return loads required to preserve safe-hold state."""

        return tuple(load for load in self.enabled_loads if load.required_for_safe_hold)

    @property
    def safe_hold_load_w(self) -> float:
        """Return power required by safe-hold loads."""

        return sum(load.power_w for load in self.safe_hold_loads)

    @property
    def power_margin_w(self) -> float:
        """Return available power minus enabled load demand."""

        return self.available_power_w - self.total_enabled_load_w


@dataclass(frozen=True, slots=True)
class PowerPriorityPolicy:
    """Conservative proof-of-concept thresholds for power-state review."""

    min_power_margin_w: float = 50.0
    min_operating_battery_fraction: float = 0.30
    conserve_battery_fraction: float = 0.45
    emergency_battery_fraction: float = 0.25
    min_safe_hold_power_margin_w: float = 10.0

    def __post_init__(self) -> None:
        _require_nonnegative_finite("min_power_margin_w", self.min_power_margin_w)
        _require_nonnegative_finite(
            "min_safe_hold_power_margin_w",
            self.min_safe_hold_power_margin_w,
        )
        _require_fraction("min_operating_battery_fraction", self.min_operating_battery_fraction)
        _require_fraction("conserve_battery_fraction", self.conserve_battery_fraction)
        _require_fraction("emergency_battery_fraction", self.emergency_battery_fraction)

        if self.emergency_battery_fraction > self.conserve_battery_fraction:
            raise ValueError("emergency_battery_fraction cannot exceed conserve_battery_fraction")
        if self.min_operating_battery_fraction > self.conserve_battery_fraction:
            raise ValueError("min_operating_battery_fraction cannot exceed conserve_battery_fraction")


@dataclass(frozen=True, slots=True)
class PowerPriorityResult:
    """Decision-support output for water-node power prioritization."""

    mode: PowerMode
    decision_status: DecisionStatus
    risk_level: RiskLevel
    allowed_loads: tuple[str, ...]
    shed_loads: tuple[str, ...]
    reasons: tuple[str, ...]
    required_actions: tuple[str, ...]

    @property
    def is_normal_operation(self) -> bool:
        """Return True only when no shedding or power hold is recommended."""

        return (
            self.mode is PowerMode.NORMAL
            and self.decision_status is DecisionStatus.ALLOW_REVIEW
            and not self.shed_loads
        )


def evaluate_power_priority(
    snapshot: PowerSystemSnapshot,
    *,
    policy: PowerPriorityPolicy | None = None,
) -> PowerPriorityResult:
    """Evaluate power posture and recommended load shedding.

    A normal result means the provided power evidence may continue to human
    review. It does not prove the electrical system is code-compliant,
    correctly wired, safely protected, or deployment-ready.
    """

    active_policy = policy or PowerPriorityPolicy()

    if not snapshot.safe_hold_loads:
        return PowerPriorityResult(
            mode=PowerMode.SERVICE_REQUIRED,
            decision_status=DecisionStatus.HOLD_FOR_TESTING,
            risk_level=RiskLevel.HIGH,
            allowed_loads=(),
            shed_loads=tuple(load.name for load in snapshot.enabled_loads),
            reasons=("no safe-hold critical load set is defined",),
            required_actions=(
                "define critical loads required for safe-hold state",
                "identify evidence logging, water-quality sensing, and minimum communications loads",
                "repeat power-priority review before operating optional loads",
            ),
        )

    if snapshot.available_power_w < (
        snapshot.safe_hold_load_w + active_policy.min_safe_hold_power_margin_w
    ):
        return PowerPriorityResult(
            mode=PowerMode.SAFE_HOLD,
            decision_status=DecisionStatus.HOLD_FOR_TESTING,
            risk_level=RiskLevel.CRITICAL,
            allowed_loads=tuple(load.name for load in snapshot.safe_hold_loads),
            shed_loads=tuple(load.name for load in snapshot.enabled_loads if not load.required_for_safe_hold),
            reasons=("available power cannot safely support the safe-hold load set",),
            required_actions=(
                "shed every non-safe-hold load",
                "restore power before treatment, pumping, harvesting, or distribution review",
                "preserve evidence if logging remains powered",
                "obtain qualified electrical review",
            ),
        )

    if snapshot.battery_state_fraction <= snapshot.reserve_battery_fraction:
        return PowerPriorityResult(
            mode=PowerMode.SAFE_HOLD,
            decision_status=DecisionStatus.HOLD_FOR_TESTING,
            risk_level=RiskLevel.CRITICAL,
            allowed_loads=tuple(load.name for load in snapshot.safe_hold_loads),
            shed_loads=tuple(load.name for load in snapshot.enabled_loads if not load.required_for_safe_hold),
            reasons=("battery state has reached the protected reserve boundary",),
            required_actions=(
                "protect emergency reserve",
                "shed every non-safe-hold load",
                "do not run active water-production or noncritical treatment loads",
                "restore charging source before continuing",
            ),
        )

    if snapshot.battery_state_fraction < active_policy.emergency_battery_fraction:
        allowed = _allowed_loads(snapshot, keep_priorities={LoadPriority.CRITICAL})
        shed = _shed_loads(snapshot, allowed)
        return PowerPriorityResult(
            mode=PowerMode.EMERGENCY,
            decision_status=DecisionStatus.HOLD_FOR_TESTING,
            risk_level=RiskLevel.HIGH,
            allowed_loads=tuple(load.name for load in allowed),
            shed_loads=tuple(load.name for load in shed),
            reasons=("battery state is below emergency threshold",),
            required_actions=(
                "run critical loads only",
                "hold active atmospheric water harvesting and optional pumping",
                "preserve telemetry and evidence logging if powered",
                "restore power before normal operation review",
            ),
        )

    if snapshot.battery_state_fraction < active_policy.conserve_battery_fraction:
        allowed = _allowed_loads(
            snapshot,
            keep_priorities={LoadPriority.CRITICAL, LoadPriority.IMPORTANT},
        )
        shed = _shed_loads(snapshot, allowed)
        return PowerPriorityResult(
            mode=PowerMode.CONSERVE,
            decision_status=DecisionStatus.ALLOW_REVIEW,
            risk_level=RiskLevel.MODERATE,
            allowed_loads=tuple(load.name for load in allowed),
            shed_loads=tuple(load.name for load in shed),
            reasons=("battery state is below conserve threshold",),
            required_actions=(
                "shed deferrable and nonessential loads",
                "delay active condensation, comfort loads, and nonurgent auxiliary loads",
                "continue only with human-reviewed priority loads",
            ),
        )

    if snapshot.total_enabled_load_w > snapshot.available_power_w:
        allowed = _fit_loads_with_priority(snapshot, active_policy)
        shed = _shed_loads(snapshot, allowed)
        return PowerPriorityResult(
            mode=PowerMode.CONSERVE,
            decision_status=DecisionStatus.HOLD_FOR_TESTING,
            risk_level=RiskLevel.HIGH,
            allowed_loads=tuple(load.name for load in allowed),
            shed_loads=tuple(load.name for load in shed),
            reasons=("enabled loads exceed available power",),
            required_actions=(
                "shed lower-priority loads until power margin is restored",
                "protect critical sensing, logging, and review functions",
                "repeat power-priority review before optional loads resume",
            ),
        )

    if snapshot.power_margin_w < active_policy.min_power_margin_w:
        allowed = _fit_loads_with_priority(snapshot, active_policy)
        shed = _shed_loads(snapshot, allowed)
        return PowerPriorityResult(
            mode=PowerMode.CONSERVE,
            decision_status=DecisionStatus.ALLOW_REVIEW,
            risk_level=RiskLevel.MODERATE,
            allowed_loads=tuple(load.name for load in allowed),
            shed_loads=tuple(load.name for load in shed),
            reasons=("power margin is below configured minimum",),
            required_actions=(
                "shed lower-priority loads or restore power margin",
                "avoid starting high-draw atmospheric water or pump loads",
                "repeat review after load state changes",
            ),
        )

    return PowerPriorityResult(
        mode=PowerMode.NORMAL,
        decision_status=DecisionStatus.ALLOW_REVIEW,
        risk_level=RiskLevel.LOW,
        allowed_loads=tuple(load.name for load in snapshot.enabled_loads),
        shed_loads=(),
        reasons=("available power, battery reserve, and load margin support normal review",),
        required_actions=(
            "continue monitoring power margin",
            "preserve energy evidence for review",
            "human review required before deployment or performance claims",
        ),
    )


def _allowed_loads(
    snapshot: PowerSystemSnapshot,
    *,
    keep_priorities: set[LoadPriority],
) -> tuple[PowerLoad, ...]:
    return tuple(load for load in snapshot.enabled_loads if load.priority in keep_priorities)


def _shed_loads(
    snapshot: PowerSystemSnapshot,
    allowed_loads: tuple[PowerLoad, ...],
) -> tuple[PowerLoad, ...]:
    allowed_names = {load.name for load in allowed_loads}
    return tuple(load for load in snapshot.enabled_loads if load.name not in allowed_names)


def _fit_loads_with_priority(
    snapshot: PowerSystemSnapshot,
    policy: PowerPriorityPolicy,
) -> tuple[PowerLoad, ...]:
    """Keep highest-priority loads while respecting the configured margin."""

    priority_order = {
        LoadPriority.CRITICAL: 0,
        LoadPriority.IMPORTANT: 1,
        LoadPriority.DEFERRABLE: 2,
        LoadPriority.NONESSENTIAL: 3,
    }
    ordered_loads = tuple(sorted(snapshot.enabled_loads, key=lambda load: priority_order[load.priority]))

    kept: list[PowerLoad] = []
    used_power_w = 0.0
    max_allowed_power_w = max(0.0, snapshot.available_power_w - policy.min_power_margin_w)

    for load in ordered_loads:
        if load.required_for_safe_hold:
            kept.append(load)
            used_power_w += load.power_w
            continue

        if used_power_w + load.power_w <= max_allowed_power_w:
            kept.append(load)
            used_power_w += load.power_w

    return tuple(kept)


def _require_nonnegative_finite(name: str, value: float) -> None:
    if not isfinite(value):
        raise ValueError(f"{name} must be finite")
    if value < 0.0:
        raise ValueError(f"{name} cannot be negative")


def _require_fraction(name: str, value: float) -> None:
    if not isfinite(value):
        raise ValueError(f"{name} must be finite")
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1")
