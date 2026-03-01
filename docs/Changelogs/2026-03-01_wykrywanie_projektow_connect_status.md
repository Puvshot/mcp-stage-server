---
date: "2026-03-01"
task: "wykrywanie_projektow_connect_status"
status: "completed"
---

# Zmiana: Wykrywanie projektów w `mss_connect` i `mss_status`

## 🎯 Cel / Problem
- **Problem:** Onboarding sesji MSS nie pokazywał listy projektów po stronie serwera ani komend wznowienia.
- **Cel:** Dodać automatyczne wykrywanie projektów z `data/projects/` oraz gotowe akcje kontynuacji.

## 📁 Zmodyfikowane Pliki
- `mss/tools/session.py`: Dodano skanowanie projektów, klasyfikację statusów i rozszerzone `message`/`next_actions`.
- `tests/test_session.py`: Dodano testy projektów gotowych i w toku dla `connect` oraz `status`.
- `docs/Documentation/interactive_protocol.md`: Uzupełniono protokół o sekcję wykrywania projektów i akcje.
- `docs/Documentation/usage.md`: Dodano opis `data/projects/`, `MSS_PROJECTS_DIR` i kryteriów klasyfikacji.
- `docs/Documentation/mss_session_tools.md`: Dodano sekcję integracji session tools z katalogiem projektów.

## ☢️ Potencjalne Zagrożenia (Dla debugowania!)
- Klient może nie obsługiwać długich `next_actions`; wtedy projektowe podpowiedzi mogą być częściowo niewidoczne.
- Ścieżki z `plan_dir` zawierające spacje wymagają poprawnego przekazywania argumentów przez warstwę kliencką.
- Błędny lub niekompletny `state.json` może zaniżyć status projektu do „zainicjalizowany”.

## 📝 Aktualizacja Głównej Dokumentacji
- [x] Czy ta zmiana wymaga aktualizacji głównej dokumentacji (`docs/usage.md`, `mss_session_tools.md` itp.)? (TAK)
- Zaktualizowano `docs/Documentation/interactive_protocol.md` o nowy kontrakt projektów i `next_actions`.
- Zaktualizowano `docs/Documentation/usage.md` o `data/projects/`, `MSS_PROJECTS_DIR` i klasyfikację.
- Zaktualizowano `docs/Documentation/mss_session_tools.md` o sekcję wykrywania projektów.