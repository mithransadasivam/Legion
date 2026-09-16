"""Legion's desktop window: a HUD showing what it's doing, instead of terminal text.

Renders legion/hud/index.html in a native window (WebView2 on Windows) and drives it by calling
straight into the page's own state functions -- no server, no build step, no second language.
"""

from __future__ import annotations

import json
import queue
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

_HUD_HTML = Path(__file__).parent / "hud" / "index.html"
_ICON = Path(__file__).parent / "assets" / "legion.ico"


class Hud:
    """Pushes state into the HUD window, and receives what the user typed into its input box.

    Safe to push state before the window has finished loading; calls made before then are dropped.
    """

    def __init__(self) -> None:
        self._window: Any = None
        self._queue: queue.Queue[tuple[str, str]] = queue.Queue()

    def attach(self, window: Any) -> None:
        self._window = window

    def submit(self, text: str) -> None:
        """Called from the page itself (as ``pywebview.api.submit``) when its input box is used."""
        self._enqueue("typed", text)

    def submit_voice(self, text: str) -> None:
        """Called by the voice watcher with whatever it transcribed, on the same queue typed
        input uses -- so the main loop can tell a follow-up is worth listening for without the
        wake word, which typed input never needs."""
        self._enqueue("voice", text)

    def _enqueue(self, source: str, text: str) -> None:
        text = text.strip()
        if text:
            self._queue.put((source, text))

    def wait_for_input(self, timeout: float | None = None) -> tuple[str, str] | None:
        """Block for (source, text) -- source is "typed" or "voice" -- until the window's input
        box is used or the voice watcher transcribes a command, or the timeout expires."""
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def set_config(self, *, model: str, host: str, voice: str, wake_phrase: str) -> None:
        self._call("setConfig", model, host, voice, wake_phrase)

    def set_mic(self, status: str) -> None:
        """The microphone's current status -- a name, or something like "(none detected)"."""
        self._call("setMic", status)

    def set_state(self, mode: str) -> None:
        self._call("setState", mode)

    def set_level(self, level: float) -> None:
        self._call("setLevel", round(level, 3))

    def set_readout(self, tag: str, text: str) -> None:
        self._call("setReadout", tag, text)

    def _call(self, function: str, *args: Any) -> None:
        if self._window is None:
            return
        js_args = ", ".join(json.dumps(arg) for arg in args)
        try:
            self._window.evaluate_js(f"{function}({js_args})")
        except Exception:
            pass  # the window may have just closed; a dropped HUD update is never worth crashing over


def run(target: Callable[[Hud], None], *, width: int = 560, height: int = 780) -> None:
    """Open the HUD window and run ``target(hud)`` on a background thread until the window closes."""
    import webview

    hud = Hud()
    window = webview.create_window(
        "Legion", str(_HUD_HTML), js_api=hud, width=width, height=height, background_color="#0a0d13"
    )
    loaded = threading.Event()
    window.events.loaded += loaded.set

    def _start() -> None:
        loaded.wait(timeout=10)
        hud.attach(window)
        try:
            target(hud)
        finally:
            # webview.start() blocks the main thread until every window closes. Without this, an
            # exception in target() -- EOFError from typed input hitting end-of-file is the one
            # that actually happened -- leaves the window open and the whole process hung forever,
            # since nothing else was ever going to close it.
            window.destroy()

    webview.start(_start, icon=str(_ICON) if _ICON.exists() else None)
