import unittest
from datetime import datetime, timezone

from icalendar import Calendar

from backend.app.calendar_export import (
    CalendarExportError,
    build_ics,
    ics_filename,
)


def make_session(**overrides):
    session = {
        "uid": "pf-0-3",
        "date": "2026-07-01",
        "start_utc": "2026-07-01T11:00:00+00:00",
        "end_utc": "2026-07-01T11:45:00+00:00",
        "resource_title": "Fluent Python",
        "resource_url": "https://example.com/x",
        "resource_type": "book",
        "skill": "Python",
        "week_index": 0,
        "goal": "Study Fluent Python (book) for Python",
    }
    session.update(overrides)
    return session


class CalendarExportTest(unittest.TestCase):
    def test_output_is_wrapped_in_vcalendar(self):
        ics = build_ics([make_session()])

        self.assertTrue(ics.startswith("BEGIN:VCALENDAR"))
        self.assertTrue(ics.rstrip().endswith("END:VCALENDAR"))

    def test_one_vevent_per_session(self):
        sessions = [
            make_session(uid="pf-0-0"),
            make_session(uid="pf-0-1"),
            make_session(uid="pf-0-2"),
        ]

        ics = build_ics(sessions)

        self.assertEqual(ics.count("BEGIN:VEVENT"), 3)
        self.assertEqual(ics.count("END:VEVENT"), 3)

    def test_event_fields_round_trip_through_parser(self):
        ics = build_ics([make_session()])

        calendar = Calendar.from_ical(ics)
        events = [item for item in calendar.walk("VEVENT")]

        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(
            event.decoded("DTSTART"),
            datetime(2026, 7, 1, 11, 0, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(
            event.decoded("DTEND"),
            datetime(2026, 7, 1, 11, 45, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(str(event["SUMMARY"]), "Learn: Fluent Python")
        self.assertEqual(str(event["UID"]), "pf-0-3@pathforge.ai")
        self.assertEqual(str(event["CATEGORIES"].to_ical().decode("utf-8")), "book")

    def test_dtstamp_equals_dtstart_for_determinism(self):
        ics = build_ics([make_session()])

        calendar = Calendar.from_ical(ics)
        event = next(iter(calendar.walk("VEVENT")))

        self.assertEqual(event.decoded("DTSTAMP"), event.decoded("DTSTART"))

    def test_calendar_metadata_is_present(self):
        ics = build_ics([make_session()], calendar_name="My Plan")

        calendar = Calendar.from_ical(ics)

        self.assertEqual(str(calendar["PRODID"]), "-//PathForge AI//Learning Planner//EN")
        self.assertEqual(str(calendar["VERSION"]), "2.0")
        self.assertEqual(str(calendar["METHOD"]), "PUBLISH")
        self.assertEqual(str(calendar["X-WR-CALNAME"]), "My Plan")

    def test_event_without_url_omits_url_but_keeps_description(self):
        ics = build_ics([make_session(resource_url=None)])

        calendar = Calendar.from_ical(ics)
        event = next(iter(calendar.walk("VEVENT")))

        self.assertNotIn("URL", event)
        description = str(event["DESCRIPTION"])
        self.assertIn("Study Fluent Python", description)
        self.assertNotIn("Resource:", description)
        self.assertIn("mark it complete in PathForge", description)

    def test_event_with_url_includes_resource_line_and_url_property(self):
        ics = build_ics([make_session(resource_url="https://example.com/x")])

        calendar = Calendar.from_ical(ics)
        event = next(iter(calendar.walk("VEVENT")))

        self.assertEqual(str(event["URL"]), "https://example.com/x")
        self.assertIn("Resource: https://example.com/x", str(event["DESCRIPTION"]))

    def test_building_twice_is_byte_identical(self):
        sessions = [make_session(uid="pf-0-0"), make_session(uid="pf-0-1")]

        first = build_ics(sessions)
        second = build_ics(sessions)

        self.assertEqual(first, second)

    def test_missing_required_key_raises(self):
        broken = make_session()
        del broken["goal"]

        with self.assertRaises(CalendarExportError):
            build_ics([broken])

    def test_end_not_after_start_raises(self):
        broken = make_session(
            start_utc="2026-07-01T11:00:00+00:00",
            end_utc="2026-07-01T11:00:00+00:00",
        )

        with self.assertRaises(CalendarExportError):
            build_ics([broken])

    def test_unparseable_datetime_raises(self):
        broken = make_session(start_utc="not-a-datetime")

        with self.assertRaises(CalendarExportError):
            build_ics([broken])

    def test_empty_sessions_returns_valid_empty_calendar(self):
        ics = build_ics([])

        self.assertTrue(ics.startswith("BEGIN:VCALENDAR"))
        self.assertTrue(ics.rstrip().endswith("END:VCALENDAR"))
        self.assertEqual(ics.count("BEGIN:VEVENT"), 0)

        calendar = Calendar.from_ical(ics)
        self.assertEqual(len([item for item in calendar.walk("VEVENT")]), 0)

    def test_ics_filename_slugifies_title(self):
        self.assertEqual(
            ics_filename("PathForge Learning Plan"),
            "pathforge-learning-plan.ics",
        )

    def test_ics_filename_collapses_and_strips_separators(self):
        self.assertEqual(ics_filename("  AI / Engineer!!  "), "ai-engineer.ics")

    def test_ics_filename_falls_back_when_empty(self):
        self.assertEqual(ics_filename("***"), "pathforge-schedule.ics")
        self.assertEqual(ics_filename(""), "pathforge-schedule.ics")


if __name__ == "__main__":
    unittest.main()
