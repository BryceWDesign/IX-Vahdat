"""IX-Vahdat package.

IX-Vahdat is a humanitarian water-resilience proof-of-concept.

The package is designed around evidence-gated decision support:
it may classify water-use candidates, account for energy and maintenance
constraints, prepare auditable records, and require human review before
field action.

It does not certify water as potable, replace licensed engineers or public
health authorities, issue permits, or authorize autonomous physical action.
"""

from ix_vahdat.atmospheric import (
    AtmosphericSiteConstraints,
    AtmosphericWaterClimate,
    AtmosphericWaterInputs,
)
from ix_vahdat.awh import (
    AWHMode,
    AWHTriageOption,
    AWHTriagePolicy,
    AWHTriageResult,
    triage_atmospheric_water,
)
from ix_vahdat.awh_scoring import (
    AWHModeScore,
    AWHScoreBand,
    score_awh_modes,
)
from ix_vahdat.domain import (
    Coordinates,
    DecisionStatus,
    EvidenceQuality,
    Measurement,
    RiskLevel,
    SensorStatus,
    SiteContext,
)
from ix_vahdat.energy import (
    EnergyAccountingPolicy,
    EnergyAccountingResult,
    EnergySnapshot,
    EnergySource,
    calculate_energy_accounting,
)
from ix_vahdat.energy_profile import (
    EnergyPortfolioPolicy,
    EnergyPortfolioResult,
    EnergyProfileAssessment,
    WaterEnergyProfile,
    WaterSupportPath,
    evaluate_energy_portfolio,
)
from ix_vahdat.failures import (
    FailureCategory,
    FailureEvaluationPolicy,
    FailureEvaluationResult,
    FailureMode,
    FailureRegistry,
    FailureSeverity,
    evaluate_failure_modes,
)
from ix_vahdat.maintenance import (
    MaintenanceCategory,
    MaintenanceItem,
    MaintenancePolicy,
    MaintenanceResult,
    MaintenanceState,
    MaintenanceSnapshot,
    evaluate_maintenance,
)
from ix_vahdat.power import (
    LoadPriority,
    PowerLoad,
    PowerMode,
    PowerPriorityPolicy,
    PowerPriorityResult,
    PowerSystemSnapshot,
    evaluate_power_priority,
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
from ix_vahdat.reserve import (
    EmergencyReservePolicy,
    EmergencyReserveResult,
    EmergencyReserveSnapshot,
    ReserveStatus,
    evaluate_emergency_reserve,
)
from ix_vahdat.review import (
    ReviewDecision,
    ReviewGateResult,
    ReviewerRecord,
    ReviewStatus,
    require_human_review,
)
from ix_vahdat.treatment import (
    TreatmentRoute,
    TreatmentRoutingPolicy,
    TreatmentRoutingResult,
    TreatmentSystemSnapshot,
    route_treatment_batch,
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
    "AWHMode",
    "AWHModeScore",
    "AWHScoreBand",
    "AWHTriageOption",
    "AWHTriagePolicy",
    "AWHTriageResult",
    "AtmosphericSiteConstraints",
    "AtmosphericWaterClimate",
    "AtmosphericWaterInputs",
    "Coordinates",
    "DecisionStatus",
    "EmergencyReservePolicy",
    "EmergencyReserveResult",
    "EmergencyReserveSnapshot",
    "EnergyAccountingPolicy",
    "EnergyAccountingResult",
    "EnergyPortfolioPolicy",
    "EnergyPortfolioResult",
    "EnergyProfileAssessment",
    "EnergySnapshot",
    "EnergySource",
    "EvidenceInput",
    "EvidenceQuality",
    "EvidenceReceipt",
    "FailureCategory",
    "FailureEvaluationPolicy",
    "FailureEvaluationResult",
    "FailureMode",
    "FailureRegistry",
    "FailureSeverity",
    "LoadPriority",
    "MaintenanceCategory",
    "MaintenanceItem",
    "MaintenancePolicy",
    "MaintenanceResult",
    "MaintenanceSnapshot",
    "MaintenanceState",
    "Measurement",
    "PowerLoad",
    "PowerMode",
    "PowerPriorityPolicy",
    "PowerPriorityResult",
    "PowerSystemSnapshot",
    "ReceiptKind",
    "ReserveStatus",
    "ReviewDecision",
    "ReviewGateResult",
    "ReviewerRecord",
    "ReviewStatus",
    "RiskLevel",
    "SensorStatus",
    "SiteContext",
    "TreatmentRoute",
    "TreatmentRoutingPolicy",
    "TreatmentRoutingResult",
    "TreatmentSystemSnapshot",
    "WaterEnergyProfile",
    "WaterQualityGatePolicy",
    "WaterQualityGateResult",
    "WaterQualitySnapshot",
    "WaterSupportPath",
    "WaterUseAssessment",
    "WaterUseClass",
    "WaterUsePolicy",
    "__version__",
    "calculate_energy_accounting",
    "classify_water_use",
    "create_receipt",
    "evaluate_emergency_reserve",
    "evaluate_energy_portfolio",
    "evaluate_failure_modes",
    "evaluate_maintenance",
    "evaluate_power_priority",
    "evaluate_water_quality_gate",
    "require_human_review",
    "route_treatment_batch",
    "score_awh_modes",
    "triage_atmospheric_water",
]
