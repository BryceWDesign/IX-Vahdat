"""Site-readiness scoring for IX-Vahdat.

This module combines outputs from IX-Vahdat evidence gates into one conservative
site-readiness posture. It helps reviewers decide whether a water-resilience
node is ready for bench testing, limited field review, emergency support review,
or should remain blocked.

It does not certify a site, authorize construction, approve public water use,
or replace local authority, public-health, environmental, or engineering review.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ix_vahdat.awh import AWHTriageResult
from ix_vahdat.domain import DecisionStatus, RiskLevel
from ix_vahdat.energy import EnergyAccountingResult
from ix_vahdat.energy_profile import EnergyPortfolioResult
from ix_vahdat.failures import FailureEvaluationResult
from ix_vahdat.infrastructure import InfrastructureHealthResult
from ix_vahdat.maintenance import MaintenanceResult
from ix_vahdat.power import PowerMode, PowerPriorityResult
from ix_vahdat.quality import WaterQualityGateResult
from ix_vahdat.recharge import MARReadinessResult
from ix_vahdat.reserve import EmergencyReserveResult
from ix_vahdat.review import ReviewGateResult
from ix_vahdat.treatment import TreatmentRoutingResult
from ix_vahdat.water_use import WaterUseAssessment


class SiteReadinessClass(str, Enum):
    """Conservative site-readiness class for a water-resilience node."""

    BLOCKED = "blocked"
    SERVICE_REQUIRED = "service_required"
    INVESTIGATION_REQUIRED = "investigation_required"
    BENCH_ONLY = "bench_only"
    LIMITED_FIELD_REVIEW = "limited_field_review"
    EMERGENCY_SUPPORT_REVIEW = "emergency_support_review"


@dataclass(frozen=True, slots=True)
class SiteReadinessInputs:
    """Gate outputs used to evaluate overall site readiness."""

    water_quality: WaterQualityGateResult
    water_use: WaterUseAssessment
    treatment: TreatmentRoutingResult
    energy: EnergyAccountingResult
    power: PowerPriorityResult
    reserve: EmergencyReserveResult
    maintenance: MaintenanceResult
    failures: FailureEvaluationResult
    infrastructure: InfrastructureHealthResult
    human_review: ReviewGateResult
    energy_portfolio: EnergyPortfolioResult | None = None
    atmospheric_water: AWHTriageResult | None = None
    recharge: MARReadinessResult | None = None


@dataclass(frozen=True, slots=True)
class SiteReadinessResult:
    """Overall readiness decision-support output for a site."""

    readiness_class: SiteReadinessClass
    decision_status: DecisionStatus
    risk_level: RiskLevel
    readiness_score: int
    reasons: tuple[str, ...]
    required_actions: tuple[str, ...]

    @property
    def may_continue_to_limited_review(self) -> bool:
        """Return True when the site may continue to limited human review."""

        return (
            self.decision_status is DecisionStatus.ALLOW_REVIEW
            and self.readiness_class
            in {
                SiteReadinessClass.LIMITED_FIELD_REVIEW,
                SiteReadinessClass.EMERGENCY_SUPPORT_REVIEW,
            }
        )


def evaluate_site_readiness(inputs: SiteReadinessInputs) -> SiteReadinessResult:
    """Evaluate the overall readiness of an IX-Vahdat site.

    The result is review-only. It does not approve drinking water, distribution,
    discharge, recharge, construction, procurement, or field operation.
    """

    gate_statuses = _collect_statuses(inputs)
    hard_block_reasons = _hard_block_reasons(inputs, gate_statuses)
    if hard_block_reasons:
        return SiteReadinessResult(
            readiness_class=SiteReadinessClass.BLOCKED,
            decision_status=DecisionStatus.BLOCK,
            risk_level=RiskLevel.CRITICAL,
            readiness_score=0,
            reasons=hard_block_reasons,
            required_actions=(
                "do not deploy or operate this water-resilience node",
                "resolve blocking quality, safety, reserve, failure, or review conditions",
                "repeat full site-readiness review after blockers are resolved",
                "preserve blocked-readiness evidence bundle",
            ),
        )

    score = _readiness_score(inputs, gate_statuses)
    risk = _max_risk(inputs)

    if _service_required(inputs, gate_statuses):
        return SiteReadinessResult(
            readiness_class=SiteReadinessClass.SERVICE_REQUIRED,
            decision_status=DecisionStatus.HOLD_FOR_TESTING,
            risk_level=max_risk(risk, RiskLevel.HIGH),
            readiness_score=min(score, 30),
            reasons=_service_reasons(inputs, gate_statuses),
            required_actions=(
                "service maintenance, power, infrastructure, or failure-mode blockers",
                "hold field use and public-facing claims",
                "repeat readiness review with updated evidence",
            ),
        )

    if _investigation_required(inputs, gate_statuses):
        return SiteReadinessResult(
            readiness_class=SiteReadinessClass.INVESTIGATION_REQUIRED,
            decision_status=DecisionStatus.HOLD_FOR_TESTING,
            risk_level=max_risk(risk, RiskLevel.HIGH),
            readiness_score=min(score, 50),
            reasons=_investigation_reasons(inputs, gate_statuses),
            required_actions=(
                "collect missing measurements, inspections, or site observations",
                "complete qualified review before field deployment",
                "do not procure or scale hardware from current evidence alone",
            ),
        )

    if not inputs.human_review.is_approved:
        return SiteReadinessResult(
            readiness_class=SiteReadinessClass.BENCH_ONLY,
            decision_status=DecisionStatus.HOLD_FOR_TESTING,
            risk_level=max_risk(risk, RiskLevel.HIGH),
            readiness_score=min(score, 55),
            reasons=("human review has not approved limited field use",),
            required_actions=(
                "keep work at bench or simulation level",
                "assign qualified human reviewer",
                "document authority basis and limits before field review",
            ),
        )

    if _emergency_support_review(inputs):
        return SiteReadinessResult(
            readiness_class=SiteReadinessClass.EMERGENCY_SUPPORT_REVIEW,
            decision_status=DecisionStatus.ALLOW_REVIEW,
            risk_level=max_risk(risk, RiskLevel.HIGH),
            readiness_score=min(score, 75),
            reasons=(
                "site may continue only to emergency support review under explicit human authority",
            ),
            required_actions=(
                "preserve emergency review record",
                "do not treat readiness as public distribution approval",
                "track reserve, quality, power, and infrastructure conditions continuously",
            ),
        )

    return SiteReadinessResult(
        readiness_class=SiteReadinessClass.LIMITED_FIELD_REVIEW,
        decision_status=DecisionStatus.ALLOW_REVIEW,
        risk_level=risk,
        readiness_score=score,
        reasons=("site evidence supports limited human-reviewed field evaluation",),
        required_actions=(
            "continue only within approved limited-use scope",
            "preserve full evidence bundle",
            "do not claim certified potable water or deployment readiness",
            "repeat review when site, water, power, or maintenance conditions change",
        ),
    )


def _collect_statuses(inputs: SiteReadinessInputs) -> tuple[DecisionStatus, ...]:
    statuses = [
        inputs.water_quality.decision_status,
        inputs.water_use.decision_status,
        inputs.treatment.decision_status,
        inputs.energy.decision_status,
        inputs.power.decision_status,
        inputs.reserve.decision_status,
        inputs.maintenance.decision_status,
        inputs.failures.decision_status,
        inputs.infrastructure.decision_status,
        inputs.human_review.decision_status,
    ]

    if inputs.energy_portfolio is not None:
        statuses.append(inputs.energy_portfolio.decision_status)
    if inputs.atmospheric_water is not None:
        statuses.append(inputs.atmospheric_water.decision_status)
    if inputs.recharge is not None:
        statuses.append(inputs.recharge.decision_status)

    return tuple(statuses)


def _hard_block_reasons(
    inputs: SiteReadinessInputs,
    statuses: tuple[DecisionStatus, ...],
) -> tuple[str, ...]:
    reasons: list[str] = []

    if DecisionStatus.BLOCK in statuses:
        reasons.append("one or more upstream gates are blocked")
    if inputs.water_quality.risk_level is RiskLevel.CRITICAL:
        reasons.append("water-quality risk is critical")
    if inputs.water_use.risk_level is RiskLevel.CRITICAL:
        reasons.append("water-use classification risk is critical")
    if inputs.treatment.risk_level is RiskLevel.CRITICAL:
        reasons.append("treatment routing risk is critical")
    if inputs.reserve.risk_level is RiskLevel.CRITICAL:
        reasons.append("emergency reserve risk is critical")
    if inputs.failures.risk_level is RiskLevel.CRITICAL and inputs.failures.fail_closed:
        reasons.append("active failure mode forces fail-closed posture")
    if inputs.infrastructure.risk_level is RiskLevel.CRITICAL:
        reasons.append("infrastructure-health risk is critical")

    return tuple(_dedupe(reasons))


def _service_required(
    inputs: SiteReadinessInputs,
    statuses: tuple[DecisionStatus, ...],
) -> bool:
    return (
        DecisionStatus.HOLD_FOR_TESTING in statuses
        and (
            not inputs.maintenance.maintenance_ready
            or inputs.failures.fail_closed
            or not inputs.infrastructure.infrastructure_ready
            or inputs.power.mode in {PowerMode.SAFE_HOLD, PowerMode.SERVICE_REQUIRED}
        )
    )


def _service_reasons(
    inputs: SiteReadinessInputs,
    statuses: tuple[DecisionStatus, ...],
) -> tuple[str, ...]:
    reasons: list[str] = []

    if DecisionStatus.HOLD_FOR_TESTING in statuses:
        reasons.append("one or more upstream gates require testing or service")
    if not inputs.maintenance.maintenance_ready:
        reasons.append("maintenance blockers are present")
    if inputs.failures.fail_closed:
        reasons.append("failure registry is in fail-closed posture")
    if not inputs.infrastructure.infrastructure_ready:
        reasons.append("infrastructure-health blockers are present")
    if inputs.power.mode in {PowerMode.SAFE_HOLD, PowerMode.SERVICE_REQUIRED}:
        reasons.append("power system requires safe-hold or service posture")

    return tuple(_dedupe(reasons))


def _investigation_required(
    inputs: SiteReadinessInputs,
    statuses: tuple[DecisionStatus, ...],
) -> bool:
    if DecisionStatus.HOLD_FOR_TESTING not in statuses:
        return False

    return (
        inputs.water_quality.decision_status is DecisionStatus.HOLD_FOR_TESTING
        or inputs.water_use.decision_status is DecisionStatus.HOLD_FOR_TESTING
        or inputs.treatment.decision_status is DecisionStatus.HOLD_FOR_TESTING
        or inputs.energy.decision_status is DecisionStatus.HOLD_FOR_TESTING
        or inputs.reserve.decision_status is DecisionStatus.HOLD_FOR_TESTING
        or (
            inputs.energy_portfolio is not None
            and inputs.energy_portfolio.decision_status is DecisionStatus.HOLD_FOR_TESTING
        )
        or (
            inputs.atmospheric_water is not None
            and inputs.atmospheric_water.decision_status is DecisionStatus.HOLD_FOR_TESTING
        )
        or (
            inputs.recharge is not None
            and inputs.recharge.decision_status is DecisionStatus.HOLD_FOR_TESTING
        )
    )


def _investigation_reasons(
    inputs: SiteReadinessInputs,
    statuses: tuple[DecisionStatus, ...],
) -> tuple[str, ...]:
    reasons: list[str] = []

    if DecisionStatus.HOLD_FOR_TESTING in statuses:
        reasons.append("one or more evidence gates require investigation")
    if inputs.water_quality.decision_status is DecisionStatus.HOLD_FOR_TESTING:
        reasons.append("water-quality evidence requires further testing")
    if inputs.treatment.decision_status is DecisionStatus.HOLD_FOR_TESTING:
        reasons.append("treatment route requires further evidence")
    if inputs.energy.decision_status is DecisionStatus.HOLD_FOR_TESTING:
        reasons.append("energy evidence requires further testing")
    if inputs.reserve.decision_status is DecisionStatus.HOLD_FOR_TESTING:
        reasons.append("reserve evidence requires further review")
    if inputs.atmospheric_water is not None and (
        inputs.atmospheric_water.decision_status is DecisionStatus.HOLD_FOR_TESTING
    ):
        reasons.append("atmospheric-water evidence requires additional site observations")
    if inputs.recharge is not None and (
        inputs.recharge.decision_status is DecisionStatus.HOLD_FOR_TESTING
    ):
        reasons.append("managed-recharge evidence requires additional investigation")

    return tuple(_dedupe(reasons))


def _emergency_support_review(inputs: SiteReadinessInputs) -> bool:
    return (
        inputs.reserve.risk_level is RiskLevel.HIGH
        or inputs.power.risk_level is RiskLevel.HIGH
        or inputs.human_review.risk_level is RiskLevel.HIGH
    )


def _readiness_score(
    inputs: SiteReadinessInputs,
    statuses: tuple[DecisionStatus, ...],
) -> int:
    score = 100

    score -= 35 * sum(status is DecisionStatus.BLOCK for status in statuses)
    score -= 15 * sum(status is DecisionStatus.HOLD_FOR_TESTING for status in statuses)

    for risk in _risks(inputs):
        if risk is RiskLevel.CRITICAL:
            score -= 30
        elif risk is RiskLevel.HIGH:
            score -= 20
        elif risk is RiskLevel.MODERATE:
            score -= 8

    if not inputs.human_review.is_approved:
        score -= 25

    return max(0, min(100, score))


def _risks(inputs: SiteReadinessInputs) -> tuple[RiskLevel, ...]:
    risks = [
        inputs.water_quality.risk_level,
        inputs.water_use.risk_level,
        inputs.treatment.risk_level,
        inputs.energy.risk_level,
        inputs.power.risk_level,
        inputs.reserve.risk_level,
        inputs.maintenance.risk_level,
        inputs.failures.risk_level,
        inputs.infrastructure.risk_level,
        inputs.human_review.risk_level,
    ]

    if inputs.energy_portfolio is not None:
        risks.append(inputs.energy_portfolio.risk_level)
    if inputs.atmospheric_water is not None:
        risks.append(inputs.atmospheric_water.risk_level)
    if inputs.recharge is not None:
        risks.append(inputs.recharge.risk_level)

    return tuple(risks)


def _max_risk(inputs: SiteReadinessInputs) -> RiskLevel:
    risks = _risks(inputs)
    order = {
        RiskLevel.LOW: 0,
        RiskLevel.MODERATE: 1,
        RiskLevel.HIGH: 2,
        RiskLevel.CRITICAL: 3,
    }
    return max(risks, key=lambda risk: order[risk])


def max_risk(left: RiskLevel, right: RiskLevel) -> RiskLevel:
    """Return the more severe of two risk levels."""

    order = {
        RiskLevel.LOW: 0,
        RiskLevel.MODERATE: 1,
        RiskLevel.HIGH: 2,
        RiskLevel.CRITICAL: 3,
    }
    return left if order[left] >= order[right] else right


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        cleaned.append(value)
    return cleaned
