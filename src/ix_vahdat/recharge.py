"""Managed aquifer recharge readiness screening for IX-Vahdat.

Managed aquifer recharge can be useful only when source water, treatment,
hydrogeology, contamination controls, monitoring, local authority, and human
review support the proposed action.

This module is a conservative feasibility screen. It does not approve recharge,
authorize injection or infiltration, replace hydrogeology studies, bypass
permits, certify source water, or operate field hardware.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite

from ix_vahdat.domain import DecisionStatus, EvidenceQuality, RiskLevel, SensorStatus
from ix_vahdat.water_use import WaterUseClass


class RechargeMethod(str, Enum):
    """Managed aquifer recharge method under review."""

    SPREADING_BASIN = "spreading_basin"
    INFILTRATION_TRENCH = "infiltration_trench"
    CHECK_DAM = "check_dam"
    WETLAND_ENHANCEMENT = "wetland_enhancement"
    INJECTION_WELL = "injection_well"
    UNKNOWN = "unknown"


class MARReadinessClass(str, Enum):
    """Conservative managed-aquifer-recharge readiness class."""

    REVIEWABLE_PILOT = "reviewable_pilot"
    INVESTIGATION_REQUIRED = "investigation_required"
    MONITORING_ONLY = "monitoring_only"
    NOT_READY = "not_ready"


@dataclass(frozen=True, slots=True)
class MARWaterSource:
    """Source-water evidence for managed aquifer recharge review."""

    source_id: str
    label: str
    water_use_class: WaterUseClass
    available_volume_l: float
    quality_gate_passed: bool
    treatment_route_reviewed: bool
    evidence_quality: EvidenceQuality
    sensor_status: SensorStatus
    salinity_risk_fraction: float = 0.0
    contamination_risk_fraction: float = 0.0
    notes: str | None = None

    def __post_init__(self) -> None:
        if not self.source_id.strip():
            raise ValueError("source_id is required")
        if not self.label.strip():
            raise ValueError("label is required")
        _require_nonnegative_finite("available_volume_l", self.available_volume_l)
        _require_fraction("salinity_risk_fraction", self.salinity_risk_fraction)
        _require_fraction("contamination_risk_fraction", self.contamination_risk_fraction)
        if self.notes is not None and not self.notes.strip():
            raise ValueError("notes cannot be blank when provided")

    @property
    def evidence_is_reliable(self) -> bool:
        """Return whether source-water evidence can support review."""

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
class MARSiteObservation:
    """Site evidence for managed aquifer recharge readiness review."""

    site_id: str
    label: str
    method: RechargeMethod
    evidence_quality: EvidenceQuality
    sensor_status: SensorStatus
    infiltration_capacity_fraction: float
    groundwater_vulnerability_fraction: float
    geotechnical_stability_fraction: float
    subsidence_risk_fraction: float
    contamination_source_distance_m: float | None
    monitoring_well_available: bool
    local_authority_review_available: bool
    environmental_review_available: bool
    community_review_available: bool
    notes: str | None = None

    def __post_init__(self) -> None:
        if not self.site_id.strip():
            raise ValueError("site_id is required")
        if not self.label.strip():
            raise ValueError("label is required")
        _require_fraction("infiltration_capacity_fraction", self.infiltration_capacity_fraction)
        _require_fraction(
            "groundwater_vulnerability_fraction",
            self.groundwater_vulnerability_fraction,
        )
        _require_fraction("geotechnical_stability_fraction", self.geotechnical_stability_fraction)
        _require_fraction("subsidence_risk_fraction", self.subsidence_risk_fraction)
        if self.contamination_source_distance_m is not None:
            _require_nonnegative_finite(
                "contamination_source_distance_m",
                self.contamination_source_distance_m,
            )
        if self.notes is not None and not self.notes.strip():
            raise ValueError("notes cannot be blank when provided")

    @property
    def evidence_is_reliable(self) -> bool:
        """Return whether site evidence can support review."""

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
class MARReadinessPolicy:
    """Proof-of-concept thresholds for managed aquifer recharge screening."""

    min_source_volume_l: float = 1_000.0
    max_salinity_risk_fraction: float = 0.35
    max_contamination_risk_fraction: float = 0.25
    min_infiltration_capacity_fraction: float = 0.40
    max_groundwater_vulnerability_fraction: float = 0.35
    min_geotechnical_stability_fraction: float = 0.65
    max_subsidence_risk_fraction_for_pilot: float = 0.60
    min_contamination_source_distance_m: float = 100.0
    require_monitoring_well: bool = True
    require_local_authority_review: bool = True
    require_environmental_review: bool = True
    require_community_review: bool = True
    block_unknown_method: bool = True
    block_injection_well_without_specialist_review: bool = True

    def __post_init__(self) -> None:
        _require_positive_finite("min_source_volume_l", self.min_source_volume_l)
        _require_fraction("max_salinity_risk_fraction", self.max_salinity_risk_fraction)
        _require_fraction("max_contamination_risk_fraction", self.max_contamination_risk_fraction)
        _require_fraction("min_infiltration_capacity_fraction", self.min_infiltration_capacity_fraction)
        _require_fraction(
            "max_groundwater_vulnerability_fraction",
            self.max_groundwater_vulnerability_fraction,
        )
        _require_fraction(
            "min_geotechnical_stability_fraction",
            self.min_geotechnical_stability_fraction,
        )
        _require_fraction(
            "max_subsidence_risk_fraction_for_pilot",
            self.max_subsidence_risk_fraction_for_pilot,
        )
        _require_nonnegative_finite(
            "min_contamination_source_distance_m",
            self.min_contamination_source_distance_m,
        )


@dataclass(frozen=True, slots=True)
class MARReadinessResult:
    """Decision-support output for managed aquifer recharge readiness."""

    readiness_class: MARReadinessClass
    decision_status: DecisionStatus
    risk_level: RiskLevel
    reasons: tuple[str, ...]
    required_actions: tuple[str, ...]

    @property
    def may_continue_to_human_review(self) -> bool:
        """Return True when a pilot concept may continue to human review."""

        return self.decision_status is DecisionStatus.ALLOW_REVIEW


def evaluate_mar_readiness(
    *,
    source: MARWaterSource,
    site: MARSiteObservation,
    policy: MARReadinessPolicy | None = None,
) -> MARReadinessResult:
    """Evaluate managed aquifer recharge readiness.

    A reviewable pilot result is not approval to recharge. It means the source
    and site evidence are sufficient to continue to qualified human review.
    """

    active_policy = policy or MARReadinessPolicy()

    source_blockers = _source_blockers(source, active_policy)
    site_blockers = _site_blockers(site, active_policy)
    hard_blockers = source_blockers + site_blockers

    if hard_blockers:
        return MARReadinessResult(
            readiness_class=MARReadinessClass.NOT_READY,
            decision_status=DecisionStatus.BLOCK,
            risk_level=RiskLevel.CRITICAL,
            reasons=hard_blockers,
            required_actions=(
                "do not perform managed aquifer recharge",
                "resolve source-water, site, monitoring, or review blockers",
                "obtain qualified hydrogeology and environmental review",
                "repeat readiness screen with reliable evidence",
            ),
        )

    investigation_reasons = _investigation_reasons(source, site, active_policy)
    if investigation_reasons:
        return MARReadinessResult(
            readiness_class=MARReadinessClass.INVESTIGATION_REQUIRED,
            decision_status=DecisionStatus.HOLD_FOR_TESTING,
            risk_level=RiskLevel.HIGH,
            reasons=investigation_reasons,
            required_actions=(
                "hold recharge action",
                "collect hydrogeology, monitoring, and source-water evidence",
                "complete qualified site investigation",
                "repeat readiness screen before pilot review",
            ),
        )

    monitoring_reasons = _monitoring_only_reasons(site, active_policy)
    if monitoring_reasons:
        return MARReadinessResult(
            readiness_class=MARReadinessClass.MONITORING_ONLY,
            decision_status=DecisionStatus.ALLOW_REVIEW,
            risk_level=RiskLevel.MODERATE,
            reasons=monitoring_reasons,
            required_actions=(
                "continue monitoring before any recharge pilot",
                "track subsidence, groundwater response, and water quality",
                "do not inject or infiltrate water from software output alone",
                "human review required before pilot design",
            ),
        )

    return MARReadinessResult(
        readiness_class=MARReadinessClass.REVIEWABLE_PILOT,
        decision_status=DecisionStatus.ALLOW_REVIEW,
        risk_level=RiskLevel.LOW,
        reasons=(
            "source-water and site evidence pass proof-of-concept recharge readiness screen",
        ),
        required_actions=(
            "continue only to qualified human pilot review",
            "obtain local authority and environmental approval before field action",
            "establish baseline groundwater, subsidence, and water-quality monitoring",
            "do not treat this result as recharge authorization",
        ),
    )


def _source_blockers(
    source: MARWaterSource,
    policy: MARReadinessPolicy,
) -> tuple[str, ...]:
    blockers: list[str] = []

    if not source.evidence_is_reliable:
        blockers.extend(_evidence_reasons(source.label, source.evidence_quality, source.sensor_status))

    if source.water_use_class is WaterUseClass.UNSAFE_HOLD:
        blockers.append("source water is classified as unsafe hold")
    if not source.quality_gate_passed:
        blockers.append("source-water quality gate has not passed")
    if not source.treatment_route_reviewed:
        blockers.append("source-water treatment route has not been reviewed")
    if source.salinity_risk_fraction > policy.max_salinity_risk_fraction:
        blockers.append("source-water salinity risk exceeds recharge threshold")
    if source.contamination_risk_fraction > policy.max_contamination_risk_fraction:
        blockers.append("source-water contamination risk exceeds recharge threshold")

    return tuple(blockers)


def _site_blockers(
    site: MARSiteObservation,
    policy: MARReadinessPolicy,
) -> tuple[str, ...]:
    blockers: list[str] = []

    if not site.evidence_is_reliable:
        blockers.extend(_evidence_reasons(site.label, site.evidence_quality, site.sensor_status))

    if policy.block_unknown_method and site.method is RechargeMethod.UNKNOWN:
        blockers.append("recharge method is unknown")

    if (
        policy.block_injection_well_without_specialist_review
        and site.method is RechargeMethod.INJECTION_WELL
    ):
        blockers.append("injection well concept requires specialist design and approval")

    if site.groundwater_vulnerability_fraction > policy.max_groundwater_vulnerability_fraction:
        blockers.append("groundwater vulnerability exceeds configured recharge limit")

    if site.contamination_source_distance_m is not None:
        if site.contamination_source_distance_m < policy.min_contamination_source_distance_m:
            blockers.append("site is too close to a known contamination source")

    if policy.require_local_authority_review and not site.local_authority_review_available:
        blockers.append("local authority review is not available")
    if policy.require_environmental_review and not site.environmental_review_available:
        blockers.append("environmental review is not available")
    if policy.require_community_review and not site.community_review_available:
        blockers.append("community review is not available")

    return tuple(blockers)


def _investigation_reasons(
    source: MARWaterSource,
    site: MARSiteObservation,
    policy: MARReadinessPolicy,
) -> tuple[str, ...]:
    reasons: list[str] = []

    if source.available_volume_l < policy.min_source_volume_l:
        reasons.append("available source-water volume is below pilot review threshold")
    if site.infiltration_capacity_fraction < policy.min_infiltration_capacity_fraction:
        reasons.append("site infiltration capacity is below pilot review threshold")
    if site.geotechnical_stability_fraction < policy.min_geotechnical_stability_fraction:
        reasons.append("site geotechnical stability is below pilot review threshold")
    if policy.require_monitoring_well and not site.monitoring_well_available:
        reasons.append("monitoring well or equivalent groundwater observation is unavailable")

    return tuple(reasons)


def _monitoring_only_reasons(
    site: MARSiteObservation,
    policy: MARReadinessPolicy,
) -> tuple[str, ...]:
    if site.subsidence_risk_fraction > policy.max_subsidence_risk_fraction_for_pilot:
        return ("subsidence risk supports monitoring-only posture before pilot recharge",)
    return ()


def _evidence_reasons(
    label: str,
    evidence_quality: EvidenceQuality,
    sensor_status: SensorStatus,
) -> tuple[str, ...]:
    reasons: list[str] = []

    if evidence_quality in {EvidenceQuality.MISSING, EvidenceQuality.CONFLICTING}:
        reasons.append(f"{label} evidence quality is {evidence_quality.value}")
    if sensor_status in {SensorStatus.STALE, SensorStatus.FAILED, SensorStatus.UNVERIFIED}:
        reasons.append(f"{label} sensor status is {sensor_status.value}")

    return tuple(reasons)


def _require_fraction(name: str, value: float) -> None:
    if not isfinite(value):
        raise ValueError(f"{name} must be finite")
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1")


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
