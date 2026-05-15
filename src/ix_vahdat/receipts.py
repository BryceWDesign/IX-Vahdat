"""Evidence receipt schema for IX-Vahdat.

Receipts are structured decision records. They preserve what evidence was
available, which gate produced the output, which thresholds were used, why the
decision was made, and what actions remain required.

Receipts are not a certification, permit, public-health approval, engineering
stamp, or proof that field action is safe. They are review artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Any, Mapping

from ix_vahdat.domain import DecisionStatus, Measurement, RiskLevel, SiteContext


class ReceiptKind(str, Enum):
    """Supported evidence receipt categories."""

    WATER_USE_ASSESSMENT = "water_use_assessment"
    HUMAN_REVIEW_GATE = "human_review_gate"
    TREATMENT_ROUTING = "treatment_routing"
    ATMOSPHERIC_WATER_TRIAGE = "atmospheric_water_triage"
    ENERGY_ACCOUNTING = "energy_accounting"
    MAINTENANCE_CHECK = "maintenance_check"
    INFRASTRUCTURE_HEALTH = "infrastructure_health"
    SITE_READINESS = "site_readiness"
    FEASIBILITY_GATE = "feasibility_gate"


@dataclass(frozen=True, slots=True)
class EvidenceInput:
    """Serializable evidence item embedded in a receipt."""

    name: str
    value: float | str | bool | None
    unit: str | None
    source_id: str
    quality: str
    sensor_status: str
    timestamp: datetime | None = None
    uncertainty: float | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("evidence input name is required")
        if not self.source_id.strip():
            raise ValueError("evidence input source_id is required")
        if not self.quality.strip():
            raise ValueError("evidence input quality is required")
        if not self.sensor_status.strip():
            raise ValueError("evidence input sensor_status is required")
        if self.unit is not None and not self.unit.strip():
            raise ValueError("evidence input unit cannot be blank when provided")
        if self.timestamp is not None:
            if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
                raise ValueError("evidence input timestamp must be timezone-aware")
        if self.uncertainty is not None and self.uncertainty < 0:
            raise ValueError("evidence input uncertainty cannot be negative")
        if self.notes is not None and not self.notes.strip():
            raise ValueError("evidence input notes cannot be blank when provided")

    @classmethod
    def from_measurement(cls, measurement: Measurement) -> EvidenceInput:
        """Create an EvidenceInput from a Measurement."""

        return cls(
            name=measurement.name,
            value=measurement.value,
            unit=measurement.unit,
            source_id=measurement.source_id,
            quality=measurement.quality.value,
            sensor_status=measurement.sensor_status.value,
            timestamp=measurement.timestamp,
            uncertainty=measurement.uncertainty,
            notes=measurement.notes,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready dictionary."""

        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "source_id": self.source_id,
            "quality": self.quality,
            "sensor_status": self.sensor_status,
            "timestamp": self.timestamp.isoformat() if self.timestamp is not None else None,
            "uncertainty": self.uncertainty,
            "notes": self.notes,
        }


@dataclass(frozen=True, slots=True)
class EvidenceReceipt:
    """Structured evidence record for an IX-Vahdat decision-support event."""

    receipt_id: str
    kind: ReceiptKind
    created_at: datetime
    site: SiteContext
    summary: str
    decision_status: DecisionStatus
    risk_level: RiskLevel
    evidence_inputs: tuple[EvidenceInput, ...]
    reasons: tuple[str, ...]
    required_actions: tuple[str, ...]
    thresholds: Mapping[str, float | int | str | bool | None] = field(default_factory=dict)
    uncertainty_notes: tuple[str, ...] = ()
    reviewer_status: str | None = None
    reviewer_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.receipt_id.strip():
            raise ValueError("receipt_id is required")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        if not self.summary.strip():
            raise ValueError("receipt summary is required")
        if not self.evidence_inputs:
            raise ValueError("at least one evidence input is required")
        if not self.reasons:
            raise ValueError("at least one reason is required")
        if not self.required_actions:
            raise ValueError("at least one required action is required")
        if any(not reason.strip() for reason in self.reasons):
            raise ValueError("receipt reasons cannot contain blank values")
        if any(not action.strip() for action in self.required_actions):
            raise ValueError("receipt required_actions cannot contain blank values")
        if any(not note.strip() for note in self.uncertainty_notes):
            raise ValueError("receipt uncertainty_notes cannot contain blank values")
        if self.reviewer_status is not None and not self.reviewer_status.strip():
            raise ValueError("reviewer_status cannot be blank when provided")
        if self.reviewer_id is not None and not self.reviewer_id.strip():
            raise ValueError("reviewer_id cannot be blank when provided")
        object.__setattr__(self, "thresholds", MappingProxyType(dict(self.thresholds)))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready dictionary for storage or review."""

        return {
            "receipt_id": self.receipt_id,
            "kind": self.kind.value,
            "created_at": self.created_at.isoformat(),
            "site": {
                "site_id": self.site.site_id,
                "name": self.site.name,
                "operator": self.site.operator,
                "coordinates": (
                    {
                        "latitude": self.site.coordinates.latitude,
                        "longitude": self.site.coordinates.longitude,
                    }
                    if self.site.coordinates is not None
                    else None
                ),
                "tags": list(self.site.tags),
                "metadata": dict(self.site.metadata),
            },
            "summary": self.summary,
            "decision_status": self.decision_status.value,
            "risk_level": self.risk_level.value,
            "evidence_inputs": [item.to_dict() for item in self.evidence_inputs],
            "reasons": list(self.reasons),
            "required_actions": list(self.required_actions),
            "thresholds": dict(self.thresholds),
            "uncertainty_notes": list(self.uncertainty_notes),
            "reviewer_status": self.reviewer_status,
            "reviewer_id": self.reviewer_id,
            "metadata": dict(self.metadata),
        }

    def to_json(self) -> str:
        """Return a deterministic JSON representation."""

        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    def content_hash(self) -> str:
        """Return a SHA-256 hash of the receipt content.

        This is useful for detecting accidental changes in exported evidence
        records. It is not a substitute for a full cryptographic signing or
        secure audit-log system.
        """

        return sha256(self.to_json().encode("utf-8")).hexdigest()


def create_receipt(
    *,
    kind: ReceiptKind,
    created_at: datetime,
    site: SiteContext,
    summary: str,
    decision_status: DecisionStatus,
    risk_level: RiskLevel,
    evidence_inputs: tuple[EvidenceInput, ...],
    reasons: tuple[str, ...],
    required_actions: tuple[str, ...],
    thresholds: Mapping[str, float | int | str | bool | None] | None = None,
    uncertainty_notes: tuple[str, ...] = (),
    reviewer_status: str | None = None,
    reviewer_id: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> EvidenceReceipt:
    """Create an evidence receipt with a deterministic content-derived ID."""

    receipt_id = _build_receipt_id(
        kind=kind,
        created_at=created_at,
        site=site,
        summary=summary,
        decision_status=decision_status,
        risk_level=risk_level,
        evidence_inputs=evidence_inputs,
        reasons=reasons,
        required_actions=required_actions,
        thresholds=thresholds or {},
        uncertainty_notes=uncertainty_notes,
        reviewer_status=reviewer_status,
        reviewer_id=reviewer_id,
        metadata=metadata or {},
    )
    return EvidenceReceipt(
        receipt_id=receipt_id,
        kind=kind,
        created_at=created_at,
        site=site,
        summary=summary,
        decision_status=decision_status,
        risk_level=risk_level,
        evidence_inputs=evidence_inputs,
        reasons=reasons,
        required_actions=required_actions,
        thresholds=thresholds or {},
        uncertainty_notes=uncertainty_notes,
        reviewer_status=reviewer_status,
        reviewer_id=reviewer_id,
        metadata=metadata or {},
    )


def _build_receipt_id(
    *,
    kind: ReceiptKind,
    created_at: datetime,
    site: SiteContext,
    summary: str,
    decision_status: DecisionStatus,
    risk_level: RiskLevel,
    evidence_inputs: tuple[EvidenceInput, ...],
    reasons: tuple[str, ...],
    required_actions: tuple[str, ...],
    thresholds: Mapping[str, float | int | str | bool | None],
    uncertainty_notes: tuple[str, ...],
    reviewer_status: str | None,
    reviewer_id: str | None,
    metadata: Mapping[str, Any],
) -> str:
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise ValueError("created_at must be timezone-aware")

    payload = {
        "kind": kind.value,
        "created_at": created_at.isoformat(),
        "site_id": site.site_id,
        "summary": summary,
        "decision_status": decision_status.value,
        "risk_level": risk_level.value,
        "evidence_inputs": [item.to_dict() for item in evidence_inputs],
        "reasons": list(reasons),
        "required_actions": list(required_actions),
        "thresholds": dict(thresholds),
        "uncertainty_notes": list(uncertainty_notes),
        "reviewer_status": reviewer_status,
        "reviewer_id": reviewer_id,
        "metadata": dict(metadata),
    }
    digest = sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"ixv-{kind.value}-{digest[:24]}"
