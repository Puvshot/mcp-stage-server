from __future__ import annotations

import json
from pathlib import Path
from mss.runner.bootstrap import bootstrap_tool_registry


TOOL_REGISTRY = bootstrap_tool_registry()
load_or_init = TOOL_REGISTRY["plan.load_or_init"]
advance = TOOL_REGISTRY["stage.advance"]
current = TOOL_REGISTRY["stage.current"]
peek_next = TOOL_REGISTRY["stage.peek_next"]
rewind = TOOL_REGISTRY["stage.rewind"]


def test_plan_load_or_init_initializes_cache_and_state(tmp_path: Path) -> None:
    _write_plan_fixture(tmp_path)

    response_payload = load_or_init(plan_id="demo-plan", plan_dir=str(tmp_path))

    assert response_payload["status"] == "initialized"
    assert response_payload["plan_id"] == "demo-plan"
    assert response_payload["stages_total"] == 2
    assert isinstance(response_payload["warnings"], list)
    assert response_payload["parse_warnings"] == len(response_payload["warnings"])

    cache_path = tmp_path / "plan_cache.json"
    state_path = tmp_path / "state.json"
    assert cache_path.exists()
    assert state_path.exists()

    cached_payload = json.loads(cache_path.read_text(encoding="utf-8"))
    assert cached_payload["plan_id"] == "demo-plan"
    assert len(cached_payload["packages"]) == 1

    state_payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert state_payload["pipeline_status"] == "running"
    assert state_payload["sequence_hooks"]["guard_reported"] is False
    assert state_payload["sequence_hooks"]["test_report_status"] is None


def test_stage_current_returns_active_stage_position(tmp_path: Path) -> None:
    _write_plan_fixture(tmp_path)
    load_or_init(plan_id="demo-plan", plan_dir=str(tmp_path))

    current_payload = current(plan_dir=str(tmp_path))

    assert current_payload["package_id"] == "PACKAGE_1"
    assert current_payload["position"]["package_index"] == 0
    assert current_payload["position"]["stage_index"] == 0
    assert current_payload["position"]["stages_in_package"] == 2
    assert current_payload["position"]["packages_total"] == 1
    assert current_payload["stage"]["stage_id"] == "PACKAGE_1_STAGE_1"
    assert current_payload["collision"]["status"] == "ok"
    assert isinstance(current_payload["collision"]["findings"], list)


def test_stage_advance_enforces_sequence_and_advances_on_ready_to_advance(tmp_path: Path) -> None:
    _write_plan_fixture(tmp_path)
    load_or_init(plan_id="demo-plan", plan_dir=str(tmp_path))

    blocked_payload = advance(plan_dir=str(tmp_path))
    assert blocked_payload["status"] == "error"
    assert blocked_payload["code"] == "ADVANCE_WITHOUT_TEST_REPORT"

    state_path = tmp_path / "state.json"
    state_payload = json.loads(state_path.read_text(encoding="utf-8"))
    state_payload["sequence_hooks"] = {
        "guard_reported": True,
        "test_report_status": "ready_to_advance",
    }
    state_path.write_text(json.dumps(state_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    first_advance_payload = advance(plan_dir=str(tmp_path))
    assert first_advance_payload["pipeline_status"] == "running"
    assert first_advance_payload["package_done"] is False
    assert first_advance_payload["next_stage_id"] == "PACKAGE_1_STAGE_2"
    assert first_advance_payload["collision"]["status"] == "ok"

    state_payload = json.loads(state_path.read_text(encoding="utf-8"))
    state_payload["sequence_hooks"] = {
        "guard_reported": True,
        "test_report_status": "ready_to_advance",
    }
    state_path.write_text(json.dumps(state_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    final_advance_payload = advance(plan_dir=str(tmp_path))
    assert final_advance_payload["pipeline_status"] == "complete"
    assert final_advance_payload["package_done"] is True
    assert final_advance_payload["package_id"] == "PACKAGE_1"
    assert final_advance_payload["git_instruction"]["squash_verified"] is True


def test_stage_peek_next_returns_next_stage_without_cursor_mutation(tmp_path: Path) -> None:
    _write_plan_fixture(tmp_path)
    load_or_init(plan_id="demo-plan", plan_dir=str(tmp_path))

    peek_payload = peek_next(plan_dir=str(tmp_path))
    assert peek_payload["status"] == "ok"
    assert peek_payload["has_next"] is True
    assert peek_payload["next_stage"]["stage_id"] == "PACKAGE_1_STAGE_2"
    assert peek_payload["collision"]["status"] == "ok"

    current_payload = current(plan_dir=str(tmp_path))
    assert current_payload["stage"]["stage_id"] == "PACKAGE_1_STAGE_1"


def test_stage_rewind_moves_cursor_to_previous_stage(tmp_path: Path) -> None:
    _write_plan_fixture(tmp_path)
    load_or_init(plan_id="demo-plan", plan_dir=str(tmp_path))

    state_path = tmp_path / "state.json"
    state_payload = json.loads(state_path.read_text(encoding="utf-8"))
    state_payload["sequence_hooks"] = {
        "guard_reported": True,
        "test_report_status": "ready_to_advance",
    }
    state_path.write_text(json.dumps(state_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    advance_payload = advance(plan_dir=str(tmp_path))
    assert advance_payload["next_stage_id"] == "PACKAGE_1_STAGE_2"

    rewound_payload = rewind(plan_dir=str(tmp_path), reason="manual retry")
    assert rewound_payload["status"] == "rewound"
    assert rewound_payload["rewound_to"] == "PACKAGE_1_STAGE_1"
    assert rewound_payload["retry_count"] == 0


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

### Stage 1: Init
1. READ: PLAN.md
2. TEST: python -m pytest -q mcp-stage-server/tests/test_state.py

### Stage 2: Advance
1. EDIT: mcp-stage-server/src/tools/stage.py
2. TEST: python -m pytest -q mcp-stage-server/tests/test_tools.py

## Testing & Verification
- `python -m pytest -q mcp-stage-server/tests/test_tools.py`
""".strip()

    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "PLAN.md").write_text(plan_markdown, encoding="utf-8")
    (plan_dir / "PACKAGE_1.md").write_text(package_markdown, encoding="utf-8")