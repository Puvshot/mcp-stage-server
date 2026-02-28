from __future__ import annotations

import re
from typing import Any


_STAGE_HEADER_RE = re.compile(r"^###\s+Stage\s+(\d+)\s*:\s*(.+)$", re.IGNORECASE)
_STEP_RE = re.compile(r"^\s*(\d+)\.\s*([A-Z_]+)\s*:\s*(.+?)\s*$")
_FILE_ENTRY_RE = re.compile(r"^\s*-\s*([A-Z_]+)\s*:\s*(.+?)\s*$")


def parse_package_markdown(markdown_text: str, package_id: str = "PACKAGE_UNKNOWN") -> dict[str, Any]:
    """Parse PACKAGE markdown in tolerant mode.

    This parser never raises for malformed sections. It always returns a package
    dictionary with a `warnings` list describing deviations from the expected
    format.
    """
    warnings: list[str] = []

    if not isinstance(markdown_text, str):
        return _empty_package(package_id, ["input is not a string; returning empty package"])

    lines = markdown_text.splitlines()
    package_name = _extract_package_name(lines, warnings)
    package_goal = _extract_section_text(lines, "## Package Goal", warnings)
    files_to_modify = _extract_files_to_modify(lines, warnings)
    stages = _extract_stages(lines, package_id, warnings)
    verification_commands = _extract_verification_commands(lines, warnings)

    return {
        "package_id": package_id,
        "package_name": package_name,
        "goal": package_goal,
        "files_to_modify": files_to_modify,
        "stages": stages,
        "verification_commands": verification_commands,
        "warnings": warnings,
    }


def _empty_package(package_id: str, warnings: list[str]) -> dict[str, Any]:
    return {
        "package_id": package_id,
        "package_name": "UNKNOWN: package name not found",
        "goal": "UNKNOWN: section not found",
        "files_to_modify": [],
        "stages": [],
        "verification_commands": [],
        "warnings": warnings,
    }


def _extract_package_name(lines: list[str], warnings: list[str]) -> str:
    for line in lines:
        if line.startswith("#"):
            text = line.lstrip("#").strip()
            if text:
                return text
            break

    warnings.append("package name header not found")
    return "UNKNOWN: package name not found"


def _extract_section_text(lines: list[str], section_header: str, warnings: list[str]) -> str:
    section_lines, found = _get_section_lines(lines, section_header)
    if not found:
        warnings.append(f"missing section: {section_header}")
        return "UNKNOWN: section not found"

    text_value = "\n".join(line.strip() for line in section_lines if line.strip())
    if not text_value:
        warnings.append(f"empty section: {section_header}")
        return "UNKNOWN: section not found"

    return text_value


def _extract_files_to_modify(lines: list[str], warnings: list[str]) -> list[dict[str, Any]]:
    section_lines, found = _get_section_lines(lines, "## Files to modify")
    if not found:
        warnings.append("missing section: ## Files to modify")
        return []

    entries: list[dict[str, Any]] = []
    for section_line in section_lines:
        match = _FILE_ENTRY_RE.match(section_line)
        if not match:
            continue

        raw_action = match.group(1).upper()
        raw_path = match.group(2).strip().strip("`")
        mapped_action = _map_action(raw_action)
        if mapped_action == "UNKNOWN":
            warnings.append(f"unknown file action in Files to modify: {raw_action}")

        entries.append(
            {
                "path": raw_path,
                "action": mapped_action,
                "is_smoke_test": False,
                "unknown": None if mapped_action != "UNKNOWN" else f"unknown action: {raw_action}",
            }
        )

    if not entries:
        warnings.append("section ## Files to modify has no parsable file entries")

    return entries


def _extract_stages(lines: list[str], package_id: str, warnings: list[str]) -> list[dict[str, Any]]:
    stage_positions: list[tuple[int, int, str]] = []
    for index, line in enumerate(lines):
        header_match = _STAGE_HEADER_RE.match(line.strip())
        if header_match:
            stage_number = int(header_match.group(1))
            stage_name = header_match.group(2).strip()
            stage_positions.append((index, stage_number, stage_name))

    if not stage_positions:
        warnings.append("no stage headers found")
        return []

    stages: list[dict[str, Any]] = []
    for stage_index, (start_line, stage_number, stage_name) in enumerate(stage_positions):
        next_start_line = stage_positions[stage_index + 1][0] if stage_index + 1 < len(stage_positions) else len(lines)
        stage_lines = lines[start_line + 1 : next_start_line]
        stage_steps = _extract_stage_steps(stage_lines, warnings)
        stage_actions = sorted({step["action"] for step in stage_steps if step["action"] != "UNKNOWN"})
        stage_test_command = _extract_stage_test_command(stage_steps)

        stages.append(
            {
                "stage_id": f"{package_id}_STAGE_{stage_number}",
                "stage_number": stage_number,
                "stage_name": stage_name,
                "steps": stage_steps,
                "test_command": stage_test_command,
                "dominant_actions": stage_actions,
            }
        )

    return stages


def _extract_stage_steps(stage_lines: list[str], warnings: list[str]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for stage_line in stage_lines:
        stripped_line = stage_line.strip()
        if not stripped_line:
            continue

        match = _STEP_RE.match(stripped_line)
        if match:
            step_number = int(match.group(1))
            raw_action = match.group(2).upper()
            step_target = match.group(3).strip().strip("`")
            mapped_action = _map_action(raw_action)
            if mapped_action == "UNKNOWN":
                warnings.append(f"unknown step action: {raw_action}")

            steps.append(
                {
                    "number": step_number,
                    "action": mapped_action,
                    "target": step_target,
                    "raw": stripped_line,
                }
            )
            continue

        if re.match(r"^\d+\.\s+", stripped_line):
            step_number = int(stripped_line.split(".", maxsplit=1)[0])
            warnings.append(f"unparsable stage step: {stripped_line}")
            steps.append(
                {
                    "number": step_number,
                    "action": "UNKNOWN",
                    "target": stripped_line,
                    "raw": stripped_line,
                }
            )

    return steps


def _extract_stage_test_command(stage_steps: list[dict[str, Any]]) -> str | None:
    for step in reversed(stage_steps):
        if step["action"] == "TEST":
            command_target = str(step["target"])
            if _is_no_specific_test_command(command_target):
                return None
            return command_target
    return None


def _is_no_specific_test_command(command_target: str) -> bool:
    normalized_target = command_target.strip().lower()
    return "no specific test identified" in normalized_target


def _extract_verification_commands(lines: list[str], warnings: list[str]) -> list[str]:
    section_lines, found = _get_section_lines(lines, "## Testing & Verification")
    if not found:
        warnings.append("missing section: ## Testing & Verification")
        return []

    commands: list[str] = []
    for section_line in section_lines:
        stripped_line = section_line.strip()
        list_match = re.match(r"^-\s+`(.+?)`$", stripped_line)
        if list_match:
            commands.append(list_match.group(1))
            continue

        plain_match = re.match(r"^-\s+(.+)$", stripped_line)
        if plain_match:
            commands.append(plain_match.group(1).strip())

    if not commands:
        warnings.append("section ## Testing & Verification has no commands")

    return commands


def _get_section_lines(lines: list[str], section_header: str) -> tuple[list[str], bool]:
    start_index: int | None = None
    for index, line in enumerate(lines):
        if line.strip().lower() == section_header.lower():
            start_index = index + 1
            break

    if start_index is None:
        return [], False

    collected_lines: list[str] = []
    for line in lines[start_index:]:
        if line.strip().startswith("## "):
            break
        collected_lines.append(line)

    return collected_lines, True


def _map_action(raw_action: str) -> str:
    valid_actions = {
        "READ",
        "CREATE",
        "EDIT",
        "DELETE",
        "MOVE",
        "RENAME",
        "TEST",
        "GIT",
    }
    return raw_action if raw_action in valid_actions else "UNKNOWN"
