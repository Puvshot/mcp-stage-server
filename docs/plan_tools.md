---
title: "Narzędzia Planowania (Plan Tools)"
type: Feature Set
scope: execution
criticality: high
status: active
---

# Narzędzia Planowania (Plan Tools)

## Cel i rola w systemie
Narzędzia planowania zajmują się wczytywaniem, przetwarzaniem i utrwalaniem zdefiniowanego przez architekta przebiegu prac (workflow) w wewnętrznym formacie JSON (`plan_cache.json`). Odpowiadają za zarządzanie repozytorium instrukcji (Plan) jako zbiorem niezmiennych zadań.

## Lista Narzędzi 

### 1. `plan_load_or_init`
- **Typ wejścia:** Identyfikator `plan_id`, Ścieżka katalogowa `plan_dir`.
- **Rola:** Odbudowuje aktualny stan maszyny, o ile już pliki stanu istnieją w katalogu docelowym (`plan_dir`). Jeśli nie, wyszukuje pliki `PLAN.md` oraz `PACKAGE_*.md` w wyznaczonym folderze i weryfikuje ich strukturę. Następnie generuje z nich JSON-owy single-source-of-truth i generuje pierwszą ramkę `state.json`. Zwraca polecenia gitowe ustawiające projekt w odpowiednim statusie repozytorium.
- **Fail Modes:** Próba wczytania ścieżki bez planu, desynchronizacja (`plan_hash` się nie zgadza w przypadku modyfikacji pliku "w locie").

### 2. `plan_store`
- **Typ wejścia:** Pełen obiekt JSON planu, opcjonalny konfig.
- **Rola:** Wstrzyknięcie pełnego obiektu zamiast generowania na bazie plików MarkDown. Podpisuje wstrzyknięty zestaw zasad, buduje `plan_cache.json` i wymusza stan. Operacja **nie idyempotentna** - nadpisuje wcześniejszy progres w katalogu, na rzecz nowego planu.

### 3. `plan_list`
- **Rola:** Podgląd (read-only) trzymanych metadanych planu w zadanym obszarze. Określa jego rozmiar, etap zaawansowania (czy status jest *initializing* czy np. *running*). Przydaje się agnetom do proaktywnego sprawdzenia czy już mają coś zainicjowanego.

### 4. `plan_reset`
- **Rola:** Przywrócenie pierwotnego stanu początkowego (`state.json`) i wyczyszczenie przebiegu etapów, powtórek testów, ewaluacji (czyszczenie hooków). Zmusza system do przejścia ponownie całej mapy drogowej od Package 0, Stage 0. Wymagane, gdy proces mocno poszedł błędną drogą.

### 5. `plan_export`
- **Reżim Wywołania:** Narzędzie zarezerwowane (forbidden) wymaga zmiennej środowiskowej zabezpieczeń: `MCP_DEBUG_VERBOSE=1`. 
- **Rola:** Wyciąga i konwertuje skeszowany postęp JSONu z pamięci z powrotem do zrzuconego strukturalnie formatu Markdown jako kopia zapasowa lub materiał do manualnego debugowania (folder `/export/PLAN.md`).

## Cykl i wytyczne (Flow)
Plan Tools używane są wyłącznie w początkowej fazie cyklu życia procesu deweloperskiego. Po pozytywnej incjalizacji za pomocą narzędzi wyższych w strukturze, agent ma zabronione (systemowo przez dobre praktyki API) callowanie `load_or_init` czy w szczególności `store` podczas trwania wykonywania samych w sobie poszczególnych Unit of Work. Należy trzymać plan jako niemutowalny relikt.
