---
title: "MCP Stage Server - Architektura i Koncepcja Główna"
type: System
scope: global
criticality: high
status: active
---

# MCP Stage Server (MSS) - Overview

## 1. Cel i rola w architekturze
**MCP Stage Server (MSS)** to serwer narzędziowy oparty na protokole **Model Context Protocol (FastMCP)**, którego zadaniem jest orkiestracja i wymuszanie sztywnych procesów wytwarzania oprogramowania ("Planów") przez agentów AI. 

System działa jako **zewnętrzna maszyna stanów (State Machine)**, pozwalająca odciążyć limitowany kontekst pamięci (context window) modeli językowych. Odbiera on od agenta plany działania i w rygorystyczny sposób egzekwuje ich realizację krok po kroku (Package -> Stage), z wbudowanymi bezpiecznikami: walidacja architektoniczna (Guard), testowanie kodu (Test) i wykrywanie kolizji (Collision).

## 2. Podział dokumentacji
Pełna dokumentacja systemu rozbita jest na poszczególne domeny działań i narzędzi (tools):

1. **[Narzędzia Planowania (Plan Tools)](plan_tools.md)** - wczytywanie, transformacja i sterowanie planem działania.
2. **[Narzędzia Etapu (Stage Tools)](stage_tools.md)** - odczyt bieżącego zadania (kursor) i nawigacja po etapach (advance / rewind).
3. **[Narzędzia Ewaluacyjne (Evaluation: Guard & Test)](eval_tools.md)** - wymuszanie raportowania kodu przed zakończeniem zadania.
4. **[Narzędzia Kontekstu / Pakietów (Rules & Exec Bundle)](context_tools.md)** - wstrzykiwanie odpowiednich reguł i komend dla agenta tworzącego kod.
5. **[Narzędzia Sesji MSS (MSS Tools)](mss_session_tools.md)** - interfejsy raportowe (artifacts: audit, package, summarize).
6. **[Proces / Flow Użycia (Workflow)](workflow.md)** - scenariusz jak prawidłowo posługiwać się serwerem od inicjalizacji planu po jego zakończenie.

## 3. Kluczowe pojęcia (Słownik)
- **PlanCache (`plan_cache.json`)**: Scentralizowana, generyczna wersja planu wgrana do pamięci i przechowywana na dysku. Jest wynikiem kompilacji z plików Markdown lub pliku JSON. W 100% deterministyczna.
- **Runtime State (`state.json`)**: Plik operacyjny z aktualną pozycją kursora. Zarządza wskaźnikami `package_index`, `stage_index`, oraz aktualnym stanem maszyny stanow (`pipeline_status`, powtórki `retry_count`, wymogi blokad `sequence_hooks`).
- **Workspace (`plan_dir`)**: Katalog projektu klienta przekazany przez agenta (zwykle folder operacyjny kodowania), gdzie wstrzykiwane są pliki stanu, np. folder docelowy aplikacji.
- **Guard Report**: Oświadczenie agenta wykonawczego po kodowaniu ("Sprawdziłem reguły, napisałem to dobrze"). Musi wystąpić przed statusem testu (Test Report).
- **Test Report**: Twardy wynik sprawdzenia oprogramowania. Zwraca PASS lub FAIL. Dopiero po uzyskaniu PASS w Test Report serwer pozwala na komendę przesuwającą kursor: `stage_advance`.
