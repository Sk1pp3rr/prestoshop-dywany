#!/usr/bin/env bash
set -euo pipefail

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

set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

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
docker exec -i -e MYSQL_PWD="${DB_ROOT_PASSWD}" "${DB_CONTAINER}" \
  mariadb -u root --default-character-set=utf8mb4 "${DB_NAME}" < "${IN_FILE}"

if docker ps --format '{{.Names}}' | grep -qx "${APP_CONTAINER}"; then
  echo "Czyszczenie cache PrestaShop w kontenerze ${APP_CONTAINER}..."
  docker exec "${APP_CONTAINER}" rm -rf /var/www/html/var/cache/*
fi

echo "Import zakończony pomyślnie."
