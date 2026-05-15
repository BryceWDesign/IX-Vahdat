"""Explainable atmospheric-water method scoring for IX-Vahdat.

This module exposes the support score, evidence factors, blockers, and review
band for each atmospheric water harvesting mode.

Scores are decision-support signals only. They are not water-yield guarantees,
procurement recommendations, public-health approvals, or deployment authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ix_vahdat.atmospheric import AtmosphericWaterInputs
from ix_vahdat.awh import AWHMode, AWHTriagePolicy


class AWHScoreBand(str, Enum):
    """Review band for an atmospheric water harvesting mode."""

    UNSUPPORTED = "unsupported"
    WEAK = "weak"
    REVIEWABLE = "reviewable"
    STRONG = "strong"


@dataclass(frozen=True, slots=True)
class AWHModeScore:
    """Explainable score for one atmospheric water harvesting mode."""

    mode: AWHMode
    score: int
    band: AWHScoreBand
    factors: tuple[str, ...]
    blockers: tuple[str, ...]
    required_actions: tuple[str, ...]

    @property
    def is_reviewable(self) -> bool:
        """Return True when the mode has enough support for human review."""

        return self.band in {AWHScoreBand.REVIEWABLE, AWHScoreBand.STRONG}


def score_awh_modes(
    inputs: AtmosphericWaterInputs,
    policy: AWHTriagePolicy | None = None,
) -> tuple[AWHModeScore, ...]:
    """Score all atmospheric water harvesting modes for explainability.

    Returned scores are sorted from strongest to weakest. A mode with blockers
    receives score zero and must not continue to deployment review.
    """

    active_policy = policy or AWHTriagePolicy()
    scores = (
        _score_fog_capture(inputs, active_policy),
        _score_radiative_dew(inputs, active_policy),
        _score_mof_adsorption(inputs, active_policy),
        _score_hydrogel_adsorption(inputs, active_policy),
        _score_solar_desorption(inputs, active_policy),
        _score_active_condensation(inputs, active_policy),
    )
    return tuple(sorted(scores, key=lambda item: item.score, reverse=True))


def _score_fog_capture(
    inputs: AtmosphericWaterInputs,
    policy: AWHTriagePolicy,
) -> AWHModeScore:
    climate = inputs.climate
    constraints = inputs.constraints
    blockers = list(_common_blockers(inputs, policy))
    factors: list[str] = []

    if not climate.has_fog_signal:
        blockers.append("fog signal is not present")
    else:
        factors.append("fog signal is present")

    if constraints.available_collection_area_m2 < policy.min_fog_collection_area_m2:
        blockers.append("collection area is below fog-capture review minimum")
    else:
        factors.append("collection area supports fog-capture review")

    score = 0
    if not blockers:
        score += 45
        score += _humidity_points(climate.relative_humidity_percent)
        score += _wind_points(climate.wind_speed_m_s)
        score += _area_points(
            constraints.available_collection_area_m2,
            policy.min_fog_collection_area_m2,
        )
        score += _clean_air_points(climate.dust_risk_fraction)
        score = _clamp_score(score)

    return _mode_score(
        mode=AWHMode.FOG_CAPTURE,
        score=score,
        factors=tuple(factors),
        blockers=tuple(blockers),
        required_actions=(
            "verify fog frequency with local observation records",
            "inspect and clean collection mesh before use",
            "route collected water through treatment and quality gates",
        ),
    )


def _score_radiative_dew(
    inputs: AtmosphericWaterInputs,
    policy: AWHTriagePolicy,
) -> AWHModeScore:
    climate = inputs.climate
    constraints = inputs.constraints
    blockers = list(_common_blockers(inputs, policy))
    factors: list[str] = []

    if not climate.has_dew_signal:
        blockers.append("dew signal is not present")
    else:
        factors.append("dew signal is present")

    if constraints.available_collection_area_m2 < policy.min_dew_collection_area_m2:
        blockers.append("collection area is below dew-capture review minimum")
    else:
        factors.append("collection area supports dew-capture review")

    score = 0
    if not blockers:
        score += 35
        score += _humidity_points(climate.relative_humidity_percent)
        score += _dew_point_points(climate.dew_point_depression_c)
        score += _area_points(
            constraints.available_collection_area_m2,
            policy.min_dew_collection_area_m2,
        )
        score += _clean_air_points(climate.dust_risk_fraction)
        score = _clamp_score(score)

    return _mode_score(
        mode=AWHMode.RADIATIVE_DEW,
        score=score,
        factors=tuple(factors),
        blockers=tuple(blockers),
        required_actions=(
            "verify night-sky exposure and surface cleanliness",
            "measure actual nightly collection before scaling",
            "route collected water through treatment and quality gates",
        ),
    )


def _score_mof_adsorption(
    inputs: AtmosphericWaterInputs,
    policy: AWHTriagePolicy,
) -> AWHModeScore:
    climate = inputs.climate
    constraints = inputs.constraints
    blockers = list(_common_blockers(inputs, policy))
    factors: list[str] = []

    if not (
        policy.min_sorbent_rh_percent
        <= climate.relative_humidity_percent
        <= policy.max_low_humidity_sorbent_rh_percent
    ):
        blockers.append("relative humidity is outside low-humidity sorbent review band")
    else:
        factors.append("relative humidity supports low-humidity sorbent review")

    if not climate.has_solar_regeneration_signal:
        blockers.append("solar input does not support passive regeneration review")
    else:
        factors.append("solar input supports passive regeneration review")

    if constraints.available_collection_area_m2 < policy.min_sorbent_collection_area_m2:
        blockers.append("collection area is below sorbent review minimum")
    else:
        factors.append("collection area supports sorbent review")

    score = 0
    if not blockers:
        score += 40
        score += _low_humidity_sorbent_points(climate.relative_humidity_percent)
        score += _solar_points(climate.solar_irradiance_w_m2)
        score += _area_points(
            constraints.available_collection_area_m2,
            policy.min_sorbent_collection_area_m2,
        )
        score += _clean_air_points(climate.dust_risk_fraction)
        score = _clamp_score(score)

    return _mode_score(
        mode=AWHMode.MOF_ADSORPTION,
        score=score,
        factors=tuple(factors),
        blockers=tuple(blockers),
        required_actions=(
            "verify sorbent material safety and lifecycle",
            "measure actual local yield instead of assuming performance",
            "route condensate through treatment and quality gates",
        ),
    )


def _score_hydrogel_adsorption(
    inputs: AtmosphericWaterInputs,
    policy: AWHTriagePolicy,
) -> AWHModeScore:
    climate = inputs.climate
    constraints = inputs.constraints
    blockers = list(_common_blockers(inputs, policy))
    factors: list[str] = []

    if not 25.0 <= climate.relative_humidity_percent <= 70.0:
        blockers.append("relative humidity is outside hydrogel/salt review band")
    else:
        factors.append("relative humidity supports hydrogel/salt review")

    if not climate.has_solar_regeneration_signal:
        blockers.append("solar input does not support passive regeneration review")
    else:
        factors.append("solar input supports passive regeneration review")

    if constraints.available_collection_area_m2 < policy.min_sorbent_collection_area_m2:
        blockers.append("collection area is below sorbent review minimum")
    else:
        factors.append("collection area supports sorbent review")

    score = 0
    if not blockers:
        score += 35
        score += _mid_humidity_points(climate.relative_humidity_percent)
        score += _solar_points(climate.solar_irradiance_w_m2)
        score += _area_points(
            constraints.available_collection_area_m2,
            policy.min_sorbent_collection_area_m2,
        )
        score += _clean_air_points(climate.dust_risk_fraction)
        score = _clamp_score(score)

    return _mode_score(
        mode=AWHMode.HYDROGEL_ADSORPTION,
        score=score,
        factors=tuple(factors),
        blockers=tuple(blockers),
        required_actions=(
            "verify salt or sorbent containment",
            "test produced water for material carryover",
            "route collected water through treatment and quality gates",
        ),
    )


def _score_solar_desorption(
    inputs: AtmosphericWaterInputs,
    policy: AWHTriagePolicy,
) -> AWHModeScore:
    climate = inputs.climate
    constraints = inputs.constraints
    blockers = list(_common_blockers(inputs, policy))
    factors: list[str] = []

    if climate.solar_irradiance_w_m2 < policy.min_solar_regeneration_w_m2:
        blockers.append("solar irradiance is below regeneration review minimum")
    else:
        factors.append("solar irradiance supports regeneration review")

    if constraints.available_collection_area_m2 < policy.min_sorbent_collection_area_m2:
        blockers.append("collection area is below sorbent review minimum")
    else:
        factors.append("collection area supports sorbent review")

    score = 0
    if not blockers:
        score += 30
        score += _solar_points(climate.solar_irradiance_w_m2)
        score += _area_points(
            constraints.available_collection_area_m2,
            policy.min_sorbent_collection_area_m2,
        )
        score = _clamp_score(score)

    return _mode_score(
        mode=AWHMode.SOLAR_DESORPTION,
        score=score,
        factors=tuple(factors),
        blockers=tuple(blockers),
        required_actions=(
            "verify thermal limits for sorbent and enclosure materials",
            "measure recovered water instead of assuming yield",
            "protect condensation and storage surfaces from contamination",
        ),
    )


def _score_active_condensation(
    inputs: AtmosphericWaterInputs,
    policy: AWHTriagePolicy,
) -> AWHModeScore:
    climate = inputs.climate
    constraints = inputs.constraints
    blockers = list(_common_blockers(inputs, policy))
    factors: list[str] = []

    if climate.relative_humidity_percent < policy.min_active_condensation_rh_percent:
        blockers.append("relative humidity is below active-condensation review minimum")
    else:
        factors.append("relative humidity supports active-condensation review")

    if constraints.available_electric_power_w < policy.min_active_condensation_power_w:
        blockers.append("available electric power is below active-condensation review minimum")
    else:
        factors.append("available electric power supports active-condensation review")

    if constraints.battery_state_fraction < policy.min_active_condensation_battery_fraction:
        blockers.append("battery state is below active-condensation review minimum")
    else:
        factors.append("battery state supports active-condensation review")

    score = 0
    if not blockers:
        score += 25
        score += _humidity_points(climate.relative_humidity_percent)
        score += _power_points(constraints.available_electric_power_w)
        score += _battery_points(constraints.battery_state_fraction)
        score = _clamp_score(score)

    return _mode_score(
        mode=AWHMode.ACTIVE_CONDENSATION,
        score=score,
        factors=tuple(factors),
        blockers=tuple(blockers),
        required_actions=(
            "complete energy-per-liter accounting",
            "protect critical loads before running active condensation",
            "verify condensate quality and storage hygiene",
        ),
    )


def _common_blockers(
    inputs: AtmosphericWaterInputs,
    policy: AWHTriagePolicy,
) -> tuple[str, ...]:
    climate = inputs.climate
    constraints = inputs.constraints
    blockers: list[str] = []

    if not constraints.has_storage_for_collection:
        blockers.append("no storage capacity remains for collected water")
    if not constraints.has_maintenance_capacity:
        blockers.append("maintenance capacity is below conservative minimum")
    if climate.air_quality_index is None:
        blockers.append("air quality index is missing")
    elif climate.air_quality_index > policy.max_air_quality_index_for_review:
        blockers.append("air quality index exceeds configured AWH review limit")
    if climate.dust_risk_fraction > policy.max_dust_risk_for_review:
        blockers.append("dust risk exceeds configured AWH review limit")

    return tuple(blockers)


def _mode_score(
    *,
    mode: AWHMode,
    score: int,
    factors: tuple[str, ...],
    blockers: tuple[str, ...],
    required_actions: tuple[str, ...],
) -> AWHModeScore:
    final_score = 0 if blockers else _clamp_score(score)
    return AWHModeScore(
        mode=mode,
        score=final_score,
        band=_band(final_score, blockers),
        factors=factors,
        blockers=blockers,
        required_actions=required_actions,
    )


def _band(score: int, blockers: tuple[str, ...]) -> AWHScoreBand:
    if blockers or score <= 0:
        return AWHScoreBand.UNSUPPORTED
    if score >= 75:
        return AWHScoreBand.STRONG
    if score >= 50:
        return AWHScoreBand.REVIEWABLE
    return AWHScoreBand.WEAK


def _humidity_points(relative_humidity_percent: float) -> int:
    if relative_humidity_percent >= 90.0:
        return 20
    if relative_humidity_percent >= 75.0:
        return 16
    if relative_humidity_percent >= 60.0:
        return 12
    if relative_humidity_percent >= 45.0:
        return 8
    return 3


def _dew_point_points(dew_point_depression_c: float) -> int:
    if dew_point_depression_c <= 1.5:
        return 20
    if dew_point_depression_c <= 3.5:
        return 15
    if dew_point_depression_c <= 5.0:
        return 10
    return 0


def _wind_points(wind_speed_m_s: float) -> int:
    if 1.0 <= wind_speed_m_s <= 8.0:
        return 15
    if 0.5 <= wind_speed_m_s < 1.0:
        return 8
    if 8.0 < wind_speed_m_s <= 12.0:
        return 5
    return 0


def _low_humidity_sorbent_points(relative_humidity_percent: float) -> int:
    if 15.0 <= relative_humidity_percent <= 30.0:
        return 20
    if 10.0 <= relative_humidity_percent < 15.0:
        return 10
    if 30.0 < relative_humidity_percent <= 35.0:
        return 10
    return 0


def _mid_humidity_points(relative_humidity_percent: float) -> int:
    if 35.0 <= relative_humidity_percent <= 60.0:
        return 20
    if 25.0 <= relative_humidity_percent < 35.0:
        return 10
    if 60.0 < relative_humidity_percent <= 70.0:
        return 10
    return 0


def _solar_points(solar_irradiance_w_m2: float) -> int:
    if solar_irradiance_w_m2 >= 800.0:
        return 20
    if solar_irradiance_w_m2 >= 600.0:
        return 15
    if solar_irradiance_w_m2 >= 350.0:
        return 10
    return 0


def _area_points(available_area_m2: float, minimum_area_m2: float) -> int:
    if available_area_m2 >= minimum_area_m2 * 4:
        return 10
    if available_area_m2 >= minimum_area_m2 * 2:
        return 7
    if available_area_m2 >= minimum_area_m2:
        return 4
    return 0


def _clean_air_points(dust_risk_fraction: float) -> int:
    if dust_risk_fraction <= 0.20:
        return 10
    if dust_risk_fraction <= 0.40:
        return 5
    return 0


def _power_points(available_electric_power_w: float) -> int:
    if available_electric_power_w >= 5_000.0:
        return 20
    if available_electric_power_w >= 2_000.0:
        return 15
    if available_electric_power_w >= 500.0:
        return 8
    return 0


def _battery_points(battery_state_fraction: float) -> int:
    if battery_state_fraction >= 0.75:
        return 15
    if battery_state_fraction >= 0.50:
        return 10
    if battery_state_fraction >= 0.25:
        return 5
    return 0


def _clamp_score(value: int) -> int:
    return max(0, min(100, value))
