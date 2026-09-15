"""Deciding whether a transcribed utterance was meant for Legion, and separating the greeting
from the actual question.

No trained wake word means anyone starting to speak gets recorded and transcribed by
legion.app._voice_watcher, well before there's any way to know if they were talking to Legion at
all. This is what tells "hey Legion, what's the capital of France" apart from someone across the
room saying "hey, did you catch the game last night" -- a text check on what Whisper heard, not an
acoustic model. The trade-off going in: common words like "hey" and "hi" will occasionally catch
nearby conversation that a trained phrase like "hey jarvis" wouldn't have.
"""

import re

GREETINGS = [
    "hey legion", "hi legion", "hello legion",
    "good morning", "good afternoon", "good evening",
    "legion", "hey", "hi", "hello", "yo",
]

# Longest first, so "hey legion" is tried before the "hey" it also starts with -- otherwise "hey"
# would match alone and leave "legion, what's..." sitting unstripped in front of the question.
_PATTERN = re.compile(
    r"^\s*(?:" + "|".join(re.escape(g) for g in sorted(GREETINGS, key=len, reverse=True)) + r")\b[,.!\s]*",
    re.IGNORECASE,
)


def strip_greeting(text: str) -> str | None:
    """What's left after the greeting Legion was addressed by, or None if ``text`` doesn't open
    with one at all -- in which case it almost certainly wasn't addressed to Legion.

    An empty string means the greeting was the whole utterance ("Hey Legion." and nothing else):
    addressed to Legion, but no question in it yet.
    """
    match = _PATTERN.match(text)
    if not match:
        return None
    return text[match.end() :].strip()
