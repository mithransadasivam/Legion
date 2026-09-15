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
