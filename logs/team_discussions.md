# Team Discussions

## Track Selection

Decision:

- Build for Job & Skills.

Options considered:

- Open track creative app.
- Job & Skills career transition planner.

Rationale:

- Job & Skills aligns with the rubric's data integrity, data quality, user focus, explainability, and process evidence requirements.

Owner:

- Product lead.

Follow-up:

- Keep SkillsFuture data visible in backend and README evidence, not as noisy UI chrome.

## UI Scope

Decision:

- Remove the process-score panel, 3-person team structure, dataset sidebar, and recommendation pipeline from the main app UI.

Rationale:

- Users need career analysis, not internal submission scaffolding.
- Judges can inspect process evidence in the repository.

Owner:

- Product and frontend.

Follow-up:

- Keep docs and logs updated before submission.

## Scoring Personalization

Decision:

- Resume/manual/GitHub skills can change the score when they match target-role skills.

Rationale:

- A user's current role alone can understate their actual evidence.
- The system should credit proof without letting unrelated keywords inflate the score.

Owner:

- Backend and data.

Follow-up:

- Add fuzzy matching and synonyms after the MVP.
