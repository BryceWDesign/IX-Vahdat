from datetime import UTC, datetime

from ix_vahdat.domain import DecisionStatus, EvidenceQuality, Measurement, RiskLevel, SensorStatus
from ix_vahdat.failures import (
    FailureCategory,
    FailureMode,
    FailureRegistry,
    FailureSeverity,
    evaluate_failure_modes,
)
from ix_vahdat.infrastructure import (
    AssetHealthState,
    InfrastructureAssetType,
    InfrastructureObservation,
    InfrastructureSnapshot,
    evaluate_infrastructure_health,
)
from ix_vahdat.maintenance import (
    MaintenanceCategory,
    MaintenanceItem,
    MaintenanceSnapshot,
    MaintenanceState,
    evaluate_maintenance,
)
from ix_vahdat.power import (
    LoadPriority,
    PowerLoad,
    PowerMode,
    PowerSystemSnapshot,
    evaluate_power_priority,
)
from ix_vahdat.quality import WaterQualityGateResult, evaluate_water_quality_gate
from ix_vahdat.recharge import (
    MARSiteObservation,
    MARWaterSource,
    RechargeMethod,
    evaluate_mar_readiness,
)
from ix_vahdat.reserve import EmergencyReserveSnapshot, ReserveStatus, evaluate_emergency_reserve
from ix_vahdat.review import ReviewStatus, require_human_review
from ix_vahdat.treatment import TreatmentRoute, TreatmentSystemSnapshot, route_treatment_batch
from ix_vahdat.water_use import WaterQualitySnapshot, WaterUseClass, classify_water_use


NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)


def _measurement(name: str, value: float, unit: str) -> Measurement:
    return Measurement(
        name=name,
        value=value,
        unit=unit,
        source_id=f"{name}-sensor",
        timestamp=NOW,
        quality=EvidenceQuality.MEASURED,
        sensor_status=SensorStatus.OK,
    )


def test_water_quality_and_water_use_gates_fail_closed_on_missing_core_evidence() -> None:
    snapshot = WaterQualitySnapshot(
        ph=_measurement("ph", 7.1, "pH"),
        turbidity_ntu=None,
        conductivity_us_cm=_measurement("conductivity", 650.0, "uS/cm"),
        e_coli_present=False,
        chemical_screen_passed=True,
        disinfection_verified=True,
    )

    quality_result = evaluate_water_quality_gate(snapshot, evaluated_at=NOW)
    use_result = classify_water_use(snapshot)

    assert quality_result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert quality_result.risk_level is RiskLevel.HIGH
    assert quality_result.may_continue_to_classification is False
    assert "missing turbidity measurement" in quality_result.reasons

    assert use_result.use_class is WaterUseClass.UNSAFE_HOLD
    assert use_result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert "missing required measurement: turbidity_ntu" in use_result.reasons


def test_human_review_gate_prevents_action_without_explicit_reviewer() -> None:
    result = require_human_review(
        upstream_status=DecisionStatus.ALLOW_REVIEW,
        upstream_risk=RiskLevel.LOW,
        action_label="release treated batch to reviewed storage",
        reviewer=None,
    )

    assert result.status is ReviewStatus.NOT_REVIEWED
    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.risk_level is RiskLevel.HIGH
    assert result.is_approved is False
    assert "assign qualified human reviewer" in result.required_actions


def test_treatment_gate_does_not_release_blocked_quality_condition() -> None:
    quality_gate = WaterQualityGateResult(
        decision_status=DecisionStatus.BLOCK,
        risk_level=RiskLevel.CRITICAL,
        reasons=("chemical screen failed",),
        required_actions=("block release",),
    )
    system = TreatmentSystemSnapshot(
        pretreatment_available=True,
        filtration_available=True,
        disinfection_available=True,
        storage_clean=True,
        recirculation_available=True,
        waste_hold_available=True,
        filter_pressure_delta_kpa=40.0,
        flow_rate_l_min=2.0,
        tank_capacity_remaining_fraction=0.5,
    )

    result = route_treatment_batch(quality_gate=quality_gate, system=system)

    assert result.route is TreatmentRoute.REJECT_TO_WASTE_REVIEW
    assert result.decision_status is DecisionStatus.BLOCK
    assert result.risk_level is RiskLevel.CRITICAL
    assert result.requires_human_review is True
    assert "hold for qualified chemical or disposal review" in result.required_actions


def test_failed_critical_maintenance_item_blocks_dependent_decisions() -> None:
    result = evaluate_maintenance(
        MaintenanceSnapshot(
            items=(
                MaintenanceItem(
                    item_id="uv-1",
                    label="UV disinfection lamp",
                    category=MaintenanceCategory.UV_DISINFECTION,
                    state=MaintenanceState.FAILED,
                    critical=True,
                    evidence_quality=EvidenceQuality.MEASURED,
                    sensor_status=SensorStatus.OK,
                    hours_since_service=50.0,
                    service_interval_hours=100.0,
                ),
            )
        )
    )

    assert result.decision_status is DecisionStatus.BLOCK
    assert result.risk_level is RiskLevel.CRITICAL
    assert result.maintenance_ready is False
    assert result.blocked_items == ("uv-1",)
    assert "critical item blocks dependent water-support decisions" in result.required_actions


def test_active_critical_failure_mode_forces_fail_closed_posture() -> None:
    result = evaluate_failure_modes(
        FailureRegistry(
            failures=(
                FailureMode(
                    failure_id="tank-contamination",
                    label="storage tank contamination",
                    category=FailureCategory.STORAGE,
                    severity=FailureSeverity.CRITICAL,
                    active=True,
                    evidence_quality=EvidenceQuality.MEASURED,
                    sensor_status=SensorStatus.OK,
                    source_id="tank-inspection",
                    required_actions=(
                        "block release",
                        "clean and inspect storage tank before reuse review",
                    ),
                    detected_at=NOW,
                ),
            )
        )
    )

    assert result.decision_status is DecisionStatus.BLOCK
    assert result.risk_level is RiskLevel.CRITICAL
    assert result.fail_closed is True
    assert result.active_failures == ("tank-contamination",)
    assert result.blocked_failures == ("tank-contamination",)


def test_safety_critical_infrastructure_leak_blocks_site_use() -> None:
    result = evaluate_infrastructure_health(
        InfrastructureSnapshot(
            observations=(
                InfrastructureObservation(
                    asset_id="pipe-1",
                    label="treated-water feed pipe",
                    asset_type=InfrastructureAssetType.PIPE,
                    health_state=AssetHealthState.NORMAL,
                    observed_at=NOW,
                    evidence_quality=EvidenceQuality.MEASURED,
                    sensor_status=SensorStatus.OK,
                    leak_detected=True,
                    critical_to_water_safety=True,
                ),
            )
        ),
        evaluated_at=NOW,
    )

    assert result.decision_status is DecisionStatus.BLOCK
    assert result.risk_level is RiskLevel.CRITICAL
    assert result.infrastructure_ready is False
    assert result.blocked_assets == ("pipe-1",)
    assert "treated-water feed pipe leak detected on safety-critical asset" in result.reasons


def test_power_gate_protects_safe_hold_loads_when_battery_reaches_reserve() -> None:
    result = evaluate_power_priority(
        PowerSystemSnapshot(
            available_power_w=500.0,
            battery_state_fraction=0.25,
            reserve_battery_fraction=0.25,
            loads=(
                PowerLoad(
                    name="evidence_logger",
                    priority=LoadPriority.CRITICAL,
                    power_w=20.0,
                    required_for_safe_hold=True,
                ),
                PowerLoad(
                    name="water_quality_sensors",
                    priority=LoadPriority.CRITICAL,
                    power_w=35.0,
                    required_for_safe_hold=True,
                ),
                PowerLoad(
                    name="active_condensation_awg",
                    priority=LoadPriority.NONESSENTIAL,
                    power_w=700.0,
                ),
            ),
        )
    )

    assert result.mode is PowerMode.SAFE_HOLD
    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.risk_level is RiskLevel.CRITICAL
    assert result.allowed_loads == ("evidence_logger", "water_quality_sensors")
    assert result.shed_loads == ("active_condensation_awg",)
    assert "protect emergency reserve" in result.required_actions


def test_emergency_reserve_gate_blocks_routine_breach_of_protected_reserve() -> None:
    result = evaluate_emergency_reserve(
        EmergencyReserveSnapshot(
            stored_water_l=300.0,
            protected_reserve_l=150.0,
            daily_priority_demand_l=100.0,
            requested_release_l=200.0,
            requested_use_label="routine hygiene release",
            water_use_class=WaterUseClass.HYGIENE_CANDIDATE,
            quality_gate_passed=True,
            treatment_route_reviewed=True,
            storage_clean=True,
            tank_integrity_verified=True,
            storage_age_hours=12.0,
            emergency_request_declared=False,
        )
    )

    assert result.status is ReserveStatus.SAFE_HOLD
    assert result.decision_status is DecisionStatus.BLOCK
    assert result.risk_level is RiskLevel.CRITICAL
    assert result.allowed_release_l == 0.0
    assert "requested release would breach protected emergency reserve" in result.reasons


def test_mar_gate_blocks_recharge_when_required_review_is_missing() -> None:
    result = evaluate_mar_readiness(
        source=MARWaterSource(
            source_id="treated-source-1",
            label="treated reclaimed water batch",
            water_use_class=WaterUseClass.UTILITY_WATER,
            available_volume_l=5_000.0,
            quality_gate_passed=True,
            treatment_route_reviewed=True,
            evidence_quality=EvidenceQuality.MEASURED,
            sensor_status=SensorStatus.OK,
            salinity_risk_fraction=0.2,
            contamination_risk_fraction=0.1,
        ),
        site=MARSiteObservation(
            site_id="mar-site-1",
            label="pilot infiltration basin candidate",
            method=RechargeMethod.SPREADING_BASIN,
            evidence_quality=EvidenceQuality.MEASURED,
            sensor_status=SensorStatus.OK,
            infiltration_capacity_fraction=0.75,
            groundwater_vulnerability_fraction=0.2,
            geotechnical_stability_fraction=0.8,
            subsidence_risk_fraction=0.3,
            contamination_source_distance_m=500.0,
            monitoring_well_available=True,
            local_authority_review_available=False,
            environmental_review_available=True,
            community_review_available=True,
        ),
    )

    assert result.decision_status is DecisionStatus.BLOCK
    assert result.risk_level is RiskLevel.CRITICAL
    assert "local authority review is not available" in result.reasons
    assert "do not perform managed aquifer recharge" in result.required_actions
