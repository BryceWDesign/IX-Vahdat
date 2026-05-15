from datetime import UTC, datetime

from ix_vahdat.atmospheric import (
    AtmosphericSiteConstraints,
    AtmosphericWaterClimate,
    AtmosphericWaterInputs,
)
from ix_vahdat.awh import AWHMode
from ix_vahdat.awh_scoring import AWHScoreBand, score_awh_modes


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


def _score_for_mode(scores, mode: AWHMode):
    return next(score for score in scores if score.mode is mode)


def test_scores_fog_capture_strong_when_fog_conditions_are_supported() -> None:
    scores = score_awh_modes(
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
    fog = _score_for_mode(scores, AWHMode.FOG_CAPTURE)

    assert fog.score >= 75
    assert fog.band is AWHScoreBand.STRONG
    assert fog.is_reviewable is True
    assert "fog signal is present" in fog.factors
    assert fog.blockers == ()


def test_scores_dew_capture_reviewable_when_dew_conditions_are_supported() -> None:
    scores = score_awh_modes(
        _inputs(
            climate=_climate(
                relative_humidity_percent=86.0,
                temperature_c=18.0,
                dew_point_c=15.0,
                observed_fog=False,
                wind_speed_m_s=0.1,
            )
        )
    )
    dew = _score_for_mode(scores, AWHMode.RADIATIVE_DEW)

    assert dew.band in {AWHScoreBand.REVIEWABLE, AWHScoreBand.STRONG}
    assert dew.is_reviewable is True
    assert "dew signal is present" in dew.factors


def test_scores_mof_adsorption_reviewable_in_low_humidity_with_solar_input() -> None:
    scores = score_awh_modes(
        _inputs(
            climate=_climate(
                relative_humidity_percent=22.0,
                temperature_c=37.0,
                dew_point_c=10.0,
                solar_irradiance_w_m2=850.0,
                observed_fog=False,
            )
        )
    )
    mof = _score_for_mode(scores, AWHMode.MOF_ADSORPTION)

    assert mof.band in {AWHScoreBand.REVIEWABLE, AWHScoreBand.STRONG}
    assert mof.is_reviewable is True
    assert "relative humidity supports low-humidity sorbent review" in mof.factors
    assert "solar input supports passive regeneration review" in mof.factors


def test_scores_hydrogel_adsorption_reviewable_in_mid_humidity_with_solar_input() -> None:
    scores = score_awh_modes(
        _inputs(
            climate=_climate(
                relative_humidity_percent=45.0,
                temperature_c=31.0,
                dew_point_c=17.5,
                solar_irradiance_w_m2=700.0,
                observed_fog=False,
            )
        )
    )
    hydrogel = _score_for_mode(scores, AWHMode.HYDROGEL_ADSORPTION)

    assert hydrogel.band in {AWHScoreBand.REVIEWABLE, AWHScoreBand.STRONG}
    assert hydrogel.is_reviewable is True
    assert "relative humidity supports hydrogel/salt review" in hydrogel.factors


def test_scores_active_condensation_reviewable_with_humidity_power_and_battery() -> None:
    scores = score_awh_modes(
        _inputs(
            climate=_climate(
                relative_humidity_percent=62.0,
                temperature_c=28.0,
                dew_point_c=20.0,
                solar_irradiance_w_m2=200.0,
                observed_fog=False,
            ),
            constraints=_constraints(
                available_electric_power_w=2_500.0,
                battery_state_fraction=0.8,
            ),
        )
    )
    active = _score_for_mode(scores, AWHMode.ACTIVE_CONDENSATION)

    assert active.band in {AWHScoreBand.REVIEWABLE, AWHScoreBand.STRONG}
    assert active.is_reviewable is True
    assert "complete energy-per-liter accounting" in active.required_actions


def test_common_blockers_force_all_modes_to_unsupported() -> None:
    scores = score_awh_modes(
        _inputs(
            climate=_climate(air_quality_index=180.0),
            constraints=_constraints(storage_capacity_remaining_l=0.0),
        )
    )

    assert all(score.score == 0 for score in scores)
    assert all(score.band is AWHScoreBand.UNSUPPORTED for score in scores)
    assert all(score.is_reviewable is False for score in scores)
    assert all("no storage capacity remains for collected water" in score.blockers for score in scores)
    assert all("air quality index exceeds configured AWH review limit" in score.blockers for score in scores)


def test_missing_air_quality_is_a_blocker_for_scoring() -> None:
    scores = score_awh_modes(_inputs(climate=_climate(air_quality_index=None)))

    assert all(score.band is AWHScoreBand.UNSUPPORTED for score in scores)
    assert all("air quality index is missing" in score.blockers for score in scores)


def test_mode_specific_blockers_do_not_hide_other_modes() -> None:
    scores = score_awh_modes(
        _inputs(
            climate=_climate(
                relative_humidity_percent=20.0,
                temperature_c=35.0,
                dew_point_c=8.0,
                solar_irradiance_w_m2=850.0,
                observed_fog=False,
            )
        )
    )
    fog = _score_for_mode(scores, AWHMode.FOG_CAPTURE)
    mof = _score_for_mode(scores, AWHMode.MOF_ADSORPTION)

    assert fog.band is AWHScoreBand.UNSUPPORTED
    assert "fog signal is not present" in fog.blockers
    assert mof.is_reviewable is True


def test_scores_are_sorted_from_strongest_to_weakest() -> None:
    scores = score_awh_modes(
        _inputs(
            climate=_climate(
                relative_humidity_percent=98.0,
                temperature_c=12.0,
                dew_point_c=11.2,
                wind_speed_m_s=2.5,
                solar_irradiance_w_m2=850.0,
                observed_fog=True,
            )
        )
    )

    score_values = [score.score for score in scores]

    assert score_values == sorted(score_values, reverse=True)
