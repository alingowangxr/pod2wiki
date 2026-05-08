"""SQLite-based run state persistence for pod2wiki."""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional, Dict

from pod2wiki.models import SourceItem


class RunStateManager:
    """Manages persistence of run states to SQLite."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize the SQLite database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    start_time TIMESTAMP,
                    end_time TIMESTAMP,
                    command_args TEXT,
                    provider TEXT,
                    model TEXT,
                    status TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS run_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT,
                    item_id TEXT,
                    title TEXT,
                    channel TEXT,
                    stage TEXT,
                    error_msg TEXT,
                    raw_json TEXT,
                    FOREIGN KEY (run_id) REFERENCES runs (id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS run_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT,
                    item_id TEXT,
                    stage TEXT,
                    timestamp TIMESTAMP,
                    message TEXT,
                    FOREIGN KEY (run_id) REFERENCES runs (id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS run_warnings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT,
                    item_id TEXT,
                    type TEXT,
                    message TEXT,
                    FOREIGN KEY (run_id) REFERENCES runs (id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS run_item_reviews (
                    item_id TEXT PRIMARY KEY,
                    status TEXT DEFAULT 'pending',
                    notes TEXT,
                    updated_at TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    password_hash TEXT,
                    role TEXT DEFAULT 'user',
                    created_at TIMESTAMP
                )
                """
            )
            conn.commit()

    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        """Fetch user record by username."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM users WHERE username = ?", (username,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def create_user(self, username: str, password_hash: str, role: str = "user"):
        """Register a new user."""
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
                (username, password_hash, role, now),
            )
            conn.commit()

    def list_users(self) -> List[Dict[str, Any]]:
        """List all registered users."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT username, role, created_at FROM users")
            return [dict(row) for row in cursor.fetchall()]

    def create_run(self, command_args: Dict[str, Any], provider: str = "", model: str = "") -> str:
        """Start a new run record."""
        run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO runs (id, start_time, command_args, provider, model, status) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    datetime.now(timezone.utc).isoformat(),
                    json.dumps(command_args, ensure_ascii=False),
                    provider,
                    model,
                    "running",
                ),
            )
            conn.commit()
        return run_id

    def finish_run(self, run_id: str, status: str = "completed"):
        """Mark a run as finished."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE runs SET end_time = ?, status = ? WHERE id = ?",
                (datetime.now(timezone.utc).isoformat(), status, run_id),
            )
            conn.commit()

    def log_item_stage(
        self,
        run_id: str,
        item: SourceItem,
        stage: str,
        error_msg: Optional[str] = None,
    ):
        """Upsert an item's current status AND log a new event."""
        raw_json = item.model_dump_json()
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            # 1. Update current status in run_items (for summary)
            cursor = conn.execute(
                "SELECT id FROM run_items WHERE run_id = ? AND item_id = ?",
                (run_id, item.id),
            )
            row = cursor.fetchone()
            if row:
                conn.execute(
                    "UPDATE run_items SET stage = ?, error_msg = ?, raw_json = ? WHERE id = ?",
                    (stage, error_msg, raw_json, row[0]),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO run_items (run_id, item_id, title, channel, stage, error_msg, raw_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (run_id, item.id, item.title, item.channel, stage, error_msg, raw_json),
                )
            
            # 2. Append to run_events (for history)
            conn.execute(
                "INSERT INTO run_events (run_id, item_id, stage, timestamp, message) VALUES (?, ?, ?, ?, ?)",
                (run_id, item.id, stage, now, error_msg),
            )
            conn.commit()

    def log_warning(self, run_id: str, item_id: str, warn_type: str, message: str):
        """Persist a specific warning to the database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO run_warnings (run_id, item_id, type, message) VALUES (?, ?, ?, ?)",
                (run_id, item_id, warn_type, message),
            )
            conn.commit()

    def update_review_status(self, item_id: str, status: str, notes: Optional[str] = None):
        """Update the review status for a specific item (persists across runs)."""
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO run_item_reviews (item_id, status, notes, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(item_id) DO UPDATE SET
                    status=excluded.status,
                    notes=excluded.notes,
                    updated_at=excluded.updated_at
                """,
                (item_id, status, notes, now),
            )
            conn.commit()

    def get_item_review(self, item_id: str) -> Dict[str, Any]:
        """Fetch the review state for a specific item."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM run_item_reviews WHERE item_id = ?", (item_id,))
            row = cursor.fetchone()
            return dict(row) if row else {"status": "pending", "notes": ""}

    def list_item_reviews(self) -> List[Dict[str, Any]]:
        """List all persisted item review records."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM run_item_reviews ORDER BY updated_at DESC")
            return [dict(row) for row in cursor.fetchall()]

    def get_active_run(self) -> Optional[Dict[str, Any]]:
        """Fetch the current running run if any."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT r.*, 
                       (SELECT count(*) FROM run_items WHERE run_id = r.id) as total_items,
                       (SELECT count(*) FROM run_items WHERE run_id = r.id AND stage = 'failed') as failed_items,
                       (SELECT count(*) FROM run_items WHERE run_id = r.id AND stage = 'skipped') as skipped_items,
                       (SELECT count(*) FROM run_warnings WHERE run_id = r.id) as warning_count
                FROM runs r 
                WHERE r.status = 'running'
                ORDER BY start_time DESC LIMIT 1
                """
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_recent_runs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Fetch summary of recent runs with counts and duration."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT r.*, 
                       (SELECT count(*) FROM run_items WHERE run_id = r.id) as total_items,
                       (SELECT count(*) FROM run_items WHERE run_id = r.id AND stage = 'failed') as failed_items,
                       (SELECT count(*) FROM run_items WHERE run_id = r.id AND stage = 'skipped') as skipped_items,
                       (SELECT count(*) FROM run_warnings WHERE run_id = r.id) as warning_count,
                       (strftime('%s', r.end_time) - strftime('%s', r.start_time)) as duration_sec
                FROM runs r 
                ORDER BY start_time DESC LIMIT ?
                """,
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_run_details(self, run_id: str) -> List[Dict[str, Any]]:
        """Fetch all items for a specific run."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM run_items WHERE run_id = ? ORDER BY id ASC",
                (run_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_run_warnings(self, run_id: str) -> List[Dict[str, Any]]:
        """Fetch all warnings for a specific run."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM run_warnings WHERE run_id = ?", (run_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_run_events(self, run_id: str, item_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch events for a specific run/item."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if item_id:
                cursor = conn.execute(
                    "SELECT * FROM run_events WHERE run_id = ? AND item_id = ? ORDER BY timestamp ASC",
                    (run_id, item_id),
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM run_events WHERE run_id = ? ORDER BY timestamp ASC",
                    (run_id,),
                )
            return [dict(row) for row in cursor.fetchall()]

    def get_failed_items(self, run_id: str) -> List[SourceItem]:
        """Fetch items that failed in a previous run."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT raw_json FROM run_items WHERE run_id = ? AND stage = 'failed'",
                (run_id,),
            )
            return self._parse_items(cursor.fetchall())

    def get_all_items(self, run_id: str) -> List[SourceItem]:
        """Fetch all items from a previous run."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT raw_json FROM run_items WHERE run_id = ?",
                (run_id,),
            )
            return self._parse_items(cursor.fetchall())

    def _parse_items(self, rows) -> List[SourceItem]:
        from pod2wiki.models import RSSItem, YouTubeItem, FileItem
        items = []
        for row in rows:
            data = json.loads(row[0])
            kind = data.get("source_kind")
            if kind == "rss":
                items.append(RSSItem(**data))
            elif kind == "youtube":
                items.append(YouTubeItem(**data))
            elif kind == "file":
                items.append(FileItem(**data))
        return items
