from __future__ import annotations

import os
from urllib.parse import urlencode

import httpx

from .config import load_env_file

load_env_file()

EXA_SEARCH_URL = "https://api.exa.ai/search"
APIFY_API_BASE = "https://api.apify.com/v2"

ACTOR_LINKEDIN_JOBS = "hKByXkMQaC5Qt9UMN"
ACTOR_INDEED = "MXLpngmVpE8WTESQr"
ACTOR_FANTASTIC_JOBS = "s3dtSTZSZWFtAVLn5"
ACTOR_SEEK = "m7tdxsBaMKJhIu4fM"
DEFAULT_JOB_ACTOR_IDS = [ACTOR_INDEED, ACTOR_FANTASTIC_JOBS, ACTOR_LINKEDIN_JOBS]


def search_learning_resources(skill: str, target_role: str | None = None, num_results: int = 5) -> dict:
    base_query = f"{skill} learning resources"
    if target_role:
        base_query = f"{skill} learning resources for {target_role}"

    api_key = os.getenv("EXA_API_KEY", "").strip()
    if not api_key:
        return {
            "provider": "exa",
            "configured": False,
            "query": base_query,
            "categories": [],
            "results": [],
            "detail": "Set EXA_API_KEY to enable live Exa search.",
        }

    resource_types = [
        ("book", "Books", f"best books for {base_query}"),
        ("course", "Online courses", f"online courses for {base_query}"),
        ("video", "Videos", f"video tutorials for {base_query}"),
        ("project", "Projects to build", f"hands-on projects to practice {skill} for {target_role or 'career growth'}"),
    ]
    categories = []
    flattened_results = []
    results_per_category = max(2, min(num_results, 5))

    try:
        for resource_type, label, query in resource_types:
            payload = {
                "query": query,
                "numResults": results_per_category,
                "contents": {"highlights": True, "summary": True},
            }
            response = httpx.post(
                EXA_SEARCH_URL,
                headers={"x-api-key": api_key, "Content-Type": "application/json"},
                json=payload,
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
            results = [
                {
                    "type": resource_type,
                    "type_label": label,
                    "title": item.get("title") or item.get("url", "Untitled"),
                    "url": item.get("url"),
                    "highlights": item.get("highlights") or [],
                    "summary": item.get("summary"),
                }
                for item in data.get("results", [])
            ]
            categories.append(
                {
                    "type": resource_type,
                    "label": label,
                    "query": query,
                    "results": results,
                }
            )
            flattened_results.extend(results)
    except httpx.HTTPError as error:
        return {
            "provider": "exa",
            "configured": True,
            "query": base_query,
            "categories": categories,
            "results": flattened_results,
            "detail": f"Exa request failed: {error}",
        }

    return {
        "provider": "exa",
        "configured": True,
        "query": base_query,
        "categories": categories,
        "results": flattened_results,
        "detail": "Live Exa search completed across books, courses, videos, and projects.",
    }


def validate_market_demand(target_role: str, skills: list[str], country: str = "Singapore") -> dict:
    token = os.getenv("APIFY_API_TOKEN", "").strip()
    actor_ids = configured_actor_ids()
    clean_skills = [skill for skill in skills if skill]
    country_label = market_country_label(country)

    if not token or not actor_ids:
        return {
            "provider": "apify",
            "configured": False,
            "target_role": target_role,
            "skills": clean_skills,
            "country": country_label,
            "actors": actor_ids,
            "signals": [],
            "jobs": [],
            "detail": "Set APIFY_API_TOKEN and APIFY_JOB_ACTOR_IDS to enable live market validation.",
        }

    actor_results = []
    combined_items = []

    for actor_id in actor_ids:
        actor_input = actor_run_input(actor_id, target_role, clean_skills, country)

        try:
            items = run_actor_and_fetch_items(actor_id, actor_input, token)
            combined_items.extend(items)
            actor_results.append(
                {
                    "actor_id": actor_id,
                    "status": "ready",
                    "items": len(items),
                    "input": actor_input,
                }
            )
        except httpx.HTTPError as error:
            actor_results.append(
                {
                    "actor_id": actor_id,
                    "status": "error",
                    "items": 0,
                    "input": actor_input,
                    "detail": str(error),
                }
            )

    text_blob = " ".join(str(item).lower() for item in combined_items)
    signals = [
        {"skill": skill, "mentions": text_blob.count(skill.lower())}
        for skill in clean_skills
    ]
    jobs = normalize_job_postings(combined_items, clean_skills)

    return {
        "provider": "apify",
        "configured": True,
        "target_role": target_role,
        "skills": clean_skills,
        "country": country_label,
        "actors": actor_results,
        "signals": signals,
        "jobs": jobs,
        "detail": f"Analysed {len(combined_items)} Apify dataset items across {len(actor_ids)} actor(s) for {country_label.lower()} search.",
    }


def configured_actor_ids() -> list[str]:
    multi_actor_value = os.getenv("APIFY_JOB_ACTOR_IDS", "").strip()
    single_actor_value = os.getenv("APIFY_JOB_ACTOR_ID", "").strip()
    raw_value = multi_actor_value or single_actor_value

    if not raw_value:
        return DEFAULT_JOB_ACTOR_IDS

    return [
        actor_id.strip()
        for actor_id in raw_value.split(",")
        if actor_id.strip()
    ]


def actor_run_input(actor_id: str, target_role: str, skills: list[str], country: str) -> dict:
    skill_query = " ".join(skills[:4])
    search_query = " ".join(part for part in [target_role, skill_query] if part).strip()
    max_items = 25
    scoped_country = clean_country(country)
    search_location = scoped_country or "Worldwide"

    if actor_id == ACTOR_INDEED:
        payload = {
            "query": target_role,
            "maxRows": max_items,
        }
        if scoped_country:
            payload["country"] = country_code(scoped_country)
            payload["location"] = scoped_country
        return payload

    if actor_id == ACTOR_FANTASTIC_JOBS:
        payload = {
            "titleSearch": target_role,
            "locationSearch": search_location,
            "descriptionSearch": skill_query or target_role,
            "descriptionType": "text",
            "maxJobs": max_items,
        }
        return payload

    if actor_id == ACTOR_SEEK:
        payload = {
            "searchTerm": target_role,
            "location": search_location,
            "maxResults": max_items,
            "sortBy": "date",
        }
        return payload

    if actor_id == ACTOR_LINKEDIN_JOBS:
        query_payload = {"keywords": search_query or target_role, "location": search_location}
        query = urlencode(query_payload)
        return {
            "startUrls": [{"url": f"https://www.linkedin.com/jobs/search/?{query}"}],
            "maxItems": max_items,
        }

    payload = {
        "query": target_role,
        "location": search_location,
        "maxItems": max_items,
        "skills": skills,
    }
    return payload


def clean_country(country: str | None) -> str:
    return (country or "").strip()


def market_country_label(country: str | None) -> str:
    return clean_country(country) or "Global"


def country_code(country: str) -> str:
    codes = {
        "singapore": "sg",
        "malaysia": "my",
        "united states": "us",
        "usa": "us",
        "australia": "au",
        "new zealand": "nz",
        "united kingdom": "gb",
        "uk": "gb",
        "canada": "ca",
        "india": "in",
        "indonesia": "id",
        "philippines": "ph",
        "thailand": "th",
        "vietnam": "vn",
        "japan": "jp",
    }
    return codes.get(country.casefold().strip(), country.casefold().strip()[:2] or "sg")


def run_actor_and_fetch_items(actor_id: str, actor_input: dict, token: str) -> list[dict]:
    run_response = httpx.post(
        f"{APIFY_API_BASE}/acts/{actor_id}/runs",
        params={"token": token, "waitForFinish": 60},
        json=actor_input,
        timeout=70,
    )
    run_response.raise_for_status()
    run_data = run_response.json().get("data", {})
    dataset_id = run_data.get("defaultDatasetId")

    if not dataset_id:
        raise httpx.HTTPError("Apify run did not return a defaultDatasetId")

    items_response = httpx.get(
        f"{APIFY_API_BASE}/datasets/{dataset_id}/items",
        params={"token": token, "clean": "true", "format": "json"},
        timeout=20,
    )
    items_response.raise_for_status()
    return items_response.json()


def normalize_job_postings(items: list[dict], skills: list[str], limit: int = 8) -> list[dict]:
    jobs = []
    seen = set()

    for item in items:
        title = first_text(
            item,
            [
                "title",
                "jobTitle",
                "job_title",
                "position",
                "positionName",
                "name",
                "headline",
            ],
        )
        company = first_text(
            item,
            [
                "company",
                "companyName",
                "company_name",
                "employer",
                "employerName",
                "organization",
                "hiringOrganization.name",
                "hiringOrganization",
            ],
        )
        url = first_url(
            item,
            [
                "url",
                "jobUrl",
                "job_url",
                "jobLink",
                "job_link",
                "jobDetailUrl",
                "jobDetailsUrl",
                "applyUrl",
                "apply_url",
                "applyLink",
                "applicationUrl",
                "externalApplyLink",
                "directApplyUrl",
                "link",
                "detailsUrl",
                "postingUrl",
                "posting_url",
                "shareLink",
                "sourceUrl",
            ],
        )
        description = first_text(
            item,
            [
                "description",
                "descriptionText",
                "jobDescription",
                "summary",
                "snippet",
                "text",
            ],
        )
        location = first_text(
            item,
            [
                "location",
                "jobLocation",
                "job_location",
                "companyLocation",
                "company_location",
                "formattedLocation",
                "formattedLocationFull",
                "jobLocationCity",
                "jobLocationState",
                "jobLocation.country",
                "jobLocation.address",
                "jobLocation.address.addressLocality",
                "jobLocation.address.addressRegion",
                "place",
                "workplace",
                "city",
                "region",
                "state",
                "country",
            ],
        )

        if not title and not company and not description:
            continue

        key = (title.casefold(), company.casefold(), (url or "").casefold())
        if key in seen:
            continue
        seen.add(key)

        text = " ".join(
            part
            for part in [
                title,
                company,
                description,
                " ".join(str(value) for value in item.values() if isinstance(value, (str, int, float))),
            ]
            if part
        ).lower()
        matched_skills = [
            skill for skill in skills if skill.casefold() in text
        ]
        listed_skills = extract_listed_skills(item)
        inferred_skills = infer_job_skills(text)
        required_skills = dedupe_preserve_order([*matched_skills, *listed_skills])[:8]
        if not required_skills:
            required_skills = inferred_skills[:8]

        jobs.append(
            {
                "title": title or "Untitled role",
                "company": company or "Company not listed",
                "location": location or "Location not listed",
                "url": url,
                "description": compact_description(description),
                "skills": required_skills,
            }
        )

        if len(jobs) >= limit:
            break

    return jobs


def first_text(item: dict, paths: list[str]) -> str:
    for path in paths:
        value = nested_value(item, path)
        if isinstance(value, str) and value.strip():
            return clean_text(value)
        if isinstance(value, dict):
            name = (
                value.get("name")
                or value.get("title")
                or value.get("label")
                or value.get("text")
                or value.get("value")
                or value.get("address")
                or value.get("fullAddress")
                or value.get("displayName")
            )
            if isinstance(name, str) and name.strip():
                return clean_text(name)
    return ""


def first_url(item: dict, paths: list[str]) -> str:
    for path in paths:
        value = nested_value(item, path)
        candidate = url_from_value(value)
        if candidate:
            return candidate
    return find_url_in_value(item)


def url_from_value(value) -> str:
    if isinstance(value, str) and value.strip().lower().startswith(("http://", "https://")):
        candidate = clean_text(value)
        return "" if looks_like_asset_url(candidate) else candidate

    if isinstance(value, dict):
        for key in ["url", "href", "link", "value"]:
            candidate = url_from_value(value.get(key))
            if candidate:
                return candidate

    return ""


def find_url_in_value(value) -> str:
    if isinstance(value, dict):
        hinted_items = [
            (key, nested_value)
            for key, nested_value in value.items()
            if any(hint in key.casefold() for hint in ["url", "link", "href", "apply", "posting", "detail", "job"])
        ]
        other_items = [
            (key, nested_value)
            for key, nested_value in value.items()
            if (key, nested_value) not in hinted_items
        ]

        for _, nested in [*hinted_items, *other_items]:
            candidate = url_from_value(nested) or find_url_in_value(nested)
            if candidate:
                return candidate

    if isinstance(value, list):
        for item in value:
            candidate = url_from_value(item) or find_url_in_value(item)
            if candidate:
                return candidate

    return ""


def looks_like_asset_url(value: str) -> bool:
    lower = value.casefold().split("?", 1)[0]
    return lower.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".ico"))


def nested_value(item: dict, path: str):
    value = item
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def extract_listed_skills(item: dict) -> list[str]:
    values = []
    for key in ["skills", "requiredSkills", "requirements", "keywords", "tags"]:
        value = item.get(key)
        if isinstance(value, list):
            values.extend(normalize_skill_entry(entry) for entry in value)
        elif isinstance(value, str):
            values.extend(part.strip() for part in value.replace(";", ",").split(","))
    return [clean_text(value) for value in values if clean_text(value)]


def normalize_skill_entry(entry) -> str:
    if isinstance(entry, str):
        return entry

    if isinstance(entry, dict):
        for key in ["label", "name", "skill", "title", "text", "value"]:
            value = entry.get(key)
            if isinstance(value, str) and value.strip():
                return value
            if isinstance(value, dict):
                nested = normalize_skill_entry(value)
                if nested:
                    return nested

    return ""


def compact_description(value: str, max_length: int = 220) -> str:
    cleaned = clean_text(value)
    if not cleaned:
        return "No short description available from the job source."
    if len(cleaned) <= max_length:
        return cleaned
    return f"{cleaned[: max_length - 3].rstrip()}..."


def clean_text(value: str) -> str:
    return " ".join(str(value).replace("*", "").replace("\n", " ").replace("\r", " ").split())


def dedupe_preserve_order(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        key = value.casefold()
        if key and key not in seen:
            seen.add(key)
            result.append(value)
    return result


def infer_job_skills(text: str) -> list[str]:
    skill_map = [
        ("Python", ["python"]),
        ("SQL", ["sql", "database"]),
        ("JavaScript", ["javascript", "react", "node.js", "nodejs"]),
        ("TypeScript", ["typescript"]),
        ("Machine Learning", ["machine learning", " ml ", "model training"]),
        ("Large Language Models", ["large language", "llm", "generative ai", "genai"]),
        ("MLOps", ["mlops", "deployment", "deploying", "production ai"]),
        ("Data Analysis", ["data analysis", "analytics", "dashboard"]),
        ("Cloud", ["aws", "azure", "gcp", "cloud"]),
        ("Stakeholder Management", ["stakeholder", "client", "b2b", "sales"]),
        ("Project Management", ["project management", "tech pm", "product manager"]),
    ]
    padded = f" {text.casefold()} "
    return [
        skill
        for skill, needles in skill_map
        if any(needle in padded for needle in needles)
    ]
