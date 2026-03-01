---
date: "2026-03-01T20:00:00"
task: "MSS_Packages_Stages"
status: "completed"
---

# Zmiana: Wdrożenie mechanizmu MSS Packages & Stages

## 🎯 Cel / Problem
- **Problem:** Wcześniejsza struktura sesji w warstwie zarządzania wiedzą (Session Tools & Artifacts) przypisywała wszystkie artefakty po abstrakcyjnym `session_id`, co tworzyło bałagan w organizacji i trudności w wznawianiu pracy pomiędzy wieloma mniejszymi sesjami. Ponadto, instrukcje i blokady z zakresu polityk sesji były nierzadko naruszane przez model (brak nakazania użytkownikowi zatwierdzania etapów oraz omijanie kroków `mss_summarize`/`mss_summarize_details`).
- **Cel:** Reforma układu plików na ścisłe grupowanie poprzez foldery faz (`audit/`, `planning/`, `prepare/`, `workout/`, `debug/`, `run/`, `package/`) ulokowane wewnątrz folderów poszczególnych projektów (`<project_name>`). Dodatkowo wdrożenie sztywnych blokad instrukcyjnych (w `mss_summarize`, `mss_end_workout`, `mss_end_debug`) nakazujących modelowi konsultacje i stosowanie szczegółowej kompresji plików przed przejściem do kodowania.

## 📁 Zmodyfikowane Pliki
- `mss/storage/session_store.py`: Przeprojektowanie sposobu zapisu pliku `session.json`, usunięcie starych ścieżek opartych na ID, obsługa folderów `_pending/` oraz migracji na strukturę projektową. Zmodyfikowana metoda `set_active_session` przyjmująca opcjonalny `project_name`.
- `mss/storage/artifact_store.py`: Implementacja stałej mapy fazowej `_ARTIFACT_PHASE_MAP`, dynamicznie wyliczającej, do którego folderu projektowego ma trafić nowo wywołany artefakt. Zależności na bazie parametru `mode`.
- `mss/tools/session.py`: Narzędzie `connect()` domyślnie tworzy projekty w `_pending/`. Wywołanie `set_mode` na `debug` lub `workout` weryfikuje istnienie projektu, przenosi struktury po ścieżce i rejestruje `project_name` w zarchiwizowanej wiedzy.
- `mss/tools/mss_artifacts.py`: Aktualizacja opisów i wiadomości zwrotnych wracających do promptu (Fix H i Fix J). Zwracane mocne sygnały `STOP` zmuszające model do spytania użytkownika o pozwolenie wejścia w dany etap lub wymuszające szybkie przejście do ewaluacji plików `files_affected` bez skręcania w generację kodu.
- `mss/engines/session_actions_policy.py`: Zaktualizowana nomenklatura przejścia miedzy etapami (zmiana `preplan` na `prepare`).
- `mss/engines/mss_session_discovery.py` *(nowy)*: Nowy silnik do skanowania starych statusów sesji i uzupełniania wyników `status()` i podpowiedzi `connect()` listą gotowych i wygasłych do odnowienia instancji pracy pod folderem `data/sessions/`.
- `docs/Documentation/mss_session_tools.md`: Aktualizacja architektury.

## ☢️ Potencjalne Zagrożenia (Dla debugowania!)
- Dawne, testowe ID sesji wygenerowane przed łatką mogą nie być możliwe do ponownego poprowadzenia (wymagany start nową sesją od zera, co zostało wdrożone skryptem pre-deployement typu `rm data/sessions/*`).
- Jeśli ścieżka systemowa do pliku aktywnej sesji napotka konflikt zapisu JSON przy dużej utracie spójności dysku podczas trwającego skryptu migracji nazwy projektu, sesja spadnie do stanu niestabilnego (chociaż funkcja `_migrate_pending` została odizolowana try-catch ze skrawkiem wycofywania). 
- Brakujące foldery faz podczas pierwszego przechodzenia ślepych korytarzy będą utworzone w locie. Mogą być puste do pierwszej operacyjnej migracji.

## 📝 Aktualizacja Głównej Dokumentacji
- [x] Opracowano dedykowany changelog.
- [x] Główne instrukcje użytkowania Session & Artifact w `mss_session_tools.md` zostały zaktualizowane, odzwierciedlając ścisłe fazowanie folderów oraz nowe warunki dla `debug`.
