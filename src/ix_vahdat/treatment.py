"""Treatment-routing logic for IX-Vahdat.

This module recommends conservative routing states for a water batch after
water-quality evidence and treatment-system readiness are considered.

It does not operate valves, pumps, UV systems, chemical dosing, discharge
points, or distribution systems. It produces decision-support output only.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ix_vahdat.domain import DecisionStatus, RiskLevel
from ix_vahdat.quality import WaterQualityGateResult


class TreatmentRoute(str, Enum):
    """Conservative treatment-routing states."""

    PASS_TO_REVIEW = "pass_to_review"
    RECIRCULATE = "recirculate"
    HOLD_FOR_TESTING = "hold_for_testing"
    REJECT_TO_WASTE_REVIEW = "reject_to_waste_review"


@dataclass(frozen=True, slots=True)
class TreatmentSystemSnapshot:
    """Current readiness state of a field treatment path.

    All values are observations for software review. They do not imply that the
    physical system is certified, permitted, or safe to operate.
    """

    pretreatment_available: bool
    filtration_available: bool
    disinfection_available: bool
    storage_clean: bool
    recirculation_available: bool
    waste_hold_available: bool
    filter_pressure_delta_kpa: float
    flow_rate_l_min: float
    tank_capacity_remaining_fraction: float

    def __post_init__(self) -> None:
        if self.filter_pressure_delta_kpa < 0:
            raise ValueError("filter_pressure_delta_kpa cannot be negative")
        if self.flow_rate_l_min < 0:
            raise ValueError("flow_rate_l_min cannot be negative")
        if not 0.0 <= self.tank_capacity_remaining_fraction <= 1.0:
            raise ValueError("tank_capacity_remaining_fraction must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class TreatmentRoutingPolicy:
    """Proof-of-concept routing thresholds.

    These are software triage thresholds, not equipment specifications or legal
    operating standards.
    """

    max_filter_pressure_delta_kpa: float = 140.0
    min_flow_rate_l_min: float = 0.2
    min_tank_capacity_remaining_fraction: float = 0.10
    allow_recirc_on_hold: bool = True
    allow_recirc_on_critical_pathogen: bool = True


@dataclass(frozen=True, slots=True)
class TreatmentRoutingResult:
    """Decision-support output for treatment routing."""

    route: TreatmentRoute
    decision_status: DecisionStatus
    risk_level: RiskLevel
    reasons: tuple[str, ...]
    required_actions: tuple[str, ...]

    @property
    def requires_human_review(self) -> bool:
        """Every route remains review-only and non-autonomous."""

        return True


def route_treatment_batch(
    *,
    quality_gate: WaterQualityGateResult,
    system: TreatmentSystemSnapshot,
    policy: TreatmentRoutingPolicy | None = None,
) -> TreatmentRoutingResult:
    """Route a water batch through conservative review-only treatment logic."""

    active_policy = policy or TreatmentRoutingPolicy()

    readiness_blockers = _readiness_blockers(system, active_policy)
    if readiness_blockers:
        return TreatmentRoutingResult(
            route=TreatmentRoute.HOLD_FOR_TESTING,
            decision_status=DecisionStatus.HOLD_FOR_TESTING,
            risk_level=RiskLevel.HIGH,
            reasons=readiness_blockers,
            required_actions=(
                "do not route batch to field use",
                "restore treatment-system readiness",
                "repeat water-quality and maintenance review",
                "human review required before any routing change",
            ),
        )

    if quality_gate.decision_status is DecisionStatus.BLOCK:
        return _route_blocked_quality(quality_gate, system, active_policy)

    if quality_gate.decision_status is DecisionStatus.HOLD_FOR_TESTING:
        return _route_hold_quality(quality_gate, system, active_policy)

    return TreatmentRoutingResult(
        route=TreatmentRoute.PASS_TO_REVIEW,
        decision_status=DecisionStatus.ALLOW_REVIEW,
        risk_level=quality_gate.risk_level,
        reasons=(
            "water-quality gate allows conservative downstream review",
            "treatment-system readiness checks passed configured proof-of-concept thresholds",
        ),
        required_actions=(
            "preserve treatment and water-quality evidence bundle",
            "route only under qualified human review",
            "do not claim potable water from software output alone",
            "continue monitoring for changed conditions",
        ),
    )


def _readiness_blockers(
    system: TreatmentSystemSnapshot,
    policy: TreatmentRoutingPolicy,
) -> tuple[str, ...]:
    blockers: list[str] = []
    if not system.pretreatment_available:
        blockers.append("pretreatment path is unavailable")
    if not system.filtration_available:
        blockers.append("filtration path is unavailable")
    if not system.disinfection_available:
        blockers.append("disinfection path is unavailable")
    if not system.storage_clean:
        blockers.append("storage cleanliness is not verified")
    if system.filter_pressure_delta_kpa > policy.max_filter_pressure_delta_kpa:
        blockers.append("filter pressure differential exceeds configured threshold")
    if system.flow_rate_l_min < policy.min_flow_rate_l_min:
        blockers.append("flow rate is below configured minimum for reliable routing")
    if system.tank_capacity_remaining_fraction < policy.min_tank_capacity_remaining_fraction:
        blockers.append("tank capacity remaining is below configured minimum")
    return tuple(blockers)


def _route_blocked_quality(
    quality_gate: WaterQualityGateResult,
    system: TreatmentSystemSnapshot,
    policy: TreatmentRoutingPolicy,
) -> TreatmentRoutingResult:
    pathogen_block = any("pathogen" in reason for reason in quality_gate.reasons)
    chemical_block = any("chemical" in reason for reason in quality_gate.reasons)
    critical_conductivity = any("conductivity exceeds critical" in reason for reason in quality_gate.reasons)

    if chemical_block or critical_conductivity:
        if system.waste_hold_available:
            return TreatmentRoutingResult(
                route=TreatmentRoute.REJECT_TO_WASTE_REVIEW,
                decision_status=DecisionStatus.BLOCK,
                risk_level=RiskLevel.CRITICAL,
                reasons=quality_gate.reasons
                + ("blocked quality condition requires waste/qualified disposal review",),
                required_actions=(
                    "isolate batch",
                    "do not recirculate through routine treatment path",
                    "hold for qualified chemical or disposal review",
                    "preserve evidence bundle",
                ),
            )

        return TreatmentRoutingResult(
            route=TreatmentRoute.HOLD_FOR_TESTING,
            decision_status=DecisionStatus.HOLD_FOR_TESTING,
            risk_level=RiskLevel.CRITICAL,
            reasons=quality_gate.reasons
            + ("waste hold is unavailable for blocked quality condition",),
            required_actions=(
                "stop routing",
                "create safe containment plan",
                "obtain qualified chemical or disposal review",
            ),
        )

    if pathogen_block and policy.allow_recirc_on_critical_pathogen and system.recirculation_available:
        return TreatmentRoutingResult(
            route=TreatmentRoute.RECIRCULATE,
            decision_status=DecisionStatus.HOLD_FOR_TESTING,
            risk_level=RiskLevel.CRITICAL,
            reasons=quality_gate.reasons
            + ("recirculation available for treatment review; no public release allowed",),
            required_actions=(
                "recirculate only under qualified operator review",
                "verify disinfection effectiveness before any candidate classification",
                "repeat pathogen testing",
                "do not release or distribute water",
            ),
        )

    return TreatmentRoutingResult(
        route=TreatmentRoute.HOLD_FOR_TESTING,
        decision_status=DecisionStatus.HOLD_FOR_TESTING,
        risk_level=RiskLevel.CRITICAL,
        reasons=quality_gate.reasons
        + ("blocked quality condition cannot be safely routed by proof-of-concept logic",),
        required_actions=(
            "hold batch",
            "obtain qualified water-quality review",
            "do not release or distribute water",
        ),
    )


def _route_hold_quality(
    quality_gate: WaterQualityGateResult,
    system: TreatmentSystemSnapshot,
    policy: TreatmentRoutingPolicy,
) -> TreatmentRoutingResult:
    if policy.allow_recirc_on_hold and system.recirculation_available:
        return TreatmentRoutingResult(
            route=TreatmentRoute.RECIRCULATE,
            decision_status=DecisionStatus.HOLD_FOR_TESTING,
            risk_level=max_risk(quality_gate.risk_level, RiskLevel.HIGH),
            reasons=quality_gate.reasons
            + ("recirculation is available while evidence is completed",),
            required_actions=(
                "recirculate or retreat only under operator review",
                "collect missing or repeated measurements",
                "hold batch from field use",
                "repeat quality gate before classification",
            ),
        )

    return TreatmentRoutingResult(
        route=TreatmentRoute.HOLD_FOR_TESTING,
        decision_status=DecisionStatus.HOLD_FOR_TESTING,
        risk_level=max_risk(quality_gate.risk_level, RiskLevel.HIGH),
        reasons=quality_gate.reasons
        + ("recirculation is unavailable or disabled by policy",),
        required_actions=(
            "hold batch",
            "collect missing or repeated measurements",
            "repeat quality gate before classification",
            "human review required before any routing change",
        ),
    )


def max_risk(left: RiskLevel, right: RiskLevel) -> RiskLevel:
    """Return the more severe of two risk levels."""

    order = {
        RiskLevel.LOW: 0,
        RiskLevel.MODERATE: 1,
        RiskLevel.HIGH: 2,
        RiskLevel.CRITICAL: 3,
    }
    return left if order[left] >= order[right] else right
