from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import mss.rules.loader as loader_module


def test_load_rules_payload_happy_path_for_required_kind() -> None:
    loaded_payload = loader_module.load_rules_payload("package_generation")

    assert loaded_payload["version"]
    assert isinstance(loaded_payload["action_directives"], dict)
    assert isinstance(loaded_payload["always"], dict)
    assert isinstance(loaded_payload["forbidden_imports"], list)
    assert isinstance(loaded_payload["templates"], dict)


def test_load_rules_payload_returns_hard_error_for_missing_required_kind(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing_rules_path = tmp_path / "missing_package_generation.json"

    monkeypatch.setattr(loader_module, "_resolve_rules_file_path", lambda _required_kind: missing_rules_path)

    with pytest.raises(loader_module.RulesLoadException) as raised_error:
        loader_module.load_rules_payload("package_generation")

    error_payload = raised_error.value.error_payload
    assert error_payload.code == "MISSING_REQUIRED_RULES_KIND"
    assert error_payload.file_path == str(missing_rules_path)
    assert error_payload.validation_issues == []


def test_rules_hash_is_stable_across_calls() -> None:
    first_payload = loader_module.load_rules_payload("package_generation")
    second_payload = loader_module.load_rules_payload("package_generation")

    first_hash = hashlib.sha256(
        json.dumps(first_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    second_hash = hashlib.sha256(
        json.dumps(second_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()

    assert first_hash == second_hash