import json
import glob
import random
import subprocess
import tempfile
import numpy as np
from pathlib import Path
from pydub import AudioSegment
from pedalboard import (
    Pedalboard,
    Compressor,
    Gain,
    HighpassFilter,
    LowShelfFilter,
    HighShelfFilter,
    PeakFilter,
    Limiter,
    load_plugin,
)

# --- CONFIGURATION ---
JSON_PATH = Path.home() / "Desktop" / "neurotype_meditations_150.json"
VOICE_DIR = Path.home() / "Desktop" / "meditation_audio"
MUSIC_DIR = Path.home() / "Desktop" / "trimmed_meditations"
FINAL_DIR = Path.home() / "Desktop" / "final_meditations"
STAGES_DIR = Path.home() / "Desktop" / "meditation_stages"

MUSIC_DUCK_DB = 3     # static duck: music sits this many dB below voice
SIDECHAIN_DUCK_DB = 6 # extra dB to duck music when voice is active
SIDECHAIN_CHUNK_MS = 50  # analysis window size
SIDECHAIN_THRESHOLD_DBFS = -50  # voice louder than this = "active"
FADE_OUT_MS = 8000
VALHALLA_ROOM_PATH = "/Library/Audio/Plug-Ins/Components/ValhallaRoomAU64.component"

# Meditations to process (add more IDs as needed)
MEDITATION_IDS = ["U012"]


def load_metadata():
    with open(JSON_PATH, "r") as f:
        data = json.load(f)
    return {m["id"]: m for m in data["meditations"]}


def find_music_file(audio_code):
    """Auto-map audio code like 'T16' to 'T16_15min.mp3' by globbing."""
    pattern = str(MUSIC_DIR / f"{audio_code}_*.mp3")
    matches = glob.glob(pattern)
    if not matches:
        raise FileNotFoundError(f"No music file found for pattern: {pattern}")
    return Path(matches[0])


def normalize_audio(audio, target_dbfs):
    change = target_dbfs - audio.dBFS
    return audio.apply_gain(change)


def sidechain_duck(music, voice, voice_offset_ms):
    """
    Dynamically duck music wherever voice is active.
    Works on the raw samples with a smoothed gain envelope to avoid clicks.
    """
    print(f"   - Sidechain ducking: -{SIDECHAIN_DUCK_DB}dB when voice active")

    # Convert music to numpy samples
    music_samples = np.array(music.get_array_of_samples(), dtype=np.float64)
    channels = music.channels
    sr = music.frame_rate
    chunk_frames = int(SIDECHAIN_CHUNK_MS / 1000 * sr)
    offset_frames = int(voice_offset_ms / 1000 * sr)
    total_frames = len(music_samples) // channels

    # Build per-frame gain reduction envelope from voice activity
    voice_samples = np.array(voice.get_array_of_samples(), dtype=np.float64)
    voice_channels = voice.channels
    voice_frames = len(voice_samples) // voice_channels

    # Compute RMS per chunk for the voice to detect activity
    duck_ratio = 10 ** (-SIDECHAIN_DUCK_DB / 20)  # e.g. 6dB -> 0.5
    gain_envelope = np.ones(total_frames, dtype=np.float64)

    for chunk_start in range(0, total_frames, chunk_frames):
        chunk_end = min(chunk_start + chunk_frames, total_frames)
        voice_start = chunk_start - offset_frames
        voice_end = chunk_end - offset_frames

        if voice_start < voice_frames and voice_end > 0:
            vs = max(voice_start, 0)
            ve = min(voice_end, voice_frames)
            voice_slice = voice_samples[vs * voice_channels:ve * voice_channels]
            if len(voice_slice) > 0:
                rms = np.sqrt(np.mean(voice_slice ** 2))
                max_val = 2 ** (music.sample_width * 8 - 1)
                rms_dbfs = 20 * np.log10(rms / max_val + 1e-10)
                if rms_dbfs > SIDECHAIN_THRESHOLD_DBFS:
                    gain_envelope[chunk_start:chunk_end] = duck_ratio

    # Smooth the envelope with a rolling window to prevent clicks
    smooth_ms = 150  # attack/release smoothing
    smooth_frames = int(smooth_ms / 1000 * sr)
    if smooth_frames > 1:
        kernel = np.ones(smooth_frames) / smooth_frames
        gain_envelope = np.convolve(gain_envelope, kernel, mode='same')

    # Apply gain envelope to music samples
    if channels == 2:
        gain_stereo = np.repeat(gain_envelope[:total_frames], 2)
        music_samples[:len(gain_stereo)] *= gain_stereo[:len(music_samples)]
    else:
        music_samples[:total_frames] *= gain_envelope[:total_frames]

    music_samples = np.clip(music_samples,
                            -(2 ** (music.sample_width * 8 - 1)),
                            (2 ** (music.sample_width * 8 - 1)) - 1)
    music_samples = music_samples.astype(
        np.int16 if music.sample_width == 2 else np.int32
    )

    return music._spawn(music_samples.tobytes())


def apply_valhalla_room(audio_segment):
    """
    Run voice through Valhalla Room AU plugin for subtle room reverb.
    Low mix keeps the voice clean and upfront.
    Comment out the call to this function to skip reverb.
    """
    print("   - Applying Valhalla Room reverb")
    vr = load_plugin(VALHALLA_ROOM_PATH)

    # Matched from Logic screenshot — Large Room, Default preset with custom mix/decay
    vr.type = 0.0833333       # Large Room
    vr.mix = 0.033            # 3.3%
    vr.predelay = 0.02        # 10.0 ms
    vr.decay = 0.025          # ~2.00 s (calibrated via impulse response)
    vr.locut = 0.0            # 0 Hz
    vr.hicut = 0.530201       # 8000 Hz
    vr.latemoddepth = 0.5     # Depth 50%
    # Early tab
    vr.earlysize = 0.029029   # 30.0 ms
    vr.earlycross = 0.1       # 0.10
    vr.earlymodrate = 0.0909091  # 0.50 Hz
    vr.earlymoddepth = 0.0   # 0.00
    vr.earlysend = 0.0        # 0.00
    vr.diffusion = 1.0        # 1.00
    vr.space = 0.0            # 0.0%

    # Valhalla Room requires stereo — convert mono to stereo if needed
    was_mono = audio_segment.channels == 1
    if was_mono:
        audio_segment = audio_segment.set_channels(2)

    samples = np.array(audio_segment.get_array_of_samples(), dtype=np.float32)
    samples = samples.reshape((-1, 2)).T
    samples = samples / (2 ** (audio_segment.sample_width * 8 - 1))

    processed = vr(samples, audio_segment.frame_rate)

    processed_int = np.clip(
        processed * (2 ** (audio_segment.sample_width * 8 - 1)),
        -(2 ** (audio_segment.sample_width * 8 - 1)),
        (2 ** (audio_segment.sample_width * 8 - 1)) - 1,
    )
    processed_int = processed_int.T.flatten()
    processed_int = processed_int.astype(
        np.int16 if audio_segment.sample_width == 2 else np.int32
    )

    return audio_segment._spawn(processed_int.tobytes())


def master_audio(input_path, output_path, target_lufs=-16.0, true_peak_dbfs=-1.0):
    """
    Mastering chain inspired by Logic's Mastering Assistant (Transparent).
    - High-pass ~40Hz (sub-rumble cut)
    - Gentle low-mid warmth boost
    - Upper-mid dip (reduce harshness)
    - High shelf air
    - Light transparent compression
    - True peak limiter at -1.0 dB
    - Loudness normalization to target LUFS via ffmpeg loudnorm
    """
    print("   - Mastering: EQ + compression + limiter")
    audio = AudioSegment.from_file(str(input_path))
    samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
    if audio.channels == 2:
        samples = samples.reshape((-1, 2)).T
    else:
        samples = samples.reshape((1, -1))
    samples = samples / (2 ** (audio.sample_width * 8 - 1))

    board = Pedalboard([
        HighpassFilter(cutoff_frequency_hz=40),
        LowShelfFilter(cutoff_frequency_hz=150, gain_db=1.5),
        PeakFilter(cutoff_frequency_hz=2500, gain_db=-1.5, q=0.8),
        HighShelfFilter(cutoff_frequency_hz=8000, gain_db=1.0),
        Compressor(threshold_db=-20, ratio=2.0, attack_ms=30, release_ms=200),
        Gain(gain_db=1.0),
        Limiter(threshold_db=true_peak_dbfs),
    ])

    processed = board(samples, audio.frame_rate)

    # Convert back to pydub for intermediate export
    processed_int = np.clip(processed * (2 ** (audio.sample_width * 8 - 1)),
                            -(2 ** (audio.sample_width * 8 - 1)),
                            (2 ** (audio.sample_width * 8 - 1)) - 1)
    if audio.channels == 2:
        processed_int = processed_int.T.flatten()
    else:
        processed_int = processed_int.flatten()
    processed_int = processed_int.astype(np.int16 if audio.sample_width == 2 else np.int32)

    mastered = audio._spawn(processed_int.tobytes())

    # Loudness normalization to target LUFS via ffmpeg loudnorm (two-pass)
    print(f"   - Mastering: loudness normalization to {target_lufs} LUFS")
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_wav = tmp.name
    mastered.export(tmp_wav, format="wav")

    cmd = [
        "ffmpeg", "-y", "-i", tmp_wav,
        "-af", f"loudnorm=I={target_lufs}:TP={true_peak_dbfs}:LRA=11",
        "-ar", str(audio.frame_rate),
        str(output_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    Path(tmp_wav).unlink()
    print(f"   - Mastering complete: {output_path}")


def mix_meditation(meditation_id, metadata):
    entry = metadata.get(meditation_id)
    if not entry:
        print(f"Meditation {meditation_id} not found in metadata.")
        return

    audio_code = entry["audio"]
    print(f"\n--- Mixing {meditation_id} (music: {audio_code}) ---")

    # Paths
    voice_path = VOICE_DIR / f"{meditation_id}.mp3"
    music_path = find_music_file(audio_code)
    stage_dir = STAGES_DIR / meditation_id
    final_path = FINAL_DIR / f"{meditation_id}.mp3"

    # Create output dirs
    stage_dir.mkdir(parents=True, exist_ok=True)
    FINAL_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load raw voice (no normalization — mastering handles levels)
    voice = AudioSegment.from_file(str(voice_path))
    print(f"   - Loaded voice: {len(voice)/1000:.1f}s, {voice.dBFS:.1f} dBFS")

    # 2. Apply Valhalla Room reverb — comment out to skip
    voice_reverbed = apply_valhalla_room(voice)
    reverb_path = stage_dir / f"{meditation_id}_1_reverb.mp3"
    voice_reverbed.export(str(reverb_path), format="mp3", bitrate="192k")
    print(f"   - Saved: {reverb_path}")

    # 3. Mix voice + music
    voice_offset_ms = int(random.uniform(2, 7) * 1000)
    voice_duration_ms = len(voice_reverbed)
    total_duration_ms = voice_duration_ms + voice_offset_ms + FADE_OUT_MS

    print(f"   - Voice offset: {voice_offset_ms / 1000:.1f}s")
    print(f"   - Total duration: {total_duration_ms / 1000:.1f}s")

    # Load and prepare music
    music = AudioSegment.from_file(str(music_path))
    if len(music) < total_duration_ms:
        repeats = (total_duration_ms // len(music)) + 1
        music = music * repeats
    music = music[:total_duration_ms]
    music = music.fade_out(FADE_OUT_MS)

    # Static duck + sidechain: music drops extra when voice is playing
    music_ducked = music.apply_gain(-MUSIC_DUCK_DB)
    music_ducked = sidechain_duck(music_ducked, voice_reverbed, voice_offset_ms)

    # Overlay voice onto ducked music
    mixed = music_ducked.overlay(voice_reverbed, position=voice_offset_ms)
    mix_path = stage_dir / f"{meditation_id}_2_mixed.mp3"
    mixed.export(str(mix_path), format="mp3", bitrate="192k")
    print(f"   - Saved: {mix_path}")

    # 4. Mastering pass — comment out to skip
    mastered_path = stage_dir / f"{meditation_id}_3_mastered.mp3"
    master_audio(mix_path, mastered_path)

    # 5. Copy mastered version to final output
    mastered = AudioSegment.from_file(str(mastered_path))
    mastered.export(str(final_path), format="mp3", bitrate="192k")
    print(f"   - Saved final: {final_path}")


if __name__ == "__main__":
    metadata = load_metadata()
    for mid in MEDITATION_IDS:
        mix_meditation(mid, metadata)
    print("\nAll meditations mixed.")
