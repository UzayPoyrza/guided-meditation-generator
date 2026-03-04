"""
Concat/split all music tracks for Logic Pro round-trip processing.

Usage:
  python concat_music.py concat   # combine all 30 tracks → combined_music.caf
  python concat_music.py split <processed_music.caf>  # chop back into individual files
"""

import sys
import json
import subprocess
import tempfile
from pathlib import Path
from pydub import AudioSegment

MUSIC_DIR = Path.home() / "Desktop" / "trimmed_meditations"
OUTPUT_DIR = Path.home() / "Desktop" / "logic_roundtrip"
MANIFEST_PATH = OUTPUT_DIR / "music_manifest.json"
SEPARATOR_MS = 1000


def concat():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    music_files = sorted(MUSIC_DIR.glob("*.mp3"))
    if not music_files:
        print("No music files found in", MUSIC_DIR)
        return

    print(f"Found {len(music_files)} music tracks\n")

    # Generate silence separator
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        silence_path = tmp.name
    AudioSegment.silent(duration=SEPARATOR_MS).export(silence_path, format="wav")

    # Probe durations and build concat list
    manifest = []
    offset_ms = 0

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for mf in music_files:
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(mf)],
                capture_output=True, text=True,
            )
            duration_ms = int(float(result.stdout.strip()) * 1000)
            code = mf.stem.split("_")[0]

            manifest.append({
                "music_code": code,
                "filename": mf.name,
                "offset_ms": offset_ms,
                "duration_ms": duration_ms,
            })
            print(f"  {mf.name} | {duration_ms / 1000:.1f}s | offset: {offset_ms / 1000:.1f}s")

            f.write(f"file '{mf}'\n")
            f.write(f"file '{silence_path}'\n")
            offset_ms += duration_ms + SEPARATOR_MS

        concat_list = f.name

    # Concat via ffmpeg → CAF (no 4GB limit)
    out_path = OUTPUT_DIR / "combined_music.caf"
    print(f"\nConcatenating → {out_path}")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
         "-i", concat_list, "-c:a", "pcm_s24le", str(out_path)],
        check=True, capture_output=True,
    )

    Path(silence_path).unlink()
    Path(concat_list).unlink()

    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)

    total_min = offset_ms / 1000 / 60
    print(f"  Total: {total_min:.1f} min")
    print(f"  Manifest: {MANIFEST_PATH}")
    print(f"\nImport {out_path} into Logic Pro, apply UZAYMEDMUSIC.cst, bounce as WAV/CAF.")
    print(f"Then run: python concat_music.py split <processed_file>")


def split(processed_path):
    if not MANIFEST_PATH.exists():
        print(f"Manifest not found: {MANIFEST_PATH}")
        print("Run 'python concat_music.py concat' first.")
        return

    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)

    out_dir = OUTPUT_DIR / "processed_music"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Splitting: {processed_path}\n")

    for entry in manifest:
        start_s = entry["offset_ms"] / 1000
        duration_s = entry["duration_ms"] / 1000
        out_path = out_dir / f"{entry['music_code']}.wav"

        subprocess.run(
            ["ffmpeg", "-y",
             "-i", str(processed_path),
             "-ss", f"{start_s:.3f}",
             "-t", f"{duration_s:.3f}",
             "-c:a", "pcm_s24le",
             str(out_path)],
            check=True, capture_output=True,
        )
        print(f"  {entry['music_code']} | {duration_s:.1f}s → {out_path}")

    print(f"\nDone! Files in {out_dir}/")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python concat_music.py concat")
        print("  python concat_music.py split <processed_music.caf>")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "concat":
        concat()
    elif cmd == "split":
        if len(sys.argv) != 3:
            print("Usage: python concat_music.py split <processed_music.caf>")
            sys.exit(1)
        split(sys.argv[2])
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
