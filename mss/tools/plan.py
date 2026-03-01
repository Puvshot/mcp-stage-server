from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mss.parsers.markdown import parse_package_markdown
from mss.rules.loader import RulesLoadException, load_rules_payload
from mss.storage.plan_cache import load_plan_cache, save_plan_cache_atomic
from mss.storage.state import create_initial_state, load_state, save_state_atomic


STATE_FILENAME = "state.json"
EXPORT_DIRNAME = "export"


def store(plan: dict[str, Any], plan_dir: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Store full JSON plan payload and initialize runtime state.

    This tool is not idempotent because it overwrites `plan_cache.json` and
    `state.json` for the provided `plan_dir`.
    """
    resolved_plan_dir = Path(plan_dir).resolve()
    resolved_plan_dir.mkdir(parents=True, exist_ok=True)

    if not isinstance(plan, dict):
        return _error_response("INVALID_PLAN_STRUCTURE", "plan must be an object")

    plan_cache_result = _build_plan_cache_from_plan_payload(plan)
    if plan_cache_result.get("status") == "error":
        return plan_cache_result

    plan_cache = plan_cache_result["plan_cache"]
    plan_cache["created_at"] = _now_iso()
    plan_cache["source_format"] = "json"
    plan_cache["rules_hash"] = _default_rules_hash()
    plan_cache["plan_hash"] = _sha256_for_text(json.dumps(plan, ensure_ascii=False, sort_keys=True))

    save_plan_cache_atomic(resolved_plan_dir, plan_cache)

    max_retries = _resolve_max_retries(config)
    state_path = resolved_plan_dir / STATE_FILENAME
    initial_state = create_initial_state(
        plan_id=str(plan_cache["plan_id"]),
        rules_hash=str(plan_cache["rules_hash"]),
        plan_hash=str(plan_cache["plan_hash"]),
        max_retries=max_retries,
    )
    initial_state["pipeline_status"] = "running"
    initial_state["sequence_hooks"] = {
        "guard_reported": False,
        "test_report_status": None,
    }
    save_state_atomic(state_path, initial_state)

    export_payload = export(plan_dir=str(resolved_plan_dir))
    if export_payload.get("status") == "error":
        return export_payload

    first_package_id = str(plan_cache["packages"][0]["package_id"])
    return {
        "status": "stored",
        "plan_id": plan_cache["plan_id"],
        "stages_total": plan_cache["stages_total"],
        "export_path": export_payload["export_path"],
        "git_instruction": {
            "baseline_command": f"git add . && git commit -m 'baseline: before {first_package_id}'",
        },
    }


def list(plan_dir: str) -> dict[str, Any]:
    """List stored plan metadata for given runtime directory.

    This read-only tool is idempotent.
    """
    resolved_plan_dir = Path(plan_dir).resolve()
    cached_plan = load_plan_cache(resolved_plan_dir)
    if cached_plan is None:
        return {"plans": []}

    state_path = resolved_plan_dir / STATE_FILENAME
    pipeline_status = "initializing"
    if state_path.exists():
        state_snapshot = load_state(state_path)
        pipeline_status = str(state_snapshot.get("pipeline_status", "initializing"))

    return {
        "plans": [
            {
                "plan_id": cached_plan.get("plan_id", ""),
                "plan_name": cached_plan.get("plan_name", "UNKNOWN: plan name not found"),
                "stages_total": int(cached_plan.get("stages_total", 0)),
                "created_at": cached_plan.get("created_at", ""),
                "pipeline_status": pipeline_status,
            }
        ]
    }


def reset(plan_dir: str) -> dict[str, Any]:
    """Reset runtime cursor and status for already initialized plan cache.

    This tool is not idempotent because it mutates persisted status fields.
    """
    resolved_plan_dir = Path(plan_dir).resolve()
    plan_cache = load_plan_cache(resolved_plan_dir)
    state_path = resolved_plan_dir / STATE_FILENAME

    if plan_cache is None or not state_path.exists():
        return _error_response("PLAN_NOT_INITIALIZED", "Plan cache or state is missing")

    for package_snapshot in plan_cache.get("packages", []):
        package_snapshot["status"] = "pending"
        package_snapshot["completed_at"] = None
        for stage_snapshot in package_snapshot.get("stages", []):
            stage_snapshot["status"] = "pending"
            stage_snapshot["retry_count"] = 0
            stage_snapshot["last_error"] = None

    save_plan_cache_atomic(resolved_plan_dir, plan_cache)

    previous_state = load_state(state_path)
    max_retries = int(previous_state.get("max_retries", 2))
    initial_state = create_initial_state(
        plan_id=str(plan_cache.get("plan_id", "")),
        rules_hash=str(plan_cache.get("rules_hash", "")),
        plan_hash=str(plan_cache.get("plan_hash", "")),
        max_retries=max_retries,
    )
    initial_state["pipeline_status"] = "running"
    initial_state["sequence_hooks"] = {
        "guard_reported": False,
        "test_report_status": None,
    }
    save_state_atomic(state_path, initial_state)

    return {
        "status": "reset",
        "plan_id": plan_cache.get("plan_id", ""),
        "pipeline_status": "running",
        "cursor": {
            "package_index": 0,
            "stage_index": 0,
        },
    }


def export(plan_dir: str) -> dict[str, Any]:
    """Export currently cached plan into Markdown backup file.

    This tool is idempotent for unchanged plan cache content.
    """
    resolved_plan_dir = Path(plan_dir).resolve()
    plan_cache = load_plan_cache(resolved_plan_dir)
    if plan_cache is None:
        return _error_response("PLAN_NOT_INITIALIZED", "Plan cache is missing")

    export_dir = resolved_plan_dir / EXPORT_DIRNAME
    export_dir.mkdir(parents=True, exist_ok=True)
    export_path = export_dir / "PLAN.md"
    export_path.write_text(_render_plan_markdown(plan_cache), encoding="utf-8")

    return {
        "status": "exported",
        "plan_id": plan_cache.get("plan_id", ""),
        "export_path": str(export_path),
    }


def load_or_init(plan_id: str, plan_dir: str) -> dict[str, Any]:
    """Load an existing pipeline state or initialize it from PLAN/PACKAGE markdown files."""
    resolved_plan_dir = Path(plan_dir).resolve()
    if not resolved_plan_dir.exists() or not resolved_plan_dir.is_dir():
        return _error_response("PLAN_DIR_NOT_FOUND", f"Plan directory not found: {resolved_plan_dir}")

    plan_path = resolved_plan_dir / "PLAN.md"
    if not plan_path.exists():
        return _error_response("PLAN_FILE_NOT_FOUND", f"Missing PLAN.md in: {resolved_plan_dir}")

    existing_cache = load_plan_cache(resolved_plan_dir)
    state_path = resolved_plan_dir / STATE_FILENAME
    if existing_cache and existing_cache.get("plan_id") == plan_id and state_path.exists():
        return _resume_response(plan_id=plan_id, plan_path=plan_path, plan_cache=existing_cache, state_path=state_path)

    initialization_result = _build_plan_cache(plan_id=plan_id, plan_path=plan_path, plan_dir=resolved_plan_dir)
    if initialization_result.get("status") == "error":
        return initialization_result

    plan_cache = initialization_result["plan_cache"]
    warnings = initialization_result["warnings"]
    parse_warnings = len(warnings)

    save_plan_cache_atomic(resolved_plan_dir, plan_cache)

    initial_state = create_initial_state(
        plan_id=plan_id,
        rules_hash=plan_cache["rules_hash"],
        plan_hash=plan_cache["plan_hash"],
    )
    initial_state["pipeline_status"] = "running"
    initial_state["sequence_hooks"] = {
        "guard_reported": False,
        "test_report_status": None,
    }
    save_state_atomic(state_path, initial_state)

    first_package_id = plan_cache["packages"][0]["package_id"]
    baseline_command = f"git add . && git commit -m 'baseline: before {first_package_id}'"

    return {
        "status": "initialized",
        "plan_id": plan_id,
        "stages_total": plan_cache["stages_total"],
        "warnings": warnings,
        "parse_warnings": parse_warnings,
        "git_instruction": {
            "baseline_command": baseline_command,
        },
    }


def _resume_response(plan_id: str, plan_path: Path, plan_cache: dict[str, Any], state_path: Path) -> dict[str, Any]:
    state_snapshot = load_state(state_path)
    package_index = int(state_snapshot["cursor"]["package_index"])
    stage_index = int(state_snapshot["cursor"]["stage_index"])

    package_snapshot = plan_cache["packages"][package_index]
    stage_snapshot = package_snapshot["stages"][stage_index]

    warnings: list[str] = []
    current_plan_hash = _sha256_for_text(plan_path.read_text(encoding="utf-8"))
    if current_plan_hash != plan_cache.get("plan_hash"):
        warnings.append("plan_modified_externally")

    return {
        "status": "resumed",
        "plan_id": plan_id,
        "resumed_at": {
            "package_id": package_snapshot["package_id"],
            "stage_id": stage_snapshot["stage_id"],
            "retry_count": int(state_snapshot.get("retry_count", 0)),
        },
        "warnings": warnings,
    }


def _build_plan_cache(plan_id: str, plan_path: Path, plan_dir: Path) -> dict[str, Any]:
    warnings: list[str] = []
    plan_markdown = plan_path.read_text(encoding="utf-8")
    package_paths = sorted(plan_dir.glob("PACKAGE_*.md"), key=_package_sort_key)

    packages: list[dict[str, Any]] = []
    for package_path in package_paths:
        package_id = package_path.stem
        package_markdown = package_path.read_text(encoding="utf-8")
        parsed_package = parse_package_markdown(package_markdown, package_id=package_id)
        warnings.extend([f"{package_id}: {package_warning}" for package_warning in parsed_package.get("warnings", [])])

        parsed_package["depends_on"] = _extract_depends_on(package_markdown, warnings, package_id)
        parsed_package["status"] = "pending"
        parsed_package["completed_at"] = None

        files_in_scope = [entry["path"] for entry in parsed_package["files_to_modify"] if entry.get("path")]
        for stage in parsed_package["stages"]:
            stage["files_in_scope"] = files_in_scope
            stage["status"] = "pending"
            stage["retry_count"] = 0
            stage["last_error"] = None

        packages.append(parsed_package)

    stages_total = sum(len(package["stages"]) for package in packages)
    if stages_total == 0:
        return _error_response("NO_STAGES_FOUND", "No stages detected in PACKAGE markdown files")

    plan_name = _extract_plan_name(plan_markdown)
    rules_hash = _default_rules_hash()
    plan_hash = _sha256_for_text(plan_markdown)

    plan_cache = {
        "plan_id": plan_id,
        "plan_name": plan_name,
        "created_at": _now_iso(),
        "source_format": "markdown",
        "goal": _extract_plan_section(plan_markdown, "## Goal", warnings),
        "scope": _extract_plan_list(plan_markdown, "## Scope", warnings),
        "out_of_scope": _extract_plan_list(plan_markdown, "## Out of scope", warnings),
        "constraints": _extract_plan_list(plan_markdown, "## Non-negotiable constraints", warnings),
        "stop_conditions": _extract_plan_list(plan_markdown, "## Stop conditions", warnings),
        "risks": _extract_plan_list(plan_markdown, "## Risks", warnings),
        "packages": packages,
        "rules_hash": rules_hash,
        "plan_hash": plan_hash,
        "stages_total": stages_total,
    }

    return {
        "status": "ok",
        "plan_cache": plan_cache,
        "warnings": warnings,
    }


def _build_plan_cache_from_plan_payload(plan_payload: dict[str, Any]) -> dict[str, Any]:
    plan_id = str(plan_payload.get("plan_id", "")).strip()
    if not plan_id:
        return _error_response("INVALID_PLAN_STRUCTURE", "plan.plan_id is required")

    packages_payload = plan_payload.get("packages")
    if not isinstance(packages_payload, list) or not packages_payload:
        return _error_response("INVALID_PLAN_STRUCTURE", "plan.packages must be a non-empty list")

    normalized_packages: list[dict[str, Any]] = []
    total_stage_count = 0
    for package_index, package_payload in enumerate(packages_payload, start=1):
        if not isinstance(package_payload, dict):
            return _error_response("INVALID_PLAN_STRUCTURE", f"package at index {package_index - 1} must be an object")

        package_id = str(package_payload.get("package_id") or f"PACKAGE_{package_index}")
        stages_payload = package_payload.get("stages")
        if not isinstance(stages_payload, list) or not stages_payload:
            return _error_response("INVALID_PLAN_STRUCTURE", f"package {package_id} must contain non-empty stages")

        normalized_stages: list[dict[str, Any]] = []
        for stage_index, stage_payload in enumerate(stages_payload, start=1):
            if not isinstance(stage_payload, dict):
                return _error_response(
                    "INVALID_PLAN_STRUCTURE",
                    f"stage at index {stage_index - 1} in {package_id} must be an object",
                )

            stage_id = str(stage_payload.get("stage_id") or f"{package_id}_STAGE_{stage_index}")
            steps_payload = stage_payload.get("steps")
            steps = steps_payload if isinstance(steps_payload, list) else []
            dominant_actions_payload = stage_payload.get("dominant_actions")
            dominant_actions = dominant_actions_payload if isinstance(dominant_actions_payload, list) else []
            files_in_scope_payload = stage_payload.get("files_in_scope")
            files_in_scope = files_in_scope_payload if isinstance(files_in_scope_payload, list) else []

            normalized_stages.append(
                {
                    "stage_id": stage_id,
                    "stage_number": int(stage_payload.get("stage_number", stage_index)),
                    "stage_name": str(stage_payload.get("stage_name", f"Stage {stage_index}")),
                    "steps": [step for step in steps if isinstance(step, dict)],
                    "test_command": stage_payload.get("test_command"),
                    "dominant_actions": [str(action) for action in dominant_actions],
                    "files_in_scope": [str(file_path) for file_path in files_in_scope if str(file_path)],
                    "status": "pending",
                    "retry_count": 0,
                    "last_error": None,
                }
            )

        total_stage_count += len(normalized_stages)

        file_entries_payload = package_payload.get("files_to_modify")
        file_entries = file_entries_payload if isinstance(file_entries_payload, list) else []
        normalized_file_entries: list[dict[str, Any]] = []
        for file_entry in file_entries:
            if not isinstance(file_entry, dict):
                continue
            normalized_file_entries.append(
                {
                    "path": str(file_entry.get("path", "")),
                    "action": str(file_entry.get("action", "UNKNOWN")),
                    "is_smoke_test": bool(file_entry.get("is_smoke_test", False)),
                    "unknown": file_entry.get("unknown"),
                }
            )

        normalized_packages.append(
            {
                "package_id": package_id,
                "package_name": str(package_payload.get("package_name", package_id)),
                "depends_on": [str(value) for value in package_payload.get("depends_on", []) if str(value)],
                "goal": str(package_payload.get("goal", "UNKNOWN: section not found")),
                "files_to_modify": normalized_file_entries,
                "stages": normalized_stages,
                "verification_commands": [
                    str(command) for command in package_payload.get("verification_commands", []) if str(command)
                ],
                "status": "pending",
                "completed_at": None,
            }
        )

    if total_stage_count <= 0:
        return _error_response("INVALID_PLAN_STRUCTURE", "No stages found in plan payload")

    plan_cache = {
        "plan_id": plan_id,
        "plan_name": str(plan_payload.get("plan_name", plan_id)),
        "created_at": _now_iso(),
        "source_format": "json",
        "goal": str(plan_payload.get("goal", "UNKNOWN: section not found")),
        "scope": [str(value) for value in plan_payload.get("scope", []) if str(value)],
        "out_of_scope": [str(value) for value in plan_payload.get("out_of_scope", []) if str(value)],
        "constraints": [str(value) for value in plan_payload.get("constraints", []) if str(value)],
        "stop_conditions": [str(value) for value in plan_payload.get("stop_conditions", []) if str(value)],
        "risks": [str(value) for value in plan_payload.get("risks", []) if str(value)],
        "packages": normalized_packages,
        "rules_hash": "",
        "plan_hash": "",
        "stages_total": total_stage_count,
    }
    return {
        "status": "ok",
        "plan_cache": plan_cache,
    }


def _extract_depends_on(package_markdown: str, warnings: list[str], package_id: str) -> list[str]:
    frontmatter_match = re.match(r"^---\s*(.*?)\s*---", package_markdown, flags=re.DOTALL)
    if not frontmatter_match:
        warnings.append(f"{package_id}: missing YAML frontmatter")
        return []

    frontmatter_text = frontmatter_match.group(1)
    depends_match = re.search(r"DEPENDS_ON\s*:\s*\[(.*?)\]", frontmatter_text)
    if not depends_match:
        warnings.append(f"{package_id}: DEPENDS_ON not found in frontmatter")
        return []

    depends_values = [value.strip().strip("\"'") for value in depends_match.group(1).split(",")]
    return [value for value in depends_values if value]


def _extract_plan_name(plan_markdown: str) -> str:
    for raw_line in plan_markdown.splitlines():
        stripped_line = raw_line.strip()
        if stripped_line.startswith("#"):
            return stripped_line.lstrip("#").strip() or "UNKNOWN: plan name not found"
    return "UNKNOWN: plan name not found"


def _extract_plan_section(plan_markdown: str, header: str, warnings: list[str]) -> str:
    section_lines, found = _extract_section_lines(plan_markdown, header)
    if not found:
        warnings.append(f"missing section: {header}")
        return "UNKNOWN: section not found"

    section_text = "\n".join(line.strip() for line in section_lines if line.strip())
    if not section_text:
        warnings.append(f"empty section: {header}")
        return "UNKNOWN: section not found"
    return section_text


def _extract_plan_list(plan_markdown: str, header: str, warnings: list[str]) -> list[str]:
    section_lines, found = _extract_section_lines(plan_markdown, header)
    if not found:
        warnings.append(f"missing section: {header}")
        return []

    list_items: list[str] = []
    for section_line in section_lines:
        stripped_line = section_line.strip()
        if stripped_line.startswith("- "):
            list_items.append(stripped_line[2:].strip())

    if not list_items:
        warnings.append(f"section {header} has no list items")

    return list_items


def _extract_section_lines(markdown_text: str, header: str) -> tuple[list[str], bool]:
    markdown_lines = markdown_text.splitlines()
    start_index: int | None = None
    for line_number, markdown_line in enumerate(markdown_lines):
        if markdown_line.strip().lower() == header.lower():
            start_index = line_number + 1
            break

    if start_index is None:
        return [], False

    collected_lines: list[str] = []
    for markdown_line in markdown_lines[start_index:]:
        stripped_line = markdown_line.strip()
        if stripped_line.startswith("## "):
            break
        collected_lines.append(markdown_line)

    return collected_lines, True


def _package_sort_key(package_path: Path) -> tuple[int, str]:
    match = re.match(r"PACKAGE_(\d+)", package_path.stem)
    package_number = int(match.group(1)) if match else 9999
    return (package_number, package_path.stem)


def _default_rules_hash() -> str:
    try:
        package_generation_rules = load_rules_payload("package_generation")
    except RulesLoadException:
        return _sha256_for_text("")

    normalized_rules_json = json.dumps(package_generation_rules, ensure_ascii=False, sort_keys=True)
    return _sha256_for_text(normalized_rules_json)


def _resolve_max_retries(config: dict[str, Any] | None) -> int:
    if not isinstance(config, dict):
        return 2

    raw_max_retries = config.get("max_retries")
    try:
        normalized_max_retries = int(raw_max_retries)
    except (TypeError, ValueError):
        return 2

    return max(1, normalized_max_retries)


def _render_plan_markdown(plan_cache: dict[str, Any]) -> str:
    lines: list[str] = []
    plan_name = str(plan_cache.get("plan_name") or plan_cache.get("plan_id") or "UNKNOWN")
    lines.append(f"# {plan_name}")
    lines.append("")

    _append_section(lines, "Goal", [str(plan_cache.get("goal", "UNKNOWN: section not found"))])
    _append_section(lines, "Scope", [f"- {entry}" for entry in plan_cache.get("scope", [])])
    _append_section(lines, "Out of scope", [f"- {entry}" for entry in plan_cache.get("out_of_scope", [])])
    _append_section(lines, "Non-negotiable constraints", [f"- {entry}" for entry in plan_cache.get("constraints", [])])
    _append_section(lines, "Stop conditions", [f"- {entry}" for entry in plan_cache.get("stop_conditions", [])])
    _append_section(lines, "Risks", [f"- {entry}" for entry in plan_cache.get("risks", [])])

    lines.append("## Packages")
    for package_snapshot in plan_cache.get("packages", []):
        package_id = str(package_snapshot.get("package_id", "PACKAGE_UNKNOWN"))
        package_name = str(package_snapshot.get("package_name", "UNKNOWN: package name not found"))
        lines.append(f"- {package_id}: {package_name}")
        for stage_snapshot in package_snapshot.get("stages", []):
            stage_id = str(stage_snapshot.get("stage_id", "UNKNOWN_STAGE"))
            stage_name = str(stage_snapshot.get("stage_name", "UNKNOWN: stage name not found"))
            lines.append(f"  - {stage_id}: {stage_name}")

    lines.append("")
    return "\n".join(lines)


def _append_section(lines: list[str], section_name: str, section_lines: list[str]) -> None:
    lines.append(f"## {section_name}")
    if section_lines:
        lines.extend(section_lines)
    else:
        lines.append("UNKNOWN: section not found")
    lines.append("")


def _sha256_for_text(text_value: str) -> str:
    return hashlib.sha256(text_value.encode("utf-8")).hexdigest()


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