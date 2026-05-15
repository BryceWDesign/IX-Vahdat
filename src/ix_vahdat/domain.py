"""Core domain models for IX-Vahdat.

These models intentionally describe observations, evidence, and review
state. They do not operate hardware and they do not certify water safety.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping


class RiskLevel(str, Enum):
    """General risk severity used by evidence gates and review records."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class SensorStatus(str, Enum):
    """Operational state for a sensor or field measurement source."""

    OK = "ok"
    DEGRADED = "degraded"
    STALE = "stale"
    FAILED = "failed"
    UNVERIFIED = "unverified"


class EvidenceQuality(str, Enum):
    """Quality of evidence available for a decision-support output."""

    MEASURED = "measured"
    ESTIMATED = "estimated"
    MISSING = "missing"
    CONFLICTING = "conflicting"


class DecisionStatus(str, Enum):
    """Decision-support state before any human-reviewed field action."""

    ALLOW_REVIEW = "allow_review"
    BLOCK = "block"
    HOLD_FOR_TESTING = "hold_for_testing"


@dataclass(frozen=True, slots=True)
class Coordinates:
    """Optional latitude/longitude metadata for a monitored site."""

    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        if not isfinite(self.latitude):
            raise ValueError("latitude must be finite")
        if not isfinite(self.longitude):
            raise ValueError("longitude must be finite")
        if self.latitude < -90.0 or self.latitude > 90.0:
            raise ValueError("latitude must be between -90 and 90 degrees")
        if self.longitude < -180.0 or self.longitude > 180.0:
            raise ValueError("longitude must be between -180 and 180 degrees")


@dataclass(frozen=True, slots=True)
class Measurement:
    """Single field measurement with source and quality metadata."""

    name: str
    value: float
    unit: str
    source_id: str
    timestamp: datetime
    quality: EvidenceQuality = EvidenceQuality.MEASURED
    sensor_status: SensorStatus = SensorStatus.OK
    uncertainty: float | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("measurement name is required")
        if not isfinite(self.value):
            raise ValueError("measurement value must be finite")
        if not self.unit.strip():
            raise ValueError("measurement unit is required")
        if not self.source_id.strip():
            raise ValueError("measurement source_id is required")
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("measurement timestamp must be timezone-aware")
        if self.uncertainty is not None:
            if not isfinite(self.uncertainty):
                raise ValueError("measurement uncertainty must be finite")
            if self.uncertainty < 0:
                raise ValueError("measurement uncertainty cannot be negative")
        if self.notes is not None and not self.notes.strip():
            raise ValueError("measurement notes cannot be blank when provided")


@dataclass(frozen=True, slots=True)
class SiteContext:
    """Context for a water-resilience node or monitored site."""

    site_id: str
    name: str
    operator: str
    coordinates: Coordinates | None = None
    tags: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.site_id.strip():
            raise ValueError("site_id is required")
        if not self.name.strip():
            raise ValueError("site name is required")
        if not self.operator.strip():
            raise ValueError("operator is required")

        cleaned_tags = tuple(tag.strip() for tag in self.tags if tag.strip())
        if len(cleaned_tags) != len(self.tags):
            raise ValueError("site tags cannot contain blank values")
        object.__setattr__(self, "tags", cleaned_tags)

        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
