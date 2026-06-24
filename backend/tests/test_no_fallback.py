from pathlib import Path
import unittest

from fastapi.testclient import TestClient

from backend.app.main import app


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class NoFallbackTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_legacy_demo_role_endpoints_are_removed(self):
        roles_response = self.client.get("/api/roles")
        analyze_response = self.client.post(
            "/api/analyze",
            json={
                "current_role_id": "student",
                "target_role_id": "data-analyst",
            },
        )

        self.assertEqual(roles_response.status_code, 404)
        self.assertEqual(analyze_response.status_code, 404)

    def test_frontend_does_not_import_local_role_fallback(self):
        app_source = (PROJECT_ROOT / "src" / "App.jsx").read_text()
        api_source = (PROJECT_ROOT / "src" / "utils" / "api.js").read_text()

        self.assertNotIn("./data/roles.js", app_source)
        self.assertNotIn("analyzeTransition", app_source)
        self.assertNotIn('setApiStatus("fallback")', app_source)
        self.assertNotIn("/api/roles", api_source)
        self.assertFalse((PROJECT_ROOT / "src" / "data" / "roles.js").exists())

    def test_cors_allows_worktree_dev_port(self):
        response = self.client.options(
            "/api/health",
            headers={
                "Origin": "http://127.0.0.1:5174",
                "Access-Control-Request-Method": "GET",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], "http://127.0.0.1:5174")


if __name__ == "__main__":
    unittest.main()
