#!/bin/bash

# ── Check for Python 3 ─────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "Python 3 not found. Installing via Homebrew..."

    # Install Homebrew if not present
    if ! command -v brew &>/dev/null; then
        echo "Installing Homebrew (you may be prompted for your Mac password)..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        # Add brew to PATH for Apple Silicon Macs
        eval "$(/opt/homebrew/bin/brew shellenv)" 2>/dev/null || true
        eval "$(/usr/local/bin/brew shellenv)" 2>/dev/null || true
    fi

    brew install python3
fi