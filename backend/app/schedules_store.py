"""Persistence for learning schedules, sessions, reflections, and share pages.

Mirrors the conventions in ``auth.py`` (``db_connection`` context manager,
``utc_now`` timestamps, ``secrets.token_hex`` ids, row -> dict converters).
Schema for the underlying tables lives in ``auth.initialise_schema``.
"""

from __future__ import annotations

import json
import secrets
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .auth import db_connection, utc_now

SESSION_STATUS_PLANNED = "planned"
SESSION_STATUS_COMPLETED = "completed"


def _new_id() -> str:
    return secrets.token_hex(12)


def _local_date(start_utc: str, timezone: str) -> str:
    """Best-effort local calendar date for a UTC ISO timestamp."""
    try:
        moment = datetime.fromisoformat(start_utc)
        return moment.astimezone(ZoneInfo(timezone)).date().isoformat()
    except (ValueError, ZoneInfoNotFoundError, KeyError):
        return start_utc[:10]


# --------------------------------------------------------------------------- #
# Schedules + sessions
# --------------------------------------------------------------------------- #
def create_schedule(
    *,
    user_id: str,
    title: str,
    target_role_id: str | None,
    horizon_days: int,
    timezone: str,
    preferences: dict,
    availability: list[dict],
    sessions: list[dict],
) -> dict:
    schedule_id = _new_id()
    created_at = utc_now()
    availability_payload = {"timezone": timezone, "slots": availability}

    with db_connection() as connection:
        connection.execute(
            """
            INSERT INTO learning_schedules
                (id, user_id, title, target_role_id, horizon_days, preferences_json, availability_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                schedule_id,
                user_id,
                title.strip() or "Learning schedule",
                target_role_id,
                int(horizon_days),
                json.dumps(preferences),
                json.dumps(availability_payload),
                created_at,
            ),
        )
        for session in sessions:
            connection.execute(
                """
                INSERT INTO schedule_sessions
                    (id, schedule_id, user_id, resource_title, resource_url, resource_type,
                     skill, goal, week_index, start_utc, end_utc, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _new_id(),
                    schedule_id,
                    user_id,
                    session.get("resource_title", "Untitled resource"),
                    session.get("resource_url"),
                    session.get("resource_type", "course"),
                    session.get("skill", ""),
                    session.get("goal", ""),
                    int(session.get("week_index", 0)),
                    session["start_utc"],
                    session["end_utc"],
                    SESSION_STATUS_PLANNED,
                    created_at,
                ),
            )

    return get_schedule(user_id, schedule_id)


def list_schedules(user_id: str) -> list[dict]:
    with db_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM learning_schedules WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
    return [_schedule_summary(row) for row in rows]


def get_schedule(user_id: str, schedule_id: str) -> dict | None:
    with db_connection() as connection:
        schedule_row = connection.execute(
            "SELECT * FROM learning_schedules WHERE id = ? AND user_id = ?",
            (schedule_id, user_id),
        ).fetchone()
        if not schedule_row:
            return None
        session_rows = connection.execute(
            "SELECT * FROM schedule_sessions WHERE schedule_id = ? ORDER BY start_utc ASC",
            (schedule_id,),
        ).fetchall()

    availability = json.loads(schedule_row["availability_json"])
    timezone = availability.get("timezone", "UTC") if isinstance(availability, dict) else "UTC"
    summary = _schedule_summary(schedule_row)
    summary["availability"] = availability
    summary["sessions"] = [_session_to_dict(row, timezone) for row in session_rows]
    return summary


def _schedule_summary(row) -> dict:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "title": row["title"],
        "target_role_id": row["target_role_id"],
        "horizon_days": row["horizon_days"],
        "preferences": json.loads(row["preferences_json"]),
        "created_at": row["created_at"],
    }


def _session_to_dict(row, timezone: str) -> dict:
    return {
        "id": row["id"],
        "uid": row["id"],
        "schedule_id": row["schedule_id"],
        "resource_title": row["resource_title"],
        "resource_url": row["resource_url"],
        "resource_type": row["resource_type"],
        "skill": row["skill"] or "",
        "goal": row["goal"] or "",
        "week_index": row["week_index"],
        "date": _local_date(row["start_utc"], timezone),
        "start_utc": row["start_utc"],
        "end_utc": row["end_utc"],
        "status": row["status"],
    }


# --------------------------------------------------------------------------- #
# Sessions: completion + reflections + progress
# --------------------------------------------------------------------------- #
def get_session(user_id: str, session_id: str) -> dict | None:
    with db_connection() as connection:
        row = connection.execute(
            "SELECT * FROM schedule_sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        ).fetchone()
    return _session_to_dict(row, "UTC") if row else None


def complete_session(user_id: str, session_id: str, content: str) -> dict | None:
    """Record a reflection and mark the session completed. Returns the updated
    session, or None if the session does not exist / is not owned by the user."""
    completed_at = utc_now()
    with db_connection() as connection:
        row = connection.execute(
            "SELECT * FROM schedule_sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        ).fetchone()
        if not row:
            return None
        connection.execute(
            "INSERT INTO learning_reflections (id, session_id, user_id, content, created_at) VALUES (?, ?, ?, ?, ?)",
            (_new_id(), session_id, user_id, content, completed_at),
        )
        connection.execute(
            "UPDATE schedule_sessions SET status = ? WHERE id = ?",
            (SESSION_STATUS_COMPLETED, session_id),
        )
        updated = connection.execute(
            "SELECT * FROM schedule_sessions WHERE id = ?", (session_id,)
        ).fetchone()

    result = _session_to_dict(updated, "UTC")
    result["reflection"] = content
    return result


def schedule_progress(user_id: str, schedule_id: str) -> dict | None:
    with db_connection() as connection:
        owns = connection.execute(
            "SELECT 1 FROM learning_schedules WHERE id = ? AND user_id = ?",
            (schedule_id, user_id),
        ).fetchone()
        if not owns:
            return None
        rows = connection.execute(
            "SELECT week_index, status FROM schedule_sessions WHERE schedule_id = ?",
            (schedule_id,),
        ).fetchall()

    total = len(rows)
    completed = sum(1 for row in rows if row["status"] == SESSION_STATUS_COMPLETED)
    by_week: dict[int, dict] = {}
    for row in rows:
        bucket = by_week.setdefault(row["week_index"], {"total": 0, "completed": 0})
        bucket["total"] += 1
        if row["status"] == SESSION_STATUS_COMPLETED:
            bucket["completed"] += 1

    return {
        "schedule_id": schedule_id,
        "total": total,
        "completed": completed,
        "percent": round(100 * completed / total) if total else 0,
        "by_week": [
            {"week_index": week, **counts} for week, counts in sorted(by_week.items())
        ],
    }


def list_completed_reflections(user_id: str, schedule_id: str | None = None) -> list[dict]:
    """Completed sessions joined with their reflection text — raw material for posts."""
    query = """
        SELECT s.resource_title, s.resource_type, s.skill, r.content, r.created_at
        FROM learning_reflections r
        JOIN schedule_sessions s ON s.id = r.session_id
        WHERE r.user_id = ?
    """
    params: list = [user_id]
    if schedule_id:
        query += " AND s.schedule_id = ?"
        params.append(schedule_id)
    query += " ORDER BY r.created_at DESC"

    with db_connection() as connection:
        rows = connection.execute(query, tuple(params)).fetchall()

    return [
        {
            "resource_title": row["resource_title"],
            "resource_type": row["resource_type"],
            "skill": row["skill"] or "",
            "reflection": row["content"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


# --------------------------------------------------------------------------- #
# Share pages (public progress pages for LinkedIn unfurl)
# --------------------------------------------------------------------------- #
def create_share_page(user_id: str, summary: dict) -> dict:
    token = secrets.token_urlsafe(12)
    created_at = utc_now()
    with db_connection() as connection:
        connection.execute(
            "INSERT INTO share_pages (token, user_id, summary_json, created_at) VALUES (?, ?, ?, ?)",
            (token, user_id, json.dumps(summary), created_at),
        )
    return {"token": token, "summary": summary, "created_at": created_at}


def get_share_page(token: str) -> dict | None:
    with db_connection() as connection:
        row = connection.execute(
            "SELECT * FROM share_pages WHERE token = ?", (token,)
        ).fetchone()
    if not row:
        return None
    return {
        "token": row["token"],
        "user_id": row["user_id"],
        "summary": json.loads(row["summary_json"]),
        "created_at": row["created_at"],
    }
