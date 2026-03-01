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
- **`mss_connect`**: Inicjuje połączenie z panelem śledzenia lub rozpoczyna nową sesję pracy agenta.
- **`mss_status`**: Informuje o obecnym stanie połączeń, trybie pracy, zrzuconych artefaktach, etc.
- **`mss_set_mode`**: Pozwala na przestawienie trybu w systemie (`audit`, `planning`, `debug`, `workout`, `run`).

### Kontrakt `mss_status` (spójność z gate)
`mss_status` korzysta z tych samych warunków blokad co warstwa gate narzędzi artefaktowych.

Priorytet decyzji dla trybów sesyjnych:
- `mode=debug` i brak `end_debug` → `next_actions: [mss.end_debug]`
- `mode=debug` i jest `end_debug`, ale brak PASS w `summarize_details` → `next_actions: [mss.summarize_details]`
- `mode=workout` i brak PASS w `summarize_details` → `next_actions: [mss.summarize_details]`

Zasada priorytetu odpowiedzi:
- Dla `mode=debug` i `mode=workout` zwracana jest jedna akcja sesyjna wynikająca z gate.
- Podpowiedzi wznowienia projektów (`plan_load_or_init`, `stage_current`) są dokładane dopiero, gdy `mode ≠ debug/workout`.

### Wykrywanie projektów po stronie MSS (`data/projects`)
Warstwa sesji może automatycznie wykrywać projekty trzymane po stronie serwera i dokładać
komendy kontynuacji do `message` oraz `next_actions`.

Domyślna lokalizacja projektów:
- `data/projects/`

Opcjonalny override:
- `MSS_PROJECTS_DIR`

Minimalne kryteria klasyfikacji:
- **Gotowy / zainicjalizowany**: istnieje `plan_cache.json` lub `state.json` z `pipeline_status=complete`.
- **W toku / zatrzymany**: istnieje `state.json` z `pipeline_status != complete`.

Dokładane akcje kontekstowe:
- `plan_load_or_init <plan_id> <plan_dir>` — dla każdego wykrytego projektu.
- `stage_current <plan_dir>` — tylko dla projektów `in_progress` z runtime (`state.json` + `plan_cache.json`).

## 2. Narzędzia Zarządzania Artefaktami (Artifacts Tools)
Rodzina narzędzi, które nakazują agentowi trzymanie i generowanie raportów w wyznaczonych folderach. Wszystkie zapisują swoje przemyślenia w formie zrzutu tekstu / podsumowania (`summary`, `notes`, `findings` itd.).

- **`mss_capabilities`**: Definiuje co dany serwer potrafi w bez podawania kontekstu.
- **`mss_list_artifacts` / `mss_get_artifact`**: Pozwala agentowi sprawdzić co on sam lub poprzedni agent zrzucił w raportach (wiedza ustrukturyzowana na nośniku trwałym).
- **`mss_workout` / `mss_end_workout`**: Cykl luźnej pracy badawczej i planowania zbrojeniowego. Zbierają **szczegółowe informacje i notatki** w postaci w pełni odtworzalnego i surowego logu inżyniera ("verbatim", bez kompresji informacji), ze szczególnym uwzględnieniem podziału wiedzy "per plik". Służy do zapotrzebowania logiki przez późniejsze procesy.
- **`mss_summarize`**: Zrzut ogólnego, wysokopoziomowego podsumowania sesji (wątek wiedzy wrzucany na dysk). **Musi zawierać listę plików zadeklarowaną w specjalnej sekcji `FILES AFFECTED`**.
- **`mss_summarize_details`**: Drugi, szczegółowy krok po `summarize`. Generuje **rygorystyczny dokument ze zbiorem danych per plik**. Walidator automatycznie wymusza, by dokument pokrywał każdy plik wymieniony wcześniej w sekcji `FILES AFFECTED`. Informacje te powinny bazować bezpośrednio na szczegółowych notatkach z `workout` / `debug`.
- **`mss_audit`**: Raport z oceny jakości wykonania.
- **`mss_prepare` / `mss_planning` / `mss_package` / `mss_run`**: Zrzuty raportowe dotyczące procesu tworzenia zadań, planowania i uruchomienia kodowania.
- **`mss_debug` / `mss_end_debug`**: Raportowanie długotrwałych sesji zbijania błędów (np. trwająca długa walka z kompilatorem). Podobnie jak `workout`, ten krok narzuca **zbieranie bardzo szczegółowych, nieskompresowanych informacji** ułożonych "per plik" (obserwacje, weryfikacje, hipotezy), które też posłużą potem na wejściach do podsumowań (`summarize_details`).

## 3. Execution Log & Audit Tail
Te narzędzia, choć zaliczane do szeroko pojętego raportowania, operują bezpośrednio na plikach deweloperskich (`execution_log.jsonl`, `runtime_audit.log`).
- **`execution_log_append` / `execution_log_read`**: Doklejenie na sam dół informacji o pomyślnie zrobionym pakiecie zadań (Append-only).
- **`audit_tail` / `audit_clear`**: Odczyt N-ostatnich linii pracy systemu deweloperskiego. Czyste narzędzia diagnostyczne.
