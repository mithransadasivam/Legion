"""Turns streamed model output into clean, speakable sentences."""

import datetime
import re

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])[\"')\]]*\s+|\n+")
_MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_URL = re.compile(r"https?://\S+")
_LIST_MARKER = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+", re.MULTILINE)
_MARKUP = re.compile(r"[*_`#>~]+")
_EMOJI = re.compile(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]")


def clean_for_speech(text: str) -> str:
    """Strip markdown, links, and emoji that a voice would otherwise read aloud literally."""
    text = _MARKDOWN_LINK.sub(r"\1", text)
    text = _URL.sub("", text)
    text = _LIST_MARKER.sub("", text)
    text = _MARKUP.sub("", text)
    text = _EMOJI.sub("", text)
    return " ".join(text.split())


def speak_moment(moment: datetime.datetime, *, year: bool = False) -> str:
    """A date and time the way a person would say it, not %Y-%m-%d %H:%M:%S -- no leading zero
    on the hour or day, explicit AM/PM, and the year left out by default since it's rarely the
    point of a spoken answer."""
    hour12 = moment.hour % 12 or 12
    ampm = "AM" if moment.hour < 12 else "PM"
    base = f"{moment:%A}, {moment:%B} {moment.day}"
    if year:
        base += f", {moment.year}"
    return f"{base}, {hour12}:{moment.minute:02d} {ampm}"


def speak_date(day: datetime.date, *, year: bool = False) -> str:
    """The date-only half of ``speak_moment``, for all-day events with no time to speak."""
    base = f"{day:%A}, {day:%B} {day.day}"
    return f"{base}, {day.year}" if year else base


class SentenceBuffer:
    """Collects streamed tokens and releases whole sentences as soon as they end.

    Fragments shorter than ``min_chars`` are merged into the next sentence, so
    abbreviations like "Dr." and one-word replies don't produce choppy audio.
    """

    def __init__(self, min_chars: int = 20) -> None:
        self._buffer = ""
        self._min_chars = min_chars

    def feed(self, text: str) -> list[str]:
        self._buffer += text
        sentences = []
        while (cut := self._find_cut()) is not None:
            sentences.append(self._buffer[:cut].strip())
            self._buffer = self._buffer[cut:]
        return sentences

    def flush(self) -> list[str]:
        rest, self._buffer = self._buffer.strip(), ""
        return [rest] if rest else []

    def _find_cut(self) -> int | None:
        for match in _SENTENCE_BOUNDARY.finditer(self._buffer):
            if len(self._buffer[: match.start()].strip()) >= self._min_chars:
                return match.end()
        return None
