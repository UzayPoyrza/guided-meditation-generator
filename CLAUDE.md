# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Three-part meditation production pipeline:

1. **`generate_voice.py`** — Batch-generates voice-only meditation audio via the ElevenLabs TTS API. Each meditation script contains spoken text interspersed with `[PAUSE: N]` markers (N = seconds of silence). The script splits on these markers, voices each text segment, inserts silent audio gaps, and concatenates everything into a single MP3 per meditation.
2. **`trim_music.sh`** — Trims long music files to 15 minutes and loudness-normalizes them to -16 LUFS. Outputs to `~/Desktop/trimmed_meditations/` with `_15min.mp3` suffix. Must be run before `mix_meditation.py`.
3. **`mix_meditation.py`** — Combines voice audio with background music tracks. Reads a JSON metadata file to map each meditation to its music track, normalizes voice loudness, applies room reverb, and mixes voice (forward) over music (ducked) with a fade-out ending.

## Running

```bash
# Activate the virtual environment
source .venv/bin/activate

# 1. Generate voice audio
python generate_voice.py

# 2. Trim and normalize music files
./trim_music.sh /path/to/long/music/files

# 3. Mix voice + music
python mix_meditation.py
```

Output MP3s are saved to `~/Desktop/meditation_audio/` (voice), `~/Desktop/trimmed_meditations/` (trimmed music), and `~/Desktop/final_meditations/` (final mix).

## Dependencies

- Python 3.10 (`.venv` already set up, no requirements.txt — packages installed directly into venv)
- `elevenlabs` (v2.33.1) — TTS API client
- `pydub` — audio concatenation and silence generation
- `pydub` requires `ffmpeg` installed on the system (`brew install ffmpeg` on Mac)

## Architecture

### `generate_voice.py`

- **`generate_meditation(meditation_id, script_text)`** — Core function. Splits script on `[PAUSE: N]` regex, iterates parts: text segments are sent to ElevenLabs `text_to_speech.convert()`, pause markers become `AudioSegment.silent()`. Chunks are concatenated and exported as MP3.
- **`meditations_to_process`** — List of dicts with `id` and `script` keys. Each entry is one meditation to generate.
- Uses ElevenLabs `eleven_multilingual_v2` model with voice settings tuned for meditation (high stability, slow speed 0.8).
- Temporary chunk files (`temp_chunk.mp3`) are written and deleted during processing.

### `trim_music.sh`

- Takes an input directory of long MP3 files as argument
- Trims each file to 15 minutes (`ffmpeg -t 900 -c copy`)
- Loudness-normalizes to -16 LUFS / -1 dBTP via ffmpeg `loudnorm` filter
- Outputs to `~/Desktop/trimmed_meditations/<name>_15min.mp3`
- Skips files that already exist in the output directory

### `mix_meditation.py`

- Loads `~/Desktop/neurotype_meditations_150.json` for meditation→music mapping
- Looks up meditation by ID to get the `audio` field (e.g. `T16`), auto-maps to `~/Desktop/trimmed_meditations/T16_15min.mp3` by globbing
- Normalizes voice audio to target dBFS, saves to `~/Desktop/normalized_meditation_audio/`
- Applies subtle room reverb via ffmpeg `aecho` subprocess
- Mixes voice over music: voice starts after a random 2–7s delay, music fades out over 8s at the end
- Exports to `~/Desktop/final_meditations/{id}.mp3`

## Key Details

- The API key is read from `.env` via `python-dotenv` in `generate_voice.py`.
- Voice ID `5MzdXfNI3TSWsCPwZFrB` is configured at the top of `generate_voice.py`.
- Output format: `mp3_44100_128`, exported at 192k bitrate.
