# PathForge AI

PathForge AI helps a user compare a current role with a target role, then builds a practical transition plan from SkillsFuture role-skill data, profile evidence, live job postings, and learning resources.

The app was built for the PyCon SG 2026 hackathon, Job & Skills track.

## What It Does

- Compares current and target roles from the SkillsFuture Job & Skills dataset.
- Calculates compatibility, difficulty, transferable skills, and priority gaps.
- Accepts resume text, PDF uploads, typed skills, GitHub profiles, LinkedIn, portfolio, and other proof links.
- Uses matched resume/manual/GitHub skills as scoring inputs, so the score reflects the user's evidence instead of only the selected current role.
- Searches learning resources through Exa when `EXA_API_KEY` is configured.
- Searches current job postings through Apify when `APIFY_API_TOKEN` and actor IDs are configured.
- Lets signed-in users save and reload roadmaps. Login is optional for analysis.

## Tech Stack

- Frontend: React 19, Vite, lucide-react
- Backend: FastAPI, Python 3.11
- Dataset parsing: openpyxl
- Resume parsing: PyMuPDF
- Tests: Python unittest through `npm run test:backend`
- External services: Exa, Apify, GitHub API

## Project Structure

```text
backend/              FastAPI app, scoring, dataset loading, evidence analysis
datasets/             SkillsFuture source workbooks
docs/                 Hackathon process notes and decisions
logs/                 Human-AI collaboration logs for submission
public/               Static frontend assets
src/                  React frontend
.env.example          Local environment variable template
```

## Dataset Usage

The backend reads all three SkillsFuture files in `datasets/`:

- `jobsandskills-skillsfuture-skills-framework-dataset.xlsx`
- `jobsandskills-skillsfuture-tsc-to-unique-skills-mapping.xlsx`
- `jobsandskills-skillsfuture-unique-skills-list.xlsx`

The framework workbook provides official job roles and role-skill links. The mapping workbook converts Skills Framework skills into updated unique skill names. The unique skills workbook validates the final vocabulary.

Use `GET /api/datasets/summary` to confirm the backend loaded all three files.

## Requirements

- Node.js 20 or newer
- Python 3.11
- Windows PowerShell commands below assume this project path:

```powershell
C:\Work and School\project\pycon26
```

## Setup

```powershell
cd "C:\Work and School\project\pycon26"
npm install
& "C:\Users\User\AppData\Local\Programs\Python\Python311\python.exe" -m venv .venv
.\.venv\Scripts\python -m pip install -r backend\requirements.txt
Copy-Item .env.example .env
```

Edit `.env` only on your machine. Do not commit real API keys.

## Run Locally

Start the backend:

```powershell
npm run api
```

Start the frontend in another terminal:

```powershell
npm run dev
```

Open the app:

```text
http://127.0.0.1:5173/
```

Useful backend URLs:

```text
http://127.0.0.1:8010/api/health
http://127.0.0.1:8010/api/datasets/summary
http://127.0.0.1:8010/docs
```

## Environment Variables

`.env.example` contains the local template:

```text
EXA_API_KEY=
APIFY_API_TOKEN=
GITHUB_TOKEN=
VITE_API_BASE_URL=http://127.0.0.1:8010
APIFY_JOB_ACTOR_IDS=MXLpngmVpE8WTESQr,s3dtSTZSZWFtAVLn5,hKByXkMQaC5Qt9UMN
APIFY_JOB_ACTOR_ID=
```

Service behavior:

- Exa powers the learning-resource search.
- Apify powers current job-posting validation.
- GitHub profile analysis works with public repositories without a token. Add `GITHUB_TOKEN` for higher rate limits or private access later.
- If Exa or Apify keys are missing, the API returns a safe unconfigured response instead of failing the whole analysis.

Configured Apify actors:

- `MXLpngmVpE8WTESQr`: Indeed job scraper
- `s3dtSTZSZWFtAVLn5`: Fantastic.jobs career-site listing API
- `hKByXkMQaC5Qt9UMN`: LinkedIn jobs scraper
- `m7tdxsBaMKJhIu4fM`: SEEK job scraper, optional for markets where SEEK fits

## Key API Routes

```text
GET  /api/datasets/summary
GET  /api/datasets/roles?query=audit&limit=5
POST /api/datasets/analyze
POST /api/resume/extract
POST /api/evidence
POST /api/enrich/resources
POST /api/enrich/market
POST /api/auth/register
POST /api/auth/login
GET  /api/roadmaps
POST /api/roadmaps
```

`POST /api/datasets/analyze` accepts `profile_skills`. The backend treats those as extra user-owned skills when they match the target role vocabulary.

Example:

```json
{
  "current_role": "associate-software-engineer",
  "target_role": "data-analyst",
  "profile_skills": [
    "Programming and Coding",
    "Data Storytelling and Visualisation"
  ]
}
```

## Verification

Run backend tests:

```powershell
npm run test:backend
```

Build the frontend:

```powershell
npm run build
```

Recommended demo smoke check:

1. Choose a current role and target role.
2. Paste resume text or upload a PDF.
3. Add a few typed skills.
4. Run Analyze profile.
5. Change the target role and run again.
6. Confirm the resume extraction, score, gaps, learning resources, and job postings belong to the latest run.

## Notes For Judges

PathForge keeps scoring deterministic. SkillsFuture data and profile evidence decide the skill overlap. OpenAI-style explanation layers can explain the result, but they should not invent the score.

The `docs/` and `logs/` folders capture the process evidence requested by the hackathon rubric, including problem discovery, prompt iterations, architecture decisions, team responsibility, and human-AI collaboration notes.
