#!/bin/bash
# deploy/nginx/generate-certs.sh

CERTS_DIR="$(dirname "$0")/ssl"

mkdir -p "$CERTS_DIR"

if [ ! -f "$CERTS_DIR/server.crt" ]; then
    echo "Generowanie certyfikatu self-signed dla localhost..."
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$CERTS_DIR/server.key" \
        -out "$CERTS_DIR/server.crt" \
        -subj "/C=PL/ST=Pomeranian/L=Gdansk/O=Sklep/OU=IT/CN=localhost"
    
    echo "Certyfikat został wygenerowany pomyślnie."
else
    echo "Certyfikat już istnieje w $CERTS_DIR. Pomijam generowanie."
fi
