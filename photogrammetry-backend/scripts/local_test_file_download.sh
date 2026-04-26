#!/usr/bin/env bash
# Download images to local directory
NUM_IMAGES=${1:-15}
BASE_URL="https://huggingface.co/datasets/wildflow/sweet-corals/resolve/main/indonesia_pemuteran_p1_20250213/raw/B1_Left"
API="http://localhost:8100"

echo "Downloading $NUM_IMAGES images..."
LOCAL_DIR="./coral_images_$JOB"
mkdir -p "$LOCAL_DIR"
END_INDEX=$((START_INDEX + NUM_IMAGES - 1))
for i in $(seq $START_INDEX $END_INDEX); do
    printf "  GPAA%s.JPG... " "$i"
    curl -sL --max-time 30 -o "$LOCAL_DIR/GPAA${i}.JPG" "${BASE_URL}/GPAA${i}.JPG"
    if [ -s "$LOCAL_DIR/GPAA${i}.JPG" ]; then
        echo "done ($(du -h "$LOCAL_DIR/GPAA${i}.JPG" | cut -f1))"
    else
        echo "SKIPPED (download failed)"
        rm -f "$LOCAL_DIR/GPAA${i}.JPG"
    fi
done
echo "Downloaded $NUM_IMAGES images ($(du -sh "$LOCAL_DIR" | cut -f1) total)"
echo ""