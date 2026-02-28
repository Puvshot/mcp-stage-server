from __future__ import annotations

from pathlib import Path
from typing import Any

from mss.guard.mechanical import core_aggregate_mechanical_errors, core_build_guard_result
from mss.guard.semantic import core_normalize_semantic_report
from mss.storage.plan_cache import runner_load_plan_cache
from mss.storage.state import runner_load_state, runner_save_state_atomic
from mss.tools.collision import analyze as collision_analyze


STATE_FILENAME = "state.json"


def report(
    plan_dir: str,
    stage_id: str,
    stop_conditions_violated: bool,
    details: str,
) -> dict[str, Any]:
    """Record guard.report status for the active stage.

    This tool is idempotent for the same stage_id and payload. It updates sequence
    hooks required by contract enforcement (`guard.report` must happen before
    `test.report`).
    """
    resolved_plan_dir = Path(plan_dir).resolve()
    state_path = resolved_plan_dir / STATE_FILENAME
    if not state_path.exists():
        return _error_response("PLAN_NOT_INITIALIZED", "State is missing")

    state_snapshot = runner_load_state(state_path)
    plan_cache = runner_load_plan_cache(resolved_plan_dir)
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

    if not isinstance(details, str):
        return _error_response("INVALID_GUARD_DETAILS", "details must be a string")

    collision_payload = collision_analyze(plan_dir=str(resolved_plan_dir), stage_id=stage_id)
    if collision_payload.get("status") == "error":
        return collision_payload

    collision_findings = collision_payload.get("findings", [])
    mechanical_errors = core_aggregate_mechanical_errors(
        collision_findings if isinstance(collision_findings, list) else []
    )
    semantic_report = core_normalize_semantic_report(
        {
            "stop_conditions_violated": stop_conditions_violated,
            "details": details,
        }
    )
    guard_result = core_build_guard_result(
        mechanical_errors=mechanical_errors,
        semantic_errors=semantic_report.get("semantic_errors", []),
    )

    sequence_hooks = state_snapshot.setdefault("sequence_hooks", {})
    sequence_hooks["guard_reported"] = True
    sequence_hooks["guard_stop_conditions_violated"] = bool(semantic_report.get("stop_conditions_violated", False))
    sequence_hooks["guard_details"] = str(semantic_report.get("details", ""))
    sequence_hooks["guard_result"] = guard_result
    sequence_hooks["guard_has_blocking_errors"] = bool(
        any(error.get("severity") == "error" for error in mechanical_errors)
    )

    package_index = int(state_snapshot["cursor"]["package_index"])
    stage_index = int(state_snapshot["cursor"]["stage_index"])
    active_stage = plan_cache["packages"][package_index]["stages"][stage_index]
    if guard_result.get("verdict") == "FAIL":
        active_stage["last_error"] = guard_result
    else:
        active_stage["last_error"] = None
    runner_save_state_atomic(state_path, state_snapshot)

    return {
        "received": True,
        "stage_id": stage_id,
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
