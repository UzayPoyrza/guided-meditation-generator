import os
import re
from pathlib import Path
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings
from pydub import AudioSegment

load_dotenv()

# --- CONFIGURATION ---
API_KEY = os.getenv("ELEVENLABS_API_KEY")

# 2. Replace with your preferred Voice ID (Found in ElevenLabs Voice Lab)
VOICE_ID = "5MzdXfNI3TSWsCPwZFrB" 

# This creates the path to your Desktop automatically (works on Mac)
DESKTOP_PATH = Path.home() / "Desktop" / "meditation_audio"

# Create the folder if it doesn't exist
DESKTOP_PATH.mkdir(parents=True, exist_ok=True)

client = ElevenLabs(api_key=API_KEY)

def generate_meditation(meditation_id, script_text):
    """Generates a single meditation file and saves it to the Desktop folder."""
    
    output_filename = f"{meditation_id}.mp3"
    final_output_path = DESKTOP_PATH / output_filename
    
    final_audio = AudioSegment.empty()
    parts = re.split(r'(\[PAUSE: \d+\])', script_text)
    
    print(f"\n--- Processing {meditation_id} ---")

    for part in parts:
        part = part.strip()
        if not part:
            continue
            
        if part.startswith("[PAUSE:"):
            seconds = int(re.search(r'\d+', part).group())
            print(f"   - Adding {seconds}s silence")
            silence = AudioSegment.silent(duration=seconds * 1000)
            final_audio += silence
            
        else:
            print(f"   - Voicing segment: '{part[:30]}...'")
            audio_generator = client.text_to_speech.convert(
                voice_id=VOICE_ID,
                text=part,
                model_id="eleven_multilingual_v2",
                output_format="mp3_44100_128",
                voice_settings=VoiceSettings(
                    speed=0.8,
                    stability=0.95,          # Increased for meditation consistency
                    similarity_boost=0.95,   # High clarity
                    style=0.0,               # Neutral style for calming effect
                    use_speaker_boost=True
                )
            )
            
            temp_file = "temp_chunk.mp3"
            with open(temp_file, "wb") as f:
                for chunk in audio_generator:
                    f.write(chunk)
            
            voice_chunk = AudioSegment.from_file(temp_file, format="mp3")
            final_audio += voice_chunk
            os.remove(temp_file)

    # Export to the Desktop folder
    final_audio.export(str(final_output_path), format="mp3", bitrate="192k")
    print(f"✅ COMPLETED: {output_filename} saved to Desktop/meditation_audio")

# --- YOUR DATA LIST ---
# Add your 120 meditations here following this format
meditations_to_process = [
{
"id": "U012",
"script": """Settle into a comfortable seat. [PAUSE: 2]
Let your shoulders rest. [PAUSE: 2]
Feel the breath moving in the belly. [PAUSE: 2]
Let the inhale arrive with ease. [PAUSE: 2]
Let the exhale soften and lengthen. [PAUSE: 3]

Let your eyes be open in a soft way. [PAUSE: 2]
Pick a simple spot in front of you. [PAUSE: 2]
Let the focus soften as if you are looking through the room. [PAUSE: 2]
Include the edges of your visual field. [PAUSE: 2]
Notice light and shape at the sides. [PAUSE: 3]

Stay with the breath as you look wide. [PAUSE: 2]
Inhale gently. [PAUSE: 2]
Exhale a little longer. [PAUSE: 2]
Let the body sense space around you. [PAUSE: 2]
That is normal if the mind wants to narrow. [PAUSE: 4]

Let the gaze stay soft. [PAUSE: 2]
Feel the exhale in the ribs. [PAUSE: 2]
Say a quiet phrase on the out breath. [PAUSE: 2]
Nothing is chasing me. [PAUSE: 3]
Return to wide view and slow breathing. [PAUSE: 4]

Stay with this quietly.
[PAUSE: 45]

Notice the edges of the room. [PAUSE: 2]
Notice the breath leaving. [PAUSE: 2]
Let the exhale be slow and steady. [PAUSE: 3]

Rest in silence.
[PAUSE: 60]

Wide view. [PAUSE: 1]
Slow breath. [PAUSE: 2]
Nothing is chasing me. [PAUSE: 3]

Stay with this quietly.
[PAUSE: 45]

Bring attention back to the breath. [PAUSE: 2]
Feel your feet on the floor. [PAUSE: 2]
Take one gentle breath in. [PAUSE: 2]
Let it out slowly. [PAUSE: 2]
Notice the whole body sitting here. [PAUSE: 2]
Notice the room around you. [PAUSE: 2]
Eyes open when ready. [PAUSE: 2]
"""
},
{
"id": "U013",
"script": """Sit or stand in a steady way. [PAUSE: 2]
Feel your feet on the floor. [PAUSE: 2]
Let the breath move naturally. [PAUSE: 2]
Let your eyes rest on the room. [PAUSE: 3]

This practice uses seeing and feeling and hearing. [PAUSE: 2]
Feet stay as your anchor. [PAUSE: 2]
Return to your feet between each step. [PAUSE: 3]

Look around with a soft gaze. [PAUSE: 2]
Name three things you can see. [PAUSE: 10]
Return to your feet. [PAUSE: 2]
Name two contact points you can feel. [PAUSE: 10]
Return to your feet. [PAUSE: 2]
Name one sound you can hear. [PAUSE: 10]
Feel your feet again. [PAUSE: 3]

Stay with this quietly.
[PAUSE: 20]

Begin the second round with ease. [PAUSE: 2]
Name three things you can see. [PAUSE: 8]
Return to your feet. [PAUSE: 2]
Name two contact points you can feel. [PAUSE: 8]
Return to your feet. [PAUSE: 2]
Name one sound you can hear. [PAUSE: 8]
Let the breath slow a little. [PAUSE: 3]

Rest in silence.
[PAUSE: 20]

Feel the whole body standing or sitting. [PAUSE: 2]
Take one gentle breath in. [PAUSE: 2]
Let it out slowly. [PAUSE: 2]
Notice the room around you. [PAUSE: 2]
Eyes open when ready. [PAUSE: 2]
"""
},
{
"id": "U014",
"script": """Find a comfortable seat. [PAUSE: 2]
Let the shoulders drop. [PAUSE: 2]
Feel the breath at the nostrils or the belly. [PAUSE: 2]
Choose one place where the breath is clear. [PAUSE: 2]
Stay with that place as your anchor. [PAUSE: 3]

Thoughts will appear. [PAUSE: 2]
That is normal. [PAUSE: 2]
When a thought shows up. Give it a simple category. [PAUSE: 2]
Worry. [PAUSE: 1]
Planning. [PAUSE: 1]
Memory. [PAUSE: 3]

Keep the label gentle and brief. [PAUSE: 2]
Label the thought.
Step down to the breath. [PAUSE: 2]
Feel one inhale. [PAUSE: 2]
Feel one exhale. [PAUSE: 3]

Notice what the mind offers next. [PAUSE: 2]
Choose the best label. [PAUSE: 2]
Label it worry or planning or memory.
Return to the breath. [PAUSE: 2]
Stay with the breath for a few moments. [PAUSE: 4]

Rest in silence.
[PAUSE: 60]

Thought appears. [PAUSE: 2]
Label it.
Step down to the breath. [PAUSE: 2]
Feel the air moving out. [PAUSE: 2]
Let the exhale soften. [PAUSE: 3]

Stay with this quietly.
[PAUSE: 90]

Worry thoughts may show up. [PAUSE: 2]
Planning thoughts may show up. [PAUSE: 2]
Memory thoughts may show up. [PAUSE: 2]
Whatever shows up is fine. [PAUSE: 2]
Label it and step down.
Feel the breath. [PAUSE: 3]

Rest in silence.
[PAUSE: 90]

Notice where the breath is most vivid. [PAUSE: 2]
Notice the breath at the nostrils or chest or belly. [PAUSE: 2]
Pick one place and stay. [PAUSE: 2]
A thought appears. Label it.
Back to the breath. [PAUSE: 3]

Stay with this quietly.
[PAUSE: 90]

Let the labels get quieter. [PAUSE: 2]
Let the breath be the main sound. [PAUSE: 2]
If you notice a thought. Use one label.
Return to the breath. [PAUSE: 3]

Rest in silence.
[PAUSE: 75]

Feel three natural breaths. [PAUSE: 2]
Feel the body sitting here. [PAUSE: 2]
Notice the room around you. [PAUSE: 2]
Take one gentle breath in. [PAUSE: 2]
Let it out slowly. [PAUSE: 2]
Eyes open when ready. [PAUSE: 2]
"""
},
{
"id": "U015",
"script": """Lie down or sit comfortably. [PAUSE: 2]
Let your face soften. [PAUSE: 2]
Feel the breath moving out. [PAUSE: 2]
Exhale is your anchor today. [PAUSE: 2]
Let the out breath be easy and long. [PAUSE: 3]

Counting happens only on the exhale. [PAUSE: 2]
Inhale without counting. [PAUSE: 2]
Exhale and count down from ten. [PAUSE: 2]
If you lose track. Return to ten with kindness. [PAUSE: 3]

Inhale gently. [PAUSE: 2]
Exhale and count ten. [PAUSE: 5]
Inhale gently. [PAUSE: 2]
Exhale and count nine. [PAUSE: 5]
Inhale gently. [PAUSE: 2]
Exhale and count eight. [PAUSE: 5]
Inhale gently. [PAUSE: 2]
Exhale and count seven. [PAUSE: 5]
Inhale gently. [PAUSE: 2]
Exhale and count six. [PAUSE: 5]
Inhale gently. [PAUSE: 2]
Exhale and count five. [PAUSE: 5]
Inhale gently. [PAUSE: 2]
Exhale and count four. [PAUSE: 5]
Inhale gently. [PAUSE: 2]
Exhale and count three. [PAUSE: 5]
Inhale gently. [PAUSE: 2]
Exhale and count two. [PAUSE: 5]
Inhale gently. [PAUSE: 2]
Exhale and count one. [PAUSE: 6]

Let the counting restart at ten. [PAUSE: 2]
Stay close to the feeling of breathing out. [PAUSE: 2]
Let the shoulders soften on the exhale. [PAUSE: 4]

Continue counting on your own.
I will be quiet for a while.
[PAUSE: 75]

If you forget the number. That is normal. [PAUSE: 2]
Return to ten gently. [PAUSE: 2]
Exhale is the anchor. [PAUSE: 3]

Stay with this quietly.
[PAUSE: 60]

Begin at ten on the next exhale. [PAUSE: 2]
Let each number ride on the out breath. [PAUSE: 2]
Keep the body soft. [PAUSE: 4]

Rest in silence.
[PAUSE: 75]

Let the counting fade away. [PAUSE: 2]
Take one easy breath in. [PAUSE: 2]
Let it out slowly. [PAUSE: 2]
Feel the body resting. [PAUSE: 2]
Notice the room around you. [PAUSE: 2]
Eyes open when ready. [PAUSE: 2]
"""
},
{
"id": "U017",
"script": """Sit in a comfortable way. [PAUSE: 2]
Let your hands rest in your lap. [PAUSE: 2]
Hands are your anchor today. [PAUSE: 2]
Let the breath be even and calm. [PAUSE: 3]

Touch thumb to each fingertip slowly. [PAUSE: 2]
Index to middle to ring to pinky. [PAUSE: 2]
Move with a steady pace. [PAUSE: 2]
Restart when you notice the mind looping. [PAUSE: 3]

Touch thumb to index finger.
Feel the contact. [PAUSE: 2]
Touch thumb to middle finger.
Feel the contact. [PAUSE: 2]
Touch thumb to ring finger.
Feel the contact. [PAUSE: 2]
Touch thumb to pinky.
Feel the contact. [PAUSE: 3]

Keep moving through the fingertips with the breath. [PAUSE: 2]
Smooth and steady is enough. [PAUSE: 4]

Stay with this quietly.
[PAUSE: 45]

Notice the touch. [PAUSE: 2]
Notice the breath. [PAUSE: 2]
Restart at index when you drift. [PAUSE: 3]

Rest in silence.
[PAUSE: 30]

Let the hands come to rest. [PAUSE: 2]
Take one gentle breath in. [PAUSE: 2]
Let it out slowly. [PAUSE: 2]
Feel the body sitting here. [PAUSE: 2]
Notice the room around you. [PAUSE: 2]
Eyes open when ready. [PAUSE: 2]
"""
},
{
"id": "U018",
"script": """Settle into a comfortable position. [PAUSE: 2]
Let your hands rest. [PAUSE: 2]
Listen to the wave like audio. [PAUSE: 2]
Let the breath stay natural. [PAUSE: 2]
Breath is your anchor today. [PAUSE: 3]

Notice the rise in the sound. [PAUSE: 2]
Let the inhale rise with it. [PAUSE: 2]
Notice the fall in the sound. [PAUSE: 2]
Let the exhale fall with it. [PAUSE: 3]

Let the breath stay light. [PAUSE: 2]
Let the timing come from the sound. [PAUSE: 2]
Ease matters more than depth. [PAUSE: 4]

Stay with this quietly.
[PAUSE: 75]

Feel one full wave of inhale. [PAUSE: 2]
Feel one full wave of exhale. [PAUSE: 2]
Let the shoulders soften on the out breath. [PAUSE: 4]

Rest in silence.
[PAUSE: 90]

If thoughts appear. Return to the sound. [PAUSE: 2]
Return to the next breath. [PAUSE: 2]
That is normal. [PAUSE: 3]

Stay with this quietly.
[PAUSE: 75]

Wave rises. [PAUSE: 1]
Breath rises. [PAUSE: 2]
Wave falls. [PAUSE: 1]
Breath falls. [PAUSE: 3]

Rest in silence.
[PAUSE: 90]

Return to the sound. [PAUSE: 2]
Let the breath follow without effort. [PAUSE: 2]

Stay with this quietly.
[PAUSE: 90]

Rest in silence.
[PAUSE: 60]

Let the sound stay in the background. [PAUSE: 2]
Bring attention to the breath alone. [PAUSE: 2]
Take one gentle breath in. [PAUSE: 2]
Let it out slowly. [PAUSE: 2]
Feel the body resting here. [PAUSE: 2]
Notice the room around you. [PAUSE: 2]
Eyes open when ready. [PAUSE: 2]
"""
},
{
"id": "U019",
"script": """Find a comfortable seat. [PAUSE: 2]
Let your shoulders soften. [PAUSE: 2]
Feel the breath moving in and out. [PAUSE: 2]
Exhale will be your anchor today. [PAUSE: 2]
Let the out breath be slow. [PAUSE: 3]

On each exhale say a simple statement. [PAUSE: 2]
In this moment I am safe enough. [PAUSE: 2]
Say it quietly as the breath leaves. [PAUSE: 2]
Return to body sensation right after the words. [PAUSE: 3]

Inhale gently. [PAUSE: 2]
Exhale and say quietly.
In this moment I am safe enough. [PAUSE: 3]
Feel the air leaving. [PAUSE: 2]
Feel the chest settle. [PAUSE: 2]

Inhale gently. [PAUSE: 2]
Exhale and say quietly.
In this moment I am safe enough. [PAUSE: 4]
Feel the hands resting. [PAUSE: 2]
Feel the feet supported. [PAUSE: 3]

Continue with the phrase on each exhale.
I will be quiet for a while.
[PAUSE: 90]

If you forget the words. That is normal. [PAUSE: 2]
Return to the next exhale. [PAUSE: 2]
Say the statement softly. [PAUSE: 3]

Stay with this quietly.
[PAUSE: 75]

Exhale and say quietly.
In this moment I am safe enough. [PAUSE: 3]
Feel the belly rise and fall. [PAUSE: 2]
Feel the throat and jaw soften. [PAUSE: 3]

Rest in silence.
[PAUSE: 90]

Notice the space after the exhale. [PAUSE: 2]
Let the face soften. [PAUSE: 2]
Exhale and say quietly.
In this moment I am safe enough. [PAUSE: 4]

Stay with this quietly.
[PAUSE: 90]

Rest in silence.
[PAUSE: 75]

Return to the next exhale. [PAUSE: 2]
Say the statement softly. [PAUSE: 2]
Feel the body settle. [PAUSE: 4]

Stay with this quietly.
[PAUSE: 90]

Rest in silence.
[PAUSE: 60]

Let the words fade into the background. [PAUSE: 2]
Feel one easy breath in. [PAUSE: 2]
Feel one long breath out. [PAUSE: 2]
Feel the whole body sitting here. [PAUSE: 2]
Notice the room around you. [PAUSE: 2]
Eyes open when ready. [PAUSE: 2]
"""
},
{
"id": "U020",
"script": """Find a steady seat. [PAUSE: 2]
Let both feet touch the floor. [PAUSE: 2]
Rest your hands on your thighs. [PAUSE: 2]
Feel the touch of fabric and skin. [PAUSE: 2]
Hands are your anchor today. [PAUSE: 3]

Turn the palms slightly upward. [PAUSE: 2]
Let the left hand represent one side of a scale. [PAUSE: 2]
Let the right hand represent the other side. [PAUSE: 2]
Feel both hands as equal weight for a moment. [PAUSE: 3]

Take a slow breath in. [PAUSE: 2]
Let it out gently. [PAUSE: 2]
Return to the feeling in your palms. [PAUSE: 2]
A calm body helps the mind see clearly. [PAUSE: 4]

Picture a simple scale between your hands. [PAUSE: 2]
Left side holds the outcome your mind worries about. [PAUSE: 2]
Right side holds the most likely outcome. [PAUSE: 2]
Both can be here without effort. [PAUSE: 3]

Bring to mind one situation that has been on your mind. [PAUSE: 2]
Keep it small enough to hold. [PAUSE: 2]
Feel your hands as you think of it. [PAUSE: 3]

Place the worried outcome on the left side. [PAUSE: 2]
Use a short phrase. [PAUSE: 2]
Use a phrase like It turns out harder than I want. [PAUSE: 3]

Place the most likely outcome on the right side. [PAUSE: 2]
Use another short phrase. [PAUSE: 2]
Use a phrase like It is manageable. [PAUSE: 3]

Notice which hand feels heavier. [PAUSE: 2]
That is normal. [PAUSE: 2]
Return to the touch in your palms. [PAUSE: 3]

Begin adding evidence to the most likely side. [PAUSE: 2]
Think of one fact that supports the likely outcome. [PAUSE: 2]
Place that fact into the right hand as weight. [PAUSE: 4]

Take a quiet moment to find evidence.
[PAUSE: 30]

Add a second piece of evidence. [PAUSE: 2]
Choose a fact you know from experience. [PAUSE: 2]
Place it into the right hand. [PAUSE: 4]

Stay with this quietly.
[PAUSE: 30]

Add a third piece of evidence. [PAUSE: 2]
Look for what is most factual. [PAUSE: 2]
Place it into the right hand. [PAUSE: 4]

Rest in silence.
[PAUSE: 45]

Notice the right hand with its added weight. [PAUSE: 2]
Notice the left hand without feeding it more. [PAUSE: 2]
Let the scale begin to rebalance. [PAUSE: 4]

Stay with this quietly.
[PAUSE: 90]

Bring in evidence of your ability to respond. [PAUSE: 2]
Recall a time you handled something like this. [PAUSE: 2]
Place that memory as weight in the right hand. [PAUSE: 4]

Rest in silence.
[PAUSE: 60]

Return to the anchor of your hands. [PAUSE: 2]
Warmth or pressure or tingling or stillness can be present. [PAUSE: 2]
Let the breath move easily. [PAUSE: 2]
Let the shoulders soften. [PAUSE: 3]

Ask one gentle question. [PAUSE: 2]
What is the most likely next step. [PAUSE: 2]
Let one simple step appear. [PAUSE: 2]
Place that step into the right hand as weight. [PAUSE: 4]

Stay with this quietly.
[PAUSE: 45]

Rest in silence.
[PAUSE: 90]

If the mind returns to the worried side. That is normal. [PAUSE: 2]
Touch back into your palms. [PAUSE: 2]
Add one more piece of evidence to the likely side. [PAUSE: 4]

Stay with this quietly.
[PAUSE: 60]

Let the right hand feel supported. [PAUSE: 2]
Let the left hand feel supported. [PAUSE: 2]

Rest in silence.
[PAUSE: 60]

Let both hands return to neutral. [PAUSE: 2]
Feel them resting on your thighs. [PAUSE: 2]
Take one slow breath in. [PAUSE: 2]
Let it out fully. [PAUSE: 2]
Feel the whole body sitting here. [PAUSE: 2]
Notice the room around you. [PAUSE: 2]
Eyes open when ready. [PAUSE: 2]
"""
}
]

if __name__ == "__main__":
    for item in meditations_to_process:
        generate_meditation(item["id"], item["script"])
    
    print("\n🎉 All meditations in the list have been processed!")