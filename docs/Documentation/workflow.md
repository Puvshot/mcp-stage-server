---
title: "MSS - Flow Pracy (Jak Używać)"
type: Concept
scope: execution
criticality: high
status: active
---

# Cykl życia i Flow operacji (Workflow)

Korzystanie z MCP Stage Server (MSS) opiera się na restrykcyjnej maszynie stanów. Narzędzia blokują agenta wykonawczego przed samowolnym wyjściem ze struktury ustalonego planu. Należy stosować ścisłą kolejność operacji.

## 1. Inicjalizacja środowiska bazowego (Bootstrapping)
Przed rozpoczęciem jakichkolwiek modyfikacji kodu, Agent upewnia się, że proces jest załadowany.
1. **Pobranie lub stworzenie planu:** Jeżeli plan dostarczono w postaci plików Markdown (PLAN.md i PACKAGE_*.md w strukturze projektu), Agent wywołuje wyrenderowanie poprzez `plan_load_or_init`.
2. Opcjonalnie wstrzyknięcie czystego JSON (jeśli system macierzysty woli komunikację strukturalną): `plan_store`.
3. Następuje wygenerowanie lokalnego `state.json` oraz `plan_cache.json`.
4. Agent ustawia *baseline komit* by zabezpieczyć stan "sprzed" zmian używając instrukcji zwracanych przez init.

## 2. Pętla deweloperska (The Execution Loop)
Wykonanie składa się z rekurencyjnego chodzenia po zadaniach (Packages) i małych etapach (Stages) do wyczerpania:

### Krok A: Zrozumienie stanu bieżącego
1. Agent musi każdorazowo uruchomić **`stage_current`** by dowiedzieć się, który etap jest do zrobienia, które pliki ma zedytować i jak ma o tym pomyśleć. 
2. Agent może wezwać **`exec_directive_bundle`** dostając odciętą (żeby uszanować token limit LLM) i super precyzyjną radę od MSS jak to nakodować.
3. System wymusza sprawdzenia kolizji przez powłokę "Modyfikujemy aktualnie plik: src/app.js. Co jeżeli inny etap go dotykał."

### Krok B: Wykonanie (Faza Agenta)
1. Narzędzia MCP same nie edytują kodu z perspektywy MSS. To uzytkownik/powłoka (np. AI IDE) modyfikuje, przepisuje programy lokalnie w IDE, w plikach użytkownika.

### Krok C: Walidacja jako stróż samego siebie (Guard)
1. Po kodowaniu The Agent (Ty, wykonawca) wysyła do MSS wezwanie funkcji **`guard_report`**:  
   - Przekazujesz id operacji, raport o tym czy kod został sprawdzony przez linter i czy nie powielono architektury. 
   - State `guard_reported` ustawione na TRUE. Brak podania do Guard rzuca błędem, że nie sprawdziłeś przed testem.

### Krok D: Testing i zdanie raportu
1. Następuje uruchomienie komendy testującej w shellu. Następnie wywołane zostaje wejście **`test_report`**.
   - Raport ma obowiązkowe flagi *PASS* / *FAIL*.
   - Serwer sprawdza, czy `test_report_status` to `ready_to_advance` lub nie.
   - Fail powoduje podbicie `retry_count` na tym zadaniu. W skrajnych sytuacjach zatrzymania - manualnie wpuszczamy `stage_rewind` (wróć, usuń chłam, jeszcze raz).

### Krok E: Zmiana stanu i popchnięcie (Advance)
1. Jak test zaświecił się na zielono, odpalane jest **`stage_advance`**.
2. Serwer w `state.json` zmienia wskaźniki (`stage_index + 1`).
3. Zwracane są nowo aktywowane etapy i instrukcje Gitowe jak np. spłaszczenie komitów (`feat: completed PACKAGE_X`).
4. Jeżeli paczka jest 100% zrobiona, serwer zmienia na wyższy `package_index`.

Wracamy do Kroku A aż `pipeline_status` zwróci `complete` a kursor dojdzie na sam koniec. Serwer jest w 100% deterministyczny (koncept maszyny turinga nad aplikacją).
