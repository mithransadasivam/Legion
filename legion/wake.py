"""Hands-free activation: wait for a wake word, then record until the user stops talking.

Wake words come from openWakeWord. It ships a ready-made "hey jarvis" model, and a custom phrase such
as "hey legion" is a single .onnx file, trained with its notebook and passed in place of the name.
With no second key press to mark the end of a command, the Silero voice activity detector that ships
alongside it decides when the user has stopped talking.
"""

import re
from collections.abc import Callable, Iterator
from pathlib import Path

import numpy as np

SAMPLE_RATE = 16_000
FRAME = 1280  # 80 ms: the chunk size openWakeWord expects
_FRAMES_PER_SECOND = SAMPLE_RATE / FRAME


def phrase(model: str) -> str:
    """What to say for a model: "hey_jarvis" is "hey jarvis", and "models/hey_legion_v0.1.onnx" is "hey legion"."""
    name = Path(model).stem if model.endswith((".onnx", ".tflite")) else model
    return re.sub(r"_v\d[\w.]*$", "", name).replace("_", " ")


class Endpointer:
    """Decides when a spoken command is over, from one speech probability per frame."""

    def __init__(
        self,
        speech_threshold: float = 0.5,
        silence_to_finish: float = 1.0,
        wait_for_speech: float = 5.0,
        longest: float = 15.0,
    ) -> None:
        self._threshold = speech_threshold
        self._silence_frames = round(silence_to_finish * _FRAMES_PER_SECOND)
        self._waiting_frames = round(wait_for_speech * _FRAMES_PER_SECOND)
        self._longest_frames = round(longest * _FRAMES_PER_SECOND)
        self._frames = 0
        self._quiet_frames = 0
        self.heard_speech = False

    def finished(self, speech_probability: float) -> bool:
        """Count one more frame, and say whether the user has stopped talking, or never started."""
        self._frames += 1
        if speech_probability >= self._threshold:
            self.heard_speech = True
            self._quiet_frames = 0
        else:
            self._quiet_frames += 1
        if self._frames >= self._longest_frames:
            return True
        if not self.heard_speech:
            return self._frames >= self._waiting_frames
        return self._quiet_frames >= self._silence_frames


class WakeWord:
    def __init__(self, model: str, threshold: float) -> None:
        # Imported here, because push-to-talk never needs them.
        import openwakeword.utils
        from openwakeword.model import Model
        from openwakeword.vad import VAD

        try:
            # Fetches only files that are missing, so after the first run this never touches the network.
            openwakeword.utils.download_models([model])
            self._detector = Model(wakeword_models=[model], inference_framework="onnx")
        except Exception as exc:
            raise RuntimeError(
                f"can't load the wake word model {model!r}: {exc}. "
                "Use a built-in name such as hey_jarvis, or the path to a .onnx file"
            ) from None
        self._vad = VAD()
        self._threshold = threshold
        self.phrase = phrase(model)

    def listen(
        self,
        device: int | str | None = None,
        on_wake: Callable[[], None] | None = None,
        wake_first: bool = True,
        on_level: Callable[[float], None] | None = None,
        stop_check: Callable[[], bool] | None = None,
    ) -> np.ndarray:
        """Wait for the wake word, unless ``wake_first`` is False, then return the command that follows it."""
        import sounddevice as sd

        with sd.InputStream(device=device, samplerate=SAMPLE_RATE, channels=1, dtype="int16", blocksize=FRAME) as stream:
            command = self.hear(_frames(stream), on_wake, wake_first, on_level, stop_check)
        return command if command is not None else np.zeros(0, dtype=np.float32)

    def hear(
        self,
        frames: Iterator[np.ndarray],
        on_wake: Callable[[], None] | None = None,
        wake_first: bool = True,
        on_level: Callable[[float], None] | None = None,
        stop_check: Callable[[], bool] | None = None,
    ) -> np.ndarray | None:
        """The command spoken after the wake word, as 16 kHz float audio.

        Empty if the user woke Legion and then said nothing; None if the frames ran out before it
        woke, or ``stop_check`` returned True first. ``on_level`` is called with a 0..1 loudness
        estimate for every frame after the wake word, for driving a live meter — not before it,
        since a HUD showing "idle" has nothing to meter yet. ``stop_check`` is polled once per
        frame, but only while still waiting for the wake word: once the user is actually talking,
        cutting them off mid-command would be worse than letting this call finish.
        """
        # Imported here, not at module scope, so importing wake.py never pulls in Piper's chain
        # (legion.audio imports Synthesizer) just to reach a small pure function.
        from legion.audio import audio_level

        self._detector.reset()
        self._vad.reset_states()
        if wake_first:
            for frame in frames:
                if stop_check and stop_check():
                    return None
                if max(self._detector.predict(frame).values()) >= self._threshold:
                    break
            else:
                return None
        if on_wake:
            on_wake()
        endpointer = Endpointer()
        command = []
        for frame in frames:
            command.append(frame)
            if on_level:
                on_level(audio_level(frame.astype(np.float32) / 32768))
            if endpointer.finished(self._vad.predict(frame, frame_size=FRAME // 2)):
                break
        if not endpointer.heard_speech:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(command).astype(np.float32) / 32768


def _frames(stream) -> Iterator[np.ndarray]:
    while True:
        frame, _overflowed = stream.read(FRAME)
        yield frame[:, 0]
