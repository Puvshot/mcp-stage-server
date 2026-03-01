"""Runtime-only MCP server wrapper.

This module keeps transport/bootstrap concerns in `src/mss_server/*` and delegates
all domain/tool execution to `mss/*` via `bootstrap_tool_registry`.
"""

from __future__ import annotations

import os
from typing import Any

from mcp.server.fastmcp import FastMCP
from mss.runner import ToolCallable, bootstrap_tool_registry


def build_tool_registry() -> dict[str, ToolCallable]:
    """Build full registry while preserving all MVP tool contracts."""
    return bootstrap_tool_registry()


TOOL_REGISTRY = build_tool_registry()


def get_registered_tool_names() -> list[str]:
    """Return deterministic list of MVP tool names required by legacy tests."""
    return sorted(
        [
            "guard.report",
            "plan.load_or_init",
            "rules.directive_pack",
            "stage.advance",
            "stage.current",
            "test.report",
        ]
    )


def call_tool(tool_name: str, **kwargs: Any) -> dict[str, Any]:
    """Call one registered tool by contract name and return structured payload."""
    tool_handler = TOOL_REGISTRY.get(tool_name)
    if tool_handler is None:
        return {
            "status": "error",
            "code": "TOOL_NOT_FOUND",
            "errors": [
                {
                    "code": "TOOL_NOT_FOUND",
                    "message": f"Unknown tool: {tool_name}",
                    "file": None,
                    "severity": "error",
                }
            ],
        }
    return tool_handler(**kwargs)


def _forbidden_verbose_mode_response(tool_name: str) -> dict[str, Any]:
    return {
        "status": "error",
        "code": "FORBIDDEN_VERBOSE_MODE",
        "errors": [
            {
                "code": "FORBIDDEN_VERBOSE_MODE",
                "message": f"{tool_name} requires MCP_DEBUG_VERBOSE=1",
                "file": None,
                "severity": "error",
            }
        ],
    }


app = FastMCP("mcp-stage-server")


@app.tool(name="plan_load_or_init", description="Load existing state or initialize plan cache and state from markdown plan files.")
def mcp_plan_load_or_init(plan_id: str, plan_dir: str) -> dict[str, Any]:
    """MCP wrapper for plan.load_or_init."""
    return call_tool("plan.load_or_init", plan_id=plan_id, plan_dir=plan_dir)


@app.tool(name="plan_store", description="Store full Plan payload and initialize runtime state/cache.")
def mcp_plan_store(plan_dir: str, plan: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
    """MCP wrapper for plan.store."""
    return call_tool("plan.store", plan=plan, plan_dir=plan_dir, config=config)


@app.tool(name="plan_list", description="List stored plan metadata for runtime directory.")
def mcp_plan_list(plan_dir: str) -> dict[str, Any]:
    """MCP wrapper for plan.list."""
    return call_tool("plan.list", plan_dir=plan_dir)


@app.tool(name="plan_reset", description="Reset runtime cursor/status for initialized plan.")
def mcp_plan_reset(plan_dir: str) -> dict[str, Any]:
    """MCP wrapper for plan.reset."""
    return call_tool("plan.reset", plan_dir=plan_dir)


@app.tool(name="plan_export", description="Export cached plan to markdown backup file.")
def mcp_plan_export(plan_dir: str) -> dict[str, Any]:
    """MCP wrapper for plan.export."""
    if not os.getenv("MCP_DEBUG_VERBOSE"):
        return _forbidden_verbose_mode_response("plan.export")
    return call_tool("plan.export", plan_dir=plan_dir)


@app.tool(name="stage_current", description="Return currently active stage payload and position in pipeline.")
def mcp_stage_current(plan_dir: str) -> dict[str, Any]:
    """MCP wrapper for stage.current."""
    return call_tool("stage.current", plan_dir=plan_dir)


@app.tool(name="stage_advance", description="Advance active stage after successful guard and test reporting sequence.")
def mcp_stage_advance(plan_dir: str) -> dict[str, Any]:
    """MCP wrapper for stage.advance."""
    return call_tool("stage.advance", plan_dir=plan_dir)


@app.tool(name="stage_rewind", description="Rewind cursor to previous stage and clear retry state.")
def mcp_stage_rewind(plan_dir: str, reason: str | None = None) -> dict[str, Any]:
    """MCP wrapper for stage.rewind."""
    return call_tool("stage.rewind", plan_dir=plan_dir, reason=reason)


@app.tool(name="stage_peek_next", description="Preview next stage payload without moving cursor.")
def mcp_stage_peek_next(plan_dir: str) -> dict[str, Any]:
    """MCP wrapper for stage.peek_next."""
    return call_tool("stage.peek_next", plan_dir=plan_dir)


@app.tool(name="guard_report", description="Record guard status for active stage before test.report.")
def mcp_guard_report(
    plan_dir: str,
    stage_id: str,
    stop_conditions_violated: bool,
    details: str,
) -> dict[str, Any]:
    """MCP wrapper for guard.report."""
    return call_tool(
        "guard.report",
        plan_dir=plan_dir,
        stage_id=stage_id,
        stop_conditions_violated=stop_conditions_violated,
        details=details,
    )


@app.tool(name="test_report", description="Record PASS/FAIL test result and return advancement or retry instruction payload.")
def mcp_test_report(
    plan_dir: str,
    stage_id: str,
    result: str,
    output: str,
    command: str,
) -> dict[str, Any]:
    """MCP wrapper for test.report."""
    return call_tool(
        "test.report",
        plan_dir=plan_dir,
        stage_id=stage_id,
        result=result,
        output=output,
        command=command,
    )


@app.tool(name="rules_directive_pack", description="Build directive pack for stage based on default and project rule overlays.")
def mcp_rules_directive_pack(plan_dir: str, stage_id: str) -> dict[str, Any]:
    """MCP wrapper for rules.directive_pack."""
    return call_tool("rules.directive_pack", plan_dir=plan_dir, stage_id=stage_id)


@app.tool(name="rules_get_full", description="Return fully merged rules payload for runtime directory.")
def mcp_rules_get_full(plan_dir: str) -> dict[str, Any]:
    """MCP wrapper for rules.get_full."""
    if not os.getenv("MCP_DEBUG_VERBOSE"):
        return _forbidden_verbose_mode_response("rules.get_full")
    return call_tool("rules.get_full", plan_dir=plan_dir)


@app.tool(name="rules_version", description="Return active rules version metadata.")
def mcp_rules_version(plan_dir: str) -> dict[str, Any]:
    """MCP wrapper for rules.version."""
    return call_tool("rules.version", plan_dir=plan_dir)


@app.tool(name="rules_convert_md_to_json", description="Convert markdown rules into JSON SSOT payloads.")
def mcp_rules_convert_md_to_json(
    rules_kind: str | None = None,
    source_markdown_path: str | None = None,
    output_json_path: str | None = None,
) -> dict[str, Any]:
    """MCP wrapper for rules.convert_md_to_json."""
    return call_tool(
        "rules.convert_md_to_json",
        rules_kind=rules_kind,
        source_markdown_path=source_markdown_path,
        output_json_path=output_json_path,
    )


@app.tool(name="exec_directive_bundle", description="Return executor-facing directive bundle with deterministic prompt trimming.")
def mcp_exec_directive_bundle(plan_dir: str, stage_id: str, char_limit: int = 4000) -> dict[str, Any]:
    """MCP wrapper for exec.directive_bundle."""
    return call_tool("exec.directive_bundle", plan_dir=plan_dir, stage_id=stage_id, char_limit=char_limit)


@app.tool(name="collision_analyze", description="Analyze deterministic file-collision risks for one stage.")
def mcp_collision_analyze(plan_dir: str, stage_id: str) -> dict[str, Any]:
    """MCP wrapper for collision.analyze."""
    return call_tool("collision.analyze", plan_dir=plan_dir, stage_id=stage_id)


@app.tool(name="execution_log_append", description="Append/upsert execution log entry for completed package.")
def mcp_execution_log_append(plan_dir: str, plan_id: str, package_id: str, narrative: str) -> dict[str, Any]:
    """MCP wrapper for execution_log.append."""
    return call_tool(
        "execution_log.append",
        plan_dir=plan_dir,
        plan_id=plan_id,
        package_id=package_id,
        narrative=narrative,
    )


@app.tool(name="execution_log_read", description="Read execution log entries for plan with optional tail window.")
def mcp_execution_log_read(plan_dir: str, plan_id: str, last_n: int | None = None) -> dict[str, Any]:
    """MCP wrapper for execution_log.read."""
    return call_tool("execution_log.read", plan_dir=plan_dir, plan_id=plan_id, last_n=last_n)


@app.tool(name="audit_tail", description="Return last N lines from runtime audit log.")
def mcp_audit_tail(plan_dir: str, last_n: int = 50) -> dict[str, Any]:
    """MCP wrapper for audit.tail."""
    return call_tool("audit.tail", plan_dir=plan_dir, last_n=last_n)


@app.tool(name="audit_clear", description="Clear runtime audit log content.")
def mcp_audit_clear(plan_dir: str) -> dict[str, Any]:
    """MCP wrapper for audit.clear."""
    return call_tool("audit.clear", plan_dir=plan_dir)


@app.tool(name="mss_connect", description="Create or resume active MSS session.")
def mcp_mss_connect() -> dict[str, Any]:
    """MCP wrapper for mss.connect."""
    return call_tool("mss.connect")


@app.tool(name="mss_status", description="Return active MSS session status.")
def mcp_mss_status() -> dict[str, Any]:
    """MCP wrapper for mss.status."""
    return call_tool("mss.status")


@app.tool(name="mss_set_mode", description="Set active MSS session mode.")
def mcp_mss_set_mode(mode: str, project_name: str | None = None) -> dict[str, Any]:
    """MCP wrapper for mss.set_mode."""
    return call_tool("mss.set_mode", mode=mode, project_name=project_name)


@app.tool(name="mss_capabilities", description="Return MSS artifact capabilities for active session.")
def mcp_mss_capabilities() -> dict[str, Any]:
    """MCP wrapper for mss.capabilities."""
    return call_tool("mss.capabilities")


@app.tool(name="mss_list_artifacts", description="List MSS artifacts for active session.")
def mcp_mss_list_artifacts() -> dict[str, Any]:
    """MCP wrapper for mss.list_artifacts."""
    return call_tool("mss.list_artifacts")


@app.tool(name="mss_get_artifact", description="Get one MSS artifact by name for active session.")
def mcp_mss_get_artifact(name: str) -> dict[str, Any]:
    """MCP wrapper for mss.get_artifact."""
    return call_tool("mss.get_artifact", name=name)


@app.tool(name="mss_workout", description="Persist workout artifact for active MSS session.")
def mcp_mss_workout(note: str | None = None) -> dict[str, Any]:
    """MCP wrapper for mss.workout."""
    return call_tool("mss.workout", note=note)


@app.tool(name="mss_end_workout", description="Persist end_workout artifact. REQUIRED: ask user 'Chcesz coś dopracować, czy zapisujemy podsumowanie?' before calling mss_summarize.")
def mcp_mss_end_workout(summary: str | None = None) -> dict[str, Any]:
    """MCP wrapper for mss.end_workout."""
    return call_tool("mss.end_workout", summary=summary)


@app.tool(name="mss_summarize", description="Persist summarize artifact. REQUIRED: call mss_summarize_details immediately after — no code changes until PASS.")
def mcp_mss_summarize(summary: str | None = None, files_affected: list[str] | None = None) -> dict[str, Any]:
    """MCP wrapper for mss.summarize."""
    return call_tool("mss.summarize", summary=summary, files_affected=files_affected)


@app.tool(name="mss_new_session", description="Create a new MSS session, archiving the current one.")
def mcp_mss_new_session() -> dict[str, Any]:
    """MCP wrapper for mss.new_session."""
    return call_tool("mss.new_session")


@app.tool(name="mss_summarize_details", description="Persist summarize_details artifact for active MSS session.")
def mcp_mss_summarize_details(details: str | None = None) -> dict[str, Any]:
    """MCP wrapper for mss.summarize_details."""
    return call_tool("mss.summarize_details", details=details)


@app.tool(name="mss_audit", description="Persist audit artifact for active MSS session.")
def mcp_mss_audit(summary: str | None = None) -> dict[str, Any]:
    """MCP wrapper for mss.audit."""
    return call_tool("mss.audit", summary=summary)


@app.tool(name="mss_prepare", description="Persist prepare artifact for active MSS session.")
def mcp_mss_prepare(notes: str | None = None) -> dict[str, Any]:
    """MCP wrapper for mss.prepare."""
    return call_tool("mss.prepare", notes=notes)


@app.tool(name="mss_planning", description="Persist planning artifact for active MSS session.")
def mcp_mss_planning(plan_outline: str | None = None) -> dict[str, Any]:
    """MCP wrapper for mss.planning."""
    return call_tool("mss.planning", plan_outline=plan_outline)


@app.tool(name="mss_package", description="Persist package artifact for active MSS session.")
def mcp_mss_package(summary: str | None = None) -> dict[str, Any]:
    """MCP wrapper for mss.package."""
    return call_tool("mss.package", summary=summary)


@app.tool(name="mss_run", description="Persist run artifact for active MSS session.")
def mcp_mss_run(output: str | None = None) -> dict[str, Any]:
    """MCP wrapper for mss.run."""
    return call_tool("mss.run", output=output)


@app.tool(name="mss_debug", description="Persist debug artifact for active MSS session.")
def mcp_mss_debug(findings: str | None = None) -> dict[str, Any]:
    """MCP wrapper for mss.debug."""
    return call_tool("mss.debug", findings=findings)


@app.tool(name="mss_end_debug", description="Persist end_debug artifact. REQUIRED: ask user 'Chcesz coś dopracować, czy zapisujemy podsumowanie?' before calling mss_summarize.")
def mcp_mss_end_debug(summary: str | None = None) -> dict[str, Any]:
    """MCP wrapper for mss.end_debug."""
    return call_tool("mss.end_debug", summary=summary)


def main() -> None:
    """Run MCP server over stdio transport for Cline integration."""
    app.run(transport="stdio")


if __name__ == "__main__":
    main()