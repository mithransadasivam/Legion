"""Microphone capture and speaker playback."""

import queue
import sys
import threading

import numpy as np
import sounddevice as sd

from legion.tts import Synthesizer


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
    """Speaks sentences in order on a background thread, so text keeps streaming during playback."""

    def __init__(self, synthesizer: Synthesizer) -> None:
        self._synthesizer = synthesizer
        self._pending: queue.Queue[str] = queue.Queue()
        threading.Thread(target=self._run, daemon=True).start()

    def say(self, text: str) -> None:
        if text:
            self._pending.put(text)

    def wait(self) -> None:
        self._pending.join()

    def _run(self) -> None:
        while True:
            text = self._pending.get()
            try:
                sd.play(self._synthesizer.synthesize(text), self._synthesizer.sample_rate)
                sd.wait()
            except Exception as exc:
                # If the worker died here, every later sentence would be silently dropped.
                print(f"\n[speech error: {exc}]", file=sys.stderr)
            finally:
                self._pending.task_done()
