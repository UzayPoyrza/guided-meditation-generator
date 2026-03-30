#!/usr/bin/env python3
"""Tests for tts_generate.py — preprocessing, config, and routing logic only (no API calls)."""

import re
import sys
sys.path.insert(0, ".")

from tts_generate import (
    normalize_pause_tags,
    ensure_break_before_skip,
    limit_breaks,
    preprocess_script,
    VOICES,
)

passed = 0
failed = 0

def check(name, actual, expected):
    global passed, failed
    if actual == expected:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        print(f"  FAIL: {name}")
        print(f"    expected: {expected!r}")
        print(f"    actual:   {actual!r}")


# ============================================================
# 1. normalize_pause_tags
# ============================================================
print("\n--- normalize_pause_tags ---")

check("standard [PAUSE: 5] unchanged",
      normalize_pause_tags("[PAUSE: 5]"), "[PAUSE: 5]")

check("lowercase [pause: 5]",
      normalize_pause_tags("[pause: 5]"), "[PAUSE: 5]")

check("angle brackets <pause: 5>",
      normalize_pause_tags("<pause: 5>"), "[PAUSE: 5]")

check("parens (pause: 5)",
      normalize_pause_tags("(pause: 5)"), "[PAUSE: 5]")

check("mixed brackets <pause: 5]",
      normalize_pause_tags("<pause: 5]"), "[PAUSE: 5]")

check("mixed brackets [pause: 5>",
      normalize_pause_tags("[pause: 5>"), "[PAUSE: 5]")

check("mixed brackets (pause: 5]",
      normalize_pause_tags("(pause: 5]"), "[PAUSE: 5]")

check("semicolon separator [pause; 5]",
      normalize_pause_tags("[pause; 5]"), "[PAUSE: 5]")

check("no spaces [pause:5]",
      normalize_pause_tags("[pause:5]"), "[PAUSE: 5]")

check("extra spaces [ pause : 5 ]",
      normalize_pause_tags("[ pause : 5 ]"), "[PAUSE: 5]")

check("decimal [pause: 3.5]",
      normalize_pause_tags("[pause: 3.5]"), "[PAUSE: 3.5]")

check("decimal angle <pause: 1.2>",
      normalize_pause_tags("<pause: 1.2>"), "[PAUSE: 1.2]")

check("mixed case [Pause: 10]",
      normalize_pause_tags("[Pause: 10]"), "[PAUSE: 10]")

check("does not touch [PAUSE: 5] already correct",
      normalize_pause_tags("hello [PAUSE: 5] world"), "hello [PAUSE: 5] world")

check("multiple malformed in one string",
      normalize_pause_tags("<pause: 3> then (pause;5)"),
      "[PAUSE: 3] then [PAUSE: 5]")

check("does not touch break tags",
      normalize_pause_tags('<break time="1.0s" />'),
      '<break time="1.0s" />')

check("does not touch skip_point",
      normalize_pause_tags("[skip_point]"), "[skip_point]")


# ============================================================
# 2. ensure_break_before_skip
# ============================================================
print("\n--- ensure_break_before_skip ---")

check("inserts break when no adjacent break/pause",
      ensure_break_before_skip("Hello\n[skip_point]\nWorld"),
      'Hello\n<break time="1.0s" />\n[skip_point]\nWorld')

check("no insert when break before",
      ensure_break_before_skip('Hello\n<break time="1.2s" />\n[skip_point]\nWorld'),
      'Hello\n<break time="1.2s" />\n[skip_point]\nWorld')

check("no insert when pause before",
      ensure_break_before_skip("Hello\n[PAUSE: 5]\n[skip_point]\nWorld"),
      "Hello\n[PAUSE: 5]\n[skip_point]\nWorld")

check("no insert when break after",
      ensure_break_before_skip('Hello\n[skip_point]\n<break time="1.0s" />\nWorld'),
      'Hello\n[skip_point]\n<break time="1.0s" />\nWorld')

check("no insert when pause after",
      ensure_break_before_skip("Hello\n[skip_point]\n[PAUSE: 10]\nWorld"),
      "Hello\n[skip_point]\n[PAUSE: 10]\nWorld")

check("handles multiple skip_points",
      ensure_break_before_skip("A\n[skip_point]\nB\n[skip_point]\nC").count('<break time="1.0s" />'),
      2)

check("skip with blank lines still checks non-empty lines",
      ensure_break_before_skip("Hello\n\n\n[skip_point]\n\n\nWorld"),
      'Hello\n\n\n<break time="1.0s" />\n[skip_point]\n\n\nWorld')


# ============================================================
# 3. limit_breaks
# ============================================================
print("\n--- limit_breaks ---")

check("3 breaks kept",
      limit_breaks(
          '<break time="1.0s" /><break time="1.0s" /><break time="1.0s" />'
      ),
      '<break time="1.0s" /><break time="1.0s" /><break time="1.0s" />')

check("4th break converted",
      limit_breaks(
          '<break time="1.0s" /><break time="1.0s" /><break time="1.0s" /><break time="1.5s" />'
      ),
      '<break time="1.0s" /><break time="1.0s" /><break time="1.0s" />[pause: 1.5]')

check("5th break starts new count (kept)",
      limit_breaks(
          '<break time="1.0s" />' * 5
      ),
      '<break time="1.0s" /><break time="1.0s" /><break time="1.0s" />[pause: 1.0]<break time="1.0s" />')

check("8 breaks: 4th and 8th converted",
      limit_breaks('<break time="1.0s" />' * 8).count('[pause: 1.0]'),
      2)

check("text between breaks does NOT reset count",
      limit_breaks(
          '<break time="1.0s" />hello<break time="1.0s" />world<break time="1.0s" />foo<break time="2.0s" />'
      ),
      '<break time="1.0s" />hello<break time="1.0s" />world<break time="1.0s" />foo[pause: 2.0]')

check("no breaks returns unchanged",
      limit_breaks("just text here"), "just text here")


# ============================================================
# 4. preprocess_script (full pipeline)
# ============================================================
print("\n--- preprocess_script ---")

# Malformed pause + skip without break + many breaks
test_script = """Hello world
<pause: 5>
Some text
[skip_point]
More text
<break time="1.0s" />
<break time="1.0s" />
<break time="1.0s" />
<break time="1.0s" />
<break time="1.0s" />
End"""

result = preprocess_script(test_script)

check("malformed <pause: 5> normalized",
      "[PAUSE: 5]" in result, True)

check("<pause: 5> original removed",
      "<pause: 5>" not in result, True)

check("break inserted before bare skip_point",
      '<break time="1.0s" />\n[skip_point]' in result, True)

check("4th break in segment converted to pause",
      "[pause: 1.0]" in result, True)

# Break counter resets at [PAUSE:]
test_reset = """<break time="1.0s" /><break time="1.0s" /><break time="1.0s" />[PAUSE: 5]<break time="1.0s" /><break time="1.0s" /><break time="1.0s" />"""
result_reset = preprocess_script(test_reset)
check("break counter resets at [PAUSE:]",
      "[pause:" not in result_reset, True)

# Break counter resets at [skip_point]
test_reset2 = """<break time="1.0s" /><break time="1.0s" /><break time="1.0s" />[skip_point]<break time="1.0s" /><break time="1.0s" /><break time="1.0s" />"""
result_reset2 = preprocess_script(test_reset2)
# Note: ensure_break_before_skip won't fire here since breaks are adjacent
check("break counter resets at [skip_point]",
      result_reset2.count("[pause:") == 0, True)


# ============================================================
# 5. VOICES config
# ============================================================
print("\n--- VOICES config ---")

check("4 voices configured", len(VOICES), 4)

check("Luna is inworld", VOICES["Luna"]["api"], "inworld")
check("Claire is inworld", VOICES["Claire"]["api"], "inworld")
check("Graham is inworld", VOICES["Graham"]["api"], "inworld")
check("Silas is elevenlabs", VOICES["Silas"]["api"], "elevenlabs")

check("Luna speed", VOICES["Luna"]["speed"], 1.0)
check("Claire speed", VOICES["Claire"]["speed"], 0.9)
check("Graham speed", VOICES["Graham"]["speed"], 0.94)
check("Silas speed", VOICES["Silas"]["speed"], 0.8)

check("Luna temp", VOICES["Luna"]["temp"], 0.9)
check("Claire temp", VOICES["Claire"]["temp"], 0.8)
check("Graham temp", VOICES["Graham"]["temp"], 0.9)

check("Silas has voice_id", VOICES["Silas"]["voice_id"], "5MzdXfNI3TSWsCPwZFrB")
check("Silas has no temp (elevenlabs doesn't use it)", "temp" not in VOICES["Silas"], True)


# ============================================================
# 6. Script splitting (what generate_meditation sees after preprocess)
# ============================================================
print("\n--- Script splitting ---")

sample = """Settle in where you are.
<break time="1.1s" />
You do not need to solve anything.
[pause: 8]
Choose one physical anchor now.
[skip_point]
Let the anchor be plain."""

processed = preprocess_script(sample)
parts = re.split(r'(\[PAUSE:\s*\d+(?:\.\d+)?\]|\[skip_point\])', processed, flags=re.IGNORECASE)
parts = [p.strip() for p in parts if p.strip()]

check("split produces text, pause, text, skip, text",
      len(parts), 5)

check("first part is text with breaks",
      "Settle in" in parts[0] and '<break time="1.1s" />' in parts[0], True)

check("second part is pause tag",
      bool(re.match(r'\[PAUSE:\s*8\]', parts[1], re.IGNORECASE)), True)

check("third part is text",
      "Choose one physical anchor" in parts[2], True)

check("fourth part is skip_point",
      parts[3].lower() == "[skip_point]", True)

check("fifth part is text",
      "Let the anchor be plain" in parts[4], True)


# ============================================================
# 7. Edge cases
# ============================================================
print("\n--- Edge cases ---")

check("empty string",
      preprocess_script(""), "")

check("only pauses",
      preprocess_script("[PAUSE: 5][PAUSE: 10]"), "[PAUSE: 5][PAUSE: 10]")

check("only skip_point",
      "[skip_point]" in preprocess_script("[skip_point]"), True)

check("no tags at all",
      preprocess_script("Just some plain text."), "Just some plain text.")

check("decimal pause preserved",
      "[PAUSE: 3.5]" in preprocess_script("[pause: 3.5]"), True)

# Break right at the boundary (exactly 3 per segment)
three_breaks = '<break time="1.0s" />\n' * 3
check("exactly 3 breaks not converted",
      "[pause:" not in preprocess_script(three_breaks), True)

# Consecutive skip_points
check("consecutive skip_points get breaks",
      preprocess_script("Text\n[skip_point]\n[skip_point]\nMore").count("[skip_point]"), 2)


# ============================================================
# 8. Usage line in docstring
# ============================================================
print("\n--- Misc ---")

import tts_generate
check("docstring references correct filename",
      "InworldTTS_test" not in (tts_generate.__doc__ or "").split("Usage")[0], True)


# ============================================================
print(f"\n{'='*50}")
print(f"Results: {passed} passed, {failed} failed")
if failed:
    sys.exit(1)
else:
    print("All tests passed!")
