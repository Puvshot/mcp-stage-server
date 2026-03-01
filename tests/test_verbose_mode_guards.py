from __future__ import annotations

from pathlib import Path
import sys

from mss.runner.bootstrap import bootstrap_tool_registry

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from mss_server.main import mcp_plan_export, mcp_rules_get_full


TOOL_REGISTRY = bootstrap_tool_registry()
rules_get_full = TOOL_REGISTRY["rules.get_full"]


def test_rules_get_full_returns_forbidden_without_verbose_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("MCP_DEBUG_VERBOSE", raising=False)

    response_payload = rules_get_full(plan_dir=str(tmp_path))

    assert response_payload["status"] == "error"
    assert response_payload["code"] == "FORBIDDEN_VERBOSE_MODE"


def test_mcp_plan_export_returns_forbidden_without_verbose_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("MCP_DEBUG_VERBOSE", raising=False)

    response_payload = mcp_plan_export(plan_dir=str(tmp_path))

    assert response_payload["status"] == "error"
    assert response_payload["code"] == "FORBIDDEN_VERBOSE_MODE"


def test_mcp_rules_get_full_returns_forbidden_without_verbose_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("MCP_DEBUG_VERBOSE", raising=False)

    response_payload = mcp_rules_get_full(plan_dir=str(tmp_path))

    assert response_payload["status"] == "error"
    assert response_payload["code"] == "FORBIDDEN_VERBOSE_MODE"
