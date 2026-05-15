from datetime import UTC, datetime

import pytest

from ix_vahdat.domain import (
    Coordinates,
    EvidenceQuality,
    Measurement,
    SensorStatus,
    SiteContext,
)


def test_coordinates_accept_valid_latitude_and_longitude() -> None:
    coordinates = Coordinates(latitude=35.6892, longitude=51.3890)

    assert coordinates.latitude == 35.6892
    assert coordinates.longitude == 51.3890


@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [
        (-91.0, 0.0),
        (91.0, 0.0),
        (0.0, -181.0),
        (0.0, 181.0),
    ],
)
def test_coordinates_reject_out_of_range_values(latitude: float, longitude: float) -> None:
    with pytest.raises(ValueError):
        Coordinates(latitude=latitude, longitude=longitude)


def test_measurement_requires_timezone_aware_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        Measurement(
            name="tank_level",
            value=0.72,
            unit="fraction",
            source_id="sensor-1",
            timestamp=datetime(2026, 5, 14, 12, 0, 0),
        )


def test_measurement_preserves_evidence_metadata() -> None:
    measurement = Measurement(
        name="conductivity",
        value=840.0,
        unit="uS/cm",
        source_id="conductivity-meter-1",
        timestamp=datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC),
        quality=EvidenceQuality.MEASURED,
        sensor_status=SensorStatus.OK,
        uncertainty=12.0,
        notes="bench-calibrated field reading",
    )

    assert measurement.name == "conductivity"
    assert measurement.quality is EvidenceQuality.MEASURED
    assert measurement.sensor_status is SensorStatus.OK
    assert measurement.uncertainty == 12.0


def test_measurement_rejects_negative_uncertainty() -> None:
    with pytest.raises(ValueError, match="uncertainty"):
        Measurement(
            name="flow",
            value=2.5,
            unit="L/min",
            source_id="flow-meter-1",
            timestamp=datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC),
            uncertainty=-0.1,
        )


def test_site_context_cleans_metadata_into_immutable_mapping() -> None:
    site = SiteContext(
        site_id="site-a",
        name="Field Node A",
        operator="local review team",
        tags=("clinic", "emergency-water"),
        metadata={"region_type": "drought-stressed"},
    )

    assert site.metadata["region_type"] == "drought-stressed"

    with pytest.raises(TypeError):
        site.metadata["region_type"] = "changed"  # type: ignore[index]


def test_site_context_rejects_blank_tag_values() -> None:
    with pytest.raises(ValueError, match="tags"):
        SiteContext(
            site_id="site-b",
            name="Field Node B",
            operator="local review team",
            tags=("valid", " "),
        )
