from __future__ import annotations

import json
from pathlib import Path

import pytest

import mss.rules.loader as loader_module
from mss.runner import bootstrap as runner_bootstrap

rules_tool = runner_bootstrap._import_tool_module("rules")


def test_directive_pack_uses_json_ssot_and_stage_scope(tmp_path: Path) -> None:
    _write_plan_cache_fixture(tmp_path)

    package_generation_rules = loader_module.load_rules_payload("package_generation")
    response_payload = rules_tool.directive_pack(str(tmp_path), "PACKAGE_5_STAGE_1")

    assert "directive_pack" in response_payload
    directive_pack_payload = response_payload["directive_pack"]

    assert directive_pack_payload["stage_id"] == "PACKAGE_5_STAGE_1"
    assert directive_pack_payload["dominant_actions"] == ["READ", "TEST"]
    assert directive_pack_payload["must"][: len(package_generation_rules["always"]["must"])] == package_generation_rules["always"]["must"]
    assert directive_pack_payload["must_not"] == package_generation_rules["always"]["must_not"]

    read_directives = package_generation_rules["action_directives"]["READ"]["must"]
    test_directives = package_generation_rules["action_directives"]["TEST"]["must"]
    for expected_directive in [*read_directives, *test_directives]:
        assert expected_directive in directive_pack_payload["must"]


def test_directive_pack_has_no_fallback_and_returns_loader_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_plan_cache_fixture(tmp_path)

    missing_rules_error = loader_module.RulesLoadException(
        loader_module.RulesLoadError(
            code="MISSING_REQUIRED_RULES_KIND",
            message="Missing required rules kind 'package_generation'.",
            file_path=str(tmp_path / "data" / "rules_json" / "package_generation.json"),
            validation_issues=[],
        )
    )
    monkeypatch.setattr(rules_tool, "load_rules_payload", lambda _rules_kind: (_ for _ in ()).throw(missing_rules_error))

    response_payload = rules_tool.directive_pack(str(tmp_path), "PACKAGE_5_STAGE_1")

    assert response_payload["status"] == "error"
    assert response_payload["code"] == "MISSING_REQUIRED_RULES_KIND"


def test_directive_pack_is_deterministic_for_same_stage(tmp_path: Path) -> None:
    _write_plan_cache_fixture(tmp_path)

    first_response = rules_tool.directive_pack(str(tmp_path), "PACKAGE_5_STAGE_2")
    second_response = rules_tool.directive_pack(str(tmp_path), "PACKAGE_5_STAGE_2")

    first_pack = first_response["directive_pack"]
    second_pack = second_response["directive_pack"]

    assert first_pack["stage_id"] == second_pack["stage_id"]
    assert first_pack["dominant_actions"] == second_pack["dominant_actions"]
    assert first_pack["must"] == second_pack["must"]
    assert first_pack["must_not"] == second_pack["must_not"]
    assert first_pack["template"] == second_pack["template"]
    assert first_pack["token_estimate"] == second_pack["token_estimate"]


def _write_plan_cache_fixture(plan_dir: Path) -> None:
    plan_cache_payload = {
        "plan_id": "updaterules",
        "plan_name": "Updaterules",
        "created_at": "2026-01-01T00:00:00+00:00",
        "source_format": "markdown",
        "goal": "goal",
        "scope": [],
        "out_of_scope": [],
        "constraints": [],
        "stop_conditions": ["stop-1", "stop-2"],
        "risks": [],
        "rules_hash": "rules",
        "plan_hash": "plan",
        "stages_total": 2,
        "packages": [
            {
                "package_id": "PACKAGE_5",
                "package_name": "tests_and_regressions",
                "depends_on": [],
                "goal": "goal",
                "files_to_modify": [],
                "verification_commands": [],
                "status": "in_progress",
                "completed_at": None,
                "stages": [
                    {
                        "stage_id": "PACKAGE_5_STAGE_1",
                        "stage_number": 1,
                        "stage_name": "Directive pack",
                        "steps": [],
                        "test_command": "python -m pytest -q tests/test_rules_directive_pack.py",
                        "dominant_actions": ["READ", "TEST"],
                        "files_in_scope": ["src/tools/rules.py"],
                        "status": "pending",
                        "retry_count": 0,
                        "last_error": None,
                    },
                    {
                        "stage_id": "PACKAGE_5_STAGE_2",
                        "stage_number": 2,
                        "stage_name": "Alternative actions",
                        "steps": [],
                        "test_command": "python -m pytest -q tests/test_rules_directive_pack.py",
                        "dominant_actions": ["CREATE"],
                        "files_in_scope": ["src/tools/exec_bundle.py"],
                        "status": "pending",
                        "retry_count": 0,
                        "last_error": None,
                    },
                ],
            }
        ],
    }

    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "plan_cache.json").write_text(json.dumps(plan_cache_payload, ensure_ascii=False, indent=2), encoding="utf-8")