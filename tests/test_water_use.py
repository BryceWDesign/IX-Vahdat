from datetime import UTC, datetime

import pytest

from ix_vahdat.domain import DecisionStatus, EvidenceQuality, Measurement, RiskLevel, SensorStatus
from ix_vahdat.water_use import WaterQualitySnapshot, WaterUseClass, classify_water_use


def _measurement(name: str, value: float, unit: str = "unit") -> Measurement:
    return Measurement(
        name=name,
        value=value,
        unit=unit,
        source_id=f"{name}-sensor",
        timestamp=datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC),
    )


def _snapshot(
    *,
    ph: float = 7.2,
    turbidity: float = 0.6,
    conductivity: float = 650.0,
    e_coli_present: bool | None = False,
    chemical_screen_passed: bool | None = True,
    disinfection_verified: bool = True,
) -> WaterQualitySnapshot:
    return WaterQualitySnapshot(
        ph=_measurement("ph", ph, "pH"),
        turbidity_ntu=_measurement("turbidity", turbidity, "NTU"),
        conductivity_us_cm=_measurement("conductivity", conductivity, "uS/cm"),
        e_coli_present=e_coli_present,
        chemical_screen_passed=chemical_screen_passed,
        disinfection_verified=disinfection_verified,
    )


def test_classifies_drinking_candidate_only_with_complete_supporting_evidence() -> None:
    assessment = classify_water_use(_snapshot())

    assert assessment.use_class is WaterUseClass.DRINKING_CANDIDATE
    assert assessment.decision_status is DecisionStatus.ALLOW_REVIEW
    assert assessment.risk_level is RiskLevel.LOW
    assert assessment.requires_human_review is True
    assert "document human reviewer approval before any drinking-water claim" in (
        assessment.required_actions
    )


def test_missing_measurements_hold_for_testing() -> None:
    assessment = classify_water_use(
        WaterQualitySnapshot(
            ph=_measurement("ph", 7.0, "pH"),
            turbidity_ntu=None,
            conductivity_us_cm=_measurement("conductivity", 700.0, "uS/cm"),
        )
    )

    assert assessment.use_class is WaterUseClass.UNSAFE_HOLD
    assert assessment.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert assessment.risk_level is RiskLevel.HIGH
    assert "missing required measurement: turbidity_ntu" in assessment.reasons


def test_stale_sensor_data_holds_for_testing() -> None:
    assessment = classify_water_use(
        WaterQualitySnapshot(
            ph=Measurement(
                name="ph",
                value=7.1,
                unit="pH",
                source_id="ph-sensor",
                timestamp=datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC),
                sensor_status=SensorStatus.STALE,
            ),
            turbidity_ntu=_measurement("turbidity", 0.5, "NTU"),
            conductivity_us_cm=_measurement("conductivity", 500.0, "uS/cm"),
        )
    )

    assert assessment.use_class is WaterUseClass.UNSAFE_HOLD
    assert assessment.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert "ph sensor status is stale" in assessment.reasons


def test_conflicting_evidence_holds_for_testing() -> None:
    assessment = classify_water_use(
        WaterQualitySnapshot(
            ph=Measurement(
                name="ph",
                value=7.1,
                unit="pH",
                source_id="ph-sensor",
                timestamp=datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC),
                quality=EvidenceQuality.CONFLICTING,
            ),
            turbidity_ntu=_measurement("turbidity", 0.5, "NTU"),
            conductivity_us_cm=_measurement("conductivity", 500.0, "uS/cm"),
        )
    )

    assert assessment.use_class is WaterUseClass.UNSAFE_HOLD
    assert assessment.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert "ph evidence quality is conflicting" in assessment.reasons


def test_pathogen_indicator_blocks_distribution() -> None:
    assessment = classify_water_use(_snapshot(e_coli_present=True))

    assert assessment.use_class is WaterUseClass.UNSAFE_HOLD
    assert assessment.decision_status is DecisionStatus.BLOCK
    assert assessment.risk_level is RiskLevel.CRITICAL
    assert "pathogen indicator present" in assessment.reasons


def test_failed_chemical_screen_blocks_distribution() -> None:
    assessment = classify_water_use(_snapshot(chemical_screen_passed=False))

    assert assessment.use_class is WaterUseClass.UNSAFE_HOLD
    assert assessment.decision_status is DecisionStatus.BLOCK
    assert assessment.risk_level is RiskLevel.CRITICAL
    assert "chemical screen failed" in assessment.reasons


def test_missing_lab_evidence_prevents_drinking_candidate() -> None:
    assessment = classify_water_use(
        _snapshot(
            e_coli_present=None,
            chemical_screen_passed=None,
            disinfection_verified=False,
        )
    )

    assert assessment.use_class is WaterUseClass.HYGIENE_CANDIDATE
    assert assessment.decision_status is DecisionStatus.ALLOW_REVIEW
    assert "pathogen evidence missing; do not classify as drinking candidate" in (
        assessment.required_actions
    )


def test_classifies_irrigation_candidate_when_hygiene_limits_are_exceeded() -> None:
    assessment = classify_water_use(
        _snapshot(
            ph=7.6,
            turbidity=35.0,
            conductivity=2_200.0,
            e_coli_present=None,
            chemical_screen_passed=None,
            disinfection_verified=False,
        )
    )

    assert assessment.use_class is WaterUseClass.IRRIGATION_CANDIDATE
    assert assessment.decision_status is DecisionStatus.ALLOW_REVIEW


def test_classifies_utility_water_when_only_broad_limits_are_met() -> None:
    assessment = classify_water_use(
        _snapshot(
            ph=10.0,
            turbidity=120.0,
            conductivity=4_500.0,
            e_coli_present=None,
            chemical_screen_passed=None,
            disinfection_verified=False,
        )
    )

    assert assessment.use_class is WaterUseClass.UTILITY_WATER
    assert assessment.decision_status is DecisionStatus.ALLOW_REVIEW
    assert "do not use for drinking, hygiene, or food-crop irrigation" in (
        assessment.required_actions
    )


@pytest.mark.parametrize(
    ("ph", "turbidity", "conductivity"),
    [
        (4.8, 5.0, 800.0),
        (11.0, 5.0, 800.0),
        (7.0, 5.0, 5_500.0),
    ],
)
def test_blocks_when_all_use_class_limits_are_exceeded(
    ph: float,
    turbidity: float,
    conductivity: float,
) -> None:
    assessment = classify_water_use(
        _snapshot(
            ph=ph,
            turbidity=turbidity,
            conductivity=conductivity,
            e_coli_present=None,
            chemical_screen_passed=None,
            disinfection_verified=False,
        )
    )

    assert assessment.use_class is WaterUseClass.UNSAFE_HOLD
    assert assessment.decision_status is DecisionStatus.BLOCK
