from __future__ import annotations

import pytest

import mss.rules.convert_md_to_json as convert_module


def test_convert_markdown_text_to_payload_is_deterministic() -> None:
    markdown_text = """
# Package Generation Rules
- MUST READ project files before EDIT
- MUST NOT DELETE unrelated files
""".strip()

    first_conversion = convert_module.convert_markdown_text_to_payload(
        rules_kind="package_generation",
        markdown_text=markdown_text,
        source_label="rules.md",
    )
    second_conversion = convert_module.convert_markdown_text_to_payload(
        rules_kind="package_generation",
        markdown_text=markdown_text,
        source_label="rules.md",
    )

    assert first_conversion["status"] == "ok"
    assert second_conversion["status"] == "ok"
    assert first_conversion["payload"] == second_conversion["payload"]
    assert first_conversion["conversion_warnings"] == second_conversion["conversion_warnings"]


def test_convert_markdown_text_to_payload_returns_error_for_unknown_in_required_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        convert_module,
        "_extract_templates",
        lambda _rules_kind, _lines, _warnings: {"default": "UNKNOWN: missing template"},
    )

    conversion_payload = convert_module.convert_markdown_text_to_payload(
        rules_kind="package_generation",
        markdown_text="# Heading\n- MUST READ files",
        source_label="rules.md",
    )

    assert conversion_payload["status"] == "error"
    assert conversion_payload["code"] == "UNKNOWN_IN_REQUIRED_FIELD"
    error_entry = conversion_payload["errors"][0]
    assert "$.templates.default" in error_entry["paths"]


def test_convert_markdown_text_to_payload_returns_error_for_required_field_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(convert_module, "_extract_action_directives", lambda _lines: "INVALID")

    conversion_payload = convert_module.convert_markdown_text_to_payload(
        rules_kind="package_generation",
        markdown_text="# Heading\n- MUST READ files",
        source_label="rules.md",
    )

    assert conversion_payload["status"] == "error"
    assert conversion_payload["code"] == "INVALID_CONVERTED_PAYLOAD"
    validation_issues = conversion_payload["errors"][0]["validation_issues"]
    assert any(issue["path"] == "$.action_directives" for issue in validation_issues)