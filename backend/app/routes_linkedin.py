"""Routes for LinkedIn sharing (no-OAuth share flow) + OAuth scaffold."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from . import schedules_store as store
from .deps import current_user
from .linkedin import (
    authorize_url,
    build_caption,
    oauth_configured,
    render_share_html,
    share_offsite_url,
    share_page_url,
)

router = APIRouter(tags=["linkedin"])


class DraftRequest(BaseModel):
    schedule_id: str | None = None
    target_role: str | None = None


class ShareCreateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    target_role: str | None = None
    highlights: list[str] = Field(default_factory=list)
    completed_count: int | None = None
    image_url: str | None = None


@router.post("/api/linkedin/draft")
def post_draft(payload: DraftRequest, authorization: str | None = Header(default=None)) -> dict:
    user = current_user(authorization)
    reflections = store.list_completed_reflections(user["id"], payload.schedule_id)
    return build_caption(reflections, payload.target_role)


@router.post("/api/share/create")
def post_share_create(payload: ShareCreateRequest, authorization: str | None = Header(default=None)) -> dict:
    user = current_user(authorization)
    summary = payload.model_dump(exclude_none=True)
    page = store.create_share_page(user["id"], summary)
    page_url = share_page_url(page["token"])
    return {
        "token": page["token"],
        "page_url": page_url,
        "share_url": share_offsite_url(page_url),
    }


@router.get("/share/{token}", response_class=HTMLResponse)
def get_share_page(token: str) -> HTMLResponse:
    page = store.get_share_page(token)
    if not page:
        raise HTTPException(status_code=404, detail="Share page not found.")
    page_url = share_page_url(token)
    return HTMLResponse(content=render_share_html(page["summary"], page_url))


# --------------------------------------------------------------------------- #
# OAuth scaffold (Phase 2) — returns 501 until LinkedIn app creds are configured
# --------------------------------------------------------------------------- #
@router.get("/api/integrations/linkedin/authorize")
def get_authorize() -> dict:
    if not oauth_configured():
        raise HTTPException(
            status_code=501,
            detail="LinkedIn OAuth is not configured. Set LINKEDIN_CLIENT_ID/SECRET/REDIRECT_URI to enable auto-publish.",
        )
    return {"authorize_url": authorize_url(state="pathforge")}
