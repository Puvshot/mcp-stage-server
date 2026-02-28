from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mss.rules.schema import REQUIRED_RULES_KINDS, RulesKind, RulesPayload, ValidationIssue, validate_rules_payload


@dataclass(frozen=True)
class RulesLoadError:
    code: str
    message: str
    file_path: str
    validation_issues: list[ValidationIssue]


class RulesLoadException(RuntimeError):
    def __init__(self, error_payload: RulesLoadError) -> None:
        super().__init__(error_payload.message)
        self.error_payload = error_payload


def runner_load_rules_payload(required_kind: RulesKind) -> RulesPayload:
    """Runner: load and validate one JSON SSOT rules file from data/rules_json."""
    resolved_file_path = _resolve_rules_file_path(required_kind)
    if not resolved_file_path.exists():
        raise RulesLoadException(
            RulesLoadError(
                code="MISSING_REQUIRED_RULES_KIND",
                message=f"Missing required rules kind '{required_kind}'.",
                file_path=str(resolved_file_path),
                validation_issues=[],
            )
        )

    raw_json_text = resolved_file_path.read_text(encoding="utf-8")
    return core_parse_and_validate_rules_payload(
        required_kind=required_kind,
        raw_json_text=raw_json_text,
        source_file_path=str(resolved_file_path),
    )


def core_parse_and_validate_rules_payload(
    required_kind: RulesKind,
    raw_json_text: str,
    source_file_path: str,
) -> RulesPayload:
    """Core: parse and validate JSON rules payload from provided text.

    This function is pure and performs no filesystem I/O.
    """
    if not isinstance(raw_json_text, str):
        raise RulesLoadException(
            RulesLoadError(
                code="INVALID_RULES_JSON_INPUT",
                message="raw_json_text must be a string.",
                file_path=source_file_path,
                validation_issues=[],
            )
        )

    try:
        loaded_payload: Any = json.loads(raw_json_text)
    except json.JSONDecodeError as decode_error:
        raise RulesLoadException(
            RulesLoadError(
                code="INVALID_RULES_JSON",
                message=f"Invalid JSON payload for required rules kind '{required_kind}'.",
                file_path=source_file_path,
                validation_issues=[
                    ValidationIssue(
                        code="INVALID_JSON",
                        message=str(decode_error),
                        path="$",
                    )
                ],
            )
        ) from decode_error

    validation_issues = validate_rules_payload(loaded_payload)
    if validation_issues:
        raise RulesLoadException(
            RulesLoadError(
                code="INVALID_RULES_PAYLOAD",
                message=f"Validation failed for required rules kind '{required_kind}'.",
                file_path=source_file_path,
                validation_issues=validation_issues,
            )
        )

    return loaded_payload


def runner_load_all_required_rules_payloads() -> dict[RulesKind, RulesPayload]:
    """Runner: load all required JSON SSOT rules files with deterministic ordering."""
    loaded_payloads: dict[RulesKind, RulesPayload] = {}
    for required_kind in REQUIRED_RULES_KINDS:
        loaded_payloads[required_kind] = runner_load_rules_payload(required_kind)
    return loaded_payloads


def load_rules_payload(required_kind: RulesKind) -> RulesPayload:
    """Backward-compatible wrapper for runner rules loading."""
    return runner_load_rules_payload(required_kind)


def load_all_required_rules_payloads() -> dict[RulesKind, RulesPayload]:
    """Backward-compatible wrapper for runner loading of all required rules."""
    return runner_load_all_required_rules_payloads()


def _resolve_rules_file_path(required_kind: RulesKind) -> Path:
    project_root = Path(__file__).resolve().parents[2]
    return project_root / "data" / "rules_json" / f"{required_kind}.json"
