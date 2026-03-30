#!/usr/bin/env python3
"""
Bundle voice batches into groups of 30 for Logic Pro round-trip processing.

Groups batches from ~/Desktop/overall_audio_batch/ into bundles of 3 batches
(~30 files each), concatenates voice files into a single WAV per bundle,
and saves a manifest for splitting back after Logic Pro processing.

Usage:
  python bundle_roundtrip.py list                    # show bundle plan
  python bundle_roundtrip.py concat <bundle_number>  # concat a specific bundle (1, 2, 3, ...)
  python bundle_roundtrip.py concat all              # concat all bundles
  python bundle_roundtrip.py split <bundle_number> <processed_voice.wav>  # split back

Directory structure created:
  ~/Desktop/logic_roundtrip/
    bundle_1/
      combined_voice.wav
      manifest.json
      processed_voice/   (after split)
    bundle_2/
      ...
"""

import sys
import json
import subprocess
import tempfile
from pathlib import Path
from pydub import AudioSegment

# --- CONFIGURATION ---
AUDIO_BATCH_DIR = Path.home() / "Desktop" / "overall_audio_batch"
OUTPUT_DIR = Path.home() / "Desktop" / "logic_roundtrip"
BATCHES_PER_BUNDLE = 3
SEPARATOR_MS = 1000  # 1s silence between voice files


def _batch_sort_key(name: str) -> tuple:
    """Sort batches: U-series first (by number), then N-series (by number)."""
    # e.g. "batch_U003" -> ("U", 3), "batch_N002" -> ("N", 2)
    prefix = name.split("_")[1][0]   # "U" or "N"
    num = int(name.split("_")[1][1:])  # 3, 2, etc.
    # U sorts before N so existing bundles don't shift
    order = {"U": 0, "N": 1}
    return (order.get(prefix, 2), num)


def discover_batches() -> list[dict]:
    """Find all batch folders and their contents, sorted U-series first then N-series."""
    batches = []
    for batch_dir in AUDIO_BATCH_DIR.iterdir():
        if not batch_dir.is_dir() or not batch_dir.name.startswith("batch_"):
            continue
        mp3s = sorted(batch_dir.glob("*.mp3"))
        timestamps = sorted(batch_dir.glob("*_timestamps.json"))
        batch_id = batch_dir.name  # e.g. "batch_U003"
        batches.append({
            "batch_id": batch_id,
            "path": batch_dir,
            "mp3s": mp3s,
            "timestamps": timestamps,
            "count": len(mp3s),
        })
    batches.sort(key=lambda b: _batch_sort_key(b["batch_id"]))
    return batches


def make_bundle_plan(batches: list[dict]) -> list[dict]:
    """Group batches into bundles of BATCHES_PER_BUNDLE."""
    bundles = []
    for i in range(0, len(batches), BATCHES_PER_BUNDLE):
        group = batches[i : i + BATCHES_PER_BUNDLE]
        bundle_num = (i // BATCHES_PER_BUNDLE) + 1
        all_mp3s = []
        all_timestamps = []
        source_batches = []
        for b in group:
            all_mp3s.extend(b["mp3s"])
            all_timestamps.extend(b["timestamps"])
            source_batches.append(b["batch_id"])
        bundles.append({
            "bundle_number": bundle_num,
            "source_batches": source_batches,
            "mp3s": all_mp3s,
            "timestamps": all_timestamps,
            "count": len(all_mp3s),
        })
    return bundles


def list_bundles():
    """Print the bundle plan."""
    batches = discover_batches()
    bundles = make_bundle_plan(batches)

    print(f"Found {len(batches)} batches -> {len(bundles)} bundles "
          f"(groups of {BATCHES_PER_BUNDLE})\n")

    for bundle in bundles:
        bundle_dir = OUTPUT_DIR / f"bundle_{bundle['bundle_number']}"
        exists = (bundle_dir / "manifest.json").exists()
        status = " [DONE]" if exists else ""
        print(f"  Bundle {bundle['bundle_number']}: "
              f"{bundle['count']} files from {', '.join(bundle['source_batches'])}{status}")
        for mp3 in bundle["mp3s"]:
            print(f"    {mp3.stem}")
    print()


def concat_bundle(bundle: dict):
    """Concatenate all voice files in a bundle into one WAV."""
    bundle_num = bundle["bundle_number"]
    bundle_dir = OUTPUT_DIR / f"bundle_{bundle_num}"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    print(f"=== Bundle {bundle_num} ({bundle['count']} files) ===")
    print(f"  Sources: {', '.join(bundle['source_batches'])}\n")

    manifest_entries = []
    combined = AudioSegment.empty()
    offset_ms = 0
    separator = AudioSegment.silent(duration=SEPARATOR_MS)

    for mp3_path in bundle["mp3s"]:
        audio = AudioSegment.from_file(str(mp3_path))
        duration_ms = len(audio)
        session_id = mp3_path.stem

        # Find matching timestamp file
        ts_path = mp3_path.parent / f"{session_id}_timestamps.json"
        has_timestamps = ts_path.exists()

        manifest_entries.append({
            "session_id": session_id,
            "source_path": str(mp3_path),
            "source_batch": mp3_path.parent.name,
            "offset_ms": offset_ms,
            "duration_ms": duration_ms,
            "timestamps_path": str(ts_path) if has_timestamps else None,
        })
        print(f"  {session_id} | {duration_ms / 1000:.1f}s | offset: {offset_ms / 1000:.1f}s")

        combined += audio + separator
        offset_ms += duration_ms + SEPARATOR_MS

    # Export combined WAV
    out_path = bundle_dir / "combined_voice.wav"
    total_s = len(combined) / 1000
    print(f"\n  Exporting combined voice ({total_s:.1f}s / {total_s / 60:.1f} min) ...")
    combined.export(str(out_path), format="wav")
    print(f"  -> {out_path}")

    # Save manifest
    manifest = {
        "bundle_number": bundle_num,
        "source_batches": bundle["source_batches"],
        "separator_ms": SEPARATOR_MS,
        "total_files": bundle["count"],
        "total_duration_ms": len(combined),
        "entries": manifest_entries,
    }
    manifest_path = bundle_dir / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"  Manifest: {manifest_path}")

    # Copy timestamp files into bundle dir for reference
    ts_dir = bundle_dir / "timestamps"
    ts_dir.mkdir(exist_ok=True)
    for ts in bundle["timestamps"]:
        dest = ts_dir / ts.name
        if not dest.exists():
            dest.write_text(ts.read_text())

    print(f"\n  Next: import {out_path} into Logic Pro")
    print(f"  Then: python bundle_roundtrip.py split {bundle_num} <processed_voice.wav>")


def split_bundle(bundle_num: int, processed_path: str):
    """Split a processed combined voice file back into individual segments."""
    bundle_dir = OUTPUT_DIR / f"bundle_{bundle_num}"
    manifest_path = bundle_dir / "manifest.json"

    if not manifest_path.exists():
        sys.exit(f"Manifest not found: {manifest_path}\n"
                 f"Run 'python bundle_roundtrip.py concat {bundle_num}' first.")

    with open(manifest_path) as f:
        manifest = json.load(f)

    out_dir = bundle_dir / "processed_voice"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"=== Splitting Bundle {bundle_num} ===")
    print(f"  Loading: {processed_path}")
    processed = AudioSegment.from_file(processed_path)
    print(f"  Duration: {len(processed) / 1000:.1f}s\n")

    for entry in manifest["entries"]:
        start = entry["offset_ms"]
        end = start + entry["duration_ms"]
        segment = processed[start:end]

        out_path = out_dir / f"{entry['session_id']}.wav"
        segment.export(str(out_path), format="wav")
        print(f"  {entry['session_id']} | {entry['duration_ms'] / 1000:.1f}s -> {out_path}")

    print(f"\nDone! Processed files in {out_dir}/")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    if command == "list":
        list_bundles()

    elif command == "concat":
        batches = discover_batches()
        bundles = make_bundle_plan(batches)

        if len(sys.argv) < 3:
            sys.exit("Usage: python bundle_roundtrip.py concat <bundle_number|all>")

        if sys.argv[2] == "all":
            for bundle in bundles:
                concat_bundle(bundle)
                print()
        else:
            num = int(sys.argv[2])
            if num < 1 or num > len(bundles):
                sys.exit(f"Bundle {num} doesn't exist. Use 'list' to see available bundles.")
            concat_bundle(bundles[num - 1])

    elif command == "split":
        if len(sys.argv) != 4:
            sys.exit("Usage: python bundle_roundtrip.py split <bundle_number> <processed_voice.wav>")
        split_bundle(int(sys.argv[2]), sys.argv[3])

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
