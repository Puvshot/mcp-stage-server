---
date: "2026-03-01"
task: "integracja_blokad_status"
status: "completed"
---

# Zmiana: Integracja blokad gate z `mss_status` (spójność end-to-end)

## 🎯 Cel / Problem
- **Problem:** `mss_status` nie był w pełni spójny z gate dla trybów `debug` i `workout` (brak priorytetu kroków `end_debug`/`summarize_details PASS` oraz mieszanie podpowiedzi sesyjnych z podpowiedziami wznowienia projektów).
- **Cel:** Ujednolicić logikę `status` z warunkami gate i zapewnić deterministyczne, jednoznaczne `next_actions` zależne od stanu artefaktów.

## 📁 Zmodyfikowane Pliki
- `mss/engines/session_actions_policy.py`: Dodano warunki statusu zgodne z gate (`debug`: najpierw `mss.end_debug`, potem `mss.summarize_details`; `workout`: wymuszenie `mss.summarize_details` przy braku PASS).
- `mss/tools/session.py`: Podłączono odczyt PASS z artefaktu `summarize_details`, ustawiono priorytet jednej akcji sesyjnej dla `debug/workout`, ograniczono podpowiedzi projektowe do trybów innych niż `debug/workout`.
- `tests/test_session.py`: Dodano testy priorytetu akcji statusu i ukrywania project-resume hints dla `workout/debug`.
- `tests/test_mss_artifacts.py`: Dodano test integracyjny potwierdzający, że `mss_status` odzwierciedla kolejność i blokady gate.
- `docs/Documentation/interactive_protocol.md`: Uzupełniono opis `mss_status` o priorytety gate i warunkowe ukrywanie podpowiedzi projektowych.
- `docs/Documentation/mss_session_tools.md`: Uzupełniono sekcję Session Tools o reguły `status` dla `debug/workout`.

## ☢️ Potencjalne Zagrożenia (Dla debugowania!)
- Klienci oczekujący zawsze rozszerzonych podpowiedzi projektowych z `mss_status` mogą uznać brak tych wpisów w `debug/workout` za regresję (to zachowanie zamierzone).
- Jeżeli `summarize_details` istnieje, ale ma walidację `FAIL`, `status` będzie konsekwentnie wymuszał krok naprawczy; może to ujawnić wcześniejsze niespójne artefakty w starych sesjach.
- Integracje mapujące stare komendy bez prefiksu `mss.` mogą wymagać dostosowania do zwracanych akcji (`mss.end_debug`, `mss.summarize_details`).

## 📝 Aktualizacja Głównej Dokumentacji
- [x] Czy ta zmiana wymaga aktualizacji głównej dokumentacji (`docs/usage.md`, `mss_session_tools.md` itp.)? (TAK)
- Zaktualizowano `docs/Documentation/interactive_protocol.md` o priorytety gate w `mss_status`.
- Zaktualizowano `docs/Documentation/mss_session_tools.md` o spójność `status` z warunkami gate i zasady podpowiedzi projektowych.
