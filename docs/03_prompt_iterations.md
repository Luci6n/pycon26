# Prompt Iterations

The product keeps scoring outside the model. Future OpenAI prompts should explain deterministic results and create readable guidance.

## System Intent

- Explain recommendations in user-friendly language.
- Never invent scoring data.
- Keep deterministic scoring separate from generated guidance.
- Cite dataset evidence and market evidence separately.
- Avoid guaranteed career outcome claims.

## Expected Model Input

- Current role
- Target role
- Transferable skills
- Missing skills
- Weighted score
- Resume/manual/GitHub skills used in scoring
- Market validation signals
- Available learning resources

## Expected Model Output

- Short transition explanation
- Why the top gaps matter
- 30/60/90 day action plan
- Source-aware caveats

## Prompt Guardrail

The model may say:

> Your resume mentions Programming and Coding, so the system moved that skill from gap to transferable.

The model must not say:

> You are guaranteed to qualify for Data Analyst roles.

## Current Implementation Note

The app currently builds explanation copy from deterministic backend data. OpenAI integration remains a clean extension point rather than a scoring dependency.
