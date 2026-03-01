from __future__ import annotations

from mss.engines.summary_details_validator import (
    extract_details_coverage,
    extract_files_affected,
    validate_details_against_files,
)


def test_extract_files_affected_happy_path_reads_backticks_and_bullets() -> None:
    summary_text = """
## Files to modify
- CREATE: `mss/engines/summary_details_validator.py`
1. tests/test_summary_details_validator.py
- EDIT: mss/tools/guard.py (optional)
""".strip()

    files_affected = extract_files_affected(summary_text)

    assert files_affected == [
        "mss/engines/summary_details_validator.py",
        "tests/test_summary_details_validator.py",
        "mss/tools/guard.py",
    ]


def test_extract_details_coverage_happy_path_supports_three_declared_formats() -> None:
    details_text = """
### `mss/engines/summary_details_validator.py`
- tests/test_summary_details_validator.py
FILE: mss\\tools\\guard.py (covered)
""".strip()

    covered_paths = extract_details_coverage(details_text)

    assert covered_paths == {
        "mss/engines/summary_details_validator.py",
        "tests/test_summary_details_validator.py",
        "mss/tools/guard.py",
    }


def test_validate_details_against_files_happy_path_reports_only_missing_entries() -> None:
    files_affected = [
        "mss/engines/summary_details_validator.py",
        "tests/test_summary_details_validator.py",
        "mss/tools/guard.py",
    ]
    covered_paths = {
        "mss/engines/summary_details_validator.py",
        "tests/test_summary_details_validator.py",
    }

    missing_paths = validate_details_against_files(files_affected, covered_paths)

    assert missing_paths == ["mss/tools/guard.py"]


def test_extractors_error_path_return_empty_for_invalid_inputs() -> None:
    assert extract_files_affected("") == []
    assert extract_files_affected(None) == []  # type: ignore[arg-type]
    assert extract_details_coverage("") == set()
    assert extract_details_coverage(None) == set()  # type: ignore[arg-type]


def test_validate_details_against_files_error_path_tolerates_invalid_collections() -> None:
    assert validate_details_against_files(None, set()) == []  # type: ignore[arg-type]
    assert validate_details_against_files(["mss/tools/guard.py"], None) == [  # type: ignore[arg-type]
        "mss/tools/guard.py"
    ]
