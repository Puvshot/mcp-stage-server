from __future__ import annotations

from pathlib import Path
from typing import Any

from mss.storage.plan_cache import load_plan_cache
from mss.storage.state import load_state


STATE_FILENAME = "state.json"


def _discover_projects(projects_dir: Path) -> list[dict[str, Any]]:
    """Discover project runtimes and return normalized summaries for session tools."""
    if not projects_dir.exists() or not projects_dir.is_dir():
        return []

    discovered: list[dict[str, Any]] = []
    for project_dir in sorted(projects_dir.iterdir(), key=lambda path: path.name.lower()):
        if not project_dir.is_dir():
            continue

        plan_cache_payload = load_plan_cache(project_dir)
        has_plan_cache = plan_cache_payload is not None
        plan_id = project_dir.name
        if isinstance(plan_cache_payload, dict):
            normalized_plan_id = str(plan_cache_payload.get("plan_id", "")).strip()
            if normalized_plan_id:
                plan_id = normalized_plan_id

        state_payload = _load_project_state(project_dir)
        has_state = state_payload is not None
        pipeline_status = ""
        cursor_payload: dict[str, int] | None = None
        if isinstance(state_payload, dict):
            pipeline_status = str(state_payload.get("pipeline_status", "")).strip()
            raw_cursor = state_payload.get("cursor")
            if isinstance(raw_cursor, dict):
                cursor_payload = {
                    "package_index": _to_int(raw_cursor.get("package_index"), 0),
                    "stage_index": _to_int(raw_cursor.get("stage_index"), 0),
                }

        project_status_value = _project_status(
            has_plan_cache=has_plan_cache,
            has_state=has_state,
            pipeline_status=pipeline_status,
        )

        discovered.append(
            {
                "name": project_dir.name,
                "plan_id": plan_id,
                "plan_dir": str(project_dir.resolve()),
                "has_plan_cache": has_plan_cache,
                "has_state": has_state,
                "pipeline_status": pipeline_status,
                "cursor": cursor_payload,
                "status": project_status_value,
            }
        )

    return discovered


def _project_status(has_plan_cache: bool, has_state: bool, pipeline_status: str) -> str:
    """Classify project runtime state for session messaging."""
    normalized_status = pipeline_status.strip().lower()
    if has_state and normalized_status == "complete":
        return "complete"
    if has_state and normalized_status:
        return "in_progress"
    if has_plan_cache:
        return "initialized"
    return "discovered"


def _load_project_state(project_dir: Path) -> dict[str, Any] | None:
    """Load project state payload if available and valid."""
    state_path = project_dir / STATE_FILENAME
    if not state_path.exists():
        return None

    try:
        return load_state(state_path)
    except (OSError, ValueError, TypeError):
        return None


def _compose_message(base_message: str, project_summaries: list[dict[str, Any]]) -> str:
    """Compose base tool message with optional discovered-projects section."""
    projects_section = _projects_message(project_summaries)
    if not projects_section:
        return base_message
    return f"{base_message}\n\n{projects_section}"


def _projects_message(project_summaries: list[dict[str, Any]]) -> str:
    """Build human-readable discovered-projects section."""
    if not project_summaries:
        return ""

    ready_projects = [
        project_summary
        for project_summary in project_summaries
        if str(project_summary.get("status", "")) in {"complete", "initialized"}
    ]
    in_progress_projects = [
        project_summary
        for project_summary in project_summaries
        if str(project_summary.get("status", "")) == "in_progress"
    ]

    lines: list[str] = ["Wykryte projekty w `data/projects`:"]
    if ready_projects:
        lines.append("✅ Gotowe / zainicjalizowane:")
        for ready_project in ready_projects:
            ready_plan_id = str(ready_project.get("plan_id", "")).strip()
            ready_plan_dir = str(ready_project.get("plan_dir", "")).strip()
            ready_status = str(ready_project.get("status", "")).strip()
            lines.append(
                f"- {ready_project.get('name', '')} [{ready_status}] → `plan_load_or_init {ready_plan_id} {ready_plan_dir}`"
            )

    if in_progress_projects:
        lines.append("⏳ W toku / zatrzymane:")
        for in_progress_project in in_progress_projects:
            in_progress_plan_id = str(in_progress_project.get("plan_id", "")).strip()
            in_progress_plan_dir = str(in_progress_project.get("plan_dir", "")).strip()
            pipeline_status = str(in_progress_project.get("pipeline_status", "")).strip() or "unknown"
            cursor_payload = in_progress_project.get("cursor")
            cursor_text = ""
            if isinstance(cursor_payload, dict):
                cursor_text = (
                    f", cursor=package:{cursor_payload.get('package_index', 0)}"
                    f" stage:{cursor_payload.get('stage_index', 0)}"
                )
            lines.append(
                f"- {in_progress_project.get('name', '')} [{pipeline_status}{cursor_text}]"
                f" → `plan_load_or_init {in_progress_plan_id} {in_progress_plan_dir}`"
            )
            if bool(in_progress_project.get("has_state")) and bool(in_progress_project.get("has_plan_cache")):
                lines.append(f"  kontynuacja: `stage_current {in_progress_plan_dir}`")

    return "\n".join(lines)


def _project_next_actions(project_summaries: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Return project-scoped next actions based on discovered summaries."""
    actions: list[dict[str, str]] = []
    for project_summary in project_summaries:
        plan_id = str(project_summary.get("plan_id", "")).strip()
        plan_dir = str(project_summary.get("plan_dir", "")).strip()
        project_name = str(project_summary.get("name", "")).strip() or "projekt"
        if not plan_id or not plan_dir:
            continue

        actions.append(_action(f"plan_load_or_init {plan_id} {plan_dir}", f"Wczytaj projekt: {project_name}"))
        if (
            bool(project_summary.get("has_state"))
            and bool(project_summary.get("has_plan_cache"))
            and str(project_summary.get("status", "")) == "in_progress"
        ):
            actions.append(_action(f"stage_current {plan_dir}", f"Pokaż aktywny etap: {project_name}"))

    return actions


def _merge_next_actions(
    base_actions: list[dict[str, str]],
    additional_actions: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Merge actions preserving order and removing duplicate commands."""
    merged_actions: list[dict[str, str]] = []
    seen_commands: set[str] = set()
    for action_payload in [*base_actions, *additional_actions]:
        action_command = str(action_payload.get("command", "")).strip()
        if not action_command or action_command in seen_commands:
            continue
        seen_commands.add(action_command)
        merged_actions.append(action_payload)
    return merged_actions


def _action(command: str, description: str) -> dict[str, str]:
    """Build one action entry for next_actions payload."""
    return {
        "command": command,
        "description": description,
    }


def _to_int(raw_value: Any, default_value: int) -> int:
    """Convert value to int with deterministic fallback."""
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return default_value


def discover_projects(projects_dir: Path) -> list[dict[str, Any]]:
    """Public adapter for project discovery summaries."""
    return _discover_projects(projects_dir)


def project_status(has_plan_cache: bool, has_state: bool, pipeline_status: str) -> str:
    """Public adapter for project status classification."""
    return _project_status(has_plan_cache=has_plan_cache, has_state=has_state, pipeline_status=pipeline_status)


def load_project_state(project_dir: Path) -> dict[str, Any] | None:
    """Public adapter for loading project runtime state."""
    return _load_project_state(project_dir)


def compose_message(base_message: str, project_summaries: list[dict[str, Any]]) -> str:
    """Public adapter for project-aware message composition."""
    return _compose_message(base_message=base_message, project_summaries=project_summaries)


def projects_message(project_summaries: list[dict[str, Any]]) -> str:
    """Public adapter for project summary rendering."""
    return _projects_message(project_summaries)


def project_next_actions(project_summaries: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Public adapter for project-scoped next actions."""
    return _project_next_actions(project_summaries)


def merge_next_actions(
    base_actions: list[dict[str, str]],
    additional_actions: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Public adapter for ordered and deduplicated next actions merge."""
    return _merge_next_actions(base_actions=base_actions, additional_actions=additional_actions)
