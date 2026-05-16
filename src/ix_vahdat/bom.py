"""Vendor-neutral BOM and cost-range estimator for IX-Vahdat.

This module totals user-supplied bill-of-materials cost ranges for humanitarian
water-resilience planning. It intentionally avoids vendor lock-in and does not
claim that any listed cost is current, locally available, certified, complete,
or procurement-ready.

The estimator is for planning and review only. It is not a purchasing order,
engineering bill of materials, safety certification, public-health approval,
or guarantee that a node can be built at the estimated cost.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping


class DeploymentTier(str, Enum):
    """Planning tier for a water-resilience node."""

    DEMO_NODE = "demo_node"
    SCHOOL_CLINIC_NODE = "school_clinic_node"
    COMMUNITY_NODE = "community_node"
    ADVANCED_HUB = "advanced_hub"


class BOMCategory(str, Enum):
    """Vendor-neutral BOM category."""

    WATER_QUALITY = "water_quality"
    TREATMENT = "treatment"
    ATMOSPHERIC_COLLECTION = "atmospheric_collection"
    STORAGE = "storage"
    ENERGY = "energy"
    POWER_ELECTRONICS = "power_electronics"
    PUMPING = "pumping"
    TELEMETRY = "telemetry"
    STRUCTURE = "structure"
    SAFETY = "safety"
    MAINTENANCE = "maintenance"
    CONSUMABLES = "consumables"
    LAB_REVIEW = "lab_review"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class BOMItem:
    """One vendor-neutral BOM line item.

    Cost ranges must be supplied by the caller. IX-Vahdat does not embed live
    pricing or claim that any estimate is current.
    """

    item_id: str
    label: str
    category: BOMCategory
    quantity: float
    unit: str
    unit_cost_low: float
    unit_cost_high: float
    currency: str = "USD"
    required: bool = True
    field_replaceable: bool = True
    local_substitution_allowed: bool = True
    notes: str | None = None

    def __post_init__(self) -> None:
        if not self.item_id.strip():
            raise ValueError("item_id is required")
        if not self.label.strip():
            raise ValueError("label is required")
        if not self.unit.strip():
            raise ValueError("unit is required")
        if not self.currency.strip():
            raise ValueError("currency is required")

        _require_positive_finite("quantity", self.quantity)
        _require_nonnegative_finite("unit_cost_low", self.unit_cost_low)
        _require_nonnegative_finite("unit_cost_high", self.unit_cost_high)

        if self.unit_cost_high < self.unit_cost_low:
            raise ValueError("unit_cost_high cannot be lower than unit_cost_low")
        if self.notes is not None and not self.notes.strip():
            raise ValueError("notes cannot be blank when provided")

    @property
    def extended_cost_low(self) -> float:
        """Return low extended line cost."""

        return self.quantity * self.unit_cost_low

    @property
    def extended_cost_high(self) -> float:
        """Return high extended line cost."""

        return self.quantity * self.unit_cost_high

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready line item."""

        return {
            "item_id": self.item_id,
            "label": self.label,
            "category": self.category.value,
            "quantity": self.quantity,
            "unit": self.unit,
            "unit_cost_low": self.unit_cost_low,
            "unit_cost_high": self.unit_cost_high,
            "currency": self.currency,
            "required": self.required,
            "field_replaceable": self.field_replaceable,
            "local_substitution_allowed": self.local_substitution_allowed,
            "extended_cost_low": self.extended_cost_low,
            "extended_cost_high": self.extended_cost_high,
            "notes": self.notes,
        }


@dataclass(frozen=True, slots=True)
class BOMEstimate:
    """Totaled BOM estimate for one deployment tier."""

    tier: DeploymentTier
    items: tuple[BOMItem, ...]
    currency: str
    assumptions: tuple[str, ...]
    non_claims: tuple[str, ...] = (
        "costs are planning estimates only",
        "not a procurement quote",
        "not a vendor recommendation",
        "not a complete engineering BOM",
        "not a public-health or safety certification",
        "local taxes, shipping, duties, labor, permits, spares, and testing may change cost",
    )
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.items:
            raise ValueError("at least one BOM item is required")
        if not self.currency.strip():
            raise ValueError("currency is required")
        if not self.assumptions:
            raise ValueError("at least one assumption is required")
        if not self.non_claims:
            raise ValueError("at least one non-claim is required")
        if any(not assumption.strip() for assumption in self.assumptions):
            raise ValueError("assumptions cannot contain blank values")
        if any(not claim.strip() for claim in self.non_claims):
            raise ValueError("non_claims cannot contain blank values")

        item_ids = [item.item_id for item in self.items]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("BOM item_id values must be unique")

        item_currencies = {item.currency for item in self.items}
        if item_currencies != {self.currency}:
            raise ValueError("all BOM items must use the estimate currency")

        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def total_cost_low(self) -> float:
        """Return low total estimate for all items."""

        return sum(item.extended_cost_low for item in self.items)

    @property
    def total_cost_high(self) -> float:
        """Return high total estimate for all items."""

        return sum(item.extended_cost_high for item in self.items)

    @property
    def required_cost_low(self) -> float:
        """Return low total estimate for required items only."""

        return sum(item.extended_cost_low for item in self.items if item.required)

    @property
    def required_cost_high(self) -> float:
        """Return high total estimate for required items only."""

        return sum(item.extended_cost_high for item in self.items if item.required)

    @property
    def optional_cost_low(self) -> float:
        """Return low total estimate for optional items only."""

        return sum(item.extended_cost_low for item in self.items if not item.required)

    @property
    def optional_cost_high(self) -> float:
        """Return high total estimate for optional items only."""

        return sum(item.extended_cost_high for item in self.items if not item.required)

    @property
    def required_item_ids(self) -> tuple[str, ...]:
        """Return required item IDs."""

        return tuple(item.item_id for item in self.items if item.required)

    @property
    def optional_item_ids(self) -> tuple[str, ...]:
        """Return optional item IDs."""

        return tuple(item.item_id for item in self.items if not item.required)

    def category_totals(self) -> dict[str, dict[str, float]]:
        """Return low/high totals by category."""

        totals: dict[str, dict[str, float]] = {}
        for item in self.items:
            category = item.category.value
            if category not in totals:
                totals[category] = {"low": 0.0, "high": 0.0}
            totals[category]["low"] += item.extended_cost_low
            totals[category]["high"] += item.extended_cost_high
        return totals

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready estimate."""

        return {
            "tier": self.tier.value,
            "currency": self.currency,
            "total_cost_low": self.total_cost_low,
            "total_cost_high": self.total_cost_high,
            "required_cost_low": self.required_cost_low,
            "required_cost_high": self.required_cost_high,
            "optional_cost_low": self.optional_cost_low,
            "optional_cost_high": self.optional_cost_high,
            "required_item_ids": list(self.required_item_ids),
            "optional_item_ids": list(self.optional_item_ids),
            "category_totals": self.category_totals(),
            "assumptions": list(self.assumptions),
            "non_claims": list(self.non_claims),
            "items": [item.to_dict() for item in self.items],
            "metadata": dict(self.metadata),
        }


def estimate_bom(
    *,
    tier: DeploymentTier,
    items: tuple[BOMItem, ...],
    currency: str = "USD",
    assumptions: tuple[str, ...] = (
        "caller supplied all unit cost ranges",
        "prices must be refreshed locally before procurement",
        "qualified review is required before build or deployment",
    ),
    non_claims: tuple[str, ...] = (
        "costs are planning estimates only",
        "not a procurement quote",
        "not a vendor recommendation",
        "not a complete engineering BOM",
        "not a public-health or safety certification",
        "local taxes, shipping, duties, labor, permits, spares, and testing may change cost",
    ),
    metadata: Mapping[str, Any] | None = None,
) -> BOMEstimate:
    """Create a vendor-neutral BOM estimate from user-supplied line items."""

    return BOMEstimate(
        tier=tier,
        items=items,
        currency=currency,
        assumptions=assumptions,
        non_claims=non_claims,
        metadata=metadata or {},
    )


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
