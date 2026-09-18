"""Conversation with a local model served by Ollama."""

import datetime
from collections.abc import Callable, Iterator

import ollama

from legion.calc import lookup as calc_lookup
from legion.gcal import CALENDAR_NOT_CHECKED, CalendarCheck
from legion.memory import Memory
from legion.persona import CALENDAR_AWARE, RESEARCH_AWARE, SEARCH_SYSTEM_PROMPT, SIR, SYSTEM_PROMPT
from legion.research import NOT_CHECKED as RESEARCH_NOT_CHECKED
from legion.research import ResearchCheck
from legion.search import NOT_CHECKED, WebCheck
from legion.text import speak_moment


class Brain:
    def __init__(
        self,
        model: str,
        host: str,
        max_turns: int = 8,
        lookup: Callable[[str], WebCheck] | None = None,
        calendar_lookup: Callable[[str], CalendarCheck] | None = None,
        research_lookup: Callable[[str], ResearchCheck] | None = None,
        memory: Memory | None = None,
    ) -> None:
        self._client = ollama.Client(host=host)
        self._model = model
        self._host = host
        self._history: list[dict[str, str]] = []
        self._max_messages = max_turns * 2
        self._lookup = lookup
        self._calendar_lookup = calendar_lookup
        self._research_lookup = research_lookup
        self._system_prompt = SEARCH_SYSTEM_PROMPT if lookup else SYSTEM_PROMPT
        self._memory = memory
        self._last_web_record = ""
        self._last_calendar_record = ""
        self._last_research_record = ""

    def check(self) -> None:
        """Raise RuntimeError with a fix-it hint if the server or model isn't available."""
        try:
            installed = {m.model for m in self._client.list().models}
        except ConnectionError:
            raise RuntimeError(f"can't reach Ollama at {self._host}. Start it with: ollama serve") from None
        if self._model not in installed and f"{self._model}:latest" not in installed:
            raise RuntimeError(f"model {self._model!r} isn't installed. Get it with: ollama pull {self._model}")

    def load(self) -> None:
        """Load the model into memory now, rather than stalling the first reply for several seconds."""
        self._client.generate(model=self._model, prompt="")

    def reply(self, text: str) -> Iterator[str]:
        """Stream a reply token by token, keeping recent turns as conversational context."""
        self._history.append({"role": "user", "content": text})
        if self._memory:
            # Before replying, so a fact told just now is already known, and taking notes can never
            # overlap the moment the user might press Enter to cut Legion off.
            self._memory.learn(text)
        messages = [{"role": "system", "content": self._prompt()}, *self._history]
        if self._last_web_record:
            # Whether the previous reply came from the web, so "where did you get that?" is answered
            # honestly. Kept for one turn only: left in permanently, the model started citing sources
            # for questions it never actually searched, having seen the pattern established earlier
            # in the same conversation.
            messages.insert(-1, {"role": "system", "content": self._last_web_record})
        if self._last_calendar_record:
            # Same one-turn honesty rule as the web record just above: kept any longer, the model
            # starts telling later, unrelated questions that it checked the calendar for those too.
            messages.insert(-1, {"role": "system", "content": self._last_calendar_record})
        if self._last_research_record:
            messages.insert(-1, {"role": "system", "content": self._last_research_record})
        web = self._look_up(text)
        if web.results:
            messages.insert(-1, {"role": "system", "content": web.results})
        calendar = self._look_up_calendar(text)
        if calendar.results:
            messages.insert(-1, {"role": "system", "content": calendar.results})
        research = self._look_up_research(text)
        if research.results:
            messages.insert(-1, {"role": "system", "content": research.results})
        calc = calc_lookup(text)
        if calc.results:
            # No one-turn "record" tracking needed here, unlike web/calendar/research: a plain
            # arithmetic question is self-contained, and there's nothing stateful to be honest
            # about afterwards the way "which site did that come from" is.
            messages.insert(-1, {"role": "system", "content": calc.results})
        parts: list[str] = []
        try:
            for chunk in self._client.chat(model=self._model, messages=messages, stream=True):
                if token := chunk.message.content:
                    parts.append(token)
                    yield token
        finally:
            self._last_web_record = web.record
            self._last_calendar_record = calendar.record
            self._last_research_record = research.record
            self._history.append({"role": "assistant", "content": "".join(parts)})
            del self._history[: -self._max_messages]

    def _prompt(self) -> str:
        prompt = self._system_prompt + self._now_line()
        if self._calendar_lookup:
            prompt += CALENDAR_AWARE
        if self._research_lookup:
            prompt += RESEARCH_AWARE
        if self._memory:
            prompt += self._memory.prompt()
        # SIR goes last, after even the user's own notes -- see its own docstring for why.
        return prompt + SIR

    def _now_line(self) -> str:
        # A model this small has no reliable sense of "today" -- its notion of the date comes from
        # whenever its training data was collected, which is why it guessed a day of the week that
        # was already wrong. Telling it the real date and time, computed here rather than asked of
        # the model, is the only way it can ever get this right.
        return f"\nRight now it's {speak_moment(datetime.datetime.now(), year=True)}.\n"

    def _look_up(self, text: str) -> WebCheck:
        return self._lookup(text) if self._lookup else NOT_CHECKED

    def _look_up_calendar(self, text: str) -> CalendarCheck:
        return self._calendar_lookup(text) if self._calendar_lookup else CALENDAR_NOT_CHECKED

    def _look_up_research(self, text: str) -> ResearchCheck:
        return self._research_lookup(text) if self._research_lookup else RESEARCH_NOT_CHECKED
