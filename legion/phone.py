"""Legion over the home network: a mobile page that talks to this same machine's Ollama, Whisper,
and Piper, so a phone becomes a remote control rather than a second brain -- nothing runs on the
phone itself, and it only works while this machine is on and reachable on the same network.

Tap-to-talk, not a wake word: recording starts and stops on a deliberate tap, the same way
push-to-talk does on the desktop, so there's no VAD or greeting-word gate needed here at all.
"""

from __future__ import annotations

import base64
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import bottle

from legion.text import clean_for_speech

if TYPE_CHECKING:
    from legion.brain import Brain
    from legion.stt import Transcriber
    from legion.tts import Synthesizer

_PAGE = Path(__file__).parent / "phone" / "index.html"


def lan_address() -> str:
    """This machine's address on the local network, for showing the phone what to open.

    Deliberately doesn't send anything: connecting a UDP socket just asks the OS to pick the
    outbound interface, without a packet ever leaving.
    """
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        try:
            probe.connect(("8.8.8.8", 80))
            return probe.getsockname()[0]
        except OSError:
            return "127.0.0.1"  # no network at all; still usable from this machine itself


def build_app(
    brain: Brain, transcriber: Transcriber, synthesizer: Synthesizer | None, model: str, host: str
) -> bottle.Bottle:
    """The routes, wired to one Brain -- kept separate from any other running Brain (the GUI's,
    say), so a phone request can never mutate conversation history another thread is using."""
    app = bottle.Bottle()

    @app.get("/")
    def page():
        return bottle.static_file(_PAGE.name, root=str(_PAGE.parent))

    @app.get("/config")
    def config():
        return {"model": model, "host": host}

    @app.post("/ask")
    def ask():
        upload = bottle.request.files.get("audio")
        if upload is None:
            bottle.response.status = 400
            return {"error": "no audio uploaded"}

        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as temp:
            upload.save(temp)
            temp_path = temp.name
        try:
            heard = transcriber.transcribe(temp_path)
        finally:
            Path(temp_path).unlink(missing_ok=True)

        if not heard:
            return {"heard": "", "reply": "", "audio": None}

        print(f"Phone: {heard}", flush=True)
        reply = "".join(brain.reply(heard))
        print(f"Legion: {reply}", flush=True)
        spoken = clean_for_speech(reply)
        audio_base64 = _synthesize_to_base64(synthesizer, spoken) if synthesizer and spoken else None
        return {"heard": heard, "reply": reply, "audio": audio_base64}

    return app


def _synthesize_to_base64(synthesizer: Synthesizer, text: str) -> str:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp:
        temp_path = temp.name
    try:
        synthesizer.save_wav(text, Path(temp_path))
        return base64.b64encode(Path(temp_path).read_bytes()).decode("ascii")
    finally:
        Path(temp_path).unlink(missing_ok=True)


def run(app: bottle.Bottle, host: str = "0.0.0.0", port: int = 8420) -> None:
    """Blocks serving ``app`` -- call this on a background thread if something else (the GUI's
    own event loop) needs the calling thread too."""
    bottle.run(app, host=host, port=port, quiet=True)
