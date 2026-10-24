#!/bin/bash
# deploy/init.sh

echo "=== Rozpoczynam inicjalizację środowiska PrestaShop ==="

if [ ! -f .env ]; then
    echo "Tworzę plik .env na podstawie .env.example..."
    cp .env.example .env
else
    echo "Plik .env już istnieje."
fi

./deploy/nginx/generate-certs.sh

echo "Podnoszę kontenery..."
# DODANA FLAGA --env-file
docker compose --env-file .env -f deploy/compose.yaml up -d

echo "Czekam na zakończenie instalacji PrestaShop (może to zająć kilka minut)..."

# DODANA FLAGA --env-file
until docker compose --env-file .env -f deploy/compose.yaml logs prestashop | grep -q "Installation successful"; do
    sleep 5
    echo -n "."
done
echo -e "\nPrestaShop został zainstalowany!"

source .env
# DODANA FLAGA --env-file
docker compose --env-file .env -f deploy/compose.yaml exec -T db mysql -u"$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" -e \
    "UPDATE ps_configuration SET value = '1' WHERE name IN ('PS_SSL_ENABLED', 'PS_SSL_ENABLED_EVERYWHERE');"
echo "Opcja SSL Everywhere włączona."

# Wczytywanie konfiguracji bazowej (jeśli istnieje w repozytorium)
if [ -f "deploy/config-export/shop_base_config.sql" ]; then
    echo "Wczytywanie konfiguracji bazowej sklepu (płatności, przewoźnicy, język)..."
    source .env
    docker compose --env-file .env -f deploy/compose.yaml exec -T db mysql -u"$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" < deploy/config-export/shop_base_config.sql
    echo "Konfiguracja bazowa wczytana!"
fi


echo "=== Środowisko gotowe! ==="
echo "Sklep: https://localhost"
echo "Panel admina: https://localhost/admin-dev"
echo "Mailpit: http://localhost:8025"