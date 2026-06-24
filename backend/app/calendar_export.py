"""Export learning-session dicts to a single iCalendar (.ics) text string.

The output follows RFC 5545 and imports cleanly into both Apple Calendar and
Google Calendar. Datetimes are emitted as UTC (``...Z``) and every value is
derived from the session input, so identical input always yields byte-identical
output (no ``datetime.now()`` anywhere).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from icalendar import Calendar, Event

PRODID = "-//PathForge AI//Learning Planner//EN"
ICALENDAR_VERSION = "2.0"
ICALENDAR_METHOD = "PUBLISH"
DEFAULT_CALENDAR_NAME = "PathForge Learning Plan"
DEFAULT_REFLECTION_PROMPT = (
    "After this session, write what you learned to mark it complete in PathForge."
)
UID_DOMAIN = "@pathforge.ai"
FALLBACK_FILENAME = "pathforge-schedule.ics"

REQUIRED_SESSION_KEYS = (
    "uid",
    "start_utc",
    "end_utc",
    "resource_title",
    "resource_type",
    "goal",
)

_SLUG_NON_ALNUM = re.compile(r"[^a-z0-9]+")


class CalendarExportError(ValueError):
    """Raised when a session cannot be turned into a valid VEVENT."""


def _require_keys(session: dict, index: int) -> None:
    missing = [key for key in REQUIRED_SESSION_KEYS if key not in session]
    if missing:
        raise CalendarExportError(
            f"session at index {index} is missing required keys: {', '.join(missing)}"
        )


def _parse_utc(value: object, *, field: str, index: int) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise CalendarExportError(
            f"session at index {index} has an empty or non-string {field}"
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise CalendarExportError(
            f"session at index {index} has an invalid {field!r}: {value!r} ({error})"
        ) from error
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _build_description(goal: str, resource_url: object, reflection_prompt: str) -> str:
    parts = [goal]
    if isinstance(resource_url, str) and resource_url.strip():
        parts.append(f"Resource: {resource_url.strip()}")
    parts.append(reflection_prompt)
    return "\n\n".join(parts)


def _build_event(session: dict, index: int, reflection_prompt: str) -> Event:
    _require_keys(session, index)

    start = _parse_utc(session["start_utc"], field="start_utc", index=index)
    end = _parse_utc(session["end_utc"], field="end_utc", index=index)
    if end <= start:
        raise CalendarExportError(
            f"session at index {index} has end ({end.isoformat()}) "
            f"not after start ({start.isoformat()})"
        )

    event = Event()
    event.add("UID", f"{session['uid']}{UID_DOMAIN}")
    event.add("DTSTAMP", start)
    event.add("DTSTART", start)
    event.add("DTEND", end)
    event.add("SUMMARY", f"Learn: {session['resource_title']}")
    event.add(
        "DESCRIPTION",
        _build_description(session["goal"], session.get("resource_url"), reflection_prompt),
    )

    resource_url = session.get("resource_url")
    if isinstance(resource_url, str) and resource_url.strip():
        event.add("URL", resource_url.strip())

    event.add("CATEGORIES", session["resource_type"])
    return event


def build_ics(
    sessions: list[dict],
    *,
    calendar_name: str = DEFAULT_CALENDAR_NAME,
    reflection_prompt: str = DEFAULT_REFLECTION_PROMPT,
) -> str:
    """Render learning sessions as an iCalendar text string.

    Raises:
        CalendarExportError: if any session is missing required keys, has
            unparseable datetimes, or has ``end`` not strictly after ``start``.

    An empty ``sessions`` list yields a valid VCALENDAR with no VEVENTs.
    """
    if not isinstance(sessions, list):
        raise CalendarExportError("sessions must be a list of session dicts")

    cal = Calendar()
    cal.add("PRODID", PRODID)
    cal.add("VERSION", ICALENDAR_VERSION)
    cal.add("METHOD", ICALENDAR_METHOD)
    cal.add("X-WR-CALNAME", calendar_name)

    for index, session in enumerate(sessions):
        if not isinstance(session, dict):
            raise CalendarExportError(f"session at index {index} is not a dict")
        cal.add_component(_build_event(session, index, reflection_prompt))

    return cal.to_ical().decode("utf-8")


def ics_filename(title: str) -> str:
    """Return a safe ``.ics`` filename slugified from ``title``."""
    slug = _SLUG_NON_ALNUM.sub("-", title.lower()).strip("-")
    if not slug:
        return FALLBACK_FILENAME
    return f"{slug}.ics"
