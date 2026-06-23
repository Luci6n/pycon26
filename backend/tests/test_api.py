import unittest
import warnings
import base64
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

warnings.filterwarnings("ignore", message="Using `httpx` with `starlette.testclient` is deprecated.*")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="fastapi.testclient")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="starlette.testclient")

import fitz
from fastapi.testclient import TestClient

from backend.app.config import load_env_file
from backend.app.enrichment import actor_run_input, configured_actor_ids, normalize_job_postings
from backend.app.evidence import analyze_repository
from backend.app.main import app


class PathForgeApiTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_roles_endpoint_exposes_domain_neutral_roles(self):
        response = self.client.get("/api/roles")

        self.assertEqual(response.status_code, 200)
        titles = {role["title"] for role in response.json()["roles"]}

        self.assertIn("AI Engineer", titles)
        self.assertIn("Legal Assistant", titles)
        self.assertIn("Robotics Engineer", titles)
        self.assertIn("Graphic Designer", titles)

    def test_dataset_summary_uses_all_three_skillsfuture_files(self):
        response = self.client.get("/api/datasets/summary")

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertTrue(payload["uses_all_three_files"])
        self.assertGreater(payload["framework_roles"], 100)
        self.assertGreater(payload["role_skill_links"], 100)
        self.assertGreater(payload["mapped_unique_skills"], 100)
        self.assertGreater(payload["unique_skill_vocabulary"], 100)

    def test_official_dataset_role_search_returns_normalised_skill_profiles(self):
        response = self.client.get("/api/datasets/roles", params={"query": "audit", "limit": 5})

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertGreaterEqual(len(payload["roles"]), 1)
        first = payload["roles"][0]
        self.assertIn("title", first)
        self.assertIn("skills", first)
        self.assertGreaterEqual(len(first["skills"]), 1)
        self.assertEqual(payload["source"]["normalisation"], "framework + TSC mapping + unique skill vocabulary")

    def test_official_dataset_analysis_uses_normalised_role_profiles(self):
        response = self.client.post(
            "/api/datasets/analyze",
            json={
                "current_role": "Audit Associate / Audit Assistant Associate",
                "target_role": "Audit Manager",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(payload["current"]["title"], "Audit Associate / Audit Assistant Associate")
        self.assertEqual(payload["target"]["title"], "Audit Manager")
        self.assertIn("compatibility", payload)
        self.assertIn("transferable", payload)
        self.assertIn("missing", payload)
        self.assertGreaterEqual(len(payload["alternatives"]), 1)
        self.assertEqual(payload["source"]["normalisation"], "framework + TSC mapping + unique skill vocabulary")

    def test_official_dataset_analysis_uses_profile_skills_in_score(self):
        baseline = self.client.post(
            "/api/datasets/analyze",
            json={
                "current_role": "associate-software-engineer",
                "target_role": "data-analyst",
            },
        )
        personalized = self.client.post(
            "/api/datasets/analyze",
            json={
                "current_role": "associate-software-engineer",
                "target_role": "data-analyst",
                "profile_skills": [
                    "Programming and Coding",
                    "Data Storytelling and Visualisation",
                ],
            },
        )

        self.assertEqual(baseline.status_code, 200)
        self.assertEqual(personalized.status_code, 200)

        baseline_payload = baseline.json()
        personalized_payload = personalized.json()
        personalized_missing = {skill["name"] for skill in personalized_payload["missing"]}

        self.assertGreater(personalized_payload["compatibility"], baseline_payload["compatibility"])
        self.assertIn("Programming and Coding", personalized_payload["transferable"])
        self.assertIn("Data Storytelling and Visualisation", personalized_payload["transferable"])
        self.assertNotIn("Programming and Coding", personalized_missing)
        self.assertNotIn("Data Storytelling and Visualisation", personalized_missing)
        self.assertEqual(
            personalized_payload["profile"]["matched_skills"],
            ["Programming and Coding", "Data Storytelling and Visualisation"],
        )

    def test_official_dataset_evidence_matches_resume_text(self):
        response = self.client.post(
            "/api/evidence",
            json={
                "target_role_id": "audit-manager",
                "resume_name": "resume.md",
                "resume_text": "Data Analytics Cybersecurity and Professional Scepticism projects.",
                "manual_skills": ["Data Analytics"],
                "market_scan_enabled": True,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(payload["resume"]["status"], "text parsed")
        self.assertEqual(payload["resume"]["filename"], "resume.md")
        self.assertGreater(payload["resume"]["text_character_count"], 0)
        self.assertIn("Data Analytics Cybersecurity", payload["resume"]["excerpt"])
        self.assertIn("Data Analytics", payload["resume"]["matched_skills"])
        self.assertEqual(payload["manual_skills"]["status"], "matched")

    def test_resume_extract_endpoint_reads_selectable_pdf_text(self):
        document = fitz.open()
        page = document.new_page()
        page.insert_text((72, 72), "Python Model Evaluation portfolio project")
        pdf_bytes = document.tobytes()
        document.close()

        response = self.client.post(
            "/api/resume/extract",
            json={
                "filename": "resume.pdf",
                "content_base64": base64.b64encode(pdf_bytes).decode("ascii"),
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "parsed")
        self.assertEqual(payload["filename"], "resume.pdf")
        self.assertIn("Python Model Evaluation", payload["text"])
        self.assertGreater(payload["text_character_count"], 0)

    def test_transition_backend_matches_prd_example(self):
        response = self.client.post(
            "/api/analyze",
            json={"current_role_id": "backend-developer", "target_role_id": "ai-engineer"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(payload["compatibility"], 73)
        self.assertEqual(payload["difficulty"], "Medium")
        self.assertEqual(payload["transferable"][:4], ["Python", "APIs", "SQL", "Docker"])
        self.assertEqual(payload["missing"][0]["name"], "Machine Learning Fundamentals")
        self.assertGreaterEqual(len(payload["alternatives"]), 3)
        self.assertIn("Dataset overlap", {item["label"] for item in payload["evidence"]})

    def test_evidence_endpoint_detects_resume_repo_links_and_market_signal(self):
        response = self.client.post(
            "/api/evidence",
            json={
                "target_role_id": "ai-engineer",
                "resume_name": "resume.md",
                "resume_text": "Python APIs SQL Docker Model Evaluation and Responsible AI projects.",
                "github_url": "https://github.com/example/pathforge",
                "portfolio_links": [
                    "https://portfolio.example/work",
                    "https://case-study.example/robotics",
                ],
                "market_scan_enabled": True,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(payload["resume"]["status"], "text parsed")
        self.assertEqual(payload["resume"]["filename"], "resume.md")
        self.assertGreater(payload["resume"]["text_character_count"], 0)
        self.assertIn("Python APIs SQL Docker", payload["resume"]["excerpt"])
        self.assertIn("Model Evaluation", payload["resume"]["matched_skills"])
        self.assertEqual(payload["repository"]["status"], "captured")
        self.assertEqual(payload["repository"]["owner"], "example")
        self.assertEqual(payload["portfolio"]["status"], "strong evidence base")
        self.assertIn("Machine Learning Fundamentals", payload["market"]["skills"])

    def test_github_profile_live_fetch_returns_repo_language_signals(self):
        payload = [
            {
                "name": "pathforge-api",
                "language": "Python",
                "topics": ["fastapi", "career"],
                "html_url": "https://github.com/example/pathforge-api",
                "fork": False,
            },
            {
                "name": "pathforge-ui",
                "language": "TypeScript",
                "topics": ["react"],
                "html_url": "https://github.com/example/pathforge-ui",
                "fork": False,
            },
        ]

        with patch("backend.app.evidence.urlopen") as mocked_urlopen:
            mocked_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(payload).encode("utf-8")
            result = analyze_repository("https://github.com/example", fetch_repository=True)

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["owner"], "example")
        self.assertIsNone(result["repo"])
        self.assertEqual(len(result["repositories"]), 2)
        self.assertEqual(result["public_repository_count"], 2)
        self.assertIn("Python", result["languages"])
        self.assertIn("APIs", result["inferred_skills"])

    def test_unknown_role_returns_404(self):
        response = self.client.post(
            "/api/analyze",
            json={"current_role_id": "unknown", "target_role_id": "ai-engineer"},
        )

        self.assertEqual(response.status_code, 404)

    def test_exa_resource_endpoint_has_safe_unconfigured_mode(self):
        with patch.dict("os.environ", {}, clear=True):
            response = self.client.post(
                "/api/enrich/resources",
                json={"skill": "Vector Databases", "target_role": "AI Engineer"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertFalse(payload["configured"])
        self.assertEqual(payload["provider"], "exa")
        self.assertIn("Vector Databases", payload["query"])

    def test_apify_market_endpoint_has_safe_unconfigured_mode(self):
        with patch.dict("os.environ", {}, clear=True):
            response = self.client.post(
                "/api/enrich/market",
                json={"target_role": "AI Engineer", "skills": ["Python", "MLOps"]},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertFalse(payload["configured"])
        self.assertEqual(payload["provider"], "apify")
        self.assertEqual(payload["skills"], ["Python", "MLOps"])
        self.assertEqual(payload["jobs"], [])

    def test_apify_actor_ids_support_multiple_configured_actors(self):
        with patch.dict(
            "os.environ",
            {
                "APIFY_JOB_ACTOR_IDS": "MXLpngmVpE8WTESQr, s3dtSTZSZWFtAVLn5, hKByXkMQaC5Qt9UMN",
                "APIFY_JOB_ACTOR_ID": "legacy",
            },
            clear=True,
        ):
            self.assertEqual(
                configured_actor_ids(),
                ["MXLpngmVpE8WTESQr", "s3dtSTZSZWFtAVLn5", "hKByXkMQaC5Qt9UMN"],
            )

    def test_apify_actor_payloads_match_selected_actor_family(self):
        indeed = actor_run_input("MXLpngmVpE8WTESQr", "AI Engineer", ["Python"], "Singapore")
        fantastic_jobs = actor_run_input("s3dtSTZSZWFtAVLn5", "AI Engineer", ["Python"], "Singapore")
        seek = actor_run_input("m7tdxsBaMKJhIu4fM", "AI Engineer", ["Python"], "Singapore")
        linkedin = actor_run_input("hKByXkMQaC5Qt9UMN", "AI Engineer", ["Python"], "Singapore")

        self.assertEqual(indeed["query"], "AI Engineer")
        self.assertEqual(fantastic_jobs["titleSearch"], "AI Engineer")
        self.assertEqual(seek["searchTerm"], "AI Engineer")
        self.assertIn("linkedin.com/jobs/search", linkedin["startUrls"][0]["url"])

        global_indeed = actor_run_input("MXLpngmVpE8WTESQr", "AI Engineer", ["Python"], "")
        global_fantastic_jobs = actor_run_input("s3dtSTZSZWFtAVLn5", "AI Engineer", ["Python"], "")
        global_linkedin = actor_run_input("hKByXkMQaC5Qt9UMN", "AI Engineer", ["Python"], "")

        self.assertNotIn("location", global_indeed)
        self.assertNotIn("country", global_indeed)
        self.assertEqual(global_fantastic_jobs["locationSearch"], "Worldwide")
        self.assertIn("location=Worldwide", global_linkedin["startUrls"][0]["url"])

    def test_apify_job_items_are_normalized_for_frontend_cards(self):
        jobs = normalize_job_postings(
            [
                {
                    "jobTitle": "AI Engineer",
                    "companyName": "Acme AI",
                    "jobUrl": "https://jobs.example/ai-engineer",
                    "descriptionText": "Build Python evaluation pipelines for production AI systems.",
                    "location": "Singapore",
                    "skills": ["Python", "Model Evaluation"],
                }
            ],
            ["Python", "Model Evaluation", "Vector Databases"],
        )

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["title"], "AI Engineer")
        self.assertEqual(jobs[0]["company"], "Acme AI")
        self.assertEqual(jobs[0]["url"], "https://jobs.example/ai-engineer")
        self.assertIn("Python", jobs[0]["skills"])

    def test_apify_nested_url_aliases_are_normalized_for_clickable_cards(self):
        jobs = normalize_job_postings(
            [
                {
                    "title": "Data Analyst",
                    "company": "Acme Data",
                    "metadata": {
                        "logoUrl": "https://cdn.example/logo.png",
                        "posting": {"href": "https://jobs.example/data-analyst"},
                    },
                    "description": "Build SQL dashboards and analytics reports.",
                    "requiredSkills": [{"label": "SQL"}],
                }
            ],
            ["SQL"],
        )

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["url"], "https://jobs.example/data-analyst")
        self.assertIn("SQL", jobs[0]["skills"])

    def test_apify_indeed_location_aliases_are_normalized_for_cards(self):
        jobs = normalize_job_postings(
            [
                {
                    "title": "Accounting & Administration Executive",
                    "companyName": "Alliance 21 Group Pte Ltd",
                    "companyLocation": "East Singapore",
                    "jobType": "Full-time",
                    "description": "Manage accounts receivable and GST reporting.",
                    "skills": [{"label": "GST"}],
                }
            ],
            ["GST"],
        )

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["location"], "East Singapore")

    def test_apify_structured_skill_objects_are_normalized_to_labels(self):
        jobs = normalize_job_postings(
            [
                {
                    "title": "Accounting & Administration Executive",
                    "companyName": "Alliance 21 Group Pte Ltd",
                    "description": "*Main Purpose* Manage accounts receivable and GST reporting.",
                    "skills": [
                        {"label": "Accounts receivable", "requirementSeverity": "PREFERRED"},
                        {"label": "Bank reconciliation", "requirementSeverity": "PREFERRED"},
                        {"label": "GST", "requirementSeverity": "PREFERRED"},
                    ],
                }
            ],
            ["GST"],
        )

        self.assertEqual(jobs[0]["skills"], ["GST", "Accounts receivable", "Bank reconciliation"])
        self.assertNotIn("{'label'", " ".join(jobs[0]["skills"]))
        self.assertNotIn("*Main Purpose*", jobs[0]["description"])

    def test_env_file_loader_sets_missing_environment_values(self):
        with TemporaryDirectory() as directory:
            env_path = Path(directory) / ".env"
            env_path.write_text("EXA_API_KEY=test-exa\nAPIFY_API_TOKEN='test-apify'\n", encoding="utf-8")

            with patch.dict("os.environ", {}, clear=True):
                load_env_file(env_path)
                self.assertEqual(__import__("os").environ["EXA_API_KEY"], "test-exa")
                self.assertEqual(__import__("os").environ["APIFY_API_TOKEN"], "test-apify")

    def test_optional_user_login_can_save_roadmap(self):
        with TemporaryDirectory() as directory:
            db_path = str(Path(directory) / "auth.sqlite3")

            with patch.dict("os.environ", {"PATHFORGE_AUTH_DB": db_path}, clear=False):
                register = self.client.post(
                    "/api/auth/register",
                    json={
                        "email": "user@example.com",
                        "password": "strong-password",
                        "name": "Demo User",
                    },
                )

                self.assertEqual(register.status_code, 200)
                token = register.json()["token"]

                blocked = self.client.get("/api/roadmaps")
                self.assertEqual(blocked.status_code, 401)

                saved = self.client.post(
                    "/api/roadmaps",
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "title": "AI Engineer plan",
                        "current_role_id": "backend-developer",
                        "target_role_id": "ai-engineer",
                        "payload": {"compatibility": 73},
                    },
                )
                self.assertEqual(saved.status_code, 200)
                self.assertEqual(saved.json()["roadmap"]["title"], "AI Engineer plan")

                listing = self.client.get("/api/roadmaps", headers={"Authorization": f"Bearer {token}"})
                self.assertEqual(listing.status_code, 200)
                self.assertEqual(len(listing.json()["roadmaps"]), 1)

    def test_admin_role_can_list_users_and_roadmaps(self):
        with TemporaryDirectory() as directory:
            db_path = str(Path(directory) / "auth.sqlite3")

            with patch.dict(
                "os.environ",
                {
                    "PATHFORGE_AUTH_DB": db_path,
                    "PATHFORGE_ADMIN_EMAILS": "admin@example.com",
                },
                clear=False,
            ):
                admin = self.client.post(
                    "/api/auth/register",
                    json={"email": "admin@example.com", "password": "strong-password"},
                )
                user = self.client.post(
                    "/api/auth/register",
                    json={"email": "user@example.com", "password": "strong-password"},
                )

                self.assertEqual(admin.status_code, 200)
                self.assertEqual(user.status_code, 200)
                admin_token = admin.json()["token"]
                user_token = user.json()["token"]

                denied = self.client.get("/api/admin/users", headers={"Authorization": f"Bearer {user_token}"})
                self.assertEqual(denied.status_code, 403)

                users = self.client.get("/api/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
                self.assertEqual(users.status_code, 200)
                self.assertEqual(len(users.json()["users"]), 2)


if __name__ == "__main__":
    unittest.main()
