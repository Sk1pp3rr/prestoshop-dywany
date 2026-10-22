# ADR-001: Struktura repozytorium, ochrona gałęzi `main` oraz potok CI (GitHub Actions)

* **Status:** Zaakceptowano
* **Data:** 2026-10-22

## Kontekst
Wymagania obowiązkowe (`W1`) oraz dodatkowe (`D5`) narzucają ścisłą strukturę katalogów (`shop/`, `scraper/`, `scraper-results/`, `tests/`, `deploy/`, `docs/`), całkowity zakaz bezpośrednich commitów do gałęzi `main`, brak sekretów w historii repozytorium (`gitleaks`), limit rozmiaru repozytorium ($\le 200\text{ MB}$, brak plików $>10\text{ MB}$, maksymalnie 20 zdjęć przykładowych w `scraper-results/`) oraz automatyczne uruchamianie lintera i testów jednostkowych scrapera dla każdego Pull Requesta.

## Rozważane opcje
1. **Ręczna weryfikacja podczas Code Review** – poleganie wyłącznie na uwadze recenzenta PR przy sprawdzaniu struktury plików, formatowania kodu i obecności kluczy/haseł.
2. **Automatyczny strażnik repozytorium w GitHub Actions (`ci.yml`)** – zdefiniowanie dwuetapowego workflow (`repo-guard` + `scraper-ci`), który przy każdym PR automatycznie weryfikuje istnienie wymaganych katalogów, blokuje obecność pliku `.env`, sprawdza rozmiar plików i liczbę zdjęć w `scraper-results/`, skanuje historię narzędziem `gitleaks` oraz uruchamia `ruff` i `pytest`.

## Decyzja
Wybrano **Opcję 2** (automatyczny workflow `.github/workflows/ci.yml` wsparty szablonem `.github/pull_request_template.md`).

## Konsekwencje
* **Pozytywne:** Eliminacja ryzyka przypadkowego dołączenia pliku `.env`, zbyt dużych archiwów lub powyżej 20 zdjęć do commita (co skutkowałoby utratą punktów w warunkach krytycznych `[K]`).
* **Pozytywne:** Spełnienie wymagania `D5` (2 pkt) od samego początku projektu – każdy PR ma widoczny status lintera (`ruff`) i testów jednostkowych (`pytest`).
* **Negatywne / Koszt:** Konieczność utrzymywania poprawnego formatowania kodu w Pythonie przy każdym PR, aby pipeline był zielony przed scaleniem.
