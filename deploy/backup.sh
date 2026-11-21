#!/usr/bin/env bash
set -euo pipefail

# Pełny backup sklepu PrestaShop (baza MariaDB + pliki z wolumenu ps_data)
# Zapisuje archiwum w deploy/backups/backup_YYYYMMDD_HHMMSS/ (ignorowane przez .gitignore).

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${REPO_ROOT}/.env"
BACKUPS_ROOT="${REPO_ROOT}/deploy/backups"
DB_CONTAINER="prestashop_db"
APP_CONTAINER="prestashop_app"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Błąd: brak pliku ${ENV_FILE}" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

DB_NAME="${DB_NAME:-prestashop}"

for c in "${DB_CONTAINER}" "${APP_CONTAINER}"; do
  if ! docker ps --format '{{.Names}}' | grep -qx "${c}"; then
    echo "Błąd: kontener ${c} nie jest uruchomiony." >&2
    exit 1
  fi
done

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="${1:-${BACKUPS_ROOT}/backup_${TIMESTAMP}}"
mkdir -p "${BACKUP_DIR}"

echo "Tworzenie backupu bazy danych '${DB_NAME}'..."
docker exec -e MYSQL_PWD="${DB_ROOT_PASSWD}" "${DB_CONTAINER}" \
  mariadb-dump -u root --single-transaction --routines --triggers \
  --default-character-set=utf8mb4 --add-drop-table "${DB_NAME}" \
  | gzip -9 > "${BACKUP_DIR}/db.sql.gz"

echo "Tworzenie backupu plików PrestaShop (bez cache)..."
docker exec "${APP_CONTAINER}" \
  tar -czf - --exclude="var/cache/*" -C /var/www/html . \
  > "${BACKUP_DIR}/ps_files.tar.gz"

echo "Backup zakończony pomyślnie w: ${BACKUP_DIR}"
ls -lh "${BACKUP_DIR}"
