from __future__ import annotations

from pathlib import Path
from typing import Any


AUDIT_LOG_FILENAME = "mcp_audit.log"


def tail(plan_dir: str, last_n: int = 50) -> dict[str, Any]:
    """Return last N audit log lines from `mcp_audit.log`.

    This read-only tool is idempotent.
    """
    resolved_plan_dir = Path(plan_dir).resolve()

    if not isinstance(last_n, int) or last_n <= 0:
        return _error_response("INVALID_LAST_N", "last_n must be a positive integer")

    audit_log_path = resolved_plan_dir / AUDIT_LOG_FILENAME
    if not audit_log_path.exists():
        return {
            "status": "ok",
            "entries": [],
            "count": 0,
        }

    with audit_log_path.open("r", encoding="utf-8") as audit_log_file:
        lines = [line.rstrip("\n") for line in audit_log_file.readlines()]

    selected_lines = lines[-last_n:]
    return {
        "status": "ok",
        "entries": selected_lines,
        "count": len(selected_lines),
    }


def clear(plan_dir: str) -> dict[str, Any]:
    """Clear `mcp_audit.log` content for a plan runtime directory.

    This tool is side-effecting and idempotent.
    """
    resolved_plan_dir = Path(plan_dir).resolve()
    audit_log_path = resolved_plan_dir / AUDIT_LOG_FILENAME
    resolved_plan_dir.mkdir(parents=True, exist_ok=True)

    removed_entries = 0
    if audit_log_path.exists():
        with audit_log_path.open("r", encoding="utf-8") as audit_log_file:
            removed_entries = sum(1 for _ in audit_log_file)

    audit_log_path.write_text("", encoding="utf-8")
    return {
        "status": "cleared",
        "removed_entries": removed_entries,
    }


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