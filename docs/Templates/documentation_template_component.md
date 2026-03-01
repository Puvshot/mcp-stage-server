---
type: [Typ architektoniczny, np. System, Component, Subsystem, Module, Concept]
scope: [Zakres odpowiedzialności, np. global, local, execution, analysis]
criticality: [Poziom krytyczności dla całości: absolute, high, medium, low]
status: [Obecny stan: active, deprecated, draft]
---

# [Nazwa Komponentu] ([Opcjonalny Skrót])

## 1. Cel i rola w architekturze
> **[Zwięzły, ale wyczerpujący opis całego zamysłu komponentu. Należy dokładnie wytłumaczyć miejsce bytu w architekturze oraz powód jego istnienia.]**

Rolą [Nazwa Komponentu] jest zapewnienie:
- [kluczowa funkcja lub dostarczana wartość 1]
- [kluczowa funkcja lub dostarczana wartość 2]
- [kolejne funkcje...]

[Opcjonalne, jednozdaniowe podsumowanie natury komponentu, informujące czym ten obiekt w swojej istocie JEST lub czym NIE JEST].

## 2. Granice odpowiedzialności
[Krótkie wprowadzenie, definiujące ogólny podział odpowiedzialności]

W zakresie [Nazwa Komponentu]:
- [obszar odpowiedzialności 1]
- [obszar odpowiedzialności 2]
- [kolejne obszary]

Poza zakresem:
- [wyraźne wskazanie zadań lub obszarów, w które ten komponent celowo nie ingeruje]
- [kolejne wykluczenia]

## 3. Model danych 
[Definicja kluczowych bytów, na których operuje lub które odczytuje komponent. Opcjonalnie podział na logiczne kategorie danych]

### [Kategoria 1]
- [element modelu 1]
- [element modelu 2]

### [Kategoria 2]
- [element modelu 1]

Relacyjnie:
- [Przedstawienie przepływu danych lub stanów między bytami, jeśli dotyczy]

## 4. Format przechowywania
[Wymienienie technologii, formatów lub mechanizmów użytych do zapisu danych i stanu przez ten komponent]
- [sposób składowania 1]
- [sposób składowania 2]

## 5. Publiczne API / operacje
Z perspektywy zewnętrznej [Nazwa Komponentu] eksponuje następujące logiczne operacje:
- [wywoływana operacja / akcja 1]
- [wywoływana operacja / akcja 2]

[Informacja o mechanizmie delegacji lub wykonania tych operacji].

## 6. Lifecycle i stany
Cykl życia dla [Nazwa Komponentu]:
1. [STAN_LUB_ETAP_1]
2. [STAN_LUB_ETAP_2]
3. [Kolejne stany]

[Dodatkowy opis mechanizmu zmiany stanów lub wznawiania cyklu].

## 7. Integracje i zależności
Wewnętrzne integracje w ramach ekosystemu:
- [[Nazwa Komponentu Zależnego]](../wzgledna/sciezka/do/pliku.md)
- [[Kolejny Komponent]]('./inna_sciezka.md')

Zewnętrzne integracje (poza aktualnym systemem):
- [Nazwa integracji zewnętrznej 1]
- [Nazwa integracji zewnętrznej 2]

## 8. Failure modes i bezpieczeństwo
Potencjalne ryzyka w działaniu komponentu:
- [zidentyfikowane ryzyko 1]
- [zidentyfikowane ryzyko 2]

Wdrożone mechanizmy ochronne (mitygacje):
- [mechanizm ochronny 1]
- [mechanizm ochronny 2]

## 9. Wydajność / skalowanie
[Nazwa Komponentu] buduje wydajność lub skaluje się poprzez:
- [zastosowany mechanizm 1]
- [zastosowany mechanizm 2]

[Dodatkowy opis strategii wydajnościowej dla tego komponentu].

## 10. Klasyfikacja architektoniczna
- Typ: [Rodzaj wzorca/architektury]
- Zakres: [Zasięg oddziaływania]
- Krytyczność: [Poziom ważności biznesowej/technicznej]
- Determinizm: [Rodzaj determinizmu operacji, np. deterministyczny, heurystyczny, hybrydowy]
- Mutowalność: [Poziom i mechanizm dozwolonych mutacji]
