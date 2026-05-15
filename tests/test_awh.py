from datetime import UTC, datetime

from ix_vahdat.atmospheric import (
    AtmosphericSiteConstraints,
    AtmosphericWaterClimate,
    AtmosphericWaterInputs,
)
from ix_vahdat.awh import AWHMode, AWHTriagePolicy, triage_atmospheric_water
from ix_vahdat.domain import DecisionStatus, RiskLevel


OBSERVED_AT = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)


def _climate(**overrides: object) -> AtmosphericWaterClimate:
    values = {
        "relative_humidity_percent": 82.0,
        "temperature_c": 22.0,
        "dew_point_c": 18.8,
        "wind_speed_m_s": 2.0,
        "solar_irradiance_w_m2": 500.0,
        "observed_fog": False,
        "air_quality_index": 70.0,
        "dust_risk_fraction": 0.1,
    }
    values.update(overrides)
    return AtmosphericWaterClimate(**values)  # type: ignore[arg-type]


def _constraints(**overrides: object) -> AtmosphericSiteConstraints:
    values = {
        "daily_priority_water_demand_l": 250.0,
        "available_electric_power_w": 1_200.0,
        "battery_state_fraction": 0.75,
        "available_collection_area_m2": 20.0,
        "maintenance_capacity_fraction": 0.8,
        "storage_capacity_remaining_l": 500.0,
        "potable_claim_allowed_by_local_review": False,
    }
    values.update(overrides)
    return AtmosphericSiteConstraints(**values)  # type: ignore[arg-type]


def _inputs(
    *,
    climate: AtmosphericWaterClimate | None = None,
    constraints: AtmosphericSiteConstraints | None = None,
) -> AtmosphericWaterInputs:
    return AtmosphericWaterInputs(
        observed_at=OBSERVED_AT,
        climate=climate or _climate(),
        constraints=constraints or _constraints(),
    )


def test_router_ranks_fog_capture_first_when_fog_signal_is_present() -> None:
    result = triage_atmospheric_water(
        _inputs(
            climate=_climate(
                relative_humidity_percent=98.0,
                temperature_c=12.0,
                dew_point_c=11.2,
                wind_speed_m_s=2.5,
                observed_fog=True,
            )
        )
    )

    assert result.decision_status is DecisionStatus.ALLOW_REVIEW
    assert result.has_reviewable_mode is True
    assert result.top_mode is AWHMode.FOG_CAPTURE
    assert result.recommended_modes[0].score == 95
    assert "route collected water through quality gate before use" in (
        result.recommended_modes[0].required_actions
    )


def test_router_recommends_dew_when_dew_signal_is_present_without_fog() -> None:
    result = triage_atmospheric_water(
        _inputs(
            climate=_climate(
                relative_humidity_percent=88.0,
                temperature_c=18.0,
                dew_point_c=15.0,
                wind_speed_m_s=0.1,
                observed_fog=False,
            )
        )
    )

    assert result.decision_status is DecisionStatus.ALLOW_REVIEW
    assert result.top_mode is AWHMode.RADIATIVE_DEW


def test_router_recommends_sorbent_modes_in_low_humidity_with_solar_regeneration() -> None:
    result = triage_atmospheric_water(
        _inputs(
            climate=_climate(
                relative_humidity_percent=22.0,
                temperature_c=37.0,
                dew_point_c=10.0,
                wind_speed_m_s=1.0,
                solar_irradiance_w_m2=800.0,
                observed_fog=False,
            )
        )
    )

    modes = [option.mode for option in result.recommended_modes]

    assert result.decision_status is DecisionStatus.ALLOW_REVIEW
    assert AWHMode.MOF_ADSORPTION in modes
    assert AWHMode.SOLAR_DESORPTION in modes
    assert result.risk_level is RiskLevel.MODERATE


def test_router_recommends_hydrogel_for_moderate_humidity_with_sun() -> None:
    result = triage_atmospheric_water(
        _inputs(
            climate=_climate(
                relative_humidity_percent=45.0,
                temperature_c=31.0,
                dew_point_c=17.5,
                wind_speed_m_s=1.5,
                solar_irradiance_w_m2=700.0,
                observed_fog=False,
            )
        )
    )

    modes = [option.mode for option in result.recommended_modes]

    assert result.decision_status is DecisionStatus.ALLOW_REVIEW
    assert AWHMode.HYDROGEL_ADSORPTION in modes
    assert AWHMode.SOLAR_DESORPTION in modes


def test_router_recommends_active_condensation_when_humidity_and_power_support_it() -> None:
    result = triage_atmospheric_water(
        _inputs(
            climate=_climate(
                relative_humidity_percent=62.0,
                temperature_c=28.0,
                dew_point_c=20.0,
                wind_speed_m_s=1.0,
                solar_irradiance_w_m2=200.0,
                observed_fog=False,
            ),
            constraints=_constraints(
                available_electric_power_w=2_000.0,
                battery_state_fraction=0.8,
            ),
        )
    )

    modes = [option.mode for option in result.recommended_modes]

    assert result.decision_status is DecisionStatus.ALLOW_REVIEW
    assert AWHMode.ACTIVE_CONDENSATION in modes
    assert "complete energy-per-liter accounting" in (
        next(option for option in result.recommended_modes if option.mode is AWHMode.ACTIVE_CONDENSATION)
        .required_actions
    )


def test_router_blocks_when_no_storage_capacity_remains() -> None:
    result = triage_atmospheric_water(
        _inputs(constraints=_constraints(storage_capacity_remaining_l=0.0))
    )

    assert result.decision_status is DecisionStatus.BLOCK
    assert result.risk_level is RiskLevel.HIGH
    assert result.top_mode is AWHMode.DO_NOT_DEPLOY_AWH
    assert "no storage capacity remains for collected water" in result.reasons


def test_router_blocks_when_maintenance_capacity_is_low() -> None:
    result = triage_atmospheric_water(
        _inputs(constraints=_constraints(maintenance_capacity_fraction=0.2))
    )

    assert result.decision_status is DecisionStatus.BLOCK
    assert result.top_mode is AWHMode.DO_NOT_DEPLOY_AWH
    assert "maintenance capacity is below conservative minimum" in result.reasons


def test_router_blocks_when_air_quality_is_too_poor() -> None:
    result = triage_atmospheric_water(
        _inputs(climate=_climate(air_quality_index=180.0))
    )

    assert result.decision_status is DecisionStatus.BLOCK
    assert result.top_mode is AWHMode.DO_NOT_DEPLOY_AWH
    assert "air quality index exceeds configured AWH review limit" in result.reasons


def test_router_holds_when_air_quality_is_missing() -> None:
    result = triage_atmospheric_water(
        _inputs(climate=_climate(air_quality_index=None))
    )

    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.top_mode is AWHMode.HOLD_FOR_TESTING
    assert "air quality index is missing" in result.reasons


def test_router_holds_when_dust_risk_is_elevated_but_not_blocking() -> None:
    result = triage_atmospheric_water(
        _inputs(climate=_climate(dust_risk_fraction=0.55))
    )

    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.top_mode is AWHMode.HOLD_FOR_TESTING
    assert "dust risk is elevated and requires surface contamination review" in result.reasons


def test_router_holds_when_no_mode_is_supported() -> None:
    result = triage_atmospheric_water(
        _inputs(
            climate=_climate(
                relative_humidity_percent=8.0,
                temperature_c=45.0,
                dew_point_c=-5.0,
                wind_speed_m_s=0.2,
                solar_irradiance_w_m2=100.0,
                observed_fog=False,
            ),
            constraints=_constraints(
                available_electric_power_w=100.0,
                battery_state_fraction=0.1,
                available_collection_area_m2=1.0,
            ),
        )
    )

    assert result.decision_status is DecisionStatus.HOLD_FOR_TESTING
    assert result.top_mode is AWHMode.HOLD_FOR_TESTING
    assert result.has_reviewable_mode is False
    assert "no reviewable AWH mode was supported by the provided evidence" in result.reasons


def test_policy_can_raise_active_condensation_power_threshold() -> None:
    policy = AWHTriagePolicy(min_active_condensation_power_w=5_000.0)

    result = triage_atmospheric_water(
        _inputs(
            climate=_climate(
                relative_humidity_percent=62.0,
                temperature_c=28.0,
                dew_point_c=20.0,
                solar_irradiance_w_m2=200.0,
            ),
            constraints=_constraints(available_electric_power_w=2_000.0),
        ),
        policy=policy,
    )

    modes = [option.mode for option in result.recommended_modes]

    assert AWHMode.ACTIVE_CONDENSATION not in modes
