"""Atmospheric water harvesting portfolio router for IX-Vahdat.

The router ranks possible atmospheric water harvesting review modes based on
climate and site constraints. It does not estimate guaranteed yield, select a
specific vendor product, certify collected water, or authorize deployment.

Outputs are conservative decision-support records. Every reviewable mode still
requires water-quality verification, maintenance planning, and human review.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ix_vahdat.atmospheric import AtmosphericWaterInputs
from ix_vahdat.domain import DecisionStatus, RiskLevel


class AWHMode(str, Enum):
    """Atmospheric water harvesting modes considered by IX-Vahdat."""

    FOG_CAPTURE = "fog_capture"
    RADIATIVE_DEW = "radiative_dew"
    MOF_ADSORPTION = "mof_adsorption"
    HYDROGEL_ADSORPTION = "hydrogel_adsorption"
    SOLAR_DESORPTION = "solar_desorption"
    ACTIVE_CONDENSATION = "active_condensation"
    HOLD_FOR_TESTING = "hold_for_testing"
    DO_NOT_DEPLOY_AWH = "do_not_deploy_awh"


@dataclass(frozen=True, slots=True)
class AWHTriagePolicy:
    """Conservative climate and site thresholds for AWH triage.

    These thresholds are planning gates only. They are not product
    specifications, water-yield guarantees, or public-health standards.
    """

    max_air_quality_index_for_review: float = 150.0
    max_dust_risk_for_review: float = 0.70

    min_fog_collection_area_m2: float = 5.0
    min_dew_collection_area_m2: float = 5.0
    min_sorbent_collection_area_m2: float = 2.0

    min_active_condensation_rh_percent: float = 45.0
    min_active_condensation_power_w: float = 500.0
    min_active_condensation_battery_fraction: float = 0.25

    min_solar_regeneration_w_m2: float = 350.0
    min_sorbent_rh_percent: float = 10.0
    max_low_humidity_sorbent_rh_percent: float = 35.0

    moderate_storage_shortfall_l: float = 25.0


@dataclass(frozen=True, slots=True)
class AWHTriageOption:
    """Single ranked atmospheric water harvesting option."""

    mode: AWHMode
    score: int
    risk_level: RiskLevel
    reasons: tuple[str, ...]
    required_actions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AWHTriageResult:
    """Portfolio-level atmospheric water harvesting triage result."""

    decision_status: DecisionStatus
    risk_level: RiskLevel
    recommended_modes: tuple[AWHTriageOption, ...]
    reasons: tuple[str, ...]
    required_actions: tuple[str, ...]

    @property
    def has_reviewable_mode(self) -> bool:
        """Return True when at least one AWH path may continue to review."""

        return (
            self.decision_status is DecisionStatus.ALLOW_REVIEW
            and any(option.score > 0 for option in self.recommended_modes)
        )

    @property
    def top_mode(self) -> AWHMode:
        """Return the top mode or a conservative non-deployment state."""

        if not self.recommended_modes:
            return AWHMode.DO_NOT_DEPLOY_AWH
        return self.recommended_modes[0].mode


def triage_atmospheric_water(
    inputs: AtmosphericWaterInputs,
    policy: AWHTriagePolicy | None = None,
) -> AWHTriageResult:
    """Rank AWH review modes from climate and site evidence.

    The result is a portfolio decision-support output. It does not imply that
    collected water is potable, abundant, locally legal, or deployment-ready.
    """

    active_policy = policy or AWHTriagePolicy()
    blockers = _deployment_blockers(inputs, active_policy)
    if blockers:
        return AWHTriageResult(
            decision_status=DecisionStatus.BLOCK,
            risk_level=RiskLevel.HIGH,
            recommended_modes=(
                AWHTriageOption(
                    mode=AWHMode.DO_NOT_DEPLOY_AWH,
                    score=0,
                    risk_level=RiskLevel.HIGH,
                    reasons=blockers,
                    required_actions=(
                        "do not deploy atmospheric water harvesting at this site yet",
                        "resolve site support, air-quality, maintenance, or storage blockers",
                        "repeat triage with verified local observations",
                    ),
                ),
            ),
            reasons=blockers,
            required_actions=(
                "resolve blockers before deployment review",
                "do not make water-yield or potable-water claims",
                "preserve triage evidence for human review",
            ),
        )

    hold_reasons = _testing_hold_reasons(inputs, active_policy)
    if hold_reasons:
        return AWHTriageResult(
            decision_status=DecisionStatus.HOLD_FOR_TESTING,
            risk_level=RiskLevel.MODERATE,
            recommended_modes=(
                AWHTriageOption(
                    mode=AWHMode.HOLD_FOR_TESTING,
                    score=0,
                    risk_level=RiskLevel.MODERATE,
                    reasons=hold_reasons,
                    required_actions=(
                        "repeat local climate measurements",
                        "inspect collection surfaces and air-quality conditions",
                        "continue only after human review",
                    ),
                ),
            ),
            reasons=hold_reasons,
            required_actions=(
                "hold AWH deployment decision",
                "collect additional site observations",
                "do not classify harvested water without treatment and testing",
            ),
        )

    options = tuple(
        sorted(
            _candidate_options(inputs, active_policy),
            key=lambda option: option.score,
            reverse=True,
        )
    )

    if not options:
        return AWHTriageResult(
            decision_status=DecisionStatus.HOLD_FOR_TESTING,
            risk_level=RiskLevel.MODERATE,
            recommended_modes=(
                AWHTriageOption(
                    mode=AWHMode.HOLD_FOR_TESTING,
                    score=0,
                    risk_level=RiskLevel.MODERATE,
                    reasons=("no atmospheric water harvesting mode has enough site support",),
                    required_actions=(
                        "collect longer-duration humidity, dew point, fog, wind, and solar records",
                        "consider water-loss reduction, reuse, treatment, or tanker supply before AWH",
                        "do not deploy AWH hardware based on this evidence alone",
                    ),
                ),
            ),
            reasons=("no reviewable AWH mode was supported by the provided evidence",),
            required_actions=(
                "collect longer-duration site data",
                "compare non-atmospheric water options",
                "repeat triage before procurement",
            ),
        )

    return AWHTriageResult(
        decision_status=DecisionStatus.ALLOW_REVIEW,
        risk_level=max_option_risk(options),
        recommended_modes=options,
        reasons=("one or more AWH modes may continue to human review",),
        required_actions=(
            "perform water-quality verification for any collected water",
            "do not claim potable water from climate fit alone",
            "complete maintenance, energy, and storage review before deployment",
            "preserve evidence bundle for human review",
        ),
    )


def _deployment_blockers(
    inputs: AtmosphericWaterInputs,
    policy: AWHTriagePolicy,
) -> tuple[str, ...]:
    climate = inputs.climate
    constraints = inputs.constraints
    blockers: list[str] = []

    if not constraints.has_storage_for_collection:
        blockers.append("no storage capacity remains for collected water")
    if not constraints.has_collection_area:
        blockers.append("no collection area is available")
    if not constraints.has_maintenance_capacity:
        blockers.append("maintenance capacity is below conservative minimum")
    if climate.air_quality_index is not None and (
        climate.air_quality_index > policy.max_air_quality_index_for_review
    ):
        blockers.append("air quality index exceeds configured AWH review limit")
    if climate.dust_risk_fraction > policy.max_dust_risk_for_review:
        blockers.append("dust risk exceeds configured AWH review limit")

    return tuple(blockers)


def _testing_hold_reasons(
    inputs: AtmosphericWaterInputs,
    policy: AWHTriagePolicy,
) -> tuple[str, ...]:
    climate = inputs.climate
    constraints = inputs.constraints
    reasons: list[str] = []

    if 0.0 < constraints.storage_capacity_remaining_l < policy.moderate_storage_shortfall_l:
        reasons.append("storage capacity is low and may not justify collection hardware")
    if climate.air_quality_index is None:
        reasons.append("air quality index is missing")
    if climate.dust_risk_fraction >= 0.50:
        reasons.append("dust risk is elevated and requires surface contamination review")

    return tuple(reasons)


def _candidate_options(
    inputs: AtmosphericWaterInputs,
    policy: AWHTriagePolicy,
) -> tuple[AWHTriageOption, ...]:
    climate = inputs.climate
    constraints = inputs.constraints
    options: list[AWHTriageOption] = []

    if (
        climate.has_fog_signal
        and constraints.available_collection_area_m2 >= policy.min_fog_collection_area_m2
    ):
        options.append(
            AWHTriageOption(
                mode=AWHMode.FOG_CAPTURE,
                score=95,
                risk_level=RiskLevel.LOW,
                reasons=(
                    "fog signal is present",
                    "collection area supports fog-capture review",
                    "fog capture is passive and low-energy when local fog conditions exist",
                ),
                required_actions=(
                    "verify fog frequency with local observations",
                    "inspect mesh contamination and cleaning plan",
                    "route collected water through quality gate before use",
                ),
            )
        )

    if (
        climate.has_dew_signal
        and constraints.available_collection_area_m2 >= policy.min_dew_collection_area_m2
    ):
        options.append(
            AWHTriageOption(
                mode=AWHMode.RADIATIVE_DEW,
                score=80,
                risk_level=RiskLevel.LOW,
                reasons=(
                    "dew signal is present",
                    "collection area supports passive dew review",
                    "radiative dew capture may support small emergency reserves",
                ),
                required_actions=(
                    "verify night-sky exposure and collection-surface cleanliness",
                    "measure actual nightly collection before scaling",
                    "route collected water through quality gate before use",
                ),
            )
        )

    if (
        climate.relative_humidity_percent >= policy.min_sorbent_rh_percent
        and climate.relative_humidity_percent <= policy.max_low_humidity_sorbent_rh_percent
        and climate.has_solar_regeneration_signal
        and constraints.available_collection_area_m2 >= policy.min_sorbent_collection_area_m2
    ):
        options.append(
            AWHTriageOption(
                mode=AWHMode.MOF_ADSORPTION,
                score=70,
                risk_level=RiskLevel.MODERATE,
                reasons=(
                    "low-humidity conditions support sorbent review",
                    "solar input supports regeneration review",
                    "sorbent mode is considered for emergency water resilience only",
                ),
                required_actions=(
                    "validate sorbent material safety and lifecycle",
                    "measure actual yield under local conditions",
                    "route condensate through treatment and quality gates",
                ),
            )
        )

    if (
        25.0 <= climate.relative_humidity_percent <= 70.0
        and climate.has_solar_regeneration_signal
        and constraints.available_collection_area_m2 >= policy.min_sorbent_collection_area_m2
    ):
        options.append(
            AWHTriageOption(
                mode=AWHMode.HYDROGEL_ADSORPTION,
                score=65,
                risk_level=RiskLevel.MODERATE,
                reasons=(
                    "humidity and solar conditions support hydrogel/salt review",
                    "passive sorbent mode may reduce electrical demand",
                    "material safety and leaching must be verified before use",
                ),
                required_actions=(
                    "verify salt or sorbent containment",
                    "test produced water for material carryover",
                    "route collected water through quality gate before use",
                ),
            )
        )

    if (
        climate.solar_irradiance_w_m2 >= policy.min_solar_regeneration_w_m2
        and constraints.available_collection_area_m2 >= policy.min_sorbent_collection_area_m2
    ):
        options.append(
            AWHTriageOption(
                mode=AWHMode.SOLAR_DESORPTION,
                score=55,
                risk_level=RiskLevel.MODERATE,
                reasons=(
                    "solar irradiance supports regeneration review",
                    "solar desorption may support sorbent cycling",
                ),
                required_actions=(
                    "verify thermal limits for sorbent and enclosure materials",
                    "measure recovered water rather than assuming yield",
                    "protect storage from contamination during condensation",
                ),
            )
        )

    if (
        climate.relative_humidity_percent >= policy.min_active_condensation_rh_percent
        and constraints.available_electric_power_w >= policy.min_active_condensation_power_w
        and constraints.battery_state_fraction >= policy.min_active_condensation_battery_fraction
        and constraints.has_power_for_active_condensation_review
    ):
        options.append(
            AWHTriageOption(
                mode=AWHMode.ACTIVE_CONDENSATION,
                score=50,
                risk_level=RiskLevel.MODERATE,
                reasons=(
                    "humidity and power support active condensation review",
                    "active condensation may produce more water where energy is available",
                ),
                required_actions=(
                    "complete energy-per-liter accounting",
                    "verify condensate quality and storage hygiene",
                    "protect critical loads before running active condensation",
                ),
            )
        )

    return tuple(options)


def max_option_risk(options: tuple[AWHTriageOption, ...]) -> RiskLevel:
    """Return the highest risk among recommended options."""

    order = {
        RiskLevel.LOW: 0,
        RiskLevel.MODERATE: 1,
        RiskLevel.HIGH: 2,
        RiskLevel.CRITICAL: 3,
    }
    highest = max(options, key=lambda option: order[option.risk_level])
    return highest.risk_level
