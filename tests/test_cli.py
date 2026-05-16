import json

from ix_vahdat.cli import build_demo_payload, main


def test_build_demo_payload_is_marked_synthetic_and_review_only() -> None:
    payload = build_demo_payload()

    assert payload["project"] == "IX-Vahdat"
    assert payload["mode"] == "synthetic_demo"
    assert payload["site"]["metadata"]["synthetic_demo"] is True
    assert payload["site"]["metadata"]["field_deployment"] is False
    assert "not a potable-water certification" in payload["non_claims"]
    assert "not a field-deployment authorization" in payload["non_claims"]
    assert payload["summary"]["site_readiness_class"] in {
        "limited_field_review",
        "emergency_support_review",
    }
    assert len(payload["receipts"]) == 2


def test_demo_payload_contains_no_field_authorization_claim() -> None:
    payload_text = json.dumps(build_demo_payload(), sort_keys=True).lower()

    assert "field_deployment_authorized" in payload_text
    assert "certified drinking-water system" in payload_text
    assert "potable-water certification" in payload_text
    assert "field-deployment authorization" in payload_text
    assert "safe to drink" not in payload_text
    assert "certified potable" not in payload_text


def test_main_demo_prints_compact_json(capsys) -> None:
    exit_code = main(["demo"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["project"] == "IX-Vahdat"
    assert payload["mode"] == "synthetic_demo"


def test_main_demo_pretty_prints_json(capsys) -> None:
    exit_code = main(["demo", "--pretty"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert "\n  " in captured.out
    assert payload["summary"]["human_review_status"] == "approved_for_limited_use"


def test_main_without_command_defaults_to_demo(capsys) -> None:
    exit_code = main([])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["project"] == "IX-Vahdat"
    assert payload["mode"] == "synthetic_demo"
