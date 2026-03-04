#!/usr/bin/env bash
#
# Trims music files to 15 minutes. No loudness normalization.
# Input:  directory of long music MP3s
# Output: ~/Desktop/trimmed_meditations/<name>_15min.mp3

set -euo pipefail

INPUT_DIR="${1:?Usage: ./trim_music_only.sh <input_dir>}"
OUTPUT_DIR="$HOME/Desktop/trimmed_meditations"
DURATION=900  # 15 minutes in seconds

mkdir -p "$OUTPUT_DIR"

for f in "$INPUT_DIR"/*.mp3; do
    [ -f "$f" ] || continue
    basename="$(basename "${f%.mp3}")"
    output="$OUTPUT_DIR/${basename}_15min.mp3"

    if [ -f "$output" ]; then
        echo "Skipping $basename (already exists)"
        continue
    fi

    echo "Processing: $basename"
    ffmpeg -y -i "$f" -t "$DURATION" -c copy "$output" 2>/dev/null
    echo "  -> $output"
done

echo "Done. Output in $OUTPUT_DIR"
