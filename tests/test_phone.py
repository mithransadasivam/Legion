"""Unit coverage for the phone server's routes, using a real bottle server on an ephemeral port
and real HTTP requests -- bottle has no bundled test client, so this is plain urllib against a
genuine socket, the same shape of request curl made in manual testing."""

import json
import threading
import time
import urllib.error
import urllib.request
import uuid
import wave

import bottle
import pytest

from legion.phone import build_app, lan_address


class FakeBrain:
    def __init__(self, reply: str = "The capital of France is Paris, sir.") -> None:
        self.reply_text = reply
        self.asked: list[str] = []

    def reply(self, text: str):
        self.asked.append(text)
        yield self.reply_text


class FakeTranscriber:
    def __init__(self, text: str = "What is the capital of France?") -> None:
        self.text = text
        self.paths: list[str] = []

    def transcribe(self, path: str) -> str:
        self.paths.append(path)
        return self.text


class FakeSynthesizer:
    def __init__(self) -> None:
        self.synthesized: list[str] = []

    def save_wav(self, text: str, path) -> None:
        self.synthesized.append(text)
        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(16000)
            wav_file.writeframes(b"\x00\x00" * 100)


@pytest.fixture
def server():
    """Starts a real bottle server on a free port for one test, tearing it down afterward."""
    started = {}

    def start(brain=None, transcriber=None, synthesizer="default"):
        brain = brain if brain is not None else FakeBrain()
        transcriber = transcriber if transcriber is not None else FakeTranscriber()
        synthesizer = FakeSynthesizer() if synthesizer == "default" else synthesizer
        app = build_app(brain, transcriber, synthesizer, model="llama3.2:3b", host="http://127.0.0.1:11434")
        wsgi_server = bottle.WSGIRefServer(host="127.0.0.1", port=0, quiet=True)
        thread = threading.Thread(target=wsgi_server.run, args=(app,), daemon=True)
        thread.start()
        for _ in range(100):
            if getattr(wsgi_server, "srv", None) is not None:
                break
            time.sleep(0.02)
        started["server"] = wsgi_server
        return f"http://127.0.0.1:{wsgi_server.port}", brain, transcriber, synthesizer

    yield start
    if "server" in started:
        started["server"].srv.shutdown()


def _post_multipart(url: str, field: str, filename: str, content: bytes) -> dict:
    boundary = uuid.uuid4().hex
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
    request = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read())


class TestRoutes:
    def test_the_page_is_served_at_root(self, server):
        base_url, *_ = server()

        with urllib.request.urlopen(f"{base_url}/") as response:
            assert response.status == 200
            assert b"Legion" in response.read()

    def test_config_reports_the_model_and_host(self, server):
        base_url, *_ = server()

        with urllib.request.urlopen(f"{base_url}/config") as response:
            assert json.loads(response.read()) == {"model": "llama3.2:3b", "host": "http://127.0.0.1:11434"}

    def test_a_real_upload_is_transcribed_answered_and_spoken(self, server):
        base_url, brain, transcriber, synthesizer = server()

        result = _post_multipart(f"{base_url}/ask", "audio", "question.webm", b"pretend audio bytes")

        assert result["heard"] == "What is the capital of France?"
        assert result["reply"] == "The capital of France is Paris, sir."
        assert result["audio"], "a WAV should have come back, base64-encoded"
        assert brain.asked == ["What is the capital of France?"]
        assert synthesizer.synthesized == ["The capital of France is Paris, sir."]

    def test_the_uploaded_audio_reaches_the_transcriber_as_a_real_file(self, server):
        base_url, _, transcriber, _ = server()

        _post_multipart(f"{base_url}/ask", "audio", "question.webm", b"pretend audio bytes")

        assert len(transcriber.paths) == 1
        assert transcriber.paths[0].endswith(".webm")

    def test_no_audio_field_is_a_client_error(self, server):
        base_url, *_ = server()
        boundary = uuid.uuid4().hex
        body = f"--{boundary}--\r\n".encode()
        request = urllib.request.Request(
            f"{base_url}/ask", data=body, method="POST",
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(request)
        assert exc_info.value.code == 400

    def test_silence_that_transcribes_to_nothing_never_reaches_the_model(self, server):
        base_url, brain, transcriber, synthesizer = server(transcriber=FakeTranscriber(text=""))

        result = _post_multipart(f"{base_url}/ask", "audio", "silence.webm", b"pretend silence")

        assert result == {"heard": "", "reply": "", "audio": None}
        assert brain.asked == []
        assert synthesizer.synthesized == []

    def test_quiet_mode_skips_synthesis_but_still_answers(self, server):
        base_url, brain, transcriber, _ = server(synthesizer=None)

        result = _post_multipart(f"{base_url}/ask", "audio", "question.webm", b"pretend audio")

        assert result["reply"] == "The capital of France is Paris, sir."
        assert result["audio"] is None


class TestLanAddress:
    def test_returns_a_plausible_ip_address(self):
        address = lan_address()

        parts = address.split(".")
        assert len(parts) == 4
        assert all(part.isdigit() and 0 <= int(part) <= 255 for part in parts)
