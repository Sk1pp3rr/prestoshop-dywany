# Dziennik wykorzystania narzędzi AI (`AI_LOG.md`)

Zgodnie z zasadami projektu, każdy istotny fragment kodu lub konfiguracji wygenerowany przy wsparciu narzędzi AI jest odnotowywany w poniższej tabeli w tym samym Pull Requeście (oznaczonym etykietą `ai-assisted`).

## Rejestr użycia AI – Etap 1

| Data i autor | Narzędzie i model | Zadanie (Issue / PR i cel użycia) | Co otrzymano | Co było błędne | Weryfikacja |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 2026-10-22, Zespół | Antigravity (Gemini) | Inicjalizacja planu realizacji (`PLAN_REALIZACJI.md`), struktury katalogów (`W1`) i pipeline'u CI (`D5`) | Wygenerowano strukturę katalogów (`shop/`, `scraper/`, `scraper-results/`, `tests/`, `deploy/`, `docs/`), konfigurację `.gitignore`, `.env.example`, szkielet pakietu `scraper` z Pydantic/Pytest/Ruff oraz workflow `.github/workflows/ci.yml`. | Domyślny `README.md` w repozytorium był zapisany w kodowaniu UTF-16LE zamiast UTF-8; wymagane było przekonwertowanie go na standardowe UTF-8 oraz doprecyzowanie reguł wykluczeń `.gitignore` pod PrestaShop 8.2 i limit 20 zdjęć przykładowych. | Uruchomiono lokalnie walidację struktury katalogów oraz linter `ruff` i testy `pytest`; zweryfikowano brak sekretów i zgodność z wytycznymi Etapu 1. |
| 2026-10-22, Zespół | Antigravity (Gemini) | Dokumentacja zawartości poszczególnych katalogów projektu (`README.md` w każdym katalogu – `W1`, `D6`) | Wygenerowano szczegółowe pliki `README.md` dla katalogów `shop/`, `scraper/`, `scraper-results/`, `tests/`, `deploy/`, `docs/` oraz `docs/adr/`, opisujące docelową strukturę plików, metryki odbioru i wykluczenia Git. | Początkowe wersje plików `README.md` w podkatalogach były zbyt skrótowe i nie zawierały pełnego drzewa docelowych plików ani konkretnych progów metryk (np. limitu wag 50 kg czy progu Lighthouse). | Ręczny przegląd wszystkich 7 plików `README.md` pod kątem zgodności z wymaganiami obowiązkowymi (`W1`–`W4`), dodatkowymi (`D1`–`D6`) oraz tabelą metryk. |

---

## Refleksja zespołu (Podsumowanie Etapu 1)

*(Sekcja do finalnego uzupełnienia przed wydaniem tagu `etap1` – do 1 strony)*

### 1. Gdzie AI realnie przyspieszyło pracę?
* Szybkie przygotowanie szkieletu infrastruktury Docker Compose, konfiguracji CI/CD (GitHub Actions) oraz schematów walidacji danych w Pydantic v2.
* Analiza struktury DOM sklepu źródłowego `dywanyluszczow.eu` i wygenerowanie selektorów dla cech dywanów (wysokość runa, skład, gramatura).

### 2. Gdzie AI wprowadziło w błąd lub wymagało korekty?
* *(Do uzupełnienia w trakcie prac nad scraperem, API PrestaShop 8.2 i testami Playwright)*

### 3. Czego zespół musiał nauczyć się samodzielnie?
* *(Do uzupełnienia – np. specyfika Webservice API PrestaShop 8.2, konfiguracja statusów zamówień pod generowanie faktury PDF przy płatności za pobraniem, optymalizacja obrazów pod limit 300 KB).*
