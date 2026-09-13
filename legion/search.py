"""Web search through DuckDuckGo, for the few questions Legion can't answer from memory.

Small models are hopeless at deciding when to search. Offered a search tool, llama3.2:3b
reaches for it even for "the capital of Australia" — a network round trip in front of every
reply, and the end of the one property Legion is built on. So a plain text gate decides
instead, and questions that don't depend on live information never touch the network.
"""

import re
from collections.abc import Callable
from typing import NamedTuple
from urllib.parse import urlparse

MAX_RESULTS = 4
TIMEOUT_SECONDS = 5
_SNIPPET_CHARS = 300

# An explicit order always wins, and only what follows it gets searched.
_ASKED_TO_SEARCH = re.compile(
    r"^\s*(?:legion[,\s]+)?(?:please\s+)?(?:could\s+you\s+|can\s+you\s+)?"
    r"(?:search(?:\s+the\s+web)?(?:\s+for)?|look\s+up|google)\s+(.+?)[?.!]*\s*$",
    re.IGNORECASE,
)

# Anything whose answer can change between now and next week. Erring towards searching is
# the cheap mistake: a needless search costs a few seconds, a missed one costs a wrong answer.
_NEEDS_LIVE_INFORMATION = re.compile(
    r"""\b(
        today | tonight | tomorrow | yesterday | right\s+now | currently | current |
        this\s+(?:week|weekend|month|year|morning|afternoon|evening) | latest | recent(?:ly)? |
        news | headlines? | weather | forecast | temps? | temperature | humidity |
        how\s+(?:hot|cold|warm|humid) | raining | rainy | snowing | will\s+it\s+(?:rain|snow) |
        what\s+time\s+is\s+it | open\s+(?:right\s+)?now | traffic |
        prices? | cost\s+of | stocks? | shares? | exchange\s+rate |
        scores? | who\s+won | winner | election | standings
    )\b""",
    re.IGNORECASE | re.VERBOSE,
)


class WebCheck(NamedTuple):
    """The outcome of checking the web for one question."""

    results: str
    """Handed to the model alongside the question, then dropped: it's bulky and goes stale."""
    record: str
    """Kept in the history, so "where did you get that?" has a true answer to give."""


NOT_CHECKED = WebCheck("", "")


def search_query(text: str) -> str | None:
    """What to look up for ``text``, or None when Legion should answer from what it knows."""
    if asked := _ASKED_TO_SEARCH.match(text):
        return asked.group(1).strip()
    return text.strip() if _NEEDS_LIVE_INFORMATION.search(text) else None


def lookup(text: str, announce: Callable[[], None] | None = None) -> WebCheck:
    """Check the web if the question needs live information.

    ``announce`` is called just before searching, so the few-second wait is visibly a search.
    """
    query = search_query(text)
    if not query:
        return NOT_CHECKED
    if announce:
        announce()
    results = _fetch(query)
    if not results:
        # Without this, a failed search looks exactly like no search, and the model guesses.
        return WebCheck(
            "You tried to check the web for this just now, but the search failed. Say you couldn't check.",
            "You tried to check the web to answer that, but the search failed.",
        )
    return WebCheck(
        f"Web results for {query!r}, fetched just now:\n" + "\n".join(map(_as_line, results)),
        "You checked the web to answer that, using " + ", ".join(dict.fromkeys(map(_site, results))) + ".",
    )


def search(query: str, max_results: int = MAX_RESULTS) -> str:
    """Return the top results as plain text, or '' if the search found nothing or failed."""
    return "\n".join(map(_as_line, _fetch(query, max_results)))


def _fetch(query: str, max_results: int = MAX_RESULTS) -> list[dict]:
    # Imported here because it pulls in lxml, and most runs never search.
    from ddgs import DDGS

    try:
        found = DDGS(timeout=TIMEOUT_SECONDS).text(query, max_results=max_results)
    except Exception:
        # Offline first: a failed search should cost one answer, not the conversation.
        return []
    return [result for result in found if result.get("title")]


def _as_line(result: dict) -> str:
    body = " ".join(str(result.get("body", "")).split())[:_SNIPPET_CHARS]
    return f"- {str(result['title']).strip()} ({_site(result)}): {body}"


def _site(result: dict) -> str:
    """The site a result came from, which is what a person means by "where did you get that?"."""
    return urlparse(str(result.get("href", ""))).netloc.removeprefix("www.") or "an unnamed site"
