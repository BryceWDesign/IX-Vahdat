"""Assembly and commissioning runbook gates for IX-Vahdat.

Runbooks convert build, inspection, calibration, commissioning, and review
procedures into auditable hold points. They are intentionally review-only:
a completed runbook does not certify the system, approve field operation,
authorize water distribution, or replace local engineering and public-health
requirements.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ix_vahdat.bom import DeploymentTier
from ix_vahdat.domain import DecisionStatus, RiskLevel


class RunbookStepKind(str, Enum):
    """Procedure step category for water-node assembly and commissioning."""

    SAFETY_BRIEF = "safety_brief"
    INVENTORY_CHECK = "inventory_check"
    ASSEMBLY = "assembly"
    SENSOR_CALIBRATION = "sensor_calibration"
    WATER_QUALITY_CHECK = "water_quality_check"
    ENERGY_CHECK = "energy_check"
    POWER_CHECK = "power_check"
    MAINTENANCE_CHECK = "maintenance_check"
    INFRASTRUCTURE_CHECK = "infrastructure_check"
    EVIDENCE_EXPORT = "evidence_export"
    HUMAN_REVIEW = "human_review"
    HOLD_POINT = "hold_point"


class RunbookStepStatus(str, Enum):
    """Observed completion state for one runbook step."""

    NOT_STARTED = "not_started"
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True, slots=True)
class RunbookStep:
    """One required assembly or commissioning procedure step."""

    step_id: str
    title: str
    kind: RunbookStepKind
    instructions: tuple[str, ...]
    required_evidence: tuple[str, ...] = ()
    requires_human_review: bool = False
    hold_point: bool = False
    safety_critical: bool = False
    notes: str | None = None

    def __post_init__(self) -> None:
        if not self.step_id.strip():
            raise ValueError("step_id is required")
        if not self.title.strip():
            raise ValueError("step title is required")
        if not self.instructions:
            raise ValueError("step instructions must contain at least one instruction")
        if any(not instruction.strip() for instruction in self.instructions):
            raise ValueError("step instructions cannot contain blank values")
        if any(not evidence.strip() for evidence in self.required_evidence):
            raise ValueError("required_evidence cannot contain blank values")
        if self.notes is not None and not self.notes.strip():
            raise ValueError("step notes cannot be blank when provided")

    @property
    def requires_evidence(self) -> bool:
        """Return True when this step must have evidence references to pass."""

        return bool(self.required_evidence)


@dataclass(frozen=True, slots=True)
class RunbookStepResult:
    """Observed result for one runbook step."""

    step_id: str
    status: RunbookStepStatus
    evidence_refs: tuple[str, ...] = ()
    reviewer_id: str | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        if not self.step_id.strip():
            raise ValueError("step_id is required")
        if any(not evidence_ref.strip() for evidence_ref in self.evidence_refs):
            raise ValueError("evidence_refs cannot contain blank values")
        if self.reviewer_id is not None and not self.reviewer_id.strip():
            raise ValueError("reviewer_id cannot be blank when provided")
        if self.notes is not None and not self.notes.strip():
            raise ValueError("step result notes cannot be blank when provided")


@dataclass(frozen=True, slots=True)
class WaterNodeRunbook:
    """Review-only assembly or commissioning runbook for a water node."""

    runbook_id: str
    title: str
    deployment_tier: DeploymentTier
    steps: tuple[RunbookStep, ...]
    non_claims: tuple[str, ...] = (
        "runbook completion is not field-deployment authorization",
        "runbook completion is not a potable-water certification",
        "runbook completion is not a public-health approval",
        "runbook completion is not a permit substitute",
        "runbook completion does not authorize autonomous physical control",
    )

    def __post_init__(self) -> None:
        if not self.runbook_id.strip():
            raise ValueError("runbook_id is required")
        if not self.title.strip():
            raise ValueError("runbook title is required")
        if not self.steps:
            raise ValueError("runbook must contain at least one step")
        if not self.non_claims:
            raise ValueError("runbook must contain at least one non-claim")
        if any(not claim.strip() for claim in self.non_claims):
            raise ValueError("runbook non_claims cannot contain blank values")

        step_ids = [step.step_id for step in self.steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("runbook step_id values must be unique")

    @property
    def hold_point_step_ids(self) -> tuple[str, ...]:
        """Return IDs for hold-point steps."""

        return tuple(step.step_id for step in self.steps if step.hold_point)

    @property
    def safety_critical_step_ids(self) -> tuple[str, ...]:
        """Return IDs for safety-critical steps."""

        return tuple(step.step_id for step in self.steps if step.safety_critical)


@dataclass(frozen=True, slots=True)
class RunbookEvaluationResult:
    """Decision-support output for runbook completion state."""

    decision_status: DecisionStatus
    risk_level: RiskLevel
    completed_steps: tuple[str, ...]
    incomplete_steps: tuple[str, ...]
    blocked_steps: tuple[str, ...]
    hold_point_steps: tuple[str, ...]
    reasons: tuple[str, ...]
    required_actions: tuple[str, ...]

    @property
    def runbook_ready_for_review(self) -> bool:
        """Return True when the runbook may continue to human review."""

        return (
            self.decision_status is DecisionStatus.ALLOW_REVIEW
            and not self.incomplete_steps
            and not self.blocked_steps
        )


def evaluate_runbook(
    *,
    runbook: WaterNodeRunbook,
    results: tuple[RunbookStepResult, ...],
) -> RunbookEvaluationResult:
    """Evaluate assembly or commissioning runbook completion.

    A passing result means the runbook evidence may continue to review. It does
    not authorize field action, water use, construction, distribution, or public
    deployment.
    """

    result_ids = [result.step_id for result in results]
    if len(result_ids) != len(set(result_ids)):
        raise ValueError("runbook result step_id values must be unique")

    step_by_id = {step.step_id: step for step in runbook.steps}
    unknown_result_ids = tuple(step_id for step_id in result_ids if step_id not in step_by_id)
    if unknown_result_ids:
        raise ValueError(f"unknown runbook step result ids: {unknown_result_ids}")

    results_by_id = {result.step_id: result for result in results}

    completed_steps: list[str] = []
    incomplete_steps: list[str] = []
    blocked_steps: list[str] = []
    hold_point_steps: list[str] = []
    reasons: list[str] = []
    required_actions: list[str] = []

    for step in runbook.steps:
        result = results_by_id.get(step.step_id)
        if result is None:
            incomplete_steps.append(step.step_id)
            reasons.append(f"{step.title} has no recorded result")
            required_actions.append(f"record result for {step.title}")
            continue

        if step.hold_point:
            hold_point_steps.append(step.step_id)

        if result.status is RunbookStepStatus.NOT_APPLICABLE:
            completed_steps.append(step.step_id)
            continue

        if result.status is RunbookStepStatus.NOT_STARTED:
            incomplete_steps.append(step.step_id)
            reasons.append(f"{step.title} is not started")
            required_actions.append(f"complete or explicitly mark {step.title} as not applicable")
            continue

        if result.status in {RunbookStepStatus.FAILED, RunbookStepStatus.BLOCKED}:
            blocked_steps.append(step.step_id)
            reasons.append(f"{step.title} result is {result.status.value}")
            required_actions.extend(_blocked_step_actions(step))
            continue

        if step.requires_evidence and not result.evidence_refs:
            incomplete_steps.append(step.step_id)
            reasons.append(f"{step.title} passed without required evidence references")
            required_actions.append(f"attach evidence references for {step.title}")
            continue

        if (step.requires_human_review or step.hold_point) and result.reviewer_id is None:
            incomplete_steps.append(step.step_id)
            reasons.append(f"{step.title} requires human reviewer identity")
            required_actions.append(f"record reviewer identity for {step.title}")
            continue

        completed_steps.append(step.step_id)

    if blocked_steps:
        risk = _blocked_risk(runbook, tuple(blocked_steps))
        decision_status = DecisionStatus.BLOCK if risk is RiskLevel.CRITICAL else DecisionStatus.HOLD_FOR_TESTING
        return RunbookEvaluationResult(
            decision_status=decision_status,
            risk_level=risk,
            completed_steps=tuple(completed_steps),
            incomplete_steps=tuple(incomplete_steps),
            blocked_steps=tuple(blocked_steps),
            hold_point_steps=tuple(hold_point_steps),
            reasons=tuple(_dedupe(reasons)),
            required_actions=tuple(
                _dedupe(
                    required_actions
                    + [
                        "hold assembly or commissioning until blocked steps are resolved",
                        "preserve failed-step evidence for human review",
                        "do not treat runbook as field authorization",
                    ]
                )
            ),
        )

    if incomplete_steps:
        return RunbookEvaluationResult(
            decision_status=DecisionStatus.HOLD_FOR_TESTING,
            risk_level=RiskLevel.HIGH,
            completed_steps=tuple(completed_steps),
            incomplete_steps=tuple(incomplete_steps),
            blocked_steps=(),
            hold_point_steps=tuple(hold_point_steps),
            reasons=tuple(_dedupe(reasons)),
            required_actions=tuple(
                _dedupe(
                    required_actions
                    + [
                        "complete missing runbook evidence before field review",
                        "human review required before any physical operation",
                    ]
                )
            ),
        )

    return RunbookEvaluationResult(
        decision_status=DecisionStatus.ALLOW_REVIEW,
        risk_level=RiskLevel.LOW,
        completed_steps=tuple(completed_steps),
        incomplete_steps=(),
        blocked_steps=(),
        hold_point_steps=tuple(hold_point_steps),
        reasons=("runbook steps are complete and evidence is reviewable",),
        required_actions=(
            "continue only to qualified human review",
            "preserve runbook result evidence",
            "do not claim certification, public-health approval, or deployment authorization",
        ),
    )


def _blocked_step_actions(step: RunbookStep) -> tuple[str, ...]:
    actions = [f"resolve failed or blocked step: {step.title}"]

    if step.safety_critical:
        actions.append("safety-critical step blocks dependent water-support decisions")
    if step.hold_point:
        actions.append("hold point must be resolved before continuing")
    if step.requires_human_review:
        actions.append("qualified human review required before continuing")

    return tuple(actions)


def _blocked_risk(
    runbook: WaterNodeRunbook,
    blocked_steps: tuple[str, ...],
) -> RiskLevel:
    by_id = {step.step_id: step for step in runbook.steps}

    for step_id in blocked_steps:
        step = by_id[step_id]
        if step.safety_critical or step.hold_point:
            return RiskLevel.CRITICAL

    return RiskLevel.HIGH


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        cleaned.append(value)
    return cleaned
