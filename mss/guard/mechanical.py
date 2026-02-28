from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any


def build_guard_error(
    code: str,
    message: str,
    file_path: str | None,
    severity: str,
) -> dict[str, Any]:
    """Build a single mechanical guard error entry.

    This helper is deterministic and idempotent. It performs lightweight
    normalization so callers can safely aggregate error payloads.
    """
    normalized_severity = severity if severity in {"error", "warning"} else "error"
    normalized_file_path = file_path if isinstance(file_path, str) and file_path else None
    return {
        "code": str(code),
        "message": str(message),
        "file": normalized_file_path,
        "severity": normalized_severity,
    }


def core_build_guard_error(
    code: str,
    message: str,
    file_path: str | None,
    severity: str,
) -> dict[str, Any]:
    """Core alias for deterministic guard error construction."""
    return build_guard_error(code=code, message=message, file_path=file_path, severity=severity)


def aggregate_mechanical_errors(raw_errors: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Normalize and aggregate mechanical guard errors.

    This function preserves input order and returns a fresh list so callers can
    reuse source payloads safely across retries.
    """
    if not isinstance(raw_errors, list):
        return []

    normalized_errors: list[dict[str, Any]] = []
    for raw_error in raw_errors:
        if not isinstance(raw_error, dict):
            continue
        normalized_errors.append(
            core_build_guard_error(
                code=str(raw_error.get("code", "UNKNOWN_MECHANICAL_ERROR")),
                message=str(raw_error.get("message", "")),
                file_path=_as_optional_text(raw_error.get("file")),
                severity=str(raw_error.get("severity", "error")),
            )
        )
    return normalized_errors


def core_aggregate_mechanical_errors(raw_errors: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Core alias for mechanical guard aggregation."""
    return aggregate_mechanical_errors(raw_errors)


def build_guard_result(
    mechanical_errors: list[dict[str, Any]] | None,
    semantic_errors: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Build a GuardResult-compatible structure from mechanical and semantic errors."""
    normalized_mechanical_errors = core_aggregate_mechanical_errors(mechanical_errors)
    normalized_semantic_errors = core_aggregate_mechanical_errors(semantic_errors)

    has_blocking_error = any(error.get("severity") == "error" for error in normalized_mechanical_errors)
    has_semantic_error = any(error.get("severity") == "error" for error in normalized_semantic_errors)
    guard_verdict = "FAIL" if has_blocking_error or has_semantic_error else "PASS"

    return {
        "verdict": guard_verdict,
        "mechanical_errors": deepcopy(normalized_mechanical_errors),
        "semantic_errors": deepcopy(normalized_semantic_errors),
        "total_errors": len(normalized_mechanical_errors) + len(normalized_semantic_errors),
        "checked_at": datetime.now(UTC).isoformat(),
    }


def core_build_guard_result(
    mechanical_errors: list[dict[str, Any]] | None,
    semantic_errors: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Core alias for guard result assembly."""
    return build_guard_result(mechanical_errors=mechanical_errors, semantic_errors=semantic_errors)


def _as_optional_text(raw_value: Any) -> str | None:
    if isinstance(raw_value, str) and raw_value:
        return raw_value
    return None
