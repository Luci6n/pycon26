import unittest
from datetime import date, datetime, timedelta, timezone

from backend.app.scheduling import (
    DEFAULT_SESSION_MINUTES,
    DEFAULT_WEIGHTS,
    RESOURCE_TYPES,
    URGENCY_RANK,
    ScheduleError,
    generate_schedule,
)

# 2026-06-29 is a Monday (weekday 0), which keeps the recurring-availability
# math easy to reason about across the test fixtures below.
ANCHOR_MONDAY = "2026-06-29"
TZ = "Asia/Singapore"


def _availability_every_weekday(start="09:00", end="18:00"):
    return [{"weekday": weekday, "start": start, "end": end} for weekday in range(7)]


def _resources(resource_type, count, *, skill=None, prefix="r"):
    return [
        {
            "type": resource_type,
            "title": f"{prefix}-{resource_type}-{i}",
            "url": f"https://example.com/{prefix}/{resource_type}/{i}",
            "skill": skill,
        }
        for i in range(count)
    ]


def _parse_utc(value):
    parsed = datetime.fromisoformat(value)
    return parsed


class ScheduleConstantsTest(unittest.TestCase):
    def test_resource_types_constant(self):
        self.assertEqual(RESOURCE_TYPES, ("video", "course", "book", "project"))

    def test_default_session_minutes_cover_all_types(self):
        for resource_type in RESOURCE_TYPES:
            self.assertIn(resource_type, DEFAULT_SESSION_MINUTES)
            self.assertGreater(DEFAULT_SESSION_MINUTES[resource_type], 0)

    def test_default_weights_cover_all_types(self):
        for resource_type in RESOURCE_TYPES:
            self.assertIn(resource_type, DEFAULT_WEIGHTS)

    def test_urgency_rank_orders_critical_above_high_above_medium(self):
        self.assertGreater(URGENCY_RANK["Critical"], URGENCY_RANK["High"])
        self.assertGreater(URGENCY_RANK["High"], URGENCY_RANK["Medium"])


class HappyPathTest(unittest.TestCase):
    def setUp(self):
        self.sessions = generate_schedule(
            horizon_days=30,
            start_date=ANCHOR_MONDAY,
            timezone=TZ,
            availability=_availability_every_weekday(),
            preferences={"max_sessions_per_day": 2, "gap_minutes": 10},
            resources=(
                _resources("video", 6)
                + _resources("course", 6)
                + _resources("book", 6)
                + _resources("project", 6)
            ),
        )

    def test_returns_non_empty_schedule(self):
        self.assertGreater(len(self.sessions), 0)

    def test_sessions_have_exact_key_shape(self):
        expected_keys = {
            "uid",
            "date",
            "start_utc",
            "end_utc",
            "resource_title",
            "resource_url",
            "resource_type",
            "skill",
            "week_index",
            "goal",
        }
        for session in self.sessions:
            self.assertEqual(set(session.keys()), expected_keys)
            self.assertIn(session["resource_type"], RESOURCE_TYPES)
            self.assertIsInstance(session["week_index"], int)

    def test_timestamps_are_tz_aware_utc(self):
        for session in self.sessions:
            start = _parse_utc(session["start_utc"])
            end = _parse_utc(session["end_utc"])
            self.assertIsNotNone(start.tzinfo)
            self.assertIsNotNone(end.tzinfo)
            self.assertEqual(start.utcoffset(), timedelta(0))
            self.assertEqual(end.utcoffset(), timedelta(0))
            self.assertLess(start, end)

    def test_sessions_sorted_by_start_utc(self):
        starts = [session["start_utc"] for session in self.sessions]
        self.assertEqual(starts, sorted(starts))

    def test_sessions_fall_within_availability_windows(self):
        tz_offset = timedelta(hours=8)  # Asia/Singapore is UTC+8, no DST
        for session in self.sessions:
            local_start = _parse_utc(session["start_utc"]) + tz_offset
            local_end = _parse_utc(session["end_utc"]) + tz_offset
            self.assertGreaterEqual(local_start.time(), datetime(2000, 1, 1, 9, 0).time())
            self.assertLessEqual(local_end.time(), datetime(2000, 1, 1, 18, 0).time())

    def test_no_two_sessions_overlap_on_same_day(self):
        by_date = {}
        for session in self.sessions:
            by_date.setdefault(session["date"], []).append(session)
        for sessions in by_date.values():
            ordered = sorted(sessions, key=lambda s: s["start_utc"])
            for earlier, later in zip(ordered, ordered[1:]):
                self.assertLessEqual(
                    _parse_utc(earlier["end_utc"]),
                    _parse_utc(later["start_utc"]),
                )

    def test_uids_are_unique(self):
        uids = [session["uid"] for session in self.sessions]
        self.assertEqual(len(uids), len(set(uids)))

    def test_week_index_matches_date_offset(self):
        anchor = date.fromisoformat(ANCHOR_MONDAY)
        for session in self.sessions:
            session_date = date.fromisoformat(session["date"])
            expected = (session_date - anchor).days // 7
            self.assertEqual(session["week_index"], expected)


class MaxSessionsPerDayTest(unittest.TestCase):
    def test_respects_max_sessions_per_day(self):
        sessions = generate_schedule(
            horizon_days=14,
            start_date=ANCHOR_MONDAY,
            timezone=TZ,
            availability=_availability_every_weekday(),
            preferences={"max_sessions_per_day": 1},
            resources=_resources("video", 30),
        )
        counts = {}
        for session in sessions:
            counts[session["date"]] = counts.get(session["date"], 0) + 1
        for count in counts.values():
            self.assertLessEqual(count, 1)

    def test_higher_cap_allows_more_sessions_per_day(self):
        sessions = generate_schedule(
            horizon_days=14,
            start_date=ANCHOR_MONDAY,
            timezone=TZ,
            availability=_availability_every_weekday(),
            preferences={"max_sessions_per_day": 3},
            resources=_resources("video", 30),
        )
        counts = {}
        for session in sessions:
            counts[session["date"]] = counts.get(session["date"], 0) + 1
        self.assertTrue(any(count > 1 for count in counts.values()))
        for count in counts.values():
            self.assertLessEqual(count, 3)


class HorizonTest(unittest.TestCase):
    def test_no_session_beyond_horizon(self):
        horizon_days = 10
        sessions = generate_schedule(
            horizon_days=horizon_days,
            start_date=ANCHOR_MONDAY,
            timezone=TZ,
            availability=_availability_every_weekday(),
            preferences={"max_sessions_per_day": 2},
            resources=_resources("video", 100),
        )
        anchor = date.fromisoformat(ANCHOR_MONDAY)
        limit = anchor + timedelta(days=horizon_days)
        for session in sessions:
            self.assertLess(date.fromisoformat(session["date"]), limit)
            self.assertGreaterEqual(date.fromisoformat(session["date"]), anchor)


class PreferenceRatioTest(unittest.TestCase):
    def test_video_share_dominates_project_share(self):
        # Capacity (slots) is the binding constraint here: total session capacity
        # is well below the resource count, so the realized mix is governed by
        # the weighted round-robin rather than by queue exhaustion. Equal session
        # lengths keep duration from biasing the ratio.
        sessions = generate_schedule(
            horizon_days=14,
            start_date=ANCHOR_MONDAY,
            timezone=TZ,
            availability=_availability_every_weekday(),
            preferences={
                "weights": {"video": 0.75, "project": 0.25},
                "session_minutes": {"video": 45, "project": 45},
                "max_sessions_per_day": 4,
            },
            resources=(
                _resources("video", 50)
                + _resources("course", 50)
                + _resources("book", 50)
                + _resources("project", 50)
            ),
        )
        type_counts = {resource_type: 0 for resource_type in RESOURCE_TYPES}
        for session in sessions:
            type_counts[session["resource_type"]] += 1

        # course/book have zero weight -> must not be scheduled at all.
        self.assertEqual(type_counts["course"], 0)
        self.assertEqual(type_counts["book"], 0)
        # 3:1 target weighting -> video share clearly dominates project share.
        self.assertGreater(type_counts["video"], type_counts["project"])
        self.assertGreater(type_counts["project"], 0)


class SkillPriorityTest(unittest.TestCase):
    def test_critical_skill_scheduled_before_medium_for_same_type(self):
        resources = (
            _resources("video", 3, skill="LowSkill", prefix="medium")
            + _resources("video", 3, skill="HotSkill", prefix="critical")
        )
        skills = [
            {"name": "HotSkill", "urgency": "Critical", "demand": 10},
            {"name": "LowSkill", "urgency": "Medium", "demand": 99},
        ]
        sessions = generate_schedule(
            horizon_days=30,
            start_date=ANCHOR_MONDAY,
            timezone=TZ,
            availability=_availability_every_weekday(),
            preferences={"weights": {"video": 1.0}, "max_sessions_per_day": 4},
            resources=resources,
            skills=skills,
        )
        scheduled_skills = [session["skill"] for session in sessions]
        first_hot = scheduled_skills.index("HotSkill")
        first_low = scheduled_skills.index("LowSkill")
        self.assertLess(first_hot, first_low)
        # Every critical resource appears before any medium one.
        last_hot = max(i for i, s in enumerate(scheduled_skills) if s == "HotSkill")
        self.assertLess(last_hot, first_low)

    def test_demand_breaks_ties_within_same_urgency(self):
        resources = (
            _resources("video", 2, skill="LowDemand", prefix="lo")
            + _resources("video", 2, skill="HighDemand", prefix="hi")
        )
        skills = [
            {"name": "LowDemand", "urgency": "High", "demand": 1},
            {"name": "HighDemand", "urgency": "High", "demand": 100},
        ]
        sessions = generate_schedule(
            horizon_days=30,
            start_date=ANCHOR_MONDAY,
            timezone=TZ,
            availability=_availability_every_weekday(),
            preferences={"weights": {"video": 1.0}, "max_sessions_per_day": 4},
            resources=resources,
            skills=skills,
        )
        scheduled_skills = [session["skill"] for session in sessions]
        self.assertLess(
            scheduled_skills.index("HighDemand"),
            scheduled_skills.index("LowDemand"),
        )


class EdgeCaseTest(unittest.TestCase):
    def test_empty_resources_returns_empty_list(self):
        sessions = generate_schedule(
            horizon_days=30,
            start_date=ANCHOR_MONDAY,
            timezone=TZ,
            availability=_availability_every_weekday(),
            preferences={},
            resources=[],
        )
        self.assertEqual(sessions, [])

    def test_no_matching_slots_returns_empty_list(self):
        # Availability only on Sunday (weekday 6) but horizon is a single day
        # starting Monday -> no concrete slots fall inside the window.
        sessions = generate_schedule(
            horizon_days=1,
            start_date=ANCHOR_MONDAY,
            timezone=TZ,
            availability=[{"weekday": 6, "start": "09:00", "end": "12:00"}],
            preferences={},
            resources=_resources("video", 5),
        )
        self.assertEqual(sessions, [])

    def test_empty_availability_raises(self):
        with self.assertRaises(ScheduleError):
            generate_schedule(
                horizon_days=30,
                start_date=ANCHOR_MONDAY,
                timezone=TZ,
                availability=[],
                preferences={},
                resources=_resources("video", 5),
            )

    def test_non_positive_horizon_raises(self):
        with self.assertRaises(ScheduleError):
            generate_schedule(
                horizon_days=0,
                start_date=ANCHOR_MONDAY,
                timezone=TZ,
                availability=_availability_every_weekday(),
                preferences={},
                resources=_resources("video", 5),
            )

    def test_unknown_timezone_raises(self):
        with self.assertRaises(ScheduleError):
            generate_schedule(
                horizon_days=30,
                start_date=ANCHOR_MONDAY,
                timezone="Mars/Phobos",
                availability=_availability_every_weekday(),
                preferences={},
                resources=_resources("video", 5),
            )

    def test_malformed_time_raises(self):
        with self.assertRaises(ScheduleError):
            generate_schedule(
                horizon_days=30,
                start_date=ANCHOR_MONDAY,
                timezone=TZ,
                availability=[{"weekday": 0, "start": "9am", "end": "18:00"}],
                preferences={},
                resources=_resources("video", 5),
            )

    def test_weekday_out_of_range_raises(self):
        with self.assertRaises(ScheduleError):
            generate_schedule(
                horizon_days=30,
                start_date=ANCHOR_MONDAY,
                timezone=TZ,
                availability=[{"weekday": 7, "start": "09:00", "end": "18:00"}],
                preferences={},
                resources=_resources("video", 5),
            )

    def test_start_not_before_end_raises(self):
        with self.assertRaises(ScheduleError):
            generate_schedule(
                horizon_days=30,
                start_date=ANCHOR_MONDAY,
                timezone=TZ,
                availability=[{"weekday": 0, "start": "18:00", "end": "09:00"}],
                preferences={},
                resources=_resources("video", 5),
            )

    def test_malformed_start_date_raises(self):
        with self.assertRaises(ScheduleError):
            generate_schedule(
                horizon_days=30,
                start_date="29-06-2026",
                timezone=TZ,
                availability=_availability_every_weekday(),
                preferences={},
                resources=_resources("video", 5),
            )

    def test_unknown_resource_type_raises(self):
        with self.assertRaises(ScheduleError):
            generate_schedule(
                horizon_days=30,
                start_date=ANCHOR_MONDAY,
                timezone=TZ,
                availability=_availability_every_weekday(),
                preferences={},
                resources=[{"type": "podcast", "title": "x", "url": None, "skill": None}],
            )


class DeterminismTest(unittest.TestCase):
    def _build(self):
        return generate_schedule(
            horizon_days=45,
            start_date=ANCHOR_MONDAY,
            timezone=TZ,
            availability=_availability_every_weekday(),
            preferences={
                "weights": {"video": 0.5, "course": 0.3, "project": 0.2},
                "session_minutes": {"video": 45, "course": 60, "project": 90},
                "max_sessions_per_day": 3,
                "gap_minutes": 15,
            },
            resources=(
                _resources("video", 20, skill="A")
                + _resources("course", 20, skill="B")
                + _resources("project", 20, skill="C")
            ),
            skills=[
                {"name": "A", "urgency": "High", "demand": 5},
                {"name": "C", "urgency": "Critical", "demand": 9},
            ],
        )

    def test_two_identical_calls_yield_identical_output(self):
        first = self._build()
        second = self._build()
        self.assertEqual(first, second)


class TimezoneConversionTest(unittest.TestCase):
    def test_local_start_converts_to_correct_utc(self):
        # 09:00 in Asia/Singapore (UTC+8) is 01:00 UTC the same day.
        sessions = generate_schedule(
            horizon_days=1,
            start_date=ANCHOR_MONDAY,
            timezone=TZ,
            availability=[{"weekday": 0, "start": "09:00", "end": "10:00"}],
            preferences={"weights": {"video": 1.0}, "session_minutes": {"video": 45}},
            resources=_resources("video", 1),
        )
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["start_utc"], "2026-06-29T01:00:00+00:00")
        self.assertEqual(sessions[0]["end_utc"], "2026-06-29T01:45:00+00:00")
        self.assertEqual(sessions[0]["uid"], "pf-0-0")


if __name__ == "__main__":
    unittest.main()
