"""Routes for the 'Arrange my time' scheduler, ICS export, and proof-of-learning."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Header, HTTPException, Response
from pydantic import BaseModel, Field

from . import schedules_store as store
from .calendar_export import CalendarExportError, build_ics, ics_filename
from .deps import current_user
from .scheduler_service import build_schedule
from .scheduling import ScheduleError

router = APIRouter(prefix="/api", tags=["schedule"])

MIN_REFLECTION_CHARS = 20


# --------------------------------------------------------------------------- #
# Request models
# --------------------------------------------------------------------------- #
class AvailabilitySlot(BaseModel):
    weekday: int = Field(..., ge=0, le=6)
    start: str = Field(..., min_length=4, max_length=5)
    end: str = Field(..., min_length=4, max_length=5)


class GenerateScheduleRequest(BaseModel):
    target_role_id: str | None = None
    target_role: str | None = None
    horizon_days: int = Field(30, ge=1, le=120)
    timezone: str = "UTC"
    availability: list[AvailabilitySlot] = Field(default_factory=list)
    preferences: dict = Field(default_factory=dict)
    resources: object = Field(default_factory=list)
    skills: list[dict] = Field(default_factory=list)


class SaveScheduleRequest(BaseModel):
    title: str = "Learning schedule"
    target_role_id: str | None = None
    horizon_days: int = Field(30, ge=1, le=120)
    timezone: str = "UTC"
    preferences: dict = Field(default_factory=dict)
    availability: list[dict] = Field(default_factory=list)
    sessions: list[dict] = Field(default_factory=list)


class ExportRequest(BaseModel):
    title: str = "PathForge Learning Plan"
    sessions: list[dict] = Field(default_factory=list)


class CompleteSessionRequest(BaseModel):
    content: str = Field(..., min_length=1)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _today_in_zone(timezone: str) -> str:
    try:
        return datetime.now(ZoneInfo(timezone)).date().isoformat()
    except (ZoneInfoNotFoundError, KeyError) as error:
        raise HTTPException(status_code=400, detail=f"Unknown timezone: {timezone}") from error


def _ics_response(sessions: list[dict], title: str) -> Response:
    try:
        ics_text = build_ics(sessions, calendar_name=title)
    except CalendarExportError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return Response(
        content=ics_text,
        media_type="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="{ics_filename(title)}"'},
    )


# --------------------------------------------------------------------------- #
# Generate (no login required to preview)
# --------------------------------------------------------------------------- #
@router.post("/schedule/generate")
def post_generate(payload: GenerateScheduleRequest) -> dict:
    start_date = _today_in_zone(payload.timezone)
    try:
        return build_schedule(
            horizon_days=payload.horizon_days,
            start_date=start_date,
            timezone=payload.timezone,
            availability=[slot.model_dump() for slot in payload.availability],
            preferences=payload.preferences,
            resources=payload.resources,
            skills=payload.skills,
            target_role=payload.target_role,
        )
    except ScheduleError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/schedule/export.ics")
def post_export_preview(payload: ExportRequest) -> Response:
    return _ics_response(payload.sessions, payload.title)


# --------------------------------------------------------------------------- #
# Saved schedules (login required)
# --------------------------------------------------------------------------- #
@router.post("/schedules")
def post_schedule(payload: SaveScheduleRequest, authorization: str | None = Header(default=None)) -> dict:
    user = current_user(authorization)
    if not payload.sessions:
        raise HTTPException(status_code=400, detail="Cannot save a schedule with no sessions.")
    schedule = store.create_schedule(
        user_id=user["id"],
        title=payload.title,
        target_role_id=payload.target_role_id,
        horizon_days=payload.horizon_days,
        timezone=payload.timezone,
        preferences=payload.preferences,
        availability=payload.availability,
        sessions=payload.sessions,
    )
    return {"schedule": schedule}


@router.get("/schedules")
def get_schedules(authorization: str | None = Header(default=None)) -> dict:
    user = current_user(authorization)
    return {"schedules": store.list_schedules(user["id"])}


@router.get("/schedules/{schedule_id}")
def get_schedule_detail(schedule_id: str, authorization: str | None = Header(default=None)) -> dict:
    user = current_user(authorization)
    schedule = store.get_schedule(user["id"], schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found.")
    return {"schedule": schedule}


@router.get("/schedules/{schedule_id}/export.ics")
def get_schedule_ics(schedule_id: str, authorization: str | None = Header(default=None)) -> Response:
    user = current_user(authorization)
    schedule = store.get_schedule(user["id"], schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found.")
    return _ics_response(schedule["sessions"], schedule["title"])


@router.get("/schedules/{schedule_id}/progress")
def get_schedule_progress(schedule_id: str, authorization: str | None = Header(default=None)) -> dict:
    user = current_user(authorization)
    progress = store.schedule_progress(user["id"], schedule_id)
    if progress is None:
        raise HTTPException(status_code=404, detail="Schedule not found.")
    return progress


# --------------------------------------------------------------------------- #
# Proof-of-learning: a session only completes with a substantive reflection
# --------------------------------------------------------------------------- #
@router.post("/sessions/{session_id}/complete")
def post_complete_session(
    session_id: str,
    payload: CompleteSessionRequest,
    authorization: str | None = Header(default=None),
) -> dict:
    user = current_user(authorization)
    reflection = payload.content.strip()
    if len(reflection) < MIN_REFLECTION_CHARS:
        raise HTTPException(
            status_code=400,
            detail=f"Tell us what you learned in at least {MIN_REFLECTION_CHARS} characters to mark this done.",
        )
    session = store.complete_session(user["id"], session_id, reflection)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {"session": session}
