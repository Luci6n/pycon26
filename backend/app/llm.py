from __future__ import annotations

import json
import os

import httpx

from .config import load_env_file

load_env_file()

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"
ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

DEFAULT_OPENAI_MODEL = "gpt-5.5"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"

REQUEST_TIMEOUT = 30

PROVIDER_OPENAI = "openai"
PROVIDER_ANTHROPIC = "anthropic"

JSON_INSTRUCTION = "Respond with ONLY a single valid JSON object. Do not include any prose, explanation, or markdown fences."


def llm_provider() -> str | None:
    override = os.getenv("LLM_PROVIDER", "").strip().lower()
    if override == PROVIDER_OPENAI:
        return PROVIDER_OPENAI if _openai_key() else None
    if override == PROVIDER_ANTHROPIC:
        return PROVIDER_ANTHROPIC if _anthropic_key() else None

    if _openai_key():
        return PROVIDER_OPENAI
    if _anthropic_key():
        return PROVIDER_ANTHROPIC
    return None


def llm_available() -> bool:
    return llm_provider() is not None


def complete_text(
    prompt: str,
    *,
    system: str | None = None,
    max_tokens: int = 800,
    temperature: float = 0.4,
) -> str | None:
    provider = llm_provider()
    if provider == PROVIDER_OPENAI:
        return _openai_complete(prompt, system=system, max_tokens=max_tokens, temperature=temperature)
    if provider == PROVIDER_ANTHROPIC:
        return _anthropic_complete(prompt, system=system, max_tokens=max_tokens, temperature=temperature)
    return None


def complete_json(
    prompt: str,
    *,
    system: str | None = None,
    max_tokens: int = 1500,
) -> dict | None:
    provider = llm_provider()
    json_prompt = f"{prompt}\n\n{JSON_INSTRUCTION}"

    if provider == PROVIDER_OPENAI:
        json_system = _ensure_json_keyword(system)
        text = _openai_complete(
            json_prompt,
            system=json_system,
            max_tokens=max_tokens,
            temperature=0,
            json_mode=True,
        )
    elif provider == PROVIDER_ANTHROPIC:
        text = _anthropic_complete(json_prompt, system=system, max_tokens=max_tokens, temperature=0)
    else:
        return None

    return _parse_json_object(text)


def _openai_key() -> str:
    return os.getenv("OPENAI_API_KEY", "").strip()


def _anthropic_key() -> str:
    return os.getenv("ANTHROPIC_API_KEY", "").strip()


def _openai_model() -> str:
    return os.getenv("LLM_MODEL", DEFAULT_OPENAI_MODEL).strip() or DEFAULT_OPENAI_MODEL


def _anthropic_model() -> str:
    return os.getenv("LLM_MODEL", DEFAULT_ANTHROPIC_MODEL).strip() or DEFAULT_ANTHROPIC_MODEL


def _openai_complete(
    prompt: str,
    *,
    system: str | None,
    max_tokens: int,
    temperature: float,
    json_mode: bool = False,
) -> str | None:
    api_key = _openai_key()
    if not api_key:
        return None

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": _openai_model(),
        "messages": messages,
        "max_completion_tokens": max_tokens,
        "temperature": temperature,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    try:
        response = httpx.post(
            OPENAI_CHAT_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
        return None

    if not isinstance(content, str):
        return None
    return content


def _anthropic_complete(
    prompt: str,
    *,
    system: str | None,
    max_tokens: int,
    temperature: float,
) -> str | None:
    api_key = _anthropic_key()
    if not api_key:
        return None

    payload = {
        "model": _anthropic_model(),
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        payload["system"] = system

    try:
        response = httpx.post(
            ANTHROPIC_MESSAGES_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": ANTHROPIC_VERSION,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        content = data["content"][0]["text"]
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
        return None

    if not isinstance(content, str):
        return None
    return content


def _ensure_json_keyword(system: str | None) -> str:
    if system and "json" in system.lower():
        return system
    if system:
        return f"{system} Respond with JSON only."
    return "Respond with JSON only."


def _parse_json_object(text: str | None) -> dict | None:
    if not text:
        return None

    cleaned = _strip_code_fences(text.strip())
    try:
        parsed = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        return None

    if not isinstance(parsed, dict):
        return None
    return parsed


def _strip_code_fences(text: str) -> str:
    if not text.startswith("```"):
        return text

    without_open = text[3:]
    if without_open[:4].lower() == "json":
        without_open = without_open[4:]
    elif "\n" in without_open:
        # Drop an arbitrary language hint on the opening fence line.
        first_line, rest = without_open.split("\n", 1)
        if first_line.strip() and " " not in first_line.strip():
            without_open = rest

    closing = without_open.rfind("```")
    if closing != -1:
        without_open = without_open[:closing]

    return without_open.strip()
