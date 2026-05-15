"""Standalone water-quality evidence gate for IX-Vahdat.

This module evaluates whether the available water-quality evidence is complete,
fresh enough, internally usable, and within broad proof-of-concept bounds.

It does not certify drinking water. It produces a conservative gate result that
other modules can use before routing, reuse classification, storage, or review.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from ix_vahdat.domain import (
    DecisionStatus,
    EvidenceQuality,
    Measurement,
    RiskLevel,
    SensorStatus,
)
from ix_vahdat.water_use import WaterQualitySnapshot


@dataclass(frozen=True, slots=True)
class WaterQualityGatePolicy:
    """Configurable proof-of-concept bounds for water-quality evidence.

    These limits are not legal standards. They are conservative software-gate
    thresholds used to decide whether a batch can move to human review or must
    be held, blocked, or retested.
    """

    maximum_measurement_age: timedelta = timedelta(hours=6)

    ph_min: float = 5.0
    ph_max: float = 10.5
    turbidity_ntu_max: float = 100.0
    conductivity_us_cm_max: float = 5_000.0

    critical_turbidity_ntu: float = 250.0
    critical_conductivity_us_cm: float = 10_000.0

    require_pathogen_indicator_for_drinking_candidate: bool = True
    require_chemical_screen_for_drinking_candidate: bool = True


@dataclass(frozen=True, slots=True)
class WaterQualityGateResult:
    """Conservative water-quality evidence gate result."""

    decision_status: DecisionStatus
    risk_level: RiskLevel
    reasons: tuple[str, ...]
    required_actions: tuple[str, ...]

    @property
    def may_continue_to_classification(self) -> bool:
        """Return True when downstream candidate classification may continue."""

        return self.decision_status is DecisionStatus.ALLOW_REVIEW


def evaluate_water_quality_gate(
    snapshot: WaterQualitySnapshot,
    *,
    evaluated_at: datetime,
    policy: WaterQualityGatePolicy | None = None,
) -> WaterQualityGateResult:
    """Evaluate water-quality evidence before downstream classification.

    The gate blocks obvious high-risk evidence, holds missing/stale/invalid
    evidence for testing, and allows review only when core evidence is complete
    and within broad configured bounds.
    """

    if evaluated_at.tzinfo is None or evaluated_at.utcoffset() is None:
        raise ValueError("evaluated_at must be timezone-aware")

    active_policy = policy or WaterQualityGatePolicy()

    missing_reasons = _missing_core_measurements(snapshot)
    if missing_reasons:
        return WaterQualityGateResult(
            decision_status=DecisionStatus.HOLD_FOR_TESTING,
            risk_level=RiskLevel.HIGH,
            reasons=missing_reasons,
            required_actions=(
                "collect complete pH, turbidity, and conductivity measurements",
                "hold water batch until core evidence is complete",
                "repeat review after verified testing",
            ),
        )

    invalid_reasons = _invalid_measurement_reasons(snapshot)
    if invalid_reasons:
        return WaterQualityGateResult(
            decision_status=DecisionStatus.HOLD_FOR_TESTING,
            risk_level=RiskLevel.HIGH,
            reasons=invalid_reasons,
            required_actions=(
                "replace, inspect, or recalibrate suspect instruments",
                "repeat measurements with verified instruments",
                "hold water batch until evidence is reliable",
            ),
        )

    stale_reasons = _stale_measurement_reasons(snapshot, evaluated_at, active_policy)
    if stale_reasons:
        return WaterQualityGateResult(
            decision_status=DecisionStatus.HOLD_FOR_TESTING,
            risk_level=RiskLevel.HIGH,
            reasons=stale_reasons,
            required_actions=(
                "repeat stale measurements",
                "verify instrument calibration status",
                "hold water batch until fresh evidence is available",
            ),
        )

    if snapshot.e_coli_present is True:
        return WaterQualityGateResult(
            decision_status=DecisionStatus.BLOCK,
            risk_level=RiskLevel.CRITICAL,
            reasons=("pathogen indicator present",),
            required_actions=(
                "block release",
                "route to treatment or disposal review",
                "require qualified water-quality review",
            ),
        )

    if snapshot.chemical_screen_passed is False:
        return WaterQualityGateResult(
            decision_status=DecisionStatus.BLOCK,
            risk_level=RiskLevel.CRITICAL,
            reasons=("chemical screen failed",),
            required_actions=(
                "block release",
                "hold for qualified chemical analysis",
                "route to treatment or disposal review",
            ),
        )

    ph = _value(snapshot.ph)
    turbidity = _value(snapshot.turbidity_ntu)
    conductivity = _value(snapshot.conductivity_us_cm)

    critical_reasons = _critical_threshold_reasons(ph, turbidity, conductivity, active_policy)
    if critical_reasons:
        return WaterQualityGateResult(
            decision_status=DecisionStatus.BLOCK,
            risk_level=RiskLevel.CRITICAL,
            reasons=critical_reasons,
            required_actions=(
                "block use",
                "isolate batch from public or field use",
                "escalate to qualified water-quality review",
            ),
        )

    broad_limit_reasons = _broad_limit_reasons(ph, turbidity, conductivity, active_policy)
    if broad_limit_reasons:
        return WaterQualityGateResult(
            decision_status=DecisionStatus.HOLD_FOR_TESTING,
            risk_level=RiskLevel.HIGH,
            reasons=broad_limit_reasons,
            required_actions=(
                "hold water batch",
                "repeat testing and evaluate treatment route",
                "do not classify as usable without qualified review",
            ),
        )

    caution_reasons: list[str] = ["core water-quality evidence is complete and within broad bounds"]
    required_actions: list[str] = [
        "continue only to conservative candidate classification",
        "preserve evidence bundle",
        "human review required before any field use",
    ]

    if (
        active_policy.require_pathogen_indicator_for_drinking_candidate
        and snapshot.e_coli_present is None
    ):
        caution_reasons.append("pathogen indicator evidence missing")
        required_actions.append("do not classify as drinking candidate without pathogen evidence")

    if (
        active_policy.require_chemical_screen_for_drinking_candidate
        and snapshot.chemical_screen_passed is None
    ):
        caution_reasons.append("chemical screen evidence missing")
        required_actions.append("do not classify as drinking candidate without chemical screen evidence")

    if not snapshot.disinfection_verified:
        caution_reasons.append("disinfection evidence missing or unverified")
        required_actions.append("do not classify as drinking candidate without disinfection evidence")

    risk_level = RiskLevel.MODERATE if len(caution_reasons) > 1 else RiskLevel.LOW

    return WaterQualityGateResult(
        decision_status=DecisionStatus.ALLOW_REVIEW,
        risk_level=risk_level,
        reasons=tuple(caution_reasons),
        required_actions=tuple(required_actions),
    )


def _missing_core_measurements(snapshot: WaterQualitySnapshot) -> tuple[str, ...]:
    reasons: list[str] = []
    if snapshot.ph is None:
        reasons.append("missing pH measurement")
    if snapshot.turbidity_ntu is None:
        reasons.append("missing turbidity measurement")
    if snapshot.conductivity_us_cm is None:
        reasons.append("missing conductivity measurement")
    return tuple(reasons)


def _invalid_measurement_reasons(snapshot: WaterQualitySnapshot) -> tuple[str, ...]:
    reasons: list[str] = []
    for measurement in snapshot.physical_measurements():
        if measurement is None:
            continue
        if measurement.quality in {
            EvidenceQuality.MISSING,
            EvidenceQuality.CONFLICTING,
        }:
            reasons.append(f"{measurement.name} evidence quality is {measurement.quality.value}")
        if measurement.sensor_status in {
            SensorStatus.STALE,
            SensorStatus.FAILED,
            SensorStatus.UNVERIFIED,
        }:
            reasons.append(f"{measurement.name} sensor status is {measurement.sensor_status.value}")
    return tuple(reasons)


def _stale_measurement_reasons(
    snapshot: WaterQualitySnapshot,
    evaluated_at: datetime,
    policy: WaterQualityGatePolicy,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for measurement in snapshot.physical_measurements():
        if measurement is None:
            continue
        if measurement.timestamp > evaluated_at:
            reasons.append(f"{measurement.name} timestamp is later than evaluation time")
            continue
        age = evaluated_at - measurement.timestamp
        if age > policy.maximum_measurement_age:
            reasons.append(
                f"{measurement.name} measurement age exceeds maximum allowed age "
                f"of {policy.maximum_measurement_age}"
            )
    return tuple(reasons)


def _critical_threshold_reasons(
    ph: float,
    turbidity: float,
    conductivity: float,
    policy: WaterQualityGatePolicy,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if ph < policy.ph_min or ph > policy.ph_max:
        reasons.append("pH is outside broad safety-gate limits")
    if turbidity > policy.critical_turbidity_ntu:
        reasons.append("turbidity exceeds critical hold threshold")
    if conductivity > policy.critical_conductivity_us_cm:
        reasons.append("conductivity exceeds critical hold threshold")
    return tuple(reasons)


def _broad_limit_reasons(
    ph: float,
    turbidity: float,
    conductivity: float,
    policy: WaterQualityGatePolicy,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if ph < policy.ph_min or ph > policy.ph_max:
        reasons.append("pH is outside broad review bounds")
    if turbidity > policy.turbidity_ntu_max:
        reasons.append("turbidity exceeds broad review threshold")
    if conductivity > policy.conductivity_us_cm_max:
        reasons.append("conductivity exceeds broad review threshold")
    return tuple(reasons)


def _value(measurement: Measurement | None) -> float:
    if measurement is None:
        raise ValueError("measurement is required")
    return measurement.value
