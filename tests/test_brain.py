from types import SimpleNamespace

import pytest

from legion import brain as brain_module
from legion.brain import Brain
from legion.search import NOT_CHECKED, WebCheck


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
    brain = Brain(model="m", host="h", lookup=lambda text: WebCheck("- Forecast (accuweather.com): Hot and dry.", "checked accuweather.com"))

    assert drain(brain, "What's the weather today?") == "Right away, sir."
    roles = [message["role"] for message in sent[0]]
    assert roles == ["system", "system", "user"], "results should arrive just before the question"
    assert "Hot and dry." in sent[0][1]["content"]


def test_results_are_not_kept_but_the_fact_of_checking_the_web_is(sent):
    checks = iter([WebCheck("- Forecast (accuweather.com): Hot and dry.", "You checked the web to answer that, using accuweather.com."), NOT_CHECKED])
    brain = Brain(model="m", host="h", lookup=lambda text: next(checks))

    drain(brain, "What's the weather today?")
    drain(brain, "Where did you get that from?")

    follow_up = sent[1]
    assert not any("Hot and dry." in message["content"] for message in follow_up), (
        "stale results should not follow the conversation around"
    )
    assert [message["role"] for message in follow_up] == ["system", "user", "assistant", "system", "user"]
    assert "accuweather.com" in follow_up[3]["content"], "otherwise the model invents where its answer came from"


def test_the_source_record_does_not_outlive_the_one_follow_up_it_is_for(sent):
    # Left in permanently, the model started citing a source for a later question it never actually
    # searched, having seen "you checked the web" established by two earlier turns in the conversation.
    checks = iter(
        [
            WebCheck("- Forecast (accuweather.com): Hot.", "You checked the web to answer that, using accuweather.com."),
            NOT_CHECKED,
            NOT_CHECKED,
        ]
    )
    brain = Brain(model="m", host="h", lookup=lambda text: next(checks))

    drain(brain, "What's the weather today?")
    drain(brain, "Where did you get that from?")
    drain(brain, "What is the capital of Australia?")

    third_turn = sent[2]
    assert not any("accuweather.com" in message["content"] for message in third_turn), (
        "an unrelated later question should not be told that earlier answers came from the web"
    )


def test_a_question_that_needs_no_search_leaves_the_prompt_and_history_alone(sent):
    brain = Brain(model="m", host="h", lookup=lambda text: NOT_CHECKED)

    drain(brain, "What is the capital of Australia?")
    drain(brain, "And of New Zealand?")

    assert [message["role"] for message in sent[1]] == ["system", "user", "assistant", "user"]


def test_the_model_is_told_the_real_current_date_and_time(sent, monkeypatch):
    import datetime

    fixed = datetime.datetime(2026, 9, 17, 15, 4)  # a Thursday
    monkeypatch.setattr(
        brain_module.datetime, "datetime", SimpleNamespace(now=lambda: fixed)
    )
    brain = Brain(model="m", host="h")

    drain(brain, "What day is it?")

    assert "Thursday, September 17, 2026, 3:04 PM" in sent[0][0]["content"]


def test_without_search_the_model_is_told_it_is_offline(sent):
    brain = Brain(model="m", host="h")

    drain(brain, "What's the weather today?")

    assert "You run offline" in sent[0][0]["content"]


def test_with_search_the_model_is_told_results_will_be_supplied(sent):
    brain = Brain(model="m", host="h", lookup=lambda text: NOT_CHECKED)

    drain(brain, "Anything at all")

    assert "You run offline" not in sent[0][0]["content"]
    assert "web results are supplied" in sent[0][0]["content"]


def test_a_fact_told_just_now_is_in_the_prompt_for_this_very_reply(sent, tmp_path, monkeypatch):
    from legion import memory as memory_module

    class NoteTaker:
        def __init__(self, **kwargs) -> None:
            pass

        def chat(self, model, messages, options):
            return SimpleNamespace(message=SimpleNamespace(content="The user's name is Mithran."))

    # Brain and Memory share the one ollama module, so each gets its own stub in turn.
    chat_stub = memory_module.ollama.Client
    monkeypatch.setattr(memory_module.ollama, "Client", NoteTaker)
    memory = memory_module.Memory(tmp_path / "memory.txt", host="h", model="m")
    monkeypatch.setattr(memory_module.ollama, "Client", chat_stub)
    brain = Brain(model="m", host="h", memory=memory)

    drain(brain, "My name is Mithran.")

    assert "The user's name is Mithran." in sent[0][0]["content"]
