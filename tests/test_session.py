from __future__ import annotations

import json
from pathlib import Path
import sys

from mss.runner.bootstrap import bootstrap_tool_registry


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from mss_server.main import mcp_mss_connect, mcp_mss_set_mode, mcp_mss_status


TOOL_REGISTRY = bootstrap_tool_registry()
connect = TOOL_REGISTRY["mss.connect"]
status = TOOL_REGISTRY["mss.status"]
set_mode = TOOL_REGISTRY["mss.set_mode"]


def test_connect_creates_and_reuses_active_session(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MSS_SESSION_DIR", str(tmp_path))

    first_payload = connect()
    second_payload = connect()

    assert first_payload["ok"] is True
    assert first_payload["session_id"]
    assert first_payload["mode"] is None
    assert first_payload["artifacts"] == []
    assert first_payload["warnings"] == []
    assert first_payload["next_actions"] == [
        {"command": "debug", "description": "Skrót: ustawia tryb debug"},
        {"command": "workout", "description": "Skrót: ustawia tryb workout"},
        {"command": "mode debug", "description": "Uruchamia tryb debug"},
        {"command": "mode workout", "description": "Uruchamia tryb workout"},
    ]
    assert "Cześć, jaką operację chcesz wykonać?" in first_payload["message"]

    assert second_payload["session_id"] == first_payload["session_id"]
    assert second_payload["next_actions"] == first_payload["next_actions"]


def test_status_returns_connect_action_when_no_active_session(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MSS_SESSION_DIR", str(tmp_path))

    response_payload = status()

    assert response_payload["ok"] is False
    assert response_payload["session_id"] is None
    assert response_payload["mode"] is None
    assert response_payload["next_actions"] == [{"command": "connect", "description": "Połącz z MSS"}]
    assert response_payload["warnings"] == ["active_session_not_found"]


def test_status_next_actions_for_audit_mode_depends_on_audit_artifact(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MSS_SESSION_DIR", str(tmp_path))
    connect_payload = connect()
    set_mode(mode="audit")

    without_artifact_payload = status()
    assert without_artifact_payload["ok"] is True
    assert without_artifact_payload["mode"] == "audit"
    assert without_artifact_payload["next_actions"] == [
        {"command": "audit", "description": "Uruchom audyt kodu"}
    ]

    _set_session_artifacts(
        session_dir=tmp_path,
        session_id=str(connect_payload["session_id"]),
        artifacts=[{"name": "audit", "version": 1}],
    )

    with_artifact_payload = status()
    assert with_artifact_payload["next_actions"] == [
        {"command": "preplan", "description": "Przygotuj preplan na bazie audytu"},
        {"command": "show audit", "description": "Pokaż artefakt audytu"},
    ]


def test_status_next_actions_for_planning_mode_with_preplan_artifact(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MSS_SESSION_DIR", str(tmp_path))
    connect_payload = connect()
    set_mode(mode="planning")

    _set_session_artifacts(
        session_dir=tmp_path,
        session_id=str(connect_payload["session_id"]),
        artifacts=[{"name": "preplan", "version": 2}],
    )

    response_payload = status()

    assert response_payload["ok"] is True
    assert response_payload["mode"] == "planning"
    assert response_payload["next_actions"] == [
        {"command": "plan", "description": "Wygeneruj plan implementacji"}
    ]


def test_set_mode_persists_and_returns_deterministic_actions(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MSS_SESSION_DIR", str(tmp_path))
    connect()

    debug_payload = set_mode(mode="debug")
    assert debug_payload["ok"] is True
    assert debug_payload["mode"] == "debug"
    assert debug_payload["next_actions"] == [
        {"command": "audit", "description": "Uruchom audyt kodu"},
    ]

    run_payload = set_mode(mode="run")
    assert run_payload["ok"] is True
    assert run_payload["mode"] == "run"
    assert run_payload["next_actions"] == [
        {"command": "plan", "description": "Wygeneruj plan"},
        {"command": "status", "description": "Sprawdź stan sesji"},
    ]

    status_payload = status()
    assert status_payload["mode"] == "run"

    workout_payload = set_mode(mode="workout", project_name="TestProject")
    assert workout_payload["ok"] is True
    assert workout_payload["mode"] == "workout"
    assert workout_payload["next_actions"] == [
        {
            "command": "mss.workout",
            "description": "Rozpocznij sesję workout (notatki / burza mózgów)",
        },
        {"command": "status", "description": "Sprawdź stan sesji"},
    ]


def test_set_mode_returns_error_for_invalid_mode(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MSS_SESSION_DIR", str(tmp_path))
    connect()

    response_payload = set_mode(mode="unknown")

    assert response_payload["ok"] is False
    assert response_payload["session_id"] is None
    assert response_payload["mode"] is None
    assert response_payload["next_actions"] == [
        {"command": "status", "description": "Sprawdź aktualny stan"}
    ]
    assert response_payload["warnings"] == ["invalid_mode_value"]


def test_mcp_wrappers_call_session_tools(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MSS_SESSION_DIR", str(tmp_path))

    connect_payload = mcp_mss_connect()
    assert connect_payload["ok"] is True

    set_mode_payload = mcp_mss_set_mode(mode="workout", project_name="TestProject")
    assert set_mode_payload["ok"] is True
    assert set_mode_payload["mode"] == "workout"

    status_payload = mcp_mss_status()
    assert status_payload["ok"] is True
    assert status_payload["mode"] == "workout"


def test_connect_includes_projects_actions_and_resume_hints(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MSS_SESSION_DIR", str(tmp_path / "sessions"))
    projects_dir = tmp_path / "projects"
    monkeypatch.setenv("MSS_PROJECTS_DIR", str(projects_dir))

    _create_project_runtime(
        projects_dir=projects_dir,
        project_name="alpha",
        plan_id="plan-alpha",
        pipeline_status="complete",
        package_index=1,
        stage_index=2,
    )
    _create_project_runtime(
        projects_dir=projects_dir,
        project_name="beta",
        plan_id="plan-beta",
        pipeline_status="running",
        package_index=3,
        stage_index=4,
    )
    _create_project_runtime(
        projects_dir=projects_dir,
        project_name="gamma",
        plan_id="plan-gamma",
        pipeline_status=None,
        package_index=0,
        stage_index=0,
    )

    payload = connect()

    assert payload["ok"] is True
    assert "Wykryte projekty w `data/projects`:" in payload["message"]
    assert "alpha [complete]" in payload["message"]
    assert "beta [running, cursor=package:3 stage:4]" in payload["message"]
    assert "gamma [initialized]" in payload["message"]
    assert "kontynuacja: `stage_current" in payload["message"]

    next_commands = [entry["command"] for entry in payload["next_actions"]]
    assert any(command.startswith("plan_load_or_init plan-alpha ") for command in next_commands)
    assert any(command.startswith("plan_load_or_init plan-beta ") for command in next_commands)
    assert any(command.startswith("plan_load_or_init plan-gamma ") for command in next_commands)
    alpha_plan_dir = str((projects_dir / "alpha").resolve())
    beta_plan_dir = str((projects_dir / "beta").resolve())
    gamma_plan_dir = str((projects_dir / "gamma").resolve())

    assert f"stage_current {alpha_plan_dir}" not in next_commands
    assert f"stage_current {beta_plan_dir}" in next_commands
    assert f"stage_current {gamma_plan_dir}" not in next_commands


def test_status_includes_projects_actions_alongside_mode_actions(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MSS_SESSION_DIR", str(tmp_path / "sessions"))
    projects_dir = tmp_path / "projects"
    monkeypatch.setenv("MSS_PROJECTS_DIR", str(projects_dir))

    _create_project_runtime(
        projects_dir=projects_dir,
        project_name="delta",
        plan_id="plan-delta",
        pipeline_status="running",
        package_index=0,
        stage_index=1,
    )

    connect()
    set_mode(mode="audit")

    payload = status()
    assert payload["ok"] is True
    assert payload["mode"] == "audit"
    assert "Stan sesji:" in payload["message"]  # Fix B: dynamiczny message
    assert "delta [running, cursor=package:0 stage:1]" in payload["message"]

    next_commands = [entry["command"] for entry in payload["next_actions"]]
    assert "audit" in next_commands
    delta_plan_dir = str((projects_dir / "delta").resolve())
    assert f"plan_load_or_init plan-delta {delta_plan_dir}" in next_commands
    assert f"stage_current {delta_plan_dir}" in next_commands


def test_status_prioritizes_workout_gate_and_hides_project_hints(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MSS_SESSION_DIR", str(tmp_path / "sessions"))
    projects_dir = tmp_path / "projects"
    monkeypatch.setenv("MSS_PROJECTS_DIR", str(projects_dir))

    _create_project_runtime(
        projects_dir=projects_dir,
        project_name="epsilon",
        plan_id="plan-epsilon",
        pipeline_status="running",
        package_index=1,
        stage_index=1,
    )

    connect()
    set_mode(mode="workout", project_name="TestProject")

    payload = status()
    assert payload["ok"] is True
    assert payload["mode"] == "workout"
    assert "Stan sesji:" in payload["message"]  # Fix B: dynamiczny message
    assert payload["next_actions"] == [
        {
            "command": "mss.workout",
            "description": "Rozpocznij sesję workout (notatki / burza mózgów)",
        }
    ]


def test_status_prioritizes_debug_gate_with_end_debug_then_summarize_details(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MSS_SESSION_DIR", str(tmp_path))
    connect_payload = connect()
    set_mode(mode="debug")

    without_end_debug_payload = status()
    assert without_end_debug_payload["ok"] is True
    assert without_end_debug_payload["mode"] == "debug"
    assert without_end_debug_payload["next_actions"] == [
        {"command": "mss.end_debug", "description": "Zapisz end_debug"}
    ]

    _set_session_artifacts(
        session_dir=tmp_path,
        session_id=str(connect_payload["session_id"]),
        artifacts=[{"name": "end_debug", "version": 1}],
    )

    without_summarize_details_pass_payload = status()
    assert without_summarize_details_pass_payload["next_actions"] == [
        {"command": "mss.summarize_details", "description": "Uzupełnij summarize_details i doprowadź do PASS"}
    ]


def _set_session_artifacts(session_dir: Path, session_id: str, artifacts: list[dict[str, object]]) -> None:
    session_path = session_dir / f"{session_id}.json"
    session_payload = json.loads(session_path.read_text(encoding="utf-8"))
    session_payload["artifacts"] = artifacts
    session_path.write_text(json.dumps(session_payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _create_project_runtime(
    projects_dir: Path,
    project_name: str,
    plan_id: str,
    pipeline_status: str | None,
    package_index: int,
    stage_index: int,
) -> None:
    project_dir = projects_dir / project_name
    project_dir.mkdir(parents=True, exist_ok=True)
    plan_cache_payload = {
        "plan_id": plan_id,
        "packages": [],
        "stages_total": 0,
    }
    (project_dir / "plan_cache.json").write_text(
        json.dumps(plan_cache_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if pipeline_status is None:
        return

    state_payload = {
        "plan_id": plan_id,
        "rules_hash": "",
        "plan_hash": "",
        "cursor": {
            "package_index": package_index,
            "stage_index": stage_index,
        },
        "retry_count": 0,
        "max_retries": 2,
        "git": {
            "commit_mode": "wip_squash",
            "package_baseline_sha": None,
            "last_stage_commit_sha": None,
        },
        "pipeline_status": pipeline_status,
        "created_at": "2026-01-01T00:00:00+00:00",
        "last_updated_at": "2026-01-01T00:00:00+00:00",
        "sequence_hooks": {
            "guard_reported": False,
            "test_report_status": None,
        },
    }
    (project_dir / "state.json").write_text(
        json.dumps(state_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def test_set_mode_workout_requires_project_name(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MSS_SESSION_DIR", str(tmp_path))
    connect()

    # bez project_name — powinno zwrócić błąd
    response = set_mode(mode="workout")
    assert response["ok"] is False
    assert "project_name_required_for_workout" in response["warnings"]

    # z project_name — sukces
    response = set_mode(mode="workout", project_name="Projekt Alpha")
    assert response["ok"] is True
    assert response["mode"] == "workout"
    assert response["project_name"] == "Projekt Alpha"


def test_new_session_creates_fresh_session_and_archives_previous(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MSS_SESSION_DIR", str(tmp_path))
    first_payload = connect()
    first_session_id = first_payload["session_id"]
    assert first_payload["ok"] is True

    new_payload = TOOL_REGISTRY["mss.new_session"]()
    assert new_payload["ok"] is True
    assert new_payload["session_id"] != first_session_id
    assert new_payload["mode"] is None
    assert new_payload["project_name"] is None
    assert new_payload["artifacts"] == []

    # status powinien zwrócić nową sesję
    status_payload = status()
    assert status_payload["session_id"] == new_payload["session_id"]