---
title: "Narzędzia Etapu (Stage Tools)"
type: Feature Set
scope: execution
criticality: high
status: active
---

# Narzędzia Etapu (Stage Tools)

## Cel i rola w systemie
Rodzina tych narzędzi obsługuje precyzyjną, atomową nawigację kursora maszyny. Kursor znajduje się zawsze tylko i wyłącznie nad jednym zadaniem (Stage). Wszystkie operacje deweloperskie agentów powiązane są z tym wskaźnikiem. 

Narzędzia te implementują sztywne zasady przechodzenia do przodu i tyłu — w tym logikę zależności zdaniowych.

## Lista Narzędzi

### 1. `stage_current`
- **Rola:** Narzędzie kluczowe. Pobiera aktualny `StageSnapshot` z miejsca, w którym stoi kursor ze `state.json`. 
- **Treść Payloadu:** Zawiera listę plików w obrębie działań (files_in_scope), dokładny biznesowy punkt (krok) do dowiezienia, informacje statystyczne oraz (co kluczowe) **Collision Payload** zawierający raport ryzyka kolizji kodu z innymi etapami w pipeline.
- **Uwagi:** Read-only / deterministyczny na dany cykl. Jest to pierwsze narzędzie wywoływane w pętli devoloeperskiej po zmianie na kolejny step. Nie wykonuje żadnych ruchów. 

### 2. `stage_advance`
- **Rola:** Przepycha kursor (i status zadania na `done`) etapów maszyny systemowej krok dalej po pomyślnych sekwencjach weryfikacyjnych (Pass -> Guard -> Pass -> Test Report).
- **Zabezpieczenia (Hooks):** System chroni przed wywołaniem w sytuacji fałszywek. Zwróci `sequence_error`, jeśli zadanie nie zwróciło statusu `ready_to_advance` uzyskanych uprzednio przez równe wezwania narzędzi Guard / Test report. 
- **Generowanie commitów:** Gdy dobiega końca wyrenderowana paczka etapu (Package/Epic), narzędzie natychmiast wręcza LLM polecenia bashowe Git'owe do squasha komitów na etapy WIP. "Teraz zbuduj z tego 1 commit bazowy".

### 3. `stage_rewind`
- **Typ Wejścia:** Opcjonalny `reason` tekstowy.
- **Rola:** Odcofuje kursor procesu o krok wstecz by wrócić do poprzedniego zadania na którym został popełniony błąd (zepsuta implementacja itp.). Narzędzie zrzuca `retry_count` poprzednika dając agentowi szanse na próbę zrobienia pliku od nowa. Operacje te są idempotentne na pierwszym wymogu.

### 4. `stage_peek_next`
- **Rola:** Narzędzie read-only. Umożliwia wgląd do definicji planu nadchodzącego Stage'a bez przesuwania kursora, zazwyczaj by model LLM miał pełniejszy szerszy kontekst i nie nadpisywał pracy która nadejdzie logicznie tuż po jego evencie programowania. Skraca horyzont zdarzeniowy halucynacji AI.
