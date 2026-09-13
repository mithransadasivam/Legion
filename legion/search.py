"""Web search through DuckDuckGo, for the few questions Legion can't answer from memory.

Small models are hopeless at deciding when to search. Offered a search tool, llama3.2:3b
reaches for it even for "the capital of Australia" — a network round trip in front of every
reply, and the end of the one property Legion is built on. So a plain text gate decides
instead, and questions that don't depend on live information never touch the network.
"""

import re

MAX_RESULTS = 4
TIMEOUT_SECONDS = 5
_SNIPPET_CHARS = 300

# An explicit order always wins, and only what follows it gets searched.
_ASKED_TO_SEARCH = re.compile(
    r"^\s*(?:legion[,\s]+)?(?:please\s+)?(?:could\s+you\s+|can\s+you\s+)?"
    r"(?:search(?:\s+the\s+web)?(?:\s+for)?|look\s+up|google)\s+(.+?)[?.!]*\s*$",
    re.IGNORECASE,
)

# Anything whose answer can change between now and next week.
_NEEDS_LIVE_INFORMATION = re.compile(
    r"""\b(
        today | tonight | tomorrow | yesterday | right\s+now | currently | current |
        this\s+(?:week|month|year|morning|afternoon|evening) | latest | recent(?:ly)? |
        news | headlines? | weather | forecast | temperature |
        prices? | cost\s+of | stocks? | shares? | exchange\s+rate |
        scores? | who\s+won | winner | election | standings
    )\b""",
    re.IGNORECASE | re.VERBOSE,
)


def search_query(text: str) -> str | None:
    """What to look up for ``text``, or None when Legion should answer from what it knows."""
    if asked := _ASKED_TO_SEARCH.match(text):
        return asked.group(1).strip()
    return text.strip() if _NEEDS_LIVE_INFORMATION.search(text) else None


def lookup(text: str) -> str:
    """Search the web if the question needs live information, and return '' when it doesn't."""
    query = search_query(text)
    return search(query) if query else ""


def search(query: str, max_results: int = MAX_RESULTS) -> str:
    """Return the top results as plain text, or '' if the search found nothing or failed."""
    # Imported here because it pulls in lxml, and most runs never search.
    from ddgs import DDGS

    try:
        results = DDGS(timeout=TIMEOUT_SECONDS).text(query, max_results=max_results)
    except Exception:
        # Offline first: a failed search should cost one answer, not the conversation.
        return ""
    return "\n".join(_as_line(result) for result in results if result.get("title"))


def _as_line(result: dict) -> str:
    body = " ".join(str(result.get("body", "")).split())[:_SNIPPET_CHARS]
    return f"- {str(result['title']).strip()}: {body}"
