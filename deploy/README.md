# Katalog `deploy/` – Konteneryzacja, Inicjalizacja, Import API i Backup (`W3`, `D2`, `D4`)

## Przeznaczenie katalogu
Zawiera definicję środowiska kontenerowego **Docker Compose v2** oraz wszystkie skrypty automatyzujące uruchomienie sklepu, wygenerowanie certyfikatu SSL, inicjalizację danych, idempotentny import przez Webservice API oraz tworzenie i odtwarzanie kopii zapasowej.

---

## Docelowa zawartość i struktura plików

```text
deploy/
├── compose.yaml                    # Definicja usług Docker Compose v2 (bez klucza 'version:') (W3 [K])
├── nginx/
│   ├── nginx.conf                  # Konfiguracja Reverse Proxy: HTTP (:80) -> 301 HTTPS (:443) (W3 [K])
│   └── generate-certs.sh           # Skrypt generujący certyfikat self-signed SSL (openssl)
├── init.sh                         # Główny skrypt inicjalizacji danych sklepu i zdjęć (<= 15 min) (W3 [K])
├── activate-theme.sh               # Skrypt aktywacji motywu potomnego classic-fashion i banera (D1)
├── seed-images.php                 # Seeder zdjęć 3:4 do motywu/banerów (D1)
├── import_api.py                   # Idempotentny skrypt importu produktów i kategorii przez Webservice API (D2)
├── export-config.sh                # Eksport zanonimizowanej konfiguracji do shop_base_config.sql (D4)
├── import-config.sh                # Import konfiguracji z shop_base_config.sql i czyszczenie cache (D4)
├── backup.sh                       # Skrypt tworzący kopię zapasową bazy i plików wolumenu ps_data (D4)
├── restore.sh                      # Skrypt odtwarzający sklep z kopii zapasowej w <= 10 min (D4)
└── config-export/                  # Zanonimizowany eksport konfiguracji sklepu (bez sekretów i danych RODO) (D4)
    └── shop_base_config.sql        # Konfiguracja przewoźników, podatków, stron CMS, płatności i statusów
```

---

## Kluczowe wymagania realizowane w tym katalogu

1. **Docker Compose v2 i HTTPS (`W3` [K]):**
   * Plik `compose.yaml` (bez przestarzałego klucza `version:`) uruchamiany komendą `docker compose`.
   * Wszystkie kontenery działają na architekturze `linux/amd64`.
   * Obsługa ruchu wyłącznie przez **HTTPS** z certyfikatem self-signed oraz przekierowaniem **HTTP $\rightarrow$ 301 HTTPS**.
   * Kontener **Mailpit** (`axllent/mailpit`) przechwytujący wszystkie wiadomości e-mail wysyłane przez PrestaShop (rejestracja, potwierdzenie zamówienia).
2. **Uruchomienie w dwóch krokach w $\le 15\text{ min}$ (`W3` [K]):**
   * Krok 1: uruchomienie kontenerów (`docker compose -f deploy/compose.yaml up -d`).
   * Krok 2: uruchomienie `deploy/init.sh`, który pobiera paczkę zdjęć z **GitHub Releases** (lub w razie braku pobiera je z adresów źródłowych z `scraper-results/products.json`) i zasila sklep kompletem $\ge 1000$ produktów, kategorii oraz konfiguracją przewoźników i płatności.
3. **Import danych przez Webservice API (`D2` – 4 pkt):**
   * Skrypt `import_api.py` tworzy/aktualizuje kategorie, podkategorie, produkty, zdjęcia, stany magazynowe ($0-10$ szt., w tym $5-20\%$ niedostępnych), wagi oraz warianty przez oficjalne API PrestaShop.
   * **Idempotentność:** ponowne uruchomienie nie tworzy duplikatów (liczba produktów przed i po drugim uruchomieniu jest identyczna).
   * Klucz API przekazywany zmienną środowiskową `PRESTASHOP_API_KEY`.
   * Na końcu wypisuje raport: liczba rekordów utworzonych (`Created`), zaktualizowanych (`Updated`) i odrzuconych (`Rejected`).
4. **Backup i odtwarzanie (`D4` – 3 pkt):**
   * `backup.sh` wykonuje zrzut bazy danych MySQL/MariaDB, archiwizuje zdjęcia produktów oraz pliki konfiguracyjne do katalogu `deploy/backups/` (wykluczonego w `.gitignore`).
   * `restore.sh` odtwarza pełny stan sklepu na czystym środowisku w czasie **$\le 10\text{ minut}$**.

---

## Instrukcja uruchomienia i obsługi krok po kroku

### 1. Pierwsze uruchomienie na nowym komputerze
1. Skopiuj plik konfiguracyjny i uzupełnij hasła:
   ```bash
   cp .env.example .env
   ```
2. Uruchom inicjalizację środowiska (wygeneruje certyfikaty SSL, postawi kontenery Dockera, poczeka na instalację PrestaShop i wgra `deploy/config-export/shop_base_config.sql`, jeśli istnieje):
   ```bash
   ./deploy/init.sh
   ```
3. Po uruchomieniu wejdź na:
   * Sklep: `https://localhost:8443/`
   * Panel admina: `https://localhost:8443/admin_dywany/` (dane z `.env`: `ADMIN_MAIL`, `ADMIN_PASSWD`)
   * Mailpit (przechwycone maile): `http://localhost:8025/`

### 2. Import produktów ze zdjęciami (`import_api.py`)
> **Uwaga:** `shop_base_config.sql` przenosi ustawienia bazy danych, ale nie przenosi plików zdjęć z wolumenu `ps_data` (`/var/www/html/img/p/`). Na czystym środowisku zdjęcia produktów pobiera `import_api.py` (albo są odtwarzane z backupu przez `restore.sh`).

1. W panelu admina przejdź do **Zaawansowane → API (Webservice)**, włącz webservice (`TAK`), wygeneruj klucz z uprawnieniami dla zasobów (`categories`, `products`, `combinations`, `stock_availables`, `images`, `product_options`, `product_option_values`, `tax_rule_groups`, `languages`) i wpisz go do `.env` jako `PRESTASHOP_API_KEY=...`.
2. Uruchom importer:
   ```bash
   python3 deploy/import_api.py --clean-demo
   ```
   *(Lub uruchom `./deploy/init.sh --with-import`, jeśli masz już ustawiony `PRESTASHOP_API_KEY` w `.env` i bazę bez produktów).*

### 3. Eksport i import samej konfiguracji (bez haseł i danych osobowych)
* **Eksport:** `./deploy/export-config.sh` zapisuje `deploy/config-export/shop_base_config.sql` z pominięciem tabel `ps_customer*`, `ps_employee*`, `ps_address`, sesji, koszyków, zamówień oraz kluczy API (`ps_webservice_*`).
* **Import:** `./deploy/import-config.sh` wgrywa `shop_base_config.sql` i czyści cache PrestaShop, pozostawiając lokalnego administratora utworzonego z `.env` w wolumenie `db_data`.

### 4. Pełny backup i odtwarzanie (baza + zdjęcia + pliki)
* **Tworzenie kopii:**
  ```bash
  ./deploy/backup.sh
  ```
  Zapisuje `db.sql.gz` i `ps_files.tar.gz` w `deploy/backups/backup_YYYYMMDD_HHMMSS/`.
* **Odtwarzanie (domyślnie z najnowszego backupu):**
  ```bash
  ./deploy/restore.sh
  ```

### 5. Aktywacja motywu potomnego i banera modowego (`D1`)
Motyw potomny `classic-fashion` jest automatycznie wdrażany podczas uruchomienia `./deploy/init.sh`. Można go również wdrożyć lub zaktualizować ręcznie w dowolnym momencie komendą:
```bash
./deploy/activate-theme.sh
```
Skrypt wykonuje:
1. Kopiowanie plików motywu potomnego z `shop/themes/classic-fashion/` do kontenera `prestashop_app`.
2. Aktywację motywu potomnego w PrestaShop (baza `ps_shop.theme_name = 'classic-fashion'` oraz CLI).
3. Podmianę grafiki slajdu oraz tekstów w module `ps_imageslider` na baner modowy Mosquito.
4. Czyszczenie pamięci podręcznej (cache) PrestaShop.
