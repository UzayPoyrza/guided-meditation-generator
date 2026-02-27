# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python script that batch-generates meditation audio files using the ElevenLabs TTS API. Each meditation script contains spoken text interspersed with `[PAUSE: N]` markers (N = seconds of silence). The script splits on these markers, voices each text segment via ElevenLabs, inserts silent audio gaps, and concatenates everything into a single MP3 per meditation.

## Running

```bash
# Activate the virtual environment
source .venv/bin/activate

# Run the meditation generator
python example.py
```

Output MP3s are saved to `~/Desktop/meditation_audio/`.

## Dependencies

- Python 3.10 (`.venv` already set up, no requirements.txt — packages installed directly into venv)
- `elevenlabs` (v2.33.1) — TTS API client
- `pydub` — audio concatenation and silence generation
- `pydub` requires `ffmpeg` installed on the system (`brew install ffmpeg` on Mac)

## Architecture

Single-file project (`example.py`):

- **`generate_meditation(meditation_id, script_text)`** — Core function. Splits script on `[PAUSE: N]` regex, iterates parts: text segments are sent to ElevenLabs `text_to_speech.convert()`, pause markers become `AudioSegment.silent()`. Chunks are concatenated and exported as MP3.
- **`meditations_to_process`** — List of dicts with `id` and `script` keys. Each entry is one meditation to generate.
- Uses ElevenLabs `eleven_multilingual_v2` model with voice settings tuned for meditation (high stability, slow speed 0.8).
- Temporary chunk files (`temp_chunk.mp3`) are written and deleted during processing.

## Key Details

- The API key is hardcoded in `example.py` (there is also a `.env` file, but the script reads from the hardcoded constant, not from `.env`).
- Voice ID `5MzdXfNI3TSWsCPwZFrB` is configured at the top of the file.
- Output format: `mp3_44100_128`, exported at 192k bitrate.
