from __future__ import annotations

from pathlib import Path
from typing import Any

from mss.storage.plan_cache import load_plan_cache
from mss.storage.state import load_state, save_state_atomic
from mss.tools.collision import analyze as collision_analyze


STATE_FILENAME = "state.json"


def current(plan_dir: str) -> dict[str, Any]:
    """Return current stage payload for the active cursor in persisted pipeline state."""
    resolved_plan_dir = Path(plan_dir).resolve()
    state_snapshot, plan_cache = _load_runtime_payload(resolved_plan_dir)
    if state_snapshot is None or plan_cache is None:
        return _error_response("PLAN_NOT_INITIALIZED", "State or plan cache is missing")

    pipeline_status = str(state_snapshot.get("pipeline_status", "running"))
    if pipeline_status == "complete":
        return _error_response("PIPELINE_ALREADY_COMPLETE", "Pipeline is already complete")
    if pipeline_status.startswith("stopped"):
        return _error_response("PIPELINE_STOPPED", f"Pipeline is stopped: {pipeline_status}")

    package_index = int(state_snapshot["cursor"]["package_index"])
    stage_index = int(state_snapshot["cursor"]["stage_index"])

    package_snapshot = plan_cache["packages"][package_index]
    stage_snapshot = package_snapshot["stages"][stage_index]
    stage_id = str(stage_snapshot["stage_id"])
    collision_payload = collision_analyze(plan_dir=str(resolved_plan_dir), stage_id=stage_id)
    if collision_payload.get("status") == "error":
        return collision_payload

    return {
        "stage": stage_snapshot,
        "package_id": package_snapshot["package_id"],
        "package_goal": package_snapshot.get("goal", "UNKNOWN: section not found"),
        "collision": collision_payload,
        "position": {
            "package_index": package_index,
            "stage_index": stage_index,
            "stages_in_package": len(package_snapshot["stages"]),
            "packages_total": len(plan_cache["packages"]),
        },
    }


def advance(plan_dir: str) -> dict[str, Any]:
    """Advance stage cursor after successful test report according to sequence hooks."""
    resolved_plan_dir = Path(plan_dir).resolve()
    state_path = resolved_plan_dir / STATE_FILENAME
    state_snapshot, plan_cache = _load_runtime_payload(resolved_plan_dir)
    if state_snapshot is None or plan_cache is None:
        return _error_response("PLAN_NOT_INITIALIZED", "State or plan cache is missing")

    if not _can_advance(state_snapshot):
        return _sequence_error(state_snapshot)

    package_index = int(state_snapshot["cursor"]["package_index"])
    stage_index = int(state_snapshot["cursor"]["stage_index"])

    package_snapshot = plan_cache["packages"][package_index]
    stage_snapshot = package_snapshot["stages"][stage_index]
    stage_snapshot["status"] = "done"
    package_snapshot["status"] = "in_progress"

    is_last_stage_in_package = stage_index + 1 >= len(package_snapshot["stages"])
    if not is_last_stage_in_package:
        state_snapshot["cursor"]["stage_index"] = stage_index + 1
        next_stage_id = package_snapshot["stages"][stage_index + 1]["stage_id"]
        collision_payload = collision_analyze(plan_dir=str(resolved_plan_dir), stage_id=str(next_stage_id))
        if collision_payload.get("status") == "error":
            return collision_payload
        _reset_sequence_hooks(state_snapshot)
        save_state_atomic(state_path, state_snapshot)
        return {
            "pipeline_status": "running",
            "package_done": False,
            "next_stage_id": next_stage_id,
            "collision": collision_payload,
        }

    package_snapshot["status"] = "done"
    package_snapshot["completed_at"] = state_snapshot.get("last_updated_at")

    next_package_index = package_index + 1
    has_next_package = next_package_index < len(plan_cache["packages"])

    git_instruction = {
        "squash_verified": True,
        "squash_command": "git reset --soft <package_baseline_sha>",
        "squash_commit_command": f"git commit -m 'feat: completed {package_snapshot['package_id']}'",
    }

    if has_next_package:
        next_package = plan_cache["packages"][next_package_index]
        state_snapshot["cursor"]["package_index"] = next_package_index
        state_snapshot["cursor"]["stage_index"] = 0
        state_snapshot["pipeline_status"] = "running"
        next_stage_id = next_package["stages"][0]["stage_id"]
        collision_payload = collision_analyze(plan_dir=str(resolved_plan_dir), stage_id=str(next_stage_id))
        if collision_payload.get("status") == "error":
            return collision_payload
        git_instruction["baseline_next_command"] = (
            f"git add . && git commit -m 'baseline: before {next_package['package_id']}'"
        )
        response_payload = {
            "pipeline_status": "running",
            "package_done": True,
            "package_id": package_snapshot["package_id"],
            "git_instruction": git_instruction,
            "next_stage_id": next_stage_id,
            "collision": collision_payload,
        }
    else:
        state_snapshot["pipeline_status"] = "complete"
        response_payload = {
            "pipeline_status": "complete",
            "package_done": True,
            "package_id": package_snapshot["package_id"],
            "git_instruction": git_instruction,
        }

    _reset_sequence_hooks(state_snapshot)
    save_state_atomic(state_path, state_snapshot)
    return response_payload


def rewind(plan_dir: str, reason: str | None = None) -> dict[str, Any]:
    """Rewind runtime cursor to previous stage and clear retry state.

    This tool is side-effecting and idempotent for repeated calls at the first
    stage. It is intended for manual recovery after stopped/failing states.
    """
    resolved_plan_dir = Path(plan_dir).resolve()
    state_path = resolved_plan_dir / STATE_FILENAME
    state_snapshot, plan_cache = _load_runtime_payload(resolved_plan_dir)
    if state_snapshot is None or plan_cache is None:
        return _error_response("PLAN_NOT_INITIALIZED", "State or plan cache is missing")

    if reason is not None and not isinstance(reason, str):
        return _error_response("INVALID_REWIND_REASON", "reason must be a string when provided")

    pipeline_status = str(state_snapshot.get("pipeline_status", "running"))
    if pipeline_status == "complete":
        return _error_response("PIPELINE_ALREADY_COMPLETE", "Pipeline is already complete")

    next_cursor = _previous_cursor(state_snapshot=state_snapshot, plan_cache=plan_cache)
    state_snapshot["cursor"]["package_index"] = next_cursor["package_index"]
    state_snapshot["cursor"]["stage_index"] = next_cursor["stage_index"]
    state_snapshot["pipeline_status"] = "running"
    _reset_sequence_hooks(state_snapshot)
    save_state_atomic(state_path, state_snapshot)

    rewound_stage_id = _active_stage_id(state_snapshot=state_snapshot, plan_cache=plan_cache)
    return {
        "status": "rewound",
        "rewound_to": rewound_stage_id,
        "retry_count": int(state_snapshot.get("retry_count", 0)),
    }


def peek_next(plan_dir: str) -> dict[str, Any]:
    """Return payload for the next stage without moving the active cursor.

    This read-only tool is idempotent.
    """
    resolved_plan_dir = Path(plan_dir).resolve()
    state_snapshot, plan_cache = _load_runtime_payload(resolved_plan_dir)
    if state_snapshot is None or plan_cache is None:
        return _error_response("PLAN_NOT_INITIALIZED", "State or plan cache is missing")

    pipeline_status = str(state_snapshot.get("pipeline_status", "running"))
    if pipeline_status.startswith("stopped"):
        return _error_response("PIPELINE_STOPPED", f"Pipeline is stopped: {pipeline_status}")
    if pipeline_status == "complete":
        return {
            "status": "ok",
            "has_next": False,
            "next_stage": None,
            "position": None,
        }

    next_cursor = _next_cursor(state_snapshot=state_snapshot, plan_cache=plan_cache)
    if next_cursor is None:
        return {
            "status": "ok",
            "has_next": False,
            "next_stage": None,
            "position": None,
        }

    package_index = int(next_cursor["package_index"])
    stage_index = int(next_cursor["stage_index"])
    package_snapshot = plan_cache["packages"][package_index]
    stage_snapshot = package_snapshot["stages"][stage_index]
    stage_id = str(stage_snapshot.get("stage_id", ""))

    collision_payload = collision_analyze(plan_dir=str(resolved_plan_dir), stage_id=stage_id)
    if collision_payload.get("status") == "error":
        return collision_payload

    return {
        "status": "ok",
        "has_next": True,
        "next_stage": stage_snapshot,
        "package_id": package_snapshot["package_id"],
        "position": {
            "package_index": package_index,
            "stage_index": stage_index,
            "stages_in_package": len(package_snapshot["stages"]),
            "packages_total": len(plan_cache["packages"]),
        },
        "collision": collision_payload,
    }


def _load_runtime_payload(plan_dir: Path) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    state_path = plan_dir / STATE_FILENAME
    if not state_path.exists():
        return None, None

    loaded_state = load_state(state_path)
    loaded_cache = load_plan_cache(plan_dir)
    if loaded_cache is None:
        return None, None
    return loaded_state, loaded_cache


def _can_advance(state_snapshot: dict[str, Any]) -> bool:
    sequence_hooks = state_snapshot.get("sequence_hooks", {})
    return sequence_hooks.get("test_report_status") == "ready_to_advance"


def _sequence_error(state_snapshot: dict[str, Any]) -> dict[str, Any]:
    sequence_hooks = state_snapshot.get("sequence_hooks", {})
    test_report_status = sequence_hooks.get("test_report_status")
    guard_reported = bool(sequence_hooks.get("guard_reported", False))

    if test_report_status == "fail":
        return _error_response("ADVANCE_ON_FAIL", "Cannot advance when test.report status is fail")
    if not guard_reported and test_report_status is not None:
        return _error_response("GUARD_REPORT_MISSING", "guard.report must precede test.report")
    return _error_response("ADVANCE_WITHOUT_TEST_REPORT", "Cannot advance before test.report PASS")


def _reset_sequence_hooks(state_snapshot: dict[str, Any]) -> None:
    state_snapshot["retry_count"] = 0
    state_snapshot["sequence_hooks"] = {
        "guard_reported": False,
        "test_report_status": None,
    }


def _next_cursor(state_snapshot: dict[str, Any], plan_cache: dict[str, Any]) -> dict[str, int] | None:
    package_index = int(state_snapshot["cursor"]["package_index"])
    stage_index = int(state_snapshot["cursor"]["stage_index"])

    package_snapshot = plan_cache["packages"][package_index]
    if stage_index + 1 < len(package_snapshot["stages"]):
        return {
            "package_index": package_index,
            "stage_index": stage_index + 1,
        }

    next_package_index = package_index + 1
    if next_package_index >= len(plan_cache["packages"]):
        return None

    return {
        "package_index": next_package_index,
        "stage_index": 0,
    }


def _previous_cursor(state_snapshot: dict[str, Any], plan_cache: dict[str, Any]) -> dict[str, int]:
    package_index = int(state_snapshot["cursor"]["package_index"])
    stage_index = int(state_snapshot["cursor"]["stage_index"])

    if stage_index > 0:
        return {
            "package_index": package_index,
            "stage_index": stage_index - 1,
        }

    if package_index > 0:
        previous_package_index = package_index - 1
        previous_stage_index = len(plan_cache["packages"][previous_package_index]["stages"]) - 1
        return {
            "package_index": previous_package_index,
            "stage_index": previous_stage_index,
        }

    return {
        "package_index": 0,
        "stage_index": 0,
    }


def _active_stage_id(state_snapshot: dict[str, Any], plan_cache: dict[str, Any]) -> str:
    package_index = int(state_snapshot["cursor"]["package_index"])
    stage_index = int(state_snapshot["cursor"]["stage_index"])
    return str(plan_cache["packages"][package_index]["stages"][stage_index]["stage_id"])


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