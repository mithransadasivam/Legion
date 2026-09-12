"""Speech recognition with faster-whisper, running on the CPU."""

import numpy as np
from faster_whisper import WhisperModel
from huggingface_hub.errors import LocalEntryNotFoundError

SAMPLE_RATE = 16_000


class Transcriber:
    def __init__(self, model_size: str) -> None:
        # Cache first, so a normal startup never touches the network.
        try:
            self._model = WhisperModel(model_size, device="cpu", compute_type="int8", local_files_only=True)
        except LocalEntryNotFoundError:
            self._model = WhisperModel(model_size, device="cpu", compute_type="int8")

    def transcribe(self, audio: np.ndarray | str) -> str:
        """Transcribe 16 kHz mono float audio, or the path to an audio file."""
        # VAD trims silence first; on pure silence Whisper tends to invent words.
        segments, _ = self._model.transcribe(audio, language="en", beam_size=1, vad_filter=True)
        return " ".join(segment.text.strip() for segment in segments).strip()
