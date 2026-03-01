from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mss.rules.loader import (
    RulesLoadException,
    runner_load_all_required_rules_payloads,
    runner_load_rules_payload,
)
from mss.storage.plan_cache import load_plan_cache

load_rules_payload = runner_load_rules_payload


def get_full(plan_dir: str) -> dict[str, Any]:
    """Return fully merged rules payload for given plan directory.

    This read-only tool is idempotent.
    """
    if not os.getenv("MCP_DEBUG_VERBOSE"):
        return _error_response(
            "FORBIDDEN_VERBOSE_MODE",
            "rules.get_full requires MCP_DEBUG_VERBOSE=1",
        )
    Path(plan_dir).resolve()
    try:
        all_rules_payloads = runner_load_all_required_rules_payloads()
    except RulesLoadException as rules_error:
        return _rules_load_error_response(rules_error)
    return {
        "rules": all_rules_payloads,
    }


def version(plan_dir: str) -> dict[str, Any]:
    """Return active rules version and hash-like metadata.

    This read-only tool is idempotent.
    """
    resolved_plan_dir = Path(plan_dir).resolve()
    try:
        package_generation_rules = load_rules_payload("package_generation")
    except RulesLoadException as rules_error:
        return _rules_load_error_response(rules_error)
    plan_cache = load_plan_cache(resolved_plan_dir)
    return {
        "version": str(package_generation_rules.get("version", "unknown")),
        "rules_hash": str(plan_cache.get("rules_hash", "")) if isinstance(plan_cache, dict) else "",
        "generated_at": _now_iso(),
    }


def directive_pack(plan_dir: str, stage_id: str) -> dict[str, Any]:
    """Return contract-first directive pack for a given stage_id.

    This read-only tool is idempotent.

    Directives are resolved exclusively from JSON SSOT kind `package_generation`
    and the selected stage snapshot.
    """
    resolved_plan_dir = Path(plan_dir).resolve()
    if not isinstance(stage_id, str) or not stage_id.strip():
        return _error_response("INVALID_STAGE_ID", "stage_id must be a non-empty string")

    plan_cache = load_plan_cache(resolved_plan_dir)
    if plan_cache is None:
        return _error_response("PLAN_NOT_INITIALIZED", "Plan cache is missing")

    stage_snapshot = _find_stage(plan_cache, stage_id)
    if stage_snapshot is None:
        return _error_response("STAGE_NOT_FOUND", f"Stage not found: {stage_id}")

    try:
        package_generation_rules = load_rules_payload("package_generation")
    except RulesLoadException as rules_error:
        return _rules_load_error_response(rules_error)

    dominant_actions = [str(action) for action in stage_snapshot.get("dominant_actions", [])]

    must_directives = list(package_generation_rules.get("always", {}).get("must", []))
    must_not_directives = list(package_generation_rules.get("always", {}).get("must_not", []))

    action_directives = package_generation_rules.get("action_directives", {})
    for dominant_action in dominant_actions:
        action_payload = action_directives.get(dominant_action, {})
        must_directives.extend(action_payload.get("must", []))
        must_not_directives.extend(action_payload.get("must_not", []))

    deduped_must = _dedupe_preserve_order(must_directives)
    deduped_must_not = _dedupe_preserve_order(must_not_directives)
    template_key = "+".join(dominant_actions)
    templates = package_generation_rules.get("templates", {})
    template_value = templates.get(template_key)
    if not isinstance(template_value, str) or not template_value:
        fallback_template = templates.get("default")
        template_value = fallback_template if isinstance(fallback_template, str) and fallback_template else None

    directive_pack_payload = {
        "stage_id": stage_id,
        "dominant_actions": dominant_actions,
        "must": deduped_must,
        "must_not": deduped_must_not,
        "template": template_value,
        "token_estimate": _token_estimate(deduped_must, deduped_must_not, template_value),
        "generated_at": _now_iso(),
    }
    return {"directive_pack": directive_pack_payload}


def _find_stage(plan_cache: dict[str, Any], stage_id: str) -> dict[str, Any] | None:
    for package_snapshot in plan_cache.get("packages", []):
        for stage_snapshot in package_snapshot.get("stages", []):
            if stage_snapshot.get("stage_id") == stage_id:
                return stage_snapshot
    return None


def _dedupe_preserve_order(values: list[Any]) -> list[Any]:
    deduped_values: list[Any] = []
    seen_values: set[str] = set()
    for value in values:
        marker = json.dumps(value, ensure_ascii=False, sort_keys=True)
        if marker in seen_values:
            continue
        seen_values.add(marker)
        deduped_values.append(value)
    return deduped_values


def _token_estimate(must_values: list[str], must_not_values: list[str], template_value: Any) -> int:
    merged_text = " ".join(must_values + must_not_values)
    if isinstance(template_value, str) and template_value:
        merged_text = f"{merged_text} {template_value}".strip()
    if not merged_text:
        return 1
    return max(1, len(merged_text) // 4)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _error_response(code: str, message: str) -> dict[str, Any]:
    return {
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