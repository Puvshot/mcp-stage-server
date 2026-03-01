from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from mss.storage.session_store import (
    create_session,
    get_active_session,
    save_session,
    set_active_session,
)


ALLOWED_MODES = {"audit", "planning", "debug", "workout", "run"}
SESSION_DIR_ENV = "MSS_SESSION_DIR"

_CONNECT_MESSAGE = (
    "Połączono. Wyświetl użytkownikowi DOKŁADNIE ten tekst: "
    "'Cześć, jaką operację chcesz wykonać?\\n\\nDostępne funkcje:\\n"
    "- **Debug** (Ścisły protokół do naprawy kodu. Pokaż mi błąd, a ja przeanalizuję "
    "pliki, postawię hipotezę i naprawię usterkę krok po kroku)\\n"
    "- **Workout** (Burza mózgów i planowanie. Porozmawiajmy o architekturze, "
    "rozważmy opcje i zapisujmy ustalenia na bieżąco, bez pisania kodu na ślepo)'"
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

    return _response(
        ok=True,
        session_id=str(active_session.get("session_id", "")),
        mode=_normalize_mode(active_session.get("mode")),
        message=_CONNECT_MESSAGE,
        artifacts=_normalize_artifacts(active_session.get("artifacts")),
        next_actions=_action_connect(),
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

    mode = _normalize_mode(active_session.get("mode"))
    artifacts = _normalize_artifacts(active_session.get("artifacts"))
    artifact_names = {str(item.get("name", "")) for item in artifacts if isinstance(item, dict)}

    return _response(
        ok=True,
        session_id=str(active_session.get("session_id", "")),
        mode=mode,
        message="Status sesji pobrany.",
        artifacts=artifacts,
        next_actions=_status_next_actions(mode=mode, artifact_names=artifact_names),
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
        next_actions=_set_mode_next_actions(normalized_mode),
        warnings=[],
    )


def _status_next_actions(mode: str | None, artifact_names: set[str]) -> list[dict[str, str]]:
    if mode is None:
        return _action_connect()

    if mode == "audit":
        if "audit" in artifact_names:
            return [
                _action("preplan", "Przygotuj preplan na bazie audytu"),
                _action("show audit", "Pokaż artefakt audytu"),
            ]
        return [_action("audit", "Uruchom audyt kodu")]

    if mode == "planning":
        if "preplan" in artifact_names:
            return [_action("plan", "Wygeneruj plan implementacji")]
        return [_action("preplan", "Wygeneruj preplan")]

    return _set_mode_next_actions(mode)


def _set_mode_next_actions(mode: str) -> list[dict[str, str]]:
    mapping: dict[str, list[dict[str, str]]] = {
        "audit": [
            _action("audit", "Uruchom audyt kodu"),
            _action("status", "Sprawdź stan sesji"),
        ],
        "planning": [
            _action("preplan", "Przygotuj preplan"),
            _action("plan", "Wygeneruj plan"),
            _action("status", "Sprawdź stan sesji"),
        ],
        "debug": [
            _action("audit", "Uruchom audyt kodu"),
            _action("status", "Sprawdź stan sesji"),
        ],
        "workout": [_action("status", "Sprawdź stan sesji")],
        "run": [
            _action("plan", "Wygeneruj plan"),
            _action("status", "Sprawdź stan sesji"),
        ],
    }
    return mapping.get(mode, [_action("status", "Sprawdź stan sesji")])


def _action_connect() -> list[dict[str, str]]:
    return [
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