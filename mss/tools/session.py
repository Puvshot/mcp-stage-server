from __future__ import annotations

import shutil
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
    PENDING_SUBDIR,
    create_session,
    get_active_session,
    save_session,
    set_active_session,
)


ALLOWED_MODES = {"audit", "planning", "debug", "workout", "run"}
SESSION_DIR_ENV = "MSS_SESSION_DIR"
PROJECTS_DIR_ENV = "MSS_PROJECTS_DIR"

# Fix A: message hint o project_name dodany na końcu
_CONNECT_MESSAGE = (
    "Połączono. Wyświetl użytkownikowi DOKŁADNIE ten tekst: "
    "'Cześć, jaką operację chcesz wykonać?\\n\\nDostępne funkcje:\\n"
    "- **Debug** (Ścisły protokół do naprawy kodu. Pokaż mi błąd, a ja przeanalizuję "
    "pliki, postawię hipotezę i naprawię usterkę krok po kroku)\\n"
    "- **Workout** (Burza mózgów i planowanie. Porozmawiajmy o architekturze, "
    "rozważmy opcje i zapisujmy ustalenia na bieżąco, bez pisania kodu na ślepo)\\n\\n"
    "Wybór trybu: wpisz `debug` lub `workout` (skróty), albo `mode debug` / `mode workout`.\\n\\n"
    "Wybierając tryb pamiętaj żeby podać nazwę projektu.'"
)


def connect() -> dict[str, Any]:
    """Create or resume active MSS session and return deterministic onboarding payload.

    This tool is idempotent for an already active valid session.
    New sessions start in _pending/ subdirectory until set_mode is called.
    """
    session_dir = _session_dir()
    session_dir.mkdir(parents=True, exist_ok=True)

    active_session = get_active_session(session_dir=session_dir)
    if active_session is None:
        # Nowa sesja zawsze startuje w _pending/
        created_session_payload = create_session(
            session_dir=session_dir,
            session_payload={
                "session_id": str(uuid4()),
                "created_at": _now_iso(),
                "mode": None,
                "artifacts": [],
                "project_name": None,
            },
        )
        session_id = str(created_session_payload["session_id"])
        set_active_session(session_dir=session_dir, session_id=session_id, project_name=None)
        active_session = created_session_payload

    project_summaries = discover_projects(_projects_dir())

    return _response(
        ok=True,
        session_id=str(active_session.get("session_id", "")),
        mode=_normalize_mode(active_session.get("mode")),
        project_name=active_session.get("project_name"),
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
            project_name=None,
            message="Brak aktywnej sesji. Uruchom `mss.connect`.",
            artifacts=[],
            next_actions=[_action("connect", "Połącz z MSS")],
            warnings=["active_session_not_found"],
        )

    session_id = str(active_session.get("session_id", "")).strip()
    mode = _normalize_mode(active_session.get("mode"))
    project_name = active_session.get("project_name")
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

    # Fix B: dynamiczny message z trybem i listą artefaktów
    artifact_list = ", ".join(a["name"] for a in artifacts) if artifacts else "brak"
    mode_label = mode if mode else "nie ustawiono"
    message_text = f"Stan sesji: tryb {mode_label}. Artefakty ({len(artifacts)}): {artifact_list}."
    if include_project_resume_hints:
        message_text = compose_projects_message(base_message=message_text, project_summaries=project_summaries)

    return _response(
        ok=True,
        session_id=session_id,
        mode=mode,
        project_name=project_name,
        message=message_text,
        artifacts=artifacts,
        next_actions=next_actions,
        warnings=[],
    )


def set_mode(mode: str, project_name: str | None = None) -> dict[str, Any]:
    """Set active session mode and return deterministic mode-specific next actions.

    For mode='workout' or mode='debug', project_name is required.
    If not provided, returns an error.
    Migrates session from _pending/ to <project_name>/ on first mode set.
    This tool is idempotent for repeated calls with the same mode and project_name.
    """
    if not isinstance(mode, str):
        return _response(
            ok=False,
            session_id=None,
            mode=None,
            project_name=None,
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
            project_name=None,
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
            project_name=None,
            message="Brak aktywnej sesji. Uruchom `mss.connect`.",
            artifacts=[],
            next_actions=[_action("connect", "Połącz z MSS")],
            warnings=["active_session_not_found"],
        )

    # project_name wymagany dla workout i debug
    if normalized_mode in {"workout", "debug"}:
        normalized_project_name = str(project_name).strip() if project_name else ""
        if not normalized_project_name:
            return _response(
                ok=False,
                session_id=None,
                mode=None,
                project_name=None,
                message="Podaj nazwę projektu (project_name) przed rozpoczęciem trybu.",
                artifacts=[],
                next_actions=[_action("status", "Sprawdź aktualny stan")],
                warnings=["project_name_required"],
            )

        # Migracja _pending/ → <project_name>/ jeśli sesja jeszcze bez projektu
        current_project = active_session.get("project_name")
        if not current_project:
            migrate_warnings = _migrate_pending(session_dir, normalized_project_name)
            if migrate_warnings:
                return _response(
                    ok=False,
                    session_id=None,
                    mode=None,
                    project_name=None,
                    message="Błąd migracji sesji z _pending/ do folderu projektu.",
                    artifacts=[],
                    next_actions=[_action("status", "Sprawdź aktualny stan")],
                    warnings=migrate_warnings,
                )
        active_session["project_name"] = normalized_project_name
        set_active_session(
            session_dir=session_dir,
            session_id=str(active_session["session_id"]),
            project_name=normalized_project_name,
        )

    active_session["mode"] = normalized_mode
    save_session(session_dir=session_dir, session_payload=active_session)

    artifacts = _normalize_artifacts(active_session.get("artifacts"))
    return _response(
        ok=True,
        session_id=str(active_session.get("session_id", "")),
        mode=normalized_mode,
        project_name=active_session.get("project_name"),
        message=f"Ustawiono tryb: {normalized_mode}.",
        artifacts=artifacts,
        next_actions=next_actions_for_set_mode(normalized_mode),
        warnings=[],
    )


def new_session() -> dict[str, Any]:
    """Create a new MSS session and set it as active, archiving the current one.

    The previous session is preserved on disk but is no longer active.
    New session starts in _pending/ until set_mode is called.
    This tool is idempotent — always returns the newly created session.
    """
    session_dir = _session_dir()
    session_dir.mkdir(parents=True, exist_ok=True)
    created = create_session(
        session_dir=session_dir,
        session_payload={
            "session_id": str(uuid4()),
            "created_at": _now_iso(),
            "mode": None,
            "artifacts": [],
            "project_name": None,
        },
    )
    set_active_session(session_dir=session_dir, session_id=str(created["session_id"]), project_name=None)
    return _response(
        ok=True,
        session_id=str(created["session_id"]),
        mode=None,
        project_name=None,
        message="Nowa sesja utworzona. Poprzednia sesja zachowana, nie jest już aktywna.",
        artifacts=[],
        next_actions=[
            _action("mode debug", "Uruchamia tryb debug"),
            _action("mode workout", "Uruchamia tryb workout"),
        ],
        warnings=[],
    )


def _action_connect() -> list[dict[str, str]]:
    return [
        _action("debug", "Skrót: ustawia tryb debug"),
        _action("workout", "Skrót: ustawia tryb workout"),
        _action("mode debug", "Uruchamia tryb debug"),
        _action("mode workout", "Uruchamia tryb workout"),
    ]


def _migrate_pending(session_dir: Path, project_name: str) -> list[str]:
    """Move _pending/ subdirectory contents to <project_name>/ and remove _pending/.

    Returns list of warning strings on failure, empty list on success.
    """
    pending_dir = session_dir / PENDING_SUBDIR
    target_dir = session_dir / project_name
    if not pending_dir.exists():
        return []
    try:
        if target_dir.exists():
            # Merge: przenieś każdy plik z _pending/ do target_dir
            for item in pending_dir.iterdir():
                dest = target_dir / item.name
                if not dest.exists():
                    shutil.move(str(item), str(dest))
        else:
            shutil.move(str(pending_dir), str(target_dir))
        # Usuń _pending/ jeśli jeszcze istnieje
        if pending_dir.exists():
            shutil.rmtree(str(pending_dir))
    except OSError as exc:
        return [f"pending_migration_failed: {exc}"]
    return []


def _action(command: str, description: str) -> dict[str, str]:
    return {
        "command": command,
        "description": description,
    }


def _response(
    ok: bool,
    session_id: str | None,
    mode: str | None,
    project_name: str | None,
    message: str,
    artifacts: list[dict[str, Any]],
    next_actions: list[dict[str, str]],
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "ok": bool(ok),
        "session_id": session_id,
        "mode": mode,
        "project_name": project_name,
        "message": message,
        "artifacts": artifacts,
        "next_actions": next_actions,
        "warnings": warnings,
    }


def _session_dir() -> Path:
    from os import getenv
    # Fix E: kotwicza ścieżkę do repo root, nie do CWD procesu
    env_path = Path(__file__).resolve().parents[2] / "data" / "sessions"
    raw_override = getenv(SESSION_DIR_ENV)
    if raw_override:
        env_path = Path(raw_override)
    return env_path.resolve()


def _projects_dir() -> Path:
    from os import getenv
    projects_path = Path(__file__).resolve().parents[2] / "data" / "projects"
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