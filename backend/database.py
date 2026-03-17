"""
GymGuard - Database Layer
=========================
All PostgreSQL interaction lives here. The detector and API
import from this module — they never write SQL directly.

Schema:
    sessions   — one row per video run
    entries    — one row per inward person crossing
    violations — one row per tailgate event
"""

import os
import uuid
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import RealDictCursor


# ── Connection ────────────────────────────────────────────────────────────────

def get_connection():
    """
    Opens a new connection using environment variables.
    DATABASE_URL takes priority; individual vars used as fallback.
    """
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return psycopg2.connect(database_url, cursor_factory=RealDictCursor)

    return psycopg2.connect(
        host     = os.getenv("POSTGRES_HOST",     "localhost"),
        port     = os.getenv("POSTGRES_PORT",     "5432"),
        dbname   = os.getenv("POSTGRES_DB",       "gymguard"),
        user     = os.getenv("POSTGRES_USER",     "gymguard"),
        password = os.getenv("POSTGRES_PASSWORD", "gymguard"),
        cursor_factory=RealDictCursor,
    )


# ── Schema setup ──────────────────────────────────────────────────────────────

def init_db():
    """
    Creates tables if they don't exist.
    Safe to call on every startup — uses IF NOT EXISTS.
    """
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id          TEXT PRIMARY KEY,
            video_path  TEXT NOT NULL,
            line_ratio  REAL NOT NULL,
            started_at  TIMESTAMPTZ NOT NULL,
            ended_at    TIMESTAMPTZ,
            total_frames INTEGER,
            fps         REAL,
            status      TEXT NOT NULL DEFAULT 'processing'
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS entries (
            id          SERIAL PRIMARY KEY,
            session_id  TEXT NOT NULL REFERENCES sessions(id),
            tracker_id  INTEGER NOT NULL,
            frame       INTEGER NOT NULL,
            timestamp   REAL NOT NULL,
            confidence  REAL NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS violations (
            id          SERIAL PRIMARY KEY,
            session_id  TEXT NOT NULL REFERENCES sessions(id),
            frame       INTEGER NOT NULL,
            timestamp   REAL NOT NULL,
            people      INTEGER NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)

    # Index for fast lookups by session
    cur.execute("CREATE INDEX IF NOT EXISTS idx_entries_session    ON entries    (session_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_violations_session ON violations (session_id);")

    conn.commit()
    cur.close()
    conn.close()
    print("✅ Database tables ready")


# ── Session ───────────────────────────────────────────────────────────────────

def create_session(video_path: str, line_ratio: float) -> str:
    """
    Inserts a new session row and returns its ID.
    Called at the start of run_detection().
    """
    session_id = str(uuid.uuid4())
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        INSERT INTO sessions (id, video_path, line_ratio, started_at)
        VALUES (%s, %s, %s, %s)
    """, (session_id, video_path, line_ratio, datetime.now(timezone.utc)))
    conn.commit()
    cur.close()
    conn.close()
    return session_id


def close_session(session_id: str, total_frames: int, fps: float, status: str = "done"):
    """
    Updates the session row when detection finishes.
    """
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        UPDATE sessions
        SET ended_at = %s, total_frames = %s, fps = %s, status = %s
        WHERE id = %s
    """, (datetime.now(timezone.utc), total_frames, fps, status, session_id))
    conn.commit()
    cur.close()
    conn.close()


# ── Entries ───────────────────────────────────────────────────────────────────

def save_entry(session_id: str, tracker_id: int, frame: int, timestamp: float, confidence: float):
    """
    Inserts one inward crossing entry.
    Called each time a new tracker ID crosses the line inward.
    """
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        INSERT INTO entries (session_id, tracker_id, frame, timestamp, confidence)
        VALUES (%s, %s, %s, %s, %s)
    """, (session_id, int(tracker_id), frame, timestamp, confidence))
    conn.commit()
    cur.close()
    conn.close()


# ── Violations ────────────────────────────────────────────────────────────────

def save_violation(session_id: str, frame: int, timestamp: float, people: int):
    """
    Inserts one tailgate violation.
    Called each time the violation condition is met.
    """
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        INSERT INTO violations (session_id, frame, timestamp, people)
        VALUES (%s, %s, %s, %s)
    """, (session_id, frame, timestamp, people))
    conn.commit()
    cur.close()
    conn.close()


# ── Query helpers (used by /history endpoints) ────────────────────────────────

def get_all_sessions():
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("SELECT * FROM sessions ORDER BY started_at DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]


def get_session(session_id: str):
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("SELECT * FROM sessions WHERE id = %s", (session_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else None


def get_entries(session_id: str):
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("SELECT * FROM entries WHERE session_id = %s ORDER BY frame", (session_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]


def get_violations(session_id: str):
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("SELECT * FROM violations WHERE session_id = %s ORDER BY frame", (session_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]


def get_all_violations():
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT v.*, s.video_path
        FROM violations v
        JOIN sessions s ON v.session_id = s.id
        ORDER BY v.created_at DESC
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]
