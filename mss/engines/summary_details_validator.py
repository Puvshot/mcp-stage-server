from __future__ import annotations

import re


_ACTION_PREFIXES_PATTERN = re.compile(
    r"^(?:CREATE|EDIT|DELETE|MOVE|RENAME|UPDATE|READ|WRITE|TEST|ADD|REMOVE):\s*",
    flags=re.IGNORECASE,
)


def extract_files_affected(summary_text: str) -> list[str]:
    """Extract normalized file paths mentioned in summary text.

    The function is read-only and idempotent. It accepts mixed formatting and
    returns unique paths while preserving first-seen order.
    """
    if not isinstance(summary_text, str) or not summary_text.strip():
        return []

    extracted_paths: list[str] = []

    for backticked_match in re.findall(r"`([^`]+)`", summary_text):
        normalized_path = _normalize_path(backticked_match)
        if normalized_path is not None and normalized_path not in extracted_paths:
            extracted_paths.append(normalized_path)

    for raw_line in summary_text.splitlines():
        line_candidate = raw_line.strip()
        if not line_candidate:
            continue

        line_candidate = re.sub(r"^[-*]\s+", "", line_candidate)
        line_candidate = re.sub(r"^\d+\.\s+", "", line_candidate)
        line_candidate = _ACTION_PREFIXES_PATTERN.sub("", line_candidate)

        normalized_path = _normalize_path(line_candidate)
        if normalized_path is not None and normalized_path not in extracted_paths:
            extracted_paths.append(normalized_path)

    return extracted_paths


def extract_details_coverage(details_text: str) -> set[str]:
    """Extract normalized file paths covered in details text.

    Supported formats per file:
    - `### <path>`
    - `- <path>` / `1. <path>`
    - `FILE: <path>`
    """
    if not isinstance(details_text, str) or not details_text.strip():
        return set()

    covered_paths: set[str] = set()

    for raw_line in details_text.splitlines():
        line_candidate = raw_line.strip()
        if not line_candidate:
            continue

        maybe_path: str | None = None

        heading_match = re.match(r"^###\s+(.+)$", line_candidate)
        if heading_match is not None:
            maybe_path = heading_match.group(1)
        else:
            file_match = re.match(r"^FILE:\s+(.+)$", line_candidate, flags=re.IGNORECASE)
            if file_match is not None:
                maybe_path = file_match.group(1)
            else:
                list_match = re.match(r"^(?:[-*]|\d+\.)\s+(.+)$", line_candidate)
                if list_match is not None:
                    maybe_path = list_match.group(1)

        if maybe_path is None:
            continue

        normalized_path = _normalize_path(maybe_path)
        if normalized_path is not None:
            covered_paths.add(normalized_path)

    return covered_paths


def validate_details_against_files(files_affected: list[str], covered: set[str]) -> list[str]:
    """Return affected file paths that are missing in details coverage."""
    if not isinstance(files_affected, list):
        return []
    if not isinstance(covered, set):
        covered = set()

    missing_paths: list[str] = []
    normalized_covered = {
        normalized_path
        for raw_path in covered
        for normalized_path in [_normalize_path(raw_path)]
        if normalized_path is not None
    }

    for raw_path in files_affected:
        normalized_path = _normalize_path(raw_path)
        if normalized_path is None:
            continue
        if normalized_path in normalized_covered:
            continue
        if normalized_path in missing_paths:
            continue
        missing_paths.append(normalized_path)

    return missing_paths


def _normalize_path(raw_path: str) -> str | None:
    if not isinstance(raw_path, str):
        return None

    normalized_path = raw_path.strip()
    if not normalized_path:
        return None

    normalized_path = normalized_path.strip("`")
    normalized_path = re.sub(r"\s*\([^)]*\)\s*$", "", normalized_path)
    normalized_path = normalized_path.rstrip(".,:;")
    normalized_path = _ACTION_PREFIXES_PATTERN.sub("", normalized_path)
    normalized_path = normalized_path.strip()

    if not _looks_like_path(normalized_path):
        return None

    return normalized_path.replace("\\", "/")


def _looks_like_path(path_candidate: str) -> bool:
    if not path_candidate:
        return False
    if " " in path_candidate:
        return False
    if "/" in path_candidate or "\\" in path_candidate:
        return True
    if re.search(r"\.[A-Za-z0-9]{1,8}$", path_candidate):
        return True
    return False
