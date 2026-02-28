from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any


PLAN_CACHE_FILENAME = "plan_cache.json"


def runner_get_plan_cache_path(plan_dir: str | Path) -> Path:
    """Return normalized path to `plan_cache.json` for a given plan directory."""
    resolved_plan_dir = Path(plan_dir).resolve()
    return resolved_plan_dir / PLAN_CACHE_FILENAME


def runner_load_plan_cache(plan_dir: str | Path) -> dict[str, Any] | None:
    """Load plan cache if it exists, otherwise return None."""
    plan_cache_path = runner_get_plan_cache_path(plan_dir)
    if not plan_cache_path.exists():
        return None

    with plan_cache_path.open("r", encoding="utf-8") as plan_cache_file:
        loaded_cache: dict[str, Any] = json.load(plan_cache_file)
    return core_normalize_plan_cache(loaded_cache)


def runner_save_plan_cache_atomic(plan_dir: str | Path, plan_cache: dict[str, Any]) -> None:
    """Persist plan cache JSON atomically using tmp file + os.replace()."""
    plan_cache_path = runner_get_plan_cache_path(plan_dir)
    plan_cache_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_cache_path = plan_cache_path.with_suffix(f"{plan_cache_path.suffix}.tmp")

    cache_payload = core_normalize_plan_cache(deepcopy(plan_cache))

    with tmp_cache_path.open("w", encoding="utf-8") as tmp_cache_file:
        json.dump(cache_payload, tmp_cache_file, ensure_ascii=False, indent=2)
        tmp_cache_file.flush()
        os.fsync(tmp_cache_file.fileno())

    os.replace(tmp_cache_path, plan_cache_path)


def core_normalize_plan_cache(plan_cache: dict[str, Any]) -> dict[str, Any]:
    normalized_cache = deepcopy(plan_cache)

    normalized_cache.setdefault("plan_id", "")
    normalized_cache.setdefault("plan_name", "UNKNOWN: plan name not found")
    normalized_cache.setdefault("created_at", "")
    normalized_cache.setdefault("source_format", "markdown")
    normalized_cache.setdefault("goal", "UNKNOWN: section not found")
    normalized_cache.setdefault("scope", [])
    normalized_cache.setdefault("out_of_scope", [])
    normalized_cache.setdefault("constraints", [])
    normalized_cache.setdefault("stop_conditions", [])
    normalized_cache.setdefault("risks", [])
    normalized_cache.setdefault("rules_hash", "")
    normalized_cache.setdefault("plan_hash", "")

    raw_packages = normalized_cache.get("packages")
    packages = raw_packages if isinstance(raw_packages, list) else []

    normalized_packages: list[dict[str, Any]] = []
    for package_entry in packages:
        if not isinstance(package_entry, dict):
            continue
        normalized_packages.append(_normalize_package_entry(package_entry))

    normalized_cache["packages"] = normalized_packages
    normalized_cache["stages_total"] = sum(len(package["stages"]) for package in normalized_packages)
    return normalized_cache


def _normalize_package_entry(package_entry: dict[str, Any]) -> dict[str, Any]:
    normalized_package = deepcopy(package_entry)

    normalized_package.setdefault("package_id", "PACKAGE_UNKNOWN")
    normalized_package.setdefault("package_name", "UNKNOWN: package name not found")
    normalized_package.setdefault("depends_on", [])
    normalized_package.setdefault("goal", "UNKNOWN: section not found")
    normalized_package.setdefault("files_to_modify", [])
    normalized_package.setdefault("verification_commands", [])
    normalized_package.setdefault("status", "pending")
    normalized_package.setdefault("completed_at", None)

    normalized_package["files_to_modify"] = _normalize_file_entries(normalized_package.get("files_to_modify"))

    raw_stages = normalized_package.get("stages")
    stages = raw_stages if isinstance(raw_stages, list) else []
    normalized_stages: list[dict[str, Any]] = []
    for stage_entry in stages:
        if not isinstance(stage_entry, dict):
            continue
        normalized_stages.append(_normalize_stage_entry(stage_entry, str(normalized_package["package_id"])))

    normalized_package["stages"] = normalized_stages
    return normalized_package


def _normalize_file_entries(raw_file_entries: Any) -> list[dict[str, Any]]:
    file_entries = raw_file_entries if isinstance(raw_file_entries, list) else []
    normalized_entries: list[dict[str, Any]] = []
    for file_entry in file_entries:
        if not isinstance(file_entry, dict):
            continue
        normalized_entry = deepcopy(file_entry)
        normalized_entry.setdefault("path", "")
        normalized_entry.setdefault("action", "UNKNOWN")
        normalized_entry.setdefault("is_smoke_test", False)
        normalized_entry.setdefault("unknown", None)
        normalized_entries.append(normalized_entry)
    return normalized_entries


def _normalize_stage_entry(stage_entry: dict[str, Any], package_id: str) -> dict[str, Any]:
    normalized_stage = deepcopy(stage_entry)

    stage_number = _to_int(normalized_stage.get("stage_number"), 0)
    normalized_stage["stage_number"] = stage_number
    normalized_stage.setdefault("stage_name", "UNKNOWN: stage name not found")
    normalized_stage.setdefault("stage_id", f"{package_id}_STAGE_{stage_number}")
    normalized_stage.setdefault("test_command", None)
    normalized_stage.setdefault("dominant_actions", [])
    normalized_stage.setdefault("files_in_scope", [])
    normalized_stage.setdefault("status", "pending")
    normalized_stage["retry_count"] = _to_int(normalized_stage.get("retry_count"), 0)
    normalized_stage.setdefault("last_error", None)

    raw_steps = normalized_stage.get("steps")
    steps = raw_steps if isinstance(raw_steps, list) else []
    normalized_steps: list[dict[str, Any]] = []
    for step_entry in steps:
        if not isinstance(step_entry, dict):
            continue
        normalized_step = deepcopy(step_entry)
        normalized_step["number"] = _to_int(normalized_step.get("number"), 0)
        normalized_step.setdefault("action", "UNKNOWN")
        normalized_step.setdefault("target", "")
        normalized_step.setdefault("raw", "")
        normalized_steps.append(normalized_step)

    normalized_stage["steps"] = normalized_steps
    return normalized_stage


def _to_int(raw_value: Any, default_value: int) -> int:
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return default_value


def get_plan_cache_path(plan_dir: str | Path) -> Path:
    """Backward-compatible wrapper for runner plan-cache path resolution."""
    return runner_get_plan_cache_path(plan_dir)


def load_plan_cache(plan_dir: str | Path) -> dict[str, Any] | None:
    """Backward-compatible wrapper for runner plan-cache loading."""
    return runner_load_plan_cache(plan_dir)


def save_plan_cache_atomic(plan_dir: str | Path, plan_cache: dict[str, Any]) -> None:
    """Backward-compatible wrapper for runner plan-cache persistence."""
    runner_save_plan_cache_atomic(plan_dir, plan_cache)