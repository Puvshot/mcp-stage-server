from __future__ import annotations

from pathlib import Path
from typing import Any

from mss.rules.convert_md_to_json import runner_convert_markdown_path_to_json_path
from mss.rules.schema import REQUIRED_RULES_KINDS, RulesKind


def convert_md_to_json(
    rules_kind: str | None = None,
    source_markdown_path: str | None = None,
    output_json_path: str | None = None,
) -> dict[str, Any]:
    """Convert markdown rules into JSON SSOT payloads.

    This tool is side-effecting because it writes JSON files. It is retry-safe
    for unchanged inputs because outputs are overwritten deterministically.
    """
    if rules_kind is None:
        return _convert_all_default_kinds()

    normalized_kind = _normalize_rules_kind(rules_kind)
    if normalized_kind is None:
        return _error_response(
            code="INVALID_RULES_KIND",
            message=f"Unsupported rules kind: {rules_kind}",
            file_path=None,
        )

    source_path = _resolve_source_markdown_path(normalized_kind, source_markdown_path)
    output_path = _resolve_output_json_path(normalized_kind, output_json_path)

    conversion_result = runner_convert_markdown_path_to_json_path(
        rules_kind=normalized_kind,
        source_markdown_path=source_path,
        output_json_path=output_path,
    )
    if conversion_result.get("status") == "error":
        return conversion_result
    return conversion_result


def _convert_all_default_kinds() -> dict[str, Any]:
    conversion_outputs: list[dict[str, Any]] = []
    for required_kind in REQUIRED_RULES_KINDS:
        source_path = _resolve_source_markdown_path(required_kind, source_markdown_path=None)
        output_path = _resolve_output_json_path(required_kind, output_json_path=None)

        conversion_result = runner_convert_markdown_path_to_json_path(
            rules_kind=required_kind,
            source_markdown_path=source_path,
            output_json_path=output_path,
        )
        if conversion_result.get("status") == "error":
            return conversion_result

        conversion_outputs.append(
            {
                "rules_kind": required_kind,
                "source_markdown_path": conversion_result["source_markdown_path"],
                "output_json_path": conversion_result["output_json_path"],
                "conversion_warnings": conversion_result.get("conversion_warnings", []),
            }
        )

    return {
        "status": "ok",
        "converted": conversion_outputs,
    }


def _normalize_rules_kind(rules_kind: str) -> RulesKind | None:
    if not isinstance(rules_kind, str):
        return None
    normalized_kind = rules_kind.strip()
    if normalized_kind in REQUIRED_RULES_KINDS:
        return normalized_kind
    return None


def _resolve_source_markdown_path(rules_kind: RulesKind, source_markdown_path: str | None) -> Path:
    if isinstance(source_markdown_path, str) and source_markdown_path.strip():
        return Path(source_markdown_path).resolve()
    project_root = Path(__file__).resolve().parents[2]
    return project_root / "Rules" / f"_rules_{rules_kind}.md"


def _resolve_output_json_path(rules_kind: RulesKind, output_json_path: str | None) -> Path:
    if isinstance(output_json_path, str) and output_json_path.strip():
        return Path(output_json_path).resolve()
    project_root = Path(__file__).resolve().parents[2]
    return project_root / "data" / "rules_json" / f"{rules_kind}.json"


def _error_response(code: str, message: str, file_path: str | None) -> dict[str, Any]:
    return {
        "status": "error",
        "code": code,
        "errors": [
            {
                "code": code,
                "message": message,
                "file": file_path,
                "severity": "error",
            }
        ],
    }