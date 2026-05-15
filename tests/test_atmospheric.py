from datetime import UTC, datetime

import pytest

from ix_vahdat.atmospheric import (
    AtmosphericSiteConstraints,
    AtmosphericWaterClimate,
    AtmosphericWaterInputs,
)


def _climate(**overrides: object) -> AtmosphericWaterClimate:
    values = {
        "relative_humidity_percent": 82.0,
        "temperature_c": 22.0,
        "dew_point_c": 18.8,
        "wind_speed_m_s": 2.0,
        "solar_irradiance_w_m2": 500.0,
        "observed_fog": False,
        "air_quality_index": 70.0,
        "dust_risk_fraction": 0.2,
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


def test_climate_accepts_valid_observations_and_computes_signals() -> None:
    climate = _climate()

    assert climate.dew_point_depression_c == pytest.approx(3.2)
    assert climate.has_dew_signal is True
    assert climate.has_solar_regeneration_signal is True
    assert climate.has_low_humidity_signal is False


def test_climate_detects_fog_signal_from_observed_fog() -> None:
    climate = _climate(
        relative_humidity_percent=70.0,
        temperature_c=20.0,
        dew_point_c=14.0,
        wind_speed_m_s=0.1,
        observed_fog=True,
    )

    assert climate.has_fog_signal is True


def test_climate_detects_fog_signal_from_saturated_moving_air() -> None:
    climate = _climate(
        relative_humidity_percent=97.0,
        temperature_c=10.0,
        dew_point_c=9.0,
        wind_speed_m_s=1.2,
        observed_fog=False,
    )

    assert climate.has_fog_signal is True


def test_climate_detects_low_humidity_signal() -> None:
    climate = _climate(
        relative_humidity_percent=18.0,
        temperature_c=35.0,
        dew_point_c=7.0,
    )

    assert climate.has_low_humidity_signal is True
    assert climate.has_dew_signal is False


@pytest.mark.parametrize(
    ("field", "value", "expected_message"),
    [
        ("relative_humidity_percent", -1.0, "relative_humidity_percent"),
        ("relative_humidity_percent", 101.0, "relative_humidity_percent"),
        ("temperature_c", 90.0, "temperature_c"),
        ("dew_point_c", 81.0, "dew_point_c"),
        ("wind_speed_m_s", -0.1, "wind_speed_m_s"),
        ("solar_irradiance_w_m2", -1.0, "solar_irradiance"),
        ("solar_irradiance_w_m2", 1_600.0, "solar_irradiance"),
        ("air_quality_index", 600.0, "air_quality_index"),
        ("dust_risk_fraction", 1.1, "dust_risk_fraction"),
    ],
)
def test_climate_rejects_invalid_values(
    field: str,
    value: float,
    expected_message: str,
) -> None:
    with pytest.raises(ValueError, match=expected_message):
        _climate(**{field: value})


def test_climate_rejects_dew_point_above_temperature() -> None:
    with pytest.raises(ValueError, match="dew_point_c"):
        _climate(temperature_c=20.0, dew_point_c=21.0)


def test_constraints_compute_site_support_signals() -> None:
    constraints = _constraints()

    assert constraints.has_storage_for_collection is True
    assert constraints.has_collection_area is True
    assert constraints.has_maintenance_capacity is True
    assert constraints.has_power_for_active_condensation_review is True


def test_constraints_detect_insufficient_power_for_active_condensation_review() -> None:
    constraints = _constraints(available_electric_power_w=100.0, battery_state_fraction=0.9)

    assert constraints.has_power_for_active_condensation_review is False


def test_constraints_detect_insufficient_battery_for_active_condensation_review() -> None:
    constraints = _constraints(available_electric_power_w=2_000.0, battery_state_fraction=0.1)

    assert constraints.has_power_for_active_condensation_review is False


@pytest.mark.parametrize(
    ("field", "value", "expected_message"),
    [
        ("daily_priority_water_demand_l", -1.0, "daily_priority_water_demand_l"),
        ("available_electric_power_w", -1.0, "available_electric_power_w"),
        ("battery_state_fraction", 1.2, "battery_state_fraction"),
        ("available_collection_area_m2", -1.0, "available_collection_area_m2"),
        ("maintenance_capacity_fraction", -0.1, "maintenance_capacity_fraction"),
        ("storage_capacity_remaining_l", -1.0, "storage_capacity_remaining_l"),
    ],
)
def test_constraints_reject_invalid_values(
    field: str,
    value: float,
    expected_message: str,
) -> None:
    with pytest.raises(ValueError, match=expected_message):
        _constraints(**{field: value})


def test_inputs_require_timezone_aware_observation_time() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        AtmosphericWaterInputs(
            observed_at=datetime(2026, 5, 14, 12, 0, 0),
            climate=_climate(),
            constraints=_constraints(),
        )


def test_inputs_compute_minimum_deployment_support() -> None:
    inputs = AtmosphericWaterInputs(
        observed_at=datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC),
        climate=_climate(),
        constraints=_constraints(),
    )

    assert inputs.has_minimum_deployment_support is True
    assert inputs.needs_non_potable_fallback_language is True


def test_inputs_fail_minimum_deployment_support_without_storage() -> None:
    inputs = AtmosphericWaterInputs(
        observed_at=datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC),
        climate=_climate(),
        constraints=_constraints(storage_capacity_remaining_l=0.0),
    )

    assert inputs.has_minimum_deployment_support is False
