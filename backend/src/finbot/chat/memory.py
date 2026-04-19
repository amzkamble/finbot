"""SQLite-backed conversation history manager."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from threading import Lock

from finbot.utils.logger import get_logger

logger = get_logger(__name__)

# Maximum number of turns (user+assistant pairs) to keep per session
MAX_TURNS = 10

# Sessions expire after this many seconds of inactivity
SESSION_TTL_SECONDS = 1800  # 30 minutes

# Default database path (relative to backend directory)
DEFAULT_DB_PATH = "finbot_chat.db"


class ChatMemory:
    """
    SQLite-backed conversation store keyed by ``session_id``.

    Each session holds the last ``MAX_TURNS`` user/assistant message pairs.
    Stale sessions are cleaned up periodically.
    """

    def __init__(
        self,
        db_path: str | Path = DEFAULT_DB_PATH,
        max_turns: int = MAX_TURNS,
        ttl_seconds: int = SESSION_TTL_SECONDS,
    ) -> None:
        self._db_path = str(db_path)
        self._max_turns = max_turns
        self._ttl = ttl_seconds
        self._lock = Lock()

        self._init_db()
        logger.info(
            "ChatMemory initialised (db=%s, max_turns=%d, ttl=%ds)",
            self._db_path,
            max_turns,
            ttl_seconds,
        )

    def _get_conn(self) -> sqlite3.Connection:
        """Create a new connection (SQLite connections are not thread-safe)."""
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self) -> None:
        """Create tables if they don't exist."""
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT,
                    last_active REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_session
                ON messages(session_id, id)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    session_id TEXT,
                    user_id TEXT NOT NULL,
                    user_role TEXT NOT NULL,
                    query TEXT NOT NULL,
                    route_name TEXT,
                    route_confidence REAL,
                    was_rbac_filtered INTEGER DEFAULT 0,
                    original_route TEXT,
                    collections_searched TEXT,
                    chunks_retrieved INTEGER DEFAULT 0,
                    blocked INTEGER DEFAULT 0,
                    blocked_reason TEXT,
                    latency_ms REAL DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_timestamp
                ON audit_log(timestamp DESC)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_user
                ON audit_log(user_id, timestamp DESC)
            """)

    # ── Public API ──────────────────────────────────────────────────────

    def get_history(self, session_id: str) -> list[dict[str, str]]:
        """
        Return the conversation history for a session.

        Returns the last ``max_turns * 2`` messages (user + assistant pairs).
        """
        with self._lock:
            self._cleanup_stale()

            with self._get_conn() as conn:
                # Update last_active timestamp
                conn.execute(
                    "UPDATE sessions SET last_active = ? WHERE session_id = ?",
                    (time.time(), session_id),
                )

                # Fetch the last N messages
                max_messages = self._max_turns * 2
                rows = conn.execute(
                    """
                    SELECT role, content FROM messages
                    WHERE session_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (session_id, max_messages),
                ).fetchall()

            # Reverse to get chronological order
            return [{"role": role, "content": content} for role, content in reversed(rows)]

    def add_user_message(self, session_id: str, content: str, user_id: str = "") -> None:
        """Append a user message to the session history."""
        self._add(session_id, "user", content, user_id)

    def add_assistant_message(self, session_id: str, content: str) -> None:
        """Append an assistant message to the session history."""
        self._add(session_id, "assistant", content)

    def clear_session(self, session_id: str) -> None:
        """Delete a specific session and its messages."""
        with self._lock:
            with self._get_conn() as conn:
                conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
                conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))

    def get_session_count(self) -> int:
        """Return the number of active sessions."""
        with self._lock:
            self._cleanup_stale()
            with self._get_conn() as conn:
                row = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()
                return row[0] if row else 0

    def get_all_sessions(self) -> list[dict]:
        """Return metadata for all active sessions (for admin)."""
        with self._lock:
            self._cleanup_stale()
            with self._get_conn() as conn:
                rows = conn.execute("""
                    SELECT s.session_id, s.user_id, s.last_active,
                           COUNT(m.id) as message_count
                    FROM sessions s
                    LEFT JOIN messages m ON s.session_id = m.session_id
                    GROUP BY s.session_id
                    ORDER BY s.last_active DESC
                """).fetchall()

            return [
                {
                    "session_id": r[0],
                    "user_id": r[1],
                    "last_active": r[2],
                    "message_count": r[3],
                }
                for r in rows
            ]

    def log_query(
        self,
        session_id: str,
        user_id: str,
        user_role: str,
        query: str,
        route_name: str | None = None,
        route_confidence: float = 0.0,
        was_rbac_filtered: bool = False,
        original_route: str | None = None,
        collections_searched: list[str] | None = None,
        chunks_retrieved: int = 0,
        blocked: bool = False,
        blocked_reason: str | None = None,
        latency_ms: float = 0.0,
    ) -> None:
        """Write an audit log entry for a user query."""
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO audit_log (
                        timestamp, session_id, user_id, user_role, query,
                        route_name, route_confidence, was_rbac_filtered,
                        original_route, collections_searched, chunks_retrieved,
                        blocked, blocked_reason, latency_ms
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        time.time(),
                        session_id,
                        user_id,
                        user_role,
                        query,
                        route_name,
                        route_confidence,
                        1 if was_rbac_filtered else 0,
                        original_route,
                        ",".join(collections_searched) if collections_searched else None,
                        chunks_retrieved,
                        1 if blocked else 0,
                        blocked_reason,
                        latency_ms,
                    ),
                )
        logger.info(
            "AUDIT | user=%s role=%s route=%s collections=%s blocked=%s latency=%.0fms",
            user_id,
            user_role,
            route_name or "none",
            collections_searched or [],
            blocked,
            latency_ms,
        )

    def get_audit_logs(
        self,
        limit: int = 100,
        user_id: str | None = None,
    ) -> list[dict]:
        """Retrieve recent audit log entries (for admin dashboard)."""
        with self._lock:
            with self._get_conn() as conn:
                if user_id:
                    rows = conn.execute(
                        """
                        SELECT timestamp, session_id, user_id, user_role, query,
                               route_name, route_confidence, was_rbac_filtered,
                               original_route, collections_searched, chunks_retrieved,
                               blocked, blocked_reason, latency_ms
                        FROM audit_log
                        WHERE user_id = ?
                        ORDER BY timestamp DESC LIMIT ?
                        """,
                        (user_id, limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT timestamp, session_id, user_id, user_role, query,
                               route_name, route_confidence, was_rbac_filtered,
                               original_route, collections_searched, chunks_retrieved,
                               blocked, blocked_reason, latency_ms
                        FROM audit_log
                        ORDER BY timestamp DESC LIMIT ?
                        """,
                        (limit,),
                    ).fetchall()

            return [
                {
                    "timestamp": r[0],
                    "session_id": r[1],
                    "user_id": r[2],
                    "user_role": r[3],
                    "query": r[4],
                    "route_name": r[5],
                    "route_confidence": r[6],
                    "was_rbac_filtered": bool(r[7]),
                    "original_route": r[8],
                    "collections_searched": r[9].split(",") if r[9] else [],
                    "chunks_retrieved": r[10],
                    "blocked": bool(r[11]),
                    "blocked_reason": r[12],
                    "latency_ms": r[13],
                }
                for r in rows
            ]

    # ── Private helpers ─────────────────────────────────────────────────

    def _add(self, session_id: str, role: str, content: str, user_id: str = "") -> None:
        with self._lock:
            now = time.time()
            with self._get_conn() as conn:
                # Upsert session
                conn.execute(
                    """
                    INSERT INTO sessions (session_id, user_id, last_active)
                    VALUES (?, ?, ?)
                    ON CONFLICT(session_id) DO UPDATE SET last_active = ?
                    """,
                    (session_id, user_id, now, now),
                )

                # Insert message
                conn.execute(
                    "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                    (session_id, role, content, now),
                )

                # Trim old messages beyond max_turns
                max_messages = self._max_turns * 2
                conn.execute(
                    """
                    DELETE FROM messages
                    WHERE session_id = ? AND id NOT IN (
                        SELECT id FROM messages
                        WHERE session_id = ?
                        ORDER BY id DESC
                        LIMIT ?
                    )
                    """,
                    (session_id, session_id, max_messages),
                )

    def _cleanup_stale(self) -> None:
        """Remove sessions that have exceeded the TTL."""
        cutoff = time.time() - self._ttl
        with self._get_conn() as conn:
            # CASCADE will delete messages too
            result = conn.execute(
                "DELETE FROM sessions WHERE last_active < ?", (cutoff,)
            )
            if result.rowcount > 0:
                logger.debug("Cleaned up %d stale sessions", result.rowcount)
