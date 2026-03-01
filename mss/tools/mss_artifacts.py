from __future__ import annotations

from pathlib import Path
from typing import Any

from mss.engines.artifact_flow_gate import (
    build_coverage_validation,
    extract_details_text,
    extract_summary_text,
    gate_for_artifact_tool,
    gate_for_planning_mode,
    normalize_mode,
    summarize_details_passed,
)
from mss.storage.artifact_store import (
    get_artifact as storage_get_artifact,
    list_artifacts as storage_list_artifacts,
    save_artifact as storage_save_artifact,
)
from mss.storage.session_store import get_active_session

SESSION_DIR_ENV = "MSS_SESSION_DIR"
_CAPABILITIES = [
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


def capabilities() -> dict[str, Any]:
    """Return available MSS artifact operations for active session mode."""
    active_session = _active_session()
    if active_session is None:
        return _missing_session_response()
    return {"ok": True, "mode": normalize_mode(active_session.get("mode")), "capabilities": _CAPABILITIES, "next_actions": [], "warnings": []}


def workout(note: str | None = None) -> dict[str, Any]:
    """Persist workout artifact and return next actions for workout flow."""
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
        gate_tool_name="workout",
    )


def end_workout(summary: str | None = None) -> dict[str, Any]:
    """Persist end_workout artifact and return next actions."""
    return _save_named_artifact(
        artifact_name="end_workout",
        payload={"summary": _normalize_optional_text(summary)},
        next_actions=[_action("mss.summarize", "Podsumuj sesję")],
    )


def summarize(summary: str | None = None) -> dict[str, Any]:
    """Persist summarize artifact and return summary metadata."""
    return _save_named_artifact(
        artifact_name="summarize",
        payload={"summary": _normalize_optional_text(summary)},
        next_actions=[
            _action("mss.summarize_details", "Uzupełnij szczegóły per plik"),
            _action("mss.list_artifacts", "Wyświetl artefakty sesji"),
        ],
    )


def summarize_details(details: str | None = None) -> dict[str, Any]:
    """Persist summarize_details artifact with strict FILES AFFECTED coverage check."""
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
    coverage_payload = build_coverage_validation(
        summary_text=extract_summary_text(summarize_artifact),
        details_text=normalized_details or "",
    )
    validation_passed = bool(coverage_payload["passed"])

    next_actions = [_action("mss.planning", "Przejdź do planowania") if validation_passed else _action("mss.summarize_details", "Uzupełnij brakujące szczegóły")]

    warnings: list[str] = []
    if summarize_artifact is None:
        warnings.append("summarize_artifact_not_found")
    if normalized_details is None:
        warnings.append("details_missing")
    if not coverage_payload["validation"]["files_affected"]:
        warnings.append("files_affected_not_found")
    if coverage_payload["validation"]["missing"]:
        warnings.append("missing_files_coverage")

    artifact_payload = {
        "details": normalized_details,
        "validation": coverage_payload["validation"],
    }
    saved_artifact = storage_save_artifact(
        session_dir=_session_dir(),
        session_id=session_id,
        artifact_name="summarize_details",
        artifact_payload=artifact_payload,
    )
    if saved_artifact is None:
        return _artifact_save_failed_response()

    return {
        "ok": validation_passed,
        "artifact": saved_artifact,
        "validation": coverage_payload["validation"],
        "next_actions": next_actions,
        "warnings": warnings,
        "message": (
            "Walidacja summarize_details zakończona powodzeniem."
            if validation_passed
            else "Walidacja summarize_details nie pokrywa wszystkich FILES AFFECTED."
        ),
    }


def audit(summary: str | None = None) -> dict[str, Any]:
    """Persist audit artifact and return next actions for audit flow."""
    return _save_named_artifact(
        artifact_name="audit",
        payload={"summary": _normalize_optional_text(summary)},
        next_actions=[
            _action("mss.prepare", "Przygotuj preplan"),
            _action("mss.planning", "Przejdź do planowania"),
        ],
        gate_tool_name="audit",
    )


def prepare(notes: str | None = None) -> dict[str, Any]:
    """Persist prepare artifact and return next actions."""
    return _save_named_artifact(
        artifact_name="prepare",
        payload={"notes": _normalize_optional_text(notes)},
        next_actions=[_action("mss.planning", "Przejdź do planowania")],
        gate_tool_name="prepare",
    )


def planning(plan_outline: str | None = None) -> dict[str, Any]:
    """Persist planning artifact and return next actions."""
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

    coverage_payload = build_coverage_validation(
        summary_text=extract_summary_text(summarize_artifact),
        details_text=extract_details_text(summarize_details_artifact),
    )
    has_summary_details = summarize_details_artifact is not None
    has_full_coverage = bool(coverage_payload["passed"])

    if not has_summary_details or not has_full_coverage:
        warnings: list[str] = []
        if summarize_artifact is None:
            warnings.append("summarize_artifact_not_found")
        if summarize_details_artifact is None:
            warnings.append("summarize_details_artifact_not_found")
        if not coverage_payload["validation"]["files_affected"]:
            warnings.append("files_affected_not_found")
        if coverage_payload["validation"]["missing"]:
            warnings.append("missing_files_coverage")

        return _planning_coverage_failed_response(coverage_payload["validation"], warnings)

    flow_state = _collect_flow_state(session_id)
    planning_mode_gate = gate_for_planning_mode(
        mode=normalize_mode(active_session.get("mode")),
        summarize_details_pass=flow_state["summarize_details_pass"],
        has_end_debug=flow_state["has_end_debug"],
    )
    if planning_mode_gate["blocked"]:
        return _gate_blocked_response(planning_mode_gate)

    return _save_named_artifact(
        artifact_name="planning",
        payload={"plan_outline": _normalize_optional_text(plan_outline)},
        next_actions=[_action("mss.package", "Spakuj wynik planowania")],
    )


def package(summary: str | None = None) -> dict[str, Any]:
    """Persist package artifact and return next actions."""
    return _save_named_artifact(
        artifact_name="package",
        payload={"summary": _normalize_optional_text(summary)},
        next_actions=[_action("mss.run", "Uruchom wykonanie pakietu")],
        gate_tool_name="package",
    )


def run(output: str | None = None) -> dict[str, Any]:
    """Persist run artifact and return next actions."""
    return _save_named_artifact(
        artifact_name="run",
        payload={"output": _normalize_optional_text(output)},
        next_actions=[_action("mss.debug", "Przejdź do debugowania")],
        gate_tool_name="run",
    )


def debug(findings: str | None = None) -> dict[str, Any]:
    """Persist debug artifact and return next actions."""
    return _save_named_artifact(
        artifact_name="debug",
        payload={"findings": _normalize_optional_text(findings)},
        next_actions=[_action("mss.end_debug", "Zakończ debugowanie")],
        gate_tool_name="debug",
    )


def end_debug(summary: str | None = None) -> dict[str, Any]:
    """Persist end_debug artifact and return next actions."""
    return _save_named_artifact(
        artifact_name="end_debug",
        payload={"summary": _normalize_optional_text(summary)},
        next_actions=[_action("mss.status", "Sprawdź status sesji")],
    )


def list_artifacts() -> dict[str, Any]:
    """List stored artifacts metadata for currently active MSS session."""
    active_session = _active_session()
    if active_session is None:
        return _missing_session_response()
    session_id = str(active_session.get("session_id", "")).strip()
    artifacts = storage_list_artifacts(session_dir=_session_dir(), session_id=session_id)
    return {"ok": True, "session_id": session_id, "artifacts": artifacts, "next_actions": [], "warnings": []}


def get_artifact(name: str) -> dict[str, Any]:
    """Load latest artifact payload by name for active MSS session."""
    active_session = _active_session()
    if active_session is None:
        return _missing_session_response()

    normalized_name = str(name).strip()
    if not normalized_name:
        return _invalid_artifact_name_response()

    session_id = str(active_session.get("session_id", "")).strip()
    artifact_document = storage_get_artifact(
        session_dir=_session_dir(),
        session_id=session_id,
        artifact_name=normalized_name,
    )
    if artifact_document is None:
        return _artifact_not_found_response(normalized_name)

    return {"ok": True, "artifact": artifact_document, "next_actions": [], "warnings": []}


def _active_session() -> dict[str, Any] | None:
    return get_active_session(session_dir=_session_dir())


def _save_named_artifact(
    artifact_name: str,
    payload: dict[str, Any],
    next_actions: list[dict[str, str]],
    gate_tool_name: str | None = None,
) -> dict[str, Any]:
    active_session = _active_session()
    if active_session is None:
        return _missing_session_response()

    session_id = str(active_session.get("session_id", "")).strip()
    if gate_tool_name is not None:
        flow_state = _collect_flow_state(session_id)
        gate_decision = gate_for_artifact_tool(
            mode=normalize_mode(active_session.get("mode")),
            tool_name=gate_tool_name,
            artifact_names=flow_state["artifact_names"],
            summarize_details_pass=flow_state["summarize_details_pass"],
            has_end_debug=flow_state["has_end_debug"],
        )
        if gate_decision["blocked"]:
            return _gate_blocked_response(gate_decision)

    saved_artifact = storage_save_artifact(
        session_dir=_session_dir(),
        session_id=session_id,
        artifact_name=artifact_name,
        artifact_payload=payload,
    )
    if saved_artifact is None:
        return _artifact_save_failed_response()

    return {"ok": True, "artifact": saved_artifact, "next_actions": next_actions, "warnings": []}


def _collect_flow_state(session_id: str) -> dict[str, Any]:
    artifacts = storage_list_artifacts(session_dir=_session_dir(), session_id=session_id)
    artifact_names = {
        str(artifact_metadata.get("name", "")).strip().lower()
        for artifact_metadata in artifacts
        if isinstance(artifact_metadata, dict)
    }
    summarize_details_artifact = storage_get_artifact(
        session_dir=_session_dir(),
        session_id=session_id,
        artifact_name="summarize_details",
    )
    return {
        "artifact_names": artifact_names,
        "summarize_details_pass": summarize_details_passed(summarize_details_artifact),
        "has_end_debug": "end_debug" in artifact_names,
    }


def _session_dir() -> Path:
    from os import getenv

    session_dir = Path.cwd() / "data" / "sessions"
    raw_override = getenv(SESSION_DIR_ENV)
    if raw_override:
        session_dir = Path(raw_override)
    return session_dir.resolve()


def _missing_session_response() -> dict[str, Any]:
    return {"ok": False, "message": "Brak aktywnej sesji. Uruchom `mss.connect`.", "next_actions": [_action("connect", "Połącz z MSS")], "warnings": ["active_session_not_found"]}


def _invalid_artifact_name_response() -> dict[str, Any]:
    return {"ok": False, "artifact": None, "next_actions": [_action("list_artifacts", "Wyświetl dostępne artefakty")], "warnings": ["invalid_artifact_name"], "message": "Nieprawidłowa nazwa artefaktu."}


def _artifact_not_found_response(artifact_name: str) -> dict[str, Any]:
    return {"ok": False, "artifact": None, "next_actions": [_action("list_artifacts", "Wyświetl dostępne artefakty")], "warnings": ["artifact_not_found"], "message": f"Nie znaleziono artefaktu: {artifact_name}."}


def _artifact_save_failed_response() -> dict[str, Any]:
    return {"ok": False, "message": "Nie udało się zapisać artefaktu.", "next_actions": [_action("mss.status", "Sprawdź status sesji")], "warnings": ["artifact_save_failed"]}


def _planning_coverage_failed_response(validation_payload: dict[str, Any], warnings: list[str]) -> dict[str, Any]:
    return {"ok": False, "message": "Przed planning wymagane jest poprawne summarize_details z pokryciem FILES AFFECTED.", "validation": validation_payload, "next_actions": [_action("mss.summarize_details", "Uzupełnij szczegóły per plik")], "warnings": warnings}


def _gate_blocked_response(gate_payload: dict[str, Any]) -> dict[str, Any]:
    return {"ok": False, "message": str(gate_payload.get("message", "STOP: Operacja zablokowana przez gate.")), "next_actions": gate_payload.get("next_actions", []), "warnings": gate_payload.get("warnings", [])}


def _normalize_optional_text(raw_value: Any) -> str | None:
    if raw_value is None:
        return None
    normalized_text = str(raw_value).strip()
    if not normalized_text:
        return None
    return normalized_text


def _action(command: str, description: str) -> dict[str, str]:
    return {"command": command, "description": description}