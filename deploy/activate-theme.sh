#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# deploy/activate-theme.sh
# Aktywuje motyw potomny 'classic-fashion' oraz podmienia baner ps_imageslider
# w dziaĹ‚ajÄ…cym kontenerze PrestaShop 8.2 (Wymaganie D1 - 5 pkt).
# ==============================================================================

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
THEME_NAME="classic-fashion"
THEME_SRC="${REPO_ROOT}/shop/themes/${THEME_NAME}"
BANNER_SRC="${THEME_SRC}/assets/img/banner-fashion.jpg"
APP_CONTAINER="${APP_CONTAINER:-prestashop_app}"
DB_CONTAINER="${DB_CONTAINER:-prestashop_db}"
ENV_FILE="${REPO_ROOT}/.env"

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi

DB_NAME="${DB_NAME:-prestashop}"
DB_ROOT_PASSWD="${DB_ROOT_PASSWD:-prestashop_root}"
HTTPS_PORT="${HTTPS_PORT:-8443}"

echo "=== [1/5] Weryfikacja kontenerĂłw PrestaShop ==="
if ! docker ps --format '{{.Names}}' | grep -qx "${APP_CONTAINER}"; then
  echo "BĹ‚Ä…d: kontener ${APP_CONTAINER} nie jest uruchomiony!" >&2
  exit 1
fi

if ! docker ps --format '{{.Names}}' | grep -qx "${DB_CONTAINER}"; then
  echo "BĹ‚Ä…d: kontener ${DB_CONTAINER} nie jest uruchomiony!" >&2
  exit 1
fi

if [[ ! -d "${THEME_SRC}" ]]; then
  echo "BĹ‚Ä…d: katalog motywu potomnego ${THEME_SRC} nie istnieje!" >&2
  exit 1
fi

echo "=== [2/5] Kopiowanie motywu potomnego do kontenera ==="
docker exec "${APP_CONTAINER}" mkdir -p "/var/www/html/themes/${THEME_NAME}"
docker cp "${THEME_SRC}/." "${APP_CONTAINER}:/var/www/html/themes/${THEME_NAME}/"
docker exec "${APP_CONTAINER}" chown -R www-data:www-data "/var/www/html/themes/${THEME_NAME}"

echo "=== [3/5] Aktywacja motywu w PrestaShop ==="
# Aktualizacja bazy danych (tabela ps_shop)
docker exec -e MYSQL_PWD="${DB_ROOT_PASSWD}" "${DB_CONTAINER}" \
  mariadb -u root "${DB_NAME}" -e "UPDATE ps_shop SET theme_name = '${THEME_NAME}' WHERE id_shop = 1;"

# PrĂłba aktywacji przez konsole Symfony PrestaShopa (jesli dostepna)
docker exec "${APP_CONTAINER}" php -d memory_limit=512M bin/console prestashop:theme:enable "${THEME_NAME}" 2>/dev/null || true

echo "=== [4/5] Podmiana domyĹ›lnego slajdu moduĹ‚u ps_imageslider ==="
if [[ -f "${BANNER_SRC}" ]]; then
  # 1. Kopiowanie grafiki banera jako sample-1.jpg
  docker exec "${APP_CONTAINER}" mkdir -p /var/www/html/modules/ps_imageslider/images
  docker cp "${BANNER_SRC}" "${APP_CONTAINER}:/var/www/html/modules/ps_imageslider/images/sample-1.jpg"
  docker exec "${APP_CONTAINER}" chown www-data:www-data /var/www/html/modules/ps_imageslider/images/sample-1.jpg

  # 2. Aktualizacja tekstow i tytulu slajdu w bazie danych
  docker exec -e MYSQL_PWD="${DB_ROOT_PASSWD}" "${DB_CONTAINER}" \
    mariadb -u root --default-character-set=utf8mb4 "${DB_NAME}" -e "
      UPDATE ps_homeslider_slides_lang
      SET title = 'Nowa Kolekcja Mosquito',
          description = '<h3>NOWA KOLEKCJA MOSQUITO</h3><p>Odkryj najnowsze trendy mody damskiej – sukienki, bluzy i komplety prosto od polskich projektantĂłw.</p>',
          legend = 'Nowa Kolekcja Mosquito',
          url = '/'
      WHERE id_homeslider_slides = 1;
    "
fi

echo "=== [5/5] Czyszczenie cache PrestaShop ==="
docker exec "${APP_CONTAINER}" rm -rf /var/www/html/var/cache/* 2>/dev/null || true
docker exec "${APP_CONTAINER}" php -d memory_limit=512M bin/console cache:clear 2>/dev/null || true

echo ""
echo "================================================================="
echo " SUKCES! Motyw potomny '${THEME_NAME}' zostaĹ‚ pomyĹ›lnie aktywowany."
echo " Baner modowy zostaĹ‚ wdroĹĽony w module ps_imageslider."
echo " Adres sklepu: https://localhost:${HTTPS_PORT}/"
echo "================================================================="
