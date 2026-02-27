#!/usr/bin/env bash
#
# Trims music files to 15 minutes and loudness-normalizes them.
# Input:  directory of long music MP3s
# Output: ~/Desktop/trimmed_meditations/<name>_15min.mp3

set -euo pipefail

INPUT_DIR="${1:?Usage: ./trim_music.sh <input_dir>}"
OUTPUT_DIR="$HOME/Desktop/trimmed_meditations"
DURATION=900  # 15 minutes in seconds
TARGET_LUFS=-16
TRUE_PEAK=-1

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

    # Trim to 15 minutes
    trimmed=$(mktemp /tmp/trimmed_XXXXXX.mp3)
    ffmpeg -y -i "$f" -t "$DURATION" -c copy "$trimmed" 2>/dev/null

    # Loudness normalize (two-pass)
    ffmpeg -y -i "$trimmed" \
        -af "loudnorm=I=$TARGET_LUFS:TP=$TRUE_PEAK:LRA=11" \
        -ar 44100 -b:a 192k \
        "$output" 2>/dev/null

    rm -f "$trimmed"
    echo "  -> $output"
done

echo "Done. Output in $OUTPUT_DIR"
