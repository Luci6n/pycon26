# Architecture Decisions

## Decision 1: Dataset-first recommendations

Skill scoring, role matching, and priority ranking stay deterministic. SkillsFuture role-skill data defines the base comparison.

## Decision 2: Profile evidence can personalize scoring

Resume matches, typed skills, GitHub language/topic signals, and portfolio evidence can support the user's profile. When those skills match the target-role vocabulary, the backend adds them to the user's current skill set for scoring.

This changes:

- Compatibility score
- Transferable skills
- Priority gaps
- Roadmap focus
- Evidence explanation

The app does not give arbitrary credit for unrelated keywords.

## Decision 3: Current architecture

The current implementation uses:

- FastAPI backend
- SQLite for saved roadmaps and optional accounts
- SkillsFuture Excel ingestion through openpyxl
- PyMuPDF for PDF resume extraction
- React/Vite frontend
- Exa resource discovery
- Apify job-market validation
- GitHub API profile and repository analysis

Recommended service ownership:

- OpenAI: explain skill gaps, summarize findings, and generate polished 30/60/90 day guidance.
- Exa: find recent learning resources, trends, and citations for missing skills.
- Apify: collect structured job postings for market validation.
- GitHub: inspect public repository language, topics, and repo names as profile evidence.

## Decision 4: External services should not block the core result

The app returns the core analysis after deterministic evidence and scoring complete. Exa and Apify run as enrichment. GitHub can refine the score after the first result if the profile scan finds extra relevant skills.

The frontend tracks the current analysis run so old requests cannot overwrite a newer target-role analysis.

## Decision 5: Evidence intake should stay domain-neutral

The product should not assume the user is in software or computer science.

Supported evidence types:

- Resume or CV upload
- Typed skills
- GitHub or repository links for code-heavy users
- Portfolio links for art, design, law, research, engineering, and other domains
- Publications, case studies, CAD samples, writing samples, or project pages

GitHub analysis is useful, but it is not the only proof-of-skill path.

## Decision 6: Process evidence belongs in the repository

The app UI focuses on the user workflow. The hackathon process score is documented through `/docs` and `/logs`, where judges can inspect decisions, prompt iterations, user feedback, and responsibility splits.
