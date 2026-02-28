from __future__ import annotations

import json
from pathlib import Path

from mss.tools.collision import analyze as collision_analyze


def test_collision_analyze_returns_warning_and_critical_findings(tmp_path: Path) -> None:
    _write_collision_fixture(tmp_path)

    payload = collision_analyze(plan_dir=str(tmp_path), stage_id="PACKAGE_1_STAGE_1")

    assert payload["status"] == "ok"
    assert payload["stage_id"] == "PACKAGE_1_STAGE_1"
    assert payload["package_id"] == "PACKAGE_1"

    findings = payload["findings"]
    assert isinstance(findings, list)
    assert any(finding["code"] == "FILE_COLLISION_WITHIN_PACKAGE" for finding in findings)
    assert any(finding["code"] == "FILE_NOT_IN_SCOPE_CRITICAL" for finding in findings)

    summary = payload["summary"]
    assert summary["findings_total"] == len(findings)
    assert summary["blocking_count"] == 1


def test_collision_analyze_returns_error_for_missing_stage(tmp_path: Path) -> None:
    _write_collision_fixture(tmp_path)

    payload = collision_analyze(plan_dir=str(tmp_path), stage_id="PACKAGE_X_STAGE_99")

    assert payload["status"] == "error"
    assert payload["code"] == "STAGE_NOT_FOUND"


def _write_collision_fixture(plan_dir: Path) -> None:
    plan_cache = {
        "plan_id": "demo",
        "plan_name": "Demo Plan",
        "created_at": "2026-01-01T00:00:00+00:00",
        "source_format": "markdown",
        "goal": "Goal",
        "scope": [],
        "out_of_scope": [],
        "constraints": [],
        "stop_conditions": [],
        "risks": [],
        "rules_hash": "rules-hash",
        "plan_hash": "plan-hash",
        "stages_total": 3,
        "packages": [
            {
                "package_id": "PACKAGE_1",
                "package_name": "Package One",
                "depends_on": [],
                "goal": "Goal",
                "files_to_modify": [
                    {"path": "src/shared.py", "action": "EDIT", "is_smoke_test": False, "unknown": None},
                    {"path": "src/feature.py", "action": "EDIT", "is_smoke_test": False, "unknown": None},
                ],
                "verification_commands": [],
                "status": "pending",
                "completed_at": None,
                "stages": [
                    {
                        "stage_id": "PACKAGE_1_STAGE_1",
                        "stage_number": 1,
                        "stage_name": "Stage 1",
                        "steps": [],
                        "test_command": None,
                        "dominant_actions": ["EDIT"],
                        "files_in_scope": ["src/shared.py", "src/feature.py"],
                        "status": "pending",
                        "retry_count": 0,
                        "last_error": None,
                    },
                    {
                        "stage_id": "PACKAGE_1_STAGE_2",
                        "stage_number": 2,
                        "stage_name": "Stage 2",
                        "steps": [],
                        "test_command": None,
                        "dominant_actions": ["EDIT"],
                        "files_in_scope": ["src/shared.py"],
                        "status": "pending",
                        "retry_count": 0,
                        "last_error": None,
                    },
                ],
            },
            {
                "package_id": "PACKAGE_2",
                "package_name": "Package Two",
                "depends_on": [],
                "goal": "Goal",
                "files_to_modify": [
                    {"path": "src/feature.py", "action": "EDIT", "is_smoke_test": False, "unknown": None}
                ],
                "verification_commands": [],
                "status": "pending",
                "completed_at": None,
                "stages": [
                    {
                        "stage_id": "PACKAGE_2_STAGE_1",
                        "stage_number": 1,
                        "stage_name": "Stage 1",
                        "steps": [],
                        "test_command": None,
                        "dominant_actions": ["EDIT"],
                        "files_in_scope": ["src/feature.py"],
                        "status": "pending",
                        "retry_count": 0,
                        "last_error": None,
                    }
                ],
            },
        ],
    }

    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "plan_cache.json").write_text(json.dumps(plan_cache, ensure_ascii=False, indent=2), encoding="utf-8")
