from pathlib import Path

import mss.parsers.markdown as parser_module


def test_parse_package_markdown_happy_path_extracts_stages_and_test_command() -> None:
    markdown_text = """
# PACKAGE_1: infrastructure_foundation

## Package Goal
Create infrastructure foundation.

## Files to modify
- CREATE: mcp-stage-server/pyproject.toml
- EDIT: mcp-stage-server/src/parsers/markdown.py

### Stage 1: Bootstrap
1. READ: PLAN.md
2. CREATE: mcp-stage-server/pyproject.toml
3. TEST: python -m pytest -q mcp-stage-server/tests/test_parser.py

## Testing & Verification
- `python -m pytest -q mcp-stage-server/tests/test_parser.py`
""".strip()

    parsed_package = parser_module.parse_package_markdown(markdown_text, package_id="PACKAGE_1")

    assert parsed_package["package_id"] == "PACKAGE_1"
    assert parsed_package["goal"] == "Create infrastructure foundation."
    assert len(parsed_package["files_to_modify"]) == 2
    assert len(parsed_package["stages"]) == 1
    assert parsed_package["stages"][0]["stage_id"] == "PACKAGE_1_STAGE_1"
    assert parsed_package["stages"][0]["test_command"] == "python -m pytest -q mcp-stage-server/tests/test_parser.py"
    assert parsed_package["verification_commands"] == ["python -m pytest -q mcp-stage-server/tests/test_parser.py"]


def test_parse_package_markdown_tolerant_mode_returns_warnings_for_missing_sections() -> None:
    markdown_text = """
# PACKAGE_1: broken

### Stage 1: Minimal
1. WRITE: unknown action should become warning
2. TEST: python -m pytest -q
""".strip()

    parsed_package = parser_module.parse_package_markdown(markdown_text, package_id="PACKAGE_1")

    assert parsed_package["goal"] == "UNKNOWN: section not found"
    assert parsed_package["files_to_modify"] == []
    assert len(parsed_package["stages"]) == 1
    assert parsed_package["stages"][0]["steps"][0]["action"] == "UNKNOWN"
    assert any("missing section: ## Package Goal" in warning for warning in parsed_package["warnings"])
    assert any("missing section: ## Files to modify" in warning for warning in parsed_package["warnings"])
    assert any("unknown step action: WRITE" in warning for warning in parsed_package["warnings"])


def test_parse_package_markdown_never_raises_for_invalid_input_type() -> None:
    parsed_package = parser_module.parse_package_markdown(markdown_text=None, package_id="PACKAGE_1")  # type: ignore[arg-type]

    assert parsed_package["package_id"] == "PACKAGE_1"
    assert parsed_package["stages"] == []
    assert any("input is not a string" in warning for warning in parsed_package["warnings"])
