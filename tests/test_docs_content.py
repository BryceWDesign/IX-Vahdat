from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT_DIR / "docs"


def _read_doc(name: str) -> str:
    return (DOCS_DIR / name).read_text(encoding="utf-8")


def _read_root_doc(name: str) -> str:
    return (ROOT_DIR / name).read_text(encoding="utf-8")


def test_build_tiers_doc_preserves_non_authorizing_boundary() -> None:
    text = _read_doc("BUILD_TIERS_AND_BOM.md").lower()

    assert "not a procurement quote" in text
    assert "not a vendor recommendation" in text
    assert "not a certified drinking-water plant" in text
    assert "do not publish a false universal cost" in text
    assert "a bom is not a system" in text


def test_build_tiers_doc_covers_all_required_deployment_tiers() -> None:
    text = _read_doc("BUILD_TIERS_AND_BOM.md")

    assert "Tier 1: Demo Node" in text
    assert "Tier 2: School or Clinic Node" in text
    assert "Tier 3: Community Node" in text
    assert "Tier 4: Advanced Hub" in text


def test_assembly_doc_preserves_hold_points_and_human_review() -> None:
    text = _read_doc("ASSEMBLY_AND_COMMISSIONING.md").lower()

    assert "hold point" in text
    assert "human review" in text
    assert "no water should be released" in text
    assert "software must not authorize recharge" in text
    assert "none of these outputs is release authorization" in text


def test_assembly_doc_contains_final_required_statement() -> None:
    text = _read_doc("ASSEMBLY_AND_COMMISSIONING.md")

    assert "This commissioning record is decision support only." in text
    assert "does not certify water" in text
    assert "does not certify water\nas potable" in text
    assert "control physical systems\nautonomously" in text


def test_humanitarian_scope_preserves_country_neutral_framing() -> None:
    text = _read_doc("HUMANITARIAN_SCOPE.md").lower()

    assert "country-neutral framing" in text
    assert "drought-stressed communities" in text
    assert "software may organize evidence. qualified humans must decide." in text
    assert "should not prescribe policy to any specific nation" in text


def test_safety_model_preserves_fail_closed_rules() -> None:
    text = _read_doc("SAFETY_MODEL.md").lower()

    assert "missing evidence should hold." in text
    assert "critical evidence should block." in text
    assert "synthetic data is not field data." in text
    assert "ix-vahdat should prefer false holds over false approvals." in text


def test_contributing_doc_requires_review_and_no_fake_data() -> None:
    text = _read_root_doc("CONTRIBUTING.md").lower()

    assert "do not weaken safety gates." in text
    assert "do not add fake field data." in text
    assert "do not remove human review requirements." in text
    assert "synthetic examples must be clearly labeled." in text


def test_security_doc_lists_high_priority_safety_issues() -> None:
    text = _read_root_doc("SECURITY.md").lower()

    assert "unsafe water-use claims" in text
    assert "missing human-review gates" in text
    assert "synthetic examples can be mistaken for field data" in text
    assert "do not publish exploit details" in text


def test_code_of_conduct_rejects_unsafe_claims_and_coercive_use() -> None:
    text = _read_root_doc("CODE_OF_CONDUCT.md").lower()

    assert "fake data or fake field measurements" in text
    assert "unsafe water-safety claims" in text
    assert "weapon, surveillance, or coercive use" in text
    assert "humanitarian neutrality" in text


def test_docs_do_not_claim_certification_or_field_authorization() -> None:
    forbidden_phrases = (
        "certified potable",
        "approved for public distribution",
        "field deployment authorized",
        "safe to drink",
        "guaranteed yield",
    )

    paths = list(DOCS_DIR.glob("*.md")) + [
        ROOT_DIR / "CONTRIBUTING.md",
        ROOT_DIR / "SECURITY.md",
        ROOT_DIR / "CODE_OF_CONDUCT.md",
    ]

    for path in sorted(paths):
        text = path.read_text(encoding="utf-8").lower()
        for phrase in forbidden_phrases:
            assert phrase not in text
