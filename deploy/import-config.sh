#!/usr/bin/env bash
set -euo pipefail

export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL="*"

# Import bazowej konfiguracji PrestaShop z deploy/config-export/shop_base_config.sql
# i wyczyszczenie cache PrestaShop.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${REPO_ROOT}/.env"
IN_FILE="${1:-${REPO_ROOT}/deploy/config-export/shop_base_config.sql}"
DB_CONTAINER="prestashop_db"
APP_CONTAINER="prestashop_app"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Błąd: brak pliku ${ENV_FILE}" >&2
  exit 1
fi

if [[ ! -f "${IN_FILE}" ]]; then
  echo "Błąd: brak pliku konfiguracyjnego ${IN_FILE}" >&2
  exit 1
fi

eval "$(tr -d '\r' < "${ENV_FILE}" | grep -E '^[A-Za-z_][A-Za-z0-9_]*=' | sed 's/^/export /')"

DB_NAME="${DB_NAME:-prestashop}"

if [[ -z "${DB_ROOT_PASSWD:-}" ]]; then
  echo "Błąd: zmienna DB_ROOT_PASSWD nie jest ustawiona w .env" >&2
  exit 1
fi

if ! docker ps --format '{{.Names}}' | grep -qx "${DB_CONTAINER}"; then
  echo "Błąd: kontener ${DB_CONTAINER} nie jest uruchomiony." >&2
  exit 1
fi

echo "Importowanie ${IN_FILE} do bazy '${DB_NAME}'..."
docker cp "${IN_FILE}" "${DB_CONTAINER}:/tmp/import_config.sql"
docker exec -e MYSQL_PWD="${DB_ROOT_PASSWD}" "${DB_CONTAINER}" sh -c \
  "mariadb -u root --default-character-set=utf8mb4 \"${DB_NAME}\" < /tmp/import_config.sql && rm -f /tmp/import_config.sql"

if docker ps --format '{{.Names}}' | grep -qx "${APP_CONTAINER}"; then
  echo "Czyszczenie cache PrestaShop w kontenerze ${APP_CONTAINER}..."
  docker exec "${APP_CONTAINER}" sh -c "rm -rf /var/www/html/var/cache/*"
fi

echo "Import zakończony pomyślnie."
