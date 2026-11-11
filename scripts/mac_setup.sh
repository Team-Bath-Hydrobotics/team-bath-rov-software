#!/usr/bin/env bash

set -Eeuo pipefail

if (( EUID == 0 )); then
    echo "Do not run this setup script with sudo or as root." >&2
    echo "Run it as your normal macOS user: ./scripts/mac_setup.sh" >&2
    exit 1
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

echo "Installing prerequisites"

/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

if ! command -v brew >/dev/null 2>&1; then
    for brew_bin in /opt/homebrew/bin/brew /usr/local/bin/brew; do
        if [[ -x "$brew_bin" ]]; then
            eval "$("$brew_bin" shellenv)"
            break
        fi
    done
fi

if ! command -v brew >/dev/null 2>&1; then
    echo "Homebrew was installed but is not available on PATH." >&2
    echo "Open a new terminal and rerun this script." >&2
    exit 1
fi

if [[ -d "/Applications/Docker.app" ]]; then
    echo "Docker Desktop is already installed; skipping."
else
    brew install --cask docker
fi

for formula in pipx python@3.11 ffmpeg mkcert node; do
    if brew list --formula "$formula" >/dev/null 2>&1; then
        echo "$formula is already installed; skipping."
    else
        brew install "$formula"
    fi
done

if ! docker info >/dev/null 2>&1; then
    if [[ ! -d "/Applications/Docker.app" ]]; then
        echo "Docker Desktop was not found in /Applications." >&2
        exit 1
    fi

    echo "Starting Docker Desktop..."
    open -a Docker

    docker_ready=0
    for _ in {1..60}; do
        if docker info >/dev/null 2>&1; then
            docker_ready=1
            break
        fi
        sleep 2
    done

    if (( docker_ready == 0 )); then
        echo "Docker Desktop did not become ready in time." >&2
        exit 1
    fi
fi

PYTHON_BIN="$(brew --prefix python@3.11)/bin/python3.11"
UI_ROOT="$REPO_ROOT/../team-bath-rov-secondary-ui"

if [[ ! -d "$UI_ROOT" ]]; then
    echo "Secondary UI repository not found at $UI_ROOT." >&2
    echo "Clone it beside team-bath-rov-software before running setup." >&2
    exit 1
fi

npm --prefix "$UI_ROOT" install

if pipx list 2>/dev/null | grep -q "package poetry"; then
    echo "Poetry is already installed; upgrading it."
    pipx upgrade poetry
else
    pipx install --python "$PYTHON_BIN" poetry
fi
pipx ensurepath
export PATH="$HOME/.local/bin:$PATH"

for service in telemetry-processor video-processor packet-simulator; do
    cd "$REPO_ROOT/$service"
    poetry env use "$PYTHON_BIN"
    poetry install --no-interaction
done

cd "$REPO_ROOT/mqtt"

if [[ -f PASSWORD ]]; then
    echo "mqtt/PASSWORD already exists; leaving it unchanged."
    if [[ -z "$(sed -n 's/^HIVEMQ_KEYSTORE_PASSWORD=//p' PASSWORD)" ]]; then
        echo "mqtt/PASSWORD exists but contains an empty keystore password." >&2
        exit 1
    fi
else
    read -r -s -p "Enter the HiveMQ keystore password: " mqtt_password
    echo
    read -r -s -p "Confirm the HiveMQ keystore password: " mqtt_password_confirm
    echo

    if [[ "$mqtt_password" != "$mqtt_password_confirm" || -z "$mqtt_password" ]]; then
        echo "Passwords did not match or were empty." >&2
        exit 1
    fi

    printf 'HIVEMQ_KEYSTORE_PASSWORD=%s\n' "$mqtt_password" > PASSWORD
    chmod 600 PASSWORD
fi

./create_keystore.sh

echo "Setup Complete!"

echo "Now running all"

sleep 5

"$PYTHON_BIN" "$REPO_ROOT/scripts/run-all.py"
