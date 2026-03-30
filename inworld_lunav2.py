#!/usr/bin/env python3
"""One-off: Luna v2 — temp 0.9, speed 1.0, with ensure_break_before_skip."""

import os
import re
import base64
import requests
from pathlib import Path
from dotenv import load_dotenv
from pydub import AudioSegment

load_dotenv()

API_KEY = os.getenv("INWORLD_API_KEY")
ENDPOINT = "https://api.inworld.ai/tts/v1/voice"
MODEL_ID = "inworld-tts-1.5-max"
SPEAKING_RATE = 0.94
TEMPERATURE = 1.0
VOICE_IDS = ["Graham"]
OUTPUT_DIR = Path.home() / "Desktop" / "inworld_test"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SCRIPT = """Settle in where you are.
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
And back to one breath, or back to both feet."""


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


def synthesize_segment(text, voice_id):
    headers = {
        "Authorization": f"Basic {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "voiceId": voice_id,
        "modelId": MODEL_ID,
        "audioConfig": {
            "audioEncoding": "MP3",
            "sampleRateHertz": 44100,
            "bitRate": 128000,
            "speakingRate": SPEAKING_RATE,
        },
        "temperature": TEMPERATURE,
    }
    response = requests.post(ENDPOINT, json=payload, headers=headers)
    response.raise_for_status()
    return base64.b64decode(response.json()["audioContent"])


if __name__ == "__main__":
    if not API_KEY:
        print("ERROR: INWORLD_API_KEY not found in .env")
        exit(1)

    script = ensure_break_before_skip(SCRIPT)

    for voice_id in VOICE_IDS:
        print(f"\n--- Voice: {voice_id} | Speed: {SPEAKING_RATE} | Temp: {TEMPERATURE} ---")

        parts = re.split(
            r'(\[PAUSE:\s*\d+(?:\.\d+)?\]|\[skip_point\])',
            script,
            flags=re.IGNORECASE,
        )

        final_audio = AudioSegment.empty()

        for part in parts:
            part = part.strip()
            if not part:
                continue
            if part.upper() == "[SKIP_POINT]":
                print("   - Skip point")
                continue
            if re.match(r'\[PAUSE:\s*\d+(?:\.\d+)?\]', part, flags=re.IGNORECASE):
                seconds = float(re.search(r'\d+(?:\.\d+)?', part).group())
                print(f"   - Adding {seconds}s silence")
                final_audio += AudioSegment.silent(duration=int(seconds * 1000))
            else:
                print(f"   - Voicing: '{part[:50]}...'")
                audio_bytes = synthesize_segment(part, voice_id)
                temp_file = f"_temp_inworld_{voice_id}.mp3"
                with open(temp_file, "wb") as f:
                    f.write(audio_bytes)
                final_audio += AudioSegment.from_file(temp_file, format="mp3")
                os.remove(temp_file)

        suffix = "_v4" if voice_id == "Graham" else ""
        output_path = OUTPUT_DIR / f"U003_{voice_id}{suffix}.mp3"
        final_audio.export(str(output_path), format="mp3", bitrate="192k")
        print(f"   -> Saved: {output_path}")
