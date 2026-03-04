"""
Combine processed voice + processed music into final meditation files.
No processing — just overlay with random voice offset and music fade-out.

Usage:
  python combine.py                    # process all IDs from MEDITATION_IDS
  python combine.py U003 U005 U012     # process specific IDs
"""

import sys
import json
import glob as glob_mod
import random
from pathlib import Path
from pydub import AudioSegment

# --- CONFIGURATION ---
JSON_PATH = Path.home() / "Desktop" / "neurotype_meditations_150.json"
VOICE_DIR = Path.home() / "Desktop" / "logic_roundtrip" / "processed_voice"
MUSIC_DIR = Path.home() / "Desktop" / "logic_roundtrip" / "processed_music"
FINAL_DIR = Path.home() / "Desktop" / "final_meditations"

FADE_OUT_MS = 8000

# Default meditations to process (override via CLI args)
MEDITATION_IDS = ["U012"]


def load_metadata():
    with open(JSON_PATH, "r") as f:
        data = json.load(f)
    return {m["id"]: m for m in data["meditations"]}


def find_voice_file(meditation_id):
    """Find processed voice file (WAV or MP3)."""
    for ext in ("wav", "mp3"):
        path = VOICE_DIR / f"{meditation_id}.{ext}"
        if path.exists():
            return path
    raise FileNotFoundError(f"No voice file found for {meditation_id} in {VOICE_DIR}")


def find_music_file(audio_code):
    """Find processed music file (WAV or MP3)."""
    for ext in ("wav", "mp3"):
        path = MUSIC_DIR / f"{audio_code}.{ext}"
        if path.exists():
            return path
    # Fallback: glob for any match
    pattern = str(MUSIC_DIR / f"{audio_code}*")
    matches = glob_mod.glob(pattern)
    if not matches:
        raise FileNotFoundError(f"No music file found for {audio_code} in {MUSIC_DIR}")
    return Path(matches[0])


def combine_meditation(meditation_id, metadata):
    entry = metadata.get(meditation_id)
    if not entry:
        print(f"  {meditation_id}: not found in metadata, skipping.")
        return

    audio_code = entry["audio"]
    print(f"\n--- {meditation_id} (music: {audio_code}) ---")

    voice_path = find_voice_file(meditation_id)
    music_path = find_music_file(audio_code)
    FINAL_DIR.mkdir(parents=True, exist_ok=True)

    # Load voice
    voice = AudioSegment.from_file(str(voice_path))
    print(f"  Voice: {len(voice)/1000:.1f}s, {voice.dBFS:.1f} dBFS")

    # Timing
    voice_offset_ms = int(random.uniform(2, 7) * 1000)
    total_duration_ms = len(voice) + voice_offset_ms + FADE_OUT_MS
    print(f"  Voice offset: {voice_offset_ms / 1000:.1f}s")
    print(f"  Total duration: {total_duration_ms / 1000:.1f}s")

    # Load and prepare music
    music = AudioSegment.from_file(str(music_path))
    if len(music) < total_duration_ms:
        repeats = (total_duration_ms // len(music)) + 1
        music = music * repeats
    music = music[:total_duration_ms]
    music = music.fade_out(FADE_OUT_MS)

    # Overlay voice onto music
    mixed = music.overlay(voice, position=voice_offset_ms)

    # Export
    final_path = FINAL_DIR / f"{meditation_id}.mp3"
    mixed.export(str(final_path), format="mp3", bitrate="192k")
    print(f"  → {final_path}")


if __name__ == "__main__":
    ids = sys.argv[1:] if len(sys.argv) > 1 else MEDITATION_IDS
    metadata = load_metadata()

    for mid in ids:
        combine_meditation(mid, metadata)

    print("\nDone.")
