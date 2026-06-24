import unittest
import warnings
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

warnings.filterwarnings("ignore", message="Using `httpx` with `starlette.testclient` is deprecated.*")
warnings.filterwarnings("ignore", category=DeprecationWarning)

from fastapi.testclient import TestClient

from backend.app.main import app

RESOURCES = [
    {"type": "video", "title": "Intro to Python", "url": "https://ex/1", "skill": "Python"},
    {"type": "video", "title": "Async Python", "url": "https://ex/2", "skill": "Python"},
    {"type": "book", "title": "Fluent Python", "url": "https://ex/3", "skill": "Python"},
    {"type": "course", "title": "ML Crash Course", "url": "https://ex/4", "skill": "Machine Learning"},
    {"type": "project", "title": "Build a Classifier", "url": "https://ex/5", "skill": "Machine Learning"},
]

AVAILABILITY = [{"weekday": d, "start": "19:00", "end": "21:00"} for d in range(7)]

GENERATE_BODY = {
    "target_role": "AI Engineer",
    "horizon_days": 30,
    "timezone": "Asia/Singapore",
    "availability": AVAILABILITY,
    "preferences": {"weights": {"video": 0.6, "book": 0.2, "course": 0.1, "project": 0.1}},
    "resources": RESOURCES,
    "skills": [{"name": "Python", "urgency": "Critical", "demand": 90}],
}


class ScheduleApiTest(unittest.TestCase):
    def setUp(self):
        # No LLM keys -> deterministic path; keeps assertions stable.
        self._env = patch.dict("os.environ", {}, clear=False)
        self._env.start()
        for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "LLM_PROVIDER"):
            __import__("os").environ.pop(key, None)
        self.client = TestClient(app)

    def tearDown(self):
        self._env.stop()

    def test_generate_returns_valid_sessions(self):
        response = self.client.post("/api/schedule/generate", json=GENERATE_BODY)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreater(payload["session_count"], 0)
        sessions = payload["sessions"]
        for session in sessions:
            self.assertIn(session["resource_type"], ("video", "course", "book", "project"))
            self.assertTrue(session["start_utc"].endswith("+00:00"))
            self.assertLess(session["start_utc"], session["end_utc"])
        # ordered by start time
        starts = [s["start_utc"] for s in sessions]
        self.assertEqual(starts, sorted(starts))

    def test_generate_rejects_empty_availability(self):
        body = {**GENERATE_BODY, "availability": []}
        response = self.client.post("/api/schedule/generate", json=body)
        self.assertEqual(response.status_code, 400)

    def test_export_ics_preview_returns_calendar(self):
        generated = self.client.post("/api/schedule/generate", json=GENERATE_BODY).json()
        response = self.client.post(
            "/api/schedule/export.ics",
            json={"title": "My Plan", "sessions": generated["sessions"]},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/calendar", response.headers["content-type"])
        self.assertIn("attachment;", response.headers["content-disposition"])
        self.assertTrue(response.text.startswith("BEGIN:VCALENDAR"))
        self.assertEqual(response.text.count("BEGIN:VEVENT"), generated["session_count"])

    def test_save_requires_login(self):
        response = self.client.post("/api/schedules", json={"sessions": []})
        self.assertEqual(response.status_code, 401)

    def test_full_save_complete_progress_flow(self):
        with TemporaryDirectory() as directory:
            db_path = str(Path(directory) / "auth.sqlite3")
            with patch.dict("os.environ", {"PATHFORGE_AUTH_DB": db_path}, clear=False):
                token = self.client.post(
                    "/api/auth/register",
                    json={"email": "learner@example.com", "password": "strong-password"},
                ).json()["token"]
                auth = {"Authorization": f"Bearer {token}"}

                generated = self.client.post("/api/schedule/generate", json=GENERATE_BODY).json()
                saved = self.client.post(
                    "/api/schedules",
                    headers=auth,
                    json={
                        "title": "AI plan",
                        "target_role_id": "ai-engineer",
                        "horizon_days": 30,
                        "timezone": "Asia/Singapore",
                        "preferences": GENERATE_BODY["preferences"],
                        "availability": AVAILABILITY,
                        "sessions": generated["sessions"],
                    },
                )
                self.assertEqual(saved.status_code, 200)
                schedule_id = saved.json()["schedule"]["id"]
                sessions = saved.json()["schedule"]["sessions"]
                self.assertGreater(len(sessions), 0)

                # listing
                listing = self.client.get("/api/schedules", headers=auth)
                self.assertEqual(len(listing.json()["schedules"]), 1)

                # short reflection rejected
                first_session = sessions[0]["id"]
                short = self.client.post(
                    f"/api/sessions/{first_session}/complete",
                    headers=auth,
                    json={"content": "too short"},
                )
                self.assertEqual(short.status_code, 400)

                # substantive reflection accepted
                ok = self.client.post(
                    f"/api/sessions/{first_session}/complete",
                    headers=auth,
                    json={"content": "I learned how Python async event loops schedule coroutines."},
                )
                self.assertEqual(ok.status_code, 200)
                self.assertEqual(ok.json()["session"]["status"], "completed")

                # progress reflects one completion
                progress = self.client.get(f"/api/schedules/{schedule_id}/progress", headers=auth).json()
                self.assertEqual(progress["completed"], 1)
                self.assertEqual(progress["total"], len(sessions))
                self.assertGreater(progress["percent"], 0)

                # saved schedule exports ICS
                ics = self.client.get(f"/api/schedules/{schedule_id}/export.ics", headers=auth)
                self.assertEqual(ics.status_code, 200)
                self.assertIn("text/calendar", ics.headers["content-type"])

    def test_linkedin_draft_and_share_page(self):
        with TemporaryDirectory() as directory:
            db_path = str(Path(directory) / "auth.sqlite3")
            with patch.dict("os.environ", {"PATHFORGE_AUTH_DB": db_path}, clear=False):
                token = self.client.post(
                    "/api/auth/register",
                    json={"email": "poster@example.com", "password": "strong-password"},
                ).json()["token"]
                auth = {"Authorization": f"Bearer {token}"}

                draft = self.client.post(
                    "/api/linkedin/draft",
                    headers=auth,
                    json={"target_role": "AI Engineer"},
                )
                self.assertEqual(draft.status_code, 200)
                self.assertIsInstance(draft.json()["caption"], str)
                self.assertEqual(draft.json()["source_count"], 0)

                created = self.client.post(
                    "/api/share/create",
                    headers=auth,
                    json={"title": "My progress", "completed_count": 3, "target_role": "AI Engineer",
                          "highlights": ["Finished Fluent Python"]},
                )
                self.assertEqual(created.status_code, 200)
                share_url = created.json()["share_url"]
                self.assertIn("linkedin.com/sharing/share-offsite", share_url)

                page = self.client.get(f"/share/{created.json()['token']}")
                self.assertEqual(page.status_code, 200)
                self.assertIn('property="og:title"', page.text)
                self.assertIn("My progress", page.text)

    def test_linkedin_oauth_scaffold_not_configured(self):
        with patch.dict("os.environ", {}, clear=True):
            response = self.client.get("/api/integrations/linkedin/authorize")
        self.assertEqual(response.status_code, 501)


if __name__ == "__main__":
    unittest.main()
