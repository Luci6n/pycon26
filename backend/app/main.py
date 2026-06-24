from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .auth import (
    create_user,
    list_all_saved_roadmaps,
    list_all_users,
    list_saved_roadmaps,
    login_user,
    save_roadmap,
    user_from_token,
)
from .data import DATA_SOURCE, ROLES
from .dataset_loader import dataset_summary, get_official_role, official_role_profiles, search_official_roles
from .enrichment import search_learning_resources, validate_market_demand
from .evidence import analyze_evidence
from .resume_parser import extract_resume_text
from .scoring import UnknownRoleError, analyze_profiles, analyze_transition, get_role

app = FastAPI(title="PathForge AI API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://localhost:5173",
        "http://localhost:5174",
    ],
    allow_origin_regex=r"http://(127\.0\.0\.1|localhost):51[0-9]{2}",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    current_role_id: str = Field(..., min_length=1)
    target_role_id: str = Field(..., min_length=1)
    profile_skills: list[str] = Field(default_factory=list)


class EvidenceRequest(BaseModel):
    target_role_id: str = Field(..., min_length=1)
    current_role_id: str | None = None
    resume_name: str | None = None
    resume_text: str | None = None
    manual_skills: list[str] = Field(default_factory=list)
    github_url: str | None = None
    portfolio_links: list[str] = Field(default_factory=list)
    market_scan_enabled: bool = True
    fetch_repository: bool = False


class OfficialAnalyzeRequest(BaseModel):
    current_role: str = Field(..., min_length=1)
    target_role: str = Field(..., min_length=1)
    profile_skills: list[str] = Field(default_factory=list)


class ResourceSearchRequest(BaseModel):
    skill: str = Field(..., min_length=1)
    target_role: str | None = None
    num_results: int = 5


class MarketValidationRequest(BaseModel):
    target_role: str = Field(..., min_length=1)
    skills: list[str] = Field(default_factory=list)
    country: str = "Singapore"


class ResumeExtractRequest(BaseModel):
    filename: str = Field(..., min_length=1)
    content_base64: str = Field(..., min_length=1)


class AuthRequest(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=8)
    name: str | None = None


class SaveRoadmapRequest(BaseModel):
    title: str = "Saved Roadmap"
    current_role_id: str | None = None
    target_role_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


def current_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Login required for this action.")

    token = authorization.split(" ", 1)[1].strip()
    user = user_from_token(token)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired session.")

    return user


def current_admin(authorization: str | None = Header(default=None)) -> dict:
    user = current_user(authorization)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")
    return user


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "pathforge-api"}


@app.get("/api/roles")
def get_roles() -> dict:
    return {"data_source": DATA_SOURCE, "roles": ROLES}


@app.post("/api/auth/register")
def register(payload: AuthRequest) -> dict:
    try:
        return create_user(email=payload.email, password=payload.password, name=payload.name)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/api/auth/login")
def login(payload: AuthRequest) -> dict:
    session = login_user(email=payload.email, password=payload.password)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    return session


@app.get("/api/auth/me")
def me(authorization: str | None = Header(default=None)) -> dict:
    return {"user": current_user(authorization)}


@app.post("/api/roadmaps")
def post_roadmap(payload: SaveRoadmapRequest, authorization: str | None = Header(default=None)) -> dict:
    user = current_user(authorization)
    return {
        "roadmap": save_roadmap(
            user_id=user["id"],
            title=payload.title,
            current_role_id=payload.current_role_id,
            target_role_id=payload.target_role_id,
            payload=payload.payload,
        )
    }


@app.get("/api/roadmaps")
def get_roadmaps(authorization: str | None = Header(default=None)) -> dict:
    user = current_user(authorization)
    return {"roadmaps": list_saved_roadmaps(user["id"])}


@app.get("/api/admin/users")
def admin_users(authorization: str | None = Header(default=None)) -> dict:
    current_admin(authorization)
    return {"users": list_all_users()}


@app.get("/api/admin/roadmaps")
def admin_roadmaps(authorization: str | None = Header(default=None)) -> dict:
    current_admin(authorization)
    return {"roadmaps": list_all_saved_roadmaps()}


@app.get("/api/datasets/summary")
def get_dataset_summary() -> dict:
    return dataset_summary()


@app.get("/api/datasets/roles")
def get_dataset_roles(query: str = "", limit: int = 200) -> dict:
    return {
        "source": {
            "name": DATA_SOURCE["name"],
            "normalisation": "framework + TSC mapping + unique skill vocabulary",
        },
        "roles": search_official_roles(query=query, limit=limit),
    }


@app.post("/api/datasets/analyze")
def post_dataset_analyze(payload: OfficialAnalyzeRequest) -> dict:
    current = get_official_role(payload.current_role)
    target = get_official_role(payload.target_role)

    if not current:
        raise HTTPException(status_code=404, detail=f"Unknown official role: {payload.current_role}")
    if not target:
        raise HTTPException(status_code=404, detail=f"Unknown official role: {payload.target_role}")

    alternatives = [
        profile
        for profile in official_role_profiles().values()
        if profile["id"] not in {current["id"], target["id"]}
    ]

    result = analyze_profiles(
        current,
        target,
        alternatives=alternatives,
        profile_skills=payload.profile_skills,
    )
    result["source"] = {
        "name": DATA_SOURCE["name"],
        "normalisation": "framework + TSC mapping + unique skill vocabulary",
    }
    return result


@app.post("/api/analyze")
def post_analyze(payload: AnalyzeRequest) -> dict:
    try:
        current = get_role(payload.current_role_id)
        target = get_role(payload.target_role_id)
        alternatives = [
            role
            for role in ROLES
            if role["id"] not in {current["id"], target["id"]} and role.get("required")
        ]
        return analyze_profiles(current, target, alternatives=alternatives, profile_skills=payload.profile_skills)
    except UnknownRoleError as error:
        raise HTTPException(status_code=404, detail=f"Unknown role: {error}") from error


@app.post("/api/enrich/resources")
def post_resource_search(payload: ResourceSearchRequest) -> dict:
    return search_learning_resources(
        skill=payload.skill,
        target_role=payload.target_role,
        num_results=payload.num_results,
    )


@app.post("/api/enrich/market")
def post_market_validation(payload: MarketValidationRequest) -> dict:
    return validate_market_demand(
        target_role=payload.target_role,
        skills=payload.skills,
        country=payload.country,
    )


@app.post("/api/resume/extract")
def post_resume_extract(payload: ResumeExtractRequest) -> dict:
    try:
        return extract_resume_text(
            filename=payload.filename,
            content_base64=payload.content_base64,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=400, detail=f"Resume extraction failed: {error}") from error


@app.post("/api/evidence")
def post_evidence(payload: EvidenceRequest) -> dict:
    try:
        return analyze_evidence(
            target_role_id=payload.target_role_id,
            resume_name=payload.resume_name,
            resume_text=payload.resume_text,
            manual_skills=payload.manual_skills,
            github_url=payload.github_url,
            portfolio_links=payload.portfolio_links,
            market_scan_enabled=payload.market_scan_enabled,
            fetch_repository=payload.fetch_repository,
        )
    except UnknownRoleError as error:
        raise HTTPException(status_code=404, detail=f"Unknown role: {error}") from error
