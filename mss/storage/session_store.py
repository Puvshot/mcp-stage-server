from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any


ACTIVE_SESSION_FILENAME = "active.json"


def create_session(
    session_dir: str | Path,
    session_payload: dict[str, Any],
) -> dict[str, Any]:
    """Create a new session document and return normalized payload.

    This operation is idempotent when called repeatedly with the same
    `session_id` and payload shape.
    """
    normalized_session = _normalize_session_payload(session_payload)
    save_session(session_dir=session_dir, session_payload=normalized_session)
    return deepcopy(normalized_session)


def load_session(session_dir: str | Path, session_id: str) -> dict[str, Any] | None:
    """Load one session payload by identifier."""
    normalized_session_id = str(session_id).strip()
    if not normalized_session_id:
        return None
    return _read_json(_session_path(session_dir, normalized_session_id))


def save_session(session_dir: str | Path, session_payload: dict[str, Any]) -> None:
    """Persist one session payload atomically."""
    normalized_session = _normalize_session_payload(session_payload)
    session_id = str(normalized_session.get("session_id", "")).strip()
    if not session_id:
        return
    _write_json_atomic(_session_path(session_dir, session_id), normalized_session)


def get_active_session(session_dir: str | Path) -> dict[str, Any] | None:
    """Resolve and load the currently active session payload."""
    active_payload = _read_json(_active_session_path(session_dir))
    if not isinstance(active_payload, dict):
        return None

    active_session_id = str(active_payload.get("session_id", "")).strip()
    if not active_session_id:
        return None
    return load_session(session_dir=session_dir, session_id=active_session_id)


def set_active_session(session_dir: str | Path, session_id: str) -> None:
    """Set active session identifier pointer atomically."""
    normalized_session_id = str(session_id).strip()
    if not normalized_session_id:
        return
    _write_json_atomic(_active_session_path(session_dir), {"session_id": normalized_session_id})


def _active_session_path(session_dir: str | Path) -> Path:
    return _session_dir_path(session_dir) / ACTIVE_SESSION_FILENAME


def _session_path(session_dir: str | Path, session_id: str) -> Path:
    return _session_dir_path(session_dir) / f"{session_id}.json"


def _session_dir_path(session_dir: str | Path) -> Path:
    return Path(session_dir).resolve()


def _write_json_atomic(file_path: Path, payload: dict[str, Any]) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = file_path.with_suffix(f"{file_path.suffix}.tmp")
    with temp_path.open("w", encoding="utf-8") as temp_file:
        json.dump(payload, temp_file, ensure_ascii=False, indent=2)
        temp_file.flush()
        os.fsync(temp_file.fileno())
    os.replace(temp_path, file_path)


def _read_json(file_path: Path) -> dict[str, Any] | None:
    if not file_path.exists():
        return None
    try:
        with file_path.open("r", encoding="utf-8") as payload_file:
            loaded_payload: dict[str, Any] = json.load(payload_file)
    except (OSError, json.JSONDecodeError):
        return None
    return _normalize_session_payload(loaded_payload)


def _normalize_session_payload(session_payload: dict[str, Any]) -> dict[str, Any]:
    normalized_session = deepcopy(session_payload)
    normalized_session.setdefault("session_id", "")
    normalized_session["session_id"] = str(normalized_session["session_id"]).strip()
    normalized_session["created_at"] = str(normalized_session.get("created_at", "")).strip()

    raw_mode = normalized_session.get("mode")
    normalized_session["mode"] = None if raw_mode is None else str(raw_mode).strip().lower()

    raw_artifacts = normalized_session.get("artifacts")
    if not isinstance(raw_artifacts, list):
        normalized_session["artifacts"] = []
    else:
        normalized_session["artifacts"] = deepcopy(raw_artifacts)
    return normalized_session