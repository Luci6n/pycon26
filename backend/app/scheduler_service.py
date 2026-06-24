"""Orchestrates schedule generation: deterministic engine + optional LLM refinement.

The deterministic engine (:mod:`scheduling`) always produces a valid, non-overlapping
plan. When an LLM provider is configured (:mod:`llm`), we additionally ask it to write
friendlier per-session goals and a short plan summary — but placement stays
deterministic, so an unconfigured or failing LLM degrades gracefully.
"""

from __future__ import annotations

import json

from .llm import complete_json, llm_available, llm_provider
from .scheduling import RESOURCE_TYPES, generate_schedule

_REFINE_SYSTEM = (
    "You are a learning coach. You receive study sessions and return JSON only. "
    "Do not change the schedule; only improve wording."
)


def flatten_resources(resources: object) -> list[dict]:
    """Accept either a flat list of resources or the Exa ``{categories: [...]}`` shape
    and return a normalized flat list of ``{type, title, url, skill}`` dicts."""
    items: list[dict] = []

    if isinstance(resources, dict):
        categories = resources.get("categories") or []
        for category in categories:
            for result in category.get("results", []):
                items.append(_normalize_resource(result, category.get("skill")))
        if not categories:
            for result in resources.get("results", []):
                items.append(_normalize_resource(result, None))
    elif isinstance(resources, list):
        for result in resources:
            if isinstance(result, dict):
                items.append(_normalize_resource(result, result.get("skill")))

    return [item for item in items if item["title"]]


def _normalize_resource(result: dict, fallback_skill: str | None) -> dict:
    resource_type = (result.get("type") or "course").lower()
    if resource_type not in RESOURCE_TYPES:
        resource_type = "course"
    return {
        "type": resource_type,
        "title": (result.get("title") or "").strip(),
        "url": result.get("url"),
        "skill": (result.get("skill") or fallback_skill or "").strip(),
    }


def build_schedule(
    *,
    horizon_days: int,
    start_date: str,
    timezone: str,
    availability: list[dict],
    preferences: dict,
    resources: object,
    skills: list[dict] | None = None,
    target_role: str | None = None,
) -> dict:
    """Build a schedule preview. Raises ``ScheduleError`` (ValueError) on bad input."""
    flat_resources = flatten_resources(resources)
    sessions = generate_schedule(
        horizon_days=horizon_days,
        start_date=start_date,
        timezone=timezone,
        availability=availability,
        preferences=preferences,
        resources=flat_resources,
        skills=skills,
    )

    refinement = _refine_with_llm(sessions, target_role, preferences) if (sessions and llm_available()) else None
    if refinement:
        sessions = _apply_goal_refinement(sessions, refinement.get("goals", {}))

    return {
        "sessions": sessions,
        "session_count": len(sessions),
        "resource_count": len(flat_resources),
        "llm_refined": bool(refinement),
        "provider": llm_provider(),
        "summary": (refinement or {}).get("summary") or _default_summary(sessions, horizon_days),
    }


def _refine_with_llm(sessions: list[dict], target_role: str | None, preferences: dict) -> dict | None:
    compact = [
        {"uid": s["uid"], "type": s["resource_type"], "skill": s["skill"], "title": s["resource_title"]}
        for s in sessions[:60]
    ]
    prompt = (
        "Improve these learning sessions for someone upskilling"
        + (f" toward {target_role}" if target_role else "")
        + ". Return a JSON object with two keys: \"summary\" (one motivating sentence about the plan) "
        + "and \"goals\" (an object mapping each session uid to a specific, encouraging one-line goal, "
        + "max 90 characters). Do not invent sessions or change titles.\n\nSessions JSON:\n"
        + json.dumps(compact)
    )
    result = complete_json(prompt, system=_REFINE_SYSTEM, max_tokens=1500)
    if not isinstance(result, dict):
        return None
    goals = result.get("goals")
    return {
        "summary": result.get("summary") if isinstance(result.get("summary"), str) else None,
        "goals": goals if isinstance(goals, dict) else {},
    }


def _apply_goal_refinement(sessions: list[dict], goals: dict) -> list[dict]:
    refined = []
    for session in sessions:
        new_goal = goals.get(session["uid"])
        if isinstance(new_goal, str) and new_goal.strip():
            refined.append({**session, "goal": new_goal.strip()[:140]})
        else:
            refined.append(session)
    return refined


def _default_summary(sessions: list[dict], horizon_days: int) -> str:
    if not sessions:
        return "No sessions could be scheduled. Add more free time or learning resources."
    return f"{len(sessions)} study sessions planned across the next {horizon_days} days."
