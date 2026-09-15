import sys
import types

import pytest

from legion.gui import Hud


class FakeWindow:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def evaluate_js(self, script: str) -> None:
        self.calls.append(script)


class TestHud:
    def test_calls_before_the_window_is_attached_are_dropped_silently(self):
        Hud().set_state("listening")  # must not raise

    def test_set_state_calls_the_page_s_setstate(self):
        hud, window = Hud(), FakeWindow()
        hud.attach(window)

        hud.set_state("listening")

        assert window.calls == ['setState("listening")']

    def test_text_arguments_are_safely_quoted_for_javascript(self):
        hud, window = Hud(), FakeWindow()
        hud.attach(window)

        hud.set_readout("HEARD", 'He said "stop", then left.')

        assert window.calls == ['setReadout("HEARD", "He said \\"stop\\", then left.")']

    def test_set_config_passes_every_field_in_order(self):
        hud, window = Hud(), FakeWindow()
        hud.attach(window)

        hud.set_config(model="llama3.2:3b", host="http://127.0.0.1:11434", mic="XM4", voice="en_GB-alan-medium", wake_phrase="hey jarvis")

        assert window.calls == [
            'setConfig("llama3.2:3b", "http://127.0.0.1:11434", "XM4", "en_GB-alan-medium", "hey jarvis")'
        ]

    def test_a_dead_window_does_not_crash_the_caller(self):
        class DeadWindow:
            def evaluate_js(self, script: str) -> None:
                raise RuntimeError("window was closed")

        hud = Hud()
        hud.attach(DeadWindow())

        hud.set_state("idle")  # must not raise


class _FiringEvent:
    """Stands in for one pywebview event: fires the callback the moment it's added, since these
    tests never wait on a real page load."""

    def __iadd__(self, callback):
        callback()
        return self


class FakeWebviewWindow(FakeWindow):
    def __init__(self) -> None:
        super().__init__()
        self.events = types.SimpleNamespace(loaded=_FiringEvent())
        self.destroyed = False

    def destroy(self) -> None:
        self.destroyed = True


def _fake_webview(window):
    """A stand-in for the pywebview module: create_window returns ``window``, and start runs the
    given function immediately instead of opening a real GUI loop."""
    return types.SimpleNamespace(create_window=lambda *a, **k: window, start=lambda fn: fn())


class TestRun:
    def test_the_window_is_destroyed_even_when_the_worker_crashes(self, monkeypatch):
        # This is the actual bug: --gui --text hung forever after typed input ran out, because
        # EOFError killed the background thread and nothing else was ever going to close the window.
        window = FakeWebviewWindow()
        monkeypatch.setitem(sys.modules, "webview", _fake_webview(window))
        from legion.gui import run

        def worker(hud):
            raise EOFError("stdin closed")

        with pytest.raises(EOFError):
            run(worker)

        assert window.destroyed

    def test_the_window_is_also_destroyed_after_an_ordinary_return(self, monkeypatch):
        window = FakeWebviewWindow()
        monkeypatch.setitem(sys.modules, "webview", _fake_webview(window))
        from legion.gui import run

        run(lambda hud: None)

        assert window.destroyed
