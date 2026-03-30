# mindflow-tts — API Documentation

## Overview

`mindflow-tts` is an AWS Lambda that converts meditation scripts into audio (MP3). It supports 4 voices across 2 TTS providers, uploads to Cloudflare R2, and returns a public audio URL.

**Function name:** `mindflow-tts`
**Region:** `us-east-1`
**Invocation:** synchronous `boto3.invoke()`

---

## Request

```python
import boto3, json

lambda_client = boto3.client("lambda", region_name="us-east-1")
response = lambda_client.invoke(
    FunctionName="mindflow-tts",
    Payload=json.dumps({
        "session_id": "6d540bab-4ad8-4e75-a56c-a7d3e5637c11",
        "script": "Take a moment to settle in.\n<break time=\"1.2s\" />\nClose your eyes.\n[pause: 10]\nNow breathe gently.",
        "voice_id": "Graham",
        "title": "Sky-Like Mind Breath Observation",
        "timestamps": False,
    }),
)
result = json.loads(response["Payload"].read())
# result["audio_url"] or result["error"]
```

### Parameters

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `session_id` | string | **yes** | — | Unique identifier. Used as the output filename. |
| `script` | string | **yes** | — | Full meditation script as plain text with inline control tags. |
| `voice_id` | string | no | `"Graham"` | One of: `"Luna"`, `"Claire"`, `"Graham"`, `"Silas"`. Case-sensitive. |
| `title` | string | no | — | Session title. Not used by TTS, passed for logging only. |
| `timestamps` | boolean | no | `false` | When `true`, generates and returns subtitle JSON URLs. |

---

## Response

### Success (timestamps: false)

```json
{
  "audio_url": "https://audio.neurotypeapp.com/incraft_audio/{session_id}.mp3"
}
```

### Success (timestamps: true)

```json
{
  "audio_url": "https://audio.neurotypeapp.com/incraft_audio/{session_id}.mp3",
  "timestamps_url": "https://audio.neurotypeapp.com/incraft_audio/{session_id}_timestamps.json",
  "calculated_url": "https://audio.neurotypeapp.com/incraft_audio/{session_id}_calculated.json"
}
```

### Error

```json
{
  "error": "description of what went wrong"
}
```

Possible errors:
- `"missing session_id"`
- `"missing script"`
- `"unknown voice_id 'X', must be one of: Luna, Claire, Graham, Silas"`
- TTS provider or upload failure message

---

## Voices

| Voice | Provider | Speed | Description |
|-------|----------|-------|-------------|
| **Graham** | Inworld | 0.94 | Default voice |
| **Luna** | Inworld | 1.0 | Normal pace |
| **Claire** | Inworld | 0.9 | Slightly slower |
| **Silas** | ElevenLabs | 0.8 | Slowest, deep meditation tone |

---

## Script Format

The `script` field is a plain text string with three control tags:

### `[pause: N]` — Silent gap (seconds)

Long meditation pauses. N can be integer or decimal. **Not sent to TTS — costs nothing.**

```
Stay with the breath.
[pause: 30]
Now return your attention.
```

### `<break time="Xs" />` — Short SSML pause

Inline pause between sentences. Sent to TTS provider. Typically 0.7–1.5s.

```
Take a deep breath in.
<break time="1.2s" />
And slowly exhale.
```

### `[skip_point]` — Navigation marker

Records a timestamp for skip-ahead in the app. Produces no audio.

```
[pause: 12]
[skip_point]
Now notice any thoughts arriving.
```

### Full example

```
Settle in where you are.
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
[pause: 8]

[skip_point]

Choose one physical anchor now.
<break time="0.9s" />
Either the breath in the body, or the feeling of your feet.
[pause: 12]

When worry appears, label it once.
<break time="0.7s" />
Worrying.
<break time="0.8s" />
Then come back to the breath, or back to the feet.
[pause: 20]

Return to the breath.
```

---

## Automatic Preprocessing

The Lambda cleans up scripts automatically. Callers do **not** need to handle these.

1. **Malformed pause tags** — `<pause: 5>`, `(pause;5)`, `[pause:5>`, etc. are all normalized to `[PAUSE: N]`
2. **Break before skip_point** — If `[skip_point]` has no adjacent break or pause tag, a `<break time="1.0s" />` is inserted before it
3. **Consecutive break limiting** — Every 4th+ consecutive `<break>` tag within a segment is converted to `[pause:]` to prevent TTS speed issues. Counter resets at each `[pause:]` or `[skip_point]`

---

## Audio Output

- **Format:** MP3, 44100 Hz, 192 kbps
- **Padding:** 1–3s random silence at start, 1–2s at end
- **URL pattern:** `https://audio.neurotypeapp.com/incraft_audio/{session_id}.mp3`

---

## Timestamps (when timestamps: true)

### timestamps_url

Timed using the TTS provider's word/character alignment. Most accurate.

```json
{
  "subtitles": [
    {"start": 2.145, "text": "Settle in where you are."},
    {"start": 5.892, "text": "You do not need to solve anything."},
    {"start": 142.5, "end": 145.2, "text": "Last line of text."}
  ],
  "skip_points": [8.5, 45.2]
}
```

### calculated_url

One entry per TTS segment, timed from chunk durations. Simpler, less granular. Same JSON structure.

### Notes

- `start` values are seconds from audio start
- Only the last subtitle has an `end` field
- `skip_points` is an array of timestamps (seconds) where `[skip_point]` markers appeared
- Timestamps add no extra cost or processing time

---

## Timeout

- Lambda timeout: 300s (5 min)
- A ~10 min meditation typically takes 1–3 min to generate
- Callers should set at least a matching timeout for synchronous invokes

---

## IAM

The calling Lambda needs `lambda:InvokeFunction` for:
`arn:aws:lambda:us-east-1:202029085974:function:mindflow-tts`
