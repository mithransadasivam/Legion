"""Command-line entry point: wires speech recognition, the model, and speech output together."""

from __future__ import annotations

import argparse
import os
import sys
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

from legion.brain import Brain
from legion.memory import DEFAULT_FILE, Memory
from legion.search import lookup
from legion.text import SentenceBuffer, clean_for_speech

if TYPE_CHECKING:
    import numpy as np

    from legion.audio import SpeechQueue
    from legion.wake import WakeWord


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
        if args.text:
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


def _announce_notes(notes: list[str]) -> None:
    # Printed, never spoken, so it's always clear what Legion is keeping about you.
    print(f"(noted: {' '.join(notes)}) ", end="", flush=True)


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


def _respond(brain: Brain, text: str, speech: SpeechQueue | None) -> str:
    """Print the reply as it streams and queue each sentence for speech; returns before speech finishes."""
    print("Legion: ", end="", flush=True)
    sentences = SentenceBuffer()
    reply: list[str] = []
    for token in brain.reply(text):
        print(token, end="", flush=True)
        reply.append(token)
        if speech:
            for sentence in sentences.feed(token):
                speech.say(clean_for_speech(sentence))
    print()
    if speech:
        for sentence in sentences.flush():
            speech.say(clean_for_speech(sentence))
    return "".join(reply)
