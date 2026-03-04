"""
Logic Pro round-trip processor.

Workflow:
  1. `python logic_roundtrip.py concat`
     - Concatenates all voice files into one WAV (combined_voice.wav)
     - Concatenates ALL 30 music tracks into one WAV (combined_music.wav)
     - Saves manifest.json with offsets and durations for splitting

  2. Import into Logic Pro:
     - combined_voice.wav  → track with UZAYMEDVOX.cst channel strip
     - combined_music.wav  → track with UZAYMEDMUSIC.cst channel strip
     - Bounce/export each track separately as WAV

  3. `python logic_roundtrip.py split <processed_voice.wav> <processed_music.wav>`
     - Chops processed files back into individual segments
     - Output: ~/Desktop/logic_roundtrip/processed_voice/
               ~/Desktop/logic_roundtrip/processed_music/

  Voice and music can also be concat/split independently:
    `python logic_roundtrip.py concat-voice`
    `python logic_roundtrip.py concat-music`
    `python logic_roundtrip.py split-voice <processed_voice.wav>`
    `python logic_roundtrip.py split-music <processed_music.wav>`
"""

import sys
import json
import glob as glob_mod
import subprocess
import tempfile
from pathlib import Path
from pydub import AudioSegment

# --- CONFIGURATION ---
JSON_PATH = Path.home() / "Desktop" / "neurotype_meditations_150.json"
VOICE_DIR = Path.home() / "Desktop" / "meditation_audio"
MUSIC_DIR = Path.home() / "Desktop" / "trimmed_meditations"
OUTPUT_DIR = Path.home() / "Desktop" / "logic_roundtrip"
MANIFEST_PATH = OUTPUT_DIR / "manifest.json"

# 1 second of silence between segments as a separator
SEPARATOR_MS = 1000


def load_metadata():
    with open(JSON_PATH, "r") as f:
        data = json.load(f)
    return {m["id"]: m for m in data["meditations"]}


def find_music_file(audio_code):
    pattern = str(MUSIC_DIR / f"{audio_code}_*.mp3")
    matches = glob_mod.glob(pattern)
    if not matches:
        raise FileNotFoundError(f"No music file found for pattern: {pattern}")
    return Path(matches[0])


def concat_voice():
    """Concatenate all voice files into one combined WAV."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metadata = load_metadata()

    voice_files = sorted(VOICE_DIR.glob("*.mp3"))
    if not voice_files:
        print("No voice files found in", VOICE_DIR)
        return

    print(f"Found {len(voice_files)} voice files\n")
    voice_manifest = []
    combined = AudioSegment.empty()
    offset_ms = 0

    for vf in voice_files:
        audio = AudioSegment.from_file(str(vf))
        duration_ms = len(audio)
        mid = vf.stem
        audio_code = metadata.get(mid, {}).get("audio", "unknown")

        voice_manifest.append({
            "id": mid,
            "filename": vf.name,
            "music_code": audio_code,
            "offset_ms": offset_ms,
            "duration_ms": duration_ms,
        })
        print(f"  {vf.name} | {duration_ms / 1000:.1f}s | music: {audio_code} | offset: {offset_ms}ms")

        combined += audio + AudioSegment.silent(duration=SEPARATOR_MS)
        offset_ms += duration_ms + SEPARATOR_MS

    out_path = OUTPUT_DIR / "combined_voice.wav"
    print(f"\nExporting combined voice ({len(combined) / 1000:.1f}s) ...")
    combined.export(str(out_path), format="wav")
    print(f"  -> {out_path}")

    # Save voice manifest
    manifest = _load_manifest()
    manifest["separator_ms"] = SEPARATOR_MS
    manifest["voice"] = voice_manifest
    _save_manifest(manifest)


def _ffmpeg_concat(file_list, silence_ms, out_path):
    """
    Concatenate audio files with silence gaps using ffmpeg concat demuxer.
    Uses CAF (Core Audio Format) for files >4GB, WAV otherwise.
    Returns list of (duration_ms, offset_ms) for each file.
    """
    # Generate a silence file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        silence_path = tmp.name
    AudioSegment.silent(duration=silence_ms).export(silence_path, format="wav")

    # Probe durations and build concat list
    entries = []
    offset_ms = 0
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as concat_file:
        for f in file_list:
            # Get exact duration via ffprobe
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(f)],
                capture_output=True, text=True,
            )
            duration_ms = int(float(result.stdout.strip()) * 1000)
            entries.append({"offset_ms": offset_ms, "duration_ms": duration_ms})

            concat_file.write(f"file '{f}'\n")
            concat_file.write(f"file '{silence_path}'\n")
            offset_ms += duration_ms + silence_ms

        concat_list_path = concat_file.name

    # Use ffmpeg concat demuxer
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", concat_list_path, "-c:a", "pcm_s24le", str(out_path),
    ]
    print(f"  Running ffmpeg concat ...")
    subprocess.run(cmd, check=True, capture_output=True)

    # Cleanup temp files
    Path(silence_path).unlink()
    Path(concat_list_path).unlink()

    return entries


def concat_music():
    """Concatenate ALL music tracks from trimmed_meditations into one combined file."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    music_files = sorted(MUSIC_DIR.glob("*.mp3"))
    if not music_files:
        print("No music files found in", MUSIC_DIR)
        return

    print(f"Found {len(music_files)} music tracks\n")

    # Probe and display info
    music_manifest = []
    for mf in music_files:
        code = mf.stem.split("_")[0]
        music_manifest.append({
            "music_code": code,
            "filename": mf.name,
        })

    # Use ffmpeg concat (handles >4GB via CAF, much more memory efficient)
    out_path = OUTPUT_DIR / "combined_music.caf"
    entries = _ffmpeg_concat(music_files, SEPARATOR_MS, out_path)

    # Merge manifest info
    for i, entry in enumerate(entries):
        music_manifest[i]["offset_ms"] = entry["offset_ms"]
        music_manifest[i]["duration_ms"] = entry["duration_ms"]
        mf = music_manifest[i]
        print(f"  {mf['filename']} | {mf['duration_ms'] / 1000:.1f}s | offset: {mf['offset_ms']}ms")

    total_s = (entries[-1]["offset_ms"] + entries[-1]["duration_ms"]) / 1000
    print(f"\n  Total: {total_s:.1f}s / {total_s / 60:.1f} min -> {out_path}")

    # Save music manifest
    manifest = _load_manifest()
    manifest["separator_ms"] = SEPARATOR_MS
    manifest["music"] = music_manifest
    _save_manifest(manifest)


def concat():
    """Concatenate both voice and music."""
    concat_voice()
    print()
    concat_music()
    print("\nNext steps:")
    print("  1. Import both WAV files into Logic Pro")
    print("  2. Apply UZAYMEDVOX.cst to the voice track")
    print("  3. Apply UZAYMEDMUSIC.cst to the music track")
    print("  4. Bounce each track separately as WAV")
    print("  5. Run: python logic_roundtrip.py split <processed_voice.wav> <processed_music.wav>")


def _load_manifest():
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH, "r") as f:
            return json.load(f)
    return {}


def _save_manifest(manifest):
    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nManifest saved: {MANIFEST_PATH}")


def split_voice(processed_voice_path):
    """Split processed combined voice file back into individual segments."""
    manifest = _load_manifest()
    if "voice" not in manifest:
        print("No voice manifest found. Run 'python logic_roundtrip.py concat-voice' first.")
        return

    voice_out_dir = OUTPUT_DIR / "processed_voice"
    voice_out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading processed voice: {processed_voice_path}")
    processed = AudioSegment.from_file(processed_voice_path)
    print(f"  Duration: {len(processed) / 1000:.1f}s\n")

    for entry in manifest["voice"]:
        start = entry["offset_ms"]
        end = start + entry["duration_ms"]
        segment = processed[start:end]

        out_path = voice_out_dir / f"{entry['id']}.wav"
        segment.export(str(out_path), format="wav")
        print(f"  {entry['id']} | {entry['duration_ms'] / 1000:.1f}s -> {out_path}")

    print(f"\nDone! Processed voice files: {voice_out_dir}/")


def split_music(processed_music_path):
    """Split processed combined music file back into individual segments using ffmpeg."""
    manifest = _load_manifest()
    if "music" not in manifest:
        print("No music manifest found. Run 'python logic_roundtrip.py concat-music' first.")
        return

    music_out_dir = OUTPUT_DIR / "processed_music"
    music_out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Splitting processed music: {processed_music_path}\n")

    for entry in manifest["music"]:
        start_s = entry["offset_ms"] / 1000
        duration_s = entry["duration_ms"] / 1000
        out_path = music_out_dir / f"{entry['music_code']}.wav"

        cmd = [
            "ffmpeg", "-y",
            "-i", str(processed_music_path),
            "-ss", f"{start_s:.3f}",
            "-t", f"{duration_s:.3f}",
            "-c:a", "pcm_s24le",
            str(out_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"  {entry['music_code']} | {duration_s:.1f}s -> {out_path}")

    print(f"\nDone! Processed music files: {music_out_dir}/")


def split(processed_voice_path, processed_music_path):
    """Split both processed files back into individual segments."""
    split_voice(processed_voice_path)
    print()
    split_music(processed_music_path)
    print(f"\nThese can now be used by mix_meditation.py (point VOICE_DIR and MUSIC_DIR to the processed folders).")


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python logic_roundtrip.py concat                  # concat both voice + music")
        print("  python logic_roundtrip.py concat-voice            # concat voice files only")
        print("  python logic_roundtrip.py concat-music            # concat all 30 music tracks")
        print("  python logic_roundtrip.py split <voice> <music>   # split both")
        print("  python logic_roundtrip.py split-voice <voice.wav> # split voice only")
        print("  python logic_roundtrip.py split-music <music.wav> # split music only")
        sys.exit(1)

    command = sys.argv[1]

    if command == "concat":
        concat()
    elif command == "concat-voice":
        concat_voice()
    elif command == "concat-music":
        concat_music()
    elif command == "split":
        if len(sys.argv) != 4:
            print("Usage: python logic_roundtrip.py split <processed_voice.wav> <processed_music.wav>")
            sys.exit(1)
        split(sys.argv[2], sys.argv[3])
    elif command == "split-voice":
        if len(sys.argv) != 3:
            print("Usage: python logic_roundtrip.py split-voice <processed_voice.wav>")
            sys.exit(1)
        split_voice(sys.argv[2])
    elif command == "split-music":
        if len(sys.argv) != 3:
            print("Usage: python logic_roundtrip.py split-music <processed_music.wav>")
            sys.exit(1)
        split_music(sys.argv[2])
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
