import pytest

from legion.gcal import CALENDAR_NOT_CHECKED, CalendarClient, needs_calendar


class TestNeedsCalendar:
    @pytest.mark.parametrize(
        "question",
        [
            "What's on my calendar today?",
            "Do I have any meetings this afternoon?",
            "What's my schedule like tomorrow?",
            "Am I free at 3pm?",
            "When is my next appointment?",
            "Any appointments this week?",
        ],
    )
    def test_calendar_questions_are_recognized(self, question):
        assert needs_calendar(question)

    @pytest.mark.parametrize(
        "question",
        [
            "What is the capital of Australia?",
            "What's the weather today?",
            "Tell me a joke.",
        ],
    )
    def test_unrelated_questions_are_not(self, question):
        assert not needs_calendar(question)


class _FakeEvents:
    def __init__(self, items: list[dict]) -> None:
        self._items = items
        self.calls: list[dict] = []

    def list(self, **kwargs):
        self.calls.append(kwargs)
        return self

    def execute(self):
        return {"items": self._items}


class _FakeService:
    def __init__(self, items: list[dict]) -> None:
        self._events = _FakeEvents(items)

    def events(self):
        return self._events


class TestCalendarClientLookup:
    def _client(self, tmp_path, items: list[dict]) -> CalendarClient:
        client = CalendarClient(tmp_path / "creds.json", tmp_path / "token.json")
        client._service = _FakeService(items)  # bypasses the real OAuth flow entirely
        return client

    def test_a_question_that_is_not_about_the_calendar_never_touches_it(self, tmp_path):
        client = self._client(tmp_path, items=[{"summary": "Should never be read"}])

        assert client.lookup("What is the capital of France?") == CALENDAR_NOT_CHECKED

    def test_upcoming_events_are_handed_to_the_model_as_a_reply_to_a_calendar_question(self, tmp_path):
        client = self._client(
            tmp_path,
            items=[{"summary": "Dentist", "start": {"dateTime": "2026-09-18T15:00:00-07:00"}}],
        )

        check = client.lookup("What's on my calendar tomorrow?")

        assert "Dentist" in check.results
        assert "3:00 PM" in check.results
        assert "checked the calendar" in check.record

    def test_an_all_day_event_is_spoken_as_a_date_not_a_time(self, tmp_path):
        client = self._client(tmp_path, items=[{"summary": "Birthday", "start": {"date": "2026-09-20"}}])

        check = client.lookup("What's on my calendar?")

        assert "Birthday" in check.results
        assert "all day" in check.results

    def test_an_empty_calendar_is_reported_honestly_rather_than_left_blank(self, tmp_path):
        client = self._client(tmp_path, items=[])

        check = client.lookup("Do I have any meetings this week?")

        assert "nothing is on it" in check.results
        assert "checked the calendar" in check.record

    def test_a_failed_check_tells_the_model_to_say_so_rather_than_guess(self, tmp_path):
        client = self._client(tmp_path, items=[])

        def broken_upcoming(*args, **kwargs):
            raise ConnectionError("no network")

        client._upcoming = broken_upcoming

        check = client.lookup("What's on my calendar today?")

        assert "couldn't check" in check.results.lower() or "failed" in check.results
        assert "failed" in check.record
