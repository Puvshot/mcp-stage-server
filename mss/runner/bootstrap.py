from __future__ import annotations

from importlib import import_module
from typing import Any, Callable


ToolCallable = Callable[..., dict[str, Any]]


def bootstrap_tool_registry() -> dict[str, ToolCallable]:
    """Build tool registry using `mss.tools.*` imports only."""
    audit_module = _import_tool_module("audit")
    collision_module = _import_tool_module("collision")
    exec_bundle_module = _import_tool_module("exec_bundle")
    execution_log_module = _import_tool_module("execution_log")
    guard_module = _import_tool_module("guard")
    plan_module = _import_tool_module("plan")
    rules_module = _import_tool_module("rules")
    rules_convert_module = _import_tool_module("rules_convert")
    stage_module = _import_tool_module("stage")
    test_report_module = _import_tool_module("test_report")

    return {
        "plan.store": plan_module.store,
        "plan.list": plan_module.list,
        "plan.reset": plan_module.reset,
        "plan.export": plan_module.export,
        "plan.load_or_init": plan_module.load_or_init,
        "stage.current": stage_module.current,
        "stage.advance": stage_module.advance,
        "stage.rewind": stage_module.rewind,
        "stage.peek_next": stage_module.peek_next,
        "guard.report": guard_module.report,
        "test.report": test_report_module.report,
        "rules.get_full": rules_module.get_full,
        "rules.version": rules_module.version,
        "rules.directive_pack": rules_module.directive_pack,
        "rules.convert_md_to_json": rules_convert_module.convert_md_to_json,
        "exec.directive_bundle": exec_bundle_module.directive_bundle,
        "collision.analyze": collision_module.analyze,
        "execution_log.append": execution_log_module.append,
        "execution_log.read": execution_log_module.read,
        "audit.tail": audit_module.tail,
        "audit.clear": audit_module.clear,
    }


def _import_tool_module(module_name: str) -> Any:
    return import_module(f"mss.tools.{module_name}")