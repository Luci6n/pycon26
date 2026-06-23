from __future__ import annotations

from .data import ROLES, role_index

DEFAULT_WEIGHT = 50


class UnknownRoleError(ValueError):
    pass


def get_role(role_id: str) -> dict:
    role = role_index().get(role_id)
    if not role:
        raise UnknownRoleError(role_id)
    return role


def analyze_transition(current_role_id: str, target_role_id: str) -> dict:
    current = get_role(current_role_id)
    target = get_role(target_role_id)
    alternatives = [
        role
        for role in ROLES
        if role["id"] not in {current["id"], target["id"]} and role.get("required")
    ]

    return analyze_profiles(current, target, alternatives=alternatives)


def analyze_profiles(
    current: dict,
    target: dict,
    alternatives: list[dict] | None = None,
    profile_skills: list[str] | None = None,
) -> dict:
    profile = build_profile_context(current, target, profile_skills)
    augmented_current = {**current, "skills": profile["augmented_skills"]}
    current_skills = set(augmented_current["skills"])
    target_weights = target.get("required") or {skill: DEFAULT_WEIGHT for skill in target["skills"]}
    target_skills = list(target_weights.keys())

    transferable = sorted(
        [skill for skill in target_skills if skill in current_skills],
        key=lambda skill: target_weights[skill],
        reverse=True,
    )

    missing = sorted(
        [
            {
                "name": skill,
                "demand": target_weights[skill],
                "urgency": urgency_for(target_weights[skill]),
            }
            for skill in target_skills
            if skill not in current_skills
        ],
        key=lambda skill: skill["demand"],
        reverse=True,
    )

    total_weight = sum(target_weights[skill] for skill in target_skills)
    overlap_weight = sum(target_weights[skill] for skill in transferable)
    raw_overlap = overlap_weight / total_weight if total_weight else 0
    bridge_score = transition_bridge_score(role_family(current), role_family(target))
    compatibility = clamp(round(15 + raw_overlap * 65 + bridge_score * 0.35), 5, 96)
    difficulty = "Low" if compatibility >= 75 else "Medium" if compatibility >= 55 else "High"

    alternative_results = []
    if alternatives:
        scored_alternatives = []
        for role in alternatives:
            if not role.get("required"):
                continue

            score = analyze_pair(augmented_current, role)
            scored_alternatives.append(
                {
                    "id": role["id"],
                    "title": role["title"],
                    "family": role_family(role),
                    "score": score["compatibility"],
                    "missingCount": score["missingCount"],
                }
            )

        alternative_results = sorted(
            scored_alternatives,
            key=lambda role: role["score"],
            reverse=True,
        )[:3]

    top_gaps = missing[:4]

    return {
        "current": current,
        "target": target,
        "profile": profile["summary"],
        "transferable": transferable,
        "missing": missing,
        "compatibility": compatibility,
        "difficulty": difficulty,
        "alternatives": alternative_results,
        "roadmap": build_roadmap(top_gaps, target["title"]),
        "evidence": build_evidence(target, transferable, missing, compatibility, profile["summary"]),
    }


def analyze_pair(current: dict, target: dict) -> dict:
    current_skills = set(current["skills"])
    weights = target.get("required") or {skill: DEFAULT_WEIGHT for skill in target["skills"]}
    skills = list(weights.keys())
    total = sum(weights[skill] for skill in skills)
    overlap = sum(weights[skill] for skill in skills if skill in current_skills)
    raw_overlap = overlap / total if total else 0
    bridge_score = transition_bridge_score(role_family(current), role_family(target))

    return {
        "compatibility": clamp(round(15 + raw_overlap * 65 + bridge_score * 0.35), 5, 96),
        "missingCount": len([skill for skill in skills if skill not in current_skills]),
    }


def role_family(role: dict) -> str:
    return role.get("family") or role.get("sector") or "Official Dataset"


def build_profile_context(current: dict, target: dict, profile_skills: list[str] | None) -> dict:
    clean_skills = dedupe_preserve_order(
        skill.strip()
        for skill in (profile_skills or [])
        if skill and skill.strip()
    )
    current_skill_set = set(current["skills"])
    target_lookup = {skill.casefold(): skill for skill in target["skills"]}
    matched_target_skills = dedupe_preserve_order(
        target_lookup[skill.casefold()]
        for skill in clean_skills
        if skill.casefold() in target_lookup
    )
    profile_only_matches = [
        skill for skill in matched_target_skills if skill not in current_skill_set
    ]
    augmented_skills = dedupe_preserve_order(
        [
            *current["skills"],
            *clean_skills,
            *matched_target_skills,
        ]
    )

    return {
        "augmented_skills": augmented_skills,
        "summary": {
            "input_skills": clean_skills,
            "matched_skills": matched_target_skills,
            "added_transferable_skills": profile_only_matches,
            "source_count": len(clean_skills),
            "used_in_scoring": bool(profile_only_matches),
        },
    }


def dedupe_preserve_order(values) -> list:
    seen = set()
    output = []
    for value in values:
        if value not in seen:
            seen.add(value)
            output.append(value)
    return output


def transition_bridge_score(current_family: str, target_family: str) -> int:
    if current_family == target_family:
        return 100

    pair = " -> ".join(sorted([current_family, target_family]))
    bridge_scores = {
        "Artificial Intelligence -> Software Engineering": 100,
        "Data -> Software Engineering": 88,
        "Artificial Intelligence -> Data": 86,
        "Business Operations -> Product": 82,
        "Creative -> Product": 72,
        "Creative -> Software Engineering": 55,
        "Creative -> Data": 48,
        "Engineering -> Software Engineering": 66,
        "Artificial Intelligence -> Engineering": 70,
        "Engineering -> Sustainability": 62,
        "Data -> Sustainability": 76,
        "Law -> Business Operations": 68,
        "Law -> Data": 48,
        "Law -> Product": 52,
        "Early Career -> Data": 62,
        "Early Career -> Product": 56,
        "Early Career -> Creative": 54,
        "Early Career -> Law": 50,
        "Early Career -> Engineering": 50,
        "Early Career -> Sustainability": 58,
    }
    return bridge_scores.get(pair, 35)


def urgency_for(weight: int) -> str:
    if weight >= 85:
        return "Critical"
    if weight >= 70:
        return "High"
    return "Medium"


def build_evidence(
    target: dict,
    transferable: list[str],
    missing: list[dict],
    compatibility: int,
    profile: dict | None = None,
) -> list[dict]:
    strongest_transfer = transferable[0] if transferable else "no direct skill"
    top_gap = missing[0] if missing else None
    second_gap = missing[1] if len(missing) > 1 else None
    profile_matches = (profile or {}).get("added_transferable_skills") or []

    return [
        {
            "label": "Dataset overlap",
            "detail": (
                f"{compatibility}% transition readiness combines exact skill overlap "
                f"with role-family adjacency for {target['title']}."
            ),
        },
        {
            "label": "Transfer signal",
            "detail": (
                (
                    f"{', '.join(profile_matches[:3])} moved from gap to transferable "
                    "because it was found in the user's resume, typed skills, or GitHub evidence."
                )
                if profile_matches
                else (
                    f"{strongest_transfer} is counted as a transferable skill because "
                    "it appears in both role profiles."
                )
            ),
        },
        {
            "label": "Priority gap",
            "detail": (
                f"{top_gap['name']} is recommended first because it appears in "
                f"{top_gap['demand']}% of target-role evidence."
                if top_gap
                else "No major missing target-role skills were found in the curated role profile."
            ),
        },
        {
            "label": "Roadmap logic",
            "detail": (
                f"{second_gap['name']} is sequenced after the top gap to build toward "
                f"a realistic {target['title']} portfolio."
                if second_gap
                else "The roadmap focuses on validating existing strengths through a portfolio project."
            ),
        },
    ]


def build_roadmap(gaps: list[dict], target_title: str) -> list[dict]:
    first = gaps[0]["name"] if len(gaps) > 0 else "target-role fundamentals"
    second = gaps[1]["name"] if len(gaps) > 1 else "portfolio evidence"
    third = gaps[2]["name"] if len(gaps) > 2 else "interview readiness"

    return [
        {
            "window": "30 days",
            "theme": "Foundation",
            "tasks": [
                f"Learn {first} with a focused notebook or mini-project.",
                "Map current skills to target-role requirements and collect proof points.",
                "Publish one short evidence write-up explaining the transition logic.",
            ],
        },
        {
            "window": "60 days",
            "theme": "Portfolio",
            "tasks": [
                f"Build a {target_title} portfolio or case project using {second}.",
                "Add tests, documentation, and a clear problem statement.",
                "Ask two practitioners to review the project for role relevance.",
            ],
        },
        {
            "window": "90 days",
            "theme": "Market test",
            "tasks": [
                f"Add {third} to the project and prepare a role-specific case study.",
                "Apply to transition-friendly roles and track skill keywords from postings.",
                "Refresh the roadmap using interview feedback and missing-skill evidence.",
            ],
        },
    ]


def clamp(value: int, minimum: int, maximum: int) -> int:
    return min(maximum, max(minimum, value))
