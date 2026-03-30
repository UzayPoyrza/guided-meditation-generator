#!/usr/bin/env python3
"""
Multi-voice TTS meditation generator (Inworld + ElevenLabs).

Voices:
    Luna, Claire, Graham — Inworld TTS
    Silas                — ElevenLabs TTS

Produces per-session:
  {id}.mp3, {id}_timestamps.json, {id}_calculated.json, {id}_session_log.md

Usage:
    source .venv/bin/activate
    python tts_generate.py
"""

import os
import re
import json
import base64
import random
import requests
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from pydub import AudioSegment
from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings

load_dotenv()

# --- CONFIGURATION ---
INWORLD_API_KEY = os.getenv("INWORLD_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
INWORLD_ENDPOINT = "https://api.inworld.ai/tts/v1/voice"
INWORLD_MODEL = "inworld-tts-1.5-max"
OUTPUT_DIR = Path("/tmp/tts") if os.getenv("AWS_LAMBDA_FUNCTION_NAME") else Path.home() / "Desktop" / "inworld_test"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

VOICES = {
    "Luna":   {"api": "inworld",    "speed": 1.0,  "temp": 0.9},
    "Claire": {"api": "inworld",    "speed": 0.9,  "temp": 0.8},
    "Graham": {"api": "inworld",    "speed": 0.94, "temp": 0.9},
    "Silas":  {"api": "elevenlabs", "voice_id": "5MzdXfNI3TSWsCPwZFrB", "speed": 0.8},
}


def normalize_pause_tags(script_text):
    """Catch malformed pause tags from LLM output and normalize to [PAUSE: N].

    Handles: <pause: N>, <pause:N>, <pause:N], [pause:N>, (pause: N),
    angle/square bracket mismatches, missing spaces, etc.
    """
    pattern = re.compile(
        r'[\[<(]\s*pause\s*[:;]\s*(\d+(?:\.\d+)?)\s*[\]>)]',
        re.IGNORECASE,
    )
    return pattern.sub(r'[PAUSE: \1]', script_text)


def ensure_break_before_skip(script_text):
    """Insert a <break> before [skip_point] if no break or pause on adjacent lines."""
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


def limit_breaks(text):
    """Convert every 4th+ consecutive <break> to [pause:] to prevent speed issues."""
    break_pattern = re.compile(r'<break\s+time="([^"]*?)s"\s*/>')
    result = []
    break_count = 0
    last_end = 0
    for m in break_pattern.finditer(text):
        result.append(text[last_end:m.start()])
        break_count += 1
        if break_count >= 4:
            result.append(f'[pause: {m.group(1)}]')
            break_count = 0
        else:
            result.append(m.group(0))
        last_end = m.end()
    result.append(text[last_end:])
    return "".join(result)


def preprocess_script(script_text):
    """Normalize tags, apply ensure_break_before_skip and limit_breaks."""
    script_text = normalize_pause_tags(script_text)
    script_text = ensure_break_before_skip(script_text)

    # Reset break counter at each [pause:] / [skip_point]
    pause_split = re.split(r'(\[PAUSE:\s*\d+(?:\.\d+)?\]|\[skip_point\])', script_text, flags=re.IGNORECASE)
    processed_parts = []
    for p in pause_split:
        if re.match(r'\[PAUSE:\s*\d+(?:\.\d+)?\]', p, flags=re.IGNORECASE) or re.match(r'\[skip_point\]', p, flags=re.IGNORECASE):
            processed_parts.append(p)
        else:
            processed_parts.append(limit_breaks(p))
    return "".join(processed_parts)


def synthesize_inworld(text, voice_id, speaking_rate, temperature):
    """Send text to Inworld TTS with WORD timestamps, return (audio_bytes, timestamp_info)."""
    headers = {
        "Authorization": f"Basic {INWORLD_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "voiceId": voice_id,
        "modelId": INWORLD_MODEL,
        "audioConfig": {
            "audioEncoding": "MP3",
            "sampleRateHertz": 44100,
            "bitRate": 128000,
            "speakingRate": speaking_rate,
        },
        "temperature": temperature,
        "timestampType": "WORD",
    }
    response = requests.post(INWORLD_ENDPOINT, json=payload, headers=headers)
    response.raise_for_status()
    result = response.json()
    audio_bytes = base64.b64decode(result["audioContent"])
    timestamp_info = result.get("timestampInfo", {})
    return audio_bytes, timestamp_info


def synthesize_elevenlabs(text, voice_cfg):
    """Send text to ElevenLabs TTS with character timestamps, return (audio_bytes, alignment)."""
    client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
    response = client.text_to_speech.convert_with_timestamps(
        voice_id=voice_cfg["voice_id"],
        text=text,
        model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128",
        voice_settings=VoiceSettings(
            speed=voice_cfg["speed"],
            stability=0.95,
            similarity_boost=0.95,
            style=0.0,
            use_speaker_boost=True,
        ),
    )
    audio_bytes = base64.b64decode(response.audio_base_64)
    return audio_bytes, response.alignment


def generate_meditation(meditation_id, script_text, voice_id, output_dir=None, timestamps=False):
    """Generate meditation MP3, optionally with subtitle JSONs + session log."""
    out = Path(output_dir) if output_dir else OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)

    voice_cfg = VOICES[voice_id]
    api = voice_cfg["api"]

    script_text = preprocess_script(script_text)

    final_audio = AudioSegment.empty()
    parts = re.split(r'(\[PAUSE:\s*\d+(?:\.\d+)?\]|\[skip_point\])', script_text, flags=re.IGNORECASE)

    # Random start/end silence (same as ElevenLabs version)
    start_silence = random.uniform(1.0, 3.0)
    end_silence = random.uniform(1.0, 2.0)

    final_audio += AudioSegment.silent(duration=int(start_silence * 1000))
    cursor = start_silence

    timestamps_subtitles = []
    calculated_subtitles = []
    raw_timestamp_log = []
    skip_points = []

    print(f"\n--- Processing {meditation_id} (voice: {voice_id}, api: {api}) ---")
    print(f"   - Adding {start_silence:.1f}s start silence")

    for part in parts:
        part = part.strip()
        if not part:
            continue

        if part.upper() == "[SKIP_POINT]":
            skip_points.append(round(cursor, 3))
            print(f"   - Skip point at {cursor:.1f}s")
            continue

        if re.match(r'\[PAUSE:\s*\d+(?:\.\d+)?\]', part, flags=re.IGNORECASE):
            seconds = float(re.search(r'\d+(?:\.\d+)?', part).group())
            print(f"   - Adding {seconds}s silence")
            final_audio += AudioSegment.silent(duration=int(seconds * 1000))
            cursor += seconds

        else:
            print(f"   - Voicing segment: '{part[:40]}...'")

            temp_file = str(out / f"_temp_{voice_id}.mp3")
            if api == "elevenlabs":
                audio_bytes, alignment = synthesize_elevenlabs(part, voice_cfg)
            else:
                audio_bytes, timestamp_info = synthesize_inworld(
                    part, voice_id, voice_cfg["speed"], voice_cfg["temp"],
                )
                alignment = None

            with open(temp_file, "wb") as f:
                f.write(audio_bytes)
            voice_chunk = AudioSegment.from_file(temp_file, format="mp3")
            final_audio += voice_chunk
            os.remove(temp_file)

            if timestamps:
                calc_text = re.sub(r'<break\s+time="[^"]*"\s*/>', '\n', part)
                calc_text = re.sub(r'\n{2,}', '\n', calc_text).strip()

                if api == "elevenlabs":
                    if calc_text:
                        calculated_subtitles.append({"start": round(cursor, 3), "text": calc_text})

                    if alignment:
                        raw_timestamp_log.append({
                            "segment_text": part,
                            "offset": round(cursor, 3),
                            "characters": alignment.characters,
                            "character_start_times": alignment.character_start_times_seconds,
                            "character_end_times": alignment.character_end_times_seconds,
                        })

                        sub_segments = re.split(r'<break\s+time="[^"]*"\s*/>', part)
                        chars = alignment.characters
                        starts = alignment.character_start_times_seconds
                        ends = alignment.character_end_times_seconds

                        is_spoken = [starts[i] != ends[i] or chars[i] in (" ", "\n", "\r", "\t")
                                     for i in range(len(chars))]

                        char_idx = 0
                        for seg in sub_segments:
                            clean_text = re.sub(r'\s+', ' ', seg).strip()
                            if not clean_text:
                                continue
                            while char_idx < len(chars) and not is_spoken[char_idx]:
                                char_idx += 1
                            while char_idx < len(chars) and chars[char_idx] in (" ", "\n", "\r", "\t"):
                                char_idx += 1
                            if char_idx < len(chars):
                                seg_start = round(starts[char_idx] + cursor, 3)
                            else:
                                seg_start = round(cursor, 3)
                            timestamps_subtitles.append({"start": seg_start, "text": clean_text})
                            seg_stripped = re.sub(r'\s+', '', clean_text)
                            matched = 0
                            while char_idx < len(chars) and matched < len(seg_stripped):
                                if chars[char_idx] not in (" ", "\n", "\r", "\t") and is_spoken[char_idx]:
                                    matched += 1
                                char_idx += 1

                else:
                    word_align = timestamp_info.get("wordAlignment", {})
                    words = word_align.get("words", [])
                    word_starts = word_align.get("wordStartTimeSeconds", [])
                    word_ends = word_align.get("wordEndTimeSeconds", [])

                    if calc_text and words and word_starts:
                        calc_start = round(word_starts[0] + cursor, 3)
                        calculated_subtitles.append({"start": calc_start, "text": calc_text})
                    elif calc_text:
                        calculated_subtitles.append({"start": round(cursor, 3), "text": calc_text})

                    if words:
                        raw_timestamp_log.append({
                            "segment_text": part,
                            "offset": round(cursor, 3),
                            "words": words,
                            "word_start_times": word_starts,
                            "word_end_times": word_ends,
                        })

                        sub_segments = re.split(r'<break\s+time="[^"]*"\s*/>', part)
                        word_idx = 0
                        for seg in sub_segments:
                            clean_text = re.sub(r'\s+', ' ', seg).strip()
                            if not clean_text:
                                continue
                            seg_words = re.findall(r"[a-zA-Z']+", clean_text)
                            if not seg_words:
                                continue
                            first_word = seg_words[0].lower()
                            found = False
                            for wi in range(word_idx, len(words)):
                                align_word = re.sub(r'[^a-zA-Z\']', '', words[wi]).lower()
                                if align_word == first_word:
                                    seg_start = round(word_starts[wi] + cursor, 3)
                                    timestamps_subtitles.append({"start": seg_start, "text": clean_text})
                                    word_idx = wi + len(seg_words)
                                    found = True
                                    break
                            if not found:
                                timestamps_subtitles.append({"start": round(cursor, 3), "text": clean_text})
                                word_idx += len(seg_words)

            chunk_duration = len(voice_chunk) / 1000.0
            cursor += chunk_duration

    # End silence
    print(f"   - Adding {end_silence:.1f}s end silence")
    final_audio += AudioSegment.silent(duration=int(end_silence * 1000))

    # Mark end time on last subtitle of each type
    cursor += end_silence

    # Export MP3
    output_path = out / f"{meditation_id}.mp3"
    final_audio.export(str(output_path), format="mp3", bitrate="192k")
    print(f"   COMPLETED: {meditation_id}.mp3 saved to {out}")

    result = {"mp3": output_path}

    if timestamps:
        if timestamps_subtitles:
            timestamps_subtitles[-1]["end"] = round(cursor, 3)
        if calculated_subtitles:
            calculated_subtitles[-1]["end"] = round(cursor, 3)

        ts_path = out / f"{meditation_id}_timestamps.json"
        with open(ts_path, "w") as f:
            json.dump({"subtitles": timestamps_subtitles, "skip_points": skip_points}, f, indent=2)
        print(f"   Timestamp subtitles saved to: {ts_path}")

        calc_path = out / f"{meditation_id}_calculated.json"
        with open(calc_path, "w") as f:
            json.dump({"subtitles": calculated_subtitles, "skip_points": skip_points}, f, indent=2)
        print(f"   Calculated subtitles saved to: {calc_path}")

        log_path = out / f"{meditation_id}_session_log.md"
        with open(log_path, "a") as f:
            f.write(f"\n## {meditation_id} — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"Voice: {voice_id} | API: {api} | Speed: {voice_cfg['speed']}\n")
            f.write(f"Start silence: {start_silence:.3f}s | End silence: {end_silence:.3f}s\n\n")
            for entry in raw_timestamp_log:
                f.write(f"### Segment (offset {entry['offset']}s)\n")
                f.write(f"**Text:** {entry['segment_text'][:100]}...\n\n")
                if "words" in entry:
                    f.write("| Word | Start | End |\n|------|-------|-----|\n")
                    for i, word in enumerate(entry["words"]):
                        f.write(f"| {word} | {entry['word_start_times'][i]:.3f} | {entry['word_end_times'][i]:.3f} |\n")
                else:
                    f.write("| Char | Start | End |\n|------|-------|-----|\n")
                    for i, char in enumerate(entry["characters"]):
                        f.write(f"| `{char}` | {entry['character_start_times'][i]:.3f} | {entry['character_end_times'][i]:.3f} |\n")
                f.write("\n")
        print(f"   Raw timestamps appended to: {log_path}")

        result["timestamps"] = ts_path
        result["calculated"] = calc_path
        result["log"] = log_path

    return result


# --- SCRIPT DATA ---
SCRIPTS = {
    "U003": """Settle in where you are.
<break time="1.1s" />
You do not need to solve anything for the next few minutes.
<break time="1.3s" />
This practice is simple.
<break time="0.9s" />
Notice worry.
<break time="0.8s" />
Name it.
<break time="1.0s" />
Return.
[skip_point]
Choose one physical anchor now.
<break time="0.9s" />
Either the breath in the body, or the feeling of your feet.
[pause: 8]
Let the anchor be plain.
<break time="1.0s" />
Air moving.
<break time="0.9s" />
Or pressure and contact.
[pause: 12]
When worry appears, label it once.
<break time="0.7s" />
Worrying.
<break time="0.8s" />
Then come back to the breath, or back to the feet.
[pause: 16]
You do not need to argue with the thought.
<break time="1.2s" />
You do not need to follow it either.
<break time="1.0s" />
Just return to what is physically here.
[pause: 18]
Maybe the mind jumps to later today.
<break time="1.0s" />
Worrying.
<break time="0.7s" />
And back to one breath, or back to both feet.""",
}


if __name__ == "__main__":
    missing = []
    if not INWORLD_API_KEY:
        missing.append("INWORLD_API_KEY")
    if not ELEVENLABS_API_KEY:
        missing.append("ELEVENLABS_API_KEY")
    if missing:
        print(f"ERROR: Missing in .env: {', '.join(missing)}")
        exit(1)

    print("Voices:")
    for v, cfg in VOICES.items():
        print(f"  {v}: api={cfg['api']}, speed={cfg['speed']}")
    print(f"Output: {OUTPUT_DIR}")

    for voice_id in VOICES:
        for script_id, script_text in SCRIPTS.items():
            med_id = f"{script_id}_{voice_id}"
            try:
                generate_meditation(med_id, script_text, voice_id)
            except Exception as e:
                print(f"\n   ERROR with {med_id}: {e}")

    print(f"\nDone! Check {OUTPUT_DIR}/")
