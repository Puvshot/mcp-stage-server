from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mss.storage.plan_cache import load_plan_cache
from mss.storage.state import load_state, save_state_atomic


STATE_FILENAME = "state.json"
__test__ = False


def report(
    plan_dir: str,
    stage_id: str,
    result: str,
    output: str,
    command: str,
) -> dict[str, Any]:
    """Record contract-first `test.report` result for the active stage.

    This tool enforces sequence constraints: `guard.report` must exist before
    `test.report`. It returns contract-level payloads for PASS/FAIL outcomes.
    """
    resolved_plan_dir = Path(plan_dir).resolve()
    state_path = resolved_plan_dir / STATE_FILENAME
    if not state_path.exists():
        return _error_response("PLAN_NOT_INITIALIZED", "State is missing")

    state_snapshot = load_state(state_path)
    plan_cache = load_plan_cache(resolved_plan_dir)
    if plan_cache is None:
        return _error_response("PLAN_NOT_INITIALIZED", "Plan cache is missing")

    pipeline_status = str(state_snapshot.get("pipeline_status", "running"))
    if pipeline_status == "complete":
        return _error_response("PIPELINE_ALREADY_COMPLETE", "Pipeline is already complete")
    if pipeline_status.startswith("stopped"):
        return _error_response("PIPELINE_STOPPED", f"Pipeline is stopped: {pipeline_status}")

    expected_stage_id = _active_stage_id(state_snapshot, plan_cache)
    if stage_id != expected_stage_id:
        return _error_response(
            "STAGE_ID_MISMATCH",
            f"Expected active stage_id {expected_stage_id}, got {stage_id}",
        )

    if not isinstance(output, str):
        return _error_response("INVALID_TEST_OUTPUT", "output must be a string")
    if not isinstance(command, str):
        return _error_response("INVALID_TEST_COMMAND", "command must be a string")

    normalized_result = str(result).upper()
    if normalized_result not in {"PASS", "FAIL"}:
        return _error_response("INVALID_TEST_RESULT", "result must be PASS or FAIL")

    sequence_hooks = state_snapshot.setdefault("sequence_hooks", {})
    if not bool(sequence_hooks.get("guard_reported", False)):
        return _error_response("GUARD_REPORT_MISSING", "guard.report must precede test.report")

    guard_result = _build_guard_result(state_snapshot, normalized_result)

    if normalized_result == "PASS":
        sequence_hooks["test_report_status"] = "ready_to_advance"
        state_snapshot["pipeline_status"] = "running"
        save_state_atomic(state_path, state_snapshot)
        return {
            "status": "ready_to_advance",
            "guard_result": guard_result,
            "git_instruction": {
                "wip_commit_command": _wip_commit_command(stage_id),
            },
        }

    state_snapshot["retry_count"] = int(state_snapshot.get("retry_count", 0)) + 1
    max_retries = int(state_snapshot.get("max_retries", 2))
    retry_available = int(state_snapshot["retry_count"]) < max_retries
    action_required = "retry" if retry_available else "stop"
    sequence_hooks["test_report_status"] = "fail"
    if not retry_available:
        state_snapshot["pipeline_status"] = "stopped_retry_exhausted"
    save_state_atomic(state_path, state_snapshot)
    return {
        "status": "fail",
        "guard_result": guard_result,
        "retry_available": retry_available,
        "action_required": action_required,
        "git_instruction": {
            "rollback_command": "git reset --hard <last_stage_commit_sha_or_package_baseline>",
        },
    }


def _build_guard_result(state_snapshot: dict[str, Any], normalized_result: str) -> dict[str, Any]:
    sequence_hooks = state_snapshot.get("sequence_hooks", {})
    semantic_errors: list[dict[str, Any]] = []
    if bool(sequence_hooks.get("guard_stop_conditions_violated", False)):
        guard_details = str(sequence_hooks.get("guard_details", ""))
        semantic_errors.append(
            {
                "code": "STOP_CONDITION_VIOLATED",
                "message": guard_details or "Stop condition violated",
                "file": None,
                "severity": "error",
            }
        )

    mechanical_errors: list[dict[str, Any]] = []
    if normalized_result == "FAIL":
        mechanical_errors.append(
            {
                "code": "TEST_FAILED",
                "message": "Reported test result is FAIL",
                "file": None,
                "severity": "error",
            }
        )

    total_errors = len(mechanical_errors) + len(semantic_errors)
    verdict = "FAIL" if total_errors > 0 else "PASS"
    return {
        "verdict": verdict,
        "mechanical_errors": mechanical_errors,
        "semantic_errors": semantic_errors,
        "total_errors": total_errors,
        "checked_at": _now_iso(),
    }


def _active_stage_id(state_snapshot: dict[str, Any], plan_cache: dict[str, Any]) -> str:
    package_index = int(state_snapshot["cursor"]["package_index"])
    stage_index = int(state_snapshot["cursor"]["stage_index"])
    return str(plan_cache["packages"][package_index]["stages"][stage_index]["stage_id"])


def _wip_commit_command(stage_id: str) -> str:
    return f"git add . && git commit -m 'wip: {stage_id}'"


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