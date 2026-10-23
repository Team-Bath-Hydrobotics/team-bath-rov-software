#!/usr/bin/env bash

# Exit on errors, unset variables, and failed commands in a pipeline.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Configuration variables
ALIAS="hivemq"
PASSWORD_FILE="$SCRIPT_DIR/PASSWORD"
KEYSTORE_NAME="keystore.jks"
PKCS12_NAME="hivemq.p12"
CERT_NAME="localhost-cert.pem"
KEY_NAME="localhost-key.pem"
CA_CERT_NAME="mkcert-rootCA.pem"

echo "========================================="
echo " Creating HiveMQ TLS Keystore via Docker"
echo "========================================="

# Read the keystore password from the local Docker Compose env file.
if [[ ! -f "$PASSWORD_FILE" ]]; then
    echo "❌ Error: $PASSWORD_FILE is missing. Copy PASSWORD.example to PASSWORD and set a password."
    exit 1
fi

PASSWORD="$(sed -n 's/^HIVEMQ_KEYSTORE_PASSWORD=//p' "$PASSWORD_FILE")"
if [[ -z "$PASSWORD" ]]; then
    echo "❌ Error: Set HIVEMQ_KEYSTORE_PASSWORD in $PASSWORD_FILE."
    exit 1
fi

# 1. Check if mkcert is installed
if ! command -v mkcert &> /dev/null; then
    echo "❌ Error: mkcert is not installed."
    echo "Please run: brew install mkcert"
    exit 1
fi

# 2. Check if Docker is installed and running
if ! command -v docker &> /dev/null; then
    echo "❌ Error: Docker is not installed or not in your PATH."
    exit 1
fi

if ! docker info &> /dev/null; then
    echo "❌ Error: Docker daemon is not running. Please start Docker."
    exit 1
fi

# 3. Clean up any leftover temporary files from previous runs
rm -f "$CERT_NAME" "$KEY_NAME" "$PKCS12_NAME" "$KEYSTORE_NAME"

echo "Step 1: Ensuring mkcert local CA is trusted..."
mkcert -install

echo "Step 2: Generating local certificates for localhost..."
mkcert -cert-file "$CERT_NAME" -key-file "$KEY_NAME" localhost 127.0.0.1

echo "Step 3: Exporting the mkcert root CA for Python MQTT clients..."
cp "$(mkcert -CAROOT)/rootCA.pem" "$CA_CERT_NAME"

echo "Step 4: Bundling PEM files into PKCS12 format..."
openssl pkcs12 -export \
  -in "$CERT_NAME" \
  -inkey "$KEY_NAME" \
  -out "$PKCS12_NAME" \
  -name "$ALIAS" \
  -password pass:"$PASSWORD"

echo "Step 5: Converting PKCS12 bundle into Java KeyStore ($KEYSTORE_NAME) using Docker..."
# Mounts the current directory into a temporary container to run keytool

if pwd -W >/dev/null 2>&1; then
    DOCKER_DIR="$(pwd -W)"   # Git Bash on Windows
else
    DOCKER_DIR="$(pwd)"      # macOS/Linux
fi

MSYS_NO_PATHCONV=1 docker run --rm \
  --mount "type=bind,source=${DOCKER_DIR},target=/tmp" \
  --workdir /tmp \
  hivemq/hivemq-ce:latest \
  keytool -importkeystore \
  -srckeystore "$PKCS12_NAME" \
  -srcstoretype PKCS12 \
  -srcstorepass "$PASSWORD" \
  -destkeystore "$KEYSTORE_NAME" \
  -deststoretype JKS \
  -deststorepass "$PASSWORD" \
  -noprompt

echo "Step 6: Cleaning up temporary files..."
rm -f "$CERT_NAME" "$KEY_NAME" "$PKCS12_NAME"

echo "========================================="
echo "✅ Success! Your '$KEYSTORE_NAME' is ready."
echo "✅ Python clients should trust '$CA_CERT_NAME'."
echo "========================================="
