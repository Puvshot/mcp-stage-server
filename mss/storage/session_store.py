from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any


ACTIVE_SESSION_FILENAME = "active.json"
SESSION_FILENAME = "session.json"
PENDING_SUBDIR = "_pending"


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


def load_session(session_dir: str | Path, project_name: str | None = None) -> dict[str, Any] | None:
    """Load session payload from the resolved subdirectory."""
    return _read_json(_session_path(session_dir, project_name))


def save_session(session_dir: str | Path, session_payload: dict[str, Any]) -> None:
    """Persist one session payload atomically."""
    normalized_session = _normalize_session_payload(session_payload)
    project_name = normalized_session.get("project_name")
    _write_json_atomic(_session_path(session_dir, project_name), normalized_session)


def get_active_session(session_dir: str | Path) -> dict[str, Any] | None:
    """Resolve and load the currently active session payload."""
    active_payload = _read_json(_active_session_path(session_dir))
    if not isinstance(active_payload, dict):
        return None

    project_name = active_payload.get("project_name") or None
    return load_session(session_dir=session_dir, project_name=project_name)


def set_active_session(
    session_dir: str | Path,
    session_id: str,
    project_name: str | None = None,
) -> None:
    """Set active session pointer atomically, including optional project_name."""
    normalized_session_id = str(session_id).strip()
    if not normalized_session_id:
        return
    payload: dict[str, Any] = {"session_id": normalized_session_id}
    if project_name:
        payload["project_name"] = str(project_name).strip()
    _write_json_atomic(_active_session_path(session_dir), payload)


def _active_session_path(session_dir: str | Path) -> Path:
    return _session_dir_path(session_dir) / ACTIVE_SESSION_FILENAME


def _session_path(session_dir: str | Path, project_name: str | None) -> Path:
    subdir = _resolve_session_subdir(_session_dir_path(session_dir), project_name)
    return subdir / SESSION_FILENAME


def _resolve_session_subdir(root: Path, project_name: str | None) -> Path:
    """Return _pending/ when no project_name is set, else <project_name>/."""
    if not project_name or not str(project_name).strip():
        return root / PENDING_SUBDIR
    return root / str(project_name).strip()


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

    # Fix A: normalizacja project_name
    raw_project_name = normalized_session.get("project_name")
    normalized_session["project_name"] = str(raw_project_name).strip() if raw_project_name else None

    return normalized_session
