from datetime import UTC, datetime
import json

import pytest

from ix_vahdat.bundles import BundleItem, EvidenceBundle, create_evidence_bundle
from ix_vahdat.domain import (
    Coordinates,
    DecisionStatus,
    EvidenceQuality,
    Measurement,
    RiskLevel,
    SiteContext,
)
from ix_vahdat.receipts import EvidenceInput, ReceiptKind, create_receipt


CREATED_AT = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)


def _site() -> SiteContext:
    return SiteContext(
        site_id="site-alpha",
        name="Community Water Node Alpha",
        operator="local review team",
        coordinates=Coordinates(latitude=35.0, longitude=51.0),
        tags=("synthetic-demo", "review"),
        metadata={"field_deployment": False},
    )


def _receipt(summary: str = "water-use gate result"):
    measurement = Measurement(
        name="turbidity",
        value=0.8,
        unit="NTU",
        source_id="turbidity-meter-1",
        timestamp=CREATED_AT,
        quality=EvidenceQuality.MEASURED,
    )
    return create_receipt(
        kind=ReceiptKind.WATER_USE_ASSESSMENT,
        created_at=CREATED_AT,
        site=_site(),
        summary=summary,
        decision_status=DecisionStatus.ALLOW_REVIEW,
        risk_level=RiskLevel.LOW,
        evidence_inputs=(EvidenceInput.from_measurement(measurement),),
        reasons=("triage thresholds passed",),
        required_actions=("human review required",),
        thresholds={"turbidity_ntu_max": 1.0},
        reviewer_status="not_reviewed",
    )


def test_bundle_item_created_from_receipt_contains_matching_hash() -> None:
    receipt = _receipt()
    item = BundleItem.from_receipt(receipt)

    assert item.receipt_id == receipt.receipt_id
    assert item.receipt_hash == receipt.content_hash()
    assert item.receipt_kind == "water_use_assessment"
    assert item.decision_status == "allow_review"
    assert item.risk_level == "low"
    assert item.payload_hash_matches() is True


def test_bundle_item_rejects_invalid_hash_length() -> None:
    with pytest.raises(ValueError, match="64-character"):
        BundleItem(
            receipt_id="receipt-1",
            receipt_hash="not-a-sha",
            receipt_kind="water_use_assessment",
            decision_status="allow_review",
            risk_level="low",
            summary="summary",
            payload={"receipt_id": "receipt-1"},
        )


def test_create_evidence_bundle_generates_stable_id() -> None:
    receipt = _receipt()

    first = create_evidence_bundle(
        created_at=CREATED_AT,
        site=_site(),
        title="Synthetic review bundle",
        receipts=(receipt,),
        decision_status=DecisionStatus.ALLOW_REVIEW,
        risk_level=RiskLevel.LOW,
        metadata={"synthetic": True},
    )
    second = create_evidence_bundle(
        created_at=CREATED_AT,
        site=_site(),
        title="Synthetic review bundle",
        receipts=(receipt,),
        decision_status=DecisionStatus.ALLOW_REVIEW,
        risk_level=RiskLevel.LOW,
        metadata={"synthetic": True},
    )

    assert first.bundle_id == second.bundle_id
    assert first.bundle_id.startswith("ixv-bundle-")
    assert first.receipt_hashes_match() is True


def test_bundle_serializes_to_deterministic_json() -> None:
    bundle = create_evidence_bundle(
        created_at=CREATED_AT,
        site=_site(),
        title="Synthetic review bundle",
        receipts=(_receipt(),),
        decision_status=DecisionStatus.ALLOW_REVIEW,
        risk_level=RiskLevel.LOW,
        metadata={"synthetic": True},
    )

    payload = json.loads(bundle.to_json())

    assert payload["bundle_id"] == bundle.bundle_id
    assert payload["title"] == "Synthetic review bundle"
    assert payload["decision_status"] == "allow_review"
    assert payload["risk_level"] == "low"
    assert payload["site"]["site_id"] == "site-alpha"
    assert payload["items"][0]["payload"]["kind"] == "water_use_assessment"
    assert len(bundle.content_hash()) == 64


def test_bundle_preserves_non_claims() -> None:
    bundle = create_evidence_bundle(
        created_at=CREATED_AT,
        site=_site(),
        title="Synthetic review bundle",
        receipts=(_receipt(),),
        decision_status=DecisionStatus.ALLOW_REVIEW,
        risk_level=RiskLevel.LOW,
    )

    assert "not a potable-water certification" in bundle.non_claims
    assert "not field-deployment authorization" in bundle.non_claims


def test_bundle_rejects_naive_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        create_evidence_bundle(
            created_at=datetime(2026, 5, 14, 12, 0, 0),
            site=_site(),
            title="Synthetic review bundle",
            receipts=(_receipt(),),
            decision_status=DecisionStatus.ALLOW_REVIEW,
            risk_level=RiskLevel.LOW,
        )


def test_bundle_rejects_empty_receipts() -> None:
    with pytest.raises(ValueError, match="at least one bundle item"):
        create_evidence_bundle(
            created_at=CREATED_AT,
            site=_site(),
            title="Synthetic review bundle",
            receipts=(),
            decision_status=DecisionStatus.ALLOW_REVIEW,
            risk_level=RiskLevel.LOW,
        )


def test_bundle_rejects_duplicate_receipt_ids() -> None:
    receipt = _receipt()

    with pytest.raises(ValueError, match="unique"):
        EvidenceBundle(
            bundle_id="bundle-1",
            created_at=CREATED_AT,
            site=_site(),
            title="Synthetic review bundle",
            decision_status=DecisionStatus.ALLOW_REVIEW,
            risk_level=RiskLevel.LOW,
            items=(BundleItem.from_receipt(receipt), BundleItem.from_receipt(receipt)),
            non_claims=("not a potable-water certification",),
            required_actions=("human review required",),
        )


def test_bundle_mappings_are_immutable_after_creation() -> None:
    bundle = create_evidence_bundle(
        created_at=CREATED_AT,
        site=_site(),
        title="Synthetic review bundle",
        receipts=(_receipt(),),
        decision_status=DecisionStatus.ALLOW_REVIEW,
        risk_level=RiskLevel.LOW,
        metadata={"synthetic": True},
    )

    with pytest.raises(TypeError):
        bundle.metadata["synthetic"] = False  # type: ignore[index]

    with pytest.raises(TypeError):
        bundle.items[0].payload["summary"] = "changed"  # type: ignore[index]
