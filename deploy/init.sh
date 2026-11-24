#!/usr/bin/env bash
set -euo pipefail

export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL="*"

# Pełna inicjalizacja sklepu PrestaShop 8.2 jedną komendą:
# 1. Tworzy .env z .env.example (jeśli brak) i generuje certyfikaty SSL (jeśli brak).
# 2. Uruchamia kontenery z deploy/compose.yaml i czeka na gotowość bazy oraz PrestaShop.
# 3. Wgrywa bazową konfigurację (deploy/config-export/shop_base_config.sql), jeśli istnieje.
# 4. Opcjonalnie uruchamia import produktów przez Webservice API (--with-import).

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${REPO_ROOT}/.env"
ENV_EXAMPLE="${REPO_ROOT}/.env.example"
COMPOSE_FILE="${REPO_ROOT}/deploy/compose.yaml"
CERT_SCRIPT="${REPO_ROOT}/deploy/nginx/generate-certs.sh"
SSL_CERT="${REPO_ROOT}/deploy/nginx/ssl/server.crt"
CONFIG_SQL="${REPO_ROOT}/deploy/config-export/shop_base_config.sql"
IMPORT_SCRIPT="${REPO_ROOT}/deploy/import_api.py"
PRODUCTS_JSON="${REPO_ROOT}/scraper-results/products.json"
THEME_ACTIVATE_SCRIPT="${REPO_ROOT}/deploy/activate-theme.sh"

WITH_IMPORT=false
if [[ "${1:-}" == "--with-import" ]]; then
  WITH_IMPORT=true
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  if [[ -f "${ENV_EXAMPLE}" ]]; then
    echo "Brak pliku .env — kopiuję z .env.example..."
    cp "${ENV_EXAMPLE}" "${ENV_FILE}"
  else
    echo "Błąd: brak pliku .env oraz .env.example" >&2
    exit 1
  fi
fi

eval "$(tr -d '\r' < "${ENV_FILE}" | grep -E '^[A-Za-z_][A-Za-z0-9_]*=' | sed 's/^/export /')"

DB_NAME="${DB_NAME:-prestashop}"
HTTPS_PORT="${HTTPS_PORT:-8443}"
PS_FOLDER_ADMIN="${PS_FOLDER_ADMIN:-admin_fashion}"
MAILPIT_UI_PORT="${MAILPIT_UI_PORT:-8025}"

if [[ ! -f "${SSL_CERT}" ]]; then
  echo "Generowanie samopodpisanych certyfikatów SSL..."
  bash "${CERT_SCRIPT}"
fi

echo "Uruchamianie kontenerów Dockera..."
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up -d

echo "Oczekiwanie na gotowość bazy danych (prestashop_db)..."
for _ in $(seq 1 60); do
  if docker exec -e MYSQL_PWD="${DB_ROOT_PASSWD}" prestashop_db \
      mariadb-admin ping -h localhost -u root --silent >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

echo "Oczekiwanie na zakończenie instalacji PrestaShop (prestashop_app)..."
for _ in $(seq 1 90); do
  if docker exec prestashop_app test -f /var/www/html/app/config/parameters.php 2>/dev/null && \
     docker exec -e MYSQL_PWD="${DB_ROOT_PASSWD}" prestashop_db \
       mariadb -u root "${DB_NAME}" -e "SELECT 1 FROM ps_configuration LIMIT 1;" >/dev/null 2>&1; then
    break
  fi
  sleep 3
done

if [[ -f "${CONFIG_SQL}" ]]; then
  echo "Wgrywanie bazowej konfiguracji z ${CONFIG_SQL}..."
  docker cp "${CONFIG_SQL}" prestashop_db:/tmp/shop_base_config.sql
  docker exec -e MYSQL_PWD="${DB_ROOT_PASSWD}" prestashop_db sh -c \
    "mariadb -u root --default-character-set=utf8mb4 \"${DB_NAME}\" < /tmp/shop_base_config.sql && rm -f /tmp/shop_base_config.sql"
  docker exec prestashop_app sh -c "rm -rf /var/www/html/var/cache/*"
else
  echo "Pominięto import SQL (brak pliku ${CONFIG_SQL})."
fi

if [[ -f "${THEME_ACTIVATE_SCRIPT}" ]]; then
  echo "Wdrażanie motywu potomnego (classic-fashion) i banera..."
  bash "${THEME_ACTIVATE_SCRIPT}"
fi

if [[ "${WITH_IMPORT}" == "true" ]]; then
  if [[ -z "${PRESTASHOP_API_KEY:-}" || "${PRESTASHOP_API_KEY}" == ChangeMe* ]]; then
    echo "Ostrzeżenie: ustaw poprawny PRESTASHOP_API_KEY w .env przed uruchomieniem importu API." >&2
  elif [[ -f "${IMPORT_SCRIPT}" && -f "${PRODUCTS_JSON}" ]]; then
    echo "Uruchamianie importu produktów przez Webservice API..."
    python3 "${IMPORT_SCRIPT}" --input "${PRODUCTS_JSON}" --clean-demo
  else
    echo "Pominięto import API (brak ${IMPORT_SCRIPT} lub ${PRODUCTS_JSON})."
  fi
fi

echo ""
echo "Sklep gotowy:"
echo "  Front:   https://localhost:${HTTPS_PORT}/"
echo "  Admin:   https://localhost:${HTTPS_PORT}/${PS_FOLDER_ADMIN}/"
echo "  Mailpit: http://localhost:${MAILPIT_UI_PORT}/"
