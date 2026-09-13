import time

import numpy as np
import pytest

from legion import audio
from legion.audio import SpeechQueue

SAMPLE_RATE = 1_000


class FakeSynthesizer:
    sample_rate = SAMPLE_RATE

    def __init__(self, seconds_per_sentence: float) -> None:
        self.seconds = seconds_per_sentence
        self.synthesized: list[str] = []

    def synthesize(self, text: str) -> np.ndarray:
        self.synthesized.append(text)
        return np.zeros(int(SAMPLE_RATE * self.seconds), dtype=np.float32)


@pytest.fixture
def played(monkeypatch) -> list[int]:
    """Replaces the speaker with one that plays in real time and records how many samples it played."""
    samples: list[int] = []

    class FakeOutputStream:
        def __init__(self, *, samplerate, **kwargs):
            self.samplerate = samplerate

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def write(self, data):
            time.sleep(len(data) / self.samplerate)
            samples.append(len(data))

    monkeypatch.setattr(audio.sd, "OutputStream", FakeOutputStream)
    return samples


def test_speaks_every_sentence_in_order(played):
    synth = FakeSynthesizer(seconds_per_sentence=0.1)
    speech = SpeechQueue(synth)
    for sentence in ["one", "two", "three"]:
        speech.say(sentence)

    assert speech.wait(timeout=5)
    assert synth.synthesized == ["one", "two", "three"]
    assert sum(played) == 3 * 100


def test_wait_with_timeout_reports_speech_still_in_progress(played):
    speech = SpeechQueue(FakeSynthesizer(seconds_per_sentence=1.0))
    speech.say("a long sentence")

    assert speech.wait(timeout=0.1) is False
    speech.interrupt()
    assert speech.wait(timeout=2)


def test_interrupt_stops_mid_sentence_and_drops_the_queue(played):
    synth = FakeSynthesizer(seconds_per_sentence=1.0)
    speech = SpeechQueue(synth)
    for sentence in ["first", "second", "third"]:
        speech.say(sentence)
    time.sleep(0.25)

    started = time.monotonic()
    speech.interrupt()
    assert speech.wait(timeout=2)

    assert time.monotonic() - started < 0.5
    assert sum(played) < SAMPLE_RATE, "the first sentence should have been cut off partway"
    assert synth.synthesized == ["first"], "queued sentences should be dropped without being synthesized"


def test_sentences_queued_after_an_interrupt_are_still_spoken(played):
    synth = FakeSynthesizer(seconds_per_sentence=0.1)
    speech = SpeechQueue(synth)
    speech.say("before")
    speech.interrupt()
    speech.wait(timeout=2)

    speech.say("after")

    assert speech.wait(timeout=2)
    assert synth.synthesized[-1] == "after"


def test_empty_text_is_ignored(played):
    speech = SpeechQueue(FakeSynthesizer(seconds_per_sentence=0.1))
    speech.say("")
    assert speech.wait(timeout=0.5)
