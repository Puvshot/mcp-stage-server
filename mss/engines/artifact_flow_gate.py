from __future__ import annotations

from typing import Any

from mss.engines.summary_details_validator import (
    extract_details_coverage,
    extract_files_affected,
    validate_details_against_files,
)


def gate_for_artifact_tool(
    mode: str | None,
    tool_name: str,
    artifact_names: set[str] | list[str],
    summarize_details_pass: bool,
    has_end_debug: bool,
) -> dict[str, Any]:
    """Return deterministic gate decision for MSS artifact tools.

    This function is read-only and idempotent.
    """
    normalized_mode = normalize_mode(mode)
    normalized_tool_name = str(tool_name).strip().lower()
    normalized_artifact_names = {str(artifact_name).strip().lower() for artifact_name in artifact_names}

    workout_blocked_tools = {"audit", "prepare", "package", "run", "debug"}
    debug_blocked_tools = {"audit", "prepare", "package", "run", "workout"}

    if normalized_mode == "workout" and normalized_tool_name in workout_blocked_tools and not summarize_details_pass:
        return {
            "blocked": True,
            "message": "STOP: Tryb workout blokuje to narzędzie do czasu PASS w summarize_details.",
            "next_actions": [_action("mss.summarize_details", "Uzupełnij summarize_details i doprowadź do PASS")],
            "warnings": ["artifact_flow_gate_workout_requires_summarize_details_pass"],
            "context": {
                "mode": normalized_mode,
                "tool_name": normalized_tool_name,
                "artifact_names": sorted(normalized_artifact_names),
            },
        }

    if normalized_mode == "debug" and normalized_tool_name in debug_blocked_tools:
        if not has_end_debug:
            return {
                "blocked": True,
                "message": "STOP: Tryb debug blokuje to narzędzie do czasu zapisania end_debug.",
                "next_actions": [_action("mss.end_debug", "Zapisz end_debug")],
                "warnings": ["artifact_flow_gate_debug_requires_end_debug"],
                "context": {
                    "mode": normalized_mode,
                    "tool_name": normalized_tool_name,
                    "artifact_names": sorted(normalized_artifact_names),
                },
            }
        if not summarize_details_pass:
            return {
                "blocked": True,
                "message": "STOP: Tryb debug blokuje to narzędzie do czasu PASS w summarize_details.",
                "next_actions": [_action("mss.summarize_details", "Uzupełnij summarize_details i doprowadź do PASS")],
                "warnings": ["artifact_flow_gate_debug_requires_summarize_details_pass"],
                "context": {
                    "mode": normalized_mode,
                    "tool_name": normalized_tool_name,
                    "artifact_names": sorted(normalized_artifact_names),
                },
            }

    return {
        "blocked": False,
        "message": "",
        "next_actions": [],
        "warnings": [],
        "context": {
            "mode": normalized_mode,
            "tool_name": normalized_tool_name,
            "artifact_names": sorted(normalized_artifact_names),
        },
    }


def gate_for_planning_mode(mode: str | None, summarize_details_pass: bool, has_end_debug: bool) -> dict[str, Any]:
    """Return deterministic mode gate decision for planning tool.

    This function is read-only and idempotent.
    """
    normalized_mode = normalize_mode(mode)

    if normalized_mode == "workout" and not summarize_details_pass:
        return {
            "blocked": True,
            "message": "STOP: Tryb workout blokuje planning do czasu PASS w summarize_details.",
            "next_actions": [_action("mss.summarize_details", "Uzupełnij summarize_details i doprowadź do PASS")],
            "warnings": ["planning_mode_gate_workout_requires_summarize_details_pass"],
        }

    if normalized_mode == "debug":
        if not has_end_debug:
            return {
                "blocked": True,
                "message": "STOP: Tryb debug blokuje planning do czasu zapisania end_debug.",
                "next_actions": [_action("mss.end_debug", "Zapisz end_debug")],
                "warnings": ["planning_mode_gate_debug_requires_end_debug"],
            }
        if not summarize_details_pass:
            return {
                "blocked": True,
                "message": "STOP: Tryb debug blokuje planning do czasu PASS w summarize_details.",
                "next_actions": [_action("mss.summarize_details", "Uzupełnij summarize_details i doprowadź do PASS")],
                "warnings": ["planning_mode_gate_debug_requires_summarize_details_pass"],
            }

    return {
        "blocked": False,
        "message": "",
        "next_actions": [],
        "warnings": [],
    }


def build_coverage_validation(summary_text: str, details_text: str) -> dict[str, Any]:
    """Build FILES AFFECTED coverage payload for summarize/planning checks.

    This function is read-only and idempotent.
    """
    files_affected = extract_files_affected(summary_text)
    covered_paths = extract_details_coverage(details_text)
    missing_paths = validate_details_against_files(files_affected, covered_paths)
    # Fix F: pusta lista plików = flow koncepcyjny, przepuszcza bez pokrycia
    validation_passed = len(missing_paths) == 0

    return {
        "passed": validation_passed,
        "validation": {
            "status": "pass" if validation_passed else "fail",
            "files_affected": files_affected,
            "covered": sorted(covered_paths),
            "missing": missing_paths,
        },
    }


def extract_summary_text(summarize_artifact: dict[str, Any] | None) -> str:
    """Extract summary text from summary artifact payload.

    Fix D: auto-dołącza files_affected z payload jako sekcję FILES AFFECTED
    dla walidatora summarize_details. Agent nie musi ręcznie formatować tekstu.
    """
    if not isinstance(summarize_artifact, dict):
        return ""
    payload = summarize_artifact.get("payload")
    if not isinstance(payload, dict):
        return ""
    summary_text = payload.get("summary") or ""
    if not isinstance(summary_text, str):
        summary_text = ""
    # Auto-append structured files_affected list as FILES AFFECTED section
    files_affected = payload.get("files_affected")
    if isinstance(files_affected, list) and files_affected:
        files_lines = "\n".join(f"- `{f}`" for f in files_affected if f)
        summary_text = f"{summary_text}\n\nFILES AFFECTED\n{files_lines}"
    return summary_text


def extract_details_text(summarize_details_artifact: dict[str, Any] | None) -> str:
    """Extract details text from summarize_details artifact payload."""
    if not isinstance(summarize_details_artifact, dict):
        return ""
    payload = summarize_details_artifact.get("payload")
    if not isinstance(payload, dict):
        return ""
    details_text = payload.get("details")
    if not isinstance(details_text, str):
        return ""
    return details_text


def summarize_details_passed(summarize_details_artifact: dict[str, Any] | None) -> bool:
    """Return True when summarize_details artifact contains validation status PASS."""
    if not isinstance(summarize_details_artifact, dict):
        return False
    payload = summarize_details_artifact.get("payload")
    if not isinstance(payload, dict):
        return False
    validation = payload.get("validation")
    if not isinstance(validation, dict):
        return False
    status_text = validation.get("status")
    return isinstance(status_text, str) and status_text.strip().lower() == "pass"


def normalize_mode(raw_mode: Any) -> str | None:
    """Normalize session mode text to lowercase or None."""
    if raw_mode is None:
        return None
    mode_text = str(raw_mode).strip().lower()
    return mode_text or None


def _action(command: str, description: str) -> dict[str, str]:
    return {"command": command, "description": description}