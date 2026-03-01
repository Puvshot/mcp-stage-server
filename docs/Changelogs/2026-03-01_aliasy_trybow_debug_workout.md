---
date: "2026-03-01"
task: "aliasy_trybow_debug_workout"
status: "completed"
---

# Zmiana: Ujednolicenie wywołania trybów Debug i Workout

## 🎯 Cel / Problem
- **Problem:** Użytkownik nie miał pewności, czy powinien wpisać `workout`, czy `mode workout` po starcie MSS.
- **Cel:** Uprościć wybór trybu i doprecyzować komunikaty, aby obie formy były jednoznaczne.

## 📁 Zmodyfikowane Pliki
- `mss/tools/session.py`: Dodano aliasy `debug`/`workout` do `next_actions` i doprecyzowano onboarding.
- `tests/test_session.py`: Zaktualizowano oczekiwane `next_actions` dla połączenia MSS.
- `docs/Information/interactive_protocol.md`: Dodano skróty `debug`/`workout` i ich mapowanie na tryby.
- `docs/Information/usage.md`: Dodano instrukcję wyboru trybu skrótem lub pełną komendą.

## ☢️ Potencjalne Zagrożenia (Dla debugowania!)
- Klient/agenta może nadal implementować własne mapowanie komend, niezależne od `next_actions`.
- Użytkownik może pomylić `workout` (skrót wyboru trybu) z narzędziem artefaktowym `mss_workout`.
- Jeśli interfejs filtruje `next_actions`, aliasy mogą nie być widoczne mimo zmian po stronie MSS.

## 📝 Aktualizacja Głównej Dokumentacji
- [x] Czy ta zmiana wymaga aktualizacji głównej dokumentacji (`docs/usage.md`, `mss_session_tools.md` itp.)? (TAK)
- Zaktualizowano `docs/Information/interactive_protocol.md` o skróty i mapowanie.
- Zaktualizowano `docs/Information/usage.md` o instrukcję wyboru trybu (`debug`/`workout` i `mode ...`).
