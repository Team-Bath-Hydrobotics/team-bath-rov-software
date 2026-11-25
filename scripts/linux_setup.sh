#!/usr/bin/env bash
# Arch Linux setup for team-bath-rov-software.
# Port of the Windows setup script: installs prerequisites, configures the
# secondary UI, syncs the Python services, creates the MQTT keystore and
# starts everything via scripts/run-all.py.
#
# Place this in scripts/ next to the Windows script and run:
#   bash scripts/setup-linux.sh

set -euo pipefail

die() {
    echo "ERROR: $*" >&2
    exit 1
}

if [[ $EUID -eq 0 ]]; then
    die "Run this as your normal user, not root. It uses sudo where needed."
fi

command -v pacman >/dev/null 2>&1 || die "pacman was not found. This script is for Arch-based systems."

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
UI_ROOT="$(dirname "$REPO_ROOT")/team-bath-rov-secondary-ui"

# Fail fast, before installing anything.
[[ -d "$UI_ROOT" ]] || die "Secondary UI repository was not found at $UI_ROOT. Clone it beside team-bath-rov-software first."

# ---------------------------------------------------------------------------
# Prerequisites
# ---------------------------------------------------------------------------
echo "==> Installing prerequisites..."
# If pacman reports 404 errors your package database is stale: run
# 'sudo pacman -Syu' first (don't use -Sy on its own, it risks partial upgrades).
#
# Python 3.11 is not installed here on purpose: Arch's system Python is far
# newer, so uv downloads and manages 3.11 itself below.
sudo pacman -S --needed \
    git \
    docker docker-compose docker-buildx \
    uv \
    nodejs npm \
    ffmpeg \
    mkcert nss \
    openssl

echo "==> Enabling the Docker service..."
sudo systemctl enable --now docker.service

if ! id -nG | tr ' ' '\n' | grep -qx docker; then
    sudo usermod -aG docker "$(id -un)"
    die "Added $(id -un) to the 'docker' group. Log out and back in (or run 'newgrp docker' in this terminal), then rerun this script."
fi

# ---------------------------------------------------------------------------
# Python 3.11 (managed by uv)
# ---------------------------------------------------------------------------
echo "==> Setting up Python 3.11 via uv..."
uv python install 3.11
PYTHON_PATH="$(uv python find 3.11)"
[[ -x "$PYTHON_PATH" ]] || die "Python 3.11 was not found (uv returned '$PYTHON_PATH')."

# ---------------------------------------------------------------------------
# Secondary UI
# ---------------------------------------------------------------------------
UI_ENV_FILE="$UI_ROOT/.env"
touch "$UI_ENV_FILE"

# Drop any existing VITE_MQTT_HOST/PORT/URL lines, then set the WebSocket URL.
tmp_env="$(mktemp)"
grep -Ev '^[[:space:]]*VITE_MQTT_(HOST|PORT|URL)[[:space:]]*=' "$UI_ENV_FILE" > "$tmp_env" || true
echo "VITE_MQTT_URL=wss://localhost:8884/mqtt" >> "$tmp_env"
cat "$tmp_env" > "$UI_ENV_FILE"
rm -f "$tmp_env"
echo "Configured MQTT WebSocket settings in $UI_ENV_FILE."

echo "==> Installing UI dependencies..."
(cd "$UI_ROOT" && npm install)

# ---------------------------------------------------------------------------
# Python services
# ---------------------------------------------------------------------------
for service in telemetry-processor video-processor packet-simulator; do
    echo "==> uv sync: $service"
    (cd "$REPO_ROOT/$service" && uv sync --python "$PYTHON_PATH")
done

# ---------------------------------------------------------------------------
# Docker readiness
# ---------------------------------------------------------------------------
if ! docker info >/dev/null 2>&1; then
    echo "Starting Docker..."
    sudo systemctl start docker.service

    docker_ready=false
    for _ in $(seq 1 60); do
        sleep 2
        if docker info >/dev/null 2>&1; then
            docker_ready=true
            break
        fi
    done
    "$docker_ready" || die "Docker did not become ready. Check 'systemctl status docker.service' and rerun the script."
fi

# ---------------------------------------------------------------------------
# MQTT keystore
# ---------------------------------------------------------------------------
MQTT_ROOT="$REPO_ROOT/mqtt"
PASSWORD_FILE="$MQTT_ROOT/PASSWORD"

if [[ ! -f "$PASSWORD_FILE" ]]; then
    read -rsp "Enter the HiveMQ keystore password: " password
    echo
    read -rsp "Confirm the HiveMQ keystore password: " confirmation
    echo

    if [[ -z "${password//[[:space:]]/}" || "$password" != "$confirmation" ]]; then
        die "Passwords did not match or were empty."
    fi

    (umask 077 && printf 'HIVEMQ_KEYSTORE_PASSWORD=%s\n' "$password" > "$PASSWORD_FILE")
    unset password confirmation
else
    echo "mqtt/PASSWORD already exists; leaving it unchanged."
    grep -Eq '^HIVEMQ_KEYSTORE_PASSWORD=.+$' "$PASSWORD_FILE" \
        || die "mqtt/PASSWORD exists but contains an empty or invalid keystore password."
fi

(cd "$MQTT_ROOT" && bash ./create_keystore.sh) || die "MQTT keystore creation failed."

# ---------------------------------------------------------------------------
# Run everything
# ---------------------------------------------------------------------------
echo "Linux setup complete. Starting all services..."
exec "$PYTHON_PATH" "$REPO_ROOT/scripts/run-all.py"
