#!/usr/bin/env bash
set -euo pipefail

# Odtwarza pełny backup sklepu PrestaShop (baza MariaDB + pliki ps_data)
# utworzony przez deploy/backup.sh. Domyślnie używa najnowszego backupu.

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

if [[ -n "${1:-}" ]]; then
  BACKUP_DIR="$1"
else
  BACKUP_DIR="$(ls -1dt "${BACKUPS_ROOT}"/backup_* 2>/dev/null | head -n 1 || true)"
fi

if [[ -z "${BACKUP_DIR}" || ! -d "${BACKUP_DIR}" ]]; then
  echo "Błąd: nie znaleziono katalogu z backupem w ${BACKUPS_ROOT}." >&2
  exit 1
fi

if [[ ! -f "${BACKUP_DIR}/db.sql.gz" || ! -f "${BACKUP_DIR}/ps_files.tar.gz" ]]; then
  echo "Błąd: w ${BACKUP_DIR} brakuje plików db.sql.gz lub ps_files.tar.gz." >&2
  exit 1
fi

for c in "${DB_CONTAINER}" "${APP_CONTAINER}"; do
  if ! docker ps --format '{{.Names}}' | grep -qx "${c}"; then
    echo "Błąd: kontener ${c} nie jest uruchomiony." >&2
    exit 1
  fi
done

echo "Odtwarzanie backupu z: ${BACKUP_DIR}"

echo "1/3 Odtwarzanie bazy danych '${DB_NAME}'..."
gunzip -c "${BACKUP_DIR}/db.sql.gz" | \
  docker exec -i -e MYSQL_PWD="${DB_ROOT_PASSWD}" "${DB_CONTAINER}" \
    mariadb -u root --default-character-set=utf8mb4 "${DB_NAME}"

echo "2/3 Odtwarzanie plików PrestaShop..."
docker exec -i "${APP_CONTAINER}" \
  tar -xzf - -C /var/www/html < "${BACKUP_DIR}/ps_files.tar.gz"

echo "3/3 Czyszczenie cache PrestaShop..."
docker exec "${APP_CONTAINER}" rm -rf /var/www/html/var/cache/*

echo "Odtwarzanie zakończone pomyślnie."
