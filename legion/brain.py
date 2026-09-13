"""Conversation with a local model served by Ollama."""

from collections.abc import Callable, Iterator

import ollama

from legion.persona import SEARCH_SYSTEM_PROMPT, SYSTEM_PROMPT
from legion.search import NOT_CHECKED, WebCheck


class Brain:
    def __init__(
        self,
        model: str,
        host: str,
        max_turns: int = 8,
        lookup: Callable[[str], WebCheck] | None = None,
    ) -> None:
        self._client = ollama.Client(host=host)
        self._model = model
        self._host = host
        self._history: list[dict[str, str]] = []
        self._max_messages = max_turns * 2
        self._lookup = lookup
        self._system_prompt = SEARCH_SYSTEM_PROMPT if lookup else SYSTEM_PROMPT

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
        messages = [{"role": "system", "content": self._system_prompt}, *self._history]
        web = self._look_up(text)
        if web.results:
            messages.insert(-1, {"role": "system", "content": web.results})
        parts: list[str] = []
        try:
            for chunk in self._client.chat(model=self._model, messages=messages, stream=True):
                if token := chunk.message.content:
                    parts.append(token)
                    yield token
        finally:
            if web.record:
                self._history.append({"role": "system", "content": web.record})
            self._history.append({"role": "assistant", "content": "".join(parts)})
            del self._history[: -self._max_messages]

    def _look_up(self, text: str) -> WebCheck:
        return self._lookup(text) if self._lookup else NOT_CHECKED
