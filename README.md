# Sklep Internetowy PrestaShop 8.2.x – Odzież Damska (`prestoshop-dywany`)

Projekt studencki realizowany w ramach przedmiotu **Biznes Elektroniczny (Etap 1)**.  
System odwzorowuje sklep internetowy z odzieżą damską na podstawie danych ze sklepu `mosquito-sklep.pl`.

---

## 1. Stos technologiczny i wersje
* **Platforma sklepu:** PrestaShop `8.2.x` (`linux/amd64`)
* **Środowisko uruchomieniowe:** PHP `8.1`, MariaDB `10.11` / MySQL `8.0`
* **Konteneryzacja:** Docker Engine + Docker Compose v2 (`deploy/compose.yaml`)
* **Poczta testowa:** Mailpit (`axllent/mailpit`)
* **Scraper:** Python `3.11+` (`httpx`, `BeautifulSoup4`, `Pydantic v2`, `Pillow`, `pytest`, `ruff`)
* **Testy E2E:** Playwright (`headless`)

---

## 2. Struktura repozytorium

| Katalog | Zawartość | Dokumentacja szczegółowa |
| :--- | :--- | :--- |
| `shop/` | Kod źródłowy sklepu, motyw potomny (`classic-fashion`), moduły własne (`ps_omnibusprice`) | [`shop/README.md`](shop/README.md) |
| `scraper/` | Kod źródłowy narzędzia do scrapowania wraz z testami jednostkowymi (`pytest`) | [`scraper/README.md`](scraper/README.md) |
| `scraper-results/` | Wyniki scrapowania w UTF-8 (`JSON`) oraz do 20 przykładowych zdjęć | [`scraper-results/README.md`](scraper-results/README.md) |
| `tests/` | Kod źródłowy automatycznych testów E2E w Playwright | [`tests/README.md`](tests/README.md) |
| `deploy/` | `compose.yaml`, skrypty instalacji, inicjalizacji danych, importu API, backupu i odtwarzania | [`deploy/README.md`](deploy/README.md) |
| `docs/` | Dziennik AI ([`docs/AI_LOG.md`](docs/AI_LOG.md)), decyzje architektoniczne ([`docs/adr/`](docs/adr/)) | [`docs/README.md`](docs/README.md) |

---

## 3. Uruchomienie sklepu krok po kroku (z czystego klona)

1. **Klonowanie repozytorium i konfiguracja zmiennych środowiskowych:**
   ```bash
   git clone https://github.com/Sk1pp3rr/prestoshop-dywany.git
   cd prestoshop-dywany
   cp .env.example .env
   ```

2. **Uruchomienie kontenerów Docker Compose (Krok 1/2):**
   ```bash
   docker compose -f deploy/compose.yaml --env-file .env up -d --build
   ```

3. **Inicjalizacja danych sklepu i zdjęć produktów (Krok 2/2):**
   ```bash
   bash deploy/init.sh --with-import
   ```

* **Adres sklepu (HTTPS):** `https://localhost:8443` (przekierowanie HTTP $\rightarrow$ 301 HTTPS z portu `8080`)
* **Panel Mailpit (przechwytywanie e-maili):** `http://localhost:8025`

---

## 4. Uruchamianie testów i narzędzi

### Testy jednostkowe i linter scrapera (`W2`, `D5`)
```bash
cd scraper
pip install -e ".[dev]"
ruff check .
pytest -v
```

### Testy E2E Playwright (`W4`)
```bash
cd tests
npm ci
BASE_URL=https://localhost:8443 npx playwright test
```

---

## 5. Proces pracy w repozytorium (`W1`, `D5`)
* Gałąź `main` jest chroniona – wszystkie zmiany trafiają wyłącznie przez **Pull Requesty** zaakceptowane po Code Review przez inną osobę z zespołu.
* Każdy PR automatycznie uruchamia workflow [`.github/workflows/ci.yml`](.github/workflows/ci.yml) weryfikujący strukturę katalogów, limity plików, brak sekretów (`gitleaks`), linter (`ruff`) oraz testy jednostkowe (`pytest`).
* PR zawierające kod wspomagany przez AI są oznaczane etykietą `ai-assisted` i dokumentowane w [`docs/AI_LOG.md`](docs/AI_LOG.md).

## 6. Skład zespołu
* Wojciech Przyborski
* Paweł Marzec
* Franciszek Łaba
* Krzysztof Szady
* Karol Żurański
