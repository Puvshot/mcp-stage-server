from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def create_initial_state(
    plan_id: str,
    rules_hash: str,
    plan_hash: str,
    max_retries: int = 2,
) -> dict[str, Any]:
    """Create an initial StateSnapshot-compatible dictionary for MVP usage."""
    return core_create_initial_state(
        plan_id=plan_id,
        rules_hash=rules_hash,
        plan_hash=plan_hash,
        max_retries=max_retries,
    )


def core_create_initial_state(
    plan_id: str,
    rules_hash: str,
    plan_hash: str,
    max_retries: int = 2,
) -> dict[str, Any]:
    """Core: build initial state snapshot payload without filesystem I/O."""
    now_iso = _now_iso()
    return core_normalize_state_snapshot(
        {
            "plan_id": plan_id,
            "rules_hash": rules_hash,
            "plan_hash": plan_hash,
            "cursor": {"package_index": 0, "stage_index": 0},
            "retry_count": 0,
            "max_retries": max_retries,
            "git": {
                "commit_mode": "wip_squash",
                "package_baseline_sha": None,
                "last_stage_commit_sha": None,
            },
            "pipeline_status": "initializing",
            "created_at": now_iso,
            "last_updated_at": now_iso,
        }
    )


def runner_load_state(state_path: str | Path) -> dict[str, Any]:
    """Load state JSON from disk."""
    path_obj = Path(state_path)
    with path_obj.open("r", encoding="utf-8") as state_file:
        loaded_state: dict[str, Any] = json.load(state_file)
    return core_normalize_state_snapshot(loaded_state)


def runner_save_state_atomic(state_path: str | Path, state_snapshot: dict[str, Any]) -> None:
    """Persist state JSON atomically using tmp file + os.replace()."""
    path_obj = Path(state_path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path_obj.with_suffix(f"{path_obj.suffix}.tmp")

    state_payload = core_normalize_state_snapshot(deepcopy(state_snapshot))
    state_payload["last_updated_at"] = _now_iso()

    with tmp_path.open("w", encoding="utf-8") as tmp_file:
        json.dump(state_payload, tmp_file, ensure_ascii=False, indent=2)
        tmp_file.flush()
        os.fsync(tmp_file.fileno())

    os.replace(tmp_path, path_obj)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def core_normalize_state_snapshot(state_snapshot: dict[str, Any]) -> dict[str, Any]:
    normalized_state = deepcopy(state_snapshot)
    current_time = _now_iso()

    normalized_state.setdefault("plan_id", "")
    normalized_state.setdefault("rules_hash", "")
    normalized_state.setdefault("plan_hash", "")

    cursor_snapshot = normalized_state.get("cursor")
    if not isinstance(cursor_snapshot, dict):
        cursor_snapshot = {}
    normalized_state["cursor"] = {
        "package_index": _to_int(cursor_snapshot.get("package_index"), 0),
        "stage_index": _to_int(cursor_snapshot.get("stage_index"), 0),
    }

    normalized_state["retry_count"] = _to_int(normalized_state.get("retry_count"), 0)
    normalized_state["max_retries"] = _to_int(normalized_state.get("max_retries"), 2)

    git_snapshot = normalized_state.get("git")
    if not isinstance(git_snapshot, dict):
        git_snapshot = {}
    normalized_state["git"] = {
        "commit_mode": str(git_snapshot.get("commit_mode", "wip_squash")),
        "package_baseline_sha": git_snapshot.get("package_baseline_sha"),
        "last_stage_commit_sha": git_snapshot.get("last_stage_commit_sha"),
    }

    normalized_state["pipeline_status"] = str(normalized_state.get("pipeline_status", "initializing"))
    normalized_state.setdefault("sequence_hooks", {"guard_reported": False, "test_report_status": None})
    normalized_state.setdefault("created_at", current_time)
    normalized_state.setdefault("last_updated_at", current_time)
    return normalized_state


def _to_int(raw_value: Any, default_value: int) -> int:
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return default_value


def load_state(state_path: str | Path) -> dict[str, Any]:
    """Backward-compatible wrapper for runner state loading."""
    return runner_load_state(state_path)


def save_state_atomic(state_path: str | Path, state_snapshot: dict[str, Any]) -> None:
    """Backward-compatible wrapper for runner state persistence."""
    runner_save_state_atomic(state_path, state_snapshot)
