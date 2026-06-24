"""Shared FastAPI auth dependencies, reused by the main app and routers."""

from __future__ import annotations

from fastapi import Header, HTTPException

from .auth import user_from_token


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
