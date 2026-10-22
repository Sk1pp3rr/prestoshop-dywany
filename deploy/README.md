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
├── import_api.py                   # Idempotentny skrypt importu produktów i kategorii przez Webservice API (D2)
├── backup.sh                       # Skrypt tworzący kopię zapasową bazy, zdjęć i konfiguracji (D4)
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
