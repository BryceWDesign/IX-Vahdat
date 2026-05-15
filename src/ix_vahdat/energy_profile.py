"""Energy-per-liter portfolio accounting for IX-Vahdat.

This module compares candidate water-support paths by measured or estimated
energy per liter. It helps IX-Vahdat avoid over-favoring high-energy options
when lower-energy loss reduction, reuse, treatment, fog/dew capture, or storage
paths may be more appropriate.

It does not guarantee cost, yield, water safety, legality, or deployment
readiness. It is decision support for human review.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import inf, isfinite
from types import MappingProxyType
from typing import Mapping

from ix_vahdat.domain import DecisionStatus, EvidenceQuality, RiskLevel


class WaterSupportPath(str, Enum):
    """Candidate water-support path considered by an energy portfolio."""

    LEAK_REPAIR_RECOVERY = "leak_repair_recovery"
    REUSE_TREATMENT = "reuse_treatment"
    SURFACE_WATER_TREATMENT = "surface_water_treatment"
    FOG_OR_DEW_CAPTURE = "fog_or_dew_capture"
    SORBENT_AWH = "sorbent_awh"
    ACTIVE_CONDENSATION_AWH = "active_condensation_awh"
    DESALINATION = "desalination"
    TANKER_SUPPLY = "tanker_supply"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class WaterEnergyProfile:
    """Energy profile for one candidate water-support path.

    `energy_input_wh` is the measured or estimated direct electrical/fuel energy
    at the chosen system boundary. For passive collection paths, direct measured
    energy may be zero, but the result must still account for maintenance,
    storage, material lifecycle, water-quality testing, and human review.
    """

    path: WaterSupportPath
    label: str
    produced_water_l: float
    energy_input_wh: float
    evidence_quality: EvidenceQuality
    safety_gate_passed: bool
    maintenance_ready: bool
    uses_passive_environmental_energy: bool = False
    notes: str | None = None

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise ValueError("label is required")
        _require_nonnegative_finite("produced_water_l", self.produced_water_l)
        _require_nonnegative_finite("energy_input_wh", self.energy_input_wh)
        if self.notes is not None and not self.notes.strip():
            raise ValueError("notes cannot be blank when provided")

    @property
    def energy_per_liter_wh_l(self) -> float | None:
        """Return Wh/L, or None when no measurable output exists."""

        if self.produced_water_l <= 0.0:
            return None
        return self.energy_input_wh / self.produced_water_l

    @property
    def energy_per_cubic_meter_kwh_m3(self) -> float | None:
        """Return kWh/m³.

        Numerically, Wh/L equals kWh/m³ because 1,000 L = 1 m³ and
        1,000 Wh = 1 kWh.
        """

        return self.energy_per_liter_wh_l


@dataclass(frozen=True, slots=True)
class EnergyPortfolioPolicy:
    """Review thresholds for comparing water-support energy profiles.

    These values are portfolio triage thresholds only. They are not vendor
    specifications, economic guarantees, or universal engineering limits.
    """

    default_max_reviewable_wh_l: float = 1_500.0
    active_awh_max_reviewable_wh_l: float = 2_500.0
    desalination_max_reviewable_wh_l: float = 6_000.0
    tanker_max_reviewable_wh_l: float = 8_000.0
    min_output_l_for_comparison: float = 0.1
    path_thresholds_wh_l: Mapping[WaterSupportPath, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_positive_finite("default_max_reviewable_wh_l", self.default_max_reviewable_wh_l)
        _require_positive_finite("active_awh_max_reviewable_wh_l", self.active_awh_max_reviewable_wh_l)
        _require_positive_finite("desalination_max_reviewable_wh_l", self.desalination_max_reviewable_wh_l)
        _require_positive_finite("tanker_max_reviewable_wh_l", self.tanker_max_reviewable_wh_l)
        _require_positive_finite("min_output_l_for_comparison", self.min_output_l_for_comparison)

        cleaned_thresholds: dict[WaterSupportPath, float] = {}
        for path, threshold in self.path_thresholds_wh_l.items():
            _require_positive_finite(f"path_thresholds_wh_l[{path.value}]", threshold)
            cleaned_thresholds[path] = threshold
        object.__setattr__(self, "path_thresholds_wh_l", MappingProxyType(cleaned_thresholds))

    def threshold_for_path(self, path: WaterSupportPath) -> float:
        """Return configured review threshold for a water-support path."""

        if path in self.path_thresholds_wh_l:
            return self.path_thresholds_wh_l[path]
        if path is WaterSupportPath.ACTIVE_CONDENSATION_AWH:
            return self.active_awh_max_reviewable_wh_l
        if path is WaterSupportPath.DESALINATION:
            return self.desalination_max_reviewable_wh_l
        if path is WaterSupportPath.TANKER_SUPPLY:
            return self.tanker_max_reviewable_wh_l
        return self.default_max_reviewable_wh_l


@dataclass(frozen=True, slots=True)
class EnergyProfileAssessment:
    """Assessment for one water-support energy profile."""

    path: WaterSupportPath
    label: str
    decision_status: DecisionStatus
    risk_level: RiskLevel
    produced_water_l: float
    energy_input_wh: float
    energy_per_liter_wh_l: float | None
    energy_per_cubic_meter_kwh_m3: float | None
    threshold_wh_l: float
    reasons: tuple[str, ...]
    required_actions: tuple[str, ...]

    @property
    def may_continue_to_review(self) -> bool:
        """Return True when this path may continue to human review."""

        return self.decision_status is DecisionStatus.ALLOW_REVIEW


@dataclass(frozen=True, slots=True)
class EnergyPortfolioResult:
    """Portfolio-level comparison of candidate water-support paths."""

    decision_status: DecisionStatus
    risk_level: RiskLevel
    assessments: tuple[EnergyProfileAssessment, ...]
    reasons: tuple[str, ...]
    required_actions: tuple[str, ...]

    @property
    def preferred_review_path(self) -> WaterSupportPath | None:
        """Return the lowest-energy reviewable path, if one exists."""

        reviewable = [item for item in self.assessments if item.may_continue_to_review]
        if not reviewable:
            return None
        return min(
            reviewable,
            key=lambda item: (
                item.energy_per_liter_wh_l if item.energy_per_liter_wh_l is not None else inf
            ),
        ).path

    @property
    def has_reviewable_path(self) -> bool:
        """Return True when at least one path may continue to human review."""

        return self.preferred_review_path is not None


def evaluate_energy_portfolio(
    profiles: tuple[WaterEnergyProfile, ...],
    *,
    policy: EnergyPortfolioPolicy | None = None,
) -> EnergyPortfolioResult:
    """Compare candidate water-support paths by energy evidence.

    A reviewable result does not prove that the path is safe, legal, affordable,
    locally acceptable, or sufficient. It means energy evidence is good enough
    to continue into broader human review.
    """

    active_policy = policy or EnergyPortfolioPolicy()

    if not profiles:
        return EnergyPortfolioResult(
            decision_status=DecisionStatus.HOLD_FOR_TESTING,
            risk_level=RiskLevel.HIGH,
            assessments=(),
            reasons=("no water-support energy profiles were provided",),
            required_actions=(
                "provide at least one measured or estimated water-support energy profile",
                "include water output, energy input, evidence quality, safety gate state, and maintenance state",
                "do not make portfolio claims without comparable evidence",
            ),
        )

    assessments = tuple(
        sorted(
            (_assess_profile(profile, active_policy) for profile in profiles),
            key=_assessment_sort_key,
        )
    )

    if any(item.decision_status is DecisionStatus.ALLOW_REVIEW for item in assessments):
        return EnergyPortfolioResult(
            decision_status=DecisionStatus.ALLOW_REVIEW,
            risk_level=_portfolio_risk(assessments),
            assessments=assessments,
            reasons=("one or more water-support paths have reviewable energy evidence",),
            required_actions=(
                "prefer lower-energy paths only after water-quality, maintenance, and local review gates",
                "do not treat energy efficiency as proof of water safety",
                "preserve energy evidence for human review",
            ),
        )

    if all(item.decision_status is DecisionStatus.BLOCK for item in assessments):
        return EnergyPortfolioResult(
            decision_status=DecisionStatus.BLOCK,
            risk_level=RiskLevel.CRITICAL,
            assessments=assessments,
            reasons=("all water-support paths are blocked by energy-profile assessment",),
            required_actions=(
                "do not procure or deploy based on this portfolio",
                "redesign candidate paths or collect new evidence",
                "repeat portfolio review after blockers are resolved",
            ),
        )

    return EnergyPortfolioResult(
        decision_status=DecisionStatus.HOLD_FOR_TESTING,
        risk_level=_portfolio_risk(assessments),
        assessments=assessments,
        reasons=("no water-support path has enough energy evidence for review",),
        required_actions=(
            "collect better output and energy measurements",
            "resolve safety and maintenance blockers",
            "repeat portfolio review before procurement or deployment",
        ),
    )


def _assess_profile(
    profile: WaterEnergyProfile,
    policy: EnergyPortfolioPolicy,
) -> EnergyProfileAssessment:
    threshold = policy.threshold_for_path(profile.path)
    energy_per_liter = profile.energy_per_liter_wh_l
    energy_per_cubic_meter = profile.energy_per_cubic_meter_kwh_m3

    if profile.evidence_quality in {EvidenceQuality.MISSING, EvidenceQuality.CONFLICTING}:
        return _assessment(
            profile=profile,
            threshold=threshold,
            decision_status=DecisionStatus.HOLD_FOR_TESTING,
            risk_level=RiskLevel.HIGH,
            reasons=(f"energy evidence quality is {profile.evidence_quality.value}",),
            required_actions=(
                "collect measured energy and water-output evidence",
                "do not compare this path until evidence is reliable",
                "preserve uncertainty in the review record",
            ),
        )

    if not profile.safety_gate_passed:
        return _assessment(
            profile=profile,
            threshold=threshold,
            decision_status=DecisionStatus.HOLD_FOR_TESTING,
            risk_level=RiskLevel.HIGH,
            reasons=("safety gate has not passed for this path",),
            required_actions=(
                "resolve water-quality, treatment, storage, or infrastructure safety blockers",
                "do not treat energy efficiency as permission to use water",
                "repeat portfolio review after safety gate passes",
            ),
        )

    if not profile.maintenance_ready:
        return _assessment(
            profile=profile,
            threshold=threshold,
            decision_status=DecisionStatus.HOLD_FOR_TESTING,
            risk_level=RiskLevel.HIGH,
            reasons=("maintenance readiness has not passed for this path",),
            required_actions=(
                "resolve maintenance blockers before deployment review",
                "verify filters, tanks, sensors, storage, and critical spare parts",
                "repeat portfolio review after maintenance readiness passes",
            ),
        )

    if profile.produced_water_l < policy.min_output_l_for_comparison:
        return _assessment(
            profile=profile,
            threshold=threshold,
            decision_status=DecisionStatus.HOLD_FOR_TESTING,
            risk_level=RiskLevel.MODERATE,
            reasons=("water output is below minimum comparison threshold",),
            required_actions=(
                "run longer or better-instrumented test",
                "do not rank this path as productive from current evidence",
                "preserve low-output evidence",
            ),
        )

    if energy_per_liter is None:
        return _assessment(
            profile=profile,
            threshold=threshold,
            decision_status=DecisionStatus.HOLD_FOR_TESTING,
            risk_level=RiskLevel.MODERATE,
            reasons=("energy per liter cannot be computed",),
            required_actions=(
                "measure water output and energy input at the same boundary",
                "repeat portfolio assessment",
                "do not make energy-efficiency claims",
            ),
        )

    if energy_per_liter > threshold:
        return _assessment(
            profile=profile,
            threshold=threshold,
            decision_status=DecisionStatus.HOLD_FOR_TESTING,
            risk_level=RiskLevel.HIGH,
            reasons=("energy per liter exceeds configured review threshold",),
            required_actions=(
                "do not scale this path without redesign",
                "compare against lower-energy water-support paths",
                "inspect losses, runtime, and measurement boundary",
            ),
        )

    reasons = ["energy per liter is within configured review threshold"]
    required_actions = [
        "continue only to broader human review",
        "verify water quality, maintenance, and local compliance before field use",
        "preserve energy boundary and measurement method",
    ]
    risk_level = RiskLevel.LOW

    if profile.evidence_quality is EvidenceQuality.ESTIMATED:
        reasons.append("energy evidence is estimated rather than measured")
        required_actions.append("replace estimate with measured data before procurement")
        risk_level = RiskLevel.MODERATE

    if profile.uses_passive_environmental_energy and profile.energy_input_wh == 0.0:
        reasons.append("direct measured energy is zero because the path is passive")
        required_actions.append(
            "do not describe passive collection as free; account for maintenance, materials, and testing"
        )

    return _assessment(
        profile=profile,
        threshold=threshold,
        decision_status=DecisionStatus.ALLOW_REVIEW,
        risk_level=risk_level,
        reasons=tuple(reasons),
        required_actions=tuple(required_actions),
    )


def _assessment(
    *,
    profile: WaterEnergyProfile,
    threshold: float,
    decision_status: DecisionStatus,
    risk_level: RiskLevel,
    reasons: tuple[str, ...],
    required_actions: tuple[str, ...],
) -> EnergyProfileAssessment:
    return EnergyProfileAssessment(
        path=profile.path,
        label=profile.label,
        decision_status=decision_status,
        risk_level=risk_level,
        produced_water_l=profile.produced_water_l,
        energy_input_wh=profile.energy_input_wh,
        energy_per_liter_wh_l=profile.energy_per_liter_wh_l,
        energy_per_cubic_meter_kwh_m3=profile.energy_per_cubic_meter_kwh_m3,
        threshold_wh_l=threshold,
        reasons=reasons,
        required_actions=required_actions,
    )


def _assessment_sort_key(assessment: EnergyProfileAssessment) -> tuple[int, float, str]:
    status_order = {
        DecisionStatus.ALLOW_REVIEW: 0,
        DecisionStatus.HOLD_FOR_TESTING: 1,
        DecisionStatus.BLOCK: 2,
    }
    energy_value = (
        assessment.energy_per_liter_wh_l if assessment.energy_per_liter_wh_l is not None else inf
    )
    return (status_order[assessment.decision_status], energy_value, assessment.label)


def _portfolio_risk(assessments: tuple[EnergyProfileAssessment, ...]) -> RiskLevel:
    order = {
        RiskLevel.LOW: 0,
        RiskLevel.MODERATE: 1,
        RiskLevel.HIGH: 2,
        RiskLevel.CRITICAL: 3,
    }
    return max(assessments, key=lambda item: order[item.risk_level]).risk_level


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
