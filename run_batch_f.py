#!/usr/bin/env python3
"""
Batch meditation TTS processor — female voice variant (_f suffix).

Usage:
    python run_batch_f.py /path/to/batches/batch1 [--first-only]

Same as run_batch.py but uses voice 0RggJOBxyZgzpa5eXp6S and appends _f
to every session ID / filename. Output goes to batch_{first_id}_f/.
"""

import sys
import re
import json
import shutil
import glob as globmod
from pathlib import Path

import generate_voice
from generate_voice import generate_meditation

# Override voice ID
generate_voice.VOICE_ID = "eUdJpUEN3EslrgE24PKx"

OUTPUT_ROOT = Path.home() / "Desktop" / "overall_audio_batch"


def find_file(batch_dir, pattern):
    matches = globmod.glob(str(batch_dir / pattern))
    if not matches:
        sys.exit(f"ERROR: No file matching '{pattern}' in {batch_dir}")
    return Path(matches[0])


def parse_sessions_json(json_path):
    with open(json_path) as f:
        return json.load(f)


def ensure_break_before_skip(script_text):
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
        before_lines = [l for l in before_text.split('\n') if l.strip()]
        has_before = bool(before_lines and pause_or_break.search(before_lines[-1]))
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
    trailing = re.compile(
        r'(\s*(\[PAUSE:\s*\d+(?:\.\d+)?\]|<break\s+time="[^"]*"\s*/>)\s*)+$',
        re.IGNORECASE,
    )
    return trailing.sub('', script_text).rstrip()


def split_scripts(txt_path):
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
    parser = argparse.ArgumentParser(description="Batch meditation TTS — female voice (_f)")
    parser.add_argument("batch_dir", help="Path to batch folder")
    parser.add_argument("--first-only", action="store_true", help="Process only the first session")
    parser.add_argument("--limit", type=int, default=0, help="Process only the first N sessions")
    parser.add_argument("--output", "-o", help="Custom output directory")
    args = parser.parse_args()

    batch_dir = Path(args.batch_dir).resolve()
    if not batch_dir.is_dir():
        sys.exit(f"ERROR: {batch_dir} is not a directory")

    json_path = find_file(batch_dir, "sessions_*.json")
    txt_path = find_file(batch_dir, "final_session_batch_*.txt")

    sessions = parse_sessions_json(json_path)
    scripts = split_scripts(txt_path)

    print(f"Batch folder: {batch_dir}")
    print(f"Voice ID: {generate_voice.VOICE_ID}")
    print(f"Sessions JSON: {json_path.name} ({len(sessions)} sessions)")
    print(f"Scripts file: {txt_path.name} ({len(scripts)} scripts extracted)")

    missing = [s["session_id"] for s in sessions if s["session_id"] not in scripts]
    if missing:
        sys.exit(f"ERROR: Sessions in JSON but not in txt: {missing}")

    extra = set(scripts.keys()) - {s["session_id"] for s in sessions}
    if extra:
        print(f"WARNING: Scripts in txt but not in JSON (will skip): {sorted(extra)}")

    if args.output:
        batch_output = Path(args.output).resolve()
    else:
        first_id = sessions[0]["session_id"]
        batch_output = OUTPUT_ROOT / f"batch_{first_id}_f"
    batch_output.mkdir(parents=True, exist_ok=True)
    print(f"\nOutput directory: {batch_output}")

    if args.first_only:
        sessions = sessions[:1]
        print("*** First session only mode ***")
    elif args.limit > 0:
        sessions = sessions[:args.limit]
        print(f"*** Limited to first {args.limit} sessions ***")

    results = []
    errors = []
    skipped = []
    consecutive_errors = 0

    for i, session in enumerate(sessions, 1):
        sid = session["session_id"]
        sid_f = f"{sid}_f"
        title = session["title"]
        script = scripts[sid]

        mp3_dest = batch_output / f"{sid_f}.mp3"
        if mp3_dest.exists():
            skipped.append(sid_f)
            print(f"\n[{i}/{len(sessions)}] {sid_f} — already exists, skipping")
            continue

        print(f"\n{'='*60}")
        print(f"[{i}/{len(sessions)}] {sid_f} — {title}")
        print(f"{'='*60}")

        temp_dir = batch_output / f"_temp_{sid_f}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            generated = generate_meditation(sid_f, script, output_dir=str(temp_dir))

            ts_dest = batch_output / f"{sid_f}_timestamps.json"
            shutil.move(str(generated["mp3"]), str(mp3_dest))
            shutil.move(str(generated["timestamps"]), str(ts_dest))

            backup_dir = batch_output / f"backup_{sid_f}"
            backup_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(generated["calculated"]), str(backup_dir / f"{sid_f}_calculated.json"))
            shutil.move(str(generated["log"]), str(backup_dir / f"{sid_f}_session_log.md"))

            shutil.rmtree(str(temp_dir), ignore_errors=True)

            results.append({"id": sid_f, "title": title, "mp3": str(mp3_dest)})
            consecutive_errors = 0

        except Exception as e:
            errors.append({"id": sid_f, "title": title, "error": str(e)})
            print(f"\n❌ ERROR processing {sid_f}: {e}")
            shutil.rmtree(str(temp_dir), ignore_errors=True)
            consecutive_errors += 1
            if consecutive_errors >= 3:
                print("\n⛔ 3 consecutive errors — stopping batch. Re-run after fixing the issue.")
                break

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
