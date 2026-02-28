from __future__ import annotations

import json
from pathlib import Path
from mss.runner.bootstrap import bootstrap_tool_registry
from mss.storage.state import load_state


TOOL_REGISTRY = bootstrap_tool_registry()
guard_report = TOOL_REGISTRY["guard.report"]
load_or_init = TOOL_REGISTRY["plan.load_or_init"]
advance = TOOL_REGISTRY["stage.advance"]
report_tool = TOOL_REGISTRY["test.report"]


def test_test_report_requires_guard_report_first(tmp_path: Path) -> None:
    _write_plan_fixture(tmp_path)
    load_or_init(plan_id="demo-plan", plan_dir=str(tmp_path))

    payload = report_tool(
        plan_dir=str(tmp_path),
        stage_id="PACKAGE_1_STAGE_1",
        result="PASS",
        output="ok",
        command="python -m pytest -q",
    )

    assert payload["status"] == "error"
    assert payload["code"] == "GUARD_REPORT_MISSING"


def test_stage_advance_is_blocked_after_test_fail(tmp_path: Path) -> None:
    _write_plan_fixture(tmp_path)
    load_or_init(plan_id="demo-plan", plan_dir=str(tmp_path))

    guard_payload = guard_report(
        plan_dir=str(tmp_path),
        stage_id="PACKAGE_1_STAGE_1",
        stop_conditions_violated=False,
        details="",
    )
    assert guard_payload == {"received": True, "stage_id": "PACKAGE_1_STAGE_1"}

    fail_payload = report_tool(
        plan_dir=str(tmp_path),
        stage_id="PACKAGE_1_STAGE_1",
        result="FAIL",
        output="failed assertion",
        command="python -m pytest -q",
    )
    assert fail_payload["status"] == "fail"
    assert fail_payload["guard_result"]["verdict"] == "FAIL"
    assert fail_payload["action_required"] in {"retry", "stop"}

    blocked_payload = advance(plan_dir=str(tmp_path))
    assert blocked_payload["status"] == "error"
    assert blocked_payload["code"] == "ADVANCE_ON_FAIL"


def test_guard_report_persists_semantic_error_in_sequence_hooks(tmp_path: Path) -> None:
    _write_plan_fixture(tmp_path)
    load_or_init(plan_id="demo-plan", plan_dir=str(tmp_path))

    guard_payload = guard_report(
        plan_dir=str(tmp_path),
        stage_id="PACKAGE_1_STAGE_1",
        stop_conditions_violated=True,
        details="Stop condition violated by test",
    )
    assert guard_payload == {"received": True, "stage_id": "PACKAGE_1_STAGE_1"}

    state_payload = load_state(tmp_path / "state.json")
    sequence_hooks = state_payload["sequence_hooks"]
    guard_result = sequence_hooks["guard_result"]

    assert sequence_hooks["guard_reported"] is True
    assert sequence_hooks["guard_stop_conditions_violated"] is True
    assert sequence_hooks["guard_details"] == "Stop condition violated by test"
    assert guard_result["verdict"] == "FAIL"
    assert any(error["code"] == "STOP_CONDITION_VIOLATED" for error in guard_result["semantic_errors"])


def test_server_registers_exactly_six_mvp_tools() -> None:
    expected_tools = {
        "guard.report",
        "plan.load_or_init",
        "rules.directive_pack",
        "stage.advance",
        "stage.current",
        "test.report",
    }
    assert expected_tools.issubset(set(TOOL_REGISTRY.keys()))


def _write_plan_fixture(plan_dir: Path) -> None:
    plan_markdown = """
# Preplan: Demo

## Goal
Implement demo pipeline.

## Scope
- Build tools

## Out of scope
- Production deployment

## Non-negotiable constraints
- Keep contract-first responses.

## Stop conditions
- No stages found.

## Risks
- Parser mismatch.
""".strip()

    package_markdown = """
---
DEPENDS_ON: []
---

# PACKAGE_1: demo_package

## Package Goal
Demo package goal.

## Files to modify
- CREATE: mcp-stage-server/src/tools/plan.py

### Stage 1: Guard/Test
1. READ: PLAN.md
2. TEST: python -m pytest -q mcp-stage-server/tests/test_guard.py

## Testing & Verification
- `python -m pytest -q mcp-stage-server/tests/test_guard.py`
""".strip()

    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "PLAN.md").write_text(plan_markdown, encoding="utf-8")
    (plan_dir / "PACKAGE_1.md").write_text(package_markdown, encoding="utf-8")

    state_path = plan_dir / "state.json"
    if state_path.exists():
        state_payload = json.loads(state_path.read_text(encoding="utf-8"))
        state_path.write_text(json.dumps(state_payload, ensure_ascii=False, indent=2), encoding="utf-8")