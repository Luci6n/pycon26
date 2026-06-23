# Final Reflections

Complete this file near submission time. Current draft:

## What AI Helped With

- Compared product directions against the judging rubric.
- Drafted the PRD and feature scope.
- Generated implementation options for React, FastAPI, dataset ingestion, Exa, Apify, and GitHub evidence.
- Helped write code, tests, docs, and README content.

## What Humans Decided

- Job & Skills was the strongest track fit.
- PathForge AI should stay data-first and explainable.
- The UI should focus on analysis, not internal process evidence.
- Resume/manual/GitHub evidence should affect scoring only when it matches SkillsFuture target skills.

## Data Limitations

- SkillsFuture role-skill mappings are broad and may not capture every employer-specific requirement.
- Resume skill matching currently uses exact vocabulary matches against target-role skills.
- GitHub analysis only reads public repository signals unless a token grants more access.
- Live job-posting results depend on configured Apify actors and selected country scope.

## Ethical Risks

- Users may over-trust a career score.
- Role recommendations can miss context from personal constraints, education, location, or hiring bias.
- Scraped job data may be incomplete or stale.

## Next Improvements

- Add OpenAI-generated explanations with citations from deterministic evidence.
- Add fuzzy skill matching and synonyms for resume extraction.
- Add stronger portfolio analysis for non-software users.
- Add user feedback capture after each recommendation.
