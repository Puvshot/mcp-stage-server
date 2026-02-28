from __future__ import annotations

from pathlib import Path

from mss.storage.state import load_state
from mss.tools.guard import report as guard_report
from mss.tools.plan import load_or_init


def test_guard_report_warning_only_collision_does_not_set_blocking_flag(tmp_path: Path) -> None:
    _write_warning_only_plan_fixture(tmp_path)
    load_or_init(plan_id="demo-plan", plan_dir=str(tmp_path))

    response_payload = guard_report(
        plan_dir=str(tmp_path),
        stage_id="PACKAGE_1_STAGE_1",
        stop_conditions_violated=False,
        details="",
    )
    assert response_payload == {"received": True, "stage_id": "PACKAGE_1_STAGE_1"}

    state_payload = load_state(tmp_path / "state.json")
    sequence_hooks = state_payload["sequence_hooks"]
    guard_result = sequence_hooks["guard_result"]

    assert sequence_hooks["guard_has_blocking_errors"] is False
    assert guard_result["verdict"] == "PASS"
    assert any(error["code"] == "FILE_COLLISION_WITHIN_PACKAGE" for error in guard_result["mechanical_errors"])


def test_guard_report_cross_package_collision_sets_blocking_flag(tmp_path: Path) -> None:
    _write_cross_package_collision_plan_fixture(tmp_path)
    load_or_init(plan_id="demo-plan", plan_dir=str(tmp_path))

    response_payload = guard_report(
        plan_dir=str(tmp_path),
        stage_id="PACKAGE_1_STAGE_1",
        stop_conditions_violated=False,
        details="",
    )
    assert response_payload == {"received": True, "stage_id": "PACKAGE_1_STAGE_1"}

    state_payload = load_state(tmp_path / "state.json")
    sequence_hooks = state_payload["sequence_hooks"]
    guard_result = sequence_hooks["guard_result"]

    assert sequence_hooks["guard_has_blocking_errors"] is True
    assert guard_result["verdict"] == "FAIL"
    assert any(error["code"] == "FILE_NOT_IN_SCOPE_CRITICAL" for error in guard_result["mechanical_errors"])


def _write_warning_only_plan_fixture(plan_dir: Path) -> None:
    plan_markdown = """
# Preplan: Demo Full Guard

## Goal
Validate guard behavior.

## Scope
- Guard checks

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
- EDIT: src/tools/stage.py

### Stage 1: Guard warning check
1. EDIT: src/tools/stage.py
2. TEST: python -m pytest -q tests/test_guard_full.py

### Stage 2: Follow-up stage with overlap
1. EDIT: src/tools/stage.py
2. TEST: python -m pytest -q tests/test_guard_full.py

## Testing & Verification
- `python -m pytest -q tests/test_guard_full.py`
""".strip()

    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "PLAN.md").write_text(plan_markdown, encoding="utf-8")
    (plan_dir / "PACKAGE_1.md").write_text(package_markdown, encoding="utf-8")


def _write_cross_package_collision_plan_fixture(plan_dir: Path) -> None:
    plan_markdown = """
# Preplan: Demo Full Guard

## Goal
Validate cross-package collisions.

## Scope
- Guard checks

## Out of scope
- Production deployment

## Non-negotiable constraints
- Keep contract-first responses.

## Stop conditions
- No stages found.

## Risks
- Parser mismatch.
""".strip()

    package_1_markdown = """
---
DEPENDS_ON: []
---

# PACKAGE_1: demo_package_1

## Package Goal
Demo package goal.

## Files to modify
- EDIT: src/tools/stage.py

### Stage 1: Guard cross package check
1. EDIT: src/tools/stage.py
2. TEST: python -m pytest -q tests/test_guard_full.py

## Testing & Verification
- `python -m pytest -q tests/test_guard_full.py`
""".strip()

    package_2_markdown = """
---
DEPENDS_ON: [PACKAGE_1]
---

# PACKAGE_2: demo_package_2

## Package Goal
Second package goal.

## Files to modify
- EDIT: src/tools/stage.py

### Stage 1: Future stage
1. EDIT: src/tools/stage.py
2. TEST: python -m pytest -q tests/test_guard_full.py

## Testing & Verification
- `python -m pytest -q tests/test_guard_full.py`
""".strip()

    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "PLAN.md").write_text(plan_markdown, encoding="utf-8")
    (plan_dir / "PACKAGE_1.md").write_text(package_1_markdown, encoding="utf-8")
    (plan_dir / "PACKAGE_2.md").write_text(package_2_markdown, encoding="utf-8")