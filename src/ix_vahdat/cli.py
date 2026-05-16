"""Command-line demo for IX-Vahdat.

The CLI intentionally provides a synthetic proof-of-concept demonstration only.
It does not read live sensors, control hardware, certify water, authorize
distribution, or approve deployment.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from typing import Any, Sequence

from ix_vahdat.asset_checks import (
    CollectionPanelKind,
    PanelHealthInput,
    PipeHealthInput,
    PumpHealthInput,
    TankHealthInput,
    build_panel_observation,
    build_pipe_observation,
    build_pump_observation,
    build_tank_observation,
)
from ix_vahdat.atmospheric import (
    AtmosphericSiteConstraints,
    AtmosphericWaterClimate,
    AtmosphericWaterInputs,
)
from ix_vahdat.awh import triage_atmospheric_water
from ix_vahdat.domain import (
    Coordinates,
    DecisionStatus,
    EvidenceQuality,
    Measurement,
    RiskLevel,
    SensorStatus,
    SiteContext,
)
from ix_vahdat.energy import EnergySnapshot, EnergySource, calculate_energy_accounting
from ix_vahdat.energy_profile import (
    WaterEnergyProfile,
    WaterSupportPath,
    evaluate_energy_portfolio,
)
from ix_vahdat.failures import (
    FailureCategory,
    FailureMode,
    FailureRegistry,
    FailureSeverity,
    evaluate_failure_modes,
)
from ix_vahdat.infrastructure import InfrastructureSnapshot, evaluate_infrastructure_health
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
    PowerSystemSnapshot,
    evaluate_power_priority,
)
from ix_vahdat.quality import evaluate_water_quality_gate
from ix_vahdat.receipts import EvidenceInput, ReceiptKind, create_receipt
from ix_vahdat.reserve import EmergencyReserveSnapshot, evaluate_emergency_reserve
from ix_vahdat.review import ReviewDecision, ReviewerRecord, require_human_review
from ix_vahdat.site_readiness import SiteReadinessInputs, evaluate_site_readiness
from ix_vahdat.treatment import TreatmentSystemSnapshot, route_treatment_batch
from ix_vahdat.water_use import WaterQualitySnapshot, WaterUseClass, classify_water_use


DEMO_TIMESTAMP = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)


def build_demo_payload() -> dict[str, Any]:
    """Build a deterministic synthetic IX-Vahdat demo payload.

    The payload is deliberately marked as synthetic. It is useful for testing
    the proof-of-concept flow and showing the shape of review records without
    pretending to represent a real deployment.
    """

    site = SiteContext(
        site_id="synthetic-demo-node",
        name="Synthetic Community Water Node",
        operator="synthetic local review team",
        coordinates=Coordinates(latitude=35.0, longitude=51.0),
        tags=("synthetic-demo", "humanitarian-water-resilience"),
        metadata={
            "synthetic_demo": True,
            "field_deployment": False,
            "claim_boundary": "software proof-of-concept only",
        },
    )

    quality_snapshot = _quality_snapshot()
    water_quality = evaluate_water_quality_gate(
        quality_snapshot,
        evaluated_at=DEMO_TIMESTAMP,
    )
    water_use = classify_water_use(quality_snapshot)

    treatment = route_treatment_batch(
        quality_gate=water_quality,
        system=TreatmentSystemSnapshot(
            pretreatment_available=True,
            filtration_available=True,
            disinfection_available=True,
            storage_clean=True,
            recirculation_available=True,
            waste_hold_available=True,
            filter_pressure_delta_kpa=40.0,
            flow_rate_l_min=2.0,
            tank_capacity_remaining_fraction=0.60,
        ),
    )

    energy = calculate_energy_accounting(
        EnergySnapshot(
            source=EnergySource.SOLAR,
            evidence_quality=EvidenceQuality.MEASURED,
            runtime_hours=2.0,
            average_power_w=300.0,
            water_output_l=10.0,
            critical_load_power_w=70.0,
            available_power_w=500.0,
            battery_state_fraction=0.80,
            reserve_battery_fraction=0.25,
            measurement_notes="synthetic boundary measurement for CLI demo",
        ),
        operation_label="synthetic treatment-and-collection demo",
        is_atmospheric_water_operation=False,
    )

    power = evaluate_power_priority(
        PowerSystemSnapshot(
            available_power_w=600.0,
            battery_state_fraction=0.80,
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
                    name="telemetry_radio",
                    priority=LoadPriority.IMPORTANT,
                    power_w=15.0,
                ),
                PowerLoad(
                    name="treatment_pump",
                    priority=LoadPriority.DEFERRABLE,
                    power_w=80.0,
                ),
            ),
        )
    )

    reserve = evaluate_emergency_reserve(
        EmergencyReserveSnapshot(
            stored_water_l=300.0,
            protected_reserve_l=100.0,
            daily_priority_demand_l=50.0,
            requested_release_l=0.0,
            requested_use_label="synthetic no-release reserve check",
            water_use_class=WaterUseClass.HYGIENE_CANDIDATE,
            quality_gate_passed=True,
            treatment_route_reviewed=True,
            storage_clean=True,
            tank_integrity_verified=True,
            storage_age_hours=12.0,
            emergency_request_declared=False,
            notes="synthetic reserve check; no release requested",
        )
    )

    maintenance = evaluate_maintenance(
        MaintenanceSnapshot(
            items=(
                MaintenanceItem(
                    item_id="filter-1",
                    label="cartridge filter",
                    category=MaintenanceCategory.FILTER,
                    state=MaintenanceState.OK,
                    critical=True,
                    evidence_quality=EvidenceQuality.MEASURED,
                    sensor_status=SensorStatus.OK,
                    hours_since_service=10.0,
                    service_interval_hours=100.0,
                ),
                MaintenanceItem(
                    item_id="tank-1",
                    label="storage tank",
                    category=MaintenanceCategory.STORAGE_TANK,
                    state=MaintenanceState.OK,
                    critical=True,
                    evidence_quality=EvidenceQuality.MEASURED,
                    sensor_status=SensorStatus.OK,
                    hours_since_service=12.0,
                    service_interval_hours=168.0,
                ),
            )
        )
    )

    failures = evaluate_failure_modes(
        FailureRegistry(
            failures=(
                FailureMode(
                    failure_id="no-active-failure",
                    label="no active synthetic failure",
                    category=FailureCategory.OTHER,
                    severity=FailureSeverity.LOW,
                    active=False,
                    evidence_quality=EvidenceQuality.MEASURED,
                    sensor_status=SensorStatus.OK,
                    source_id="synthetic-demo",
                    required_actions=("continue monitoring failure registry",),
                    detected_at=DEMO_TIMESTAMP,
                ),
            )
        )
    )

    infrastructure = evaluate_infrastructure_health(
        InfrastructureSnapshot(
            observations=(
                build_tank_observation(
                    TankHealthInput(
                        asset_id="tank-1",
                        label="synthetic storage tank",
                        observed_at=DEMO_TIMESTAMP,
                        evidence_quality=EvidenceQuality.MEASURED,
                        sensor_status=SensorStatus.OK,
                        leak_detected=False,
                        storage_clean=True,
                        tank_integrity_verified=True,
                    )
                ),
                build_pipe_observation(
                    PipeHealthInput(
                        asset_id="pipe-1",
                        label="synthetic feed pipe",
                        observed_at=DEMO_TIMESTAMP,
                        evidence_quality=EvidenceQuality.MEASURED,
                        sensor_status=SensorStatus.OK,
                        leak_detected=False,
                    )
                ),
                build_pump_observation(
                    PumpHealthInput(
                        asset_id="pump-1",
                        label="synthetic transfer pump",
                        observed_at=DEMO_TIMESTAMP,
                        evidence_quality=EvidenceQuality.MEASURED,
                        sensor_status=SensorStatus.OK,
                        operational=True,
                        leak_detected=False,
                    )
                ),
                build_panel_observation(
                    PanelHealthInput(
                        asset_id="panel-1",
                        label="synthetic AWH panel",
                        panel_kind=CollectionPanelKind.AWH_PANEL,
                        observed_at=DEMO_TIMESTAMP,
                        evidence_quality=EvidenceQuality.MEASURED,
                        sensor_status=SensorStatus.OK,
                        mounted_securely=True,
                        collection_surface_clean=True,
                        electrical_or_collection_fault_detected=False,
                    )
                ),
            )
        ),
        evaluated_at=DEMO_TIMESTAMP,
    )

    atmospheric_water = triage_atmospheric_water(
        AtmosphericWaterInputs(
            observed_at=DEMO_TIMESTAMP,
            climate=AtmosphericWaterClimate(
                relative_humidity_percent=82.0,
                temperature_c=22.0,
                dew_point_c=18.8,
                wind_speed_m_s=2.0,
                solar_irradiance_w_m2=500.0,
                observed_fog=False,
                air_quality_index=70.0,
                dust_risk_fraction=0.1,
            ),
            constraints=AtmosphericSiteConstraints(
                daily_priority_water_demand_l=250.0,
                available_electric_power_w=1_200.0,
                battery_state_fraction=0.75,
                available_collection_area_m2=20.0,
                maintenance_capacity_fraction=0.8,
                storage_capacity_remaining_l=500.0,
                potable_claim_allowed_by_local_review=False,
            ),
        )
    )

    energy_portfolio = evaluate_energy_portfolio(
        (
            WaterEnergyProfile(
                path=WaterSupportPath.REUSE_TREATMENT,
                label="synthetic reuse-treatment path",
                produced_water_l=100.0,
                energy_input_wh=25_000.0,
                evidence_quality=EvidenceQuality.MEASURED,
                safety_gate_passed=True,
                maintenance_ready=True,
                notes="synthetic portfolio example",
            ),
            WaterEnergyProfile(
                path=WaterSupportPath.FOG_OR_DEW_CAPTURE,
                label="synthetic passive fog/dew path",
                produced_water_l=5.0,
                energy_input_wh=0.0,
                evidence_quality=EvidenceQuality.ESTIMATED,
                safety_gate_passed=True,
                maintenance_ready=True,
                uses_passive_environmental_energy=True,
                notes="synthetic passive path; not a yield claim",
            ),
        )
    )

    reviewer = ReviewerRecord(
        reviewer_id="synthetic-reviewer",
        reviewer_name="Synthetic Reviewer",
        role="demo reviewer",
        organization="synthetic local review team",
        reviewed_at=DEMO_TIMESTAMP,
        decision=ReviewDecision.APPROVE_LIMITED_USE,
        authority_basis="synthetic proof-of-concept review only",
        notes="approved limited software-demo review; no field action authorized",
    )
    human_review = require_human_review(
        upstream_status=DecisionStatus.ALLOW_REVIEW,
        upstream_risk=RiskLevel.LOW,
        action_label="synthetic limited field-review package",
        reviewer=reviewer,
    )

    site_readiness = evaluate_site_readiness(
        SiteReadinessInputs(
            water_quality=water_quality,
            water_use=water_use,
            treatment=treatment,
            energy=energy,
            power=power,
            reserve=reserve,
            maintenance=maintenance,
            failures=failures,
            infrastructure=infrastructure,
            human_review=human_review,
            energy_portfolio=energy_portfolio,
            atmospheric_water=atmospheric_water,
            recharge=None,
        )
    )

    receipts = _build_demo_receipts(
        site=site,
        quality_snapshot=quality_snapshot,
        site_readiness_score=site_readiness.readiness_score,
        site_readiness_class=site_readiness.readiness_class.value,
    )

    return {
        "project": "IX-Vahdat",
        "mode": "synthetic_demo",
        "generated_at": DEMO_TIMESTAMP.isoformat(),
        "non_claims": [
            "not a certified drinking-water system",
            "not a potable-water certification",
            "not a permit substitute",
            "not a public-health approval",
            "not an autonomous physical-control system",
            "not a field-deployment authorization",
        ],
        "site": {
            "site_id": site.site_id,
            "name": site.name,
            "operator": site.operator,
            "coordinates": {
                "latitude": site.coordinates.latitude if site.coordinates else None,
                "longitude": site.coordinates.longitude if site.coordinates else None,
            },
            "metadata": dict(site.metadata),
        },
        "summary": {
            "water_quality_status": water_quality.decision_status.value,
            "water_use_class": water_use.use_class.value,
            "treatment_route": treatment.route.value,
            "energy_status": energy.decision_status.value,
            "power_mode": power.mode.value,
            "reserve_status": reserve.status.value,
            "maintenance_status": maintenance.decision_status.value,
            "failure_status": failures.decision_status.value,
            "infrastructure_status": infrastructure.decision_status.value,
            "top_atmospheric_water_mode": atmospheric_water.top_mode.value,
            "preferred_energy_path": (
                energy_portfolio.preferred_review_path.value
                if energy_portfolio.preferred_review_path is not None
                else None
            ),
            "human_review_status": human_review.status.value,
            "site_readiness_class": site_readiness.readiness_class.value,
            "site_readiness_score": site_readiness.readiness_score,
        },
        "required_actions": list(site_readiness.required_actions),
        "receipts": [receipt.to_dict() for receipt in receipts],
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Run the IX-Vahdat CLI."""

    parser = argparse.ArgumentParser(
        prog="ix-vahdat",
        description="IX-Vahdat proof-of-concept command-line tools.",
    )
    subparsers = parser.add_subparsers(dest="command")

    demo_parser = subparsers.add_parser(
        "demo",
        help="print a deterministic synthetic review-only demo payload",
    )
    demo_parser.add_argument(
        "--pretty",
        action="store_true",
        help="pretty-print JSON output",
    )

    parsed = parser.parse_args(list(argv) if argv is not None else None)

    if parsed.command is None:
        parsed = parser.parse_args(["demo"])

    if parsed.command == "demo":
        payload = build_demo_payload()
        if parsed.pretty:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
        return 0

    parser.error(f"unsupported command: {parsed.command}")
    return 2


def _quality_snapshot() -> WaterQualitySnapshot:
    return WaterQualitySnapshot(
        ph=_measurement("ph", 7.2, "pH"),
        turbidity_ntu=_measurement("turbidity", 0.6, "NTU"),
        conductivity_us_cm=_measurement("conductivity", 650.0, "uS/cm"),
        temperature_c=_measurement("temperature", 20.0, "C"),
        e_coli_present=False,
        chemical_screen_passed=True,
        disinfection_verified=True,
    )


def _measurement(name: str, value: float, unit: str) -> Measurement:
    return Measurement(
        name=name,
        value=value,
        unit=unit,
        source_id=f"synthetic-{name}-source",
        timestamp=DEMO_TIMESTAMP,
        quality=EvidenceQuality.MEASURED,
        sensor_status=SensorStatus.OK,
        notes="synthetic CLI demo measurement; not field data",
    )


def _build_demo_receipts(
    *,
    site: SiteContext,
    quality_snapshot: WaterQualitySnapshot,
    site_readiness_score: int,
    site_readiness_class: str,
) -> tuple:
    evidence_inputs = tuple(
        EvidenceInput.from_measurement(measurement)
        for measurement in quality_snapshot.physical_measurements()
        if measurement is not None
    )

    water_receipt = create_receipt(
        kind=ReceiptKind.WATER_USE_ASSESSMENT,
        created_at=DEMO_TIMESTAMP,
        site=site,
        summary="synthetic water-use assessment receipt",
        decision_status=DecisionStatus.ALLOW_REVIEW,
        risk_level=RiskLevel.LOW,
        evidence_inputs=evidence_inputs,
        reasons=("synthetic water-quality readings passed demo triage checks",),
        required_actions=(
            "do not treat this synthetic receipt as field evidence",
            "repeat with real measurements before any field review",
            "human review required before any water-use claim",
        ),
        thresholds={
            "synthetic_demo": True,
            "potable_certification": False,
        },
        uncertainty_notes=("synthetic deterministic CLI example only",),
        reviewer_status="synthetic_demo",
        reviewer_id="synthetic-reviewer",
        metadata={
            "site_readiness_score": site_readiness_score,
            "site_readiness_class": site_readiness_class,
        },
    )

    readiness_receipt = create_receipt(
        kind=ReceiptKind.SITE_READINESS,
        created_at=DEMO_TIMESTAMP,
        site=site,
        summary="synthetic site-readiness receipt",
        decision_status=DecisionStatus.ALLOW_REVIEW,
        risk_level=RiskLevel.MODERATE,
        evidence_inputs=(
            EvidenceInput(
                name="site_readiness_score",
                value=float(site_readiness_score),
                unit="score_0_to_100",
                source_id="synthetic-site-readiness-engine",
                quality=EvidenceQuality.ESTIMATED.value,
                sensor_status=SensorStatus.OK.value,
                timestamp=DEMO_TIMESTAMP,
                notes="synthetic aggregated score; not field certification",
            ),
        ),
        reasons=("synthetic site-readiness flow completed for software demonstration",),
        required_actions=(
            "do not treat this as deployment approval",
            "replace synthetic demo inputs with verified local evidence",
            "obtain qualified human review before any field action",
        ),
        thresholds={
            "synthetic_demo": True,
            "field_deployment_authorized": False,
        },
        uncertainty_notes=("aggregated from deterministic synthetic demo inputs",),
        reviewer_status="synthetic_demo",
        reviewer_id="synthetic-reviewer",
        metadata={"site_readiness_class": site_readiness_class},
    )

    return (water_receipt, readiness_receipt)


if __name__ == "__main__":
    raise SystemExit(main())
