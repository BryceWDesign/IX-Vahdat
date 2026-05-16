"""Evidence bundle exporter for IX-Vahdat.

Bundles group evidence receipts into deterministic JSON artifacts that reviewers
can inspect, archive, and compare. Bundle hashes help detect accidental drift or
tampering in review artifacts.

A bundle is not a certification, public-health approval, permit, deployment
authorization, legal record, or secure signing system. It is a structured
software evidence package for human review.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Any, Mapping

from ix_vahdat.domain import DecisionStatus, RiskLevel, SiteContext
from ix_vahdat.receipts import EvidenceReceipt


@dataclass(frozen=True, slots=True)
class BundleItem:
    """Receipt snapshot embedded in an evidence bundle."""

    receipt_id: str
    receipt_hash: str
    receipt_kind: str
    decision_status: str
    risk_level: str
    summary: str
    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not self.receipt_id.strip():
            raise ValueError("receipt_id is required")
        if not self.receipt_hash.strip():
            raise ValueError("receipt_hash is required")
        if len(self.receipt_hash) != 64:
            raise ValueError("receipt_hash must be a 64-character SHA-256 digest")
        if not self.receipt_kind.strip():
            raise ValueError("receipt_kind is required")
        if not self.decision_status.strip():
            raise ValueError("decision_status is required")
        if not self.risk_level.strip():
            raise ValueError("risk_level is required")
        if not self.summary.strip():
            raise ValueError("summary is required")
        if not self.payload:
            raise ValueError("payload is required")
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))

    @classmethod
    def from_receipt(cls, receipt: EvidenceReceipt) -> BundleItem:
        """Create a bundle item from an evidence receipt."""

        return cls(
            receipt_id=receipt.receipt_id,
            receipt_hash=receipt.content_hash(),
            receipt_kind=receipt.kind.value,
            decision_status=receipt.decision_status.value,
            risk_level=receipt.risk_level.value,
            summary=receipt.summary,
            payload=receipt.to_dict(),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready bundle item payload."""

        return {
            "receipt_id": self.receipt_id,
            "receipt_hash": self.receipt_hash,
            "receipt_kind": self.receipt_kind,
            "decision_status": self.decision_status,
            "risk_level": self.risk_level,
            "summary": self.summary,
            "payload": dict(self.payload),
        }

    def payload_hash(self) -> str:
        """Return a hash of the embedded receipt payload."""

        return sha256(
            json.dumps(
                self.payload,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

    def payload_hash_matches(self) -> bool:
        """Return True when the embedded payload still matches receipt_hash."""

        return self.payload_hash() == self.receipt_hash


@dataclass(frozen=True, slots=True)
class EvidenceBundle:
    """Deterministic review package containing one or more receipt snapshots."""

    bundle_id: str
    created_at: datetime
    site: SiteContext
    title: str
    decision_status: DecisionStatus
    risk_level: RiskLevel
    items: tuple[BundleItem, ...]
    non_claims: tuple[str, ...]
    required_actions: tuple[str, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.bundle_id.strip():
            raise ValueError("bundle_id is required")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        if not self.title.strip():
            raise ValueError("bundle title is required")
        if not self.items:
            raise ValueError("at least one bundle item is required")
        if not self.non_claims:
            raise ValueError("at least one non-claim is required")
        if not self.required_actions:
            raise ValueError("at least one required action is required")
        if any(not claim.strip() for claim in self.non_claims):
            raise ValueError("non_claims cannot contain blank values")
        if any(not action.strip() for action in self.required_actions):
            raise ValueError("required_actions cannot contain blank values")

        receipt_ids = [item.receipt_id for item in self.items]
        if len(receipt_ids) != len(set(receipt_ids)):
            raise ValueError("bundle item receipt_id values must be unique")

        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready evidence bundle."""

        return {
            "bundle_id": self.bundle_id,
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
            "title": self.title,
            "decision_status": self.decision_status.value,
            "risk_level": self.risk_level.value,
            "items": [item.to_dict() for item in self.items],
            "non_claims": list(self.non_claims),
            "required_actions": list(self.required_actions),
            "metadata": dict(self.metadata),
        }

    def to_json(self) -> str:
        """Return deterministic JSON for export or comparison."""

        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    def content_hash(self) -> str:
        """Return SHA-256 hash of the full bundle content."""

        return sha256(self.to_json().encode("utf-8")).hexdigest()

    def receipt_hashes_match(self) -> bool:
        """Return True when every embedded receipt payload matches its hash."""

        return all(item.payload_hash_matches() for item in self.items)


def create_evidence_bundle(
    *,
    created_at: datetime,
    site: SiteContext,
    title: str,
    receipts: tuple[EvidenceReceipt, ...],
    decision_status: DecisionStatus,
    risk_level: RiskLevel,
    non_claims: tuple[str, ...] = (
        "not a certified drinking-water system",
        "not a potable-water certification",
        "not a public-health approval",
        "not a permit substitute",
        "not a construction authorization",
        "not an autonomous physical-control instruction",
        "not field-deployment authorization",
    ),
    required_actions: tuple[str, ...] = (
        "review all receipts with qualified humans",
        "replace synthetic or estimated evidence with verified local measurements",
        "obtain applicable local approval before field action",
        "preserve the exported bundle and content hash",
    ),
    metadata: Mapping[str, Any] | None = None,
) -> EvidenceBundle:
    """Create a deterministic evidence bundle from receipts."""

    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise ValueError("created_at must be timezone-aware")

    items = tuple(BundleItem.from_receipt(receipt) for receipt in receipts)
    bundle_id = _bundle_id(
        created_at=created_at,
        site=site,
        title=title,
        decision_status=decision_status,
        risk_level=risk_level,
        items=items,
        non_claims=non_claims,
        required_actions=required_actions,
        metadata=metadata or {},
    )

    return EvidenceBundle(
        bundle_id=bundle_id,
        created_at=created_at,
        site=site,
        title=title,
        decision_status=decision_status,
        risk_level=risk_level,
        items=items,
        non_claims=non_claims,
        required_actions=required_actions,
        metadata=metadata or {},
    )


def _bundle_id(
    *,
    created_at: datetime,
    site: SiteContext,
    title: str,
    decision_status: DecisionStatus,
    risk_level: RiskLevel,
    items: tuple[BundleItem, ...],
    non_claims: tuple[str, ...],
    required_actions: tuple[str, ...],
    metadata: Mapping[str, Any],
) -> str:
    payload = {
        "created_at": created_at.isoformat(),
        "site_id": site.site_id,
        "title": title,
        "decision_status": decision_status.value,
        "risk_level": risk_level.value,
        "items": [item.to_dict() for item in items],
        "non_claims": list(non_claims),
        "required_actions": list(required_actions),
        "metadata": dict(metadata),
    }
    digest = sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"ixv-bundle-{digest[:24]}"
