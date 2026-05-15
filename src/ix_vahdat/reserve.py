"""Emergency water-reserve protection for IX-Vahdat.

This module protects emergency water reserves from being treated as ordinary
inventory. It evaluates whether a requested release would breach a protected
reserve, whether the stored water evidence is suitable for review, and whether
the node should enter conserve, emergency, safe-hold, or service-required mode.

It does not authorize water distribution, rationing, public release, or
drinking-water use. It produces decision-support output for qualified human
review under local authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite

from ix_vahdat.domain import DecisionStatus, RiskLevel
from ix_vahdat.water_use import WaterUseClass


class ReserveStatus(str, Enum):
    """Emergency-reserve operating posture."""

    NORMAL = "normal"
    CONSERVE = "conserve"
    EMERGENCY_REVIEW = "emergency_review"
    SAFE_HOLD = "safe_hold"
    SERVICE_REQUIRED = "service_required"


@dataclass(frozen=True, slots=True)
class EmergencyReserveSnapshot:
    """Observed state of a protected water reserve.

    The snapshot represents decision-support evidence. It does not prove water
    safety, local compliance, tank hygiene, or permission to distribute water.
    """

    stored_water_l: float
    protected_reserve_l: float
    daily_priority_demand_l: float
    requested_release_l: float
    requested_use_label: str
    water_use_class: WaterUseClass
    quality_gate_passed: bool
    treatment_route_reviewed: bool
    storage_clean: bool
    tank_integrity_verified: bool
    storage_age_hours: float
    emergency_request_declared: bool = False
    notes: str | None = None

    def __post_init__(self) -> None:
        _require_nonnegative_finite("stored_water_l", self.stored_water_l)
        _require_nonnegative_finite("protected_reserve_l", self.protected_reserve_l)
        _require_nonnegative_finite("daily_priority_demand_l", self.daily_priority_demand_l)
        _require_nonnegative_finite("requested_release_l", self.requested_release_l)
        _require_nonnegative_finite("storage_age_hours", self.storage_age_hours)

        if not self.requested_use_label.strip():
            raise ValueError("requested_use_label is required")
        if self.protected_reserve_l > self.stored_water_l and self.stored_water_l > 0.0:
            raise ValueError("protected_reserve_l cannot exceed stored_water_l when water is stored")
        if self.notes is not None and not self.notes.strip():
            raise ValueError("notes cannot be blank when provided")

    @property
    def post_release_storage_l(self) -> float:
        """Return expected stored water after requested release."""

        return self.stored_water_l - self.requested_release_l

    @property
    def would_breach_protected_reserve(self) -> bool:
        """Return whether the requested release crosses protected reserve."""

        return self.post_release_storage_l < self.protected_reserve_l

    @property
    def current_demand_coverage_days(self) -> float | None:
        """Return current stored-water coverage in days, if demand is known."""

        if self.daily_priority_demand_l <= 0.0:
            return None
        return self.stored_water_l / self.daily_priority_demand_l

    @property
    def post_release_demand_coverage_days(self) -> float | None:
        """Return post-release demand coverage in days, if demand is known."""

        if self.daily_priority_demand_l <= 0.0:
            return None
        return max(0.0, self.post_release_storage_l) / self.daily_priority_demand_l


@dataclass(frozen=True, slots=True)
class EmergencyReservePolicy:
    """Proof-of-concept thresholds for emergency reserve protection."""

    max_storage_age_hours_for_review: float = 72.0
    min_post_release_coverage_days: float = 1.0
    min_routine_release_margin_l: float = 5.0
    allow_emergency_review_below_reserve: bool = True

    def __post_init__(self) -> None:
        _require_positive_finite(
            "max_storage_age_hours_for_review",
            self.max_storage_age_hours_for_review,
        )
        _require_nonnegative_finite(
            "min_post_release_coverage_days",
            self.min_post_release_coverage_days,
        )
        _require_nonnegative_finite(
            "min_routine_release_margin_l",
            self.min_routine_release_margin_l,
        )


@dataclass(frozen=True, slots=True)
class EmergencyReserveResult:
    """Decision-support output for protected water reserve review."""

    status: ReserveStatus
    decision_status: DecisionStatus
    risk_level: RiskLevel
    allowed_release_l: float
    protected_reserve_l: float
    post_release_storage_l: float
    reasons: tuple[str, ...]
    required_actions: tuple[str, ...]

    @property
    def may_continue_to_human_review(self) -> bool:
        """Return True when a limited release may continue to human review."""

        return self.decision_status is DecisionStatus.ALLOW_REVIEW


def evaluate_emergency_reserve(
    snapshot: EmergencyReserveSnapshot,
    *,
    policy: EmergencyReservePolicy | None = None,
) -> EmergencyReserveResult:
    """Evaluate whether a requested release respects emergency reserve logic.

    A reviewable result is not distribution approval. It means the reserve
    evidence may continue to qualified human review.
    """

    active_policy = policy or EmergencyReservePolicy()

    service_blockers = _service_blockers(snapshot, active_policy)
    if service_blockers:
        return EmergencyReserveResult(
            status=ReserveStatus.SERVICE_REQUIRED,
            decision_status=DecisionStatus.HOLD_FOR_TESTING,
            risk_level=RiskLevel.HIGH,
            allowed_release_l=0.0,
            protected_reserve_l=snapshot.protected_reserve_l,
            post_release_storage_l=max(0.0, snapshot.stored_water_l),
            reasons=service_blockers,
            required_actions=(
                "hold reserve from routine use",
                "resolve storage, treatment, or water-quality evidence blockers",
                "repeat reserve review before release",
                "human review required before any emergency use",
            ),
        )

    if snapshot.stored_water_l <= 0.0:
        return EmergencyReserveResult(
            status=ReserveStatus.SAFE_HOLD,
            decision_status=DecisionStatus.BLOCK,
            risk_level=RiskLevel.CRITICAL,
            allowed_release_l=0.0,
            protected_reserve_l=snapshot.protected_reserve_l,
            post_release_storage_l=0.0,
            reasons=("no stored water is available",),
            required_actions=(
                "do not report reserve availability",
                "activate alternate water-source review",
                "preserve empty-reserve evidence for response planning",
            ),
        )

    if snapshot.requested_release_l <= 0.0:
        return _no_release_result(snapshot, active_policy)

    if snapshot.requested_release_l > snapshot.stored_water_l:
        return EmergencyReserveResult(
            status=ReserveStatus.SAFE_HOLD,
            decision_status=DecisionStatus.BLOCK,
            risk_level=RiskLevel.CRITICAL,
            allowed_release_l=0.0,
            protected_reserve_l=snapshot.protected_reserve_l,
            post_release_storage_l=snapshot.stored_water_l,
            reasons=("requested release exceeds stored water volume",),
            required_actions=(
                "block release request",
                "correct inventory measurement or request volume",
                "repeat reserve review",
            ),
        )

    if snapshot.water_use_class is WaterUseClass.UNSAFE_HOLD:
        return EmergencyReserveResult(
            status=ReserveStatus.SAFE_HOLD,
            decision_status=DecisionStatus.BLOCK,
            risk_level=RiskLevel.CRITICAL,
            allowed_release_l=0.0,
            protected_reserve_l=snapshot.protected_reserve_l,
            post_release_storage_l=snapshot.stored_water_l,
            reasons=("reserve water is classified as unsafe hold",),
            required_actions=(
                "do not release reserve water",
                "route to treatment, disposal review, or qualified testing",
                "do not use unsafe-hold water for emergency distribution",
            ),
        )

    if snapshot.would_breach_protected_reserve:
        return _reserve_breach_result(snapshot, active_policy)

    coverage_reasons = _coverage_reasons(snapshot, active_policy)
    if coverage_reasons:
        return EmergencyReserveResult(
            status=ReserveStatus.CONSERVE,
            decision_status=DecisionStatus.ALLOW_REVIEW,
            risk_level=RiskLevel.MODERATE,
            allowed_release_l=snapshot.requested_release_l,
            protected_reserve_l=snapshot.protected_reserve_l,
            post_release_storage_l=snapshot.post_release_storage_l,
            reasons=coverage_reasons,
            required_actions=(
                "approve only through qualified human review",
                "prioritize life-safety and public-health uses",
                "replenish protected reserve before routine use",
                "preserve reserve decision record",
            ),
        )

    return EmergencyReserveResult(
        status=ReserveStatus.NORMAL,
        decision_status=DecisionStatus.ALLOW_REVIEW,
        risk_level=RiskLevel.LOW,
        allowed_release_l=snapshot.requested_release_l,
        protected_reserve_l=snapshot.protected_reserve_l,
        post_release_storage_l=snapshot.post_release_storage_l,
        reasons=("requested release preserves protected reserve and demand-coverage thresholds",),
        required_actions=(
            "human review required before release",
            "preserve reserve evidence bundle",
            "continue monitoring storage hygiene, tank integrity, and water-quality status",
        ),
    )


def _service_blockers(
    snapshot: EmergencyReserveSnapshot,
    policy: EmergencyReservePolicy,
) -> tuple[str, ...]:
    blockers: list[str] = []

    if not snapshot.storage_clean:
        blockers.append("storage cleanliness is not verified")
    if not snapshot.tank_integrity_verified:
        blockers.append("tank integrity is not verified")
    if not snapshot.quality_gate_passed:
        blockers.append("water-quality gate has not passed")
    if not snapshot.treatment_route_reviewed:
        blockers.append("treatment route has not been reviewed")
    if snapshot.storage_age_hours > policy.max_storage_age_hours_for_review:
        blockers.append("storage age exceeds configured review threshold")

    return tuple(blockers)


def _no_release_result(
    snapshot: EmergencyReserveSnapshot,
    policy: EmergencyReservePolicy,
) -> EmergencyReserveResult:
    coverage = snapshot.current_demand_coverage_days
    if coverage is not None and coverage < policy.min_post_release_coverage_days:
        return EmergencyReserveResult(
            status=ReserveStatus.CONSERVE,
            decision_status=DecisionStatus.ALLOW_REVIEW,
            risk_level=RiskLevel.MODERATE,
            allowed_release_l=0.0,
            protected_reserve_l=snapshot.protected_reserve_l,
            post_release_storage_l=snapshot.stored_water_l,
            reasons=("current reserve coverage is below configured minimum",),
            required_actions=(
                "do not release reserve water for routine use",
                "prioritize replenishment",
                "review alternate water sources",
            ),
        )

    return EmergencyReserveResult(
        status=ReserveStatus.NORMAL,
        decision_status=DecisionStatus.ALLOW_REVIEW,
        risk_level=RiskLevel.LOW,
        allowed_release_l=0.0,
        protected_reserve_l=snapshot.protected_reserve_l,
        post_release_storage_l=snapshot.stored_water_l,
        reasons=("no release requested and reserve evidence is reviewable",),
        required_actions=(
            "continue monitoring reserve state",
            "preserve water-quality and storage evidence",
            "human review required before future release",
        ),
    )


def _reserve_breach_result(
    snapshot: EmergencyReserveSnapshot,
    policy: EmergencyReservePolicy,
) -> EmergencyReserveResult:
    if snapshot.emergency_request_declared and policy.allow_emergency_review_below_reserve:
        return EmergencyReserveResult(
            status=ReserveStatus.EMERGENCY_REVIEW,
            decision_status=DecisionStatus.ALLOW_REVIEW,
            risk_level=RiskLevel.HIGH,
            allowed_release_l=snapshot.requested_release_l,
            protected_reserve_l=snapshot.protected_reserve_l,
            post_release_storage_l=snapshot.post_release_storage_l,
            reasons=(
                "requested emergency release would breach protected reserve",
                "emergency request is declared for human review",
            ),
            required_actions=(
                "require explicit emergency human authorization",
                "document why protected reserve breach is justified",
                "activate replenishment and alternate-source review",
                "do not treat this result as automatic distribution approval",
            ),
        )

    return EmergencyReserveResult(
        status=ReserveStatus.SAFE_HOLD,
        decision_status=DecisionStatus.BLOCK,
        risk_level=RiskLevel.CRITICAL,
        allowed_release_l=0.0,
        protected_reserve_l=snapshot.protected_reserve_l,
        post_release_storage_l=snapshot.stored_water_l,
        reasons=("requested release would breach protected emergency reserve",),
        required_actions=(
            "block routine release",
            "protect emergency reserve",
            "seek qualified emergency review if life-safety conditions exist",
        ),
    )


def _coverage_reasons(
    snapshot: EmergencyReserveSnapshot,
    policy: EmergencyReservePolicy,
) -> tuple[str, ...]:
    reasons: list[str] = []
    coverage = snapshot.post_release_demand_coverage_days

    if coverage is not None and coverage < policy.min_post_release_coverage_days:
        reasons.append("post-release demand coverage is below configured minimum")

    reserve_margin = snapshot.post_release_storage_l - snapshot.protected_reserve_l
    if reserve_margin < policy.min_routine_release_margin_l:
        reasons.append("post-release reserve margin is below configured routine-use margin")

    return tuple(reasons)


def _require_nonnegative_finite(name: str, value: float) -> None:
    if not isfinite(value):
        raise ValueError(f"{name} must be finite")
    if value < 0.0:
        raise ValueError(f"{name} cannot be negative")


def _require_positive_finite(name: str, value: float) -> None:
    if not isfinite(value):
        raise ValueError(f"{name} must be finite")
    if value <= 0.0:
        raise ValueError(f"{name} must be positive")
