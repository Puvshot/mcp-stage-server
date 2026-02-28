from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from mss.rules.loader import RulesLoadException, load_rules_payload
from mss.storage.plan_cache import runner_load_plan_cache
from mss.tools import rules as rules_tool


DEFAULT_PROMPT_CHAR_LIMIT = 4000


def directive_bundle(plan_dir: str, stage_id: str, char_limit: int = DEFAULT_PROMPT_CHAR_LIMIT) -> dict[str, Any]:
    """Return executor-facing directive bundle with deterministic prompt trimming.

    This read-only tool is idempotent.
    """
    resolved_plan_dir = Path(plan_dir).resolve()
    if not isinstance(stage_id, str) or not stage_id.strip():
        return _error_response("INVALID_STAGE_ID", "stage_id must be a non-empty string")
    if not isinstance(char_limit, int) or char_limit <= 0:
        return _error_response("INVALID_CHAR_LIMIT", "char_limit must be a positive integer")

    plan_cache = runner_load_plan_cache(resolved_plan_dir)
    if plan_cache is None:
        return _error_response("PLAN_NOT_INITIALIZED", "Plan cache is missing")

    package_snapshot, stage_snapshot = _find_stage_context(plan_cache, stage_id)
    if package_snapshot is None or stage_snapshot is None:
        return _error_response("STAGE_NOT_FOUND", f"Stage not found: {stage_id}")

    directive_pack_result = rules_tool.directive_pack(str(resolved_plan_dir), stage_id)
    if directive_pack_result.get("status") == "error":
        return directive_pack_result

    directive_pack_payload = directive_pack_result.get("directive_pack", {})
    must_directives = [str(entry) for entry in directive_pack_payload.get("must", []) if str(entry)]
    must_not_directives = [str(entry) for entry in directive_pack_payload.get("must_not", []) if str(entry)]
    template_value = directive_pack_payload.get("template")

    try:
        package_generation_rules = load_rules_payload("package_generation")
    except RulesLoadException as rules_error:
        return _rules_load_error_response(rules_error)

    ruleset_hash = _ruleset_hash(package_generation_rules)
    dominant_actions = [str(action) for action in stage_snapshot.get("dominant_actions", []) if str(action)]
    used_rule_identifiers = _collect_used_rule_identifiers(package_generation_rules, dominant_actions)

    prompt_build_result = _build_prompt_text(
        package_id=str(package_snapshot.get("package_id", "PACKAGE_UNKNOWN")),
        stage_id=stage_id,
        files_in_scope=[str(path) for path in stage_snapshot.get("files_in_scope", []) if str(path)],
        prohibitions=must_not_directives,
        stop_conditions=[str(item) for item in plan_cache.get("stop_conditions", []) if str(item)],
        test_command=stage_snapshot.get("test_command"),
        required_directives=must_directives,
        template_value=template_value,
        char_limit=char_limit,
    )
    if prompt_build_result.get("status") == "error":
        return prompt_build_result

    return {
        "directive_bundle": {
            "package_id": str(package_snapshot.get("package_id", "PACKAGE_UNKNOWN")),
            "stage_id": stage_id,
            "prompt_text": prompt_build_result["prompt_text"],
            "RULESET_HASH": ruleset_hash,
            "used_rule_identifiers": used_rule_identifiers,
            "char_limit": char_limit,
            "prompt_characters": len(prompt_build_result["prompt_text"]),
            "trimmed": bool(prompt_build_result["trimmed"]),
        }
    }


def _find_stage_context(plan_cache: dict[str, Any], stage_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    for package_snapshot in plan_cache.get("packages", []):
        for stage_snapshot in package_snapshot.get("stages", []):
            if stage_snapshot.get("stage_id") == stage_id:
                return package_snapshot, stage_snapshot
    return None, None


def _build_prompt_text(
    package_id: str,
    stage_id: str,
    files_in_scope: list[str],
    prohibitions: list[str],
    stop_conditions: list[str],
    test_command: Any,
    required_directives: list[str],
    template_value: Any,
    char_limit: int,
) -> dict[str, Any]:
    non_trimmable_sections = [
        "EXECUTION DIRECTIVE BUNDLE",
        f"PACKAGE_ID: {package_id}",
        f"STAGE_ID: {stage_id}",
        "",
        "SCOPE (NON-TRIMMABLE):",
    ]
    if files_in_scope:
        non_trimmable_sections.extend([f"- {file_path}" for file_path in files_in_scope])
    else:
        non_trimmable_sections.append("- UNKNOWN: files_in_scope is empty")

    non_trimmable_sections.append("")
    non_trimmable_sections.append("PROHIBITIONS (NON-TRIMMABLE):")
    if prohibitions:
        non_trimmable_sections.extend([f"- {prohibition}" for prohibition in prohibitions])
    else:
        non_trimmable_sections.append("- NONE")

    non_trimmable_sections.append("")
    non_trimmable_sections.append("STOP CONDITIONS (NON-TRIMMABLE):")
    if stop_conditions:
        non_trimmable_sections.extend([f"- {stop_condition}" for stop_condition in stop_conditions])
    else:
        non_trimmable_sections.append("- NONE")

    non_trimmable_sections.append("")
    non_trimmable_sections.append("TEST COMMAND (NON-TRIMMABLE):")
    if isinstance(test_command, str) and test_command.strip():
        non_trimmable_sections.append(f"- {test_command.strip()}")
    else:
        non_trimmable_sections.append("- (No specific test identified. Re-run baseline)")

    non_trimmable_text = "\n".join(non_trimmable_sections)
    if len(non_trimmable_text) > char_limit:
        return _error_response(
            "CHAR_LIMIT_TOO_LOW",
            "char_limit is too low to preserve required non-trimmable sections",
            extra={"required_minimum": len(non_trimmable_text)},
        )

    optional_lines: list[str] = []
    optional_lines.append("REQUIRED DIRECTIVES (TRIMMABLE):")
    optional_lines.extend([f"- {directive}" for directive in required_directives])
    if isinstance(template_value, str) and template_value:
        optional_lines.append("")
        optional_lines.append("TEMPLATE (TRIMMABLE):")
        optional_lines.append(template_value)

    optional_prefix = "\n\n"
    available_for_optional = char_limit - len(non_trimmable_text) - len(optional_prefix)
    if available_for_optional <= 0:
        return {"status": "ok", "prompt_text": non_trimmable_text, "trimmed": bool(optional_lines)}

    included_optional_lines: list[str] = []
    current_optional_text = ""
    for line in optional_lines:
        candidate_lines = [*included_optional_lines, line]
        candidate_optional_text = "\n".join(candidate_lines)
        if len(candidate_optional_text) > available_for_optional:
            break
        included_optional_lines = candidate_lines
        current_optional_text = candidate_optional_text

    if not included_optional_lines:
        return {"status": "ok", "prompt_text": non_trimmable_text, "trimmed": bool(optional_lines)}

    prompt_text = f"{non_trimmable_text}{optional_prefix}{current_optional_text}"
    return {
        "status": "ok",
        "prompt_text": prompt_text,
        "trimmed": len(included_optional_lines) < len(optional_lines),
    }


def _collect_used_rule_identifiers(package_generation_rules: dict[str, Any], dominant_actions: list[str]) -> dict[str, Any]:
    always_payload = package_generation_rules.get("always", {})
    action_directives = package_generation_rules.get("action_directives", {})

    always_must = always_payload.get("must", []) if isinstance(always_payload, dict) else []
    always_must_not = always_payload.get("must_not", []) if isinstance(always_payload, dict) else []

    always_must_ids = [f"always.must[{index}]" for index, _ in enumerate(always_must)]
    always_must_not_ids = [f"always.must_not[{index}]" for index, _ in enumerate(always_must_not)]

    action_ids: list[str] = []
    for action_name in dominant_actions:
        action_payload = action_directives.get(action_name, {}) if isinstance(action_directives, dict) else {}
        if not isinstance(action_payload, dict):
            continue

        must_entries = action_payload.get("must", [])
        must_not_entries = action_payload.get("must_not", [])

        action_ids.extend(
            [
                f"action_directives.{action_name}.must[{index}]"
                for index, _ in enumerate(must_entries if isinstance(must_entries, list) else [])
            ]
        )
        action_ids.extend(
            [
                f"action_directives.{action_name}.must_not[{index}]"
                for index, _ in enumerate(must_not_entries if isinstance(must_not_entries, list) else [])
            ]
        )

    return {
        "rules_kind": "package_generation",
        "dominant_actions": dominant_actions,
        "always": {
            "must": always_must_ids,
            "must_not": always_must_not_ids,
        },
        "action_directives": action_ids,
    }


def _ruleset_hash(package_generation_rules: dict[str, Any]) -> str:
    canonical_payload = json.dumps(package_generation_rules, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()


def _error_response(code: str, message: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    response_payload: dict[str, Any] = {
        "status": "error",
        "code": code,
        "errors": [
            {
                "code": code,
                "message": message,
                "file": None,
                "severity": "error",
            }
        ],
    }
    if isinstance(extra, dict):
        response_payload.update(extra)
    return response_payload


def _rules_load_error_response(rules_error: RulesLoadException) -> dict[str, Any]:
    error_payload = rules_error.error_payload
    return {
        "status": "error",
        "code": error_payload.code,
        "errors": [
            {
                "code": error_payload.code,
                "message": error_payload.message,
                "file": error_payload.file_path,
                "severity": "error",
                "validation_issues": [
                    {
                        "code": issue.code,
                        "message": issue.message,
                        "path": issue.path,
                    }
                    for issue in error_payload.validation_issues
                ],
            }
        ],
    }