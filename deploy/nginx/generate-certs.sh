#!/bin/bash
# deploy/nginx/generate-certs.sh
# Generowanie certyfikatu self-signed SSL dla localhost (Wymaganie W3)

set -e

CERTS_DIR="$(cd "$(dirname "$0")" && pwd)/ssl"
mkdir -p "$CERTS_DIR"

if [ ! -f "$CERTS_DIR/server.crt" ] || [ ! -f "$CERTS_DIR/server.key" ]; then
    echo "Generowanie certyfikatu self-signed SSL dla localhost..."
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$CERTS_DIR/server.key" \
        -out "$CERTS_DIR/server.crt" \
        -subj "/C=PL/ST=Pomorskie/L=Gdansk/O=Politechnika Gdanska/OU=ETI/CN=localhost"
    chmod 600 "$CERTS_DIR/server.key"
    chmod 644 "$CERTS_DIR/server.crt"
    echo "Certyfikat SSL wygenerowany pomyślnie w $CERTS_DIR."
else
    echo "Certyfikat SSL już istnieje w $CERTS_DIR. Pomijam generowanie."
fi
