"""End-to-end check of hands-free listening: synthesize speech, wake on it, and transcribe the command."""

import os

import numpy as np
import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("LEGION_INTEGRATION") != "1",
    reason="downloads wake word and speech models; set LEGION_INTEGRATION=1 to run",
)


@pytest.fixture(scope="module")
def speak():
    from scipy.signal import resample_poly

    from legion.tts import Synthesizer
    from legion.wake import FRAME, SAMPLE_RATE

    voice = Synthesizer("en_GB-alan-medium")

    def frames(*parts: str | float):
        """Speech and pauses (in seconds), cut into the 80 ms frames a microphone would deliver."""
        pieces = []
        for part in parts:
            if isinstance(part, str):
                pieces.append(resample_poly(voice.synthesize(part), SAMPLE_RATE, voice.sample_rate))
            else:
                pieces.append(np.zeros(int(part * SAMPLE_RATE), dtype=np.float32))
        audio = (np.clip(np.concatenate(pieces), -1, 1) * 32767).astype(np.int16)
        return iter([audio[i : i + FRAME] for i in range(0, len(audio) - FRAME + 1, FRAME)])

    return frames


@pytest.fixture(scope="module")
def wake():
    from legion.wake import WakeWord

    return WakeWord("hey_jarvis", threshold=0.5)


def test_the_command_after_the_wake_word_is_heard_and_transcribed(speak, wake):
    from legion.stt import Transcriber

    woke = []
    command = wake.hear(speak(1.0, "Hey Jarvis.", 0.4, "What is the capital of France?", 3.0), on_wake=lambda: woke.append(True))

    assert woke == [True]
    assert command is not None and command.size
    heard = Transcriber("base.en").transcribe(command).lower()
    assert "capital" in heard and "france" in heard


def test_speech_without_the_wake_word_never_wakes_legion(speak, wake):
    assert wake.hear(speak(1.0, "Good morning, what is the capital of France?", 2.0)) is None


def test_the_wake_word_in_one_breath_with_the_question_still_works(speak, wake):
    from legion.stt import Transcriber

    command = wake.hear(speak(1.0, "Hey Jarvis, what is the capital of France?", 3.0))

    assert command is not None and command.size
    assert "france" in Transcriber("base.en").transcribe(command).lower()


def test_a_follow_up_is_heard_without_repeating_the_wake_word(speak, wake):
    """The scenario the follow-up window exists for: ask something, then ask again with no
    wake word at all -- exactly what --gui does right after a voice-originated reply."""
    first = wake.hear(speak(1.0, "Hey Jarvis.", 0.4, "What is the capital of France?", 3.0))
    assert first is not None and first.size

    second = wake.hear(speak("And what is its population?", 3.0), wake_first=False, wait_for_speech=6.0)

    assert second is not None and second.size
    from legion.stt import Transcriber

    heard = Transcriber("base.en").transcribe(second).lower()
    assert "population" in heard
