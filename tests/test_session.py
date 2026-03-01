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
        {"command": "status", "description": "Sprawdź stan sesji"},
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

    set_mode_payload = mcp_mss_set_mode(mode="workout")
    assert set_mode_payload["ok"] is True
    assert set_mode_payload["mode"] == "workout"

    status_payload = mcp_mss_status()
    assert status_payload["ok"] is True
    assert status_payload["mode"] == "workout"


def _set_session_artifacts(session_dir: Path, session_id: str, artifacts: list[dict[str, object]]) -> None:
    session_path = session_dir / f"{session_id}.json"
    session_payload = json.loads(session_path.read_text(encoding="utf-8"))
    session_payload["artifacts"] = artifacts
    session_path.write_text(json.dumps(session_payload, ensure_ascii=False, indent=2), encoding="utf-8")