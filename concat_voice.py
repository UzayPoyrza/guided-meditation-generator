"""
Concat/split all voice tracks for Logic Pro round-trip processing.

Usage:
  python concat_voice.py concat   # combine all voice files → combined_voice.wav
  python concat_voice.py split <processed_voice.wav>  # chop back into individual files
"""

import sys
import json
import glob as glob_mod
from pathlib import Path
from pydub import AudioSegment

JSON_PATH = Path.home() / "Desktop" / "neurotype_meditations_150.json"
VOICE_DIR = Path.home() / "Desktop" / "meditation_audio"
OUTPUT_DIR = Path.home() / "Desktop" / "logic_roundtrip"
MANIFEST_PATH = OUTPUT_DIR / "voice_manifest.json"
SEPARATOR_MS = 1000


def load_metadata():
    with open(JSON_PATH, "r") as f:
        data = json.load(f)
    return {m["id"]: m for m in data["meditations"]}


def concat():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metadata = load_metadata()

    voice_files = sorted(VOICE_DIR.glob("*.mp3"))
    if not voice_files:
        print("No voice files found in", VOICE_DIR)
        return

    print(f"Found {len(voice_files)} voice files\n")
    manifest = []
    combined = AudioSegment.empty()
    offset_ms = 0

    for vf in voice_files:
        audio = AudioSegment.from_file(str(vf))
        duration_ms = len(audio)
        mid = vf.stem
        audio_code = metadata.get(mid, {}).get("audio", "unknown")

        manifest.append({
            "id": mid,
            "filename": vf.name,
            "music_code": audio_code,
            "offset_ms": offset_ms,
            "duration_ms": duration_ms,
        })
        print(f"  {vf.name} | {duration_ms / 1000:.1f}s | music: {audio_code} | offset: {offset_ms / 1000:.1f}s")

        combined += audio + AudioSegment.silent(duration=SEPARATOR_MS)
        offset_ms += duration_ms + SEPARATOR_MS

    out_path = OUTPUT_DIR / "combined_voice.wav"
    print(f"\nExporting combined voice ({len(combined) / 1000:.1f}s / {len(combined) / 1000 / 60:.1f} min) ...")
    combined.export(str(out_path), format="wav")
    print(f"  → {out_path}")

    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"  Manifest: {MANIFEST_PATH}")
    print(f"\nImport {out_path} into Logic Pro, apply UZAYMEDVOX.cst, bounce as WAV.")
    print(f"Then run: python concat_voice.py split <processed_voice.wav>")


def split(processed_path):
    if not MANIFEST_PATH.exists():
        print(f"Manifest not found: {MANIFEST_PATH}")
        print("Run 'python concat_voice.py concat' first.")
        return

    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)

    out_dir = OUTPUT_DIR / "processed_voice"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading processed voice: {processed_path}")
    processed = AudioSegment.from_file(processed_path)
    print(f"  Duration: {len(processed) / 1000:.1f}s\n")

    for entry in manifest:
        start = entry["offset_ms"]
        end = start + entry["duration_ms"]
        segment = processed[start:end]

        out_path = out_dir / f"{entry['id']}.wav"
        segment.export(str(out_path), format="wav")
        print(f"  {entry['id']} | {entry['duration_ms'] / 1000:.1f}s → {out_path}")

    print(f"\nDone! Files in {out_dir}/")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python concat_voice.py concat")
        print("  python concat_voice.py split <processed_voice.wav>")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "concat":
        concat()
    elif cmd == "split":
        if len(sys.argv) != 3:
            print("Usage: python concat_voice.py split <processed_voice.wav>")
            sys.exit(1)
        split(sys.argv[2])
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
