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
- **`mss_status`**: Informuje o obecnym stanie połączeń, trybie pracy, etc.
- **`mss_set_mode`**: Pozwala na przestawienie trybu analizy w systemie (np. tryb śledzenia błędów versus tryb planowania).

## 2. Narzędzia Zarządzania Artefaktami (Artifacts Tools)
Rodzina narzędzi, które nakazują agentowi trzymanie i generowanie raportów w wyznaczonych folderach, by użytkownik miał do nich przejrzysty wgląd. Wszystkie zapisują swoje przemyślenia w formie zrzutu tekstu / podsumowania (`summary`).
- **`mss_capabilities`**: Definiuje co dany serwer potrafi w danej fazie (jakie schematy raportów są wspierane).
- **`mss_list_artifacts` / `mss_get_artifact`**: Pozwala agentowi sprawdzić co on sam lub poprzedni agent zrzucił w raportach (wiedza ustrukturyzowana na nośniku trwałym).
- **`mss_planning` / `mss_prepare` / `mss_package`**: Zrzuty raportowe dotyczące procesu tworzenia zadań i dokumentacji.
- **`mss_audit`**: Raport z oceny jakości wykonania.
- **`mss_workout` / `mss_end_workout`**: Tworzenie notatek typu "log inżyniera" - start pracy i zwięzłe podsumowanie co udało się dzisiaj osiągnąć na koniec pracy.
- **`mss_debug` / `mss_end_debug`**: Raportowanie długotrwałych sesji zbijania błędów (np. trwająca długa walka z kompilatorem powinna skończyć się raportem "co ustaliliśmy").
- **`mss_summarize`**: Narzędzie zrzutu pełnego podsumowania (obecny wątek wiedzy wrzucany na dysk by następna instancja AI wiedziała na czym stoisz).

## 3. Execution Log & Audit Tail
Te narzędzia, choć zaliczane do szeroko pojętego raportowania, operują bezpośrednio na plikach deweloperskich (`execution_log.jsonl`, `runtime_audit.log`).
- **`execution_log_append` / `execution_log_read`**: Doklejenie na sam dół informacji o pomyślnie zrobionym pakiecie zadań (Append-only).
- **`audit_tail` / `audit_clear`**: Odczyt N-ostatnich linii pracy systemu deweloperskiego. Czyste narzędzia diagnostyczne.
