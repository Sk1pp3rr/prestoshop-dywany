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
DB_READY=false
for _ in $(seq 1 60); do
  if docker exec -e MYSQL_PWD="${DB_ROOT_PASSWD}" prestashop_db \
      mariadb-admin ping -h localhost -u root --silent >/dev/null 2>&1; then
    DB_READY=true
    break
  fi
  sleep 2
done

if [[ "${DB_READY}" != "true" ]]; then
  echo "Błąd: Baza danych (prestashop_db) nie uruchomiła się w wyznaczonym czasie (120s)." >&2
  exit 1
fi

echo "Oczekiwanie na zakończenie instalacji PrestaShop (prestashop_app)..."
PS_READY=false
for _ in $(seq 1 90); do
  if docker exec prestashop_app test -f /var/www/html/app/config/parameters.php 2>/dev/null && \
     docker exec -e MYSQL_PWD="${DB_ROOT_PASSWD}" prestashop_db \
       mariadb -u root "${DB_NAME}" -e "SELECT 1 FROM ps_configuration LIMIT 1;" >/dev/null 2>&1; then
    PS_READY=true
    break
  fi
  sleep 3
done

if [[ "${PS_READY}" != "true" ]]; then
  echo "Błąd: PrestaShop (prestashop_app) nie zakończył instalacji w wyznaczonym czasie (270s)." >&2
  exit 1
fi

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
# Automatyczna aktywacja Webservice API i lokalnego klucza z .env
if [[ -z "${PRESTASHOP_API_KEY:-}" || "${PRESTASHOP_API_KEY}" == ChangeMe* ]]; then
  PRESTASHOP_API_KEY="$(tr -dc 'A-Z0-9' </dev/urandom | head -c 32 || true)"
  if grep -q '^PRESTASHOP_API_KEY=' "${ENV_FILE}"; then
    sed -i "s/^PRESTASHOP_API_KEY=.*/PRESTASHOP_API_KEY=${PRESTASHOP_API_KEY}/" "${ENV_FILE}"
  else
    printf "\nPRESTASHOP_API_KEY=%s\n" "${PRESTASHOP_API_KEY}" >> "${ENV_FILE}"
  fi
  echo "Wygenerowano lokalny klucz PRESTASHOP_API_KEY w .env."
fi

echo "Aktywacja PrestaShop Webservice API dla lokalnego klucza..."
docker exec -i -e MYSQL_PWD="${DB_ROOT_PASSWD}" prestashop_db \
  mariadb -u root "${DB_NAME}" <<SQL
INSERT INTO ps_configuration (name, value, date_add, date_upd)
VALUES ('PS_WEBSERVICE', '1', NOW(), NOW())
ON DUPLICATE KEY UPDATE value = '1', date_upd = NOW();

INSERT INTO ps_webservice_account (\`key\`, description, class_name, is_module, module_name, active)
SELECT '${PRESTASHOP_API_KEY}', 'init_sh_api', 'WebserviceRequest', 0, NULL, 1
WHERE NOT EXISTS (SELECT 1 FROM ps_webservice_account WHERE \`key\` = '${PRESTASHOP_API_KEY}');

SET @ws_id := (SELECT id_webservice_account FROM ps_webservice_account WHERE \`key\` = '${PRESTASHOP_API_KEY}' LIMIT 1);

INSERT IGNORE INTO ps_webservice_account_shop (id_webservice_account, id_shop)
VALUES (@ws_id, 1);

# Minimalne uprawnienia (least privilege) wymagane wyłącznie przez deploy/import_api.py
DELETE FROM ps_webservice_permission WHERE id_webservice_account = @ws_id;

INSERT INTO ps_webservice_permission (resource, method, id_webservice_account) VALUES
  ('languages', 'GET', @ws_id),
  ('tax_rule_groups', 'GET', @ws_id),
  ('product_options', 'GET', @ws_id),
  ('product_options', 'POST', @ws_id),
  ('product_option_values', 'GET', @ws_id),
  ('product_option_values', 'POST', @ws_id),
  ('combinations', 'GET', @ws_id),
  ('combinations', 'POST', @ws_id),
  ('stock_availables', 'GET', @ws_id),
  ('stock_availables', 'PUT', @ws_id),
  ('images', 'POST', @ws_id),
  ('categories', 'GET', @ws_id),
  ('categories', 'POST', @ws_id),
  ('categories', 'DELETE', @ws_id),
  ('products', 'GET', @ws_id),
  ('products', 'POST', @ws_id),
  ('products', 'DELETE', @ws_id);
SQL

if [[ -f "${REPO_ROOT}/deploy/theme/custom.js" ]]; then
  echo "Wgrywanie banera cookies (deploy/theme/custom.js)..."
  docker cp "${REPO_ROOT}/deploy/theme/custom.js" prestashop_app:/var/www/html/themes/classic/assets/js/custom.js
  docker exec prestashop_app chown www-data:www-data /var/www/html/themes/classic/assets/js/custom.js
fi

if [[ "${WITH_IMPORT}" == "true" ]]; then
  if [[ -f "${IMPORT_SCRIPT}" && -f "${PRODUCTS_JSON}" ]]; then
    echo "Uruchamianie importu produktów przez Webservice API..."
    PRESTASHOP_API_KEY="${PRESTASHOP_API_KEY}" python3 "${IMPORT_SCRIPT}" --input "${PRODUCTS_JSON}" --clean-demo
  else
    echo "Pominięto import API (brak ${IMPORT_SCRIPT} lub ${PRODUCTS_JSON})."
  fi
fi

echo ""
echo "Sklep gotowy:"
echo "  Front:   https://localhost:${HTTPS_PORT}/"
echo "  Admin:   https://localhost:${HTTPS_PORT}/${PS_FOLDER_ADMIN}/"
echo "  Mailpit: http://localhost:${MAILPIT_UI_PORT}/"
