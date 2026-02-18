"""
Polaris Trace Logger — SQLite-based audit trail for all agent actions.
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path


class TraceLogger:
    """Records every tool invocation, approval decision, and result to SQLite."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = str(Path(__file__).parent.parent / "data" / "trace.db")

        # Ensure directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_table()

    def _create_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS traces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                thought TEXT,
                tool TEXT,
                args TEXT,
                result TEXT,
                approval_level TEXT,
                approved_by TEXT,
                session_id TEXT
            )
        """)
        self.conn.commit()

    def _row_to_dict(self, row: sqlite3.Row) -> Dict:
        return dict(row)

    def log(
        self,
        thought: str,
        tool: str,
        args: dict,
        result: str,
        approval_level: str,
        approved_by: str = "",
        session_id: str = "",
    ):
        """Insert a trace record."""
        self.conn.execute(
            """INSERT INTO traces (timestamp, thought, tool, args, result, approval_level, approved_by, session_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                datetime.utcnow().isoformat(),
                thought,
                tool,
                json.dumps(args, ensure_ascii=False),
                result,
                approval_level,
                approved_by,
                session_id,
            ),
        )
        self.conn.commit()

    def by_session(self, session_id: str, limit: int = 50) -> List[Dict]:
        """Return trace records for a given session."""
        cursor = self.conn.execute(
            "SELECT * FROM traces WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit),
        )
        return [self._row_to_dict(r) for r in cursor.fetchall()]

    def by_tool(self, tool_name: str, limit: int = 50) -> List[Dict]:
        """Return trace records for a given tool."""
        cursor = self.conn.execute(
            "SELECT * FROM traces WHERE tool = ? ORDER BY id DESC LIMIT ?",
            (tool_name, limit),
        )
        return [self._row_to_dict(r) for r in cursor.fetchall()]

    def by_date_range(self, start_date: str, end_date: str) -> List[Dict]:
        """Return trace records within a date range (ISO format strings)."""
        cursor = self.conn.execute(
            "SELECT * FROM traces WHERE timestamp BETWEEN ? AND ? ORDER BY id ASC",
            (start_date, end_date),
        )
        return [self._row_to_dict(r) for r in cursor.fetchall()]

    def export_json(self, session_id: Optional[str] = None) -> str:
        """Export records as a JSON string. Optionally filter by session."""
        if session_id:
            cursor = self.conn.execute(
                "SELECT * FROM traces WHERE session_id = ? ORDER BY id ASC",
                (session_id,),
            )
        else:
            cursor = self.conn.execute("SELECT * FROM traces ORDER BY id ASC")
        rows = [self._row_to_dict(r) for r in cursor.fetchall()]
        return json.dumps(rows, ensure_ascii=False, indent=2)

    def get_recent(self, limit: int = 10) -> List[Dict]:
        """Return the most recent trace records."""
        cursor = self.conn.execute(
            "SELECT * FROM traces ORDER BY id DESC LIMIT ?", (limit,)
        )
        return [self._row_to_dict(r) for r in cursor.fetchall()]
