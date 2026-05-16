import json
from pathlib import Path


EXAMPLE_CONFIG_DIR = Path(__file__).resolve().parents[1] / "examples" / "site_configs"


def _load_config(name: str) -> dict:
    with (EXAMPLE_CONFIG_DIR / name).open(encoding="utf-8") as file:
        return json.load(file)


def test_reviewable_example_config_is_synthetic_and_non_authorizing() -> None:
    config = _load_config("synthetic_reviewable_node.json")

    assert config["project"] == "IX-Vahdat"
    assert config["schema_version"] == "0.1.0"
    assert config["synthetic_example"] is True
    assert config["field_deployment_authorized"] is False
    assert config["site"]["metadata"]["real_world_site"] is False
    assert config["site"]["metadata"]["country_specific_policy"] is False
    assert "not a potable-water certification" in config["non_claims"]
    assert "not an autonomous physical-control instruction" in config["non_claims"]


def test_hold_for_testing_example_config_is_synthetic_and_non_authorizing() -> None:
    config = _load_config("synthetic_hold_for_testing_node.json")

    assert config["project"] == "IX-Vahdat"
    assert config["schema_version"] == "0.1.0"
    assert config["synthetic_example"] is True
    assert config["field_deployment_authorized"] is False
    assert config["site"]["metadata"]["real_world_site"] is False
    assert config["human_review"]["reviewer_id"] is None
    assert config["human_review"]["decision"] is None
    assert "not a permit substitute" in config["non_claims"]


def test_example_configs_do_not_contain_field_approval_language() -> None:
    for path in sorted(EXAMPLE_CONFIG_DIR.glob("*.json")):
        text = path.read_text(encoding="utf-8").lower()

        assert "safe to drink" not in text
        assert "certified potable" not in text
        assert "approved for public distribution" not in text
        assert "deployment authorized" not in text
        assert "autonomous control" not in text


def test_example_configs_contain_required_top_level_sections() -> None:
    required_sections = {
        "schema_version",
        "project",
        "config_id",
        "synthetic_example",
        "field_deployment_authorized",
        "non_claims",
        "site",
        "water_quality",
        "treatment_system",
        "energy",
        "power",
        "reserve",
        "atmospheric_water",
        "maintenance",
        "infrastructure",
        "human_review",
    }

    for path in sorted(EXAMPLE_CONFIG_DIR.glob("*.json")):
        config = _load_config(path.name)

        assert required_sections.issubset(config.keys())


def test_power_load_examples_define_safe_hold_loads() -> None:
    for path in sorted(EXAMPLE_CONFIG_DIR.glob("*.json")):
        config = _load_config(path.name)
        safe_hold_loads = [
            load
            for load in config["power"]["loads"]
            if load["priority"] == "critical" and load["required_for_safe_hold"]
        ]

        assert len(safe_hold_loads) >= 2
        assert any(load["name"] == "evidence_logger" for load in safe_hold_loads)
        assert any(load["name"] == "water_quality_sensors" for load in safe_hold_loads)


def test_atmospheric_examples_never_allow_potable_claim_by_default() -> None:
    for path in sorted(EXAMPLE_CONFIG_DIR.glob("*.json")):
        config = _load_config(path.name)

        assert (
            config["atmospheric_water"]["constraints"]["potable_claim_allowed_by_local_review"]
            is False
        )
