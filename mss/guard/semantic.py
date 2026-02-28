from __future__ import annotations

from copy import deepcopy
from typing import Any


def normalize_semantic_report(raw_report: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize raw semantic guard payload from client-facing reporting flow.

    This function is idempotent and tolerant to partial input. It guarantees
    stable keys for downstream guard aggregation.
    """
    if not isinstance(raw_report, dict):
        return {
            "stop_conditions_violated": False,
            "details": "",
            "semantic_errors": [],
        }

    stop_conditions_violated = bool(raw_report.get("stop_conditions_violated", False))
    details = _as_text(raw_report.get("details"))
    semantic_errors = _normalize_semantic_errors(raw_report.get("semantic_errors"))

    if stop_conditions_violated and not semantic_errors:
        semantic_errors.append(
            {
                "code": "STOP_CONDITION_VIOLATED",
                "message": details or "Stop condition violated",
                "file": None,
                "severity": "error",
            }
        )

    return {
        "stop_conditions_violated": stop_conditions_violated,
        "details": details,
        "semantic_errors": deepcopy(semantic_errors),
    }


def core_normalize_semantic_report(raw_report: dict[str, Any] | None) -> dict[str, Any]:
    """Core alias for semantic report normalization."""
    return normalize_semantic_report(raw_report)


def _normalize_semantic_errors(raw_semantic_errors: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_semantic_errors, list):
        return []

    normalized_errors: list[dict[str, Any]] = []
    for raw_semantic_error in raw_semantic_errors:
        if not isinstance(raw_semantic_error, dict):
            continue

        normalized_errors.append(
            {
                "code": str(raw_semantic_error.get("code", "STOP_CONDITION_VIOLATED")),
                "message": _as_text(raw_semantic_error.get("message")),
                "file": _as_optional_text(raw_semantic_error.get("file")),
                "severity": _normalize_severity(raw_semantic_error.get("severity")),
            }
        )

    return normalized_errors


def _normalize_severity(raw_severity: Any) -> str:
    if raw_severity == "warning":
        return "warning"
    return "error"


def _as_text(raw_value: Any) -> str:
    if isinstance(raw_value, str):
        return raw_value
    return ""


def _as_optional_text(raw_value: Any) -> str | None:
    if isinstance(raw_value, str) and raw_value:
        return raw_value
    return None
