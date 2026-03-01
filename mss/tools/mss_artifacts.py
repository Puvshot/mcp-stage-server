from __future__ import annotations

from pathlib import Path
from typing import Any

from mss.engines.summary_details_validator import (
    extract_details_coverage,
    extract_files_affected,
    validate_details_against_files,
)
from mss.storage.artifact_store import (
    get_artifact as storage_get_artifact,
    list_artifacts as storage_list_artifacts,
    save_artifact as storage_save_artifact,
)
from mss.storage.session_store import get_active_session


SESSION_DIR_ENV = "MSS_SESSION_DIR"


def capabilities() -> dict[str, Any]:
    """Return available MSS artifact operations for active session mode.

    This read-only tool is idempotent.
    """
    active_session = _active_session()
    if active_session is None:
        return _missing_session_response()

    mode = _normalize_mode(active_session.get("mode"))
    return {
        "ok": True,
        "mode": mode,
        "capabilities": _capabilities_for_mode(mode),
        "next_actions": [],
        "warnings": [],
    }


def workout(note: str | None = None) -> dict[str, Any]:
    """Persist workout artifact and return next actions for workout flow.

    Contract for `note` content:
    - Note must include per-file sections, preferred format: `### <filepath>`.
    - For each file include: decisions, rejected alternatives with reason, and implications/tests.
    - Keep content verbatim (no compression), because it is later rewritten into `summarize_details`.

    This tool is side-effecting and non-idempotent.
    """
    return _save_named_artifact(
        artifact_name="workout",
        payload={"note": _normalize_optional_text(note)},
        next_actions=[
            _action("mss.end_workout", "Zamknij sesję workout"),
            _action(
                "mss.summarize",
                "Podsumuj sesję i pamiętaj, że summarize_details wymaga później sekcji per plik",
            ),
        ],
    )


def end_workout(summary: str | None = None) -> dict[str, Any]:
    """Persist end_workout artifact and return next actions.

    This tool is side-effecting and non-idempotent.
    """
    return _save_named_artifact(
        artifact_name="end_workout",
        payload={"summary": _normalize_optional_text(summary)},
        next_actions=[_action("mss.summarize", "Podsumuj sesję")],
    )


def summarize(summary: str | None = None) -> dict[str, Any]:
    """Persist summarize artifact and return summary metadata.

    This tool is side-effecting and non-idempotent.
    """
    return _save_named_artifact(
        artifact_name="summarize",
        payload={"summary": _normalize_optional_text(summary)},
        next_actions=[
            _action("mss.summarize_details", "Uzupełnij szczegóły per plik"),
            _action("mss.list_artifacts", "Wyświetl artefakty sesji"),
        ],
    )


def summarize_details(details: str | None = None) -> dict[str, Any]:
    """Persist summarize_details artifact with strict FILES AFFECTED coverage check.

    Contract for `details` content:
    - For each file in FILES AFFECTED from summarize artifact, write section `### <filepath>`.
    - `details` is the target format and must align with FILES AFFECTED from summarize.
    - Copy verbatim from workout/debug notes — no compression.
    - Include exact classes/functions/fields/signatures/algorithm decisions.

    Validation is deterministic and compares `details` coverage against FILES AFFECTED extracted from
    latest `summarize` artifact payload. This tool is side-effecting and non-idempotent.
    """
    active_session = _active_session()
    if active_session is None:
        return _missing_session_response()

    session_id = str(active_session.get("session_id", "")).strip()
    normalized_details = _normalize_optional_text(details)

    summarize_artifact = storage_get_artifact(
        session_dir=_session_dir(),
        session_id=session_id,
        artifact_name="summarize",
    )
    summarize_summary = _extract_summarize_summary_text(summarize_artifact)

    files_affected = extract_files_affected(summarize_summary)
    covered_paths = extract_details_coverage(normalized_details or "")
    missing_files = validate_details_against_files(files_affected, covered_paths)

    validation_passed = len(files_affected) > 0 and len(missing_files) == 0
    next_actions = [
        _action("mss.planning", "Przejdź do planowania")
        if validation_passed
        else _action("mss.summarize_details", "Uzupełnij brakujące szczegóły")
    ]

    warnings: list[str] = []
    if summarize_artifact is None:
        warnings.append("summarize_artifact_not_found")
    if normalized_details is None:
        warnings.append("details_missing")
    if not files_affected:
        warnings.append("files_affected_not_found")
    if missing_files:
        warnings.append("missing_files_coverage")

    artifact_payload = {
        "details": normalized_details,
        "validation": {
            "status": "pass" if validation_passed else "fail",
            "files_affected": files_affected,
            "covered": sorted(covered_paths),
            "missing": missing_files,
        },
    }

    saved_artifact = storage_save_artifact(
        session_dir=_session_dir(),
        session_id=session_id,
        artifact_name="summarize_details",
        artifact_payload=artifact_payload,
    )
    if saved_artifact is None:
        return {
            "ok": False,
            "message": "Nie udało się zapisać artefaktu.",
            "next_actions": [_action("mss.status", "Sprawdź status sesji")],
            "warnings": ["artifact_save_failed"],
        }

    return {
        "ok": validation_passed,
        "artifact": saved_artifact,
        "validation": artifact_payload["validation"],
        "next_actions": next_actions,
        "warnings": warnings,
        "message": (
            "Walidacja summarize_details zakończona powodzeniem."
            if validation_passed
            else "Walidacja summarize_details nie pokrywa wszystkich FILES AFFECTED."
        ),
    }


def audit(summary: str | None = None) -> dict[str, Any]:
    """Persist audit artifact and return next actions for audit flow.

    This tool is side-effecting and non-idempotent.
    """
    return _save_named_artifact(
        artifact_name="audit",
        payload={"summary": _normalize_optional_text(summary)},
        next_actions=[
            _action("mss.prepare", "Przygotuj preplan"),
            _action("mss.planning", "Przejdź do planowania"),
        ],
    )


def prepare(notes: str | None = None) -> dict[str, Any]:
    """Persist prepare artifact and return next actions.

    This tool is side-effecting and non-idempotent.
    """
    return _save_named_artifact(
        artifact_name="prepare",
        payload={"notes": _normalize_optional_text(notes)},
        next_actions=[_action("mss.planning", "Przejdź do planowania")],
    )


def planning(plan_outline: str | None = None) -> dict[str, Any]:
    """Persist planning artifact and return next actions.

    This tool is side-effecting and non-idempotent.
    """
    active_session = _active_session()
    if active_session is None:
        return _missing_session_response()

    session_id = str(active_session.get("session_id", "")).strip()
    summarize_artifact = storage_get_artifact(
        session_dir=_session_dir(),
        session_id=session_id,
        artifact_name="summarize",
    )
    summarize_details_artifact = storage_get_artifact(
        session_dir=_session_dir(),
        session_id=session_id,
        artifact_name="summarize_details",
    )

    summarize_summary = _extract_summarize_summary_text(summarize_artifact)
    files_affected = extract_files_affected(summarize_summary)
    details_text = _extract_summarize_details_text(summarize_details_artifact)
    covered_paths = extract_details_coverage(details_text)
    missing_files = validate_details_against_files(files_affected, covered_paths)

    has_summary_details = summarize_details_artifact is not None
    has_full_coverage = len(files_affected) > 0 and len(missing_files) == 0
    if not has_summary_details or not has_full_coverage:
        warnings: list[str] = []
        if summarize_artifact is None:
            warnings.append("summarize_artifact_not_found")
        if summarize_details_artifact is None:
            warnings.append("summarize_details_artifact_not_found")
        if not files_affected:
            warnings.append("files_affected_not_found")
        if missing_files:
            warnings.append("missing_files_coverage")

        return {
            "ok": False,
            "message": "Przed planning wymagane jest poprawne summarize_details z pokryciem FILES AFFECTED.",
            "validation": {
                "files_affected": files_affected,
                "covered": sorted(covered_paths),
                "missing": missing_files,
            },
            "next_actions": [
                _action("mss.summarize_details", "Uzupełnij szczegóły per plik")
            ],
            "warnings": warnings,
        }

    return _save_named_artifact(
        artifact_name="planning",
        payload={"plan_outline": _normalize_optional_text(plan_outline)},
        next_actions=[_action("mss.package", "Spakuj wynik planowania")],
    )


def package(summary: str | None = None) -> dict[str, Any]:
    """Persist package artifact and return next actions.

    This tool is side-effecting and non-idempotent.
    """
    return _save_named_artifact(
        artifact_name="package",
        payload={"summary": _normalize_optional_text(summary)},
        next_actions=[_action("mss.run", "Uruchom wykonanie pakietu")],
    )


def run(output: str | None = None) -> dict[str, Any]:
    """Persist run artifact and return next actions.

    This tool is side-effecting and non-idempotent.
    """
    return _save_named_artifact(
        artifact_name="run",
        payload={"output": _normalize_optional_text(output)},
        next_actions=[_action("mss.debug", "Przejdź do debugowania")],
    )


def debug(findings: str | None = None) -> dict[str, Any]:
    """Persist debug artifact and return next actions.

    Contract for `findings` content:
    - Findings should be collected per file, preferred format: `### <filepath>`.
    - Keep content verbatim (no compression) for later reuse.
    - For each file include: observations, hypotheses, experiments, result, and final fix.

    This tool is side-effecting and non-idempotent.
    """
    return _save_named_artifact(
        artifact_name="debug",
        payload={"findings": _normalize_optional_text(findings)},
        next_actions=[_action("mss.end_debug", "Zakończ debugowanie")],
    )


def end_debug(summary: str | None = None) -> dict[str, Any]:
    """Persist end_debug artifact and return next actions.

    This tool is side-effecting and non-idempotent.
    """
    return _save_named_artifact(
        artifact_name="end_debug",
        payload={"summary": _normalize_optional_text(summary)},
        next_actions=[_action("mss.status", "Sprawdź status sesji")],
    )


def list_artifacts() -> dict[str, Any]:
    """List stored artifacts metadata for currently active MSS session.

    This read-only tool is idempotent.
    """
    active_session = _active_session()
    if active_session is None:
        return _missing_session_response()

    session_id = str(active_session.get("session_id", "")).strip()
    artifacts = storage_list_artifacts(session_dir=_session_dir(), session_id=session_id)
    return {
        "ok": True,
        "session_id": session_id,
        "artifacts": artifacts,
        "next_actions": [],
        "warnings": [],
    }


def get_artifact(name: str) -> dict[str, Any]:
    """Load latest artifact payload by name for active MSS session.

    This read-only tool is idempotent.
    """
    active_session = _active_session()
    if active_session is None:
        return _missing_session_response()

    normalized_name = str(name).strip()
    if not normalized_name:
        return {
            "ok": False,
            "artifact": None,
            "next_actions": [{"command": "list_artifacts", "description": "Wyświetl dostępne artefakty"}],
            "warnings": ["invalid_artifact_name"],
            "message": "Nieprawidłowa nazwa artefaktu.",
        }

    session_id = str(active_session.get("session_id", "")).strip()
    artifact_document = storage_get_artifact(
        session_dir=_session_dir(),
        session_id=session_id,
        artifact_name=normalized_name,
    )
    if artifact_document is None:
        return {
            "ok": False,
            "artifact": None,
            "next_actions": [{"command": "list_artifacts", "description": "Wyświetl dostępne artefakty"}],
            "warnings": ["artifact_not_found"],
            "message": f"Nie znaleziono artefaktu: {normalized_name}.",
        }

    return {
        "ok": True,
        "artifact": artifact_document,
        "next_actions": [],
        "warnings": [],
    }


def _active_session() -> dict[str, Any] | None:
    return get_active_session(session_dir=_session_dir())


def _save_named_artifact(
    artifact_name: str,
    payload: dict[str, Any],
    next_actions: list[dict[str, str]],
) -> dict[str, Any]:
    active_session = _active_session()
    if active_session is None:
        return _missing_session_response()

    session_id = str(active_session.get("session_id", "")).strip()
    saved_artifact = storage_save_artifact(
        session_dir=_session_dir(),
        session_id=session_id,
        artifact_name=artifact_name,
        artifact_payload=payload,
    )
    if saved_artifact is None:
        return {
            "ok": False,
            "message": "Nie udało się zapisać artefaktu.",
            "next_actions": [_action("mss.status", "Sprawdź status sesji")],
            "warnings": ["artifact_save_failed"],
        }

    return {
        "ok": True,
        "artifact": saved_artifact,
        "next_actions": next_actions,
        "warnings": [],
    }


def _session_dir() -> Path:
    from os import getenv

    session_dir = Path.cwd() / "data" / "sessions"
    raw_override = getenv(SESSION_DIR_ENV)
    if raw_override:
        session_dir = Path(raw_override)
    return session_dir.resolve()


def _missing_session_response() -> dict[str, Any]:
    return {
        "ok": False,
        "message": "Brak aktywnej sesji. Uruchom `mss.connect`.",
        "next_actions": [{"command": "connect", "description": "Połącz z MSS"}],
        "warnings": ["active_session_not_found"],
    }


def _normalize_mode(raw_mode: Any) -> str | None:
    if raw_mode is None:
        return None
    mode = str(raw_mode).strip().lower()
    if not mode:
        return None
    return mode


def _capabilities_for_mode(mode: str | None) -> list[str]:
    base_capabilities = [
        "capabilities",
        "list_artifacts",
        "get_artifact",
        "workout",
        "end_workout",
        "summarize",
        "summarize_details",
        "audit",
        "prepare",
        "planning",
        "package",
        "run",
        "debug",
        "end_debug",
    ]
    if mode in {"workout", "audit", "planning", "debug", "run"}:
        return base_capabilities
    return base_capabilities


def _normalize_optional_text(raw_value: Any) -> str | None:
    if raw_value is None:
        return None
    normalized_text = str(raw_value).strip()
    if not normalized_text:
        return None
    return normalized_text


def _action(command: str, description: str) -> dict[str, str]:
    return {
        "command": command,
        "description": description,
    }


def _extract_summarize_summary_text(summarize_artifact: dict[str, Any] | None) -> str:
    if not isinstance(summarize_artifact, dict):
        return ""

    payload = summarize_artifact.get("payload")
    if not isinstance(payload, dict):
        return ""

    summary_text = payload.get("summary")
    if not isinstance(summary_text, str):
        return ""

    return summary_text


def _extract_summarize_details_text(summarize_details_artifact: dict[str, Any] | None) -> str:
    if not isinstance(summarize_details_artifact, dict):
        return ""

    payload = summarize_details_artifact.get("payload")
    if not isinstance(payload, dict):
        return ""

    details_text = payload.get("details")
    if not isinstance(details_text, str):
        return ""

    return details_text