---
title: "Narzędzia Ewaluacyjne (Evaluation: Guard & Test)"
type: Subsystem
scope: execution
criticality: absolute
status: active
---

# Narzędzia Ewaluacyjne (Guard & Test Report)

## 1. Cel i rola w architekturze
Rdzeniem filozofii MCP Stage Server jest weryfikowalność wykonanego przebiegu i blokowanie w pozycjach błędnych. Agent wykonuje kod (u siebie) a następnie **przed** wyjściem z pętli etapu zadaniowego musi zdać solidny "rachunek sumienia" z tego, co wytworzył, i potwierdzić ten stan wynikiem fizycznych testów z uruchomienia środowiska. 

Te dwa narzędzia chronią postęp przepływu w `state.json`.

## 2. Granice odpowiedzialności i wymuszony porządek (Sequence Hooks)
Narzędzia stanowią sprzężoną sieć logiczną - Guard Report musi pójść w pierwszej kolejności, a tuż po nim z wynikiem pozytywnym (Pass) musi nadejść raport z Unit Testów. Tylko ta jedyna logiczna ścieżka uprawnia agenta zaangażowanego w pętle dev cycle aby zaatakował metodę `stage_advance`. Próba ominięcia któregokolwiek rodzi błąd "ADVANCE_ON_FAIL" lub "ADVANCE_WITHOUT_TEST_REPORT".

## 3. Publiczne Narzędzia 

### I. `guard_report`
- **Typ wejścia:** Id stage, boolean weryfikacyjny dla Stop Conditions (`stop_conditions_violated`) i tekstowy raport (details).
- **Rodzaj akcji:** Agent przesyła podsumowanie sam weryfikując architekturę swojego wytworzonego potworka w plikach z żądanymi restrykcjami. Model musi zadecydować czy jego poprawki są dobre. Logika MSS oznacza to zdarzenie parametrem `sequence_hooks.guard_reported = true`. Oznacza to gotowość do wpuszczenia testów.

### II. `test_report`
- **Typ Wejścia:** Result ('pass' lub 'fail'), standardowe wyjście (output output z CLI), używana instrukcja w wierszu komend (`command`).
- **Rodzaj akcji:** Dostarczenie namacalnego faktu z shella, dowód na to czy zrzucono błąd czy aplikacja/plik/unit test świeci na zielono. 
- **Zależności stanów:**
  1. Jeżeli wysłano *pass* -> system przesuwa ukrytą dźwignie w `state.json` (`test_report_status="ready_to_advance"`). Wtedy kursor jest do przesterowania narzędziem `stage_advance`. Zawsze trzeba pamiętać o zgłoszeniu Guard Tool przed Test Tool by wąż hooka był poprawny.
  2. Jeżeli wysłano *fail* -> system nabija flagę błędu (`test_report_status="fail"`) i inkrementuje statystykę `retry_count` konkretnego zadania (stage). Model LLM musi jeszcze raz przebadać pliki, popoprawiać błędy, odpalić CLI test i rzucić `test_report` od nowa.
