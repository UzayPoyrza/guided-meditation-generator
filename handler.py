"""AWS Lambda handler for mindflow-tts.

Invoked by mindflow-api Lambda via boto3.invoke() with payload:
{
    "session_id": "uuid-string",
    "title": "Session Title",
    "script": "Full meditation script text...",
    "voice_id": "Graham",        # optional, defaults to "Graham"
    "timestamps": false           # optional, defaults to false
}

Returns:
    {"audio_url": "https://audio.neurotypeapp.com/meditation_voices/incraft_audio/{session_id}.mp3"}
    or on failure:
    {"error": "description"}
"""

import os
import json
import boto3
from pathlib import Path

from tts_generate import generate_meditation, VOICES

# R2 config
R2_ENDPOINT = "https://ad354e56e3488dfc373c8da6d8a4a311.r2.cloudflarestorage.com"
R2_BUCKET = "neurotype-meditation-music"
R2_PREFIX = "incraft_audio"
PUBLIC_BASE_URL = "https://audio.neurotypeapp.com/incraft_audio"

TMP_DIR = Path("/tmp/tts")

s3 = boto3.client(
    "s3",
    endpoint_url=R2_ENDPOINT,
    aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
    region_name="auto",
)


def handler(event, context):
    # Parse payload (handle both direct dict and API Gateway string body)
    if isinstance(event, str):
        event = json.loads(event)
    body = json.loads(event["body"]) if "body" in event else event

    session_id = body.get("session_id")
    script = body.get("script")
    voice_id = body.get("voice_id", "Graham")
    timestamps = body.get("timestamps", False)

    if not session_id:
        return {"error": "missing session_id"}
    if not script:
        return {"error": "missing script"}
    if voice_id not in VOICES:
        return {"error": f"unknown voice_id '{voice_id}', must be one of: {', '.join(VOICES)}"}

    try:
        # Generate audio in /tmp
        out_dir = TMP_DIR / session_id
        out_dir.mkdir(parents=True, exist_ok=True)

        result = generate_meditation(
            meditation_id=session_id,
            script_text=script,
            voice_id=voice_id,
            output_dir=str(out_dir),
            timestamps=timestamps,
        )

        response = {}

        # Upload MP3
        mp3_key = f"{R2_PREFIX}/{session_id}.mp3"
        s3.upload_file(
            str(result["mp3"]),
            R2_BUCKET,
            mp3_key,
            ExtraArgs={"ContentType": "audio/mpeg"},
        )
        response["audio_url"] = f"{PUBLIC_BASE_URL}/{session_id}.mp3"

        # Upload timestamps if generated
        if timestamps and "timestamps" in result:
            ts_key = f"{R2_PREFIX}/{session_id}_timestamps.json"
            s3.upload_file(
                str(result["timestamps"]),
                R2_BUCKET,
                ts_key,
                ExtraArgs={"ContentType": "application/json"},
            )
            response["timestamps_url"] = f"{PUBLIC_BASE_URL}/{session_id}_timestamps.json"

            calc_key = f"{R2_PREFIX}/{session_id}_calculated.json"
            s3.upload_file(
                str(result["calculated"]),
                R2_BUCKET,
                calc_key,
                ExtraArgs={"ContentType": "application/json"},
            )
            response["calculated_url"] = f"{PUBLIC_BASE_URL}/{session_id}_calculated.json"

        # Cleanup /tmp
        for f in out_dir.iterdir():
            f.unlink()
        out_dir.rmdir()

        return response

    except Exception as e:
        return {"error": str(e)}
