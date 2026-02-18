"""
Polaris Feedback Manager — Aha! Memory (correction feedback loop).

Detects user corrections, stores them with embeddings, and formats them
as caution blocks for system prompt injection.
"""

import logging
import re
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Korean + English correction patterns
CORRECTION_PATTERNS = [
    # Korean explicit corrections
    r"틀렸어",
    r"틀렸는데",
    r"틀린 거",
    r"잘못됐어",
    r"잘못된 거",
    r"그게 아니라",
    r"그거 아니야",
    r"아니야[,.]?\s",
    r"아닌데",
    r"아니거든",
    r"그건 아니고",
    r"사실은",
    r"실제로는",
    r"정확히는",
    r"정정할게",
    r"고쳐줘",
    r"수정해",
    r"다시 해",
    r"다시 말해",
    r"제대로",
    # English explicit corrections
    r"(?i)that'?s wrong",
    r"(?i)that'?s not right",
    r"(?i)that'?s incorrect",
    r"(?i)you'?re wrong",
    r"(?i)not correct",
    r"(?i)actually[,.]?\s",
    r"(?i)no[,.]?\s+it'?s",
    r"(?i)correction:",
    r"(?i)wrong[.!]",
]

# Compiled patterns for performance
_COMPILED_PATTERNS = [re.compile(p) for p in CORRECTION_PATTERNS]

# Max character length for stored feedback text
MAX_FEEDBACK_LENGTH = 200
# Max feedback items for prompt injection
MAX_PROMPT_FEEDBACK = 3
# Max characters per feedback item in prompt
MAX_PROMPT_ITEM_LENGTH = 60


class FeedbackManager:
    """Manages user correction feedback: detection, storage, retrieval, and formatting."""

    def __init__(self, memory, embedder=None):
        """
        Args:
            memory: PolarisMemory instance (provides DB connection).
            embedder: Optional OllamaEmbedder for semantic search.
        """
        self.memory = memory
        self.embedder = embedder or getattr(memory, "embedder", None)
        self._migrate_schema()

    def _migrate_schema(self):
        """Add new columns to feedback table if they don't exist (idempotent)."""
        conn = self.memory.conn
        cursor = conn.execute("PRAGMA table_info(feedback)")
        existing_cols = {row[1] for row in cursor.fetchall()}

        new_columns = {
            "embedding": "BLOB",
            "session_id": "TEXT",
            "category": "TEXT",
        }

        for col_name, col_type in new_columns.items():
            if col_name not in existing_cols:
                conn.execute(f"ALTER TABLE feedback ADD COLUMN {col_name} {col_type}")
                logger.info("Added column '%s' to feedback table", col_name)

        conn.commit()

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    @staticmethod
    def detect_correction(user_message: str) -> bool:
        """Check if a user message contains a correction pattern.

        Stateless — only checks text against regex patterns.
        """
        if not user_message or len(user_message) < 2:
            return False

        for pattern in _COMPILED_PATTERNS:
            if pattern.search(user_message):
                return True
        return False

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------

    def save_correction(
        self,
        session_id: str,
        original_response: str,
        user_correction: str,
        category: Optional[str] = None,
    ) -> int:
        """Save a correction to the feedback table.

        Returns the row id.
        """
        # Truncate to avoid bloating the DB
        original_response = original_response[:MAX_FEEDBACK_LENGTH]
        user_correction = user_correction[:MAX_FEEDBACK_LENGTH]

        # Embed the correction for semantic search
        embedding_blob = None
        if self.embedder:
            try:
                vec = self.embedder.embed(user_correction)
                if vec:
                    embedding_blob = self.embedder.to_bytes(vec)
            except Exception as e:
                logger.debug("Embedding correction failed: %s", e)

        conn = self.memory.conn
        cursor = conn.execute(
            """INSERT INTO feedback
               (timestamp, original_action, correction, applied, embedding, session_id, category)
               VALUES (?, ?, ?, 0, ?, ?, ?)""",
            (
                datetime.utcnow().isoformat(),
                original_response,
                user_correction,
                embedding_blob,
                session_id,
                category,
            ),
        )
        conn.commit()
        logger.info("Saved correction (id=%d, category=%s)", cursor.lastrowid, category)
        return cursor.lastrowid

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def get_relevant_feedback(self, query: str, top_k: int = 3) -> List[Dict]:
        """Retrieve feedback most relevant to query.

        Uses semantic search if embedder is available, else falls back to most recent.
        """
        conn = self.memory.conn

        # Try semantic search first
        if self.embedder:
            try:
                query_vec = self.embedder.embed(query)
                if query_vec:
                    return self._semantic_feedback_search(query_vec, top_k)
            except Exception as e:
                logger.debug("Semantic feedback search failed: %s", e)

        # Fallback: most recent
        cursor = conn.execute(
            """SELECT id, timestamp, original_action, correction, category, session_id
               FROM feedback ORDER BY id DESC LIMIT ?""",
            (top_k,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def _semantic_feedback_search(self, query_vec: list, top_k: int) -> List[Dict]:
        """Rank feedback by cosine similarity to query vector."""
        conn = self.memory.conn
        cursor = conn.execute(
            """SELECT id, timestamp, original_action, correction, category, session_id, embedding
               FROM feedback WHERE embedding IS NOT NULL"""
        )

        candidates = []
        for row in cursor:
            row_dict = dict(row)
            vec = self.embedder.from_bytes(row_dict.pop("embedding"))
            sim = self.embedder.cosine_similarity(query_vec, vec)
            row_dict["score"] = sim
            candidates.append(row_dict)

        candidates.sort(key=lambda c: c["score"], reverse=True)
        return candidates[:top_k]

    def get_recent_feedback(self, limit: int = 10) -> List[Dict]:
        """Get most recent feedback entries. For /feedback command."""
        cursor = self.memory.conn.execute(
            """SELECT id, timestamp, original_action, correction, category
               FROM feedback ORDER BY id DESC LIMIT ?""",
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_correction_count(self, category: Optional[str] = None) -> int:
        """Count total corrections, optionally filtered by category."""
        conn = self.memory.conn
        if category:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM feedback WHERE category = ?", (category,)
            )
        else:
            cursor = conn.execute("SELECT COUNT(*) FROM feedback")
        return cursor.fetchone()[0]

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------

    @staticmethod
    def format_as_caution(feedbacks: List[Dict]) -> str:
        """Format feedback list as a caution block for system prompt injection.

        Returns empty string if no feedback.
        """
        if not feedbacks:
            return ""

        items = []
        for fb in feedbacks[:MAX_PROMPT_FEEDBACK]:
            correction = fb.get("correction", "")
            if len(correction) > MAX_PROMPT_ITEM_LENGTH:
                correction = correction[:MAX_PROMPT_ITEM_LENGTH] + "..."
            original = fb.get("original_action", "")
            if len(original) > MAX_PROMPT_ITEM_LENGTH:
                original = original[:MAX_PROMPT_ITEM_LENGTH] + "..."
            items.append(f"- 잘못: {original} → 교정: {correction}")

        block = "[주의: 과거 실수 기록]\n" + "\n".join(items)
        return block
