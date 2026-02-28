from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from mss.rules.schema import (
    REQUIRED_RULES_KINDS,
    RulesConversionCoreResult,
    RulesConversionRunnerResult,
    RulesKind,
    validate_rules_payload,
)


_ACTION_NAMES: tuple[str, ...] = ("READ", "CREATE", "EDIT", "DELETE", "MOVE", "RENAME", "TEST", "GIT")


def runner_convert_markdown_path_to_payload(
    rules_kind: RulesKind,
    source_markdown_path: Path,
) -> RulesConversionRunnerResult:
    """Runner: convert markdown file from filesystem into schema-compatible payload.

    This function performs filesystem reads and is idempotent for unchanged inputs.
    """
    resolved_source_path = source_markdown_path.resolve()
    if not resolved_source_path.exists():
        return _error_response(
            code="SOURCE_MARKDOWN_NOT_FOUND",
            message=f"Source markdown file does not exist: {resolved_source_path}",
            file_path=str(resolved_source_path),
        )

    markdown_text = resolved_source_path.read_text(encoding="utf-8")
    conversion_payload = core_convert_markdown_text_to_payload(
        rules_kind=rules_kind,
        markdown_text=markdown_text,
        source_label=str(resolved_source_path),
    )
    if conversion_payload.get("status") == "error":
        return conversion_payload

    return {
        "status": "ok",
        "rules_kind": rules_kind,
        "source_markdown_path": str(resolved_source_path),
        "payload": conversion_payload["payload"],
        "conversion_warnings": conversion_payload["conversion_warnings"],
    }


def runner_convert_markdown_path_to_json_path(
    rules_kind: RulesKind,
    source_markdown_path: Path,
    output_json_path: Path,
) -> dict[str, Any]:
    """Runner: convert markdown file and persist JSON payload to filesystem."""
    conversion_result = runner_convert_markdown_path_to_payload(
        rules_kind=rules_kind,
        source_markdown_path=source_markdown_path,
    )
    if conversion_result.get("status") == "error":
        return conversion_result

    runner_write_payload_json(conversion_result["payload"], output_json_path)
    return {
        "status": "ok",
        "rules_kind": conversion_result["rules_kind"],
        "source_markdown_path": conversion_result["source_markdown_path"],
        "output_json_path": str(output_json_path.resolve()),
        "conversion_warnings": conversion_result.get("conversion_warnings", []),
    }


def core_convert_markdown_text_to_payload(
    rules_kind: RulesKind,
    markdown_text: str,
    source_label: str,
) -> RulesConversionCoreResult:
    """Core: convert markdown text into schema-compatible JSON payload.

    This function is pure: it does not perform filesystem reads/writes.
    """
    if rules_kind not in REQUIRED_RULES_KINDS:
        return _error_response(
            code="INVALID_RULES_KIND",
            message=f"Unsupported rules kind: {rules_kind}",
            file_path=source_label,
        )
    if not isinstance(markdown_text, str):
        return _error_response(
            code="INVALID_MARKDOWN_TYPE",
            message="markdown_text must be a string",
            file_path=source_label,
        )

    normalized_lines = _normalize_lines(markdown_text)
    conversion_warnings: list[str] = []
    always_must, always_must_not = _extract_always_rules(normalized_lines, conversion_warnings)
    action_directives = _extract_action_directives(normalized_lines)
    templates = _extract_templates(rules_kind, normalized_lines, conversion_warnings)

    payload: dict[str, Any] = {
        "version": "1.0",
        "action_directives": action_directives,
        "always": {
            "must": always_must,
            "must_not": always_must_not,
        },
        "forbidden_imports": [],
        "templates": templates,
        "metadata": {
            "source_markdown": source_label,
            "derivation_mode": "deterministic_regex_v1",
            "optional_non_derivable": {
                "domain_specific_semantics": (
                    "UNKNOWN: conversion preserves textual constraints only and does not infer domain semantics"
                )
            },
        },
        "conversion_warnings": conversion_warnings,
    }

    validation_issues = validate_rules_payload(payload)
    if validation_issues:
        return {
            "status": "error",
            "code": "INVALID_CONVERTED_PAYLOAD",
            "errors": [
                {
                    "code": "INVALID_CONVERTED_PAYLOAD",
                    "message": "Converted payload does not satisfy required schema fields.",
                    "file": source_label,
                    "severity": "error",
                    "validation_issues": [
                        {
                            "code": issue.code,
                            "message": issue.message,
                            "path": issue.path,
                        }
                        for issue in validation_issues
                    ],
                }
            ],
        }

    unknown_required_paths = _find_unknown_required_paths(payload)
    if unknown_required_paths:
        return {
            "status": "error",
            "code": "UNKNOWN_IN_REQUIRED_FIELD",
            "errors": [
                {
                    "code": "UNKNOWN_IN_REQUIRED_FIELD",
                    "message": "UNKNOWN value detected in required field.",
                    "file": source_label,
                    "severity": "error",
                    "paths": unknown_required_paths,
                }
            ],
        }

    return {
        "status": "ok",
        "payload": payload,
        "conversion_warnings": conversion_warnings,
    }


def convert_markdown_path_to_payload(rules_kind: RulesKind, source_markdown_path: Path) -> RulesConversionRunnerResult:
    """Backward-compatible wrapper for runner conversion from markdown path."""
    return runner_convert_markdown_path_to_payload(rules_kind, source_markdown_path)


def convert_markdown_text_to_payload(rules_kind: RulesKind, markdown_text: str, source_label: str) -> RulesConversionCoreResult:
    """Backward-compatible wrapper for core conversion from markdown text."""
    return core_convert_markdown_text_to_payload(rules_kind, markdown_text, source_label)


def runner_write_payload_json(payload: dict[str, Any], output_path: Path) -> None:
    """Runner: write converted payload as deterministic JSON file.

    This function is side-effecting and idempotent for unchanged payload/output path.
    """
    resolved_output_path = output_path.resolve()
    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_payload_json(payload: dict[str, Any], output_path: Path) -> None:
    """Backward-compatible wrapper for runner JSON write operation."""
    runner_write_payload_json(payload, output_path)


def _normalize_lines(markdown_text: str) -> list[str]:
    normalized_lines: list[str] = []
    for raw_line in markdown_text.splitlines():
        stripped_line = raw_line.strip()
        if not stripped_line:
            continue
        normalized_lines.append(stripped_line)
    return normalized_lines


def _extract_always_rules(lines: list[str], conversion_warnings: list[str]) -> tuple[list[str], list[str]]:
    must_lines: list[str] = []
    must_not_lines: list[str] = []

    for line in lines:
        normalized_line = _normalize_constraint_line(line)
        if _is_negative_constraint(normalized_line):
            must_not_lines.append(normalized_line)
            continue
        if _is_positive_constraint(normalized_line):
            must_lines.append(normalized_line)

    deduped_must = _dedupe_preserve_order(must_lines)
    deduped_must_not = _dedupe_preserve_order(must_not_lines)

    if not deduped_must:
        deduped_must = ["Preserve deterministic behavior from the source markdown rules."]
        conversion_warnings.append("No explicit MUST constraints detected; inserted deterministic default MUST directive.")
    if not deduped_must_not:
        deduped_must_not = ["Do not deviate from explicit prohibitions in the source markdown rules."]
        conversion_warnings.append(
            "No explicit MUST NOT constraints detected; inserted deterministic default MUST NOT directive."
        )

    return deduped_must, deduped_must_not


def _extract_action_directives(lines: list[str]) -> dict[str, dict[str, list[str]]]:
    directives: dict[str, dict[str, list[str]]] = {}

    for line in lines:
        normalized_line = _normalize_constraint_line(line)
        matched_actions = [action_name for action_name in _ACTION_NAMES if re.search(rf"\b{action_name}\b", normalized_line)]
        if not matched_actions:
            continue

        is_negative = _is_negative_constraint(normalized_line)
        for action_name in matched_actions:
            if action_name not in directives:
                directives[action_name] = {"must": [], "must_not": []}
            target_key = "must_not" if is_negative else "must"
            directives[action_name][target_key].append(normalized_line)

    for action_name, action_payload in directives.items():
        action_payload["must"] = _dedupe_preserve_order(action_payload["must"])
        action_payload["must_not"] = _dedupe_preserve_order(action_payload["must_not"])

    return directives


def _extract_templates(rules_kind: RulesKind, lines: list[str], conversion_warnings: list[str]) -> dict[str, str]:
    heading_lines = [line for line in lines if line.startswith("#")]
    if heading_lines:
        heading_text = " | ".join(heading_lines[:6])
        return {"default": f"{rules_kind}: {heading_text}"}

    conversion_warnings.append("No markdown headings detected; using deterministic fallback template.")
    return {"default": f"{rules_kind}: deterministic conversion template"}


def _normalize_constraint_line(line: str) -> str:
    compacted_line = re.sub(r"\s+", " ", line).strip()
    return compacted_line.strip("`")


def _is_positive_constraint(line: str) -> bool:
    upper_line = line.upper()
    return (
        "MUST" in upper_line
        or "REQUIRED" in upper_line
        or "RULE:" in upper_line
        or upper_line.startswith("ON_PASS")
        or upper_line.startswith("VALIDATION_LOGIC")
    )


def _is_negative_constraint(line: str) -> bool:
    upper_line = line.upper()
    return (
        "MUST NOT" in upper_line
        or "DO_NOT" in upper_line
        or "BLOCK(" in upper_line
        or "HALT" in upper_line
        or "ON_FAIL" in upper_line
        or "FORBIDDEN" in upper_line
    )


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    deduped_values: list[str] = []
    seen_values: set[str] = set()
    for value in values:
        if value in seen_values:
            continue
        seen_values.add(value)
        deduped_values.append(value)
    return deduped_values


def _find_unknown_required_paths(payload: dict[str, Any]) -> list[str]:
    unknown_paths: list[str] = []

    def _scan(node: Any, path: str) -> None:
        if isinstance(node, str) and node.startswith("UNKNOWN:"):
            unknown_paths.append(path)
            return
        if isinstance(node, list):
            for index, value in enumerate(node):
                _scan(value, f"{path}[{index}]")
            return
        if isinstance(node, dict):
            for key, value in node.items():
                _scan(value, f"{path}.{key}")

    required_projection = {
        "version": payload.get("version"),
        "action_directives": payload.get("action_directives"),
        "always": payload.get("always"),
        "forbidden_imports": payload.get("forbidden_imports"),
        "templates": payload.get("templates"),
    }
    _scan(required_projection, "$")
    return _dedupe_preserve_order(unknown_paths)


def _error_response(code: str, message: str, file_path: str) -> dict[str, Any]:
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
