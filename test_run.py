"""One-off test run: generates a single meditation test output."""
import generate_voice

# Override voice ID for this test
generate_voice.VOICE_ID = "0RggJOBxyZgzpa5eXp6S"

script = """Let your eyes stay open.
<break time="0.9s" />
Find one steady place in the room.
[pause: 4]
Feel both feet on the floor.
<break time="1.0s" />
Notice pressure in the heels, the toes, or the edges of your shoes.
[pause: 6]
If something around you truly needs attention, follow that.
<break time="1.1s" />
Otherwise stay with this brief orienting practice.
[pause: 5]
Name one body sensation plainly.
<break time="0.9s" />
Maybe racing heart.
<break time="0.8s" />
Maybe tight chest.
<break time="0.8s" />
Maybe shaky hands.
[pause: 4]
Then return to the feet.
<break time="0.7s" />
Feel the ground under you.
[pause: 8]
Again, choose one true label.
<break time="1.0s" />
Only the sensation."""

generate_voice.test_tts(script)
