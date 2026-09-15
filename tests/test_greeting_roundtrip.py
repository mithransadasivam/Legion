"""End-to-end check of greeting-based activation: real VAD, real Whisper, real greeting matching --
no trained wake word involved at all, since WakeWord(model=None) never loads one."""

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("LEGION_INTEGRATION") != "1",
    reason="downloads speech models; set LEGION_INTEGRATION=1 to run",
)


@pytest.fixture(scope="module")
def speak():
    from scipy.signal import resample_poly

    from legion.tts import Synthesizer
    from legion.wake import FRAME, SAMPLE_RATE

    voice = Synthesizer("en_GB-alan-medium")

    def frames(*parts: str | float):
        pieces = []
        for part in parts:
            if isinstance(part, str):
                pieces.append(resample_poly(voice.synthesize(part), SAMPLE_RATE, voice.sample_rate))
            else:
                pieces.append(__import__("numpy").zeros(int(part * SAMPLE_RATE), dtype="float32"))
        import numpy as np

        audio = (np.clip(np.concatenate(pieces), -1, 1) * 32767).astype(np.int16)
        return iter([audio[i : i + FRAME] for i in range(0, len(audio) - FRAME + 1, FRAME)])

    return frames


@pytest.fixture(scope="module")
def listener():
    from legion.wake import WakeWord

    return WakeWord(model=None)


def test_a_real_greeting_is_heard_and_transcribed_with_no_trained_model(speak, listener):
    from legion.greeting import strip_greeting
    from legion.stt import Transcriber

    heard = listener.hear(speak(1.0, "Hey Legion, what is the capital of France?", 3.0), wake_first=False)

    assert heard is not None and heard.size
    text = Transcriber("base.en").transcribe(heard)
    question = strip_greeting(text)
    assert question is not None, f"the greeting should have been recognized in {text!r}"
    assert "france" in question.lower()


def test_speech_with_no_greeting_is_heard_but_correctly_rejected(speak, listener):
    from legion.greeting import strip_greeting
    from legion.stt import Transcriber

    heard = listener.hear(speak(1.0, "I think it might rain later today.", 3.0), wake_first=False)

    assert heard is not None and heard.size, "VAD should still capture it -- rejecting happens after transcription"
    text = Transcriber("base.en").transcribe(heard)
    assert strip_greeting(text) is None
