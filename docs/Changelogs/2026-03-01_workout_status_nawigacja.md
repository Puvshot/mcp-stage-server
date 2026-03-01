---
date: "2026-03-01T14:21:00"
task: "workout_status_nawigacja"
status: "completed"
---

# Zmiana: Deterministyczna nawigacja `mss_status` dla trybu `workout`

## 🎯 Cel / Problem
- **Problem:** W `workout` status mógł prowadzić od razu do `mss.summarize_details`, co bez wcześniejszego `summarize` (sekcja `FILES AFFECTED`) powodowało FAIL i pętlę.
- **Cel:** Ustawić deterministyczną sekwencję kroków w `workout`: rozmowa/notatki → domknięcie workout → summarize → summarize_details (PASS) → planning.

## 📁 Zmodyfikowane Pliki
- `mss/engines/session_actions_policy.py`: Zmieniono policy `next_actions` dla `set_mode(workout)` oraz pełną sekwencję `next_actions_for_status()` w `mode=workout` (`mss.workout` → `mss.end_workout` → `mss.summarize` → `mss.summarize_details` → `mss.planning`).
- `tests/test_session.py`: Zaktualizowano oczekiwania dla statusu `workout` i dodano asercję `set_mode(workout)` z pierwszą sugestią `mss.workout`.
- `tests/test_mss_artifacts.py`: Zaktualizowano test statusu i dodano łańcuch regresyjny potwierdzający kolejne kroki oraz finalne przejście do `mss.planning` po PASS w `summarize_details`.
- `docs/Documentation/interactive_protocol.md`: Doprecyzowano ścieżkę `workout` i kontrakt `mss_status` zgodnie z nową sekwencją.
- `docs/Documentation/mss_session_tools.md`: Rozszerzono sekcję kontraktu `mss_status` o szczegółową kolejność działań dla `mode=workout`.

## ☢️ Potencjalne Zagrożenia (Dla debugowania!)
- Integracje oczekujące starego `next_actions` w `workout` (bezpośrednio `mss.summarize_details`) mogą wymagać aktualizacji mapowania komend.
- Jeśli sesja ma niespójne/stare artefakty, nowa deterministyczna kolejność może ujawnić brakujące kroki wcześniej „maskowane” przez starą podpowiedź statusu.

## 📝 Aktualizacja Głównej Dokumentacji
- [x] Czy ta zmiana wymaga aktualizacji głównej dokumentacji (`docs/usage.md`, `mss_session_tools.md` itp.)? (TAK)
- Zaktualizowano `docs/Documentation/interactive_protocol.md` (ścieżka Workout + status).
- Zaktualizowano `docs/Documentation/mss_session_tools.md` (kontrakt `mss_status` dla `mode=workout`).