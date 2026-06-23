# ChatGPT Logs

## 2026-06-23: Product Direction And PRD Refinement

Prompt summary:

- Compare the Job & Skills track against the Open track using the PyCon SG 2026 rubric.
- Decide between two PRD directions.
- Incorporate SkillsFuture, OpenAI, Exa, Apify, explainability, and process-score evidence.

Key output:

- Job & Skills had the strongest rubric fit because it supports data integrity, data quality, explainability, and process documentation.
- The product should answer a single career-transition question rather than act as a generic chatbot.
- OpenAI should explain deterministic recommendations, not decide the score.
- Exa should find learning resources.
- Apify should validate market demand through current job postings.

Human decision:

- Build PathForge AI as a dataset-first career transition planner.
- Keep deterministic scoring at the core.
- Include process evidence in `docs/` and `logs/`.

Project change:

- README and docs now describe the split between deterministic scoring, profile evidence, and enrichment services.

## 2026-06-23: Feature Scope Updates

Prompt summary:

- Add resume upload, manual skills, GitHub profile scanning, LinkedIn, portfolio links, job postings, and learning resources.
- Keep the product domain-neutral.
- Remove internal process panels from the user UI.

Key output:

- Evidence intake should support more than software users.
- GitHub should be optional evidence, not the main profile path.
- Resume/manual/GitHub skills should feed scoring when they match target-role skills.

Human decision:

- Personalize the compatibility score with matched profile skills.
- Keep optional login for saved roadmaps.

Project change:

- Backend scoring now accepts `profile_skills`.
- Frontend sends resume/manual/GitHub evidence into personalized analysis.
