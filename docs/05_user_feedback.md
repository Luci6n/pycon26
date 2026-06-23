# User Feedback

User direction captured during the build:

- Combine the best parts of both PRDs.
- Keep the build practical for the hackathon.
- Include OpenAI, Exa, Apify, explainability, and 50% process-score evidence.
- Build a Python backend, not only a frontend prototype.
- Use all three SkillsFuture datasets.
- Support resume upload, manual skills, GitHub profile scanning, LinkedIn, portfolio, and extra links.
- Keep the tool domain-neutral for law, art, engineering, finance, software, and other fields.
- Remove internal process panels from the user UI.
- Make Apify always part of analysis rather than a user-facing toggle.
- Show job cards with company, title, description, skills, location, and links.
- Separate resume/CV and links/portfolio intake into capsule tabs.
- Fix stale async states when changing target roles or loading saved roadmaps.

## Product Response

- PathForge AI brand retained.
- Deterministic SkillsFuture scoring retained.
- Resume/manual/GitHub skills now feed personalized scoring.
- Exa and Apify run as enrichment layers.
- Optional login lets users save roadmaps.
- Process evidence moved to repository docs and logs.
- Async run guards prevent older analysis responses from overwriting the latest target-role run.
