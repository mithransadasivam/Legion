"""Legion's desktop window: a HUD showing what it's doing, instead of terminal text.

Renders legion/hud/index.html in a native window (WebView2 on Windows) and drives it by calling
straight into the page's own state functions -- no server, no build step, no second language.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

_HUD_HTML = Path(__file__).parent / "hud" / "index.html"


class Hud:
    """Pushes state into the HUD window. Safe to call before the window has finished loading."""

    def __init__(self) -> None:
        self._window: Any = None

    def attach(self, window: Any) -> None:
        self._window = window

    def set_config(self, *, model: str, host: str, mic: str, voice: str, wake_phrase: str) -> None:
        self._call("setConfig", model, host, mic, voice, wake_phrase)

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
    window = webview.create_window("Legion", str(_HUD_HTML), width=width, height=height, background_color="#0a0d13")
    loaded = threading.Event()
    window.events.loaded += loaded.set

    def _start() -> None:
        loaded.wait(timeout=10)
        hud.attach(window)
        target(hud)

    webview.start(_start)
