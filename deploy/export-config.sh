#!/usr/bin/env bash
set -euo pipefail

# Export bazowej konfiguracji PrestaShop do deploy/config-export/shop_base_config.sql
# Pomija dane tymczasowe (logi odwiedzin, koszyki, zamówienia testowe, maile),
# zachowując pełną strukturę wszystkich tabel.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${REPO_ROOT}/.env"
OUT_DIR="${REPO_ROOT}/deploy/config-export"
OUT_FILE="${OUT_DIR}/shop_base_config.sql"
DB_CONTAINER="prestashop_db"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Błąd: brak pliku ${ENV_FILE}" >&2
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

mkdir -p "${OUT_DIR}"

# Tabele z danymi sesyjnymi/analitycznymi/testowymi, których nie chcemy w bazowym configu
IGNORED_DATA_TABLES=(
  "${DB_NAME}.ps_connections"
  "${DB_NAME}.ps_connections_page"
  "${DB_NAME}.ps_connections_source"
  "${DB_NAME}.ps_guest"
  "${DB_NAME}.ps_page_viewed"
  "${DB_NAME}.ps_log"
  "${DB_NAME}.ps_mail"
  "${DB_NAME}.ps_smarty_cache"
  "${DB_NAME}.ps_smarty_last_flush"
  "${DB_NAME}.ps_smarty_lazy_cache"
  "${DB_NAME}.ps_cart"
  "${DB_NAME}.ps_cart_product"
  "${DB_NAME}.ps_cart_cart_rule"
  "${DB_NAME}.ps_orders"
  "${DB_NAME}.ps_order_detail"
  "${DB_NAME}.ps_order_detail_tax"
  "${DB_NAME}.ps_order_history"
  "${DB_NAME}.ps_order_invoice"
  "${DB_NAME}.ps_order_invoice_payment"
  "${DB_NAME}.ps_order_invoice_tax"
  "${DB_NAME}.ps_order_carrier"
  "${DB_NAME}.ps_order_payment"
  "${DB_NAME}.ps_order_cart_rule"
  "${DB_NAME}.ps_order_slip"
  "${DB_NAME}.ps_order_slip_detail"
  "${DB_NAME}.ps_message"
  "${DB_NAME}.ps_customer_thread"
  "${DB_NAME}.ps_customer_message"
  "${DB_NAME}.ps_webservice_account"
  "${DB_NAME}.ps_webservice_account_shop"
  "${DB_NAME}.ps_webservice_permission"
  # Katalog produktów i wyszukiwarka (ładowane czysto przez import_api.py)
  "${DB_NAME}.ps_category_product"
  "${DB_NAME}.ps_product"
  "${DB_NAME}.ps_product_lang"
  "${DB_NAME}.ps_product_shop"
  "${DB_NAME}.ps_product_attribute"
  "${DB_NAME}.ps_product_attribute_combination"
  "${DB_NAME}.ps_product_attribute_image"
  "${DB_NAME}.ps_product_attribute_lang"
  "${DB_NAME}.ps_product_attribute_shop"
  "${DB_NAME}.ps_product_carrier"
  "${DB_NAME}.ps_product_country_tax"
  "${DB_NAME}.ps_product_tag"
  "${DB_NAME}.ps_product_sale"
  "${DB_NAME}.ps_attribute"
  "${DB_NAME}.ps_attribute_lang"
  "${DB_NAME}.ps_attribute_shop"
  "${DB_NAME}.ps_attribute_group"
  "${DB_NAME}.ps_attribute_group_lang"
  "${DB_NAME}.ps_attribute_group_shop"
  "${DB_NAME}.ps_image"
  "${DB_NAME}.ps_image_lang"
  "${DB_NAME}.ps_image_shop"
  "${DB_NAME}.ps_stock"
  "${DB_NAME}.ps_stock_available"
  "${DB_NAME}.ps_stock_mvt"
  "${DB_NAME}.ps_search_index"
  "${DB_NAME}.ps_search_word"
  "${DB_NAME}.ps_layered_price_index"
  "${DB_NAME}.ps_layered_product_attribute"
)

# Tabele użytkowników, pracowników, adresów, sesji oraz korzenia kategorii pomijamy w całości (schemat + dane),
# aby nie eksportować haseł/danych osobowych i zachować lokalnego admina oraz kategorie bazowe (1, 2).
IGNORED_FULL_TABLES=(
  "${DB_NAME}.ps_customer"
  "${DB_NAME}.ps_customer_group"
  "${DB_NAME}.ps_customer_session"
  "${DB_NAME}.ps_address"
  "${DB_NAME}.ps_employee"
  "${DB_NAME}.ps_employee_shop"
  "${DB_NAME}.ps_employee_session"
  "${DB_NAME}.ps_category"
  "${DB_NAME}.ps_category_group"
  "${DB_NAME}.ps_category_lang"
  "${DB_NAME}.ps_category_shop"
)

FULL_IGNORE_FLAGS=()
for tbl in "${IGNORED_FULL_TABLES[@]}"; do
  FULL_IGNORE_FLAGS+=("--ignore-table=${tbl}")
done

DATA_IGNORE_FLAGS=("${FULL_IGNORE_FLAGS[@]}")
for tbl in "${IGNORED_DATA_TABLES[@]}"; do
  DATA_IGNORE_FLAGS+=("--ignore-table=${tbl}")
done

TMP_FILE="$(mktemp "${OUT_DIR}/.shop_base_config.XXXXXX.sql")"
trap 'rm -f "${TMP_FILE}"' EXIT

echo "Eksportowanie struktury i konfiguracji z bazy '${DB_NAME}'..."

# 1. Struktura tabel konfiguracyjnych (z pominięciem tabel użytkowników/pracowników/sesji)
docker exec -e MYSQL_PWD="${DB_ROOT_PASSWD}" "${DB_CONTAINER}" \
  mariadb-dump -u root --no-data --add-drop-table --default-character-set=utf8mb4 \
  "${FULL_IGNORE_FLAGS[@]}" "${DB_NAME}" \
  > "${TMP_FILE}"

# 2. Dane konfiguracyjne (bez tabel sesyjnych, logów, użytkowników, koszyków i zamówień)
docker exec -e MYSQL_PWD="${DB_ROOT_PASSWD}" "${DB_CONTAINER}" \
  mariadb-dump -u root --no-create-info --single-transaction --default-character-set=utf8mb4 \
  "${DATA_IGNORE_FLAGS[@]}" "${DB_NAME}" \
  >> "${TMP_FILE}"

mv "${TMP_FILE}" "${OUT_FILE}"
chmod 644 "${OUT_FILE}"
echo "Gotowe: ${OUT_FILE} ($(du -h "${OUT_FILE}" | cut -f1))"
