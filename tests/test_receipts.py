from datetime import UTC, datetime
import json

import pytest

from ix_vahdat.domain import (
    Coordinates,
    DecisionStatus,
    EvidenceQuality,
    Measurement,
    RiskLevel,
    SiteContext,
)
from ix_vahdat.receipts import EvidenceInput, EvidenceReceipt, ReceiptKind, create_receipt


def _site() -> SiteContext:
    return SiteContext(
        site_id="site-alpha",
        name="Community Water Node Alpha",
        operator="local review team",
        coordinates=Coordinates(latitude=35.0, longitude=51.0),
        tags=("clinic", "proof-of-concept"),
        metadata={"deployment_class": "demo"},
    )


def _measurement() -> Measurement:
    return Measurement(
        name="turbidity",
        value=0.8,
        unit="NTU",
        source_id="turbidity-meter-1",
        timestamp=datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC),
        quality=EvidenceQuality.MEASURED,
    )


def _evidence_input() -> EvidenceInput:
    return EvidenceInput.from_measurement(_measurement())


def test_evidence_input_can_be_created_from_measurement() -> None:
    evidence = EvidenceInput.from_measurement(_measurement())

    assert evidence.name == "turbidity"
    assert evidence.value == 0.8
    assert evidence.unit == "NTU"
    assert evidence.source_id == "turbidity-meter-1"
    assert evidence.quality == "measured"
    assert evidence.sensor_status == "ok"
    assert evidence.timestamp == datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)


def test_evidence_input_rejects_blank_required_fields() -> None:
    with pytest.raises(ValueError, match="name"):
        EvidenceInput(
            name=" ",
            value=1.0,
            unit="NTU",
            source_id="sensor-1",
            quality="measured",
            sensor_status="ok",
        )


def test_evidence_input_rejects_naive_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        EvidenceInput(
            name="turbidity",
            value=1.0,
            unit="NTU",
            source_id="sensor-1",
            quality="measured",
            sensor_status="ok",
            timestamp=datetime(2026, 5, 14, 12, 0, 0),
        )


def test_receipt_requires_timezone_aware_creation_time() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        EvidenceReceipt(
            receipt_id="receipt-1",
            kind=ReceiptKind.WATER_USE_ASSESSMENT,
            created_at=datetime(2026, 5, 14, 12, 0, 0),
            site=_site(),
            summary="water-use gate result",
            decision_status=DecisionStatus.ALLOW_REVIEW,
            risk_level=RiskLevel.LOW,
            evidence_inputs=(_evidence_input(),),
            reasons=("triage thresholds passed",),
            required_actions=("human review required",),
        )


def test_create_receipt_generates_stable_content_derived_id() -> None:
    created_at = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)

    first = create_receipt(
        kind=ReceiptKind.WATER_USE_ASSESSMENT,
        created_at=created_at,
        site=_site(),
        summary="water-use gate result",
        decision_status=DecisionStatus.ALLOW_REVIEW,
        risk_level=RiskLevel.LOW,
        evidence_inputs=(_evidence_input(),),
        reasons=("triage thresholds passed",),
        required_actions=("human review required",),
        thresholds={"turbidity_ntu_max": 1.0},
        uncertainty_notes=("field reading requires local review",),
        reviewer_status="not_reviewed",
        metadata={"software_mode": "proof_of_concept"},
    )
    second = create_receipt(
        kind=ReceiptKind.WATER_USE_ASSESSMENT,
        created_at=created_at,
        site=_site(),
        summary="water-use gate result",
        decision_status=DecisionStatus.ALLOW_REVIEW,
        risk_level=RiskLevel.LOW,
        evidence_inputs=(_evidence_input(),),
        reasons=("triage thresholds passed",),
        required_actions=("human review required",),
        thresholds={"turbidity_ntu_max": 1.0},
        uncertainty_notes=("field reading requires local review",),
        reviewer_status="not_reviewed",
        metadata={"software_mode": "proof_of_concept"},
    )

    assert first.receipt_id == second.receipt_id
    assert first.receipt_id.startswith("ixv-water_use_assessment-")


def test_receipt_serializes_to_json_ready_dictionary() -> None:
    receipt = create_receipt(
        kind=ReceiptKind.WATER_USE_ASSESSMENT,
        created_at=datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC),
        site=_site(),
        summary="water-use gate result",
        decision_status=DecisionStatus.ALLOW_REVIEW,
        risk_level=RiskLevel.LOW,
        evidence_inputs=(_evidence_input(),),
        reasons=("triage thresholds passed",),
        required_actions=("human review required",),
        thresholds={"turbidity_ntu_max": 1.0},
        reviewer_status="not_reviewed",
    )

    payload = receipt.to_dict()

    assert payload["kind"] == "water_use_assessment"
    assert payload["site"]["site_id"] == "site-alpha"
    assert payload["site"]["coordinates"] == {"latitude": 35.0, "longitude": 51.0}
    assert payload["decision_status"] == "allow_review"
    assert payload["risk_level"] == "low"
    assert payload["evidence_inputs"][0]["name"] == "turbidity"


def test_receipt_json_is_deterministic_and_hashable() -> None:
    receipt = create_receipt(
        kind=ReceiptKind.WATER_USE_ASSESSMENT,
        created_at=datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC),
        site=_site(),
        summary="water-use gate result",
        decision_status=DecisionStatus.ALLOW_REVIEW,
        risk_level=RiskLevel.LOW,
        evidence_inputs=(_evidence_input(),),
        reasons=("triage thresholds passed",),
        required_actions=("human review required",),
    )

    loaded = json.loads(receipt.to_json())

    assert loaded["receipt_id"] == receipt.receipt_id
    assert len(receipt.content_hash()) == 64


def test_receipt_requires_at_least_one_evidence_input() -> None:
    with pytest.raises(ValueError, match="evidence input"):
        EvidenceReceipt(
            receipt_id="receipt-1",
            kind=ReceiptKind.WATER_USE_ASSESSMENT,
            created_at=datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC),
            site=_site(),
            summary="water-use gate result",
            decision_status=DecisionStatus.ALLOW_REVIEW,
            risk_level=RiskLevel.LOW,
            evidence_inputs=(),
            reasons=("triage thresholds passed",),
            required_actions=("human review required",),
        )


def test_receipt_mappings_are_immutable_after_creation() -> None:
    receipt = create_receipt(
        kind=ReceiptKind.WATER_USE_ASSESSMENT,
        created_at=datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC),
        site=_site(),
        summary="water-use gate result",
        decision_status=DecisionStatus.ALLOW_REVIEW,
        risk_level=RiskLevel.LOW,
        evidence_inputs=(_evidence_input(),),
        reasons=("triage thresholds passed",),
        required_actions=("human review required",),
        thresholds={"turbidity_ntu_max": 1.0},
        metadata={"software_mode": "proof_of_concept"},
    )

    with pytest.raises(TypeError):
        receipt.thresholds["turbidity_ntu_max"] = 2.0  # type: ignore[index]

    with pytest.raises(TypeError):
        receipt.metadata["software_mode"] = "changed"  # type: ignore[index]
