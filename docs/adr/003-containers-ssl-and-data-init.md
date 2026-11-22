# ADR-003: Kontenery Docker Compose, HTTPS i inicjalizacja danych

* **Status:** Zaakceptowano
* **Data:** 2026-11-22

## Kontekst

Etap 1 wymaga sklepu PrestaShop 8.2 uruchamianego lokalnie przez Docker Compose v2, z ruchem sklepu po HTTPS, samopodpisanym certyfikatem i przekierowaniem HTTP na HTTPS. Poczta transakcyjna ma trafiać do Mailpit, a nie do prawdziwego serwera SMTP. Osobno potrzebna jest inicjalizacja bazy, import konfiguracji, opcjonalny import produktów oraz kopia zapasowa i jej odtworzenie. Etap 2 ma przenieść ten sam układ na Docker Swarm, więc obrazy muszą być określone jako `linux/amd64`.

Opis implementacji opiera się na stanie gałęzi `main` z commita `cea885a`. Ten zapis opisuje pliki z repozytorium: [`deploy/compose.yaml`](../../deploy/compose.yaml), [`deploy/init.sh`](../../deploy/init.sh), [`deploy/backup.sh`](../../deploy/backup.sh), [`deploy/restore.sh`](../../deploy/restore.sh), [`deploy/import-config.sh`](../../deploy/import-config.sh), [`deploy/export-config.sh`](../../deploy/export-config.sh), [`deploy/nginx/nginx.conf`](../../deploy/nginx/nginx.conf), [`deploy/nginx/generate-certs.sh`](../../deploy/nginx/generate-certs.sh) i [`.env.example`](../../.env.example). Kontenerów, `init.sh` i `restore.sh` przy sporządzaniu dokumentu nie uruchamiano. Działanie poniżej wynika z treści tych plików, a nie z wykonanego testu środowiska.

## Rozważane opcje

1. **Jeden kontener PrestaShop wystawiający HTTP oraz baza na hoście.** Mniej plików, ale brak wydzielonego reverse proxy, brak wymuszenia HTTPS i brak Mailpit w tej samej definicji.
2. **Docker Compose v2: PrestaShop, MariaDB, Nginx i Mailpit.** Cztery usługi w [`deploy/compose.yaml`](../../deploy/compose.yaml), bez klucza `version`. Nginx kończy TLS, aplikacja zostaje w sieci Compose, a poczta idzie do Mailpit.
3. **Od razu Docker Swarm albo Kubernetes.** Spełniałoby kierunek etapu 2, ale na etapie 1 nie ma w repozytorium pliku stacka ani manifestów klastra. Lokalne uruchomienie byłoby trudniejsze niż Compose.

## Decyzja

Wybrano **opcję 2**. Definicja środowiska jest w [`deploy/compose.yaml`](../../deploy/compose.yaml). Uruchomienie przewidziane przez skrypt to `docker compose --env-file .env -f deploy/compose.yaml up -d`.

### Usługi

| Usługa Compose | Obraz | `container_name` | Porty na hoście |
| :--- | :--- | :--- | :--- |
| `db` | `mariadb:10.11` | `prestashop_db` | brak mapowania |
| `prestashop` | `prestashop/prestashop:8.2-apache` | `prestashop_app` | brak mapowania |
| `mailpit` | `axllent/mailpit` | `prestashop_mailpit` | `${MAILPIT_UI_PORT:-8025}:8025` |
| `nginx` | `nginx:alpine` | `prestashop_nginx` | `${HTTP_PORT:-8080}:80` i `${HTTPS_PORT:-8443}:443` |

W [`.env.example`](../../.env.example) te porty mają wartości `8080`, `8443` i `8025`. Baza nasłuchuje tylko w sieci Compose pod nazwą `db`. PrestaShop dostaje `DB_SERVER: db`. Port `DB_PORT=3306` z `.env.example` nie jest użyty w `compose.yaml`.

`prestashop` czeka na `db` przez `depends_on` z warunkiem `service_healthy`. Healthcheck woła `mariadb-admin ping` jako `root` z hasłem `MYSQL_ROOT_PASSWORD`. Wyniku tego sprawdzenia nie potwierdzano uruchomieniem.

Wolumeny nazwane to `db_data` (`/var/lib/mysql`) i `ps_data` (`/var/www/html`). MariaDB startuje z `--character-set-server=utf8mb4` i `--collation-server=utf8mb4_unicode_ci`. Obraz PrestaShop ma `PS_INSTALL_AUTO: 1`, `PS_ENABLE_SSL: 1`, język `${PS_LANGUAGE:-pl}` i kraj `${PS_COUNTRY:-PL}`.

Poczta: `PS_MAIL_METHOD: 2`, serwer `mailpit`, port `1025`, szyfrowanie `off`, pusty użytkownik i hasło. Na hoście publikowany jest tylko interfejs Mailpit. Zmienna `MAILPIT_SMTP_PORT` z `.env.example` nie steruje Compose. SMTP zostaje w sieci wewnętrznej.

Każda usługa ma `platform: linux/amd64` i `restart: unless-stopped`. Tagi obrazów nie są skrótami digest. `nginx:alpine` i `axllent/mailpit` nie mają numeru wersji. To jest ograniczenie powtarzalności, nie wynik testu pobrania obrazów.

### HTTPS

[`deploy/nginx/nginx.conf`](../../deploy/nginx/nginx.conf) ma dwa bloki `server` z `server_name localhost`. Port 80 zwraca `301` na `https://$host:8443$request_uri`. Port 443 używa TLS 1.2 i 1.3, certyfikatu `/etc/nginx/ssl/server.crt` oraz klucza `/etc/nginx/ssl/server.key`. Katalog `deploy/nginx/ssl` jest montowany tylko do odczytu. Żądania `/` idą na `http://prestashop:80` z nagłówkami `X-Forwarded-Proto https`, `X-Forwarded-Port 8443` i `HTTPS on`. Limit ciała żądania to `64M`. Timeouty proxy to `300s`.

[`deploy/nginx/generate-certs.sh`](../../deploy/nginx/generate-certs.sh) tworzy certyfikat self-signed `server.crt` i klucz `server.key` (RSA 2048, 365 dni, `CN=localhost`), jeśli tych plików nie ma. `.gitignore` wyklucza `*.crt` i `*.key`.

Port `8443` w przekierowaniu i w nagłówku jest wpisany w konfiguracji Nginx, a nie brany z `HTTPS_PORT`. Przy domyślnych wartościach z `.env.example` zapis się zgadza. Zmiana samego `HTTPS_PORT` nie zmienia przekierowania.

### Inicjalizacja

[`deploy/init.sh`](../../deploy/init.sh) kopiuje `.env.example` do `.env`, gdy brakuje `.env`, woła generator certyfikatów, uruchamia Compose i następnie próbuje wgrać [`deploy/config-export/shop_base_config.sql`](../../deploy/config-export/shop_base_config.sql). Argument `--with-import` ustawia dodatkowo wywołanie `python3 deploy/import_api.py --input scraper-results/products.json --clean-demo`, ale tylko gdy klucz `PRESTASHOP_API_KEY` nie jest pusty i nie zaczyna się od `ChangeMe`, a oba pliki istnieją. W analizowanym `main` nie ma pliku `deploy/import_api.py`, więc `init.sh` wypisze, że import API został pominięty. Importer jest w otwartym PR #39 (`feature/import-api`); ta zmiana nie jest scalona z `main`. Adres archiwum zdjęć `IMAGES_RELEASE_ARCHIVE_URL` jest w `.env.example`, lecz `init.sh` go nie czyta.

Pętle oczekiwania mają 60 iteracji po 2 sekundy dla `mariadb-admin ping` w `prestashop_db` oraz 90 iteracji po 3 sekundy na plik `parameters.php` i zapytanie `SELECT 1 FROM ps_configuration`. Po wyjściu z pętli skrypt w analizowanym `main` nie sprawdza, czy warunek został spełniony, i przechodzi dalej. To jest luka w tym commicie, nie zaobserwowana awaria uruchomienia. Poprawka jest w otwartym PR #40 (`fix/init-script-timeout-check`) i nie jest scalona z `main`.

Gdy plik SQL istnieje, `init.sh` i [`deploy/import-config.sh`](../../deploy/import-config.sh) podają go klientowi `mariadb` użytkownika `root`. Obecny dump zawiera `DROP TABLE IF EXISTS` dla tabel konfiguracji i katalogu, w tym `ps_product`. Ponowny import nadpisuje te tabele. Skrypt eksportu pomija przy nowym zrzucie tabele klientów, pracowników i sesji oraz dane zamówień, koszyków i kont API, ale i tak zapisuje strukturę pozostałych tabel z `--add-drop-table`. Importu na działającym sklepie przy tym ADR nie wykonywano.

Domyślny katalog panelu nie jest jednolity. Compose przy braku zmiennej ustawia `PS_FOLDER_ADMIN` na `admin_dev`. `.env.example` i komunikat końcowy `init.sh` używają `admin_dywany`. Po skopiowaniu `.env.example` obie strony dostają `admin_dywany`.

`init.sh` sprawdza istnienie `deploy/nginx/ssl/localhost.crt`. Generator i Nginx używają `server.crt` oraz `server.key`. Warunek z `init.sh` nie odpowiada plikom, które faktycznie powstają i są montowane.

### Kopia zapasowa

[`deploy/backup.sh`](../../deploy/backup.sh) wymaga działających kontenerów `prestashop_db` i `prestashop_app`. Zapisuje katalog `deploy/backups/backup_YYYYMMDD_HHMMSS/`, wykluczony w `.gitignore`. W środku są `db.sql.gz` (`mariadb-dump` z `--single-transaction`, `--routines`, `--triggers`, `--add-drop-table`, kompresja `gzip -9`) oraz `ps_files.tar.gz` z `/var/www/html` bez `var/cache/*`.

[`deploy/restore.sh`](../../deploy/restore.sh) bierze katalog podany argumentem albo najnowszy `backup_*`. Wymaga obu archiwów i działających kontenerów. Rozpakowuje SQL do bazy, nakłada archiwum plików na `/var/www/html` i kasuje `var/cache`. Rozpakowanie `tar` nie usuwa plików, których w archiwum już nie ma. Zrzut bazy z `--add-drop-table` przy odtworzeniu kasuje i tworzy tabele od nowa. Czas „do 10 minut” jest wymaganiem opisanym w [`deploy/README.md`](../../deploy/README.md). Ten ADR go nie mierzył.

## Konsekwencje

* **Pozytywne:** Jeden plik Compose opisuje bazę, aplikację, pocztę testową i wejście HTTPS. Sklep nie publikuje własnego portu HTTP na hoście. Domyślne porty z `.env.example` to `http://localhost:8080`, `https://localhost:8443` i interfejs Mailpit `http://localhost:8025`.
* **Pozytywne:** `platform: linux/amd64` przy wszystkich czterech usługach ustala architekturę pod etap 2. Swarm ma dostać te same obrazy, a nie osobny wariant ARM.
* **Pozytywne:** Certyfikat jest lokalny i nie wchodzi do Gita. Mailpit przyjmuje pocztę wewnątrz sieci Compose, bez konta SMTP.
* **Pozytywne:** Backup obejmuje bazę i pliki sklepu, w tym zdjęcia z wolumenu `ps_data`. Sam SQL konfiguracyjny zdjęć nie przenosi.
* **Negatywne / Koszt:** `container_name` i lokalne wolumeny nazwane są modelem Compose. Stack Swarm nie używa `container_name` w ten sam sposób i wymaga wolumenu dostępnego dla węzłów, które dostaną usługi `db` i `prestashop`. Tego układu w repozytorium jeszcze nie ma.
* **Negatywne / Koszt:** Ponowny `init.sh` albo `import-config.sh` wgrywa dump z `DROP TABLE`. To nie jest dopisanie konfiguracji do istniejącego katalogu produktów.
* **Negatywne / Koszt:** W analizowanym `main` pętle w `init.sh` nie kończą skryptu błędem, gdy baza albo instalator nie zdążą. Otwarty PR #40 (`fix/init-script-timeout-check`) zawiera poprawkę i nie jest scalony. Niezgodność `localhost.crt` z `server.crt` sprawia, że warunek „certyfikat już jest” nie pilnuje pliku używanego przez Nginx.
* **Negatywne / Koszt:** Przekierowanie HTTPS ma na stałe port `8443`. W analizowanym `main` importer produktów opisany w `deploy/README.md` nie jest obecny jako `deploy/import_api.py`, więc `--with-import` nie ma czego uruchomić. Otwarty PR #39 (`feature/import-api`) zawiera importer i nie jest scalony.
* **Negatywne / Koszt:** Tagi `8.2-apache`, `nginx:alpine` i `axllent/mailpit` mogą się zmienić bez zmiany pliku Compose. README główny podaje także PHP 8.1 i MySQL 8.0. Compose ustala MariaDB `10.11` i obraz PrestaShop `8.2-apache`. Wersji PHP w obrazie tu nie sprawdzano.
