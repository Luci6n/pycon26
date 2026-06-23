from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .dataset_loader import get_official_role
from .scoring import get_role
from .scoring import UnknownRoleError


def analyze_evidence(
    target_role_id: str,
    resume_name: str | None = None,
    resume_text: str | None = None,
    manual_skills: list[str] | None = None,
    github_url: str | None = None,
    portfolio_links: list[str] | None = None,
    market_scan_enabled: bool = True,
    fetch_repository: bool = False,
) -> dict:
    target = resolve_target_role(target_role_id)
    portfolio_links = portfolio_links or []
    manual_skills = manual_skills or []
    resume = analyze_resume(target, resume_name, resume_text)
    typed_skills = analyze_manual_skills(target, manual_skills)
    repository = analyze_repository(github_url, fetch_repository)
    portfolio = analyze_portfolio(portfolio_links)
    market = analyze_market_signal(target, market_scan_enabled)

    return {
        "resume": resume,
        "manual_skills": typed_skills,
        "repository": repository,
        "portfolio": portfolio,
        "market": market,
        "summary": [
            resume["label"],
            typed_skills["label"],
            repository["label"],
            portfolio["label"],
            market["label"],
        ],
    }


def resolve_target_role(target_role_id: str) -> dict:
    try:
        return get_role(target_role_id)
    except UnknownRoleError:
        official_role = get_official_role(target_role_id)
        if official_role:
            return official_role
        raise


def analyze_resume(target: dict, resume_name: str | None, resume_text: str | None) -> dict:
    raw_text = resume_text or ""
    text = raw_text.lower()
    text_character_count = len(raw_text.strip())
    excerpt = compact_resume_excerpt(raw_text)
    matched_skills = [
        skill for skill in target["skills"] if skill.lower() in text
    ][:6]

    if matched_skills:
        return {
            "status": "text parsed",
            "label": f"{len(matched_skills)} target skills found",
            "filename": resume_name,
            "text_character_count": text_character_count,
            "excerpt": excerpt,
            "matched_skills": matched_skills,
            "detail": f"Resume text mentions: {', '.join(matched_skills)}.",
        }

    if resume_name:
        return {
            "status": "attached",
            "label": "Resume attached",
            "filename": resume_name,
            "text_character_count": text_character_count,
            "excerpt": excerpt,
            "matched_skills": [],
            "detail": (
                "Resume text was captured, but no direct target-role skill matches were found."
                if text_character_count
                else "The file is attached. PDF and DOC parsing can run in the backend ingestion step."
            ),
        }

    return {
        "status": "missing",
        "label": "Resume pending",
        "filename": None,
        "text_character_count": 0,
        "excerpt": "",
        "matched_skills": [],
        "detail": "Attach a resume or paste text to compare against target-role skills.",
    }


def compact_resume_excerpt(value: str, max_length: int = 320) -> str:
    cleaned = " ".join(value.split())
    if len(cleaned) <= max_length:
        return cleaned
    return f"{cleaned[: max_length - 3].rstrip()}..."


def analyze_manual_skills(target: dict, manual_skills: list[str]) -> dict:
    clean_skills = [
        skill.strip()
        for skill in manual_skills
        if skill and skill.strip()
    ]
    target_lookup = {skill.casefold(): skill for skill in target["skills"]}
    matched = [
        target_lookup[skill.casefold()]
        for skill in clean_skills
        if skill.casefold() in target_lookup
    ]

    if matched:
        return {
            "status": "matched",
            "label": f"{len(matched)} typed skills match",
            "skills": clean_skills,
            "matched_skills": matched,
            "detail": f"Typed skills already aligned to target role: {', '.join(matched[:6])}.",
        }

    if clean_skills:
        return {
            "status": "captured",
            "label": f"{len(clean_skills)} typed skills captured",
            "skills": clean_skills,
            "matched_skills": [],
            "detail": "Typed skills are captured as profile evidence, but none directly match the target role vocabulary yet.",
        }

    return {
        "status": "missing",
        "label": "typed skills optional",
        "skills": [],
        "matched_skills": [],
        "detail": "Add a few skills if the resume does not cover your latest work.",
    }


def analyze_repository(github_url: str | None, fetch_repository: bool = False) -> dict:
    parsed = parse_github_target(github_url or "")

    if not github_url:
        return {
            "status": "missing",
            "label": "repository optional",
            "owner": None,
            "repo": None,
            "languages": [],
            "repositories": [],
            "public_repository_count": 0,
            "inferred_skills": [],
            "detail": "For non-code domains, portfolio links can be stronger than repository evidence.",
        }

    if not parsed:
        return {
            "status": "captured",
            "label": "repository link captured",
            "owner": None,
            "repo": None,
            "languages": [],
            "repositories": [],
            "public_repository_count": 0,
            "inferred_skills": [],
            "detail": "The URL was captured as supporting evidence. GitHub parsing needs a github.com owner/repo URL.",
        }

    owner, repo = parsed["owner"], parsed.get("repo")
    languages = []
    repositories = []
    public_repository_count = 0
    inferred_skills = []
    status = "captured"
    label = "repository evidence"
    detail = "Public GitHub target parsed. Run live evidence analysis to fetch repo signals."

    if fetch_repository and repo:
        fetched = fetch_github_languages(owner, repo)
        languages = fetched["languages"]
        inferred_skills = fetched["inferred_skills"]
        detail = fetched["detail"]
        status = fetched["status"]
    elif fetch_repository:
        fetched = fetch_github_profile(owner)
        languages = fetched["languages"]
        repositories = fetched["repositories"]
        public_repository_count = fetched["public_repository_count"]
        inferred_skills = fetched["inferred_skills"]
        detail = fetched["detail"]
        status = fetched["status"]
        label = "GitHub profile evidence"
    elif not repo:
        label = "GitHub profile captured"
        detail = "GitHub profile parsed. Run live evidence analysis to inspect public repositories."

    return {
        "status": status,
        "label": label,
        "owner": owner,
        "repo": repo,
        "languages": languages,
        "repositories": repositories,
        "public_repository_count": public_repository_count,
        "inferred_skills": inferred_skills,
        "detail": detail,
    }


def analyze_portfolio(portfolio_links: list[str]) -> dict:
    clean_links = [link.strip() for link in portfolio_links if link.strip()]
    signals = [classify_portfolio_link(link) for link in clean_links]
    signal_labels = [signal["label"] for signal in signals]

    if len(clean_links) >= 2:
        status = "strong evidence base"
        detail = f"Multiple proof points found: {', '.join(signal_labels[:4])}."
    elif len(clean_links) == 1:
        status = "needs one more proof point"
        detail = f"One proof point found: {signal_labels[0]}. Add one more link for a stronger review."
    else:
        status = "not assessed"
        detail = "Add portfolio, publication, case study, writing, CAD, or project links."

    return {
        "status": status,
        "label": f"{len(clean_links)} portfolio link{'s' if len(clean_links) != 1 else ''}",
        "links": clean_links,
        "signals": signals,
        "detail": detail,
    }


def analyze_market_signal(target: dict, market_scan_enabled: bool) -> dict:
    required = target.get("required") or {skill: 50 for skill in target["skills"]}
    skills = [
        skill for skill, _ in sorted(required.items(), key=lambda item: item[1], reverse=True)
    ][:3]

    if not market_scan_enabled:
        return {
            "status": "skipped",
            "label": "market scan skipped",
            "skills": [],
            "detail": "Core scoring still works from SkillsFuture data without live scraping.",
        }

    return {
        "status": "ready",
        "label": "market scan ready",
        "skills": skills,
        "detail": "Apify can validate these high-weight skills against current postings or course listings.",
    }


def parse_github_target(raw_url: str) -> dict | None:
    trimmed = raw_url.strip()
    if not trimmed:
        return None

    parsed = urlparse(trimmed if trimmed.startswith("http") else f"https://{trimmed}")
    if not parsed.netloc.lower().endswith("github.com"):
        return None

    parts = [part for part in parsed.path.split("/") if part]
    if not parts:
        return None

    if len(parts) == 1:
        return {"owner": parts[0], "repo": None}

    return {"owner": parts[0], "repo": parts[1].removesuffix(".git")}


def parse_github_repo(raw_url: str) -> dict | None:
    parsed = parse_github_target(raw_url)
    if not parsed or not parsed.get("repo"):
        return None
    return {"owner": parsed["owner"], "repo": parsed["repo"]}


def fetch_github_languages(owner: str, repo: str) -> dict:
    request = Request(
        f"https://api.github.com/repos/{owner}/{repo}/languages",
        headers=github_headers(),
    )

    try:
        with urlopen(request, timeout=4) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        return {
            "status": "error",
            "languages": [],
            "detail": f"GitHub returned HTTP {error.code}. Repo link is still captured.",
        }
    except URLError as error:
        return {
            "status": "error",
            "languages": [],
            "detail": f"GitHub fetch failed: {error.reason}. Repo link is still captured.",
        }

    languages = [
        language
        for language, _ in sorted(payload.items(), key=lambda item: item[1], reverse=True)
    ][:4]
    inferred_skills = infer_repository_skills(languages=languages, topics=[], repo_names=[repo])

    return {
        "status": "ready",
        "languages": languages,
        "inferred_skills": inferred_skills,
        "detail": f"GitHub language signal: {', '.join(languages) if languages else 'no languages reported'}.",
    }


def fetch_github_profile(owner: str) -> dict:
    try:
        payload = fetch_public_github_repositories(owner)
    except HTTPError as error:
        return {
            "status": "error",
            "languages": [],
            "repositories": [],
            "inferred_skills": [],
            "detail": f"GitHub returned HTTP {error.code}. Profile link is still captured.",
        }
    except URLError as error:
        return {
            "status": "error",
            "languages": [],
            "repositories": [],
            "inferred_skills": [],
            "detail": f"GitHub fetch failed: {error.reason}. Profile link is still captured.",
        }

    repositories = [
        {
            "name": item.get("name", "untitled"),
            "language": item.get("language"),
            "topics": item.get("topics", []),
            "url": item.get("html_url"),
            "fork": bool(item.get("fork")),
        }
        for item in payload
    ]
    visible_repositories = repositories[:8]
    languages = sorted({repo["language"] for repo in repositories if repo.get("language")})
    topics = sorted({topic for repo in repositories for topic in repo.get("topics", [])})
    repo_names = [repo["name"] for repo in repositories]
    inferred_skills = infer_repository_skills(languages=languages, topics=topics, repo_names=repo_names)
    private_note = " Private repos require a GitHub token." if not os.getenv("GITHUB_TOKEN", "").strip() else ""

    return {
        "status": "ready",
        "languages": languages,
        "repositories": visible_repositories,
        "public_repository_count": len(repositories),
        "inferred_skills": inferred_skills,
        "detail": (
            f"Scanned {len(repositories)} public repos exposed by GitHub. "
            f"Language signal: {', '.join(languages[:5]) if languages else 'no primary languages reported'}."
            f"{private_note}"
        ),
    }


def fetch_public_github_repositories(owner: str) -> list[dict]:
    repositories = []

    for page in range(1, 4):
        request = Request(
            f"https://api.github.com/users/{owner}/repos?per_page=100&page={page}&sort=updated&type=all",
            headers=github_headers(),
        )

        with urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))

        if not payload:
            break

        repositories.extend(payload)

        if len(payload) < 100:
            break

    return repositories


def github_headers() -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "pathforge-ai",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def infer_repository_skills(languages: list[str], topics: list[str], repo_names: list[str]) -> list[str]:
    text = " ".join([*languages, *topics, *repo_names]).lower()
    mappings = [
        ("Python", ["python", "jupyter notebook", "fastapi", "django", "flask"]),
        ("JavaScript", ["javascript", "react", "node", "vite", "nextjs", "vue"]),
        ("TypeScript", ["typescript", "tsx"]),
        ("Data Analysis", ["pandas", "numpy", "analytics", "data"]),
        ("Machine Learning", ["machine-learning", "machinelearning", "model", "scikit", "tensorflow", "pytorch"]),
        ("APIs", ["api", "fastapi", "rest", "graphql"]),
        ("Frontend Development", ["react", "css", "html", "frontend", "ui"]),
        ("Cloud Deployment", ["docker", "kubernetes", "aws", "gcp", "azure", "vercel"]),
    ]

    skills = [
        skill
        for skill, needles in mappings
        if any(needle in text for needle in needles)
    ]
    return skills[:6]


def classify_portfolio_link(link: str) -> dict:
    parsed = urlparse(link if link.startswith("http") else f"https://{link}")
    host = parsed.netloc.lower().removeprefix("www.")

    if "linkedin.com" in host:
        label = "LinkedIn profile"
        category = "professional_profile"
    elif "github.com" in host:
        label = "GitHub evidence"
        category = "code_or_project"
    elif "behance.net" in host or "dribbble.com" in host:
        label = "design portfolio"
        category = "creative_portfolio"
    elif "medium.com" in host or "substack.com" in host:
        label = "writing sample"
        category = "writing"
    elif "scholar.google" in host or "orcid.org" in host or "researchgate.net" in host:
        label = "research profile"
        category = "research"
    else:
        label = host or "portfolio link"
        category = "general_portfolio"

    return {"url": link, "host": host, "label": label, "category": category}
