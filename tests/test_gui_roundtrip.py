"""End-to-end check of the GUI wiring: real wake detection, transcription, and a real Ollama
reply, all landing on the HUD in the right order. No window, no speakers, no live microphone --
a FakeWindow stands in for pywebview, and playback is captured instead of played."""

import os

import numpy as np
import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("LEGION_INTEGRATION") != "1",
    reason="downloads models and needs Ollama running; set LEGION_INTEGRATION=1 to run",
)


class FakeWindow:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def evaluate_js(self, script: str) -> None:
        self.calls.append(script)


class FakeVoice:
    """A fast stand-in for Piper: this test's real cost should be Whisper + Ollama, not a second TTS pass."""

    sample_rate = 16_000

    def synthesize(self, text: str) -> np.ndarray:
        return np.full(8000, 0.3, dtype=np.float32)


@pytest.fixture
def speak():
    from scipy.signal import resample_poly

    from legion.tts import Synthesizer
    from legion.wake import FRAME, SAMPLE_RATE

    voice = Synthesizer("en_GB-alan-medium")

    def frames(*parts):
        pieces = []
        for part in parts:
            if isinstance(part, str):
                pieces.append(resample_poly(voice.synthesize(part), SAMPLE_RATE, voice.sample_rate))
            else:
                pieces.append(np.zeros(int(part * SAMPLE_RATE), dtype=np.float32))
        audio = (np.clip(np.concatenate(pieces), -1, 1) * 32767).astype(np.int16)
        return iter([audio[i : i + FRAME] for i in range(0, len(audio) - FRAME + 1, FRAME)])

    return frames


@pytest.fixture
def played(monkeypatch):
    """Captures what SpeechQueue would have played, instead of touching real speakers."""
    from legion import audio as audio_module

    class FakeOutputStream:
        def __init__(self, *, samplerate, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def write(self, data):
            pass

    monkeypatch.setattr(audio_module.sd, "OutputStream", FakeOutputStream)


def test_a_real_question_reaches_the_hud_through_the_whole_pipeline(speak, played):
    from legion.audio import SpeechQueue
    from legion.brain import Brain
    from legion.gui import Hud
    from legion.stt import Transcriber
    from legion.wake import WakeWord

    wake = WakeWord("hey_jarvis", threshold=0.5)
    heard = wake.hear(speak(1.0, "Hey Jarvis.", 0.4, "What is the capital of France?", 3.0))
    assert heard is not None and heard.size, "the wake word should have fired and captured a command"

    text = Transcriber("base.en").transcribe(heard)
    assert "france" in text.lower()

    brain = Brain(model="llama3.2:3b", host="http://127.0.0.1:11434")
    try:
        brain.check()
    except RuntimeError as exc:
        pytest.skip(f"Ollama not ready for this check: {exc}")

    window = FakeWindow()
    hud = Hud()
    hud.attach(window)

    speech = SpeechQueue(FakeVoice(), on_level=hud.set_level)
    reply: list[str] = []
    speaking_started = False
    for token in brain.reply(text):
        reply.append(token)
        if not speaking_started:
            hud.set_state("speaking")
            speaking_started = True
        hud.set_readout("REPLY", "".join(reply))
    speech.say("".join(reply))
    assert speech.wait(timeout=10)

    calls = " ".join(window.calls)
    assert 'setState("speaking")' in calls
    assert "paris" in calls.lower(), "the real reply should have reached the HUD"
    assert any("setLevel" in c for c in window.calls), "played audio should have driven the level meter"
