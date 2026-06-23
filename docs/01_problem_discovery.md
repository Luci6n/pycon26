# Problem Discovery

PathForge AI targets the PyCon SG 2026 Hackathon Job & Skills track.

Career switchers can name the role they want, but they often cannot tell which current skills transfer, which gaps matter most, or whether the transition is realistic. Fresh graduates and mid-career professionals face the same problem when their evidence sits across resumes, GitHub, LinkedIn, portfolios, and project links.

The product needs to answer one practical question:

> How do I get from my current role to my target role, and which evidence supports that path?

## Product Constraints

- Use SkillsFuture data as the ground-truth role and skill layer.
- Keep scoring deterministic and inspectable.
- Use user evidence to personalize the score when the evidence matches target-role skills.
- Use live job postings and learning resources as enrichment, not as the only source of truth.
- Avoid guaranteed career-outcome claims.

## Primary Users

- Career switchers comparing their current role against a target role.
- Fresh graduates trying to identify credible entry paths.
- Mid-career professionals who need to translate existing experience into a new domain.

## Current Product Answer

The app compares a current role and target role, extracts skills from resume/manual/GitHub evidence, recalculates the score with matched profile skills, then returns transferable skills, priority gaps, adjacent routes, learning resources, and current job postings.
