#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Wdrożenie i aktywacja motywu potomnego classic-fashion oraz seed zdjęć Mosquito
# ==============================================================================

export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL="*"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if command -v cygpath >/dev/null 2>&1; then
  REPO_ROOT="$(cygpath -m "${REPO_ROOT}")"
fi
THEME_NAME="classic-fashion"
THEME_SRC="${REPO_ROOT}/shop/themes/${THEME_NAME}"
OMNIBUS_SRC="${REPO_ROOT}/shop/modules/ps_omnibusprice"
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

echo "=== [1/7] Weryfikacja kontenerow PrestaShop ==="
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

echo "=== [2/7] Kopiowanie motywu potomnego i zasobow Mosquito ==="
if ! docker exec "${APP_CONTAINER}" test -f "/var/www/html/themes/${THEME_NAME}/config/theme.yml"; then
  docker exec "${APP_CONTAINER}" mkdir -p "/var/www/html/themes/${THEME_NAME}"
  docker cp "${THEME_SRC}/." "${APP_CONTAINER}:/var/www/html/themes/${THEME_NAME}/"
fi
docker exec "${APP_CONTAINER}" chown -R www-data:www-data "/var/www/html/themes/${THEME_NAME}" 2>/dev/null || true

if [[ -f "${SLIDER_DIR}/logo.png" ]]; then
  docker cp "${SLIDER_DIR}/logo.png" "${APP_CONTAINER}:/var/www/html/img/logo.png"
  docker exec "${APP_CONTAINER}" chown www-data:www-data /var/www/html/img/logo.png
fi

echo "=== [3/7] Aktywacja motywu i klucza Webservice API w bazie danych PrestaShop ==="
if [[ ! "${PRESTASHOP_API_KEY:-}" =~ ^[A-Za-z0-9]{32}$ ]]; then
  PRESTASHOP_API_KEY="$(LC_ALL=C tr -dc 'A-Z0-9' </dev/urandom | head -c 32 || true)"
  if [[ -f "${ENV_FILE}" ]]; then
    if grep -q '^PRESTASHOP_API_KEY=' "${ENV_FILE}"; then
      TMP_ENV="$(mktemp "${ENV_FILE}.XXXXXX")"
      awk -v key="${PRESTASHOP_API_KEY}" '
        /^PRESTASHOP_API_KEY=/ { print "PRESTASHOP_API_KEY=" key; next }
        { print }
      ' "${ENV_FILE}" > "${TMP_ENV}"
      mv "${TMP_ENV}" "${ENV_FILE}"
    else
      printf "\nPRESTASHOP_API_KEY=%s\n" "${PRESTASHOP_API_KEY}" >> "${ENV_FILE}"
    fi
    echo "Wygenerowano poprawny 32-znakowy klucz PRESTASHOP_API_KEY w .env."
  fi
fi

docker exec -i -e MYSQL_PWD="${DB_ROOT_PASSWD}" "${DB_CONTAINER}" \
  mariadb --default-character-set=utf8mb4 -u root "${DB_NAME}" <<SQL
UPDATE ps_shop SET theme_name = '${THEME_NAME}' WHERE id_shop = 1;
UPDATE ps_configuration SET value = 'jpg' WHERE name = 'PS_IMAGE_QUALITY';

INSERT INTO ps_configuration (name, value, date_add, date_upd)
VALUES ('PS_WEBSERVICE', '1', NOW(), NOW())
ON DUPLICATE KEY UPDATE value = '1', date_upd = NOW();

INSERT INTO ps_webservice_account (\`key\`, description, class_name, is_module, module_name, active)
SELECT '${PRESTASHOP_API_KEY}', 'init_sh_api', 'WebserviceRequest', 0, NULL, 1
WHERE NOT EXISTS (SELECT 1 FROM ps_webservice_account WHERE \`key\` = '${PRESTASHOP_API_KEY}');

SET @ws_id := (SELECT id_webservice_account FROM ps_webservice_account WHERE \`key\` = '${PRESTASHOP_API_KEY}' LIMIT 1);

INSERT IGNORE INTO ps_webservice_account_shop (id_webservice_account, id_shop)
VALUES (@ws_id, 1);

INSERT IGNORE INTO ps_webservice_permission (resource, method, id_webservice_account) VALUES
  ('languages', 'GET', @ws_id),
  ('tax_rule_groups', 'GET', @ws_id),
  ('configurations', 'GET', @ws_id),
  ('configurations', 'POST', @ws_id),
  ('configurations', 'PUT', @ws_id),
  ('product_options', 'GET', @ws_id),
  ('product_options', 'POST', @ws_id),
  ('product_option_values', 'GET', @ws_id),
  ('product_option_values', 'POST', @ws_id),
  ('product_features', 'GET', @ws_id),
  ('product_features', 'POST', @ws_id),
  ('product_features', 'DELETE', @ws_id),
  ('product_feature_values', 'GET', @ws_id),
  ('product_feature_values', 'POST', @ws_id),
  ('product_feature_values', 'DELETE', @ws_id),
  ('combinations', 'GET', @ws_id),
  ('combinations', 'POST', @ws_id),
  ('combinations', 'PUT', @ws_id),
  ('combinations', 'DELETE', @ws_id),
  ('stock_availables', 'GET', @ws_id),
  ('stock_availables', 'PUT', @ws_id),
  ('images', 'GET', @ws_id),
  ('images', 'POST', @ws_id),
  ('categories', 'GET', @ws_id),
  ('categories', 'POST', @ws_id),
  ('categories', 'PUT', @ws_id),
  ('categories', 'DELETE', @ws_id),
  ('products', 'GET', @ws_id),
  ('products', 'POST', @ws_id),
  ('products', 'PUT', @ws_id),
  ('products', 'DELETE', @ws_id),
  ('specific_prices', 'GET', @ws_id),
  ('specific_prices', 'POST', @ws_id),
  ('specific_prices', 'PUT', @ws_id),
  ('specific_prices', 'DELETE', @ws_id);
SQL

docker exec -u www-data "${APP_CONTAINER}" php -d memory_limit=512M -r '
  require_once "/var/www/html/config/config.inc.php";
  Tools::generateHtaccess();
' 2>/dev/null || true
docker exec "${APP_CONTAINER}" php -d memory_limit=512M bin/console prestashop:theme:enable "${THEME_NAME}" 2>/dev/null || true

echo "=== [4/7] Kopiowanie grafik slidera (ps_imageslider) ==="
docker exec "${APP_CONTAINER}" mkdir -p /var/www/html/modules/ps_imageslider/images
for slide_img in sample-1.jpg sample-2.jpg; do
  if [[ -f "${SLIDER_DIR}/${slide_img}" ]]; then
    docker cp "${SLIDER_DIR}/${slide_img}" "${APP_CONTAINER}:/var/www/html/modules/ps_imageslider/images/${slide_img}"
    docker exec "${APP_CONTAINER}" chown www-data:www-data "/var/www/html/modules/ps_imageslider/images/${slide_img}"
  fi
done

echo "=== [5/7] Generowanie zdjec produktowych 3:4 (seed-images.php) ==="
EXISTING_PRODUCTS="$(docker exec -e MYSQL_PWD="${DB_ROOT_PASSWD}" "${DB_CONTAINER}" \
  mariadb -N -B -u root "${DB_NAME}" -e "SELECT COUNT(*) FROM ps_product;" 2>/dev/null | tr -d '[:space:]' || echo "0")"
if [[ "${EXISTING_PRODUCTS:-0}" -gt 20 ]]; then
  echo "Pominieto seed-images.php (wykryto ${EXISTING_PRODUCTS} zaimportowanych produktow — zdjecia zarzadzane przez import_api.py)."
elif [[ -f "${SEED_PHP}" ]]; then
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

echo "=== [6/7] Instalacja i aktywacja modulu Dyrektywy Omnibus (ps_omnibusprice, D3) ==="
if [[ -d "${OMNIBUS_SRC}" ]]; then
  if ! docker exec "${APP_CONTAINER}" test -f /var/www/html/modules/ps_omnibusprice/ps_omnibusprice.php; then
    docker exec "${APP_CONTAINER}" mkdir -p /var/www/html/modules/ps_omnibusprice
    docker cp "${OMNIBUS_SRC}/." "${APP_CONTAINER}:/var/www/html/modules/ps_omnibusprice/"
  fi
  docker exec "${APP_CONTAINER}" chown -R www-data:www-data /var/www/html/modules/ps_omnibusprice 2>/dev/null || true
  IS_OMNIBUS_INSTALLED="$(docker exec -e MYSQL_PWD="${DB_ROOT_PASSWD}" "${DB_CONTAINER}" \
    mariadb -N -B -u root "${DB_NAME}" -e "SELECT COUNT(*) FROM ps_module WHERE name = 'ps_omnibusprice';" 2>/dev/null | tr -d '[:space:]' || echo "0")"
  if [[ "${IS_OMNIBUS_INSTALLED:-0}" -eq 0 ]]; then
    docker exec -u www-data "${APP_CONTAINER}" php -d memory_limit=512M bin/console prestashop:module install ps_omnibusprice
  fi
  docker exec -u www-data "${APP_CONTAINER}" php -d memory_limit=512M -r '
    require_once "/var/www/html/config/config.inc.php";
    $mod = Module::getInstanceByName("ps_omnibusprice");
    if ($mod) {
      $mod->createTables();
      if (!Configuration::hasKey("PS_OMNIBUS_SHOW_ON_SHEET")) {
        Configuration::updateValue("PS_OMNIBUS_SHOW_ON_SHEET", "1");
      }
      if (!Configuration::hasKey("PS_OMNIBUS_SHOW_ON_LIST")) {
        Configuration::updateValue("PS_OMNIBUS_SHOW_ON_LIST", "1");
      }
      if (!Configuration::get("PS_OMNIBUS_LABEL_TPL")) {
        Configuration::updateValue("PS_OMNIBUS_LABEL_TPL", Ps_Omnibusprice::DEFAULT_LABEL);
      }
      foreach ([
        "displayHeader",
        "displayProductPriceBlock",
        "actionObjectProductAddAfter",
        "actionObjectProductUpdateAfter",
        "actionObjectSpecificPriceAddAfter",
        "actionObjectSpecificPriceUpdateAfter",
        "actionObjectSpecificPriceDeleteAfter"
      ] as $h) {
        $mod->registerHook($h);
      }
      Db::getInstance()->execute("UPDATE " . _DB_PREFIX_ . "module SET active = 1 WHERE name = \"ps_omnibusprice\"");
      Db::getInstance()->execute("INSERT IGNORE INTO " . _DB_PREFIX_ . "module_shop (id_module, id_shop, enable_device) SELECT id_module, 1, 7 FROM " . _DB_PREFIX_ . "module WHERE name = \"ps_omnibusprice\"");
      if (method_exists($mod, "syncCatalogHistory")) {
        $mod->syncCatalogHistory();
      }
    }
  '
fi

echo "=== [7/7] Czyszczenie cache PrestaShop ==="
docker exec "${APP_CONTAINER}" sh -c "rm -rf /var/www/html/var/cache/*" 2>/dev/null || true
docker exec -u www-data "${APP_CONTAINER}" php -d memory_limit=512M bin/console cache:clear 2>/dev/null || true
docker exec "${APP_CONTAINER}" chown -R www-data:www-data /var/www/html/var/cache 2>/dev/null || true

echo "Motyw '${THEME_NAME}' i zasoby Mosquito wdrozone pomyslnie!"
