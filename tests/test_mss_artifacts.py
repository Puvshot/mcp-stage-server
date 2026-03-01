from __future__ import annotations

from pathlib import Path
import sys

from mss.runner.bootstrap import bootstrap_tool_registry
from mss.storage.artifact_store import save_artifact
from mss.tools.mss_artifacts import capabilities, get_artifact, list_artifacts
from mss.tools.session import connect


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from mss_server.main import (
    mcp_mss_audit,
    mcp_mss_capabilities,
    mcp_mss_debug,
    mcp_mss_end_debug,
    mcp_mss_end_workout,
    mcp_mss_get_artifact,
    mcp_mss_list_artifacts,
    mcp_mss_package,
    mcp_mss_planning,
    mcp_mss_prepare,
    mcp_mss_run,
    mcp_mss_summarize,
    mcp_mss_summarize_details,
    mcp_mss_workout,
)


TOOL_REGISTRY = bootstrap_tool_registry()

def test_artifact_tools_require_active_session(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MSS_SESSION_DIR", str(tmp_path))

    capabilities_payload = capabilities()
    list_payload = list_artifacts()
    get_payload = get_artifact(name="audit")

    assert capabilities_payload["ok"] is False
    assert capabilities_payload["next_actions"] == [{"command": "connect", "description": "Połącz z MSS"}]

    assert list_payload["ok"] is False
    assert list_payload["next_actions"] == [{"command": "connect", "description": "Połącz z MSS"}]

    assert get_payload["ok"] is False
    assert get_payload["next_actions"] == [{"command": "connect", "description": "Połącz z MSS"}]


def test_capabilities_list_and_get_for_active_session(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MSS_SESSION_DIR", str(tmp_path))
    connect_payload = connect()
    assert connect_payload["ok"] is True

    saved_artifact = save_artifact(
        session_dir=tmp_path,
        session_id=str(connect_payload["session_id"]),
        artifact_name="audit",
        artifact_payload={"summary": "ok"},
    )
    assert saved_artifact is not None

    capabilities_payload = capabilities()
    assert capabilities_payload["ok"] is True
    assert capabilities_payload["capabilities"] == [
        "capabilities",
        "list_artifacts",
        "get_artifact",
        "workout",
        "end_workout",
        "summarize",
        "summarize_details",
        "audit",
        "prepare",
        "planning",
        "package",
        "run",
        "debug",
        "end_debug",
    ]

    list_payload = list_artifacts()
    assert list_payload["ok"] is True
    assert len(list_payload["artifacts"]) == 1
    assert list_payload["artifacts"][0]["name"] == "audit"
    assert list_payload["artifacts"][0]["version"] == 1

    get_payload = get_artifact(name="audit")
    assert get_payload["ok"] is True
    assert get_payload["artifact"]["name"] == "audit"
    assert get_payload["artifact"]["version"] == 1
    assert get_payload["artifact"]["payload"] == {"summary": "ok"}


def test_registry_contains_mss_artifact_tools() -> None:
    assert "mss.capabilities" in TOOL_REGISTRY
    assert "mss.list_artifacts" in TOOL_REGISTRY
    assert "mss.get_artifact" in TOOL_REGISTRY
    assert "mss.workout" in TOOL_REGISTRY
    assert "mss.end_workout" in TOOL_REGISTRY
    assert "mss.summarize" in TOOL_REGISTRY
    assert "mss.summarize_details" in TOOL_REGISTRY
    assert "mss.audit" in TOOL_REGISTRY
    assert "mss.prepare" in TOOL_REGISTRY
    assert "mss.planning" in TOOL_REGISTRY
    assert "mss.package" in TOOL_REGISTRY
    assert "mss.run" in TOOL_REGISTRY
    assert "mss.debug" in TOOL_REGISTRY
    assert "mss.end_debug" in TOOL_REGISTRY


def test_flow_tools_persist_artifacts_and_mcp_wrappers_work(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MSS_SESSION_DIR", str(tmp_path))
    connect_payload = connect()
    assert connect_payload["ok"] is True

    assert mcp_mss_capabilities()["ok"] is True
    assert mcp_mss_workout(note="brainstorm")["ok"] is True
    assert mcp_mss_end_workout(summary="done")["ok"] is True
    summarize_payload = mcp_mss_summarize(
            summary="""
FILES AFFECTED
- `mss/tools/mss_artifacts.py`
- `tests/test_mss_artifacts.py`
""".strip()
    )
    assert summarize_payload["ok"] is True
    assert summarize_payload["next_actions"][0]["command"] == "mss.summarize_details"
    assert (
        mcp_mss_summarize_details(
            details="""
### mss/tools/mss_artifacts.py
dokładny opis zmian

### tests/test_mss_artifacts.py
dokładny opis zmian
""".strip()
        )["ok"]
        is True
    )
    assert mcp_mss_audit(summary="audit")["ok"] is True
    assert mcp_mss_prepare(notes="notes")["ok"] is True
    assert mcp_mss_planning(plan_outline="outline")["ok"] is True
    assert mcp_mss_package(summary="pkg")["ok"] is True
    assert mcp_mss_run(output="run output")["ok"] is True
    assert mcp_mss_debug(findings="issue")["ok"] is True
    assert mcp_mss_end_debug(summary="fixed")["ok"] is True

    list_payload = mcp_mss_list_artifacts()
    assert list_payload["ok"] is True
    assert [entry["name"] for entry in list_payload["artifacts"]] == [
        "audit",
        "debug",
        "end_debug",
        "end_workout",
        "package",
        "planning",
        "prepare",
        "run",
        "summarize",
        "summarize_details",
        "workout",
    ]

    get_payload = mcp_mss_get_artifact(name="end_debug")
    assert get_payload["ok"] is True
    assert get_payload["artifact"]["name"] == "end_debug"
    assert get_payload["artifact"]["payload"] == {"summary": "fixed"}


def test_planning_requires_summarize_details_artifact(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MSS_SESSION_DIR", str(tmp_path))
    connect_payload = connect()
    assert connect_payload["ok"] is True

    summarize_payload = mcp_mss_summarize(
        summary="""
FILES AFFECTED
- `mss/tools/mss_artifacts.py`
""".strip()
    )
    assert summarize_payload["ok"] is True

    planning_payload = mcp_mss_planning(plan_outline="outline")
    assert planning_payload["ok"] is False
    assert planning_payload["next_actions"] == [
        {"command": "mss.summarize_details", "description": "Uzupełnij szczegóły per plik"}
    ]
    assert "summarize_details_artifact_not_found" in planning_payload["warnings"]