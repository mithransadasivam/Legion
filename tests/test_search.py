import pytest

from legion.search import lookup, search, search_query


@pytest.fixture
def fake_ddgs(monkeypatch):
    """Replaces DuckDuckGo with a stub, so the tests never touch the network."""
    state = {"results": [], "error": None, "calls": []}

    class FakeDDGS:
        def __init__(self, **kwargs) -> None:
            pass

        def text(self, query, max_results=None, **kwargs):
            state["calls"].append((query, max_results))
            if state["error"]:
                raise state["error"]
            return state["results"]

    monkeypatch.setattr("ddgs.DDGS", FakeDDGS)
    return state


class TestSearchQuery:
    @pytest.mark.parametrize(
        "question",
        [
            "What's the weather in Las Vegas today?",
            "Any news about the election?",
            "What's the current price of petrol?",
            "Who won the game last night?",
            "What are the latest headlines?",
        ],
    )
    def test_questions_about_live_information_are_searched(self, question):
        assert search_query(question) == question

    @pytest.mark.parametrize(
        "question",
        [
            "What is the capital of Australia?",
            "Explain how a jet engine works.",
            "What is 17 times 23?",
            "Who wrote Brave New World?",
            "Why is the sky blue?",
        ],
    )
    def test_general_knowledge_never_touches_the_network(self, question):
        assert search_query(question) is None

    @pytest.mark.parametrize(
        ("order", "expected"),
        [
            ("Legion, search for cheap flights to Tokyo", "cheap flights to Tokyo"),
            ("look up the Titanfall 2 release date", "the Titanfall 2 release date"),
            ("Could you google the Ollama changelog?", "the Ollama changelog"),
        ],
    )
    def test_an_explicit_order_searches_only_what_follows_it(self, order, expected):
        assert search_query(order) == expected


class TestSearch:
    def test_each_result_becomes_one_line(self, fake_ddgs):
        fake_ddgs["results"] = [
            {"title": "BBC News", "body": "Something happened today.", "href": "https://bbc.co.uk"},
            {"title": "Reuters", "body": "It happened twice.", "href": "https://reuters.com"},
        ]

        assert search("what happened") == "- BBC News: Something happened today.\n- Reuters: It happened twice."

    def test_ragged_whitespace_in_snippets_is_collapsed(self, fake_ddgs):
        fake_ddgs["results"] = [{"title": "A site", "body": "spread\n  over   lines"}]

        assert search("anything") == "- A site: spread over lines"

    def test_a_failed_search_costs_the_answer_not_the_conversation(self, fake_ddgs):
        fake_ddgs["error"] = OSError("no network")

        assert search("anything") == ""

    def test_results_without_a_title_are_dropped(self, fake_ddgs):
        fake_ddgs["results"] = [{"body": "orphaned snippet"}, {"title": "Real", "body": "kept"}]

        assert search("anything") == "- Real: kept"


class TestLookup:
    def test_general_knowledge_is_never_looked_up(self, fake_ddgs):
        assert lookup("What is the capital of Australia?") == ""
        assert fake_ddgs["calls"] == [], "no search should have been attempted"

    def test_live_questions_are_looked_up(self, fake_ddgs):
        fake_ddgs["results"] = [{"title": "Forecast", "body": "Hot and dry."}]

        assert lookup("What's the weather today?") == "- Forecast: Hot and dry."
        assert fake_ddgs["calls"][0][0] == "What's the weather today?"
