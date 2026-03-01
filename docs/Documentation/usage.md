---
title: "Instrukcja Użycia Servera (Usage Guide)"
type: Documentation
scope: execution
criticality: medium
status: active
---

# Instrukcja Konfiguracji i Użycia (Usage Guide)

## 1. Wprowadzenie
MCP Stage Server (MSS) funkcjonuje jako standardowy serwer Model Context Protocol komunikujący się za pomocą standardowego wejścia/wyjścia (`stdio`). Oznacza to, że nie nasłuchuje on lokalnie na porcie HTTP, lecz jest uruchamiany bezpośrednio "pod spodem" przez Twojego Agenta AI (np. w środowisku VS Code przez rozszerzenie takie jak *RooCode / Cline* lub w aplikacji stacjonarnej *Claude Desktop*).

Poniżej znajdziesz kompletne instrukcje na to, jak sprawić, by ten serwer "odżył" i jak skonfigurować go w najpopularniejszych środowiskach deweloperskich sztucznej inteligencji.

---

## 2. Instalacja i środowisko
Serwer napisany jest w języku Python i wymaga środowiska wspierającego paczki zdefiniowane w Twoim systemie, takich jak biblioteka `mcp`. 

**Wymagania:**
- Python w wersji `>= 3.11`.
- Zainstalowane wymagania ukryte w module. Najwygodniej posługiwać się narzędziem `uv` lub klasycznym `pip`.

Głównym punktem wejściowym całej aplikacji jest plik:
```bash
src/mss_server/main.py
```

---

## 3. Konfiguracja w klientach MCP

Aby Twój agent, współpracujący z Tobą nad rozwojem projektu, mógł zobaczyć narzędzia dostarczane przez (Plan Tools, Stage Tools), musisz poinformować go o tym, że istnieje serwer MCP Stage Server. Możesz osiągnąć to dopisując serwer do pliku konfiguracyjnego `mcp_settings.json` lub pliku instalatora serwerów w Twoim IDE:

### Przypadek A: Uruchomienie za pomocą interpretera globalnego / wirtualnego:
```json
{
  "mcpServers": {
    "mcp-stage-server": {
      "command": "python",
      "args": [
        "Bezwzględna/Sciezka/Do/src/mss_server/main.py"
      ],
      "env": {
        "PYTHONPATH": "Bezwzględna/Sciezka/Do/mcp-stage-server"
      }
    }
  }
}
```

### Przypadek B: Optymalne użycie via narzędzie `uv` (rekomendowane):
Jeżeli korzystasz z menedżera pakietów `uv`:
```json
{
  "mcpServers": {
    "mcp-stage-server": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "Bezwzględna/Sciezka/Do/mcp-stage-server",
        "src/mss_server/main.py"
      ],
      "env": {
         "MCP_DEBUG_VERBOSE": "0" 
      }
    }
  }
}
```

---

## 4. Tryb Debugowania (Verbose Mode)
Niektóre z narzędzi deweloperskich, eksponujących tzw. całą prawdę o funkcjonowaniu serwera, domyślnie są zablokowane dla Agenta by nie zaśmiecać jego horyzontu (context limits). Przykładem jest narzędzie `plan_export` albo `rules_get_full`.

Jeśli potrzebujesz ich użyć lub kazać modelowi zrzucić stan maszyny zbrojeniowej i przejrzeć jego cache - musisz wymusić flagę w konfiguracji serwera ustawiając zmienną środowiskową:

```env
MCP_DEBUG_VERBOSE=1
```
Znajdziesz to w bloku `env: {}` podczas wpisywania komendy ładującej.

---

## 5. Jak działa sesja deweloperska (Start Agenta)

1. **Uruchomienie serwera:** Po dodaniu w/w konfiguracji w swoim środowisku, zrestartuj IDE. Poinfromuje ono, że nawiązało połączenie po protokole Transport STDIO.
2. **Sprawdzenie narzędzi:** Twój Agent AI na pasku dostępnych narzędzi (w zakładkach narządzi) powinien widzieć zestaw zaczynający się m.in. od `mss_connect`, `plan_load_or_init`, `stage_current`.
3. **Nawiązanie połączenia (Interaktywne menu):** Najprostszym sposobem na rozpoczęcie pracy jest napisanie do Agenta AI krótkiej komendy:
   > "Połącz się z MSS"
   
   Agent wywoła `mss_connect` i w odpowiedzi **przekaże Ci powitanie serwera**, pytając, jaką operację chcesz wykonać. Domyślnie serwer podpowie Agentowi, aby zaproponował Ci interaktywne tryby wsparcia:
   - **Debug** – włączenie ścisłego protokołu do diagnozowania i naprawy błędów kodu.
   - **Workout** – wejście w tryb burzy mózgów i planowania projektów architektonicznych bez "pisania kodu na ślepo".
   
   Możesz wybrać tryb na dwa sposoby:
   - skrótem: `debug` albo `workout`
   - pełną komendą: `mode debug` albo `mode workout`
   
4. **Przejście do kodowania (Opcjonalnie):** Oprócz luźnych trybów sesyjnych (jak Debug/Workout), możesz od razu kazać mu działać na konkretnym planie budowy. Wtedy piszesz:
   > "Rozpocznijmy zadanie z planu deweloperskiego. Wczytaj `plan_load_or_init` z katalogu X, a następnie zanalizuj etap: `stage_current`".
5. Odtąd, agent będzie przestrzegał sztywnej maszyny stanów określonej w odpowiednio załadowanym planie.

### 5.1 Automatyczne wykrywanie projektów (`data/projects`)
Po połączeniu (`mss_connect`) oraz przy odczycie statusu (`mss_status`) MSS może automatycznie wyświetlić
listę projektów wykrytych po stronie serwera.

Domyślny katalog skanowania:
- `data/projects/`

Opcjonalny override:
- zmienna środowiskowa `MSS_PROJECTS_DIR`

#### Jak MSS klasyfikuje projekty
- **Gotowe / zainicjalizowane**:
  - istnieje `plan_cache.json`, lub
  - istnieje `state.json` z `pipeline_status=complete`.
- **W toku / zatrzymane**:
  - istnieje `state.json` z `pipeline_status != complete`.

#### Jakie komendy zobaczysz w `next_actions`
- `plan_load_or_init <plan_id> <plan_dir>` — dla każdego wykrytego projektu.
- `stage_current <plan_dir>` — tylko dla projektów `in_progress` z pełnym runtime
  (`state.json` + `plan_cache.json`).

---

## 6. Co użytkownik musi umieścić w projekcie
Aby po wpisaniu tego w IDE, system i server zadziałały:
1. Skopiować przynajmniej dwa pliki szablonowe (Markdown): 
   - Plik `PLAN.md` -> w którym opiszesz ogólny **Goal / Scope** jako tekst dla robota.
   - Plik `PACKAGE_1.md` -> w którym rozbijesz swojemu asystentowi co ma zaprogramować na etapy (`stages`).
2. Tę paczkę plików trzymasz w jednym folderze z kodem źródłowym programu. Ścieżkę do tego folderu podajesz Agentowi do ładowania przy pierwszej promtce konwersacji (tzw. `plan_dir`).
