from __future__ import annotations

import json
from pathlib import Path

from mss.tools.audit import clear as audit_clear
from mss.tools.audit import tail as audit_tail
from mss.tools.execution_log import append as execution_log_append
from mss.tools.execution_log import read as execution_log_read


def test_execution_log_append_and_read_happy_path(tmp_path: Path) -> None:
    _write_plan_cache_fixture(tmp_path)
    _write_state_fixture(tmp_path)

    append_payload = execution_log_append(
        plan_dir=str(tmp_path),
        plan_id="mcp-stage-server-full",
        package_id="PACKAGE_3",
        narrative="Zaimplementowano execution_log i audit.",
    )

    assert append_payload["status"] == "appended"
    assert append_payload["entry_index"] == 0

    read_payload = execution_log_read(plan_dir=str(tmp_path), plan_id="mcp-stage-server-full")

    assert read_payload["plan_id"] == "mcp-stage-server-full"
    assert len(read_payload["entries"]) == 1
    entry = read_payload["entries"][0]
    assert entry["package_id"] == "PACKAGE_3"
    assert entry["narrative"] == "Zaimplementowano execution_log i audit."
    assert entry["stages_completed"] == ["PACKAGE_3_STAGE_1"]
    assert entry["retries_total"] == 1
    assert entry["files_modified"] == ["src/tools/execution_log.py", "src/tools/audit.py"]
    assert entry["test_results"]["command"] == "python -m pytest -q tests/test_execution_log.py"
    assert entry["test_results"]["result"] == "PASS"


def test_execution_log_append_returns_error_for_missing_package(tmp_path: Path) -> None:
    _write_plan_cache_fixture(tmp_path)

    payload = execution_log_append(
        plan_dir=str(tmp_path),
        plan_id="mcp-stage-server-full",
        package_id="PACKAGE_X",
        narrative="narracja",
    )

    assert payload["status"] == "error"
    assert payload["code"] == "PACKAGE_NOT_FOUND"


def test_execution_log_read_validates_last_n(tmp_path: Path) -> None:
    _write_plan_cache_fixture(tmp_path)

    payload = execution_log_read(plan_dir=str(tmp_path), plan_id="mcp-stage-server-full", last_n=0)

    assert payload["status"] == "error"
    assert payload["code"] == "INVALID_LAST_N"


def test_audit_tail_and_clear_happy_path(tmp_path: Path) -> None:
    audit_log_path = tmp_path / "mcp_audit.log"
    audit_log_path.write_text("line-1\nline-2\nline-3\n", encoding="utf-8")

    tail_payload = audit_tail(plan_dir=str(tmp_path), last_n=2)
    assert tail_payload["status"] == "ok"
    assert tail_payload["entries"] == ["line-2", "line-3"]
    assert tail_payload["count"] == 2

    clear_payload = audit_clear(plan_dir=str(tmp_path))
    assert clear_payload["status"] == "cleared"
    assert clear_payload["removed_entries"] == 3
    assert audit_log_path.read_text(encoding="utf-8") == ""


def test_audit_tail_validates_last_n(tmp_path: Path) -> None:
    payload = audit_tail(plan_dir=str(tmp_path), last_n=-1)

    assert payload["status"] == "error"
    assert payload["code"] == "INVALID_LAST_N"


def _write_plan_cache_fixture(plan_dir: Path) -> None:
    plan_cache_payload = {
        "plan_id": "mcp-stage-server-full",
        "plan_name": "Full",
        "created_at": "2026-01-01T00:00:00+00:00",
        "source_format": "markdown",
        "goal": "goal",
        "scope": [],
        "out_of_scope": [],
        "constraints": [],
        "stop_conditions": [],
        "risks": [],
        "rules_hash": "rules",
        "plan_hash": "plan",
        "stages_total": 1,
        "packages": [
            {
                "package_id": "PACKAGE_3",
                "package_name": "execution_log_and_audit",
                "depends_on": [],
                "goal": "goal",
                "files_to_modify": [
                    {
                        "path": "src/tools/execution_log.py",
                        "action": "CREATE",
                        "is_smoke_test": False,
                        "unknown": None,
                    },
                    {
                        "path": "src/tools/audit.py",
                        "action": "CREATE",
                        "is_smoke_test": False,
                        "unknown": None,
                    },
                ],
                "verification_commands": ["python -m pytest -q tests/test_execution_log.py"],
                "status": "in_progress",
                "completed_at": None,
                "stages": [
                    {
                        "stage_id": "PACKAGE_3_STAGE_1",
                        "stage_number": 1,
                        "stage_name": "Execution log",
                        "steps": [],
                        "test_command": "python -m pytest -q tests/test_execution_log.py",
                        "dominant_actions": ["CREATE", "TEST"],
                        "files_in_scope": ["src/tools/execution_log.py", "src/tools/audit.py"],
                        "status": "pending",
                        "retry_count": 1,
                        "last_error": {
                            "verdict": "PASS",
                            "mechanical_errors": [
                                {
                                    "code": "FILE_NOT_IN_SCOPE_CREATED",
                                    "message": "warning",
                                    "file": "tmp/generated.txt",
                                    "severity": "warning",
                                }
                            ],
                            "semantic_errors": [],
                            "total_errors": 1,
                            "checked_at": "2026-01-01T00:00:00+00:00",
                        },
                    }
                ],
            }
        ],
    }

    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "plan_cache.json").write_text(
        json.dumps(plan_cache_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_state_fixture(plan_dir: Path) -> None:
    state_payload = {
        "plan_id": "mcp-stage-server-full",
        "rules_hash": "rules",
        "plan_hash": "plan",
        "cursor": {"package_index": 0, "stage_index": 0},
        "retry_count": 0,
        "max_retries": 2,
        "git": {
            "commit_mode": "wip_squash",
            "package_baseline_sha": None,
            "last_stage_commit_sha": None,
        },
        "pipeline_status": "running",
        "sequence_hooks": {
            "guard_reported": True,
            "test_report_status": "ready_to_advance",
        },
        "created_at": "2026-01-01T00:00:00+00:00",
        "last_updated_at": "2026-01-01T00:00:00+00:00",
    }
    (plan_dir / "state.json").write_text(json.dumps(state_payload, ensure_ascii=False, indent=2), encoding="utf-8")