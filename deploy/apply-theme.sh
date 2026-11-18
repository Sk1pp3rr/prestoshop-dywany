#!/usr/bin/env bash
set -euo pipefail

# Kopiuje deploy/theme/custom.css do działającego kontenera prestashop_app
# i czyści cache PrestaShop, aby stylizacja była od razu widoczna.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CSS_SRC="${REPO_ROOT}/deploy/theme/custom.css"
APP_CONTAINER="prestashop_app"
CSS_DEST="/var/www/html/themes/classic/assets/css/custom.css"

if [[ ! -f "${CSS_SRC}" ]]; then
  echo "Błąd: brak pliku ${CSS_SRC}" >&2
  exit 1
fi

if ! docker ps --format '{{.Names}}' | grep -qx "${APP_CONTAINER}"; then
  echo "Błąd: kontener ${APP_CONTAINER} nie jest uruchomiony." >&2
  exit 1
fi

docker cp "${CSS_SRC}" "${APP_CONTAINER}:${CSS_DEST}"
docker exec "${APP_CONTAINER}" chown www-data:www-data "${CSS_DEST}"
docker exec "${APP_CONTAINER}" rm -rf /var/www/html/var/cache/*

echo "Zastosowano stylizację ${CSS_DEST} i wyczyszczono cache PrestaShop."
