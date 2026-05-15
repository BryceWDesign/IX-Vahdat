"""IX-Vahdat package.

IX-Vahdat is a humanitarian water-resilience proof-of-concept.

The package is designed around evidence-gated decision support:
it may classify water-use candidates, account for energy and maintenance
constraints, prepare auditable records, and require human review before
field action.

It does not certify water as potable, replace licensed engineers or public
health authorities, issue permits, or authorize autonomous physical action.
"""

from ix_vahdat.domain import (
    Coordinates,
    DecisionStatus,
    EvidenceQuality,
    Measurement,
    RiskLevel,
    SensorStatus,
    SiteContext,
)
from ix_vahdat.quality import (
    WaterQualityGatePolicy,
    WaterQualityGateResult,
    evaluate_water_quality_gate,
)
from ix_vahdat.receipts import (
    EvidenceInput,
    EvidenceReceipt,
    ReceiptKind,
    create_receipt,
)
from ix_vahdat.review import (
    ReviewDecision,
    ReviewGateResult,
    ReviewerRecord,
    ReviewStatus,
    require_human_review,
)
from ix_vahdat.version import __version__
from ix_vahdat.water_use import (
    WaterQualitySnapshot,
    WaterUseAssessment,
    WaterUseClass,
    WaterUsePolicy,
    classify_water_use,
)

__all__ = [
    "Coordinates",
    "DecisionStatus",
    "EvidenceInput",
    "EvidenceQuality",
    "EvidenceReceipt",
    "Measurement",
    "ReceiptKind",
    "ReviewDecision",
    "ReviewGateResult",
    "ReviewerRecord",
    "ReviewStatus",
    "RiskLevel",
    "SensorStatus",
    "SiteContext",
    "WaterQualityGatePolicy",
    "WaterQualityGateResult",
    "WaterQualitySnapshot",
    "WaterUseAssessment",
    "WaterUseClass",
    "WaterUsePolicy",
    "__version__",
    "classify_water_use",
    "create_receipt",
    "evaluate_water_quality_gate",
    "require_human_review",
]
