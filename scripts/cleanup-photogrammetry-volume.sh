#!/usr/bin/env bash
# Cleans up the photogrammetry Docker volume to reclaim disk space.
# Usage: ./scripts/cleanup-photogrammetry-volume.sh [--force]

set -euo pipefail

COMPOSE_FILE="docker-compose.photogrammetry.yml"
VOLUME_NAME="$(basename "$(pwd)")_photogrammetry-data"

echo "Photogrammetry volume cleanup"
echo "=============================="

# Check if volume exists
if ! docker volume inspect "$VOLUME_NAME" &>/dev/null; then
    echo "Volume '$VOLUME_NAME' does not exist. Nothing to clean up."
    exit 0
fi

# Show current volume usage
SIZE=$(docker run --rm -v "$VOLUME_NAME":/data alpine sh -c 'du -sh /data 2>/dev/null' | cut -f1)
echo "Current volume usage: $SIZE"

if [[ "${1:-}" != "--force" ]]; then
    read -rp "This will delete all uploaded images and reconstruction outputs. Continue? [y/N] " confirm
    if [[ "$confirm" != [yY] ]]; then
        echo "Aborted."
        exit 0
    fi
fi

# Stop the container if running
if docker compose -f "$COMPOSE_FILE" ps --status running 2>/dev/null | grep -q photogrammetry; then
    echo "Stopping photogrammetry service..."
    docker compose -f "$COMPOSE_FILE" down
fi

# Remove and recreate the volume
echo "Removing volume '$VOLUME_NAME'..."
docker volume rm "$VOLUME_NAME"
echo "Done. Volume will be recreated on next startup."
