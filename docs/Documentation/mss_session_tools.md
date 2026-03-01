---
title: "Narzędzia Sesji Lobbystycznej (MSS Session & Artifacts)"
type: Subsystem
scope: global
criticality: medium
status: active
---

# Narzędzia Sesji MSS i Artefakty

## Cel i rola w systemie
Poza rdzeniem wykonawczym i przemieszczaniem kursora w pętli kodowania, MCP Stage Server posiada domenę zarządzania pobocznymi zadaniami raportowymi — Session & Artifacts. Służą one do zrzucania nieustrukturyzowanej (lub częściowo ustrukturyzowanej) wiedzy, myśli agenta i notatek audytowych w pliki, których użytkownik może łatwo doglądać.

## 1. Narzędzia Zarządzania Sesją (Session Tools)
- **`mss_connect`**: Inicjuje połączenie z panelem śledzenia lub wznawia aktywną sesję. Powoduje utworzenie nowej sesji w katalogu tymczasowym `_pending/`. `project_name` w payloadu sesji ustawiany jest `null` do czasu wywołania `mss_set_mode(mode, project_name=...)`.
- **`mss_status`**: Informuje o obecnym stanie połączeń, trybie pracy, zrzuconych artefaktach etc. Zwraca dynamiczny komunikat z trybem i listą artefaktów: `"Stan sesji: tryb {mode}. Artefakty ({N}): {lista}."`.
- **`mss_set_mode`**: Pozwala na przestawienie trybu w systemie (`audit`, `planning`, `debug`, `workout`, `run`). **Dla `mode=workout` oraz `mode=debug` parametr `project_name` jest wymagany** — bez jego podania narzędzie zwraca błąd. Po otrzymaniu prawidłowego `project_name`, folder sesji zostaje przeniesiony z `_pending/` do głównego folderu z nazwą projektu (`<project_name>/`).
- **`mss_new_session`**: Tworzy nową, czystą sesję i ustawia ją jako aktywną w podfolderze `_pending/`. Poprzednia sesja jest zachowana na dysku jako archiwum. `project_name` ustalany jest później przy wywołaniu `mss_set_mode`.

### Kontrakt `mss_status` (spójność z gate)
`mss_status` korzysta z tych samych warunków blokad co warstwa gate narzędzi artefaktowych.

Priorytet decyzji dla trybów sesyjnych:
- `mode=debug` i brak `end_debug` → `next_actions: [mss.end_debug]`
- `mode=debug` i jest `end_debug`, ale brak PASS w `summarize_details` → `next_actions: [mss.summarize_details]`
- `mode=workout` i brak `workout` → `next_actions: [mss.workout]`
- `mode=workout` i jest `workout`, ale brak `end_workout` → `next_actions: [mss.end_workout]`
- `mode=workout` i jest `end_workout`, ale brak `summary` → `next_actions: [mss.summarize]`
- `mode=workout` i jest `summary`, ale brak PASS w `summarize_details` → `next_actions: [mss.summarize_details]`
- `mode=workout` i jest PASS w `summarize_details` → `next_actions: [mss.planning]`

Sekwencja ta jest celowa: `mss.summarize_details` waliduje pokrycie `FILES AFFECTED` zapisanych w artefakcie `summary`, więc poprawna nawigacja w `workout` wymaga najpierw `mss.summarize`.

Zasada priorytetu odpowiedzi:
- Dla `mode=debug` i `mode=workout` zwracana jest jedna akcja sesyjna wynikająca z gate.
- Podpowiedzi wznowienia projektów (`plan_load_or_init`, `stage_current`) są dokładane dopiero, gdy `mode ≠ debug/workout`.

### Wykrywanie projektów po stronie MSS (`data/sessions`)
Ulepszona warstwa sesji (w ramach mechanizmu "MSS Packages & Stages") potrafi również automatycznie wykrywać bieżące fazy pracy nad projektami MSS. Program skanuje i przypina do powiadomienia sugestie wznowienia.
Minimalne kryteria klasyfikacji dla sesji:
- Skanowane są katalogi projektów (z pominięciem struktury tymczasowej `_pending`).
- Algorytm sprawdza obecność odpowiednich podfolderów fazowych w nazwie projektu (`audit/`, `prepare/`, `planning/`, `run/`).
- Zwracany status to `needs_audit`, `needs_prepare`, `needs_planning`, `needs_run` lub `done`.


## 2. Narzędzia Zarządzania Artefaktami (Artifacts Tools)
System zrządza folderami artefaktów na bazie ustalonego strukturalnego mapowania *MSS Packages & Stages*. 
Zrezygnowano ze zszywania artefaktów z ID sesji, przechodząc na sztywny układ podziału wewnątrz folderu konkretnego projektu: `<project_name>/<faza>/<nazwa>.vN.json`.

Artefakty i narzędzia powiązane z ich obsługą:
- **`mss_capabilities`**: Definiuje co dany serwer potrafi bez podawania kontekstu.
- **`mss_list_artifacts` / `mss_get_artifact`**: Pozwala agentowi sprawdzić co on sam lub poprzedni agent zrzucił w raportach (wiedza ustrukturyzowana na nośniku trwałym, ładowana cross-sesyjnie w granicach projektu).
- **`mss_workout` / `mss_end_workout`**: Cykl luźnej pracy badawczej i planowania zbrojeniowego. Zbierają **szczegółowe informacje i notatki** w postaci w pełni odtworzalnego i surowego logu inżyniera ("verbatim", bez kompresji informacji), ze szczególnym uwzględnieniem podziału wiedzy "per plik". `mss_end_workout` przy wywołaniu wyświetli ostrzeżenie dla Agenta i przypomni o konieczności **zasięgnięcia decyzji użytkownika** przed przejściem do sekcji podsumowań.
- **`mss_summarize`**: Zrzut ogólnego, wysokopoziomowego podsumowania sesji. Przyjmuje opcjonalny parametr `files_affected: list[str]` — gdy podany, system automatycznie generuje sekcję `FILES AFFECTED` wymaganą przez walidator `summarize_details`. Wraca rygorystyczny zestaw instrukcji: STOP - agent musi od razu iść do kroku detali (`mss_summarize_details`). Artefakt zapisywany bezwarunkowo pod nazwą **`summary`**, zależnie od warunków uruchomienia do folderu zgodnego z trybem.
- **`mss_summarize_details`**: Drugi, szczegółowy krok po `summarize`. Generuje rygorystyczny dokument ze zbiorem danych per plik. Wymusza pokrycie dla każdego zgłoszonego przy wywołaniu `files_affected` pliku.
- **`mss_audit`**: Raport z oceny jakości wykonania, trafiający do `/audit/`.
- **`mss_prepare` / `mss_planning` / `mss_package` / `mss_run`**: Zrzuty raportowe dotyczące procesu tworzenia zadań, planowania i uruchomienia kodowania, trafiające do osobnych folderów faz, wg ścieżki (`/prepare/`, `/planning/`, `/package/`, `/run/`).
- **`mss_debug` / `mss_end_debug`**: Raportowanie długotrwałych sesji zbijania błędów (np. trwająca długa walka z kompilatorem). Podobnie jak `workout`, ten krok narzuca **zbieranie bardzo szczegółowych, nieskompresowanych informacji** ułożonych "per plik" (obserwacje, weryfikacje, hipotezy), które też posłużą potem na wejściach do podsumowań (`summarize_details`).

## 3. Execution Log & Audit Tail
Te narzędzia, choć zaliczane do szeroko pojętego raportowania, operują bezpośrednio na plikach deweloperskich (`execution_log.jsonl`, `runtime_audit.log`).
- **`execution_log_append` / `execution_log_read`**: Doklejenie na sam dół informacji o pomyślnie zrobionym pakiecie zadań (Append-only).
- **`audit_tail` / `audit_clear`**: Odczyt N-ostatnich linii pracy systemu deweloperskiego. Czyste narzędzia diagnostyczne.
