"""Legion over the home network: a mobile page that talks to this same machine's Ollama, Whisper,
and Piper, so a phone becomes a remote control rather than a second brain -- nothing runs on the
phone itself, and it only works while this machine is on and reachable on the same network.

Tap-to-talk, not a wake word: recording starts and stops on a deliberate tap, the same way
push-to-talk does on the desktop, so there's no VAD or greeting-word gate needed here at all.

Two servers, one app: browsers refuse to expose the microphone at all -- ``navigator.mediaDevices``
is simply undefined -- on a page that isn't a secure context, and a plain LAN address never is.
The plain HTTP server (``run_http``) exists to serve the page that explains this and hands over a
certificate to trust; once that's done, the same page over HTTPS (``run_https``) is where the
microphone actually works.
"""

from __future__ import annotations

import base64
import datetime
import ipaddress
import ssl
import sys
import tempfile
import threading
from pathlib import Path
from socketserver import ThreadingMixIn
from typing import TYPE_CHECKING
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

import bottle

from legion.text import clean_for_speech

if TYPE_CHECKING:
    from legion.brain import Brain
    from legion.stt import Transcriber
    from legion.tts import Synthesizer

_PAGE = Path(__file__).parent / "phone" / "index.html"
_WATCH_FACE = Path(__file__).parent / "assets" / "watchface.png"
_CERT_VALID_DAYS = 3650


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


def ensure_certificate(cert_dir: Path, lan_ip: str) -> tuple[Path, Path]:
    """A self-signed certificate covering ``lan_ip``, kept on disk and reused across restarts so a
    phone that has already trusted it doesn't need to trust it again next time Legion runs.

    Regenerated only when there's no cert yet, it's expired, or it doesn't cover the current
    address -- a DHCP lease can hand this machine a different one than last time.
    """
    cert_path, key_path = cert_dir / "phone-cert.pem", cert_dir / "phone-key.pem"
    if cert_path.exists() and key_path.exists() and _covers(cert_path, lan_ip):
        return cert_path, key_path
    cert_dir.mkdir(parents=True, exist_ok=True)
    _generate_certificate(cert_path, key_path, lan_ip)
    return cert_path, key_path


def _covers(cert_path: Path, lan_ip: str) -> bool:
    from cryptography import x509

    try:
        cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
        if cert.not_valid_after_utc < datetime.datetime.now(datetime.timezone.utc):
            return False
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        addresses = {str(ip) for ip in san.get_values_for_type(x509.IPAddress)}
        return lan_ip in addresses
    except Exception:
        return False


def _generate_certificate(cert_path: Path, key_path: Path, lan_ip: str) -> None:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Legion")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=_CERT_VALID_DAYS))
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.IPAddress(ipaddress.ip_address(lan_ip)),
                    x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
                    x509.DNSName("localhost"),
                ]
            ),
            critical=False,
        )
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )


def build_app(
    brain: Brain,
    transcriber: Transcriber,
    synthesizer: Synthesizer | None,
    model: str,
    host: str,
    https_url: str,
    cert_path: Path,
) -> bottle.Bottle:
    """The routes, wired to one Brain -- kept separate from any other running Brain (the GUI's,
    say), so a phone request can never mutate conversation history another thread is using.

    Shared between the HTTP and HTTPS servers: the page it serves checks which one it's actually
    on and shows the right thing either way.
    """
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization

    cert_der = x509.load_pem_x509_certificate(cert_path.read_bytes()).public_bytes(serialization.Encoding.DER)

    app = bottle.Bottle()
    # Requests now run concurrently, but a Brain's conversation history isn't safe to mutate from
    # two threads at once -- so replies take turns, while everything else (uploads, transcription,
    # serving the page) no longer waits on them.
    brain_lock = threading.Lock()

    @app.get("/")
    def page():
        return bottle.static_file(_PAGE.name, root=str(_PAGE.parent))

    @app.get("/config")
    def config():
        return {"model": model, "host": host, "httpsUrl": https_url}

    @app.get("/watchface.png")
    def watch_face():
        return bottle.static_file(_WATCH_FACE.name, root=str(_WATCH_FACE.parent), mimetype="image/png")

    @app.get("/legion-cert.cer")
    def download_cert():
        bottle.response.content_type = "application/x-x509-ca-cert"
        return cert_der

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
        with brain_lock:
            reply = "".join(brain.reply(heard))
        print(f"Legion: {reply}", flush=True)
        spoken = clean_for_speech(reply)
        audio_base64 = _synthesize_to_base64(synthesizer, spoken) if synthesizer and spoken else None
        return {"heard": heard, "reply": reply, "audio": audio_base64}

    @app.post("/say")
    def say():
        # For clients that already have text and can only speak it themselves -- an Apple Watch
        # Shortcut dictates on the watch, posts the words here, and reads the reply aloud with the
        # watch's own voice. Plain text back, not JSON, so the Shortcut needs no parsing step.
        text = bottle.request.forms.getunicode("text")
        if text is None and (bottle.request.content_type or "").startswith("application/json"):
            text = (bottle.request.json or {}).get("text")
        text = (text or "").strip()
        if not text:
            bottle.response.status = 400
            bottle.response.content_type = "text/plain; charset=utf-8"
            return "no text sent"
        print(f"Watch: {text}", flush=True)
        with brain_lock:
            reply = "".join(brain.reply(text))
        print(f"Legion: {reply}", flush=True)
        bottle.response.content_type = "text/plain; charset=utf-8"
        return clean_for_speech(reply)

    return app


def _synthesize_to_base64(synthesizer: Synthesizer, text: str) -> str:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp:
        temp_path = temp.name
    try:
        synthesizer.save_wav(text, Path(temp_path))
        return base64.b64encode(Path(temp_path).read_bytes()).decode("ascii")
    finally:
        Path(temp_path).unlink(missing_ok=True)


class _ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    """One thread per connection. wsgiref's own server handles them strictly one at a time, and a
    browser that opens a connection and then says nothing -- which Safari does routinely, to have
    one ready -- left every real request queued behind it, forever: the page sat on "thinking"."""

    daemon_threads = True

    def handle_error(self, request, client_address) -> None:  # noqa: ANN001 -- matches socketserver
        # A silent connection timing out, or a phone dropping one mid-handshake, is routine here,
        # and there's no console for the traceback to go to anyway.
        if not isinstance(sys.exc_info()[1], (OSError, ssl.SSLError)):
            super().handle_error(request, client_address)


class _QuietHandler(WSGIRequestHandler):
    # Bounds how long any one connection can sit silent, now that each has a thread of its own to
    # tie up. Only counts time spent waiting on the socket, never the model's thinking time.
    timeout = 30

    def log_request(self, *args, **kwargs) -> None:
        pass


class _ThreadedWSGIRefServer(bottle.WSGIRefServer):
    def run(self, app) -> None:  # noqa: ANN001 -- matches bottle.ServerAdapter's own signature
        self.srv = make_server(self.host, self.port, app, _ThreadingWSGIServer, _QuietHandler)
        self.port = self.srv.server_port
        self.srv.serve_forever()


class _SSLWSGIRefServer(_ThreadedWSGIRefServer):
    """bottle has no built-in HTTPS support; this wraps the same wsgiref server it already uses
    with a TLS socket, rather than pulling in a second, heavier server just for this."""

    def __init__(self, cert_path: Path, key_path: Path, **kwargs) -> None:
        super().__init__(**kwargs)
        self._cert_path = cert_path
        self._key_path = key_path

    def run(self, app) -> None:  # noqa: ANN001 -- matches bottle.ServerAdapter's own signature
        self.srv = make_server(self.host, self.port, app, _ThreadingWSGIServer, _QuietHandler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certfile=str(self._cert_path), keyfile=str(self._key_path))
        # Handshake in each connection's own thread, not in accept(): otherwise a client that
        # connects and never completes one stalls the accept loop itself, threads or no threads.
        self.srv.socket = context.wrap_socket(self.srv.socket, server_side=True, do_handshake_on_connect=False)
        self.port = self.srv.server_port
        self.srv.serve_forever()


def run_http(app: bottle.Bottle, host: str = "0.0.0.0", port: int = 8420) -> None:
    """Blocks serving ``app`` over plain HTTP -- call on a background thread if the calling thread
    is needed for something else (the GUI's own event loop, or run_https on another thread)."""
    bottle.run(app, server=_ThreadedWSGIRefServer(host=host, port=port, quiet=True), quiet=True)


def run_https(app: bottle.Bottle, cert_path: Path, key_path: Path, host: str = "0.0.0.0", port: int = 8443) -> None:
    """Blocks serving ``app`` over HTTPS with a self-signed certificate -- the only way a phone's
    browser will expose the microphone at all. Same threading note as run_http."""
    server = _SSLWSGIRefServer(cert_path, key_path, host=host, port=port, quiet=True)
    bottle.run(app, server=server, quiet=True)
