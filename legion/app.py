"""Command-line entry point: wires speech recognition, the model, and speech output together."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from legion.brain import Brain
from legion.text import SentenceBuffer, clean_for_speech

if TYPE_CHECKING:
    from legion.audio import SpeechQueue


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    brain = Brain(model=args.model, host=args.host)
    try:
        brain.check()
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
    parser.add_argument("--save", type=Path, metavar="WAV", help="with --ask: write the spoken reply to a file")
    parser.add_argument("--quiet", action="store_true", help="print replies without speaking them")

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


def _voice_loop(args: argparse.Namespace, brain: Brain) -> None:
    from legion.audio import microphone_name, record_until_enter
    from legion.stt import SAMPLE_RATE, Transcriber

    print(f"Microphone: {microphone_name(args.mic, SAMPLE_RATE)}")
    speech = None if args.quiet else _start_speech(args.voice)
    print("Loading speech recognition...", flush=True)
    transcriber = Transcriber(args.whisper)
    print("Legion is online. Press Enter to talk, Enter again to stop. Ctrl+C to quit.")
    while True:
        input("\n[Enter] to talk ")
        print("● Listening... [Enter] to stop", flush=True)
        text = transcriber.transcribe(record_until_enter(SAMPLE_RATE, args.mic))
        if not text:
            print("(Didn't catch that.)")
            continue
        print(f"You: {text}")
        _respond(brain, text, speech)


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
        _respond(brain, question, None if args.quiet else _start_speech(args.voice))
    return 0


def _respond(brain: Brain, text: str, speech: SpeechQueue | None) -> str:
    """Print the reply as it streams, speaking each sentence as soon as it's complete."""
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
        speech.wait()
    return "".join(reply)
