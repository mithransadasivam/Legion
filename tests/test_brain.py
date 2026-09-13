from types import SimpleNamespace

import pytest

from legion import brain as brain_module
from legion.brain import Brain


@pytest.fixture
def sent(monkeypatch) -> list[list[dict]]:
    """Replaces Ollama with a stub, recording the messages each reply was built from."""
    conversations: list[list[dict]] = []

    class FakeClient:
        def __init__(self, **kwargs) -> None:
            pass

        def chat(self, model, messages, stream):
            conversations.append([dict(message) for message in messages])
            for token in ("Right ", "away, ", "sir."):
                yield SimpleNamespace(message=SimpleNamespace(content=token))

    monkeypatch.setattr(brain_module.ollama, "Client", FakeClient)
    return conversations


def drain(brain: Brain, text: str) -> str:
    return "".join(brain.reply(text))


def test_web_results_are_handed_to_the_model_with_the_question(sent):
    brain = Brain(model="m", host="h", lookup=lambda text: "- Forecast: Hot and dry.")

    assert drain(brain, "What's the weather today?") == "Right away, sir."
    roles = [message["role"] for message in sent[0]]
    assert roles == ["system", "system", "user"], "results should arrive just before the question"
    assert "Hot and dry." in sent[0][1]["content"]


def test_results_are_not_kept_in_the_conversation_history(sent):
    lookups = iter(["- Forecast: Hot and dry.", ""])
    brain = Brain(model="m", host="h", lookup=lambda text: next(lookups))

    drain(brain, "What's the weather today?")
    drain(brain, "And what did I just ask?")

    second = sent[1]
    assert not any("Hot and dry." in message["content"] for message in second), (
        "stale results should not follow the conversation around"
    )
    assert [message["role"] for message in second] == ["system", "user", "assistant", "user"]


def test_a_search_that_finds_nothing_leaves_the_prompt_alone(sent):
    brain = Brain(model="m", host="h", lookup=lambda text: "")

    drain(brain, "What's the weather today?")

    assert [message["role"] for message in sent[0]] == ["system", "user"]


def test_without_search_the_model_is_told_it_is_offline(sent):
    brain = Brain(model="m", host="h")

    drain(brain, "What's the weather today?")

    assert "You run offline" in sent[0][0]["content"]


def test_with_search_the_model_is_told_results_will_be_supplied(sent):
    brain = Brain(model="m", host="h", lookup=lambda text: "")

    drain(brain, "Anything at all")

    assert "You run offline" not in sent[0][0]["content"]
    assert "web results are supplied" in sent[0][0]["content"]
