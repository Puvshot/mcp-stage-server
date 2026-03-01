from __future__ import annotations

from pathlib import Path
from typing import Any


PENDING_SUBDIR = "_pending"


def _discover_mss_sessions(sessions_dir: Path) -> list[dict[str, Any]]:
    """Scan data/sessions/ and classify each project folder by MSS phase.

    Skips _pending/ and top-level files. Returns one summary per project folder.
    """
    if not sessions_dir.exists() or not sessions_dir.is_dir():
        return []

    summaries: list[dict[str, Any]] = []
    for entry in sorted(sessions_dir.iterdir(), key=lambda p: p.name.lower()):
        if not entry.is_dir():
            continue
        if entry.name == PENDING_SUBDIR:
            continue

        next_phase = _next_mss_phase(entry)
        summaries.append(
            {
                "name": entry.name,
                "session_dir": str(entry.resolve()),
                "next_phase": next_phase,
            }
        )

    return summaries


def _next_mss_phase(project_dir: Path) -> str:
    """Determine the next required MSS phase based on existing subfolders."""
    subfolders = {p.name for p in project_dir.iterdir() if p.is_dir()}
    if "audit" not in subfolders:
        return "needs_audit"
    if "prepare" not in subfolders:
        return "needs_prepare"
    if "planning" not in subfolders:
        return "needs_planning"
    if "run" not in subfolders:
        return "needs_run"
    return "done"


def _compose_mss_message(base_message: str, session_summaries: list[dict[str, Any]]) -> str:
    """Compose base message with optional MSS sessions section."""
    sessions_section = _sessions_section(session_summaries)
    if not sessions_section:
        return base_message
    return f"{base_message}\n\n{sessions_section}"


def _sessions_section(session_summaries: list[dict[str, Any]]) -> str:
    """Build human-readable MSS session status section."""
    if not session_summaries:
        return ""

    lines = ["Wykryte projekty MSS w `data/sessions`:"]
    for summary in session_summaries:
        name = str(summary.get("name", "")).strip()
        phase = str(summary.get("next_phase", "")).strip()
        lines.append(f"- {name} → {phase}")

    return "\n".join(lines)


def _mss_session_next_actions(session_summaries: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Return set_mode actions for projects that need a specific phase."""
    _PHASE_TO_MODE: dict[str, str] = {
        "needs_audit": "audit",
        "needs_prepare": "planning",
        "needs_planning": "planning",
        "needs_run": "run",
    }
    actions: list[dict[str, str]] = []
    for summary in session_summaries:
        name = str(summary.get("name", "")).strip()
        phase = str(summary.get("next_phase", "")).strip()
        mode = _PHASE_TO_MODE.get(phase)
        if name and mode:
            actions.append(
                _action(
                    f"set_mode {mode} {name}",
                    f"Wznów projekt {name} (faza: {phase})",
                )
            )
    return actions


def _action(command: str, description: str) -> dict[str, str]:
    return {"command": command, "description": description}


# Public adapters

def discover_mss_sessions(sessions_dir: Path) -> list[dict[str, Any]]:
    """Public adapter: discover MSS project sessions and their next phases."""
    return _discover_mss_sessions(sessions_dir)


def compose_mss_message(base_message: str, session_summaries: list[dict[str, Any]]) -> str:
    """Public adapter: compose message with MSS session status section."""
    return _compose_mss_message(base_message=base_message, session_summaries=session_summaries)


def mss_session_next_actions(session_summaries: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Public adapter: return next_actions based on discovered session phases."""
    return _mss_session_next_actions(session_summaries)
