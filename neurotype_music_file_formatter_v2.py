#!/usr/bin/env python3
"""
neurotype_music_file_formatter_v2.py

Formats music files for meditation use:
1. Converts non-MP3 files to MP3
2. Trims files over 16 minutes to 16 minutes
3. Loops files under 14 minutes until they exceed 15 minutes (finishing the current loop cleanly)
4. Outputs to ~/Desktop/formatted_music/

Usage:
    python neurotype_music_file_formatter_v2.py <input_directory>
"""

import os
import sys
import subprocess
import json
from pathlib import Path


OUTPUT_DIR = Path.home() / "Desktop" / "formatted_music"
MAX_DURATION = 16 * 60  # 16 minutes in seconds
MIN_DURATION = 14 * 60  # 14 minutes in seconds
LOOP_TARGET = 15 * 60   # 15 minutes in seconds

AUDIO_EXTENSIONS = {
    ".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg", ".opus", ".wma", ".aiff", ".aif"
}


def get_duration(filepath: Path) -> float:
    """Get audio file duration in seconds using ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", str(filepath)
        ],
        capture_output=True, text=True
    )
    info = json.loads(result.stdout)
    return float(info["format"]["duration"])


def convert_to_mp3(filepath: Path, output: Path) -> None:
    """Convert any audio file to MP3 320kbps."""
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(filepath),
            "-codec:a", "libmp3lame", "-b:a", "320k",
            "-ar", "44100",
            str(output)
        ],
        capture_output=True, check=True
    )


def trim_to_duration(filepath: Path, output: Path, duration: float) -> None:
    """Trim an MP3 file to the specified duration in seconds."""
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(filepath),
            "-t", str(duration),
            "-codec:a", "libmp3lame", "-b:a", "320k",
            "-ar", "44100",
            str(output)
        ],
        capture_output=True, check=True
    )


def loop_audio(filepath: Path, output: Path, file_duration: float) -> None:
    """Loop an MP3 until it exceeds 15 minutes, with crossfades between loops."""
    CROSSFADE_SECS = 4  # seconds of crossfade overlap between loops

    # Calculate how many full loops we need so total >= LOOP_TARGET
    # Each crossfade removes CROSSFADE_SECS from the total, so account for that
    loops_needed = 1
    while (loops_needed * file_duration - (loops_needed - 1) * CROSSFADE_SECS) < LOOP_TARGET:
        loops_needed += 1

    effective_duration = loops_needed * file_duration - (loops_needed - 1) * CROSSFADE_SECS
    print(f"    Looping {loops_needed}x with {CROSSFADE_SECS}s crossfades "
          f"(~{effective_duration:.1f}s / {effective_duration/60:.1f}min)")

    if loops_needed == 1:
        # No looping needed after all, just copy
        convert_to_mp3(filepath, output)
        return

    # Build crossfaded result iteratively:
    # Start with the first copy, then crossfade each subsequent copy onto it
    temp_files = []
    try:
        current = filepath

        for i in range(1, loops_needed):
            temp_out = output.parent / f"_xfade_{output.stem}_{i}.mp3"
            temp_files.append(temp_out)

            # acrossfade with equal-power (sqrt) curves for natural-sounding blend
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", str(current),
                    "-i", str(filepath),
                    "-filter_complex",
                    f"acrossfade=d={CROSSFADE_SECS}:c1=tri:c2=tri",
                    "-codec:a", "libmp3lame", "-b:a", "320k",
                    "-ar", "44100",
                    str(temp_out)
                ],
                capture_output=True, check=True
            )

            # Clean up previous temp (not the original file)
            if current != filepath and current.exists():
                current.unlink()

            current = temp_out

        # Rename final temp to output
        current.rename(output)
        if output in temp_files:
            temp_files.remove(output)

    finally:
        # Clean up any remaining temp files
        for tf in temp_files:
            if tf.exists():
                tf.unlink()


def process_file(filepath: Path) -> None:
    """Process a single audio file through the pipeline."""
    stem = filepath.stem
    output_path = OUTPUT_DIR / f"{stem}.mp3"

    if output_path.exists():
        print(f"  Skipping {filepath.name} (already exists)")
        return

    print(f"  Processing: {filepath.name}")

    # Step 1: Convert to MP3 if needed
    if filepath.suffix.lower() != ".mp3":
        print(f"    Converting {filepath.suffix} -> .mp3")
        mp3_temp = OUTPUT_DIR / f"_temp_{stem}.mp3"
        convert_to_mp3(filepath, mp3_temp)
        working_file = mp3_temp
    else:
        working_file = filepath

    try:
        duration = get_duration(working_file)
        duration_min = duration / 60
        print(f"    Duration: {duration_min:.1f} min")

        if duration > MAX_DURATION:
            # Trim to 16 minutes
            print(f"    Trimming to {MAX_DURATION/60:.0f} min")
            trim_to_duration(working_file, output_path, MAX_DURATION)

        elif duration < MIN_DURATION:
            # Loop until over 15 minutes
            print(f"    Under {MIN_DURATION/60:.0f} min, looping...")
            loop_audio(working_file, output_path, duration)

        else:
            # Duration is between 14-16 min, just copy/re-encode as MP3
            print(f"    Duration OK, encoding to MP3")
            convert_to_mp3(working_file, output_path)

    finally:
        # Clean up temp file if we created one
        if working_file != filepath and working_file.exists():
            working_file.unlink()

    final_dur = get_duration(output_path)
    print(f"    -> {output_path.name} ({final_dur/60:.1f} min)")


def main():
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <input_directory_or_file>")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if input_path.is_file():
        if input_path.suffix.lower() not in AUDIO_EXTENSIONS:
            print(f"Error: {input_path} is not a supported audio file")
            sys.exit(1)
        files = [input_path]
    elif input_path.is_dir():
        files = sorted(
            f for f in input_path.iterdir()
            if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS
        )
    else:
        print(f"Error: {input_path} is not a valid file or directory")
        sys.exit(1)

    if not files:
        print(f"No audio files found in {input_path}")
        sys.exit(1)

    print(f"Found {len(files)} audio file(s)")
    print(f"Output: {OUTPUT_DIR}\n")

    for f in files:
        process_file(f)

    print(f"\nDone. {len(files)} file(s) processed -> {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
