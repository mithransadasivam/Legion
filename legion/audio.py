"""Microphone capture and speaker playback."""

import queue
import sys
import threading

import numpy as np
import sounddevice as sd

from legion.tts import Synthesizer

_PLAYBACK_BLOCK_SECONDS = 0.1


def microphone_name(device: int | str | None, sample_rate: int) -> str:
    """Confirm the microphone can record at ``sample_rate`` and return its name."""
    try:
        sd.check_input_settings(device=device, channels=1, dtype="float32", samplerate=sample_rate)
        return sd.query_devices(device, kind="input")["name"]
    except (ValueError, sd.PortAudioError) as exc:
        raise RuntimeError(
            f"can't use microphone {device if device is not None else '(default)'}: {exc}. "
            "List devices with: python -m sounddevice"
        ) from None


def record_until_enter(sample_rate: int, device: int | str | None = None) -> np.ndarray:
    """Record mono audio until the user presses Enter."""
    blocks: list[np.ndarray] = []
    with sd.InputStream(
        device=device,
        samplerate=sample_rate,
        channels=1,
        dtype="float32",
        callback=lambda data, frames, time, status: blocks.append(data.copy()),
    ):
        input()
    return np.concatenate(blocks).ravel() if blocks else np.zeros(0, dtype=np.float32)


class SpeechQueue:
    """Speaks sentences in order on a background thread, and can be cut off mid-sentence."""

    def __init__(self, synthesizer: Synthesizer) -> None:
        self._synthesizer = synthesizer
        self._pending: queue.Queue[tuple[int, str]] = queue.Queue()
        # Bumped by interrupt(); anything queued or playing under an older value is abandoned.
        self._generation = 0
        self._outstanding = 0
        self._idle = threading.Condition()
        threading.Thread(target=self._run, daemon=True).start()

    def say(self, text: str) -> None:
        if not text:
            return
        with self._idle:
            self._outstanding += 1
        self._pending.put((self._generation, text))

    def wait(self, timeout: float | None = None) -> bool:
        """Block until everything queued has been spoken. Returns False if the timeout expired first."""
        with self._idle:
            return self._idle.wait_for(lambda: self._outstanding == 0, timeout)

    def interrupt(self) -> None:
        """Stop talking within a fraction of a second and drop whatever is still queued."""
        self._generation += 1

    def _run(self) -> None:
        while True:
            generation, text = self._pending.get()
            try:
                if generation == self._generation:
                    self._play(self._synthesizer.synthesize(text), generation)
            except Exception as exc:
                # Keep the worker alive: if it died, wait() would block forever.
                print(f"\n[speech error: {exc}]", file=sys.stderr)
            finally:
                with self._idle:
                    self._outstanding -= 1
                    self._idle.notify_all()

    def _play(self, audio: np.ndarray, generation: int) -> None:
        rate = self._synthesizer.sample_rate
        block = int(rate * _PLAYBACK_BLOCK_SECONDS)
        audio = audio.astype(np.float32, copy=False)
        with sd.OutputStream(samplerate=rate, channels=1, dtype="float32") as stream:
            for start in range(0, len(audio), block):
                if generation != self._generation:
                    return
                stream.write(audio[start : start + block].reshape(-1, 1))
