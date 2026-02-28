from __future__ import annotations

from pathlib import Path
from typing import Any

from mss.storage.plan_cache import runner_load_plan_cache


def analyze(plan_dir: str, stage_id: str) -> dict[str, Any]:
    """Analyze deterministic file-collision risks for one stage.

    This read-only tool is idempotent. It compares `files_in_scope` from the
    requested stage against files declared by sibling stages and other packages.
    """
    resolved_plan_dir = Path(plan_dir).resolve()
    if not isinstance(stage_id, str) or not stage_id.strip():
        return _error_response("INVALID_STAGE_ID", "stage_id must be a non-empty string")

    plan_cache = runner_load_plan_cache(resolved_plan_dir)
    if plan_cache is None:
        return _error_response("PLAN_NOT_INITIALIZED", "Plan cache is missing")

    stage_context = _find_stage_context(plan_cache, stage_id)
    if stage_context is None:
        return _error_response("STAGE_NOT_FOUND", f"Stage not found: {stage_id}")

    package_snapshot, stage_snapshot = stage_context
    current_files = _normalize_files(stage_snapshot.get("files_in_scope", []))

    stage_overlap_warnings: list[dict[str, Any]] = []
    for sibling_stage in package_snapshot.get("stages", []):
        sibling_stage_id = str(sibling_stage.get("stage_id", ""))
        if sibling_stage_id == stage_id:
            continue

        sibling_files = _normalize_files(sibling_stage.get("files_in_scope", []))
        overlapping_files = sorted(current_files.intersection(sibling_files))
        if not overlapping_files:
            continue

        for file_path in overlapping_files:
            stage_overlap_warnings.append(
                {
                    "code": "FILE_COLLISION_WITHIN_PACKAGE",
                    "message": f"File overlaps with sibling stage: {sibling_stage_id}",
                    "file": file_path,
                    "severity": "warning",
                    "related_stage_id": sibling_stage_id,
                }
            )

    package_id = str(package_snapshot.get("package_id", "PACKAGE_UNKNOWN"))
    cross_package_errors = _build_cross_package_errors(plan_cache, package_id, current_files)

    all_findings = sorted(
        stage_overlap_warnings + cross_package_errors,
        key=lambda finding: (
            str(finding.get("severity", "")),
            str(finding.get("file", "")),
            str(finding.get("code", "")),
            str(finding.get("related_package_id", "")),
            str(finding.get("related_stage_id", "")),
        ),
    )
    blocking_count = sum(1 for finding in all_findings if finding.get("severity") == "error")

    return {
        "status": "ok",
        "stage_id": stage_id,
        "package_id": package_id,
        "findings": all_findings,
        "summary": {
            "files_in_scope": sorted(current_files),
            "findings_total": len(all_findings),
            "blocking_count": blocking_count,
        },
    }


def _find_stage_context(plan_cache: dict[str, Any], stage_id: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
    for package_snapshot in plan_cache.get("packages", []):
        if not isinstance(package_snapshot, dict):
            continue
        for stage_snapshot in package_snapshot.get("stages", []):
            if not isinstance(stage_snapshot, dict):
                continue
            if str(stage_snapshot.get("stage_id", "")) == stage_id:
                return package_snapshot, stage_snapshot
    return None


def _build_cross_package_errors(
    plan_cache: dict[str, Any],
    current_package_id: str,
    current_files: set[str],
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    if not current_files:
        return errors

    for package_snapshot in plan_cache.get("packages", []):
        if not isinstance(package_snapshot, dict):
            continue
        package_id = str(package_snapshot.get("package_id", ""))
        if package_id == current_package_id:
            continue

        declared_files: set[str] = set()
        for file_entry in package_snapshot.get("files_to_modify", []):
            if isinstance(file_entry, dict):
                declared_path = str(file_entry.get("path", "")).strip()
                if declared_path:
                    declared_files.add(declared_path)

        overlapping_files = sorted(current_files.intersection(declared_files))
        for file_path in overlapping_files:
            errors.append(
                {
                    "code": "FILE_NOT_IN_SCOPE_CRITICAL",
                    "message": f"File belongs to another package scope: {package_id}",
                    "file": file_path,
                    "severity": "error",
                    "related_package_id": package_id,
                }
            )

    return errors


def _normalize_files(raw_files: Any) -> set[str]:
    if not isinstance(raw_files, list):
        return set()
    normalized_files: set[str] = set()
    for raw_file in raw_files:
        normalized_file = str(raw_file).strip()
        if normalized_file:
            normalized_files.add(normalized_file)
    return normalized_files


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
