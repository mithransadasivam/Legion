import re
import time
from types import SimpleNamespace

import numpy as np
import pytest

from legion import rag
from legion.documents import Chunk
from legion.rag import (
    MAX_CONTEXT_CHARS,
    Embedder,
    Index,
    Retriever,
    _unit_length,
    load_index,
    save_index,
    scan,
    update_index,
)
from legion.research import NOT_CHECKED, ResearchCheck

MODEL = "fake-embed"

# Words that mean the same thing share a dimension -- so "heart attack" lands next to "myocardial
# infarction" despite having no word in common, which is exactly what keyword search can't do.
CONCEPTS = {
    "heart": 0, "cardiac": 0, "infarction": 0, "myocardial": 0, "attack": 0,
    "robot": 1, "robots": 1, "walk": 1, "legged": 1, "locomotion": 1,
    "crispr": 2, "gene": 2, "editing": 2, "dna": 2,
    "pasta": 3, "recipe": 3, "cook": 3,
}


@pytest.fixture
def calls():
    return []


@pytest.fixture
def embed(calls):
    def fake(texts):
        calls.append(list(texts))
        vectors = np.zeros((len(texts), 4), np.float32)
        for row, text in enumerate(texts):
            for word in re.findall(r"[a-z]+", text.lower()):
                if word in CONCEPTS:
                    vectors[row, CONCEPTS[word]] += 1
        return _unit_length(vectors)

    return fake


@pytest.fixture
def dirs(tmp_path):
    library, knowledge = tmp_path / "library", tmp_path / "knowledge"
    library.mkdir()
    knowledge.mkdir()
    return SimpleNamespace(library=library, knowledge=knowledge, index=tmp_path / "state" / "index.json")


def retriever(dirs, embed, fallback=None, **kwargs):
    return Retriever(embed, MODEL, dirs.library, dirs.index, knowledge_dir=dirs.knowledge, fallback=fallback, **kwargs)


def warm(found):
    """Warm the embedder and build the index -- what the background thread does after startup."""
    assert found.warm_up()
    found.refresh()
    return found


CURATED = """\
## Statins and cardiac events
Source: Example et al., 2020 -- PMID:1
Keywords: statin

A myocardial infarction is less likely after years of cholesterol lowering treatment.
"""


class TestUpdateIndex:
    def test_embeds_everything_the_first_time(self, dirs, embed, calls):
        (dirs.library / "a.txt").write_text("Robots walk with legged locomotion.")
        (dirs.knowledge / "cardio.md").write_text(CURATED)

        index = update_index(None, scan(dirs.library, dirs.knowledge), embed, MODEL)

        assert len(index) == 2
        assert set(index.records) == {"library:a.txt", "notes:cardio.md"}
        assert len(calls) == 1, "one batched request, not one per passage"

    def test_embeds_passages_with_the_document_prefix_the_model_expects(self, dirs, embed, calls):
        (dirs.library / "a.txt").write_text("Robots walk.")

        update_index(None, scan(dirs.library, dirs.knowledge), embed, MODEL)

        assert calls[0] == ["search_document: Robots walk."]

    def test_unchanged_files_are_never_embedded_again(self, dirs, embed, calls):
        (dirs.library / "a.txt").write_text("Robots walk.")
        first = update_index(None, scan(dirs.library, dirs.knowledge), embed, MODEL)
        calls.clear()

        second = update_index(first, scan(dirs.library, dirs.knowledge), embed, MODEL)

        assert calls == []
        assert len(second) == 1

    def test_only_the_changed_file_is_embedded_again(self, dirs, embed, calls):
        (dirs.library / "a.txt").write_text("Robots walk.")
        (dirs.library / "b.txt").write_text("Pasta recipe.")
        first = update_index(None, scan(dirs.library, dirs.knowledge), embed, MODEL)
        calls.clear()
        (dirs.library / "b.txt").write_text("Pasta recipe, now much longer than before.")

        update_index(first, scan(dirs.library, dirs.knowledge), embed, MODEL)

        assert calls == [["search_document: Pasta recipe, now much longer than before."]]

    def test_a_deleted_file_is_forgotten(self, dirs, embed):
        (dirs.library / "a.txt").write_text("Robots walk.")
        (dirs.library / "b.txt").write_text("Pasta recipe.")
        first = update_index(None, scan(dirs.library, dirs.knowledge), embed, MODEL)
        (dirs.library / "b.txt").unlink()

        second = update_index(first, scan(dirs.library, dirs.knowledge), embed, MODEL)

        assert set(second.records) == {"library:a.txt"}

    def test_a_different_embedding_model_means_starting_over(self, dirs, embed, calls):
        (dirs.library / "a.txt").write_text("Robots walk.")
        first = update_index(None, scan(dirs.library, dirs.knowledge), embed, MODEL)
        calls.clear()

        update_index(first, scan(dirs.library, dirs.knowledge), embed, "another-model")

        assert len(calls) == 1, "vectors from one model mean nothing to another"

    def test_curated_notes_are_one_passage_each_labelled_with_their_citation(self, dirs, embed):
        (dirs.knowledge / "cardio.md").write_text(CURATED)

        index = update_index(None, scan(dirs.library, dirs.knowledge), embed, MODEL)

        [chunk] = index.records["notes:cardio.md"].chunks
        assert chunk.source == "Example et al., 2020 -- PMID:1"
        assert chunk.text.startswith("Statins and cardiac events.")

    def test_an_empty_or_unreadable_file_contributes_nothing_and_breaks_nothing(self, dirs, embed):
        (dirs.library / "empty.txt").write_text("")
        (dirs.library / "broken.pdf").write_bytes(b"not a pdf")
        (dirs.library / "good.txt").write_text("Robots walk.")

        index = update_index(None, scan(dirs.library, dirs.knowledge), embed, MODEL)

        assert set(index.records) == {"library:good.txt"}


class TestPersistence:
    def build(self, dirs, embed):
        (dirs.library / "a.txt").write_text("Robots walk.")
        (dirs.knowledge / "cardio.md").write_text(CURATED)
        return update_index(None, scan(dirs.library, dirs.knowledge), embed, MODEL)

    def test_a_saved_index_loads_back_identically(self, dirs, embed):
        index = self.build(dirs, embed)

        save_index(index, dirs.index)
        loaded = load_index(dirs.index, MODEL)

        assert loaded is not None
        assert [c for r in loaded.records.values() for c in r.chunks] == [c for r in index.records.values() for c in r.chunks]
        np.testing.assert_allclose(loaded._matrix, index._matrix)

    def test_an_index_from_another_model_is_not_used(self, dirs, embed):
        save_index(self.build(dirs, embed), dirs.index)

        assert load_index(dirs.index, "another-model") is None

    def test_nothing_saved_means_no_index(self, dirs):
        assert load_index(dirs.index, MODEL) is None

    def test_a_corrupt_index_is_discarded_rather_than_crashing(self, dirs, embed):
        save_index(self.build(dirs, embed), dirs.index)
        dirs.index.write_text("{ not json")

        assert load_index(dirs.index, MODEL) is None

    def test_vectors_that_no_longer_match_the_passages_are_discarded(self, dirs, embed):
        save_index(self.build(dirs, embed), dirs.index)
        with open(dirs.index.with_suffix(".npz"), "wb") as handle:
            np.savez(handle, vectors=np.zeros((1, 4), np.float32))

        assert load_index(dirs.index, MODEL) is None

    def test_a_missing_vectors_file_is_discarded(self, dirs, embed):
        save_index(self.build(dirs, embed), dirs.index)
        dirs.index.with_suffix(".npz").unlink()

        assert load_index(dirs.index, MODEL) is None

    def test_no_temporary_files_are_left_behind(self, dirs, embed):
        save_index(self.build(dirs, embed), dirs.index)

        assert sorted(path.name for path in dirs.index.parent.iterdir()) == ["index.json", "index.npz"]


class TestLookup:
    def ready(self, dirs, embed, fallback=None):
        (dirs.library / "cardio.txt").write_text("A myocardial infarction needs urgent treatment.")
        (dirs.library / "robots.txt").write_text("Legged robots learn locomotion in simulation.")
        (dirs.library / "pasta.txt").write_text("A pasta recipe starts with salted water.")
        found = warm(retriever(dirs, embed, fallback))
        return found

    def test_finds_a_passage_by_meaning_when_no_word_is_shared(self, dirs, embed):
        found = self.ready(dirs, embed)

        check = found.lookup("What should I do about a heart attack?")

        assert "myocardial infarction" in check.results
        assert "cardio.txt" in check.record

    def test_an_unrelated_question_gets_nothing(self, dirs, embed):
        found = self.ready(dirs, embed)

        assert found.lookup("What is the capital of Australia?") == NOT_CHECKED

    def test_only_passages_close_to_the_best_match_are_included(self, dirs, embed, monkeypatch):
        (dirs.library / "exact.txt").write_text("A heart attack is a myocardial infarction.")
        # Half about hearts, half about robots: scores 0.71, clearing the bare minimum of 0.70 but
        # nowhere near the exact match's 1.0.
        (dirs.library / "vague.txt").write_text("A heart attack robots walk.")
        found = warm(retriever(dirs, embed))
        question = "Explain heart attack and myocardial infarction."

        # Control: with the closeness rule switched off, the vague passage does get through --
        # so the assertion below is the rule doing its job, not the minimum doing it by accident.
        monkeypatch.setattr(rag, "CLOSE_TO_BEST", 1.0)
        assert "vague.txt" in found.lookup(question).record
        monkeypatch.undo()

        check = found.lookup(question)

        assert "exact.txt" in check.record
        assert "vague.txt" not in check.record

    def test_the_question_is_embedded_with_the_query_prefix(self, dirs, embed, calls):
        found = self.ready(dirs, embed)
        calls.clear()

        found.lookup("What should I do about a heart attack?")

        assert calls == [["search_query: What should I do about a heart attack?"]]

    def test_a_one_word_message_is_not_searched_at_all(self, dirs, embed, calls):
        found = self.ready(dirs, embed)
        calls.clear()

        assert found.lookup("Hello") == NOT_CHECKED
        assert calls == []

    def test_no_more_than_the_context_budget_is_ever_handed_over(self, dirs, embed):
        # Curated notes are kept whole, so they're the one thing that can outgrow the budget:
        # three of ~1000 characters is 3000, against a budget of 2400.
        entries = "\n".join(
            f"## Note {n}\nSource: Source {n}\nKeywords: heart\n\nheart attack myocardial infarction {'x' * 950}\n"
            for n in range(3)
        )
        (dirs.knowledge / "cardio.md").write_text(entries)
        found = warm(retriever(dirs, embed))

        check = found.lookup("heart attack myocardial infarction")

        assert check.record.count("Source ") == 2, "the third would have gone over budget"
        assert len(check.results) <= MAX_CONTEXT_CHARS + 200

    def test_the_best_passage_always_gets_through_even_if_it_alone_is_over_budget(self, dirs, embed):
        (dirs.knowledge / "cardio.md").write_text(
            f"## Big note\nSource: Big source\nKeywords: heart\n\nheart attack myocardial infarction {'x' * 3000}\n"
        )
        found = warm(retriever(dirs, embed))

        check = found.lookup("heart attack myocardial infarction")

        assert "Big source" in check.record


class TestFallbackToKeywords:
    def keyword(self, text):
        return ResearchCheck("keyword result", "keyword record")

    def test_before_any_index_exists_the_keyword_search_answers(self, dirs, embed):
        found = retriever(dirs, embed, fallback=self.keyword)

        assert found.lookup("Tell me about CRISPR gene editing").results == "keyword result"

    def test_when_embedding_fails_the_keyword_search_answers(self, dirs, embed):
        (dirs.library / "a.txt").write_text("Robots walk.")
        found = warm(retriever(dirs, embed, fallback=self.keyword))
        found._embed_query = lambda texts: (_ for _ in ()).throw(ConnectionError("ollama is down"))

        assert "keyword result" in found.lookup("Tell me about legged robots").results

    def test_with_no_fallback_and_no_index_nothing_is_returned(self, dirs, embed):
        assert retriever(dirs, embed).lookup("Tell me about CRISPR gene editing") == NOT_CHECKED


class TestRefresh:
    def test_reports_whether_it_did_anything(self, dirs, embed):
        (dirs.library / "a.txt").write_text("Robots walk.")
        found = retriever(dirs, embed)

        assert found.refresh() is True
        assert found.refresh() is False, "nothing changed since last time"

    def test_a_file_added_later_is_picked_up(self, dirs, embed):
        found = warm(retriever(dirs, embed))
        assert found.lookup("What should I do about a heart attack?") == NOT_CHECKED

        (dirs.library / "cardio.txt").write_text("A myocardial infarction needs urgent treatment.")

        assert found.refresh() is True
        assert "cardio.txt" in found.lookup("What should I do about a heart attack?").record

    def test_the_index_is_saved_and_reused_by_the_next_run_without_re_embedding_files(self, dirs, embed, calls):
        (dirs.library / "cardio.txt").write_text("A myocardial infarction needs urgent treatment.")
        warm(retriever(dirs, embed))
        calls.clear()

        second = retriever(dirs, embed)
        second.warm_up()
        calls.clear()
        second.refresh()

        assert calls == [], "the saved passages were already embedded; only the question needs embedding"
        assert "cardio.txt" in second.lookup("What should I do about a heart attack?").record

    def test_a_failure_falls_back_quietly_and_waits_before_trying_again(self, dirs, embed, capsys, monkeypatch):
        (dirs.library / "a.txt").write_text("Robots walk.")
        attempts = []

        def failing(texts):
            attempts.append(texts)
            raise ConnectionError("ollama is down")

        found = retriever(dirs, failing)
        clock = {"now": 1000.0}
        monkeypatch.setattr(rag.time, "monotonic", lambda: clock["now"])

        assert found.refresh() is False
        assert found.refresh() is False
        assert len(attempts) == 1, "no hammering Ollama while it's down"
        assert capsys.readouterr().out.count("couldn't use the embedding model") == 1

        clock["now"] += 31
        found._embed = embed
        assert found.refresh() is True

    def test_the_watcher_keeps_the_index_current_and_can_be_stopped(self, dirs, embed, monkeypatch):
        monkeypatch.setattr(rag, "_POLL_SECONDS", 0.02)
        found = retriever(dirs, embed)
        found.start()
        try:
            (dirs.library / "cardio.txt").write_text("A myocardial infarction needs urgent treatment.")
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and not found._index:
                time.sleep(0.02)
            assert found._index and "library:cardio.txt" in found._index.records
        finally:
            found.stop()
            found._thread.join(timeout=5)
        assert not found._thread.is_alive()


class TestEmbedder:
    @pytest.fixture
    def client(self, monkeypatch):
        sent = type("Sent", (list,), {})()
        sent.timeouts = timeouts = []

        class FakeClient:
            def __init__(self, host, timeout=None):
                self.host = host
                timeouts.append(timeout)

            def embed(self, model, input, keep_alive=None):
                sent.append({"model": model, "n": len(input), "keep_alive": keep_alive})
                return SimpleNamespace(embeddings=[[3.0, 4.0] for _ in input])

        monkeypatch.setattr(rag.ollama, "Client", FakeClient)
        return sent

    def test_vectors_come_back_unit_length(self, client):
        vectors = Embedder("http://h")(["a", "b"])

        np.testing.assert_allclose(np.linalg.norm(vectors, axis=1), [1.0, 1.0], rtol=1e-6)

    def test_every_request_asks_ollama_to_keep_the_model_loaded(self, client):
        from legion.memory import KEEP_ALIVE

        Embedder("http://h")(["a"])

        assert client[0]["keep_alive"] == KEEP_ALIVE

    def test_big_jobs_go_out_in_batches(self, client):
        Embedder("http://h")([f"text {n}" for n in range(70)])

        assert [request["n"] for request in client] == [32, 32, 6]

    def test_a_timeout_can_be_set_for_impatient_callers(self, client):
        Embedder("http://h", timeout=5.0)
        Embedder("http://h")

        assert client.timeouts == [5.0, None]

    def test_nothing_to_embed_is_fine(self, client):
        assert Embedder("http://h")([]).size == 0
        assert client == []


class TestIndexSearch:
    def test_returns_best_first_and_respects_k(self):
        records = {
            "a": rag._Record("1", [Chunk("a", "A")], np.array([[1.0, 0.0]], np.float32)),
            "b": rag._Record("1", [Chunk("b", "B")], np.array([[0.6, 0.8]], np.float32)),
            "c": rag._Record("1", [Chunk("c", "C")], np.array([[0.0, 1.0]], np.float32)),
        }
        index = Index(MODEL, records)

        results = index.search(np.array([1.0, 0.0], np.float32), 2)

        assert [chunk.source for _, chunk in results] == ["a", "b"]
        assert results[0][0] == pytest.approx(1.0)

    def test_an_empty_index_finds_nothing(self):
        assert Index(MODEL, {}).search(np.array([1.0, 0.0], np.float32), 3) == []


class TestNeverWaitsOnAColdEmbedder:
    """Ollama loads one model at a time, so a question that needs a cold embedding model waits
    behind its whole load -- measured at 28 seconds, and over a minute alongside the chat model.
    A reply must never wait on that: it answers from the keyword search instead."""

    keyword = staticmethod(lambda text: ResearchCheck("keyword result", "keyword record"))

    def saved_index(self, dirs, embed):
        (dirs.library / "cardio.txt").write_text("A myocardial infarction needs urgent treatment.")
        warm(retriever(dirs, embed))

    def test_a_saved_index_is_not_used_until_the_embedder_is_known_to_be_warm(self, dirs, embed, calls):
        self.saved_index(dirs, embed)
        calls.clear()
        found = retriever(dirs, embed, fallback=self.keyword)  # a fresh start: index on disk, embedder cold

        assert "keyword result" in found.lookup("What should I do about a heart attack?").results
        assert calls == [], "the question must not have been sent to a model that may not be loaded"

        found.warm_up()
        calls.clear()

        assert "cardio.txt" in found.lookup("What should I do about a heart attack?").record
        assert len(calls) == 1

    def test_questions_use_their_own_impatient_embedder(self, dirs, embed, calls):
        self.saved_index(dirs, embed)
        query_calls = []

        def query_embed(texts):
            query_calls.append(texts)
            return embed(texts)

        found = retriever(dirs, embed, embed_query=query_embed)
        found.warm_up()

        found.lookup("What should I do about a heart attack?")

        assert query_calls == [["search_query: What should I do about a heart attack?"]]

    def test_a_question_that_times_out_gets_the_keyword_answer_and_the_embedder_is_marked_cold(self, dirs, embed):
        self.saved_index(dirs, embed)
        found = retriever(dirs, embed, fallback=self.keyword)
        found.warm_up()
        found._embed_query = lambda texts: (_ for _ in ()).throw(TimeoutError("still loading"))

        assert "keyword result" in found.lookup("What should I do about a heart attack?").results

        # Marked cold: the next question doesn't try (and wait) again either, until it's warmed.
        found._embed_query = lambda texts: pytest.fail("a cold embedder must not be asked")
        assert "keyword result" in found.lookup("What should I do about a heart attack?").results

    def test_warming_up_failing_is_quiet_and_not_retried_straight_away(self, dirs, capsys, monkeypatch):
        attempts = []

        def failing(texts):
            attempts.append(texts)
            raise ConnectionError("ollama is down")

        clock = {"now": 1000.0}
        monkeypatch.setattr(rag.time, "monotonic", lambda: clock["now"])
        found = retriever(dirs, failing)

        assert found.warm_up() is False
        assert found.warm_up() is False
        assert len(attempts) == 1
        assert capsys.readouterr().out.count("couldn't use the embedding model") == 1
        clock["now"] += 31
        assert found.warm_up() is False
        assert len(attempts) == 2

    def test_the_watcher_leaves_ollama_alone_until_the_chat_model_has_loaded(self, dirs, embed, calls, monkeypatch):
        monkeypatch.setattr(rag, "_POLL_SECONDS", 0.02)
        monkeypatch.setattr(rag, "_MODEL_POLL_SECONDS", 0.02)
        chat_loaded = {"yes": False}
        found = retriever(dirs, embed, wait_until=lambda: chat_loaded["yes"])
        found.start()
        try:
            time.sleep(0.4)
            assert calls == [], "loading the embedder now would slow the chat model's own load to a crawl"

            chat_loaded["yes"] = True
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and not calls:
                time.sleep(0.02)
            assert calls, "once the chat model is loaded, the embedder warms up"
        finally:
            found.stop()
            found._thread.join(timeout=5)


class TestChatModelLoaded:
    def fake(self, monkeypatch, names=None, error=None):
        class FakeClient:
            def __init__(self, host):
                pass

            def ps(self):
                if error:
                    raise error
                return SimpleNamespace(models=[SimpleNamespace(model=name) for name in names])

        monkeypatch.setattr(rag.ollama, "Client", FakeClient)

    def test_true_when_the_model_is_loaded(self, monkeypatch):
        self.fake(monkeypatch, names=["llama3.1:8b"])

        assert rag.chat_model_loaded("http://h", "llama3.1:8b") is True

    def test_a_bare_name_matches_ollamas_latest_tag(self, monkeypatch):
        self.fake(monkeypatch, names=["mistral:latest"])

        assert rag.chat_model_loaded("http://h", "mistral") is True

    def test_false_when_only_something_else_is_loaded(self, monkeypatch):
        self.fake(monkeypatch, names=["nomic-embed-text:latest"])

        assert rag.chat_model_loaded("http://h", "llama3.1:8b") is False

    def test_false_when_ollama_cannot_be_asked(self, monkeypatch):
        self.fake(monkeypatch, error=ConnectionError("down"))

        assert rag.chat_model_loaded("http://h", "llama3.1:8b") is False


class TestHonestWhileTheLibraryIsNotReady:
    """Asked about a document it couldn't see yet, the model invented a number -- so while the
    user's documents can't be searched, it's told so, and told not to guess about them."""

    keyword = staticmethod(lambda text: ResearchCheck("keyword result", "keyword record"))

    def test_is_told_the_library_is_still_loading_when_the_user_has_documents(self, dirs, embed):
        (dirs.library / "mine.txt").write_text("The Zephyr-9 stall torque is 41 newton metres.")
        found = retriever(dirs, embed, fallback=self.keyword)

        check = found.lookup("What is the stall torque of the Zephyr-9?")

        assert "still loading" in check.results
        assert "rather than guessing" in check.results
        assert "keyword result" in check.results, "whatever the keyword search found still comes along"
        assert check.record == "keyword record"

    def test_a_library_that_is_unavailable_is_not_described_as_loading(self, dirs):
        (dirs.library / "mine.txt").write_text("Some notes.")

        def failing(texts):
            raise ConnectionError("down")

        found = retriever(dirs, failing, fallback=self.keyword)
        found.warm_up()

        check = found.lookup("What do my notes say about the garden?")

        assert "isn't available right now" in check.results
        assert "still loading" not in check.results

    def test_nothing_is_said_when_the_user_has_no_documents(self, dirs, embed):
        found = retriever(dirs, embed, fallback=self.keyword)

        assert found.lookup("Tell me about legged robots").results == "keyword result"

    def test_the_note_alone_is_returned_when_the_keyword_search_finds_nothing(self, dirs, embed):
        (dirs.library / "mine.txt").write_text("Some notes.")
        found = retriever(dirs, embed)

        check = found.lookup("What is the stall torque of the Zephyr-9?")

        assert check.results.startswith("The user's own documents can't be searched yet")
        assert check.record == ""

    def test_the_note_disappears_once_the_library_is_ready(self, dirs, embed):
        (dirs.library / "mine.txt").write_text("A myocardial infarction needs urgent treatment.")
        found = warm(retriever(dirs, embed, fallback=self.keyword))

        check = found.lookup("What should I do about a heart attack?")

        assert "can't be searched yet" not in check.results
        assert "mine.txt" in check.record
