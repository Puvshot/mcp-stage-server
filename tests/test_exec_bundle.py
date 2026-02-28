from __future__ import annotations

import hashlib
import json
from pathlib import Path

from mss.rules.loader import load_rules_payload
from mss.tools.exec_bundle import directive_bundle


def test_exec_directive_bundle_returns_contract_fields_and_identifiers(tmp_path: Path) -> None:
    _write_plan_cache_fixture(tmp_path)

    response_payload = directive_bundle(str(tmp_path), "PACKAGE_5_STAGE_1", char_limit=12000)

    assert "directive_bundle" in response_payload
    bundle_payload = response_payload["directive_bundle"]
    assert bundle_payload["package_id"] == "PACKAGE_5"
    assert bundle_payload["stage_id"] == "PACKAGE_5_STAGE_1"
    assert isinstance(bundle_payload["prompt_text"], str)
    assert bundle_payload["prompt_characters"] == len(bundle_payload["prompt_text"])
    assert bundle_payload["char_limit"] == 12000

    rules_payload = load_rules_payload("package_generation")
    expected_hash = hashlib.sha256(
        json.dumps(rules_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    assert bundle_payload["RULESET_HASH"] == expected_hash

    used_identifiers = bundle_payload["used_rule_identifiers"]
    assert used_identifiers["rules_kind"] == "package_generation"
    assert used_identifiers["dominant_actions"] == ["READ", "TEST"]
    assert used_identifiers["always"]["must"]
    assert used_identifiers["always"]["must_not"]
    assert any(identifier.startswith("action_directives.READ") for identifier in used_identifiers["action_directives"])
    assert any(identifier.startswith("action_directives.TEST") for identifier in used_identifiers["action_directives"])


def test_exec_directive_bundle_trimming_is_deterministic_and_keeps_non_trimmable_sections(tmp_path: Path) -> None:
    _write_plan_cache_fixture(tmp_path)

    too_low_payload = directive_bundle(str(tmp_path), "PACKAGE_5_STAGE_1", char_limit=1)
    assert too_low_payload["status"] == "error"
    assert too_low_payload["code"] == "CHAR_LIMIT_TOO_LOW"

    required_minimum = int(too_low_payload["required_minimum"])
    target_limit = required_minimum + 50

    first_payload = directive_bundle(str(tmp_path), "PACKAGE_5_STAGE_1", char_limit=target_limit)
    second_payload = directive_bundle(str(tmp_path), "PACKAGE_5_STAGE_1", char_limit=target_limit)

    first_bundle = first_payload["directive_bundle"]
    second_bundle = second_payload["directive_bundle"]
    assert first_bundle["prompt_text"] == second_bundle["prompt_text"]
    assert first_bundle["trimmed"] is True
    assert first_bundle["prompt_characters"] <= target_limit

    prompt_text = first_bundle["prompt_text"]
    assert "SCOPE (NON-TRIMMABLE):" in prompt_text
    assert "PROHIBITIONS (NON-TRIMMABLE):" in prompt_text
    assert "STOP CONDITIONS (NON-TRIMMABLE):" in prompt_text
    assert "TEST COMMAND (NON-TRIMMABLE):" in prompt_text
    assert "src/tools/exec_bundle.py" in prompt_text
    assert "python -m pytest -q tests/test_exec_bundle.py" in prompt_text


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
        "stop_conditions": ["stop-condition-1", "stop-condition-2"],
        "risks": [],
        "rules_hash": "rules",
        "plan_hash": "plan",
        "stages_total": 1,
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
                        "stage_name": "Exec bundle",
                        "steps": [],
                        "test_command": "python -m pytest -q tests/test_exec_bundle.py",
                        "dominant_actions": ["READ", "TEST"],
                        "files_in_scope": ["src/tools/exec_bundle.py", "src/tools/rules.py"],
                        "status": "pending",
                        "retry_count": 0,
                        "last_error": None,
                    }
                ],
            }
        ],
    }

    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "plan_cache.json").write_text(json.dumps(plan_cache_payload, ensure_ascii=False, indent=2), encoding="utf-8")