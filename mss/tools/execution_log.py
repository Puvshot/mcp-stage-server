from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mss.storage.plan_cache import runner_load_plan_cache
from mss.storage.state import runner_load_state


EXECUTION_LOG_FILENAME = "execution_log.json"
STATE_FILENAME = "state.json"
_FILE_ACTIONS_WITH_SIDE_EFFECTS = {"CREATE", "EDIT", "DELETE", "MOVE", "RENAME"}
_SCOPE_WARNING_CODES = {"FILE_NOT_IN_SCOPE_TRACKED", "FILE_NOT_IN_SCOPE_CREATED"}


def append(plan_dir: str, plan_id: str, package_id: str, narrative: str) -> dict[str, Any]:
    """Append or upsert one execution log entry with mechanical + narrative data.

    This tool is side-effecting and not idempotent by default because it writes to
    `execution_log.json`. For the same `(plan_id, package_id)` pair it performs an
    upsert to remain retry-safe.
    """
    resolved_plan_dir = Path(plan_dir).resolve()

    if not isinstance(plan_id, str) or not plan_id.strip():
        return _error_response("INVALID_PLAN_ID", "plan_id must be a non-empty string")
    if not isinstance(package_id, str) or not package_id.strip():
        return _error_response("INVALID_PACKAGE_ID", "package_id must be a non-empty string")
    if not isinstance(narrative, str):
        return _error_response("INVALID_NARRATIVE", "narrative must be a string")

    plan_cache = runner_load_plan_cache(resolved_plan_dir)
    if plan_cache is None:
        return _error_response("PLAN_NOT_INITIALIZED", "Plan cache is missing")
    if str(plan_cache.get("plan_id", "")) != plan_id:
        return _error_response("PLAN_ID_MISMATCH", f"Expected plan_id {plan_cache.get('plan_id', '')}, got {plan_id}")

    package_snapshot = _find_package(plan_cache, package_id)
    if package_snapshot is None:
        return _error_response("PACKAGE_NOT_FOUND", f"Package not found: {package_id}")

    state_snapshot = _load_state_if_exists(resolved_plan_dir)
    mechanical_entry = _build_mechanical_entry(package_snapshot, state_snapshot)
    mechanical_entry["package_id"] = package_id
    mechanical_entry["narrative"] = narrative

    log_payload = _load_execution_log_payload(resolved_plan_dir, plan_id)
    entries = log_payload["entries"]

    existing_index = _find_entry_index(entries, package_id)
    if existing_index is None:
        entries.append(mechanical_entry)
        entry_index = len(entries) - 1
    else:
        entries[existing_index] = mechanical_entry
        entry_index = existing_index

    _save_execution_log_payload(resolved_plan_dir, {"plan_id": plan_id, "entries": entries})
    return {
        "status": "appended",
        "entry_index": entry_index,
    }


def read(plan_dir: str, plan_id: str, last_n: int | None = None) -> dict[str, Any]:
    """Read execution log entries for one plan with optional tail window.

    This read-only tool is idempotent.
    """
    resolved_plan_dir = Path(plan_dir).resolve()

    if not isinstance(plan_id, str) or not plan_id.strip():
        return _error_response("INVALID_PLAN_ID", "plan_id must be a non-empty string")

    normalized_last_n: int | None = None
    if last_n is not None:
        if not isinstance(last_n, int) or last_n <= 0:
            return _error_response("INVALID_LAST_N", "last_n must be a positive integer")
        normalized_last_n = last_n

    payload = _load_execution_log_payload(resolved_plan_dir, plan_id)
    entries = payload["entries"]
    if normalized_last_n is not None:
        entries = entries[-normalized_last_n:]

    return {
        "plan_id": plan_id,
        "entries": entries,
    }


def _build_mechanical_entry(package_snapshot: dict[str, Any], state_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    package_stages = package_snapshot.get("stages", [])
    stage_ids = [str(stage.get("stage_id", "")) for stage in package_stages if str(stage.get("stage_id", ""))]
    completed_stage_ids = [
        str(stage.get("stage_id", ""))
        for stage in package_stages
        if str(stage.get("status", "")) == "done" and str(stage.get("stage_id", ""))
    ]

    if _active_stage_ready_to_advance(package_snapshot, state_snapshot):
        active_stage_id = _active_stage_id(package_snapshot, state_snapshot)
        if active_stage_id and active_stage_id not in completed_stage_ids and active_stage_id in stage_ids:
            completed_stage_ids.append(active_stage_id)

    retries_total = 0
    scope_warnings: list[dict[str, Any]] = []
    for stage_snapshot in package_stages:
        retries_total += _to_int(stage_snapshot.get("retry_count"), 0)
        last_error = stage_snapshot.get("last_error")
        if isinstance(last_error, dict):
            mechanical_errors = last_error.get("mechanical_errors", [])
            if isinstance(mechanical_errors, list):
                for mechanical_error in mechanical_errors:
                    if not isinstance(mechanical_error, dict):
                        continue
                    error_code = str(mechanical_error.get("code", ""))
                    error_severity = str(mechanical_error.get("severity", ""))
                    if error_code in _SCOPE_WARNING_CODES and error_severity == "warning":
                        scope_warnings.append(mechanical_error)

    files_modified = _collect_files_modified(package_snapshot)
    test_results = _derive_test_results(package_snapshot, state_snapshot)

    return {
        "package_id": str(package_snapshot.get("package_id", "PACKAGE_UNKNOWN")),
        "completed_at": _now_iso(),
        "stages_completed": completed_stage_ids,
        "retries_total": retries_total,
        "files_modified": files_modified,
        "scope_warnings": scope_warnings,
        "test_results": test_results,
        "narrative": None,
    }


def _collect_files_modified(package_snapshot: dict[str, Any]) -> list[str]:
    files_modified: list[str] = []
    seen_paths: set[str] = set()
    for file_entry in package_snapshot.get("files_to_modify", []):
        if not isinstance(file_entry, dict):
            continue
        action_name = str(file_entry.get("action", "")).upper()
        file_path = str(file_entry.get("path", "")).strip()
        if action_name not in _FILE_ACTIONS_WITH_SIDE_EFFECTS or not file_path:
            continue
        if file_path in seen_paths:
            continue
        seen_paths.add(file_path)
        files_modified.append(file_path)
    return files_modified


def _derive_test_results(package_snapshot: dict[str, Any], state_snapshot: dict[str, Any] | None) -> dict[str, str]:
    command_value = ""
    package_verification_commands = package_snapshot.get("verification_commands", [])
    if isinstance(package_verification_commands, list) and package_verification_commands:
        command_value = str(package_verification_commands[-1])
    if not command_value:
        package_stages = package_snapshot.get("stages", [])
        if isinstance(package_stages, list) and package_stages:
            last_stage = package_stages[-1]
            if isinstance(last_stage, dict):
                command_value = str(last_stage.get("test_command") or "")

    result_value = "PASS"
    if isinstance(state_snapshot, dict):
        sequence_hooks = state_snapshot.get("sequence_hooks", {})
        if isinstance(sequence_hooks, dict) and str(sequence_hooks.get("test_report_status", "")) == "fail":
            result_value = "FAIL"

    return {
        "command": command_value,
        "result": result_value,
        "output_snippet": "",
    }


def _active_stage_ready_to_advance(package_snapshot: dict[str, Any], state_snapshot: dict[str, Any] | None) -> bool:
    if not isinstance(state_snapshot, dict):
        return False
    sequence_hooks = state_snapshot.get("sequence_hooks", {})
    if not isinstance(sequence_hooks, dict):
        return False
    if str(sequence_hooks.get("test_report_status", "")) != "ready_to_advance":
        return False

    active_stage_id = _active_stage_id(package_snapshot, state_snapshot)
    if not active_stage_id:
        return False
    return True


def _active_stage_id(package_snapshot: dict[str, Any], state_snapshot: dict[str, Any] | None) -> str:
    if not isinstance(state_snapshot, dict):
        return ""
    cursor = state_snapshot.get("cursor", {})
    if not isinstance(cursor, dict):
        return ""
    active_stage_index = _to_int(cursor.get("stage_index"), -1)
    package_stages = package_snapshot.get("stages", [])
    if not isinstance(package_stages, list):
        return ""
    if active_stage_index < 0 or active_stage_index >= len(package_stages):
        return ""
    stage_snapshot = package_stages[active_stage_index]
    if not isinstance(stage_snapshot, dict):
        return ""
    return str(stage_snapshot.get("stage_id", ""))


def _find_package(plan_cache: dict[str, Any], package_id: str) -> dict[str, Any] | None:
    for package_snapshot in plan_cache.get("packages", []):
        if not isinstance(package_snapshot, dict):
            continue
        if str(package_snapshot.get("package_id", "")) == package_id:
            return package_snapshot
    return None


def _find_entry_index(entries: list[dict[str, Any]], package_id: str) -> int | None:
    for index, entry in enumerate(entries):
        if str(entry.get("package_id", "")) == package_id:
            return index
    return None


def _load_execution_log_payload(plan_dir: Path, plan_id: str) -> dict[str, Any]:
    execution_log_path = plan_dir / EXECUTION_LOG_FILENAME
    if not execution_log_path.exists():
        return {"plan_id": plan_id, "entries": []}

    with execution_log_path.open("r", encoding="utf-8") as execution_log_file:
        loaded_payload = json.load(execution_log_file)

    loaded_plan_id = str(loaded_payload.get("plan_id", ""))
    loaded_entries = loaded_payload.get("entries", [])
    if loaded_plan_id and loaded_plan_id != plan_id:
        return {"plan_id": plan_id, "entries": []}
    if not isinstance(loaded_entries, list):
        return {"plan_id": plan_id, "entries": []}
    normalized_entries = [entry for entry in loaded_entries if isinstance(entry, dict)]
    return {
        "plan_id": plan_id,
        "entries": normalized_entries,
    }


def _save_execution_log_payload(plan_dir: Path, payload: dict[str, Any]) -> None:
    execution_log_path = plan_dir / EXECUTION_LOG_FILENAME
    plan_dir.mkdir(parents=True, exist_ok=True)
    with execution_log_path.open("w", encoding="utf-8") as execution_log_file:
        json.dump(payload, execution_log_file, ensure_ascii=False, indent=2)


def _load_state_if_exists(plan_dir: Path) -> dict[str, Any] | None:
    state_path = plan_dir / STATE_FILENAME
    if not state_path.exists():
        return None
    return runner_load_state(state_path)


def _to_int(raw_value: Any, default_value: int) -> int:
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return default_value


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