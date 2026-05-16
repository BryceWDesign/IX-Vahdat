from ix_vahdat.domain import DecisionStatus, RiskLevel
from ix_vahdat.energy import EnergyAccountingResult
from ix_vahdat.failures import FailureEvaluationResult
from ix_vahdat.infrastructure import InfrastructureHealthResult
from ix_vahdat.maintenance import MaintenanceResult
from ix_vahdat.power import PowerMode, PowerPriorityResult
from ix_vahdat.quality import WaterQualityGateResult
from ix_vahdat.reserve import EmergencyReserveResult, ReserveStatus
from ix_vahdat.review import ReviewGateResult, ReviewStatus
from ix_vahdat.site_readiness import (
    SiteReadinessClass,
    SiteReadinessInputs,
    evaluate_site_readiness,
)
from ix_vahdat.treatment import TreatmentRoute, TreatmentRoutingResult
from ix_vahdat.water_use import WaterUseAssessment, WaterUseClass


def _water_quality(
    status: DecisionStatus = DecisionStatus.ALLOW_REVIEW,
    risk: RiskLevel = RiskLevel.LOW,
) -> WaterQualityGateResult:
    return WaterQualityGateResult(
        decision_status=status,
        risk_level=risk,
        reasons=("water-quality gate passed",),
        required_actions=("human review required",),
    )


def _water_use(
    status: DecisionStatus = DecisionStatus.ALLOW_REVIEW,
    risk: RiskLevel = RiskLevel.LOW,
) -> WaterUseAssessment:
    return WaterUseAssessment(
        use_class=WaterUseClass.HYGIENE_CANDIDATE,
        decision_status=status,
        risk_level=risk,
        reasons=("water-use class is reviewable",),
        required_actions=("human review required",),
    )


def _treatment(
    status: DecisionStatus = DecisionStatus.ALLOW_REVIEW,
    risk: RiskLevel = RiskLevel.LOW,
) -> TreatmentRoutingResult:
    return TreatmentRoutingResult(
        route=TreatmentRoute.PASS_TO_REVIEW,
        decision_status=status,
        risk_level=risk,
        reasons=("treatment route is reviewable",),
        required_actions=("human review required",),
    )


def _energy(
    status: DecisionStatus = DecisionStatus.ALLOW_REVIEW,
    risk: RiskLevel = RiskLevel.LOW,
) -> EnergyAccountingResult:
    return EnergyAccountingResult(
        decision_status=status,
        risk_level=risk,
        energy_input_wh=1_000.0,
        energy_per_liter_wh_l=500.0,
        reasons=("energy evidence is reviewable",),
        required_actions=("human review required",),
    )


def _power(
    status: DecisionStatus = DecisionStatus.ALLOW_REVIEW,
    risk: RiskLevel = RiskLevel.LOW,
    mode: PowerMode = PowerMode.NORMAL,
) -> PowerPriorityResult:
    return PowerPriorityResult(
        mode=mode,
        decision_status=status,
        risk_level=risk,
        allowed_loads=("evidence_logger", "water_quality_sensors"),
        shed_loads=(),
        reasons=("power evidence is reviewable",),
        required_actions=("human review required",),
    )


def _reserve(
    status: DecisionStatus = DecisionStatus.ALLOW_REVIEW,
    risk: RiskLevel = RiskLevel.LOW,
) -> EmergencyReserveResult:
    return EmergencyReserveResult(
        status=ReserveStatus.NORMAL,
        decision_status=status,
        risk_level=risk,
        allowed_release_l=0.0,
        protected_reserve_l=100.0,
        post_release_storage_l=300.0,
        reasons=("reserve evidence is reviewable",),
        required_actions=("human review required",),
    )


def _maintenance(
    status: DecisionStatus = DecisionStatus.ALLOW_REVIEW,
    risk: RiskLevel = RiskLevel.LOW,
    ready: bool = True,
) -> MaintenanceResult:
    return MaintenanceResult(
        decision_status=status,
        risk_level=risk,
        ready_items=("filter-1",) if ready else (),
        due_soon_items=(),
        blocked_items=() if ready else ("filter-1",),
        reasons=("maintenance evidence is reviewable",),
        required_actions=("human review required",),
    )


def _failures(
    status: DecisionStatus = DecisionStatus.ALLOW_REVIEW,
    risk: RiskLevel = RiskLevel.LOW,
    fail_closed: bool = False,
) -> FailureEvaluationResult:
    return FailureEvaluationResult(
        decision_status=status,
        risk_level=risk,
        active_failures=("failure-1",) if fail_closed else (),
        blocked_failures=("failure-1",) if fail_closed else (),
        warning_failures=(),
        reasons=("failure registry evaluated",),
        required_actions=("human review required",),
    )


def _infrastructure(
    status: DecisionStatus = DecisionStatus.ALLOW_REVIEW,
    risk: RiskLevel = RiskLevel.LOW,
    ready: bool = True,
) -> InfrastructureHealthResult:
    return InfrastructureHealthResult(
        decision_status=status,
        risk_level=risk,
        normal_assets=("tank-1",) if ready else (),
        watch_assets=(),
        blocked_assets=() if ready else ("tank-1",),
        reasons=("infrastructure evidence is reviewable",),
        required_actions=("human review required",),
    )


def _review(approved: bool = True, risk: RiskLevel = RiskLevel.LOW) -> ReviewGateResult:
    return ReviewGateResult(
        status=ReviewStatus.APPROVED_FOR_LIMITED_USE if approved else ReviewStatus.NOT_REVIEWED,
        decision_status=DecisionStatus.ALLOW_REVIEW if approved else DecisionStatus.HOLD_FOR_TESTING,
        risk_level=risk,
        reviewer=None if not approved else object(),  # type: ignore[arg-type]
        reasons=("review state recorded",),
        required_actions=("human review required",),
    )


def _inputs(**overrides: object) -> SiteReadinessInputs:
    values = {
        "water_quality": _water_quality(),
        "water_use": _water_use(),
        "treatment": _treatment(),
        "energy": _energy(),
        "power": _power(),
        "reserve": _reserve(),
        "maintenance": _maintenance(),
        "failures": _failures(),
        "infrastructure": _infrastructure(),
        "human_review": _review(),
        "energy_portfolio": None,
        "atmospheric_water": None,
        "recharge": None,
    }
    values.update(overrides)
    return SiteReadinessInputs(**values)  # type: ignore[arg-type]


def test_limited_field_review_when_all_required_gates_are_reviewable() -> None:
    result = evaluate_site_readiness(_inputs())

    assert result.readiness_class is SiteReadinessClass.LIMITED_FIELD_REVIEW
    assert result.decision_status is DecisionStatus.ALLOW_REVIEW
    assert result.risk_level is RiskLevel.LOW
    assert result.readiness_score == 100
    assert result.may_continue_to_limited_review is True
    assert "site evidence supports limited human-reviewed field evaluation" in result.reasons


def test_blocked_when_any_upstream_gate_blocks() -> None:
    result = evaluate_site_readiness(
        _inputs(water_quality=_water_quality(DecisionStatus.BLOCK, RiskLevel.CRITICAL))
    )

    assert result.readiness_class is SiteReadinessClass.BLOCKED
    assert result.decision_status is DecisionStatus.BLOCK
    assert result.risk_level is RiskLevel.CRITICAL
    assert result.readiness_score == 0
    assert "one or more upstream gates are blocked" in result.reasons
    assert "water-quality risk is critical" in result.reasons


def test_service_required_when_maintenance_blocks() -> None:
    result = evaluate_site_readiness(
        _inputs(
            maintenance=_maintenance(
                DecisionStatus.HOLD_FOR_TESTING,
                RiskLevel.HIGH,
                ready=False,
            )
        )
    )

    assert result.readiness_class is SiteReadinessClass.SERVICE_REQUIRED
    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.risk_level is RiskLevel.HIGH
    assert result.readiness_score <= 30
    assert "maintenance blockers are present" in result.reasons


def test_service_required_when_failure_registry_is_fail_closed() -> None:
    result = evaluate_site_readiness(
        _inputs(
            failures=_failures(
                DecisionStatus.HOLD_FOR_TESTING,
                RiskLevel.HIGH,
                fail_closed=True,
            )
        )
    )

    assert result.readiness_class is SiteReadinessClass.SERVICE_REQUIRED
    assert "failure registry is in fail-closed posture" in result.reasons


def test_service_required_when_infrastructure_not_ready() -> None:
    result = evaluate_site_readiness(
        _inputs(
            infrastructure=_infrastructure(
                DecisionStatus.HOLD_FOR_TESTING,
                RiskLevel.HIGH,
                ready=False,
            )
        )
    )

    assert result.readiness_class is SiteReadinessClass.SERVICE_REQUIRED
    assert "infrastructure-health blockers are present" in result.reasons


def test_service_required_when_power_is_in_safe_hold() -> None:
    result = evaluate_site_readiness(
        _inputs(
            power=_power(
                DecisionStatus.HOLD_FOR_TESTING,
                RiskLevel.HIGH,
                PowerMode.SAFE_HOLD,
            )
        )
    )

    assert result.readiness_class is SiteReadinessClass.SERVICE_REQUIRED
    assert "power system requires safe-hold or service posture" in result.reasons


def test_investigation_required_when_quality_needs_testing() -> None:
    result = evaluate_site_readiness(
        _inputs(
            water_quality=_water_quality(
                DecisionStatus.HOLD_FOR_TESTING,
                RiskLevel.HIGH,
            )
        )
    )

    assert result.readiness_class is SiteReadinessClass.INVESTIGATION_REQUIRED
    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.risk_level is RiskLevel.HIGH
    assert result.readiness_score <= 50
    assert "water-quality evidence requires further testing" in result.reasons


def test_bench_only_when_human_review_has_not_approved_limited_field_use() -> None:
    result = evaluate_site_readiness(_inputs(human_review=_review(approved=False)))

    assert result.readiness_class is SiteReadinessClass.BENCH_ONLY
    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.risk_level is RiskLevel.HIGH
    assert result.readiness_score <= 55
    assert "human review has not approved limited field use" in result.reasons


def test_emergency_support_review_when_reviewable_but_high_risk_reserve_exists() -> None:
    result = evaluate_site_readiness(
        _inputs(reserve=_reserve(DecisionStatus.ALLOW_REVIEW, RiskLevel.HIGH))
    )

    assert result.readiness_class is SiteReadinessClass.EMERGENCY_SUPPORT_REVIEW
    assert result.decision_status is DecisionStatus.ALLOW_REVIEW
    assert result.risk_level is RiskLevel.HIGH
    assert result.readiness_score <= 75
    assert result.may_continue_to_limited_review is True
    assert "site may continue only to emergency support review under explicit human authority" in (
        result.reasons
    )


def test_emergency_support_review_when_power_is_high_risk_but_reviewable() -> None:
    result = evaluate_site_readiness(
        _inputs(power=_power(DecisionStatus.ALLOW_REVIEW, RiskLevel.HIGH, PowerMode.CONSERVE))
    )

    assert result.readiness_class is SiteReadinessClass.EMERGENCY_SUPPORT_REVIEW
    assert result.decision_status is DecisionStatus.ALLOW_REVIEW
    assert result.risk_level is RiskLevel.HIGH


def test_score_drops_for_moderate_risk_even_when_reviewable() -> None:
    result = evaluate_site_readiness(
        _inputs(energy=_energy(DecisionStatus.ALLOW_REVIEW, RiskLevel.MODERATE))
    )

    assert result.readiness_class is SiteReadinessClass.LIMITED_FIELD_REVIEW
    assert result.decision_status is DecisionStatus.ALLOW_REVIEW
    assert result.risk_level is RiskLevel.MODERATE
    assert result.readiness_score == 92
