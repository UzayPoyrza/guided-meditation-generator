# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Meditation audio production pipeline: voice generation (ElevenLabs TTS), music preparation, Logic Pro mastering round-trips, and final mixing.

## Running

```bash
source .venv/bin/activate

# Batch voice generation (primary workflow)
python run_batch.py ~/Desktop/batches/batch1
python run_batch_f.py ~/Desktop/batches/batch1 --first-only   # _f voice variant, single session test
python run_batch_f.py ~/Desktop/batches/batch1 --limit 5      # first N sessions only

# Standalone voice generation (for scripts in meditations_to_process list)
python generate_voice.py
python generate_voice.py --test "your script text here"

# Music prep
./trim_music.sh /path/to/long/music/files

# Final mix (voice + music)
python mix_meditation.py
```

## Dependencies

- Python 3.10 (`.venv` already set up, no requirements.txt — packages installed directly into venv)
- `elevenlabs` (v2.33.1) — TTS API client
- `pydub` — audio concatenation and silence generation
- `pedalboard` — audio effects (compressor, EQ, limiter) used in mixing
- `numpy` — audio array manipulation in mixing
- `ffmpeg` required on system (`brew install ffmpeg`)

## Architecture

### Voice Generation — `generate_voice.py`

- **`generate_meditation(meditation_id, script_text, output_dir=None)`** — Core function. Splits script on `[PAUSE: N]` regex, voices text segments via ElevenLabs `text_to_speech.convert_with_timestamps()`, inserts `AudioSegment.silent()` for pauses, concatenates into MP3. Also generates two subtitle JSONs (ElevenLabs timestamps + calculated) and a session log.
- Limits consecutive `<break>` tags: every 4th+ consecutive break is converted to `[pause:]` to prevent TTS speed issues.
- `[skip_point]` markers record timestamps for skip navigation but produce no audio.
- Uses `eleven_multilingual_v2` model with voice settings tuned for meditation (stability=0.95, speed=0.8).
- Default voice ID `5MzdXfNI3TSWsCPwZFrB` is configured at the top; `run_batch_f.py` overrides this for the female voice variant.

### Batch Processing — `run_batch.py` / `run_batch_f.py`

- Reads from batch folders at `~/Desktop/batches/batch{N}/` containing:
  - `sessions_*.json` — list of `{session_id, title}` dicts
  - `final_session_batch_*.txt` — all scripts concatenated, split by `U### — Title` headers
- Output goes to `~/Desktop/overall_audio_batch/batch_{first_session_id}/` (or `batch_{id}_f/` for female variant)
- Each session gets: `{id}.mp3`, `{id}_timestamps.json` at batch root; `backup_{id}/` subfolder with calculated subtitles and session log
- Skips sessions where the MP3 already exists; stops after 3 consecutive errors
- `run_batch_f.py` appends `_f` to all session IDs/filenames and uses an alternate voice ID

### Music Prep — `trim_music.sh`

- Trims MP3s to 15 minutes, loudness-normalizes to -16 LUFS / -1 dBTP
- Outputs to `~/Desktop/trimmed_meditations/<name>_15min.mp3`

### Final Mix — `mix_meditation.py`

- Maps meditation→music via `~/Desktop/neurotype_meditations_150.json`
- Normalizes voice loudness, applies Valhalla Room reverb (AU plugin), sidechain-ducks music under voice
- Exports to `~/Desktop/final_meditations/{id}.mp3`

### Logic Pro Round-Trip Tools

- **`concat_music.py`** — Concatenates all music tracks from `~/Desktop/formatted_music/` into a single CAF for batch mastering in Logic Pro, then splits back after processing. Uses 5s silence gaps between tracks.
- **`bundle_roundtrip.py`** — Groups voice batches (~30 files per bundle) into concatenated WAV files for Logic Pro round-trip processing, then splits back.

### QA Pipeline

- **`extract_pause_ledger.py`** — Parses script files to extract pause events (>= 4s) with surrounding speech context. Outputs `sessions.json` and `pause_ledger.json`.
- **`run_merge.py`** — Merges pause reports and full QA reports into consolidated severity-graded reports.

## Key Details

- API key loaded from `.env` via `python-dotenv`.
- Output format: `mp3_44100_128`, exported at 192k bitrate.
- Batch input folders live at `~/Desktop/batches/batch{1-21}/`.
- 21 batches total have been processed with the default (male) voice.
