from __future__ import annotations


def next_actions_for_set_mode(mode: str) -> list[dict[str, str]]:
    """Return deterministic next actions after successful mode switch."""
    mapping: dict[str, list[dict[str, str]]] = {
        "audit": [
            _action("audit", "Uruchom audyt kodu"),
            _action("status", "Sprawdź stan sesji"),
        ],
        "planning": [
            _action("preplan", "Przygotuj preplan"),
            _action("plan", "Wygeneruj plan"),
            _action("status", "Sprawdź stan sesji"),
        ],
        "debug": [_action("audit", "Uruchom audyt kodu")],
        "workout": [
            _action("mss.workout", "Rozpocznij sesję workout (notatki / burza mózgów)"),
            _action("status", "Sprawdź stan sesji"),
        ],
        "run": [
            _action("plan", "Wygeneruj plan"),
            _action("status", "Sprawdź stan sesji"),
        ],
    }
    return mapping.get(mode, [_action("status", "Sprawdź stan sesji")])


def next_actions_for_status(
    mode: str | None,
    artifact_names: set[str],
    summarize_details_pass: bool = False,
) -> list[dict[str, str]]:
    """Return deterministic next actions for status payload."""
    if mode is None:
        return _action_connect()

    has_end_debug = "end_debug" in artifact_names
    summarize_details_passed_flag = bool(summarize_details_pass)

    if mode == "debug":
        if not has_end_debug:
            return [_action("mss.end_debug", "Zapisz end_debug")]
        if not summarize_details_passed_flag:
            return [_action("mss.summarize_details", "Uzupełnij summarize_details i doprowadź do PASS")]

    if mode == "workout":
        has_workout = "workout" in artifact_names
        has_end_workout = "end_workout" in artifact_names
        has_summarize = "summary" in artifact_names  # Fix C: zmiana nazwy artefaktu
        if not has_workout:
            return [_action("mss.workout", "Rozpocznij sesję workout (notatki / burza mózgów)")]
        if not has_end_workout:
            return [_action("mss.end_workout", "Zamknij sesję workout")]
        if not has_summarize:
            return [_action("mss.summarize", "Podsumuj sesję")]
        if not summarize_details_passed_flag:
            return [_action("mss.summarize_details", "Uzupełnij summarize_details i doprowadź do PASS")]
        return [_action("mss.planning", "Przejdź do planowania")]

    if mode == "audit":
        if "audit" in artifact_names:
            return [
                _action("preplan", "Przygotuj preplan na bazie audytu"),
                _action("show audit", "Pokaż artefakt audytu"),
            ]
        return [_action("audit", "Uruchom audyt kodu")]

    if mode == "planning":
        if "preplan" in artifact_names:
            return [_action("plan", "Wygeneruj plan implementacji")]
        return [_action("preplan", "Wygeneruj preplan")]

    return next_actions_for_set_mode(mode)


def _action_connect() -> list[dict[str, str]]:
    return [
        _action("debug", "Skrót: ustawia tryb debug"),
        _action("workout", "Skrót: ustawia tryb workout"),
        _action("mode debug", "Uruchamia tryb debug"),
        _action("mode workout", "Uruchamia tryb workout"),
    ]


def _action(command: str, description: str) -> dict[str, str]:
    return {
        "command": command,
        "description": description,
    }
