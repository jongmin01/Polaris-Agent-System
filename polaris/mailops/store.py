"""SQLite store for MailOps."""

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional


class MailOpsStore:
    """Persistence for ingested mail, classification, alerts, and actions."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = str(Path(__file__).resolve().parent.parent.parent / "data" / "mailops.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS mail_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ext_id TEXT UNIQUE NOT NULL,
                thread_id TEXT,
                account_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                sender TEXT,
                subject TEXT,
                body_preview TEXT,
                received_at TEXT,
                is_unread INTEGER NOT NULL DEFAULT 1,
                raw_json TEXT,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_mail_messages_received_at ON mail_messages(received_at);
            CREATE INDEX IF NOT EXISTS idx_mail_messages_account_id ON mail_messages(account_id);

            CREATE TABLE IF NOT EXISTS mail_classification (
                ext_id TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                confidence REAL NOT NULL,
                reason TEXT,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(ext_id) REFERENCES mail_messages(ext_id)
            );

            CREATE INDEX IF NOT EXISTS idx_mail_classification_category ON mail_classification(category);

            CREATE TABLE IF NOT EXISTS mail_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ext_id TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                notified_at TEXT NOT NULL,
                UNIQUE(ext_id, alert_type)
            );

            CREATE TABLE IF NOT EXISTS mail_actions_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ext_id TEXT,
                action TEXT NOT NULL,
                status TEXT NOT NULL,
                detail TEXT,
                created_at TEXT NOT NULL
            );
            """
        )
        self.conn.commit()

    def upsert_message(self, message: dict) -> bool:
        """Insert message if new. Returns True when inserted."""
        now = datetime.utcnow().isoformat()
        cursor = self.conn.execute(
            """
            INSERT OR IGNORE INTO mail_messages
            (ext_id, thread_id, account_id, provider, sender, subject, body_preview, received_at, is_unread, raw_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message["ext_id"],
                message.get("thread_id", ""),
                message.get("account_id", "unknown"),
                message.get("provider", "unknown"),
                message.get("sender", ""),
                message.get("subject", ""),
                message.get("body_preview", ""),
                message.get("received_at", ""),
                1 if message.get("is_unread", True) else 0,
                json.dumps(message, ensure_ascii=False),
                now,
            ),
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def save_classification(self, ext_id: str, category: str, confidence: float, reason: str):
        now = datetime.utcnow().isoformat()
        self.conn.execute(
            """
            INSERT INTO mail_classification (ext_id, category, confidence, reason, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(ext_id) DO UPDATE SET
                category=excluded.category,
                confidence=excluded.confidence,
                reason=excluded.reason,
                updated_at=excluded.updated_at
            """,
            (ext_id, category, confidence, reason, now),
        )
        self.conn.commit()

    def get_digest(self, category: Optional[str] = None, account_id: Optional[str] = None, limit: int = 50) -> list:
        sql = (
            """
            SELECT m.ext_id, m.account_id, m.provider, m.sender, m.subject, m.body_preview, m.received_at,
                   c.category, c.confidence, c.reason
            FROM mail_messages m
            LEFT JOIN mail_classification c ON c.ext_id = m.ext_id
            WHERE 1=1
            """
        )
        params = []
        if category:
            sql += " AND c.category = ?"
            params.append(category)
        if account_id:
            sql += " AND m.account_id = ?"
            params.append(account_id)
        sql += " ORDER BY COALESCE(m.received_at, m.created_at) DESC LIMIT ?"
        params.append(limit)
        rows = self.conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def list_unalerted_urgent(self, limit: int = 20) -> list:
        rows = self.conn.execute(
            """
            SELECT m.ext_id, m.account_id, m.sender, m.subject, m.body_preview, m.received_at
            FROM mail_messages m
            JOIN mail_classification c ON c.ext_id = m.ext_id
            LEFT JOIN mail_alerts a ON a.ext_id = m.ext_id AND a.alert_type = 'urgent'
            WHERE c.category = 'urgent' AND a.id IS NULL
            ORDER BY COALESCE(m.received_at, m.created_at) DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def mark_alerted(self, ext_id: str, alert_type: str = "urgent"):
        self.conn.execute(
            """
            INSERT OR IGNORE INTO mail_alerts (ext_id, alert_type, notified_at)
            VALUES (?, ?, ?)
            """,
            (ext_id, alert_type, datetime.utcnow().isoformat()),
        )
        self.conn.commit()

    def log_action(self, action: str, status: str, detail: str = "", ext_id: str = ""):
        self.conn.execute(
            """
            INSERT INTO mail_actions_log (ext_id, action, status, detail, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (ext_id, action, status, detail, datetime.utcnow().isoformat()),
        )
        self.conn.commit()
