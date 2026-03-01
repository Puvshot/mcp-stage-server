from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from mss.engines.artifact_flow_gate import summarize_details_passed
from mss.engines.projects_discovery import (
    compose_message as compose_projects_message,
    discover_projects,
    merge_next_actions,
    project_next_actions,
)
from mss.engines.session_actions_policy import (
    next_actions_for_set_mode,
    next_actions_for_status,
)
from mss.storage.artifact_store import get_artifact as get_stored_artifact
from mss.storage.session_store import (
    create_session,
    get_active_session,
    save_session,
    set_active_session,
)


ALLOWED_MODES = {"audit", "planning", "debug", "workout", "run"}
SESSION_DIR_ENV = "MSS_SESSION_DIR"
PROJECTS_DIR_ENV = "MSS_PROJECTS_DIR"

_CONNECT_MESSAGE = (
    "Połączono. Wyświetl użytkownikowi DOKŁADNIE ten tekst: "
    "'Cześć, jaką operację chcesz wykonać?\\n\\nDostępne funkcje:\\n"
    "- **Debug** (Ścisły protokół do naprawy kodu. Pokaż mi błąd, a ja przeanalizuję "
    "pliki, postawię hipotezę i naprawię usterkę krok po kroku)\\n"
    "- **Workout** (Burza mózgów i planowanie. Porozmawiajmy o architekturze, "
    "rozważmy opcje i zapisujmy ustalenia na bieżąco, bez pisania kodu na ślepo)\\n\\n"
    "Wybór trybu: wpisz `debug` lub `workout` (skróty), albo `mode debug` / `mode workout`.'"
)


def connect() -> dict[str, Any]:
    """Create or resume active MSS session and return deterministic onboarding payload.

    This tool is idempotent for an already active valid session.
    """
    session_dir = _session_dir()
    session_dir.mkdir(parents=True, exist_ok=True)

    active_session = get_active_session(session_dir=session_dir)
    if active_session is None:
        created_session_payload = create_session(
            session_dir=session_dir,
            session_payload={
                "session_id": str(uuid4()),
                "created_at": _now_iso(),
                "mode": None,
                "artifacts": [],
            },
        )
        set_active_session(session_dir=session_dir, session_id=str(created_session_payload["session_id"]))
        active_session = created_session_payload

    project_summaries = discover_projects(_projects_dir())

    return _response(
        ok=True,
        session_id=str(active_session.get("session_id", "")),
        mode=_normalize_mode(active_session.get("mode")),
        message=compose_projects_message(base_message=_CONNECT_MESSAGE, project_summaries=project_summaries),
        artifacts=_normalize_artifacts(active_session.get("artifacts")),
        next_actions=merge_next_actions(_action_connect(), project_next_actions(project_summaries)),
        warnings=[],
    )


def status() -> dict[str, Any]:
    """Return active MSS session state with deterministic next actions.

    This read-only tool is idempotent.
    """
    session_dir = _session_dir()
    active_session = get_active_session(session_dir=session_dir)
    if active_session is None:
        return _response(
            ok=False,
            session_id=None,
            mode=None,
            message="Brak aktywnej sesji. Uruchom `mss.connect`.",
            artifacts=[],
            next_actions=[_action("connect", "Połącz z MSS")],
            warnings=["active_session_not_found"],
        )

    session_id = str(active_session.get("session_id", "")).strip()
    mode = _normalize_mode(active_session.get("mode"))
    artifacts = _normalize_artifacts(active_session.get("artifacts"))
    artifact_names = {str(item.get("name", "")) for item in artifacts if isinstance(item, dict)}
    summarize_details_artifact = None
    if session_id:
        summarize_details_artifact = get_stored_artifact(
            session_dir=_session_dir(),
            session_id=session_id,
            artifact_name="summarize_details",
        )
    summarize_details_pass = summarize_details_passed(summarize_details_artifact)
    include_project_resume_hints = mode not in {"workout", "debug"}

    project_summaries: list[dict[str, Any]] = []
    if include_project_resume_hints:
        project_summaries = discover_projects(_projects_dir())

    session_actions = next_actions_for_status(
        mode=mode,
        artifact_names=artifact_names,
        summarize_details_pass=summarize_details_pass,
    )
    next_actions = session_actions
    if include_project_resume_hints:
        next_actions = merge_next_actions(session_actions, project_next_actions(project_summaries))

    message_text = "Status sesji pobrany."
    if include_project_resume_hints:
        message_text = compose_projects_message(base_message=message_text, project_summaries=project_summaries)

    return _response(
        ok=True,
        session_id=session_id,
        mode=mode,
        message=message_text,
        artifacts=artifacts,
        next_actions=next_actions,
        warnings=[],
    )


def set_mode(mode: str) -> dict[str, Any]:
    """Set active session mode and return deterministic mode-specific next actions.

    This tool is idempotent for repeated calls with the same mode.
    """
    if not isinstance(mode, str):
        return _response(
            ok=False,
            session_id=None,
            mode=None,
            message="Nieprawidłowy parametr `mode`.",
            artifacts=[],
            next_actions=[_action("status", "Sprawdź aktualny stan")],
            warnings=["invalid_mode_type"],
        )

    normalized_mode = mode.strip().lower()
    if normalized_mode not in ALLOWED_MODES:
        return _response(
            ok=False,
            session_id=None,
            mode=None,
            message="Nieobsługiwany tryb. Dozwolone: audit, planning, debug, workout, run.",
            artifacts=[],
            next_actions=[_action("status", "Sprawdź aktualny stan")],
            warnings=["invalid_mode_value"],
        )

    session_dir = _session_dir()
    active_session = get_active_session(session_dir=session_dir)
    if active_session is None:
        return _response(
            ok=False,
            session_id=None,
            mode=None,
            message="Brak aktywnej sesji. Uruchom `mss.connect`.",
            artifacts=[],
            next_actions=[_action("connect", "Połącz z MSS")],
            warnings=["active_session_not_found"],
        )

    active_session["mode"] = normalized_mode
    save_session(session_dir=session_dir, session_payload=active_session)

    artifacts = _normalize_artifacts(active_session.get("artifacts"))
    return _response(
        ok=True,
        session_id=str(active_session.get("session_id", "")),
        mode=normalized_mode,
        message=f"Ustawiono tryb: {normalized_mode}.",
        artifacts=artifacts,
        next_actions=next_actions_for_set_mode(normalized_mode),
        warnings=[],
    )


def _action_connect() -> list[dict[str, str]]:
    return [
        _action("debug", "Skrót: ustawia tryb debug"),
        _action("workout", "Skrót: ustawia tryb workout"),
        _action("mode debug", "Uruchamia tryb debug"),
        _action("mode workout", "Uruchamia tryb workout"),
    ]


def _action(command: str, description: str) -> dict[str, str]:
    return {
        "command": command,
        "description": description,
    }


def _response(
    ok: bool,
    session_id: str | None,
    mode: str | None,
    message: str,
    artifacts: list[dict[str, Any]],
    next_actions: list[dict[str, str]],
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "ok": bool(ok),
        "session_id": session_id,
        "mode": mode,
        "message": message,
        "artifacts": artifacts,
        "next_actions": next_actions,
        "warnings": warnings,
    }


def _session_dir() -> Path:
    env_path = Path(str(Path.cwd() / "data" / "sessions"))
    from os import getenv

    raw_override = getenv(SESSION_DIR_ENV)
    if raw_override:
        env_path = Path(raw_override)
    return env_path.resolve()


def _projects_dir() -> Path:
    projects_path = Path.cwd() / "data" / "projects"
    from os import getenv

    raw_override = getenv(PROJECTS_DIR_ENV)
    if raw_override:
        projects_path = Path(raw_override)
    return projects_path.resolve()


def _normalize_artifacts(raw_artifacts: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_artifacts, list):
        return []
    normalized: list[dict[str, Any]] = []
    for raw_item in raw_artifacts:
        if not isinstance(raw_item, dict):
            continue
        artifact_name = str(raw_item.get("name", "")).strip()
        if not artifact_name:
            continue
        normalized.append(
            {
                "name": artifact_name,
                "version": int(raw_item.get("version", 1)) if str(raw_item.get("version", "")).isdigit() else 1,
            }
        )
    return normalized


def _normalize_mode(raw_mode: Any) -> str | None:
    if raw_mode is None:
        return None
    mode_text = str(raw_mode).strip().lower()
    if mode_text in ALLOWED_MODES:
        return mode_text
    return None


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()