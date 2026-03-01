---
date: "2026-03-01T16:43:31"
task: "MSS_Fix_A-G"
status: "completed"
---

# Zmiana: Naprawiono problemy A–G w MSS Session & Artifacts

## 🎯 Cel / Problem
- **Problem:** System MSS miał 7 zidentyfikowanych problemów (A–G): brak nazwy projektu w sesji, nieinformatywny `status`, błędna nazwa artefaktu `summarize`, brak ustrukturyzowanego `files_affected`, ścieżki sesji zależne od CWD, blokada flow koncepcyjnego i brak mechanizmu reset/abort.
- **Cel:** Determinizm pracy agenta, czytelność UX, niezawodność artefaktów.

## 📁 Zmodyfikowane Pliki

- `mss/tools/session.py`: [Fix A] `project_name: None` w nowych sesjach, `_response()` z `project_name`; [Fix A] hint o `project_name` w `_CONNECT_MESSAGE`; [Fix B] dynamiczny `message` w `status()`; [Fix E] `__file__` zamiast `Path.cwd()` w `_session_dir()` i `_projects_dir()`; [Fix G] `set_mode` wymaga `project_name` dla `workout`, nowa funkcja `new_session()`.
- `mss/storage/session_store.py`: [Fix A] normalizacja `project_name` w `_normalize_session_payload`.
- `mss/tools/mss_artifacts.py`: [Fix C] rename artefaktu `"summarize"` → `"summary"` w `summarize()`; [Fix C] pole `message` w odpowiedzi `summarize()`; [Fix D] parametr `files_affected: list[str]` w `summarize()`; [Fix E] `__file__` w `_session_dir()`.
- `mss/engines/artifact_flow_gate.py`: [Fix D] `extract_summary_text` auto-dołącza `files_affected` z payload; [Fix F] `validation_passed = len(missing_paths) == 0` (bypass dla flow koncepcyjnego).
- `mss/engines/session_actions_policy.py`: [Fix C] `has_summarize = "summary" in artifact_names`.
- `mss/runner/bootstrap.py`: [Fix G] rejestracja `mss.new_session`.
- `src/mss_server/main.py`: [Fix D] `files_affected` w `mcp_mss_summarize`; [Fix G] `project_name` w `mcp_mss_set_mode`, nowy wrapper `mcp_mss_new_session`.
- `tests/test_session.py`: aktualizacja asercji `message` (Fix B), dodanie `project_name` do wywołań workout, nowe testy Fix G.
- `tests/test_mss_artifacts.py`: aktualizacja nazwy artefaktu `"summary"`, nowe testy Fix C + D.
- `docs/Documentation/mss_session_tools.md`: aktualizacja dokumentacji.

## ☢️ Potencjalne Zagrożenia
- Zmiana nazwy artefaktu z `"summarize"` na `"summary"` — **istniejące sesje na dysku** będą miały stary artefakt `"summarize"`. System ich nie znajdzie. Sesje archiwalne nie będą kompatybilne z nowym flow.
- `set_mode(workout)` bez `project_name` teraz zwraca `ok=False` — wszelkie narzędzia (zewnętrzne skrypty, inne narzędzia) wywołujące `set_mode` bez nazwy projektu dla trybu workout przestaną działać.
- `_session_dir()` i `_projects_dir()` zmienione na `__file__`-relative — jeśli serwer był uruchamiany z innego CWD i tam trzymał dane, teraz znajdzie je w `<repo_root>/data/`.

## 📝 Aktualizacja Głównej Dokumentacji
- [x] `docs/Documentation/mss_session_tools.md` zaktualizowany.
