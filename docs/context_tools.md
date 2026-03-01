---
title: "Narzędzia Kontekstu / Pakietów (Rules & Exec Bundle)"
type: Feature Set
scope: execution
criticality: medium
status: active
---

# Narzędzia Kontekstu / Pakietów (Rules & Context Tools)

## Cel i rola w systemie
Rodzina zapytań read-only służących do pompowania agenta niezbędną wiedzą (kontekstem) w bezpiecznych dawkach. Agenci uruchamiają te narzędzia zanim wpiszą pierwszy znak kodu, chłonąc zasady architektoniczne lub weryfikując jakie biblioteki powinny pojawić się w projekcie.

## Lista Narzędzi

### 1. `rules_directive_pack`
- **Rola:** Dostarcza zbitkę zasad projektowych skrojoną dokładnie pod etap (Stage). Serwer łączy zasady z pliku projektu klienta `.rules` oraz wbudowane zasady ogólne (Global Defaults).

### 2. `rules_get_full`
- **Reżim Wywołania:** Narzędzie zarezerwowane (wymaga `MCP_DEBUG_VERBOSE=1`).
- **Rola:** Wyciąga strukturę JSON ze wszystkimi załadowanymi na serwer regułami. Przeznaczone dla debugowania parsowania reguł architektonicznych przez człowieka.

### 3. `rules_convert_md_to_json`
- **Rola:** Narzędzie pomocnicze do ręcznego przeparsowania Markdown z zasadami do SSOT JSON, by zweryfikować czy linter składniowy wychwytuje wszystkie zasady spisane przez inżyniera. Eksponowane na zewnątrz tylko w celach administracyjnych lub CLI.

### 4. `exec_directive_bundle`
- **Typ Wejścia:** `plan_dir`, `stage_id`, oraz limit długości znaków `char_limit`.
- **Rola:** Najpoteżniejsze narzędzie przygotowawcze dla agenta. Kompiluje *Execution Directive Bundle* - zbiór ścisłych wytycznych, instrukcji do wykonania z uwzględnieniem obcinania długiego tekstu (trimming rules) by wpasować się w okno kontekstu LLM.
- **Fail Modes:** Próba dostarczenia paczki do niezinicjalizowanego folderu lub zadania (Stage), które fizycznie nie istnieje w cache.

### 5. `rules_version`
- **Rola:** Funkcjonalny wskaźnik wersji (Hash). LLM może odpytać ten end-point by zobaczyć, czy w ogóle wgrywać nowe zasady (np. jeśli powrócił do pracy z projektem sprzed kilku dni, sprawdza czy `rules_hash` się nie zmienił).
