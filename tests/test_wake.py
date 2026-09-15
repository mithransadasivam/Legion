import pytest

from legion.wake import Endpointer, phrase

SPEECH, SILENCE = 0.9, 0.1
FRAMES_PER_SECOND = 12.5


def frames_until_finished(endpointer: Endpointer, probabilities) -> int | None:
    for count, probability in enumerate(probabilities, start=1):
        if endpointer.finished(probability):
            return count
    return None


def seconds(n: float) -> int:
    return round(n * FRAMES_PER_SECOND)


class TestEndpointer:
    def test_a_command_ends_after_a_second_of_silence(self):
        endpointer = Endpointer()
        talking, then_quiet = [SPEECH] * seconds(2), [SILENCE] * seconds(3)

        finished_at = frames_until_finished(endpointer, talking + then_quiet)

        assert finished_at == seconds(2) + seconds(1)
        assert endpointer.heard_speech

    def test_a_short_pause_mid_sentence_does_not_end_it(self):
        endpointer = Endpointer()
        with_a_pause = [SPEECH] * seconds(1) + [SILENCE] * seconds(0.5) + [SPEECH] * seconds(1)

        assert frames_until_finished(endpointer, with_a_pause) is None

    def test_waking_legion_and_saying_nothing_gives_up_after_five_seconds(self):
        endpointer = Endpointer()

        assert frames_until_finished(endpointer, [SILENCE] * seconds(10)) == seconds(5)
        assert not endpointer.heard_speech

    def test_someone_who_never_stops_talking_is_cut_off_at_fifteen_seconds(self):
        endpointer = Endpointer()

        assert frames_until_finished(endpointer, [SPEECH] * seconds(30)) == seconds(15)


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("hey_jarvis", "hey jarvis"),
        ("models/hey_legion_v0.1.onnx", "hey legion"),
        ("C:/wake/hey_legion.onnx", "hey legion"),
    ],
)
def test_the_phrase_to_say_comes_from_the_model_name(model, expected):
    assert phrase(model) == expected
