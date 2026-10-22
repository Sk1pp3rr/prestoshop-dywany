# Katalog `scraper/` – Narzędzie do Scrapowania `dywanyluszczow.eu` (`W2`, `D5`)

## Przeznaczenie katalogu
Zawiera kod źródłowy w języku Python 3.11+ odpowiedzialny za pobranie kategorii, podkategorii, produktów, wariantów rozmiarowych oraz zdjęć ze sklepu źródłowego `https://dywanyluszczow.eu/`, ich walidację oraz testy jednostkowe parsowania.

---

## Docelowa zawartość i struktura plików

```text
scraper/
├── pyproject.toml                  # Konfiguracja pakietu, zależności, Ruff oraz Pytest
├── src/
│   └── dywany_scraper/
│       ├── __init__.py
│       ├── main.py                 # Punkt wejścia CLI z obsługą przerywania i wznawiania (checkpoint)
│       ├── crawler.py              # Pobieranie stron z obsługą robots.txt, User-Agent i limitu <= 2 req/s
│       ├── parser.py               # Parsowanie HTML (BeautifulSoup4/lxml): kategorie, ceny, cechy, rozmiary
│       ├── image_processor.py      # Pobieranie i skalowanie zdjęć (Pillow: 800-1600 px, <= 300 KB)
│       └── models.py               # Schematy walidacji danych (Pydantic v2)
└── tests/
    ├── fixtures/                   # Zapisane lokalnie przykładowe pliki HTML ze sklepu dywanyluszczow.eu
    │   ├── category_page.html      # Przykładowa strona listy produktów w kategorii
    │   └── product_page.html       # Przykładowa karta produktu z atrybutami i wariantami
    ├── test_models.py              # Testy jednostkowe schematów walidacji Pydantic
    └── test_parser.py              # Testy jednostkowe parsowania lokalnych plików HTML (W2, D5)
```

---

## Kluczowe wymagania realizowane w tym katalogu

1. **Pobierane dane (`W2` [K]):**
   * Minimum **4 kategorie główne** (*Dywany, Chodniki, Wykładziny, Akcesoria*), każda mająca minimum **2 niepuste podkategorie**.
   * Minimum **1000 produktów**: nazwa, opis, cena brutto, stawka VAT (23%), cechy (wysokość runa, skład, gramatura $\text{kg/m}^2$), wyliczona waga w kg (do 50 kg) oraz warianty rozmiarowe.
   * **Zdjęcia:** minimum 1 zdjęcie na każdy produkt oraz minimum **2 zdjęcia dla co najmniej 50 produktów**.
2. **Przetwarzanie zdjęć (`W2`):**
   * Przeskalowanie tak, aby dłuższy bok miał **od 800 do 1600 px**.
   * Zapis w formacie **JPEG lub WebP** o rozmiarze pliku **$\le 300\text{ KB}$** (miniatury nie są akceptowane).
3. **Kultura pracy scrapera (`W2`):**
   * Ograniczenie tempa zapytań do **$\le 2$ zapytań na sekundę**.
   * Respektowanie pliku `robots.txt` oraz jawny nagłówek `User-Agent`.
   * Możliwość przerwania (`Ctrl+C`) i wznowienia pracy bez ponownego pobierania już zapisanych produktów.
   * Walidacja każdego rekordu przez **Pydantic** (`models.py`) i logowanie ewentualnych błędów.
4. **Jakość kodu i testy (`W2`, `D5`):**
   * Testy jednostkowe (`pytest`) działające offline na plikach z `tests/fixtures/`.
   * Kod sformatowany i sprawdzany linterem `ruff` w potoku CI.

---

## Jak uruchomić

```bash
cd scraper
pip install -e ".[dev]"

# Sprawdzenie jakości kodu (Linter + Formatter)
ruff check .
ruff format --check .

# Uruchomienie testów jednostkowych
pytest -v
```
