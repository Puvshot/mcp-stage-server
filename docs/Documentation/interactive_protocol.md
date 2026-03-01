---
title: "MSS - Interaktywny Protokół Sesji (krok po kroku)"
type: Documentation
scope: execution
criticality: high
status: active
---

# Interaktywny Protokół Sesji MSS — Krok po Kroku

MSS nie jest biernym repozytorium komend. Po każdym wywołaniu narzędzia serwer zwraca `next_actions` — listę konkretnych podpowiedzi dla agenta co powinno nastąpić jako kolejne. Dzięki temu agent AI zawsze wie co zrobić dalej bez zgadywania.

Poniżej opisana jest każda możliwa ścieżka od połączenia z serwerem po zakończenie sesji.

---

## 1. Start: Połączenie z serwerem

**Komenda użytkownika do agenta:** `"Połącz się z MSS"`

Agent wywołuje: `mss_connect`

**Odpowiedź serwera (komunikat wyświetlany użytkownikowi):**
> *"Cześć, jaką operację chcesz wykonać?*
>
> *Dostępne funkcje:*
> - ***Debug** (Ścisły protokół do naprawy kodu. Pokaż mi błąd, a ja przeanalizuję pliki, postawię hipotezę i naprawię usterkę krok po kroku)*
> - ***Workout** (Burza mózgów i planowanie. Porozmawiajmy o architekturze, rozważmy opcje i zapisujmy ustalenia na bieżąco, bez pisania kodu na ślepo)"*

Jeśli serwer wykryje katalogi projektów w `data/projects/` (lub w katalogu zdefiniowanym przez `MSS_PROJECTS_DIR`),
to ten sam komunikat zawiera dodatkowo sekcje:
- `✅ Gotowe / zainicjalizowane`
- `⏳ W toku / zatrzymane`

W każdej sekcji pojawiają się gotowe komendy kontynuacji, m.in.:
- `plan_load_or_init <plan_id> <plan_dir>`
- `stage_current <plan_dir>` (tylko dla projektów `in_progress` z pełnym runtime: `state.json` + `plan_cache.json`)

**`next_actions` sugerowane przez serwer:**
- `debug` — Skrót: ustawia tryb debug
- `workout` — Skrót: ustawia tryb workout
- `mode debug` — Uruchamia tryb debug
- `mode workout` — Uruchamia tryb workout
- `plan_load_or_init <plan_id> <plan_dir>` — Wczytuje wykryty projekt
- `stage_current <plan_dir>` — Pokazuje aktywny etap projektu w toku (warunkowo)

---

## 2. Wybór trybu: `mss_set_mode`

Agent wywołuje: `mss_set_mode(mode="debug")` lub `mss_set_mode(mode="workout")`

Skróty akceptowane przez warstwę interakcji użytkownika/agenta:
- `debug` → równoważne `mode debug`
- `workout` → równoważne `mode workout`

Dozwolone wartości trybu: `audit`, `planning`, `debug`, `workout`, `run`

**Po ustawieniu trybu `debug`, serwer sugeruje:**
- `audit` — Uruchom audyt kodu
- `status` — Sprawdź stan sesji

**Po ustawieniu trybu `workout`, serwer sugeruje:**
- `mss.workout` — Rozpocznij sesję workout (notatki / burza mózgów)
- `status` — Sprawdź stan sesji

**Po ustawieniu trybu `planning`, serwer sugeruje:**
- `preplan` — Przygotuj preplan
- `plan` — Wygeneruj plan
- `status` — Sprawdź stan sesji

**Po ustawieniu trybu `run`, serwer sugeruje:**
- `plan` — Wygeneruj plan
- `status` — Sprawdź stan sesji

---

## 3. Ścieżka: Workout (burza mózgów)

`mss_status` w trybie `workout` prowadzi deterministycznie przez kroki:
`mss.workout` → `mss.end_workout` → `mss.summarize` → `mss.summarize_details` → `mss.planning`.

`mss.summarize_details` ma sens dopiero po `mss.summarize`, ponieważ waliduje pokrycie sekcji `FILES AFFECTED`.

### Krok 3.1: Zapis notatek z sesji pracy
Agent wywołuje: `mss_workout(note="...")`

**`next_actions` po zapisie:**
- `mss.end_workout` — Zamknij sesję workout
- `mss.summarize` — Podsumuj sesję

### Krok 3.2: Zamknięcie sesji workout
Agent wywołuje: `mss_end_workout(summary="...")`

**`next_actions` po zamknięciu:**
- `mss.summarize` — Podsumuj sesję

---

## 4. Ścieżka: Podsumowanie (summarize)

> Może nastąpić po workout, debug lub jako samodzielna akcja.

### Krok 4.1: Ogólne podsumowanie
Agent wywołuje: `mss_summarize(summary="...")`

Podsumowanie **musi zawierać sekcję `FILES AFFECTED`** z listą zmodyfikowanych plików (używaną przez walidator w kroku 4.2).

**`next_actions` po zapisie:**
- `mss.summarize_details` — Uzupełnij szczegóły per plik
- `mss.list_artifacts` — Wyświetl artefakty sesji

### Krok 4.2: Szczegóły per plik (`summarize_details`)
Agent wywołuje: `mss_summarize_details(details="...")`

Serwer waliduje czy `details` pokrywa **każdy plik** wymieniony w sekcji `FILES AFFECTED` z kroku 4.1. Każdy plik musi mieć własną sekcję `### <ścieżka_pliku>`.

**Jeśli walidacja PASS (`next_actions`):**
- `mss.planning` — Przejdź do planowania

**Jeśli walidacja FAIL (`next_actions`):**
- `mss.summarize_details` — Uzupełnij brakujące szczegóły

---

## 5. Ścieżka: Audyt (`audit`)

Agent wywołuje: `mss_audit(summary="...")`

**`next_actions` po audycie:**
- `mss.prepare` — Przygotuj preplan
- `mss.planning` — Przejdź do planowania

---

## 6. Ścieżka: Przygotowanie (`prepare`)

Agent wywołuje: `mss_prepare(notes="...")`

**`next_actions` po zapisie:**
- `mss.planning` — Przejdź do planowania

---

## 7. Ścieżka: Planowanie (`planning`)

Agent wywołuje: `mss_planning(plan_outline="...")`

> **UWAGA:** Serwer blokuje tę operację jeśli nie istnieje poprawny `summarize_details` pokrywający wszystkie `FILES AFFECTED`. Zwróci błąd i podpowie:
> - `mss.summarize_details` — Uzupełnij szczegóły per plik

**Jeśli warunek spełniony, `next_actions` po zapisie:**
- `mss.package` — Spakuj wynik planowania

---

## 8. Ścieżka: Package (`package`)

Agent wywołuje: `mss_package(summary="...")`

**`next_actions` po zapisie:**
- `mss.run` — Uruchom wykonanie pakietu

---

## 9. Ścieżka: Run (`run`)

Agent wywołuje: `mss_run(output="...")`

**`next_actions` po zapisie:**
- `mss.debug` — Przejdź do debugowania

---

## 10. Ścieżka: Debug (`debug`)

Agent wywołuje: `mss_debug(findings="...")`

**`next_actions` po zapisie:**
- `mss.end_debug` — Zakończ debugowanie

### Zakończenie debugowania
Agent wywołuje: `mss_end_debug(summary="...")`

**`next_actions` po zapisie:**
- `mss.status` — Sprawdź status sesji

---

## 11. Pipeline deweloperski: Guard → Test → Advance

To jest protokół używany **wewnątrz pętli kodowania** (niezależnie od trybów sesji powyżej).

### Krok A — Guard Report
Agent wywołuje: `guard_report(plan_dir, stage_id, stop_conditions_violated=False, details="...")`

Serwer ustawia w stanie: `sequence_hooks.guard_reported = true`

Zwraca: `{"received": true, "stage_id": "..."}`

### Krok B — Test Report (PASS)
Agent wywołuje: `test_report(plan_dir, stage_id, result="PASS", output="...", command="...")`

Serwer ustawia: `test_report_status = "ready_to_advance"`

**Odpowiedź serwera:**
```json
{
  "status": "ready_to_advance",
  "guard_result": { "verdict": "PASS", ... },
  "git_instruction": {
    "wip_commit_command": "git add . && git commit -m 'wip: <stage_id>'"
  }
}
```

### Krok B — Test Report (FAIL)
Serwer inkrementuje `retry_count`. Jeśli pozostały retry:

```json
{
  "status": "fail",
  "retry_available": true,
  "action_required": "retry",
  "git_instruction": {
    "rollback_command": "git reset --hard <last_stage_commit_sha_or_package_baseline>"
  }
}
```

Jeśli retries wyczerpane — `action_required: "stop"`, pipeline przechodzi w stan `stopped_retry_exhausted`.

### Krok C — Advance
Agent wywołuje: `stage_advance(plan_dir)`

Serwer przesuwa kursor, zeruje sequence_hooks. Jeśli Package zakończony — dostarcza instrukcje squash commita:
```json
{
  "pipeline_status": "running",
  "package_done": true,
  "git_instruction": {
    "squash_command": "git reset --soft <package_baseline_sha>",
    "squash_commit_command": "git commit -m 'feat: completed PACKAGE_X'"
  }
}
```

---

## 12. Sprawdzenie statusu bieżącego

W dowolnym momencie: `mss_status`

Serwer analizuje aktualny tryb i artefakty sesji i zwraca kontekstowe `next_actions`:
- Brak sesji → `connect`
- Tryb `audit` bez artefaktu → `audit`
- Tryb `audit` z artefaktem → `preplan` lub `show audit`
- Tryb `planning` bez preplanu → `preplan`
- Tryb `planning` z preplanem → `plan`
- Tryb `debug` bez `end_debug` → `mss.end_debug` (najwyższy priorytet)
- Tryb `debug` z `end_debug`, ale bez PASS w `summarize_details` → `mss.summarize_details`
- Tryb `workout` bez `workout` → `mss.workout`
- Tryb `workout` z `workout`, ale bez `end_workout` → `mss.end_workout`
- Tryb `workout` z `end_workout`, ale bez `summarize` → `mss.summarize`
- Tryb `workout` z `summarize`, ale bez PASS w `summarize_details` → `mss.summarize_details`
- Tryb `workout` z PASS w `summarize_details` → `mss.planning`

### Priorytet akcji statusowych vs podpowiedzi projektowe
- Dla `mode=debug` i `mode=workout` `mss_status` zwraca **jedną akcję sesyjną** wynikającą z gate (blokada end-to-end).
- Dla `mode=debug` i `mode=workout` nie są dokładane podpowiedzi wznowienia projektów (`plan_load_or_init`, `stage_current`).
- Podpowiedzi projektowe są dokładane dopiero dla trybów innych niż `debug/workout`.

Dodatkowo `mss_status` zwraca sekcję wykrytych projektów (tak jak `mss_connect`) i dokłada akcje:
- `plan_load_or_init <plan_id> <plan_dir>` dla każdego wykrytego projektu
- `stage_current <plan_dir>` dla projektów `in_progress` z runtime (`state.json` + `plan_cache.json`)
