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

MUSIC_DIR = Path.home() / "Desktop" / "formatted_music"
OUTPUT_DIR = Path.home() / "Desktop" / "logic_roundtrip"
MANIFEST_PATH = OUTPUT_DIR / "music_manifest.json"
SEPARATOR_MS = 5000  # 5s gap — enough for mastering reverb/compressor tails to decay


def concat():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    music_files = sorted(MUSIC_DIR.glob("*.mp3"))
    if not music_files:
        print("No music files found in", MUSIC_DIR)
        return

    print(f"Found {len(music_files)} music tracks\n")

    # Load all files into pydub for sample-accurate concatenation
    manifest = []
    combined = AudioSegment.empty()
    offset_ms = 0
    separator = AudioSegment.silent(duration=SEPARATOR_MS)

    for mf in music_files:
        code = mf.stem
        audio = AudioSegment.from_file(str(mf))
        duration_ms = len(audio)

        manifest.append({
            "music_code": code,
            "filename": mf.name,
            "offset_ms": offset_ms,
            "duration_ms": duration_ms,
        })
        print(f"  {mf.name} | {duration_ms / 1000:.1f}s | offset: {offset_ms / 1000:.1f}s")

        combined += audio + separator
        offset_ms += duration_ms + SEPARATOR_MS

    # Export to temp WAV, then convert to CAF via ffmpeg (WAV has 4GB limit)
    out_path = OUTPUT_DIR / "combined_music.caf"
    print(f"\nExporting → {out_path} ({len(combined) / 1000 / 60:.1f} min)")

    with tempfile.NamedTemporaryFile(suffix=".raw", delete=False) as tmp:
        tmp_raw = tmp.name

    # Export raw PCM from pydub, then wrap in CAF via ffmpeg
    combined.export(tmp_raw, format="raw")
    subprocess.run(
        ["ffmpeg", "-y",
         "-f", "s16le", "-ar", str(combined.frame_rate),
         "-ac", str(combined.channels),
         "-i", tmp_raw,
         "-c:a", "pcm_s24le", str(out_path)],
        check=True, capture_output=True,
    )
    Path(tmp_raw).unlink()

    # Verify duration matches
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(out_path)],
        capture_output=True, text=True,
    )
    actual_s = float(result.stdout.strip())
    expected_s = offset_ms / 1000
    print(f"  Expected: {expected_s:.1f}s | Actual: {actual_s:.1f}s | Diff: {abs(actual_s - expected_s):.3f}s")

    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)

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

    FADE_IN_S = 0.5  # gentle fade-in to mask any mastering bleed from previous track

    for i, entry in enumerate(manifest):
        start_s = entry["offset_ms"] / 1000
        duration_s = entry["duration_ms"] / 1000
        out_path = out_dir / entry["filename"]

        subprocess.run(
            ["ffmpeg", "-y",
             "-i", str(processed_path),
             "-ss", f"{start_s:.3f}",
             "-t", f"{duration_s:.3f}",
             "-af", f"afade=t=in:d={FADE_IN_S}",
             "-codec:a", "libmp3lame", "-b:a", "320k",
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
