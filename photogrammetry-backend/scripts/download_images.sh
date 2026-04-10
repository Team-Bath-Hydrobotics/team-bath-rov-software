#!/usr/bin/env bash
BASE_URL="https://huggingface.co/datasets/wildflow/sweet-corals/resolve/main/indonesia_pemuteran_p1_20250213/raw/B1_Left"
START_INDEX=7546
NUM_IMAGES=15
TMP_DIR=$(mktemp -d)

for i in $(seq $START_INDEX $((START_INDEX + NUM_IMAGES - 1))); do
    echo "Downloading GPAA${i}.JPG..."
    curl -sL --max-time 30 -o "$TMP_DIR/GPAA${i}.JPG" "${BASE_URL}/GPAA${i}.JPG"
done

zip -j ~/Desktop/coral_images.zip "$TMP_DIR"/*.JPG
rm -rf "$TMP_DIR"
echo "Done — coral_images.zip saved to Desktop"