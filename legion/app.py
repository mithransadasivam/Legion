"""Command-line entry point: wires speech recognition, the model, and speech output together."""

from __future__ import annotations

import argparse
import os
import sys
import threading
import time
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

from legion.brain import Brain
from legion.memory import DEFAULT_FILE, Memory
from legion.search import lookup
from legion.text import SentenceBuffer, clean_for_speech

if TYPE_CHECKING:
    from collections.abc import Callable

    import numpy as np

    from legion.audio import SpeechQueue
    from legion.gui import Hud
    from legion.stt import Transcriber
    from legion.wake import WakeWord

# Set only while the GUI window is running, so the search/memory announce hooks below -- shared
# with every other mode -- can also mirror themselves onto the HUD without threading a parameter
# through Brain, which is built once in main() before the mode is even chosen.
_active_hud: Hud | None = None


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    web = None if args.no_search else partial(lookup, announce=_announce_search)
    try:
        memory = None if args.no_memory else Memory(args.memory, args.host, args.model, on_noted=_announce_notes)
        brain = Brain(model=args.model, host=args.host, lookup=web, memory=memory)
        brain.check()
        print("Loading model...", flush=True)
        brain.load()
        if memory:
            print(f"Memory: {len(memory.notes)} notes in {args.memory}")
        if args.ask:
            return _answer_recording(args, brain)
        if args.gui:
            _gui_loop(args, brain)
        elif args.text:
            _text_loop(brain, None if args.quiet else _start_speech(args.voice))
        else:
            _voice_loop(args, brain)
    except RuntimeError as exc:
        print(f"legion: {exc}", file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print("\nStanding down.")
    return 0


def _announce_search() -> None:
    # Printed, never spoken: it explains the pause, and shows which answers came from the web.
    print("(checking the web) ", end="", flush=True)
    if _active_hud:
        _active_hud.set_readout("PROCESSING", "checking the web...")


def _announce_notes(notes: list[str]) -> None:
    # Printed, never spoken, so it's always clear what Legion is keeping about you.
    print(f"(noted: {' '.join(notes)}) ", end="", flush=True)
    if _active_hud:
        _active_hud.set_readout("NOTED", " ".join(notes))


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="legion", description="A local, offline voice assistant.")
    parser.add_argument(
        "--model",
        default=os.environ.get("LEGION_MODEL", "llama3.2:3b"),
        help="Ollama model to talk to (default: %(default)s)",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("LEGION_OLLAMA_HOST", "http://127.0.0.1:11434"),
        help="Ollama server URL; point it at another machine to borrow its GPU (default: %(default)s)",
    )
    parser.add_argument(
        "--whisper",
        default=os.environ.get("LEGION_WHISPER_MODEL", "base.en"),
        help="faster-whisper model size (default: %(default)s)",
    )
    parser.add_argument(
        "--voice",
        default=os.environ.get("LEGION_VOICE", "en_GB-alan-medium"),
        help="Piper voice (default: %(default)s)",
    )
    parser.add_argument(
        "--mic",
        type=lambda value: int(value) if value.isdigit() else value,
        default=os.environ.get("LEGION_MIC"),
        help="microphone name (or part of it) or device number; list them with: python -m sounddevice",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--text", action="store_true", help="type instead of talking")
    mode.add_argument("--ask", type=Path, metavar="WAV", help="answer a recorded question, then exit")
    mode.add_argument(
        "--wake",
        action="store_true",
        default=os.environ.get("LEGION_WAKE") == "1",
        help="hands-free: say the wake word to talk, instead of pressing Enter",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        default=os.environ.get("LEGION_GUI") == "1",
        help="open a HUD window alongside the terminal; hands-free via the wake word, or combine "
        "with --text to type without a microphone",
    )
    parser.add_argument(
        "--wake-model",
        default=os.environ.get("LEGION_WAKE_MODEL", "hey_jarvis"),
        help="wake word: a built-in name, or the path to a custom .onnx model (default: %(default)s)",
    )
    parser.add_argument(
        "--wake-threshold",
        type=float,
        default=float(os.environ.get("LEGION_WAKE_THRESHOLD", "0.5")),
        help="how sure the wake word model must be, from 0 to 1; raise it if Legion wakes by mistake (default: %(default)s)",
    )
    parser.add_argument("--save", type=Path, metavar="WAV", help="with --ask: write the spoken reply to a file")
    parser.add_argument("--quiet", action="store_true", help="print replies without speaking them")
    parser.add_argument(
        "--no-search",
        action="store_true",
        default=os.environ.get("LEGION_SEARCH", "1") == "0",
        help="stay fully offline: never look anything up, even for questions about live information",
    )
    parser.add_argument(
        "--memory",
        type=Path,
        metavar="FILE",
        default=Path(os.environ.get("LEGION_MEMORY_FILE", DEFAULT_FILE)),
        help="where Legion keeps its notes about you (default: %(default)s)",
    )
    parser.add_argument(
        "--no-memory",
        action="store_true",
        default=os.environ.get("LEGION_MEMORY", "1") == "0",
        help="don't remember anything between sessions, or take new notes",
    )

    args = parser.parse_args(argv)
    if args.save and not args.ask:
        parser.error("--save only works with --ask")
    if args.save and args.quiet:
        parser.error("--save and --quiet contradict each other")
    if args.gui and args.ask:
        parser.error("--gui doesn't work with --ask: --ask answers one recording and exits, --gui keeps a window open")
    return args


def _start_speech(voice: str) -> SpeechQueue:
    from legion.audio import SpeechQueue
    from legion.tts import Synthesizer

    print("Loading voice...", flush=True)
    return SpeechQueue(Synthesizer(voice))


def _text_loop(brain: Brain, speech: SpeechQueue | None) -> None:
    print("Legion is online. Type a message, Ctrl+C to quit.")
    while True:
        text = input("\nYou: ").strip()
        if text:
            _respond(brain, text, speech)
            if speech:
                speech.wait()


def _voice_loop(args: argparse.Namespace, brain: Brain) -> None:
    from legion.audio import microphone_name
    from legion.stt import SAMPLE_RATE, Transcriber

    print(f"Microphone: {microphone_name(args.mic, SAMPLE_RATE)}")
    speech = None if args.quiet else _start_speech(args.voice)
    print("Loading speech recognition...", flush=True)
    transcriber = Transcriber(args.whisper)
    if args.wake:
        from legion.wake import WakeWord

        print("Loading wake word...", flush=True)
        wake = WakeWord(args.wake_model, args.wake_threshold)
        print(f'Legion is online. Say "{wake.phrase}", then your question; it stops listening when you do.')
    else:
        print("Legion is online. Press Enter to talk, Enter again to stop.")
    print("Press Enter while Legion is talking to cut in. Ctrl+C to quit.")
    cut_in = False
    while True:
        audio = _hear_after_wake_word(wake, args.mic, cut_in) if args.wake else _record_after_enter(args.mic, cut_in)
        text = transcriber.transcribe(audio) if audio.size else ""
        if not text:
            print("(Didn't catch that.)")
            cut_in = False
            continue
        print(f"You: {text}")
        _respond(brain, text, speech)
        cut_in = speech is not None and _wait_unless_cut_in(speech)


def _record_after_enter(mic: int | str | None, cut_in: bool) -> np.ndarray:
    from legion.audio import record_until_enter
    from legion.keys import discard_pending_keys
    from legion.stt import SAMPLE_RATE

    if not cut_in:
        discard_pending_keys()
        input("\n[Enter] to talk ")
    discard_pending_keys()
    print("● Listening... [Enter] to stop", flush=True)
    return record_until_enter(SAMPLE_RATE, mic)


def _hear_after_wake_word(wake: WakeWord, mic: int | str | None, cut_in: bool) -> np.ndarray:
    # After a cut-in the user is already talking, so there's no wake word to wait for.
    if not cut_in:
        print(f'\n(say "{wake.phrase}")', flush=True)
    return wake.listen(mic, on_wake=lambda: print("● Listening...", flush=True), wake_first=not cut_in)


def _gui_loop(args: argparse.Namespace, brain: Brain) -> None:
    """The conversation shown in a HUD window instead of the terminal.

    With --text, the window's own input box is the only way in: no microphone is ever touched.
    Otherwise both a spoken greeting and the input box work at once -- say "hey", "hi", "legion",
    a time-of-day greeting, or type, whichever's easier at the time (see legion/greeting.py for
    the full list and why a trained wake word isn't used here) -- and a background watcher
    re-detects the microphone every couple of seconds, so reconnecting a headset partway through a
    session picks it back up without restarting Legion. Point --mic at a name rather than a number
    for that to survive a reconnect: Windows can hand a reconnected device a new number, but its
    name doesn't change.

    No cut-in yet: interrupting Legion mid-reply isn't supported from either voice or the box.
    """
    from legion.audio import SpeechQueue
    from legion.gui import run
    from legion.tts import Synthesizer

    global _active_hud

    synthesizer = None
    if not args.quiet:
        print("Loading voice...", flush=True)
        synthesizer = Synthesizer(args.voice)

    wake = None
    transcriber = None
    if args.text:
        print("Opening the Legion window. Type into it; close the window to quit.")
    else:
        from legion.stt import Transcriber
        from legion.wake import WakeWord

        # These don't need a microphone to exist yet -- only actually listening does, and that's
        # handled by _voice_watcher, which tolerates one not being connected at all. model=None:
        # no trained wake word, just the voice activity detector openWakeWord ships alongside one.
        print("Loading speech recognition...", flush=True)
        transcriber = Transcriber(args.whisper)
        wake = WakeWord(model=None)
        print('Opening the Legion window. Greet it ("hey", "hi", "legion", ...) or type; close the window to quit.')

    def worker(hud: Hud) -> None:
        global _active_hud
        _active_hud = hud
        speech = SpeechQueue(synthesizer, on_level=hud.set_level) if synthesizer else None
        hud.set_config(model=args.model, host=args.host, voice=args.voice, wake_phrase="a greeting" if wake else "(typing only)")

        busy = threading.Event()
        # Set right after a voice-originated reply finishes, so the watcher's next listen skips
        # straight to capture -- a follow-up shouldn't need a greeting repeated.
        follow_up = threading.Event()
        if wake:
            threading.Thread(target=_voice_watcher, args=(args.mic, wake, transcriber, hud, busy, follow_up), daemon=True).start()
        else:
            hud.set_mic("(typing only, no microphone)")

        try:
            while True:
                hud.set_state("idle")
                hud.set_readout(
                    "STANDBY",
                    'Say "hey", "hi", "legion" (or type above).' if wake else "Type your question above, then press Enter.",
                )
                heard = hud.wait_for_input()
                if not heard:
                    continue
                source, text = heard
                busy.set()
                hud.set_state("thinking")
                print(f"You: {text}")
                hud.set_readout("HEARD", text)
                _respond(brain, text, speech, hud=hud)
                if speech:
                    speech.wait()
                hud.set_level(0)
                busy.clear()
                if source == "voice":
                    follow_up.set()
        except KeyboardInterrupt:
            # gui.run() always closes the window once this function returns, either way.
            print("\nStanding down.")

    run(worker)


_MIC_POLL_SECONDS = 2.0
_FOLLOW_UP_SECONDS = 6.0
_SPEECH_LEVEL_THRESHOLD = 0.08


def _speech_reactive(hud: Hud) -> Callable[[float], None]:
    """Wraps hud.set_level so the HUD only shows "listening" once actual speech is heard, not the
    instant a capture cycle starts -- with no wake word, a cycle begins on a plain timer, and
    flashing the state every empty poll would just be visual noise."""
    woken = False

    def on_level(level: float) -> None:
        nonlocal woken
        if not woken and level > _SPEECH_LEVEL_THRESHOLD:
            hud.set_state("listening")
            woken = True
        hud.set_level(level)

    return on_level


def _voice_watcher(
    mic_arg: int | str | None,
    wake: WakeWord,
    transcriber: Transcriber,
    hud: Hud,
    busy: threading.Event,
    follow_up: threading.Event,
) -> None:
    """Runs for the life of the window: re-detects the microphone every couple of seconds and, once
    one's connected, waits for speech and transcribes it -- pushing it onto the same queue the
    input box uses only if legion.greeting recognizes it as addressed to Legion (skipped for a
    follow-up, which is already known to be). Backs off and retries on any error, which is what
    actually happens when a Bluetooth headset disconnects mid-recording, and pauses around a reply
    already in progress rather than letting two conversations run at once.

    ``follow_up`` sends the next capture straight through with no greeting required, whether that's
    because Legion just answered something spoken, or because the last thing heard was a greeting
    with nothing after it ("Legion?") -- either way, a repeated greeting would be redundant.
    """
    from legion.greeting import strip_greeting

    while True:
        if busy.is_set():
            time.sleep(_MIC_POLL_SECONDS)
            continue
        device, label = _resolve_mic(mic_arg)
        if device is None:
            hud.set_mic("(none detected)")
            time.sleep(_MIC_POLL_SECONDS)
            continue
        hud.set_mic(label)
        skip_greeting_check = follow_up.is_set()
        follow_up.clear()
        hud.set_state("idle")
        if skip_greeting_check:
            hud.set_readout("LISTENING", "Go ahead, or stay quiet to go back to standby.")
        try:
            heard = wake.listen(
                device,
                wake_first=False,
                on_level=_speech_reactive(hud),
                stop_check=busy.is_set,
                wait_for_speech=_FOLLOW_UP_SECONDS if skip_greeting_check else 5.0,
            )
        except Exception:
            hud.set_level(0)
            time.sleep(_MIC_POLL_SECONDS)
            continue
        hud.set_level(0)
        if heard.size == 0:
            continue
        hud.set_state("thinking")
        hud.set_readout("PROCESSING", "")
        text = transcriber.transcribe(heard)
        if not text:
            hud.set_state("idle")
            continue

        if skip_greeting_check:
            question = text
        else:
            question = strip_greeting(text)
            if question is None:
                # Not addressed to Legion -- background chatter, someone else's name, the TV.
                # Say nothing and just keep listening.
                continue
            if question == "":
                # "Legion?" and nothing else: addressed to Legion, but no question in it yet.
                follow_up.set()
                continue
        hud.submit_voice(question)


def _resolve_mic(mic_arg: int | str | None) -> tuple[int | str | None, str] | tuple[None, None]:
    """The current device for ``mic_arg`` and its display name, or (None, None) if it's not there
    right now. A name is re-searched by name each time, so a reconnect landing on a new device
    number is still found; a number or the system default is just tried as given."""
    from legion.audio import find_input_device, microphone_name
    from legion.stt import SAMPLE_RATE

    if isinstance(mic_arg, str):
        device = find_input_device(mic_arg, SAMPLE_RATE)
        if device is None:
            return None, None
        return device, microphone_name(device, SAMPLE_RATE)
    try:
        return mic_arg, microphone_name(mic_arg, SAMPLE_RATE)
    except RuntimeError:
        return None, None


def _wait_unless_cut_in(speech: SpeechQueue) -> bool:
    """Let Legion finish talking, unless the user presses Enter first. Returns True if they cut in."""
    from legion.keys import discard_pending_keys, enter_pressed

    # A press made while the model was still thinking would silence Legion before it said a word.
    discard_pending_keys()
    while not speech.wait(timeout=0.05):
        if enter_pressed():
            speech.interrupt()
            speech.wait()
            print("\n(Cut in.)")
            return True
    return False


def _answer_recording(args: argparse.Namespace, brain: Brain) -> int:
    from legion.stt import Transcriber

    question = Transcriber(args.whisper).transcribe(str(args.ask))
    if not question:
        print("legion: no speech found in that recording", file=sys.stderr)
        return 1
    print(f"You: {question}")

    if args.save:
        from legion.tts import Synthesizer

        reply = _respond(brain, question, speech=None)
        Synthesizer(args.voice).save_wav(clean_for_speech(reply), args.save)
        print(f"Reply saved to {args.save}")
    else:
        speech = None if args.quiet else _start_speech(args.voice)
        _respond(brain, question, speech)
        if speech:
            speech.wait()
    return 0


def _respond(brain: Brain, text: str, speech: SpeechQueue | None, hud: Hud | None = None) -> str:
    """Print the reply as it streams and queue each sentence for speech; returns before speech finishes."""
    print("Legion: ", end="", flush=True)
    sentences = SentenceBuffer()
    reply: list[str] = []
    speaking = False
    for token in brain.reply(text):
        print(token, end="", flush=True)
        reply.append(token)
        if hud:
            if not speaking:
                # The first token is the moment generation actually starts, after any search --
                # exactly when "thinking" should give way to "speaking" in the HUD.
                hud.set_state("speaking")
                speaking = True
            hud.set_readout("REPLY", "".join(reply))
        if speech:
            for sentence in sentences.feed(token):
                speech.say(clean_for_speech(sentence))
    print()
    if speech:
        for sentence in sentences.flush():
            speech.say(clean_for_speech(sentence))
    return "".join(reply)
