"""End-to-end check of the audio stages: synthesize a phrase, then transcribe it back."""

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("LEGION_INTEGRATION") != "1",
    reason="downloads speech models; set LEGION_INTEGRATION=1 to run",
)


def test_synthesized_speech_transcribes_back_to_the_same_words(tmp_path):
    from legion.stt import Transcriber
    from legion.tts import Synthesizer

    wav = tmp_path / "phrase.wav"
    Synthesizer("en_GB-alan-medium").save_wav("The quick brown fox jumps over the lazy dog.", wav)

    heard = Transcriber("base.en").transcribe(str(wav)).lower()

    for word in ("quick", "brown", "fox", "lazy", "dog"):
        assert word in heard
