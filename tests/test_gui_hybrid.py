"""Unit coverage for the hybrid --gui logic in app.py: re-detecting the microphone (including a
reconnect landing on a new device number) and how the voice watcher uses that detection. No real
audio device, no real window -- see tests/test_gui_roundtrip.py for the real-pipeline check."""

import threading
import time

import pytest

import legion.app as app_module

APIS = [{"name": "MME"}, {"name": "Windows WASAPI"}]


class FakeDevices:
    """A stand-in for sounddevice's device table that can change mid-test, the way a real
    reconnect changes it -- and, crucially, can hand a device a different index than before."""

    def __init__(self, monkeypatch):
        import sounddevice as sd

        self._table = []

        def query_devices(device=None, kind=None):
            if device is None:
                return self._table
            if not 0 <= device < len(self._table):
                raise sd.PortAudioError("Invalid device")
            return self._table[device]

        monkeypatch.setattr("sounddevice.query_devices", query_devices)
        monkeypatch.setattr("sounddevice.query_hostapis", lambda index=None: APIS if index is None else APIS[index])
        monkeypatch.setattr("sounddevice.check_input_settings", lambda **kwargs: None)

    def set(self, *devices):
        self._table = list(devices)


MME_HEADSET = {"name": "Headset (WH-1000XM4)", "max_input_channels": 1, "hostapi": 0}


class TestResolveMic:
    def test_a_name_that_is_not_connected_resolves_to_nothing(self, monkeypatch):
        FakeDevices(monkeypatch).set()

        assert app_module._resolve_mic("XM4") == (None, None)

    def test_a_reconnect_landing_on_a_different_device_number_is_still_found(self, monkeypatch):
        devices = FakeDevices(monkeypatch)
        devices.set({"name": "Other Mic", "max_input_channels": 1, "hostapi": 0}, MME_HEADSET)
        first = app_module._resolve_mic("XM4")

        # Simulates a reconnect: the device table is rebuilt and the headset now sits at index 0.
        devices.set(MME_HEADSET, {"name": "Other Mic", "max_input_channels": 1, "hostapi": 0})
        second = app_module._resolve_mic("XM4")

        assert first == (1, "Headset (WH-1000XM4)")
        assert second == (0, "Headset (WH-1000XM4)"), "the new device number should still be found by name"

    def test_a_fixed_device_number_that_is_not_connected_resolves_to_nothing(self, monkeypatch):
        FakeDevices(monkeypatch).set()

        assert app_module._resolve_mic(3) == (None, None)


class FakeWakeWord:
    def __init__(self, results):
        self.phrase = "hey jarvis"
        self._results = iter(results)
        self.calls = []

    def listen(self, device, on_wake=None, on_level=None, stop_check=None, wake_first=True, wait_for_speech=5.0):
        self.calls.append({"device": device, "wake_first": wake_first, "wait_for_speech": wait_for_speech})
        result = next(self._results)
        if isinstance(result, Exception):
            raise result
        return result


class FakeTranscriber:
    def __init__(self, text):
        self._text = text

    def transcribe(self, audio):
        return self._text


class RecordingHud:
    def __init__(self):
        self.mic_status: list[str] = []
        self.submitted: list[str] = []
        self.states: list[str] = []

    def set_mic(self, status):
        self.mic_status.append(status)

    def submit_voice(self, text):
        self.submitted.append(text)

    def set_state(self, mode):
        self.states.append(mode)

    def set_level(self, level):
        pass

    def set_readout(self, tag, text):
        pass


def run_watcher_briefly(wake, transcriber, hud, busy, follow_up=None, seconds=0.3):
    args = ("XM4", wake, transcriber, hud, busy, follow_up if follow_up is not None else threading.Event())
    thread = threading.Thread(target=app_module._voice_watcher, args=args, daemon=True)
    thread.start()
    time.sleep(seconds)
    return thread


class TestVoiceWatcher:
    @pytest.fixture(autouse=True)
    def fast_polling(self, monkeypatch):
        monkeypatch.setattr(app_module, "_MIC_POLL_SECONDS", 0.05)

    def test_a_transcribed_command_is_submitted_the_same_way_typed_text_is(self, monkeypatch):
        import numpy as np

        FakeDevices(monkeypatch).set(MME_HEADSET)
        wake = FakeWakeWord([np.ones(100, dtype=np.float32)])
        hud = RecordingHud()

        run_watcher_briefly(wake, FakeTranscriber("what's the weather"), hud, threading.Event())

        assert hud.submitted == ["what's the weather"]

    def test_the_microphone_status_is_reported_before_it_connects_and_after(self, monkeypatch):
        import numpy as np

        devices = FakeDevices(monkeypatch)
        devices.set()
        wake = FakeWakeWord([np.ones(100, dtype=np.float32)])
        hud = RecordingHud()
        busy = threading.Event()

        thread = threading.Thread(
            target=app_module._voice_watcher, args=("XM4", wake, FakeTranscriber("hi"), hud, busy, threading.Event()), daemon=True
        )
        thread.start()
        time.sleep(app_module._MIC_POLL_SECONDS + 0.05)
        assert "(none detected)" in hud.mic_status

        devices.set(MME_HEADSET)
        time.sleep(app_module._MIC_POLL_SECONDS + 0.05)
        assert "Headset (WH-1000XM4)" in hud.mic_status

    def test_the_watcher_never_starts_listening_while_a_reply_is_in_progress(self, monkeypatch):
        FakeDevices(monkeypatch).set(MME_HEADSET)
        wake = FakeWakeWord([RuntimeError("should not have been called")])
        hud = RecordingHud()
        busy = threading.Event()
        busy.set()

        run_watcher_briefly(wake, FakeTranscriber("hi"), hud, busy, seconds=app_module._MIC_POLL_SECONDS * 3)

        assert wake.calls == [], "no wake.listen() call should happen while busy is set"

    def test_a_stream_error_from_a_disconnect_mid_recording_is_absorbed_and_retried(self, monkeypatch):
        import numpy as np

        FakeDevices(monkeypatch).set(MME_HEADSET)
        wake = FakeWakeWord([OSError("device disappeared"), np.ones(100, dtype=np.float32)])
        hud = RecordingHud()

        run_watcher_briefly(wake, FakeTranscriber("still here"), hud, threading.Event(), seconds=app_module._MIC_POLL_SECONDS + 0.05)

        assert hud.submitted == ["still here"], "the watcher should recover instead of dying on one bad cycle"

    def test_empty_speech_is_not_submitted(self, monkeypatch):
        import numpy as np

        FakeDevices(monkeypatch).set(MME_HEADSET)
        wake = FakeWakeWord([np.zeros(0, dtype=np.float32)])
        hud = RecordingHud()

        run_watcher_briefly(wake, FakeTranscriber("should not be reached"), hud, threading.Event())

        assert hud.submitted == []

    def test_a_pending_follow_up_skips_the_wake_word_for_one_listen(self, monkeypatch):
        import numpy as np

        FakeDevices(monkeypatch).set(MME_HEADSET)
        wake = FakeWakeWord([np.ones(100, dtype=np.float32), np.ones(100, dtype=np.float32)])
        hud = RecordingHud()
        follow_up = threading.Event()
        follow_up.set()

        run_watcher_briefly(wake, FakeTranscriber("a follow-up"), hud, threading.Event(), follow_up=follow_up)

        assert wake.calls[0]["wake_first"] is False, "the follow-up itself should not require the wake word"
        assert wake.calls[0]["wait_for_speech"] == app_module._FOLLOW_UP_SECONDS

    def test_the_follow_up_flag_is_only_honoured_once(self, monkeypatch):
        import numpy as np

        FakeDevices(monkeypatch).set(MME_HEADSET)
        wake = FakeWakeWord([np.ones(100, dtype=np.float32) for _ in range(3)])
        hud = RecordingHud()
        follow_up = threading.Event()
        follow_up.set()

        run_watcher_briefly(wake, FakeTranscriber("hi"), hud, threading.Event(), follow_up=follow_up, seconds=0.4)

        assert wake.calls[0]["wake_first"] is False
        assert all(call["wake_first"] is True for call in wake.calls[1:]), (
            "later cycles should require the wake word again, or every reply would leave the mic wide open"
        )

    def test_without_a_pending_follow_up_the_wake_word_is_required_as_usual(self, monkeypatch):
        import numpy as np

        FakeDevices(monkeypatch).set(MME_HEADSET)
        wake = FakeWakeWord([np.ones(100, dtype=np.float32)])
        hud = RecordingHud()

        run_watcher_briefly(wake, FakeTranscriber("hi"), hud, threading.Event(), follow_up=threading.Event())

        assert wake.calls[0]["wake_first"] is True
        assert wake.calls[0]["wait_for_speech"] == 5.0
