import sqlite3
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional


def _db_path() -> Path:
    from config import settings
    p = Path(settings.db_path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_db_path()))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS thoughts (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       INTEGER NOT NULL,
                created_at    TEXT    NOT NULL,
                raw_input     TEXT    NOT NULL,
                source        TEXT    NOT NULL DEFAULT 'text',
                idea_type     TEXT,
                novelty_score REAL,
                clarity_score REAL,
                publishable   INTEGER,
                risk_level    TEXT,
                summary       TEXT
            );

            CREATE TABLE IF NOT EXISTS outputs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                thought_id  INTEGER NOT NULL REFERENCES thoughts(id),
                created_at  TEXT    NOT NULL,
                platform    TEXT    NOT NULL,
                content     TEXT    NOT NULL,
                tokens_used INTEGER
            );

            CREATE TABLE IF NOT EXISTS chat_messages (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                chat_id     INTEGER NOT NULL,
                message_id  INTEGER NOT NULL,
                content     TEXT    NOT NULL,
                created_at  TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tags (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                chat_id     INTEGER NOT NULL,
                label       TEXT,
                created_at  TEXT    NOT NULL
            );
        """)


# ── chat_messages ─────────────────────────────────────────────────────────────

def delete_messages_since(user_id: int, chat_id: int, since: str) -> None:
    """Delete chat messages accumulated since a given ISO timestamp.

    Called when a session is cancelled or switched without /analyze, so that
    the discarded messages are never picked up by a future /analyze call.
    """
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM chat_messages WHERE user_id=? AND chat_id=? AND created_at>=?",
            (user_id, chat_id, since),
        )


def save_chat_message(user_id: int, chat_id: int, message_id: int, content: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO chat_messages (user_id, chat_id, message_id, content, created_at) VALUES (?,?,?,?,?)",
            (user_id, chat_id, message_id, content, now),
        )


def get_messages_since_tag(user_id: int, chat_id: int, since: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM chat_messages WHERE user_id=? AND chat_id=? AND created_at>? ORDER BY created_at",
            (user_id, chat_id, since),
        ).fetchall()
    return [dict(r) for r in rows]


def get_today_messages(user_id: int, chat_id: int) -> list[dict]:
    today = datetime.now(timezone.utc).date().isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM chat_messages WHERE user_id=? AND chat_id=? AND created_at>=? ORDER BY created_at",
            (user_id, chat_id, today),
        ).fetchall()
    return [dict(r) for r in rows]


# ── tags ──────────────────────────────────────────────────────────────────────

def save_tag(user_id: int, chat_id: int, label: Optional[str]) -> int:
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO tags (user_id, chat_id, label, created_at) VALUES (?,?,?,?)",
            (user_id, chat_id, label, now),
        )
        return cur.lastrowid


def get_latest_tag(user_id: int, chat_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM tags WHERE user_id=? AND chat_id=? ORDER BY created_at DESC LIMIT 1",
            (user_id, chat_id),
        ).fetchone()
    return dict(row) if row else None


# ── thoughts + outputs ────────────────────────────────────────────────────────

def save_thought(
    user_id: int,
    raw_input: str,
    source: str,
    analysis: dict,
) -> int:
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO thoughts
               (user_id, created_at, raw_input, source, idea_type, novelty_score,
                clarity_score, publishable, risk_level, summary)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                user_id, now, raw_input, source,
                analysis.get("idea_type"),
                analysis.get("novelty_score"),
                analysis.get("clarity_score"),
                1 if analysis.get("publishable") else 0,
                analysis.get("risk_level"),
                analysis.get("summary"),
            ),
        )
        return cur.lastrowid


def save_output(thought_id: int, platform: str, content: str, tokens_used: int = 0) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO outputs (thought_id, created_at, platform, content, tokens_used) VALUES (?,?,?,?,?)",
            (thought_id, now, platform, content, tokens_used),
        )


def get_history(user_id: int, limit: int = 10) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT t.id, t.created_at, t.source, t.idea_type, t.summary,
                      t.novelty_score, t.clarity_score, t.publishable, t.risk_level
               FROM thoughts t WHERE t.user_id=? ORDER BY t.created_at DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def get_thought_count(user_id: int) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM thoughts WHERE user_id=?",
            (user_id,),
        ).fetchone()
    return row[0] if row else 0


def get_thought_with_outputs(thought_id: int, user_id: int) -> Optional[dict]:
    with get_conn() as conn:
        thought = conn.execute(
            "SELECT * FROM thoughts WHERE id=? AND user_id=?",
            (thought_id, user_id),
        ).fetchone()
        if not thought:
            return None
        outputs = conn.execute(
            "SELECT * FROM outputs WHERE thought_id=? ORDER BY platform",
            (thought_id,),
        ).fetchall()
    return {"thought": dict(thought), "outputs": [dict(o) for o in outputs]}
