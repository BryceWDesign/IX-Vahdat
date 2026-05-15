"""Water-use classification for IX-Vahdat.

This module classifies water into conservative *candidate* use classes for
decision support. It does not certify water as potable, safe, compliant, or
approved for public distribution.

All classifications must be treated as review inputs for qualified local
operators, water-quality professionals, public-health authorities, and
licensed engineers where applicable.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ix_vahdat.domain import (
    DecisionStatus,
    EvidenceQuality,
    Measurement,
    RiskLevel,
    SensorStatus,
)


class WaterUseClass(str, Enum):
    """Conservative water-use classes used by IX-Vahdat."""

    DRINKING_CANDIDATE = "drinking_candidate"
    HYGIENE_CANDIDATE = "hygiene_candidate"
    IRRIGATION_CANDIDATE = "irrigation_candidate"
    UTILITY_WATER = "utility_water"
    UNSAFE_HOLD = "unsafe_hold"


@dataclass(frozen=True, slots=True)
class WaterUsePolicy:
    """Configurable non-certification thresholds for water-use triage.

    The default values are conservative proof-of-concept thresholds for
    software testing and field-review planning. They are not a substitute for
    local law, laboratory analysis, treatment design, or public-health approval.
    """

    drinking_ph_min: float = 6.5
    drinking_ph_max: float = 8.5
    drinking_turbidity_ntu_max: float = 1.0
    drinking_conductivity_us_cm_max: float = 1_000.0

    hygiene_ph_min: float = 6.0
    hygiene_ph_max: float = 9.0
    hygiene_turbidity_ntu_max: float = 10.0
    hygiene_conductivity_us_cm_max: float = 1_500.0

    irrigation_ph_min: float = 5.5
    irrigation_ph_max: float = 9.5
    irrigation_turbidity_ntu_max: float = 50.0
    irrigation_conductivity_us_cm_max: float = 3_000.0

    utility_ph_min: float = 5.0
    utility_ph_max: float = 10.5
    utility_conductivity_us_cm_max: float = 5_000.0


@dataclass(frozen=True, slots=True)
class WaterQualitySnapshot:
    """Water-quality evidence available for a single classification event."""

    ph: Measurement | None = None
    turbidity_ntu: Measurement | None = None
    conductivity_us_cm: Measurement | None = None
    temperature_c: Measurement | None = None
    e_coli_present: bool | None = None
    chemical_screen_passed: bool | None = None
    disinfection_verified: bool = False

    def physical_measurements(self) -> tuple[Measurement | None, ...]:
        """Return core physical measurements used by the classifier."""

        return (self.ph, self.turbidity_ntu, self.conductivity_us_cm)


@dataclass(frozen=True, slots=True)
class WaterUseAssessment:
    """Result of a conservative water-use classification."""

    use_class: WaterUseClass
    decision_status: DecisionStatus
    risk_level: RiskLevel
    reasons: tuple[str, ...]
    required_actions: tuple[str, ...]

    @property
    def requires_human_review(self) -> bool:
        """All non-blocked outputs are still review-only decision support."""

        return self.decision_status is DecisionStatus.ALLOW_REVIEW


def classify_water_use(
    snapshot: WaterQualitySnapshot,
    policy: WaterUsePolicy | None = None,
) -> WaterUseAssessment:
    """Classify a water sample into a conservative candidate use class.

    The classifier is intentionally cautious. It blocks or holds when evidence
    is missing, stale, conflicting, failed, or materially unsafe. A
    DRINKING_CANDIDATE result is still not a potable-water certification.
    """

    active_policy = policy or WaterUsePolicy()
    reasons: list[str] = []
    required_actions: list[str] = ["human review required before field use"]

    missing = _missing_core_measurements(snapshot)
    if missing:
        return WaterUseAssessment(
            use_class=WaterUseClass.UNSAFE_HOLD,
            decision_status=DecisionStatus.HOLD_FOR_TESTING,
            risk_level=RiskLevel.HIGH,
            reasons=tuple(f"missing required measurement: {name}" for name in missing),
            required_actions=(
                "collect complete pH, turbidity, and conductivity measurements",
                "hold water until testing is complete",
                "human review required before field use",
            ),
        )

    invalid_evidence = _invalid_evidence_reasons(snapshot)
    if invalid_evidence:
        return WaterUseAssessment(
            use_class=WaterUseClass.UNSAFE_HOLD,
            decision_status=DecisionStatus.HOLD_FOR_TESTING,
            risk_level=RiskLevel.HIGH,
            reasons=tuple(invalid_evidence),
            required_actions=(
                "replace or recalibrate suspect sensors",
                "repeat measurements with verified instruments",
                "hold water until evidence is reliable",
                "human review required before field use",
            ),
        )

    ph = _value(snapshot.ph)
    turbidity = _value(snapshot.turbidity_ntu)
    conductivity = _value(snapshot.conductivity_us_cm)

    if snapshot.e_coli_present is True:
        return WaterUseAssessment(
            use_class=WaterUseClass.UNSAFE_HOLD,
            decision_status=DecisionStatus.BLOCK,
            risk_level=RiskLevel.CRITICAL,
            reasons=("pathogen indicator present",),
            required_actions=(
                "block distribution",
                "route to treatment or disposal review",
                "require qualified water-quality review",
            ),
        )

    if snapshot.chemical_screen_passed is False:
        return WaterUseAssessment(
            use_class=WaterUseClass.UNSAFE_HOLD,
            decision_status=DecisionStatus.BLOCK,
            risk_level=RiskLevel.CRITICAL,
            reasons=("chemical screen failed",),
            required_actions=(
                "block distribution",
                "hold water for qualified chemical analysis",
                "route to treatment or disposal review",
            ),
        )

    if _is_drinking_candidate(snapshot, ph, turbidity, conductivity, active_policy):
        return WaterUseAssessment(
            use_class=WaterUseClass.DRINKING_CANDIDATE,
            decision_status=DecisionStatus.ALLOW_REVIEW,
            risk_level=RiskLevel.LOW,
            reasons=("core indicators are within drinking-candidate triage thresholds",),
            required_actions=(
                "confirm local public-health requirements",
                "verify treatment chain and storage hygiene",
                "document human reviewer approval before any drinking-water claim",
            ),
        )

    if _is_hygiene_candidate(snapshot, ph, turbidity, conductivity, active_policy):
        reasons.append("indicators support hygiene-candidate review only")
        if snapshot.e_coli_present is None:
            required_actions.append("pathogen evidence missing; do not classify as drinking candidate")
        if snapshot.chemical_screen_passed is None:
            required_actions.append("chemical screen missing; restrict to review-only non-drinking use")
        return WaterUseAssessment(
            use_class=WaterUseClass.HYGIENE_CANDIDATE,
            decision_status=DecisionStatus.ALLOW_REVIEW,
            risk_level=RiskLevel.MODERATE,
            reasons=tuple(reasons),
            required_actions=tuple(required_actions),
        )

    if _is_irrigation_candidate(ph, turbidity, conductivity, active_policy):
        reasons.append("indicators support irrigation-candidate review only")
        if snapshot.chemical_screen_passed is None:
            required_actions.append("chemical screen missing; confirm crop and soil compatibility")
        return WaterUseAssessment(
            use_class=WaterUseClass.IRRIGATION_CANDIDATE,
            decision_status=DecisionStatus.ALLOW_REVIEW,
            risk_level=RiskLevel.MODERATE,
            reasons=tuple(reasons),
            required_actions=tuple(required_actions),
        )

    if _is_utility_water(ph, conductivity, active_policy):
        return WaterUseAssessment(
            use_class=WaterUseClass.UTILITY_WATER,
            decision_status=DecisionStatus.ALLOW_REVIEW,
            risk_level=RiskLevel.HIGH,
            reasons=("water only meets broad utility-water triage limits",),
            required_actions=(
                "restrict to non-contact utility review",
                "do not use for drinking, hygiene, or food-crop irrigation",
                "human review required before field use",
            ),
        )

    return WaterUseAssessment(
        use_class=WaterUseClass.UNSAFE_HOLD,
        decision_status=DecisionStatus.BLOCK,
        risk_level=RiskLevel.HIGH,
        reasons=("water-quality indicators exceed all configured use-class limits",),
        required_actions=(
            "block use",
            "hold for treatment, disposal review, or qualified laboratory testing",
        ),
    )


def _missing_core_measurements(snapshot: WaterQualitySnapshot) -> tuple[str, ...]:
    missing: list[str] = []
    if snapshot.ph is None:
        missing.append("pH")
    if snapshot.turbidity_ntu is None:
        missing.append("turbidity_ntu")
    if snapshot.conductivity_us_cm is None:
        missing.append("conductivity_us_cm")
    return tuple(missing)


def _invalid_evidence_reasons(snapshot: WaterQualitySnapshot) -> tuple[str, ...]:
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


def _is_drinking_candidate(
    snapshot: WaterQualitySnapshot,
    ph: float,
    turbidity: float,
    conductivity: float,
    policy: WaterUsePolicy,
) -> bool:
    return (
        policy.drinking_ph_min <= ph <= policy.drinking_ph_max
        and turbidity <= policy.drinking_turbidity_ntu_max
        and conductivity <= policy.drinking_conductivity_us_cm_max
        and snapshot.e_coli_present is False
        and snapshot.chemical_screen_passed is True
        and snapshot.disinfection_verified
    )


def _is_hygiene_candidate(
    snapshot: WaterQualitySnapshot,
    ph: float,
    turbidity: float,
    conductivity: float,
    policy: WaterUsePolicy,
) -> bool:
    return (
        policy.hygiene_ph_min <= ph <= policy.hygiene_ph_max
        and turbidity <= policy.hygiene_turbidity_ntu_max
        and conductivity <= policy.hygiene_conductivity_us_cm_max
        and snapshot.e_coli_present is not True
        and snapshot.chemical_screen_passed is not False
    )


def _is_irrigation_candidate(
    ph: float,
    turbidity: float,
    conductivity: float,
    policy: WaterUsePolicy,
) -> bool:
    return (
        policy.irrigation_ph_min <= ph <= policy.irrigation_ph_max
        and turbidity <= policy.irrigation_turbidity_ntu_max
        and conductivity <= policy.irrigation_conductivity_us_cm_max
    )


def _is_utility_water(ph: float, conductivity: float, policy: WaterUsePolicy) -> bool:
    return (
        policy.utility_ph_min <= ph <= policy.utility_ph_max
        and conductivity <= policy.utility_conductivity_us_cm_max
    )


def _value(measurement: Measurement | None) -> float:
    if measurement is None:
        raise ValueError("measurement is required")
    return measurement.value
