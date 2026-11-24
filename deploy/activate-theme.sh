#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Wdrożenie i aktywacja motywu potomnego classic-fashion oraz seed zdjęć Mosquito
# ==============================================================================

export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL="*"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
THEME_NAME="classic-fashion"
THEME_SRC="${REPO_ROOT}/shop/themes/${THEME_NAME}"
SLIDER_DIR="${THEME_SRC}/assets/img"
SEED_PHP="${REPO_ROOT}/deploy/seed-images.php"
SAMPLE_IMAGES_DIR="${REPO_ROOT}/scraper-results/images"
PRODUCTS_JSON="${REPO_ROOT}/scraper-results/products.json"
APP_CONTAINER="${APP_CONTAINER:-prestashop_app}"
DB_CONTAINER="${DB_CONTAINER:-prestashop_db}"
ENV_FILE="${REPO_ROOT}/.env"

if [[ -f "${ENV_FILE}" ]]; then
  # Bezpieczne wczytanie .env (takze przy koncach linii CRLF na Windows)
  eval "$(tr -d '\r' < "${ENV_FILE}" | grep -E '^[A-Za-z_][A-Za-z0-9_]*=' | sed 's/^/export /')"
fi

DB_NAME="${DB_NAME:-prestashop}"
DB_ROOT_PASSWD="${DB_ROOT_PASSWD:-prestashop_root}"

echo "=== [1/6] Weryfikacja kontenerow PrestaShop ==="
if ! docker ps --format '{{.Names}}' | grep -qx "${APP_CONTAINER}"; then
  echo "Blad: kontener ${APP_CONTAINER} nie jest uruchomiony!" >&2
  exit 1
fi

if ! docker ps --format '{{.Names}}' | grep -qx "${DB_CONTAINER}"; then
  echo "Blad: kontener ${DB_CONTAINER} nie jest uruchomiony!" >&2
  exit 1
fi

if [[ ! -d "${THEME_SRC}" ]]; then
  echo "Blad: katalog motywu potomnego ${THEME_SRC} nie istnieje!" >&2
  exit 1
fi

echo "=== [2/6] Kopiowanie motywu potomnego i zasobow Mosquito ==="
if ! docker exec "${APP_CONTAINER}" test -f "/var/www/html/themes/${THEME_NAME}/config/theme.yml"; then
  docker exec "${APP_CONTAINER}" mkdir -p "/var/www/html/themes/${THEME_NAME}"
  docker cp "${THEME_SRC}/." "${APP_CONTAINER}:/var/www/html/themes/${THEME_NAME}/"
fi
docker exec "${APP_CONTAINER}" chown -R www-data:www-data "/var/www/html/themes/${THEME_NAME}" 2>/dev/null || true

if [[ -f "${SLIDER_DIR}/logo.png" ]]; then
  docker cp "${SLIDER_DIR}/logo.png" "${APP_CONTAINER}:/var/www/html/img/logo.png"
  docker exec "${APP_CONTAINER}" chown www-data:www-data /var/www/html/img/logo.png
fi

echo "=== [3/6] Aktywacja motywu w bazie danych PrestaShop ==="
docker exec -e MYSQL_PWD="${DB_ROOT_PASSWD}" "${DB_CONTAINER}" \
  mariadb -u root --default-character-set=utf8mb4 "${DB_NAME}" -e "
    UPDATE ps_shop SET theme_name = '${THEME_NAME}' WHERE id_shop = 1;
    UPDATE ps_configuration SET value = 'jpg' WHERE name = 'PS_IMAGE_QUALITY';
  "
docker exec "${APP_CONTAINER}" php -d memory_limit=512M bin/console prestashop:theme:enable "${THEME_NAME}" 2>/dev/null || true

echo "=== [4/6] Kopiowanie grafik slidera (ps_imageslider) ==="
docker exec "${APP_CONTAINER}" mkdir -p /var/www/html/modules/ps_imageslider/images
for slide_img in sample-1.jpg sample-2.jpg; do
  if [[ -f "${SLIDER_DIR}/${slide_img}" ]]; then
    docker cp "${SLIDER_DIR}/${slide_img}" "${APP_CONTAINER}:/var/www/html/modules/ps_imageslider/images/${slide_img}"
    docker exec "${APP_CONTAINER}" chown www-data:www-data "/var/www/html/modules/ps_imageslider/images/${slide_img}"
  fi
done

echo "=== [5/6] Generowanie zdjec produktowych 3:4 (seed-images.php) ==="
if [[ -f "${SEED_PHP}" ]]; then
  docker exec "${APP_CONTAINER}" rm -rf /tmp/sample-images /tmp/products.json /tmp/seed-images.php
  if [[ -d "${SAMPLE_IMAGES_DIR}" ]]; then
    docker exec "${APP_CONTAINER}" mkdir -p /tmp/sample-images
    docker cp "${SAMPLE_IMAGES_DIR}/." "${APP_CONTAINER}:/tmp/sample-images/"
  fi
  if [[ -f "${PRODUCTS_JSON}" ]]; then
    docker cp "${PRODUCTS_JSON}" "${APP_CONTAINER}:/tmp/products.json"
  fi
  docker cp "${SEED_PHP}" "${APP_CONTAINER}:/tmp/seed-images.php"
  docker exec "${APP_CONTAINER}" php -d memory_limit=512M /tmp/seed-images.php
  docker exec "${APP_CONTAINER}" rm -rf /tmp/sample-images /tmp/products.json /tmp/seed-images.php
  docker exec "${APP_CONTAINER}" chown -R www-data:www-data /var/www/html/img/p
fi

echo "=== [6/6] Czyszczenie cache PrestaShop ==="
docker exec "${APP_CONTAINER}" sh -c "rm -rf /var/www/html/var/cache/*" 2>/dev/null || true
docker exec "${APP_CONTAINER}" php -d memory_limit=512M bin/console cache:clear 2>/dev/null || true

echo "Motyw '${THEME_NAME}' i zasoby Mosquito wdrozone pomyslnie!"
