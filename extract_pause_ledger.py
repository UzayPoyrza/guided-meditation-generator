#!/usr/bin/env python3
"""Extract pause ledger from a plaintext meditation script file.

Reads a script file containing multiple sessions (headed by U### — Title),
parses each line as speech, break, or pause event, extracts every [pause: X]
where X >= 4, and outputs sessions.json and pause_ledger.json with surrounding
speech context (breaks kept separate from speech fields).
"""

import json
import re
import sys
from pathlib import Path


SESSION_RE = re.compile(r"^([A-Z]\d{3})\s*[—–-]\s*(.+)$")
PAUSE_RE = re.compile(r"^\[pause:\s*(\d+)\]$", re.IGNORECASE)
BREAK_RE = re.compile(r'^<break\s+time="([\d.]+)s"\s*/>\s*$')


def split_sessions(text: str) -> list[dict]:
    """Split script text into sessions based on U### headings."""
    lines = text.splitlines()
    sessions: list[dict] = []
    current = None

    for line in lines:
        m = SESSION_RE.match(line.strip())
        if m:
            if current:
                sessions.append(current)
            current = {
                "session_id": m.group(1),
                "title": m.group(2).strip(),
                "lines": [],
            }
        elif current is not None:
            current["lines"].append(line)

    if current:
        sessions.append(current)

    if not sessions:
        sys.exit("No sessions found. Expected headings like: U001 — Title")
    return sessions


def parse_events(lines: list[str]) -> list[dict]:
    """Parse raw lines into a typed event stream: speech, break, or pause."""
    events: list[dict] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        pause_m = PAUSE_RE.match(stripped)
        if pause_m:
            events.append({"type": "pause", "seconds": int(pause_m.group(1))})
            continue

        break_m = BREAK_RE.match(stripped)
        if break_m:
            events.append({"type": "break", "seconds": float(break_m.group(1))})
            continue

        # It's speech — normalize whitespace
        clean = re.sub(r"\s+", " ", stripped)
        if clean:
            events.append({"type": "speech", "text": clean})

    return events


def extract_pauses(sessions: list[dict]) -> list[dict]:
    """Extract pause entries (>= 4s) with surrounding speech/break context."""
    ledger = []
    for session in sessions:
        sid = session["session_id"]
        events = parse_events(session["lines"])

        pause_count = 0
        for i, ev in enumerate(events):
            if ev["type"] != "pause" or ev["seconds"] < 4:
                continue
            pause_count += 1

            # Collect previous speech lines (walk backwards, skip non-speech)
            prev_speeches = []
            break_between_prev_speech_2_and_1 = None
            for j in range(i - 1, -1, -1):
                if events[j]["type"] == "speech":
                    prev_speeches.append(events[j]["text"])
                    if len(prev_speeches) == 2:
                        break
                elif events[j]["type"] == "break" and break_between_prev_speech_2_and_1 is None:
                    break_between_prev_speech_2_and_1 = events[j]["seconds"]

            # Collect next speech lines (walk forwards, skip non-speech)
            next_speeches = []
            break_between_next_speech_1_and_2 = None
            for j in range(i + 1, len(events)):
                if events[j]["type"] == "speech":
                    next_speeches.append(events[j]["text"])
                    if len(next_speeches) == 2:
                        break
                elif events[j]["type"] == "break" and break_between_next_speech_1_and_2 is None:
                    break_between_next_speech_1_and_2 = events[j]["seconds"]

            ledger.append({
                "session_id": sid,
                "pause_id": f"{sid}_P{pause_count:03d}",
                "pause_seconds": ev["seconds"],
                "prev_speech_1": prev_speeches[0] if len(prev_speeches) >= 1 else "",
                "prev_speech_2": prev_speeches[1] if len(prev_speeches) >= 2 else "",
                "next_speech_1": next_speeches[0] if len(next_speeches) >= 1 else "",
                "next_speech_2": next_speeches[1] if len(next_speeches) >= 2 else "",
                "break_between_prev_speech_2_and_1": break_between_prev_speech_2_and_1,
                "break_between_next_speech_1_and_2": break_between_next_speech_1_and_2,
            })
    return ledger


def main():
    if len(sys.argv) < 2:
        sys.exit("Usage: python extract_pause_ledger.py <script_file> [output_dir]")

    script_path = Path(sys.argv[1])
    if not script_path.is_file():
        sys.exit(f"File not found: {script_path}")

    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("pause_output")
    output_dir.mkdir(parents=True, exist_ok=True)

    text = script_path.read_text(encoding="utf-8")
    sessions = split_sessions(text)

    sessions_out = [{"session_id": s["session_id"], "title": s["title"]} for s in sessions]
    ledger = extract_pauses(sessions)

    first_id = sessions_out[0]["session_id"]
    sessions_path = output_dir / f"sessions_{first_id}.json"
    ledger_path = output_dir / f"pause_ledger_{first_id}.json"

    sessions_path.write_text(json.dumps(sessions_out, indent=2, ensure_ascii=False))
    ledger_path.write_text(json.dumps(ledger, indent=2, ensure_ascii=False))

    print(f"Wrote {len(sessions_out)} sessions to {sessions_path}")
    print(f"Wrote {len(ledger)} pause entries (>= 4s) to {ledger_path}")


if __name__ == "__main__":
    main()
