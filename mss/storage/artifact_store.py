from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mss.storage.session_store import load_session, save_session


ARTIFACTS_DIRNAME = "artifacts"


def save_artifact(
    session_dir: str | Path,
    session_id: str,
    artifact_name: str,
    artifact_payload: Any,
) -> dict[str, Any] | None:
    """Persist one versioned artifact for a session and update metadata in session file."""
    normalized_session_id = str(session_id).strip()
    normalized_artifact_name = str(artifact_name).strip()
    if not normalized_session_id or not normalized_artifact_name:
        return None

    session_payload = load_session(session_dir=session_dir, session_id=normalized_session_id)
    if session_payload is None:
        return None

    artifact_version = _next_artifact_version(session_payload, normalized_artifact_name)
    saved_at = _now_iso()
    artifact_document = {
        "name": normalized_artifact_name,
        "version": artifact_version,
        "saved_at": saved_at,
        "payload": deepcopy(artifact_payload),
    }

    _write_json_atomic(
        _artifact_path(session_dir, normalized_session_id, normalized_artifact_name, artifact_version),
        artifact_document,
    )

    artifacts_metadata = list_artifacts(session_dir=session_dir, session_id=normalized_session_id)
    artifacts_metadata = [
        metadata
        for metadata in artifacts_metadata
        if str(metadata.get("name", "")).strip() != normalized_artifact_name
    ]
    artifacts_metadata.append(
        {
            "name": normalized_artifact_name,
            "version": artifact_version,
            "saved_at": saved_at,
        }
    )

    session_payload["artifacts"] = artifacts_metadata
    save_session(session_dir=session_dir, session_payload=session_payload)

    return deepcopy(artifact_document)


def get_artifact(
    session_dir: str | Path,
    session_id: str,
    artifact_name: str,
) -> dict[str, Any] | None:
    """Load latest artifact document for a given session and artifact name."""
    normalized_session_id = str(session_id).strip()
    normalized_artifact_name = str(artifact_name).strip()
    if not normalized_session_id or not normalized_artifact_name:
        return None

    session_payload = load_session(session_dir=session_dir, session_id=normalized_session_id)
    if session_payload is None:
        return None

    artifacts_metadata = list_artifacts(session_dir=session_dir, session_id=normalized_session_id)
    artifact_version = 0
    for metadata in artifacts_metadata:
        metadata_name = str(metadata.get("name", "")).strip()
        if metadata_name != normalized_artifact_name:
            continue
        version_value = _to_int(metadata.get("version"), 0)
        artifact_version = max(artifact_version, version_value)

    if artifact_version <= 0:
        return None
    return _read_json(_artifact_path(session_dir, normalized_session_id, normalized_artifact_name, artifact_version))


def list_artifacts(session_dir: str | Path, session_id: str) -> list[dict[str, Any]]:
    """List latest artifact metadata available for a given session."""
    normalized_session_id = str(session_id).strip()
    if not normalized_session_id:
        return []

    session_payload = load_session(session_dir=session_dir, session_id=normalized_session_id)
    if session_payload is None:
        return []

    raw_artifacts = session_payload.get("artifacts")
    if not isinstance(raw_artifacts, list):
        return []

    latest_versions: dict[str, dict[str, Any]] = {}
    for raw_artifact in raw_artifacts:
        if not isinstance(raw_artifact, dict):
            continue

        normalized_artifact_name = str(raw_artifact.get("name", "")).strip()
        if not normalized_artifact_name:
            continue

        normalized_metadata = {
            "name": normalized_artifact_name,
            "version": _to_int(raw_artifact.get("version"), 1),
            "saved_at": str(raw_artifact.get("saved_at", "")).strip(),
        }

        previous_metadata = latest_versions.get(normalized_artifact_name)
        if previous_metadata is None or int(previous_metadata.get("version", 0)) <= normalized_metadata["version"]:
            latest_versions[normalized_artifact_name] = normalized_metadata

    return [latest_versions[name] for name in sorted(latest_versions)]


def _artifact_path(session_dir: str | Path, session_id: str, artifact_name: str, version: int) -> Path:
    safe_artifact_name = _safe_artifact_name(artifact_name)
    artifacts_dir = Path(session_dir).resolve() / ARTIFACTS_DIRNAME / session_id
    return artifacts_dir / f"{safe_artifact_name}.v{version}.json"


def _safe_artifact_name(artifact_name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", str(artifact_name).strip())


def _next_artifact_version(session_payload: dict[str, Any], artifact_name: str) -> int:
    current_version = 0
    raw_artifacts = session_payload.get("artifacts")
    if not isinstance(raw_artifacts, list):
        return 1

    for raw_artifact in raw_artifacts:
        if not isinstance(raw_artifact, dict):
            continue
        if str(raw_artifact.get("name", "")).strip() != artifact_name:
            continue
        current_version = max(current_version, _to_int(raw_artifact.get("version"), 0))
    return current_version + 1


def _write_json_atomic(file_path: Path, payload: dict[str, Any]) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = file_path.with_suffix(f"{file_path.suffix}.tmp")
    with tmp_path.open("w", encoding="utf-8") as tmp_file:
        json.dump(payload, tmp_file, ensure_ascii=False, indent=2)
        tmp_file.flush()
        os.fsync(tmp_file.fileno())
    os.replace(tmp_path, file_path)


def _read_json(file_path: Path) -> dict[str, Any] | None:
    if not file_path.exists():
        return None
    try:
        with file_path.open("r", encoding="utf-8") as payload_file:
            loaded_payload: dict[str, Any] = json.load(payload_file)
    except (OSError, json.JSONDecodeError):
        return None
    return deepcopy(loaded_payload)


def _to_int(raw_value: Any, default_value: int) -> int:
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return default_value


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()