from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, TypedDict

RulesKind = Literal[
    "preplan_gate",
    "plan_generation",
    "plan_validation",
    "package_generation",
    "package_collision",
]

REQUIRED_RULES_KINDS: tuple[RulesKind, ...] = (
    "preplan_gate",
    "plan_generation",
    "plan_validation",
    "package_generation",
    "package_collision",
)


class ActionDirectivePayload(TypedDict):
    must: list[str]
    must_not: list[str]


class AlwaysPayload(TypedDict):
    must: list[str]
    must_not: list[str]


class RulesPayload(TypedDict):
    version: str
    action_directives: dict[str, ActionDirectivePayload]
    always: AlwaysPayload
    forbidden_imports: list[str]
    templates: dict[str, str]


class RulesConversionCoreSuccess(TypedDict):
    status: Literal["ok"]
    payload: RulesPayload
    conversion_warnings: list[str]


class RulesConversionCoreError(TypedDict):
    status: Literal["error"]
    code: str
    errors: list[dict[str, Any]]


class RulesConversionRunnerSuccess(TypedDict):
    status: Literal["ok"]
    rules_kind: RulesKind
    source_markdown_path: str
    payload: RulesPayload
    conversion_warnings: list[str]


class RulesConversionRunnerError(TypedDict):
    status: Literal["error"]
    code: str
    errors: list[dict[str, Any]]


RulesConversionCoreResult = RulesConversionCoreSuccess | RulesConversionCoreError
RulesConversionRunnerResult = RulesConversionRunnerSuccess | RulesConversionRunnerError


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    path: str


def validate_rules_payload(payload: Any) -> list[ValidationIssue]:
    """Validate JSON SSOT payload and return deterministic validation issues."""
    validation_issues: list[ValidationIssue] = []
    if not isinstance(payload, dict):
        return [
            ValidationIssue(
                code="INVALID_RULES_PAYLOAD_TYPE",
                message="Rules payload must be an object.",
                path="$",
            )
        ]

    _require_string_field(payload, "version", validation_issues)
    _require_action_directives(payload, validation_issues)
    _require_always_section(payload, validation_issues)
    _require_string_list_field(payload, "forbidden_imports", validation_issues)
    _require_templates_section(payload, validation_issues)
    return validation_issues


def _require_string_field(payload: dict[str, Any], field_name: str, validation_issues: list[ValidationIssue]) -> None:
    value = payload.get(field_name)
    if isinstance(value, str) and value:
        return
    validation_issues.append(
        ValidationIssue(
            code="MISSING_REQUIRED_FIELD",
            message=f"Required field '{field_name}' must be a non-empty string.",
            path=f"$.{field_name}",
        )
    )


def _require_action_directives(payload: dict[str, Any], validation_issues: list[ValidationIssue]) -> None:
    action_directives_value = payload.get("action_directives")
    if not isinstance(action_directives_value, dict):
        validation_issues.append(
            ValidationIssue(
                code="MISSING_REQUIRED_FIELD",
                message="Required field 'action_directives' must be an object.",
                path="$.action_directives",
            )
        )
        return

    for action_name, action_payload in action_directives_value.items():
        if not isinstance(action_name, str) or not action_name:
            validation_issues.append(
                ValidationIssue(
                    code="INVALID_ACTION_NAME",
                    message="Action directive keys must be non-empty strings.",
                    path="$.action_directives",
                )
            )
            continue
        if not isinstance(action_payload, dict):
            validation_issues.append(
                ValidationIssue(
                    code="INVALID_ACTION_PAYLOAD",
                    message=f"Action '{action_name}' payload must be an object.",
                    path=f"$.action_directives.{action_name}",
                )
            )
            continue
        _require_string_list_field(action_payload, "must", validation_issues, f"$.action_directives.{action_name}")
        _require_string_list_field(action_payload, "must_not", validation_issues, f"$.action_directives.{action_name}")


def _require_always_section(payload: dict[str, Any], validation_issues: list[ValidationIssue]) -> None:
    always_value = payload.get("always")
    if not isinstance(always_value, dict):
        validation_issues.append(
            ValidationIssue(
                code="MISSING_REQUIRED_FIELD",
                message="Required field 'always' must be an object.",
                path="$.always",
            )
        )
        return
    _require_string_list_field(always_value, "must", validation_issues, "$.always")
    _require_string_list_field(always_value, "must_not", validation_issues, "$.always")


def _require_templates_section(payload: dict[str, Any], validation_issues: list[ValidationIssue]) -> None:
    templates_value = payload.get("templates")
    if not isinstance(templates_value, dict):
        validation_issues.append(
            ValidationIssue(
                code="MISSING_REQUIRED_FIELD",
                message="Required field 'templates' must be an object.",
                path="$.templates",
            )
        )
        return

    for template_name, template_text in templates_value.items():
        if not isinstance(template_name, str) or not template_name:
            validation_issues.append(
                ValidationIssue(
                    code="INVALID_TEMPLATE_NAME",
                    message="Template keys must be non-empty strings.",
                    path="$.templates",
                )
            )
            continue
        if isinstance(template_text, str) and template_text:
            continue
        validation_issues.append(
            ValidationIssue(
                code="INVALID_TEMPLATE_VALUE",
                message=f"Template '{template_name}' must be a non-empty string.",
                path=f"$.templates.{template_name}",
            )
        )


def _require_string_list_field(
    payload: dict[str, Any],
    field_name: str,
    validation_issues: list[ValidationIssue],
    base_path: str = "$",
) -> None:
    value = payload.get(field_name)
    field_path = f"{base_path}.{field_name}"
    if not isinstance(value, list):
        validation_issues.append(
            ValidationIssue(
                code="MISSING_REQUIRED_FIELD",
                message=f"Required field '{field_name}' must be a list of strings.",
                path=field_path,
            )
        )
        return

    for index, list_value in enumerate(value):
        if isinstance(list_value, str) and list_value:
            continue
        validation_issues.append(
            ValidationIssue(
                code="INVALID_LIST_ITEM",
                message=f"Field '{field_name}' must contain only non-empty strings.",
                path=f"{field_path}[{index}]",
            )
        )
