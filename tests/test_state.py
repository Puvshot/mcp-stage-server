from pathlib import Path

import mss.storage.state as state_module


def test_create_initial_state_returns_state_snapshot_shape() -> None:
    state_snapshot = state_module.create_initial_state(
        plan_id="demo-plan",
        rules_hash="rules-hash",
        plan_hash="plan-hash",
    )

    assert state_snapshot["plan_id"] == "demo-plan"
    assert state_snapshot["rules_hash"] == "rules-hash"
    assert state_snapshot["plan_hash"] == "plan-hash"
    assert state_snapshot["cursor"] == {"package_index": 0, "stage_index": 0}
    assert state_snapshot["retry_count"] == 0
    assert state_snapshot["max_retries"] == 2
    assert state_snapshot["git"]["commit_mode"] == "wip_squash"
    assert state_snapshot["pipeline_status"] == "initializing"
    assert isinstance(state_snapshot["created_at"], str)
    assert isinstance(state_snapshot["last_updated_at"], str)


def test_save_state_atomic_writes_with_tmp_and_replace(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    state_path = tmp_path / "state.json"
    state_snapshot = state_module.create_initial_state(
        plan_id="demo-plan",
        rules_hash="rules-hash",
        plan_hash="plan-hash",
    )

    replace_calls: list[tuple[str | Path, str | Path]] = []
    original_replace = __import__("os").replace

    def track_replace(source_path: str | Path, target_path: str | Path) -> None:
        replace_calls.append((source_path, target_path))
        original_replace(source_path, target_path)

    monkeypatch.setattr("mss.storage.state.os.replace", track_replace)

    state_module.save_state_atomic(state_path, state_snapshot)

    assert state_path.exists()
    assert len(replace_calls) == 1
    source_path, target_path = replace_calls[0]
    assert str(source_path).endswith("state.json.tmp")
    assert str(target_path).endswith("state.json")


def test_save_state_atomic_and_load_state_roundtrip(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    state_snapshot = state_module.create_initial_state(
        plan_id="demo-plan",
        rules_hash="rules-hash",
        plan_hash="plan-hash",
    )
    state_snapshot["pipeline_status"] = "running"
    state_snapshot["last_updated_at"] = "2000-01-01T00:00:00+00:00"

    state_module.save_state_atomic(state_path, state_snapshot)
    loaded_state = state_module.load_state(state_path)

    assert loaded_state["plan_id"] == "demo-plan"
    assert loaded_state["pipeline_status"] == "running"
    assert loaded_state["last_updated_at"] != state_snapshot["last_updated_at"]
    assert not (tmp_path / "state.json.tmp").exists()
