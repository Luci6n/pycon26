"""LinkedIn sharing helpers.

Phase 1 (wired into the product): build a post caption from the user's verified
learnings, a public progress page with OpenGraph tags, and a no-OAuth
share-offsite URL where the user reviews and posts in LinkedIn's own composer.

Phase 2 (scaffold only, not wired into the demo): 3-legged OAuth + ``/v2/ugcPosts``
auto-publish. Requires a verified LinkedIn Company Page and the env vars below.
There is intentionally no 'draft into LinkedIn's composer' path — the LinkedIn
API does not support it; review happens in-app before share.
"""

from __future__ import annotations

import html
import os
from urllib.parse import quote, urlencode

from .config import load_env_file
from .llm import complete_text, llm_available

load_env_file()

SHARE_OFFSITE_BASE = "https://www.linkedin.com/sharing/share-offsite/"
LINKEDIN_AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
LINKEDIN_SCOPES = "openid profile w_member_social"
MAX_CAPTION_CHARS = 1300


def public_base_url() -> str:
    configured_url = os.getenv("APP_PUBLIC_BASE_URL", "").strip()
    if configured_url:
        return configured_url.rstrip("/")

    vercel_url = os.getenv("VERCEL_PROJECT_PRODUCTION_URL") or os.getenv("VERCEL_URL")
    if vercel_url:
        if vercel_url.startswith(("http://", "https://")):
            return vercel_url.rstrip("/")
        return f"https://{vercel_url}".rstrip("/")

    return "http://127.0.0.1:8010"


def share_page_url(token: str) -> str:
    return f"{public_base_url()}/share/{token}"


def share_offsite_url(page_url: str) -> str:
    return f"{SHARE_OFFSITE_BASE}?url={quote(page_url, safe='')}"


# --------------------------------------------------------------------------- #
# Caption generation
# --------------------------------------------------------------------------- #
def build_caption(reflections: list[dict], target_role: str | None = None) -> dict:
    """Return ``{caption, source_count, provider}``. Uses the LLM when configured,
    otherwise a deterministic template built from the user's reflections."""
    if not reflections:
        return {
            "caption": _empty_caption(target_role),
            "source_count": 0,
            "provider": None,
        }

    if llm_available():
        caption = _llm_caption(reflections, target_role)
        if caption:
            return {"caption": caption[:MAX_CAPTION_CHARS], "source_count": len(reflections), "provider": "llm"}

    return {
        "caption": _template_caption(reflections, target_role)[:MAX_CAPTION_CHARS],
        "source_count": len(reflections),
        "provider": "template",
    }


def _llm_caption(reflections: list[dict], target_role: str | None) -> str | None:
    lines = [
        f"- {item['resource_title']} ({item['resource_type']}): {item['reflection']}"
        for item in reflections[:12]
    ]
    prompt = (
        "Write a first-person LinkedIn post about my recent self-directed learning"
        + (f" as I work toward becoming a {target_role}" if target_role else "")
        + ". Keep it authentic and professional, under 1200 characters, with 2-4 relevant hashtags "
        + "at the end. Base it ONLY on these completed resources and what I learned:\n"
        + "\n".join(lines)
    )
    return complete_text(prompt, system="You are a concise professional ghostwriter.", max_tokens=600)


def _template_caption(reflections: list[dict], target_role: str | None) -> str:
    headline = (
        f"🚀 Another step toward {target_role}!" if target_role else "🚀 Learning-in-public update!"
    )
    bullets = "\n".join(
        f"• {item['resource_title']} — {_first_sentence(item['reflection'])}"
        for item in reflections[:5]
    )
    skills = sorted({item["skill"] for item in reflections if item.get("skill")})
    hashtags = " ".join(f"#{_hashtag(skill)}" for skill in skills[:3]) or "#LearningInPublic #Upskilling"
    return (
        f"{headline}\n\nRecently I completed and reflected on:\n{bullets}\n\n"
        f"Proof-of-learning, one session at a time.\n\n{hashtags}"
    )


def _empty_caption(target_role: str | None) -> str:
    goal = f" toward {target_role}" if target_role else ""
    return (
        f"Complete a learning session and write what you learned{goal} — "
        "your reflections become the post."
    )


def _first_sentence(text: str) -> str:
    cleaned = " ".join(text.split())
    for sep in (". ", "! ", "? "):
        if sep in cleaned:
            return cleaned.split(sep, 1)[0].strip()
    return cleaned[:120]


def _hashtag(skill: str) -> str:
    return "".join(part.capitalize() for part in skill.replace("/", " ").split() if part.isalnum()) or "Skill"


# --------------------------------------------------------------------------- #
# Public OpenGraph share page (so LinkedIn unfurls a preview card)
# --------------------------------------------------------------------------- #
def render_share_html(summary: dict, page_url: str) -> str:
    title = html.escape(str(summary.get("title") or "My learning progress on PathForge AI"))
    description = html.escape(str(summary.get("description") or _summary_description(summary)))
    image = summary.get("image_url")
    image_tag = f'<meta property="og:image" content="{html.escape(str(image))}" />' if image else ""
    bullets = "".join(f"<li>{html.escape(str(item))}</li>" for item in summary.get("highlights", [])[:6])

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <meta property="og:type" content="article" />
  <meta property="og:title" content="{title}" />
  <meta property="og:description" content="{description}" />
  <meta property="og:url" content="{html.escape(page_url)}" />
  {image_tag}
  <meta name="twitter:card" content="summary_large_image" />
  <style>body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:640px;margin:3rem auto;padding:0 1rem;color:#2b2b2b;background:#f4eee5}}h1{{color:#b86149}}li{{margin:.35rem 0}}</style>
</head>
<body>
  <h1>{title}</h1>
  <p>{description}</p>
  <ul>{bullets}</ul>
  <p><small>Generated by PathForge AI</small></p>
</body>
</html>"""


def _summary_description(summary: dict) -> str:
    completed = summary.get("completed_count")
    role = summary.get("target_role")
    if completed and role:
        return f"I've completed {completed} verified learning sessions working toward {role}."
    if completed:
        return f"I've completed {completed} verified learning sessions on my upskilling plan."
    return "Tracking verified, reflection-backed learning progress with PathForge AI."


# --------------------------------------------------------------------------- #
# OAuth scaffold (Phase 2 — not wired into the demo path)
# --------------------------------------------------------------------------- #
def oauth_configured() -> bool:
    return bool(os.getenv("LINKEDIN_CLIENT_ID") and os.getenv("LINKEDIN_CLIENT_SECRET"))


def authorize_url(state: str) -> str | None:
    if not oauth_configured():
        return None
    params = {
        "response_type": "code",
        "client_id": os.getenv("LINKEDIN_CLIENT_ID", ""),
        "redirect_uri": os.getenv("LINKEDIN_REDIRECT_URI", ""),
        "scope": LINKEDIN_SCOPES,
        "state": state,
    }
    return f"{LINKEDIN_AUTH_URL}?{urlencode(params)}"
