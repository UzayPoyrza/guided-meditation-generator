#!/usr/bin/env python3
"""
Batch meditation TTS processor.

Usage:
    python run_batch.py /path/to/batches/batch1

Reads sessions JSON + script txt from the batch folder, generates audio and
subtitle files for each session, and organizes output into:
    ~/Desktop/overall_audio_batch/batch_{first_session_id}/
"""

import sys
import re
import json
import shutil
import glob as globmod
from pathlib import Path

from generate_voice import generate_meditation

OUTPUT_ROOT = Path.home() / "Desktop" / "overall_audio_batch"


def find_file(batch_dir, pattern):
    """Glob for a single file matching pattern in batch_dir."""
    matches = globmod.glob(str(batch_dir / pattern))
    if not matches:
        sys.exit(f"ERROR: No file matching '{pattern}' in {batch_dir}")
    if len(matches) > 1:
        print(f"WARNING: Multiple matches for '{pattern}', using first: {matches[0]}")
    return Path(matches[0])


def parse_sessions_json(json_path):
    """Load session list from JSON file."""
    with open(json_path) as f:
        sessions = json.load(f)
    return sessions


def ensure_break_before_skip(script_text):
    """Insert a <break> before [skip_point] if no break or pause exists on the
    line immediately before or immediately after it."""
    tag = re.compile(r'\[skip_point\]', re.IGNORECASE)
    pause_or_break = re.compile(
        r'(\[pause:\s*\d+(?:\.\d+)?\s*\]|<break\s+time="[^"]*"\s*/>)',
        re.IGNORECASE,
    )
    result = []
    last_end = 0
    for m in tag.finditer(script_text):
        before_text = script_text[last_end:m.start()]
        after_text = script_text[m.end():]

        # Check the last non-empty line before [skip_point]
        before_lines = [l for l in before_text.split('\n') if l.strip()]
        has_before = bool(before_lines and pause_or_break.search(before_lines[-1]))

        # Check the first non-empty line after [skip_point]
        after_lines = [l for l in after_text.split('\n') if l.strip()]
        has_after = bool(after_lines and pause_or_break.search(after_lines[0]))

        result.append(before_text)
        if not has_before and not has_after:
            result.append('<break time="1.0s" />\n')
        result.append(m.group(0))
        last_end = m.end()
    result.append(script_text[last_end:])
    return ''.join(result)


def strip_trailing_pause(script_text):
    """Remove any trailing [PAUSE: N] or <break> tags from the end of a script."""
    trailing = re.compile(
        r'(\s*(\[PAUSE:\s*\d+(?:\.\d+)?\]|<break\s+time="[^"]*"\s*/>)\s*)+$',
        re.IGNORECASE,
    )
    return trailing.sub('', script_text).rstrip()


def split_scripts(txt_path):
    """Split batch txt file into {session_id: script_text} dict."""
    with open(txt_path) as f:
        content = f.read()

    header_pattern = re.compile(r'^\s*([UN]\d+)\s*—\s*(.+)$', re.MULTILINE)
    headers = list(header_pattern.finditer(content))

    if not headers:
        sys.exit(f"ERROR: No session headers found in {txt_path}")

    scripts = {}
    for i, match in enumerate(headers):
        session_id = match.group(1)
        start = match.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(content)
        script_text = content[start:end].strip()
        script_text = ensure_break_before_skip(script_text)
        script_text = strip_trailing_pause(script_text)
        scripts[session_id] = script_text

    return scripts


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Batch meditation TTS processor")
    parser.add_argument("batch_dir", help="Path to batch folder")
    parser.add_argument("--output", "-o", help="Custom output directory (default: ~/Desktop/overall_audio_batch/batch_{first_id})")
    args = parser.parse_args()

    batch_dir = Path(args.batch_dir).resolve()
    if not batch_dir.is_dir():
        sys.exit(f"ERROR: {batch_dir} is not a directory")

    # Step 1: Parse inputs
    json_path = find_file(batch_dir, "sessions_*.json")
    txt_path = find_file(batch_dir, "final_session_batch_*.txt")

    sessions = parse_sessions_json(json_path)
    scripts = split_scripts(txt_path)

    print(f"Batch folder: {batch_dir}")
    print(f"Sessions JSON: {json_path.name} ({len(sessions)} sessions)")
    print(f"Scripts file: {txt_path.name} ({len(scripts)} scripts extracted)")

    # Validate: every session in JSON has a matching script
    missing = [s["session_id"] for s in sessions if s["session_id"] not in scripts]
    if missing:
        sys.exit(f"ERROR: Sessions in JSON but not in txt: {missing}")

    extra = set(scripts.keys()) - {s["session_id"] for s in sessions}
    if extra:
        print(f"WARNING: Scripts in txt but not in JSON (will skip): {sorted(extra)}")

    # Step 2: Create output structure
    if args.output:
        batch_output = Path(args.output).resolve()
    else:
        first_id = sessions[0]["session_id"]
        batch_output = OUTPUT_ROOT / f"batch_{first_id}"
    batch_output.mkdir(parents=True, exist_ok=True)
    print(f"\nOutput directory: {batch_output}")

    # Step 3: Process each session
    results = []
    errors = []
    skipped = []
    consecutive_errors = 0

    for i, session in enumerate(sessions, 1):
        sid = session["session_id"]
        title = session["title"]
        script = scripts[sid]

        # Skip if already generated
        mp3_dest = batch_output / f"{sid}.mp3"
        if mp3_dest.exists():
            skipped.append(sid)
            print(f"\n[{i}/{len(sessions)}] {sid} — already exists, skipping")
            continue

        print(f"\n{'='*60}")
        print(f"[{i}/{len(sessions)}] {sid} — {title}")
        print(f"{'='*60}")

        # Generate into a temp dir, then organize
        temp_dir = batch_output / f"_temp_{sid}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            generated = generate_meditation(sid, script, output_dir=str(temp_dir))

            # Move mp3 and timestamps JSON to batch folder root
            ts_dest = batch_output / f"{sid}_timestamps.json"
            shutil.move(str(generated["mp3"]), str(mp3_dest))
            shutil.move(str(generated["timestamps"]), str(ts_dest))

            # Move calculated JSON and session log to backup subfolder
            backup_dir = batch_output / f"backup_{sid}"
            backup_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(generated["calculated"]), str(backup_dir / f"{sid}_calculated.json"))
            shutil.move(str(generated["log"]), str(backup_dir / f"{sid}_session_log.md"))

            # Clean up temp dir
            shutil.rmtree(str(temp_dir), ignore_errors=True)

            results.append({"id": sid, "title": title, "mp3": str(mp3_dest)})
            consecutive_errors = 0

        except Exception as e:
            errors.append({"id": sid, "title": title, "error": str(e)})
            print(f"\n❌ ERROR processing {sid}: {e}")
            # Clean up temp dir on error
            shutil.rmtree(str(temp_dir), ignore_errors=True)
            consecutive_errors += 1
            if consecutive_errors >= 3:
                print("\n⛔ 3 consecutive errors — stopping batch. Re-run after fixing the issue.")
                break

    # Step 4: Summary
    print(f"\n{'='*60}")
    print("BATCH COMPLETE")
    print(f"{'='*60}")
    print(f"Output: {batch_output}")
    print(f"Succeeded: {len(results)}/{len(sessions)}")
    if skipped:
        print(f"Skipped (already existed): {len(skipped)}")

    if results:
        print("\nGenerated:")
        for r in results:
            print(f"  {r['id']} — {r['title']}")

    if errors:
        print(f"\nFailed ({len(errors)}):")
        for e in errors:
            print(f"  {e['id']} — {e['title']}: {e['error']}")


if __name__ == "__main__":
    main()
