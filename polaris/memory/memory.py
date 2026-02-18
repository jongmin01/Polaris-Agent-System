"""
Polaris Memory — Second Brain with semantic search and conversation history.

Stores conversations, knowledge, traces, and user feedback in SQLite.
Embeds text via OllamaEmbedder (nomic-embed-text, local, free).
When Ollama is unavailable, falls back to keyword-based search.
"""

import json
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from polaris.memory.embedder import OllamaEmbedder

logger = logging.getLogger(__name__)


class PolarisMemory:
    """Unified memory interface for the Polaris agent system."""

    def __init__(self, db_path: Optional[str] = None, embedder: Optional[OllamaEmbedder] = None):
        if db_path is None:
            db_path = str(Path(__file__).parent.parent.parent / "data" / "polaris_memory.db")

        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

        self.embedder = embedder if embedder is not None else OllamaEmbedder()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _init_schema(self):
        """Create all tables from schema.sql."""
        schema_path = Path(__file__).parent / "schema.sql"
        with open(schema_path, "r") as f:
            schema_sql = f.read()
        self.conn.executescript(schema_sql)

    # ------------------------------------------------------------------
    # Conversations
    # ------------------------------------------------------------------

    def save_conversation(self, session_id: str, role: str, content: str) -> int:
        """Save a conversation turn and return the row id."""
        embedding = self.embedder.embed(content)
        blob = self.embedder.to_bytes(embedding) if embedding else None

        cursor = self.conn.execute(
            """INSERT INTO conversations (timestamp, session_id, role, content, embedding)
               VALUES (?, ?, ?, ?, ?)""",
            (datetime.utcnow().isoformat(), session_id, role, content, blob),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_recent_conversations(self, session_id: str, limit: int = 20) -> List[Dict]:
        """Return the most recent conversation turns for a session."""
        cursor = self.conn.execute(
            """SELECT id, timestamp, session_id, role, content
               FROM conversations
               WHERE session_id = ?
               ORDER BY id DESC LIMIT ?""",
            (session_id, limit),
        )
        rows = [dict(r) for r in cursor.fetchall()]
        rows.reverse()  # oldest first
        return rows

    # ------------------------------------------------------------------
    # Knowledge
    # ------------------------------------------------------------------

    def save_knowledge(
        self,
        category: str,
        title: str,
        content: str,
        source: str = "manual",
        tags: Optional[List[str]] = None,
    ) -> int:
        """Save a knowledge entry and return the row id."""
        embedding = self.embedder.embed(content)
        blob = self.embedder.to_bytes(embedding) if embedding else None

        cursor = self.conn.execute(
            """INSERT INTO knowledge (timestamp, category, title, content, embedding, source, tags)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                datetime.utcnow().isoformat(),
                category,
                title,
                content,
                blob,
                source,
                json.dumps(tags or [], ensure_ascii=False),
            ),
        )
        self.conn.commit()
        return cursor.lastrowid

    # ------------------------------------------------------------------
    # Feedback
    # ------------------------------------------------------------------

    def save_feedback(self, original_action: str, correction: str) -> int:
        """Save user feedback and return the row id."""
        cursor = self.conn.execute(
            """INSERT INTO feedback (timestamp, original_action, correction, applied)
               VALUES (?, ?, ?, 0)""",
            (datetime.utcnow().isoformat(), original_action, correction),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_pending_feedback(self, limit: int = 50) -> List[Dict]:
        """Return feedback entries that haven't been applied yet."""
        cursor = self.conn.execute(
            "SELECT * FROM feedback WHERE applied = 0 ORDER BY id ASC LIMIT ?",
            (limit,),
        )
        return [dict(r) for r in cursor.fetchall()]

    # ------------------------------------------------------------------
    # Semantic search
    # ------------------------------------------------------------------

    def search_memory(self, query: str, top_k: int = 5) -> List[Dict]:
        """Search conversations + knowledge by semantic similarity.

        Falls back to keyword search when embeddings are unavailable.
        """
        query_vec = self.embedder.embed(query)

        if query_vec is not None:
            return self._semantic_search(query_vec, top_k)
        return self._keyword_search(query, top_k)

    def get_relevant_context(self, query: str, top_k: int = 3) -> str:
        """Return a formatted context string for injection into the system prompt."""
        results = self.search_memory(query, top_k=top_k)
        if not results:
            return ""

        parts = []
        for r in results:
            source_label = r.get("source_table", "memory")
            parts.append(f"[{source_label}] {r['content'][:300]}")

        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Internal search implementations
    # ------------------------------------------------------------------

    def _semantic_search(self, query_vec: List[float], top_k: int) -> List[Dict]:
        """Rank by cosine similarity across conversations and knowledge."""
        candidates = []

        # Search conversations
        cursor = self.conn.execute(
            "SELECT id, content, embedding FROM conversations WHERE embedding IS NOT NULL"
        )
        for row in cursor:
            vec = self.embedder.from_bytes(row["embedding"])
            sim = self.embedder.cosine_similarity(query_vec, vec)
            candidates.append({
                "source_table": "conversation",
                "id": row["id"],
                "content": row["content"],
                "score": sim,
            })

        # Search knowledge
        cursor = self.conn.execute(
            "SELECT id, title, content, category, embedding FROM knowledge WHERE embedding IS NOT NULL"
        )
        for row in cursor:
            vec = self.embedder.from_bytes(row["embedding"])
            sim = self.embedder.cosine_similarity(query_vec, vec)
            candidates.append({
                "source_table": "knowledge",
                "id": row["id"],
                "content": f"{row['title']}: {row['content']}",
                "category": row["category"],
                "score": sim,
            })

        candidates.sort(key=lambda c: c["score"], reverse=True)
        return candidates[:top_k]

    def _keyword_search(self, query: str, top_k: int) -> List[Dict]:
        """Simple LIKE-based fallback when embeddings are unavailable."""
        results = []
        pattern = f"%{query}%"

        cursor = self.conn.execute(
            "SELECT id, content FROM conversations WHERE content LIKE ? ORDER BY id DESC LIMIT ?",
            (pattern, top_k),
        )
        for row in cursor:
            results.append({
                "source_table": "conversation",
                "id": row["id"],
                "content": row["content"],
                "score": 0.0,
            })

        remaining = top_k - len(results)
        if remaining > 0:
            cursor = self.conn.execute(
                """SELECT id, title, content, category
                   FROM knowledge
                   WHERE content LIKE ? OR title LIKE ?
                   ORDER BY id DESC LIMIT ?""",
                (pattern, pattern, remaining),
            )
            for row in cursor:
                results.append({
                    "source_table": "knowledge",
                    "id": row["id"],
                    "content": f"{row['title']}: {row['content']}",
                    "category": row["category"],
                    "score": 0.0,
                })

        return results

    # ------------------------------------------------------------------
    # User profile (master_prompt.md)
    # ------------------------------------------------------------------

    def get_user_profile(self, master_prompt_path: Optional[str] = None) -> str:
        """Read master_prompt.md and return its content.

        Returns empty string if the file is not found.
        """
        try:
            from polaris.memory.obsidian_writer import ObsidianWriter
            writer = ObsidianWriter()
            return writer.read_master_prompt(master_prompt_path)
        except Exception as e:
            logger.warning("Failed to read master_prompt.md: %s", e)
            return ""

    def get_user_profile_sections(
        self,
        sections: Optional[List[str]] = None,
        master_prompt_path: Optional[str] = None,
    ) -> str:
        """Extract specific sections from master_prompt.md for prompt injection.

        By default extracts 00_CORE only. Pass section prefixes to customise.
        Returns concatenated section text.
        """
        if sections is None:
            sections = ["00_CORE"]
        try:
            from polaris.memory.obsidian_writer import ObsidianWriter
            writer = ObsidianWriter()
            parts = []
            for sec in sections:
                text = writer.read_master_prompt_section(sec, master_prompt_path)
                if text:
                    parts.append(text)
            return "\n\n".join(parts)
        except Exception as e:
            logger.warning("Failed to read master_prompt sections: %s", e)
            return ""

    # ------------------------------------------------------------------
    # Migration: corrections.jsonl → feedback table
    # ------------------------------------------------------------------

    def migrate_corrections(self, jsonl_path: Optional[str] = None) -> int:
        """Import data/feedback/corrections.jsonl into the feedback table.

        Returns the number of records imported.
        """
        if jsonl_path is None:
            jsonl_path = str(
                Path(__file__).parent.parent.parent / "data" / "feedback" / "corrections.jsonl"
            )

        if not os.path.exists(jsonl_path):
            logger.info("No corrections.jsonl found at %s — nothing to migrate", jsonl_path)
            return 0

        count = 0
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    original = (
                        f"[{entry.get('hash', '')}] {entry.get('subject', '')} → "
                        f"{entry.get('original_label', '')}"
                    )
                    correction = entry.get("corrected_label", "")
                    ts = entry.get("timestamp", datetime.utcnow().isoformat())

                    self.conn.execute(
                        """INSERT INTO feedback (timestamp, original_action, correction, applied)
                           VALUES (?, ?, ?, 1)""",
                        (ts, original, correction),
                    )
                    count += 1
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning("Skipping malformed line in corrections.jsonl: %s", e)

        self.conn.commit()
        logger.info("Migrated %d corrections from %s", count, jsonl_path)
        return count
