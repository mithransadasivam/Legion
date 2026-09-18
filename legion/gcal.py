"""Read-only access to the user's Google Calendar, mirroring how legion.search hands the model
live results: a plain text gate decides when a question is calendar-shaped (small models are as
unreliable at deciding *when* to check a calendar as they are at deciding when to search), and
only then does anything touch the network.

Read-only on purpose, and not just as a matter of which methods this module happens to call:
the OAuth scope requested below (calendar.readonly) is enforced by Google itself, so Legion has
no way to create, edit, or delete anything on the user's calendar even if it wanted to.
"""

from __future__ import annotations

import datetime
import re
from pathlib import Path
from typing import NamedTuple

from legion.text import speak_date, speak_moment

_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

_NEEDS_CALENDAR = re.compile(
    r"""\b(
        my\s+calendar | my\s+schedule | my\s+agenda |
        my\s+meetings? | my\s+appointments? | my\s+plans? |
        any\s+meetings? | any\s+appointments? |
        what(?:'s|\s+is)\s+(?:on\s+)?(?:my\s+)?(?:calendar|schedule|agenda) |
        do\s+i\s+have\s+(?:anything|any\s+meetings?|any\s+appointments?|plans?) |
        when\s+is\s+my\s+next | next\s+meeting | next\s+appointment |
        am\s+i\s+(?:free|busy)
    )\b""",
    re.IGNORECASE | re.VERBOSE,
)


class CalendarCheck(NamedTuple):
    """The outcome of checking the calendar for one question -- shaped just like WebCheck."""

    results: str
    """Handed to the model alongside the question, then dropped: it's bulky and goes stale."""
    record: str
    """Kept in the history, so "where did you get that?" has a true answer to give."""


CALENDAR_NOT_CHECKED = CalendarCheck("", "")


def needs_calendar(text: str) -> bool:
    """Whether ``text`` is asking about the user's calendar, rather than something Legion
    already knows or would search the web for."""
    return bool(_NEEDS_CALENDAR.search(text))


class CalendarClient:
    """Wraps Google's Calendar API behind the same ``lookup(text) -> Check`` shape web search
    uses, so Brain can treat both the same way.

    The first call opens a browser for the user to sign in and grant read-only access; after
    that, a refresh token cached at ``token_path`` means it never has to ask again until that
    grant is revoked.
    """

    def __init__(self, credentials_path: Path, token_path: Path) -> None:
        self._credentials_path = credentials_path
        self._token_path = token_path
        self._service = None

    def lookup(self, text: str) -> CalendarCheck:
        if not needs_calendar(text):
            return CALENDAR_NOT_CHECKED
        try:
            events = self._upcoming()
        except Exception:
            # Offline first: a failed calendar check should cost one answer, not the conversation.
            return CalendarCheck(
                "You tried to check the user's calendar just now, but it failed. Say you couldn't check.",
                "You tried to check the calendar to answer that, but it failed.",
            )
        if not events:
            return CalendarCheck(
                "The user's calendar, checked just now: nothing is on it for the next 7 days.",
                "You checked the calendar to answer that.",
            )
        lines = "\n".join(_as_line(event) for event in events)
        return CalendarCheck(
            f"The user's calendar, checked just now:\n{lines}",
            "You checked the calendar to answer that.",
        )

    def _upcoming(self, max_events: int = 8, days: int = 7) -> list[dict]:
        if self._service is None:
            self._service = self._connect()
        now = datetime.datetime.now(datetime.timezone.utc)
        response = (
            self._service.events()
            .list(
                calendarId="primary",
                timeMin=now.isoformat(),
                timeMax=(now + datetime.timedelta(days=days)).isoformat(),
                maxResults=max_events,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        return response.get("items", [])

    def _connect(self):
        # Imported here because these pull in Google's API client dependency tree, and most runs
        # never touch a calendar.
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        creds = None
        if self._token_path.exists():
            creds = Credentials.from_authorized_user_file(str(self._token_path), _SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(str(self._credentials_path), _SCOPES)
                creds = flow.run_local_server(port=0)
            self._token_path.parent.mkdir(parents=True, exist_ok=True)
            self._token_path.write_text(creds.to_json())
        return build("calendar", "v3", credentials=creds)


def _as_line(event: dict) -> str:
    start = event.get("start", {})
    when = _speak_start(start)
    return f"- {event.get('summary', 'Untitled event')}: {when}"


def _speak_start(start: dict) -> str:
    if "dateTime" in start:
        return speak_moment(datetime.datetime.fromisoformat(start["dateTime"]))
    return speak_date(datetime.date.fromisoformat(start["date"])) + " (all day)"
