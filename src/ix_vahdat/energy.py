"""Energy accounting for IX-Vahdat.

This module calculates energy-per-liter and energy-readiness evidence for
water-support operations such as pumping, treatment, filtration, UV, telemetry,
and atmospheric water harvesting.

It does not guarantee water yield, certify energy performance, size electrical
systems, or authorize field operation. It blocks or holds when measured energy
evidence is missing, implausible, or insufficient for safety-critical loads.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite

from ix_vahdat.domain import DecisionStatus, EvidenceQuality, RiskLevel


class EnergySource(str, Enum):
    """Energy source category used for evidence accounting."""

    GRID = "grid"
    SOLAR = "solar"
    BATTERY = "battery"
    GENERATOR = "generator"
    HYBRID = "hybrid"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class EnergySnapshot:
    """Measured or estimated energy state for a water-support operation."""

    source: EnergySource
    evidence_quality: EvidenceQuality
    runtime_hours: float
    average_power_w: float
    water_output_l: float
    critical_load_power_w: float
    available_power_w: float
    battery_state_fraction: float
    reserve_battery_fraction: float
    measurement_notes: str | None = None

    def __post_init__(self) -> None:
        _require_finite_nonnegative("runtime_hours", self.runtime_hours)
        _require_finite_nonnegative("average_power_w", self.average_power_w)
        _require_finite_nonnegative("water_output_l", self.water_output_l)
        _require_finite_nonnegative("critical_load_power_w", self.critical_load_power_w)
        _require_finite_nonnegative("available_power_w", self.available_power_w)

        if not 0.0 <= self.battery_state_fraction <= 1.0:
            raise ValueError("battery_state_fraction must be between 0 and 1")
        if not 0.0 <= self.reserve_battery_fraction <= 1.0:
            raise ValueError("reserve_battery_fraction must be between 0 and 1")
        if self.reserve_battery_fraction > self.battery_state_fraction:
            raise ValueError("reserve_battery_fraction cannot exceed battery_state_fraction")
        if self.measurement_notes is not None and not self.measurement_notes.strip():
            raise ValueError("measurement_notes cannot be blank when provided")

    @property
    def energy_input_wh(self) -> float:
        """Return gross measured/estimated energy input in watt-hours."""

        return self.average_power_w * self.runtime_hours

    @property
    def energy_per_liter_wh_l(self) -> float | None:
        """Return energy per liter, or None when no water output was measured."""

        if self.water_output_l <= 0.0:
            return None
        return self.energy_input_wh / self.water_output_l

    @property
    def has_power_margin_for_critical_loads(self) -> bool:
        """Return whether available power exceeds critical load demand."""

        return self.available_power_w >= self.critical_load_power_w

    @property
    def battery_reserve_is_protected(self) -> bool:
        """Return whether the declared reserve remains protected."""

        return self.battery_state_fraction >= self.reserve_battery_fraction


@dataclass(frozen=True, slots=True)
class EnergyAccountingPolicy:
    """Proof-of-concept thresholds for water-system energy truth.

    These values are review gates, not hardware specifications. They prevent
    unsupported water-yield claims from passing when energy evidence is absent,
    implausible, or too costly for the configured deployment class.
    """

    max_energy_per_liter_wh_l: float = 1_500.0
    max_awh_energy_per_liter_wh_l: float = 2_500.0
    min_runtime_hours_for_claim: float = 0.25
    min_water_output_l_for_claim: float = 0.1
    min_power_margin_w: float = 50.0
    min_battery_state_fraction: float = 0.20
    block_unknown_energy_source: bool = True

    def __post_init__(self) -> None:
        _require_positive("max_energy_per_liter_wh_l", self.max_energy_per_liter_wh_l)
        _require_positive("max_awh_energy_per_liter_wh_l", self.max_awh_energy_per_liter_wh_l)
        _require_positive("min_runtime_hours_for_claim", self.min_runtime_hours_for_claim)
        _require_positive("min_water_output_l_for_claim", self.min_water_output_l_for_claim)
        _require_finite_nonnegative("min_power_margin_w", self.min_power_margin_w)
        if not 0.0 <= self.min_battery_state_fraction <= 1.0:
            raise ValueError("min_battery_state_fraction must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class EnergyAccountingResult:
    """Decision-support result for energy truth accounting."""

    decision_status: DecisionStatus
    risk_level: RiskLevel
    energy_input_wh: float
    energy_per_liter_wh_l: float | None
    reasons: tuple[str, ...]
    required_actions: tuple[str, ...]

    @property
    def has_claim_support(self) -> bool:
        """Return True when energy evidence may continue to human review."""

        return self.decision_status is DecisionStatus.ALLOW_REVIEW


def calculate_energy_accounting(
    snapshot: EnergySnapshot,
    *,
    policy: EnergyAccountingPolicy | None = None,
    operation_label: str = "water-support operation",
    is_atmospheric_water_operation: bool = False,
) -> EnergyAccountingResult:
    """Evaluate energy evidence for a water-support operation.

    A passing result means the energy evidence may continue to human review.
    It does not prove that the water output is safe, sufficient, economical,
    locally compliant, or deployment-ready.
    """

    if not operation_label.strip():
        raise ValueError("operation_label is required")

    active_policy = policy or EnergyAccountingPolicy()
    reasons: list[str] = []
    required_actions: list[str] = []

    invalid_evidence_reasons = _invalid_evidence_reasons(snapshot, active_policy)
    if invalid_evidence_reasons:
        return EnergyAccountingResult(
            decision_status=DecisionStatus.HOLD_FOR_TESTING,
            risk_level=RiskLevel.HIGH,
            energy_input_wh=snapshot.energy_input_wh,
            energy_per_liter_wh_l=snapshot.energy_per_liter_wh_l,
            reasons=invalid_evidence_reasons,
            required_actions=(
                "collect measured energy and water-output evidence",
                "protect critical loads before continuing",
                "repeat energy accounting before making any output claim",
            ),
        )

    if active_policy.block_unknown_energy_source and snapshot.source is EnergySource.UNKNOWN:
        return EnergyAccountingResult(
            decision_status=DecisionStatus.HOLD_FOR_TESTING,
            risk_level=RiskLevel.HIGH,
            energy_input_wh=snapshot.energy_input_wh,
            energy_per_liter_wh_l=snapshot.energy_per_liter_wh_l,
            reasons=("energy source is unknown",),
            required_actions=(
                "identify energy source before review",
                "document energy boundary and measurement method",
                "do not claim water output without energy traceability",
            ),
        )

    if snapshot.water_output_l < active_policy.min_water_output_l_for_claim:
        return EnergyAccountingResult(
            decision_status=DecisionStatus.HOLD_FOR_TESTING,
            risk_level=RiskLevel.MODERATE,
            energy_input_wh=snapshot.energy_input_wh,
            energy_per_liter_wh_l=snapshot.energy_per_liter_wh_l,
            reasons=("water output is below minimum measurable claim threshold",),
            required_actions=(
                "run a longer or better-instrumented test",
                "do not claim production rate from this run",
                "preserve zero or low-output evidence",
            ),
        )

    energy_per_liter = snapshot.energy_per_liter_wh_l
    if energy_per_liter is None:
        return EnergyAccountingResult(
            decision_status=DecisionStatus.HOLD_FOR_TESTING,
            risk_level=RiskLevel.MODERATE,
            energy_input_wh=snapshot.energy_input_wh,
            energy_per_liter_wh_l=None,
            reasons=("energy per liter cannot be computed without measured water output",),
            required_actions=(
                "measure water output",
                "repeat energy accounting",
                "do not make efficiency claims",
            ),
        )

    limit = (
        active_policy.max_awh_energy_per_liter_wh_l
        if is_atmospheric_water_operation
        else active_policy.max_energy_per_liter_wh_l
    )
    if energy_per_liter > limit:
        return EnergyAccountingResult(
            decision_status=DecisionStatus.HOLD_FOR_TESTING,
            risk_level=RiskLevel.HIGH,
            energy_input_wh=snapshot.energy_input_wh,
            energy_per_liter_wh_l=energy_per_liter,
            reasons=(
                f"{operation_label} energy per liter exceeds configured review threshold",
            ),
            required_actions=(
                "do not scale this configuration without redesign",
                "inspect losses, runtime, power draw, and measured water output",
                "compare against lower-energy water options before procurement",
            ),
        )

    reasons.append(f"{operation_label} energy evidence is within configured review threshold")
    required_actions.extend(
        (
            "preserve measured energy boundary and water-output evidence",
            "repeat test under representative local conditions",
            "human review required before performance or deployment claims",
        )
    )

    if snapshot.evidence_quality is EvidenceQuality.ESTIMATED:
        reasons.append("energy evidence is estimated rather than directly measured")
        required_actions.append("replace estimate with measured evidence before procurement")

    risk_level = RiskLevel.MODERATE if snapshot.evidence_quality is EvidenceQuality.ESTIMATED else RiskLevel.LOW

    return EnergyAccountingResult(
        decision_status=DecisionStatus.ALLOW_REVIEW,
        risk_level=risk_level,
        energy_input_wh=snapshot.energy_input_wh,
        energy_per_liter_wh_l=energy_per_liter,
        reasons=tuple(reasons),
        required_actions=tuple(required_actions),
    )


def _invalid_evidence_reasons(
    snapshot: EnergySnapshot,
    policy: EnergyAccountingPolicy,
) -> tuple[str, ...]:
    reasons: list[str] = []

    if snapshot.evidence_quality in {EvidenceQuality.MISSING, EvidenceQuality.CONFLICTING}:
        reasons.append(f"energy evidence quality is {snapshot.evidence_quality.value}")
    if snapshot.runtime_hours < policy.min_runtime_hours_for_claim:
        reasons.append("runtime is below minimum duration for a water-output claim")
    if not snapshot.has_power_margin_for_critical_loads:
        reasons.append("available power is below critical load demand")
    elif snapshot.available_power_w - snapshot.critical_load_power_w < policy.min_power_margin_w:
        reasons.append("power margin above critical loads is below configured minimum")
    if snapshot.battery_state_fraction < policy.min_battery_state_fraction:
        reasons.append("battery state is below configured minimum")
    if not snapshot.battery_reserve_is_protected:
        reasons.append("battery reserve is not protected")

    return tuple(reasons)


def _require_finite_nonnegative(name: str, value: float) -> None:
    if not isfinite(value):
        raise ValueError(f"{name} must be finite")
    if value < 0.0:
        raise ValueError(f"{name} cannot be negative")


def _require_positive(name: str, value: float) -> None:
    if not isfinite(value):
        raise ValueError(f"{name} must be finite")
    if value <= 0.0:
        raise ValueError(f"{name} must be positive")
