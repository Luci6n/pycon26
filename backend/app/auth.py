from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from contextlib import contextmanager
from pathlib import Path


def database_path() -> Path:
    configured_path = os.getenv("PATHFORGE_AUTH_DB", "").strip()
    if configured_path:
        return Path(configured_path)
    return Path(__file__).resolve().parents[1] / "pathforge.sqlite3"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    initialise_schema(connection)
    return connection


@contextmanager
def db_connection():
    connection = connect()
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def initialise_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            name TEXT,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS saved_roadmaps (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            current_role_id TEXT,
            target_role_id TEXT,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS learning_schedules (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            target_role_id TEXT,
            horizon_days INTEGER NOT NULL,
            preferences_json TEXT NOT NULL,
            availability_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS schedule_sessions (
            id TEXT PRIMARY KEY,
            schedule_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            resource_title TEXT NOT NULL,
            resource_url TEXT,
            resource_type TEXT NOT NULL,
            skill TEXT,
            goal TEXT,
            week_index INTEGER NOT NULL DEFAULT 0,
            start_utc TEXT NOT NULL,
            end_utc TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'planned',
            created_at TEXT NOT NULL,
            FOREIGN KEY (schedule_id) REFERENCES learning_schedules(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS learning_reflections (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES schedule_sessions(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS share_pages (
            token TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            summary_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS linkedin_tokens (
            user_id TEXT PRIMARY KEY,
            access_token TEXT NOT NULL,
            member_urn TEXT,
            expires_at TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        """
    )
    connection.commit()


def public_user(row: sqlite3.Row | dict) -> dict:
    return {
        "id": row["id"],
        "email": row["email"],
        "name": row["name"],
        "role": row["role"],
        "created_at": row["created_at"],
    }


def normalise_email(email: str) -> str:
    return email.strip().lower()


def role_for_email(email: str) -> str:
    admin_emails = {
        item.strip().lower()
        for item in os.getenv("PATHFORGE_ADMIN_EMAILS", "admin@pathforge.local").split(",")
        if item.strip()
    }
    return "admin" if normalise_email(email) in admin_emails else "user"


def hash_password(password: str, salt: str) -> str:
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        120_000,
    )
    return digest.hex()


def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    return hmac.compare_digest(hash_password(password, salt), expected_hash)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_user(email: str, password: str, name: str | None = None) -> dict:
    clean_email = normalise_email(email)
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")

    salt = secrets.token_hex(16)
    user_id = secrets.token_hex(12)

    try:
        with db_connection() as connection:
            connection.execute(
                """
                INSERT INTO users (id, email, name, password_hash, salt, role, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    clean_email,
                    name.strip() if name else None,
                    hash_password(password, salt),
                    salt,
                    role_for_email(clean_email),
                    utc_now(),
                ),
            )
            row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    except sqlite3.IntegrityError as error:
        raise ValueError("Email is already registered.") from error

    return create_session(row)


def login_user(email: str, password: str) -> dict | None:
    with db_connection() as connection:
        row = connection.execute("SELECT * FROM users WHERE email = ?", (normalise_email(email),)).fetchone()

    if not row or not verify_password(password, row["salt"], row["password_hash"]):
        return None

    return create_session(row)


def create_session(user_row: sqlite3.Row) -> dict:
    token = secrets.token_urlsafe(32)
    with db_connection() as connection:
        connection.execute(
            "INSERT INTO sessions (token_hash, user_id, created_at) VALUES (?, ?, ?)",
            (token_hash(token), user_row["id"], utc_now()),
        )

    return {"token": token, "user": public_user(user_row)}


def user_from_token(token: str) -> dict | None:
    with db_connection() as connection:
        row = connection.execute(
            """
            SELECT users.*
            FROM sessions
            JOIN users ON users.id = sessions.user_id
            WHERE sessions.token_hash = ?
            """,
            (token_hash(token),),
        ).fetchone()

    return public_user(row) if row else None


def save_roadmap(user_id: str, title: str, current_role_id: str | None, target_role_id: str | None, payload: dict) -> dict:
    roadmap_id = secrets.token_hex(12)
    created_at = utc_now()

    with db_connection() as connection:
        connection.execute(
            """
            INSERT INTO saved_roadmaps (id, user_id, title, current_role_id, target_role_id, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                roadmap_id,
                user_id,
                title.strip() or "Saved Roadmap",
                current_role_id,
                target_role_id,
                json.dumps(payload),
                created_at,
            ),
        )

    return {
        "id": roadmap_id,
        "title": title.strip() or "Saved Roadmap",
        "current_role_id": current_role_id,
        "target_role_id": target_role_id,
        "payload": payload,
        "created_at": created_at,
    }


def list_saved_roadmaps(user_id: str) -> list[dict]:
    with db_connection() as connection:
        rows = connection.execute(
            """
            SELECT * FROM saved_roadmaps
            WHERE user_id = ?
            ORDER BY created_at DESC
            """,
            (user_id,),
        ).fetchall()

    return [roadmap_from_row(row) for row in rows]


def list_all_users() -> list[dict]:
    with db_connection() as connection:
        rows = connection.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    return [public_user(row) for row in rows]


def list_all_saved_roadmaps() -> list[dict]:
    with db_connection() as connection:
        rows = connection.execute("SELECT * FROM saved_roadmaps ORDER BY created_at DESC").fetchall()
    return [roadmap_from_row(row) for row in rows]


def roadmap_from_row(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "title": row["title"],
        "current_role_id": row["current_role_id"],
        "target_role_id": row["target_role_id"],
        "payload": json.loads(row["payload_json"]),
        "created_at": row["created_at"],
    }
