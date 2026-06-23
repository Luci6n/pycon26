# Cursor / Codex Logs

## 2026-06-23: Frontend And Backend Build Session

Task:

- Build PathForge AI from the PRD.
- Create a React/Vite frontend and FastAPI backend.
- Add SkillsFuture role search, scoring, resume extraction, evidence analysis, Exa resources, Apify job postings, optional login, and saved roadmaps.

Agent suggestions:

- Keep scoring deterministic.
- Use PyMuPDF for PDF extraction.
- Use all three SkillsFuture workbooks.
- Treat Exa and Apify as enrichment layers.
- Split resume/CV and links/portfolio intake into capsule tabs.
- Add stale-run guards to prevent old async results from overwriting new target-role analysis.

Human decisions:

- Use Python 3.11.
- Remove internal process and team-structure panels from the user UI.
- Keep Apify enabled as part of analysis rather than a visible toggle.
- Let profile evidence affect scoring.

Resulting changes:

- `backend/app/scoring.py` accepts profile skills.
- `backend/app/evidence.py` analyzes resume/manual/GitHub/portfolio evidence.
- `backend/app/enrichment.py` normalizes Exa and Apify results.
- `src/App.jsx` coordinates personalized analysis and async enrichment.
- `README.md`, `docs/`, and `logs/` now document the current product and process.

Verification:

- `npm run test:backend` passed with 22 tests.
- `npm run build` passed.
- Live API smoke confirmed profile skills are used in scoring.
