"""Tests for polaris.memory.feedback_manager (FeedbackManager).

All tests use a temporary SQLite DB and mock embedders
so they run without Ollama or any external service.
"""

import tempfile
import pytest
from unittest.mock import patch, MagicMock

from polaris.memory.embedder import OllamaEmbedder
from polaris.memory.memory import PolarisMemory
from polaris.memory.feedback_manager import FeedbackManager


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

class FakeEmbedder:
    """Deterministic embedder for tests."""

    available = True

    def embed(self, text):
        seed = len(text) + ord(text[0]) if text else 0
        return [float(seed % (i + 1)) / (i + 1) for i in range(8)]

    @staticmethod
    def to_bytes(vector):
        return OllamaEmbedder.to_bytes(vector)

    @staticmethod
    def from_bytes(blob):
        return OllamaEmbedder.from_bytes(blob)

    @staticmethod
    def cosine_similarity(a, b):
        return OllamaEmbedder.cosine_similarity(a, b)


class NoEmbedder:
    """Embedder that simulates Ollama being unavailable."""

    available = False

    def embed(self, text):
        return None

    @staticmethod
    def to_bytes(vector):
        return OllamaEmbedder.to_bytes(vector)

    @staticmethod
    def from_bytes(blob):
        return OllamaEmbedder.from_bytes(blob)

    @staticmethod
    def cosine_similarity(a, b):
        return OllamaEmbedder.cosine_similarity(a, b)


@pytest.fixture
def memory_db(tmp_path):
    """Create a PolarisMemory with temp DB and fake embedder."""
    db_path = str(tmp_path / "test_feedback.db")
    mem = PolarisMemory(db_path=db_path, embedder=FakeEmbedder())
    return mem


@pytest.fixture
def feedback_mgr(memory_db):
    """Create a FeedbackManager with fake embedder."""
    return FeedbackManager(memory_db, embedder=FakeEmbedder())


@pytest.fixture
def feedback_mgr_no_embed(tmp_path):
    """Create a FeedbackManager without embedder."""
    db_path = str(tmp_path / "test_feedback_no_embed.db")
    mem = PolarisMemory(db_path=db_path, embedder=NoEmbedder())
    return FeedbackManager(mem, embedder=NoEmbedder())


# ==================================================================
# TestDetectCorrection (8 tests)
# ==================================================================

class TestDetectCorrection:
    """Test correction pattern detection."""

    def test_korean_explicit(self):
        assert FeedbackManager.detect_correction("틀렸어, MoS2 밴드갭은 1.8eV야") is True

    def test_korean_not_that(self):
        assert FeedbackManager.detect_correction("그게 아니라 WSe2로 해야 해") is True

    def test_korean_actually(self):
        assert FeedbackManager.detect_correction("실제로는 3.1eV가 맞아") is True

    def test_korean_wrong_info(self):
        assert FeedbackManager.detect_correction("잘못됐어 다시 확인해봐") is True

    def test_english_wrong(self):
        assert FeedbackManager.detect_correction("That's wrong, the value is 2.5") is True

    def test_english_actually(self):
        assert FeedbackManager.detect_correction("Actually, it should be Python 3.11") is True

    def test_false_positive_greeting(self):
        """Normal greetings should not be detected as corrections."""
        assert FeedbackManager.detect_correction("안녕? 잘 지내?") is False

    def test_false_positive_question(self):
        """Normal questions should not be detected as corrections."""
        assert FeedbackManager.detect_correction("MoS2 밴드갭이 얼마야?") is False

    def test_empty_message(self):
        assert FeedbackManager.detect_correction("") is False

    def test_short_message(self):
        assert FeedbackManager.detect_correction("a") is False


# ==================================================================
# TestSaveCorrection (4 tests)
# ==================================================================

class TestSaveCorrection:
    """Test saving corrections to DB."""

    def test_save_basic(self, feedback_mgr):
        row_id = feedback_mgr.save_correction(
            session_id="user123",
            original_response="MoS2 밴드갭은 2.0eV",
            user_correction="틀렸어, 1.8eV가 맞아",
        )
        assert row_id > 0

    def test_save_fields(self, feedback_mgr):
        feedback_mgr.save_correction(
            session_id="user123",
            original_response="Original",
            user_correction="Correction",
            category="factual",
        )
        rows = feedback_mgr.get_recent_feedback(limit=1)
        assert len(rows) == 1
        assert rows[0]["correction"] == "Correction"
        assert rows[0]["original_action"] == "Original"
        assert rows[0]["category"] == "factual"

    def test_save_with_category(self, feedback_mgr):
        row_id = feedback_mgr.save_correction(
            session_id="user123",
            original_response="X",
            user_correction="Y",
            category="tone",
        )
        assert row_id > 0

    def test_save_truncates_long_text(self, feedback_mgr):
        long_text = "A" * 500
        feedback_mgr.save_correction(
            session_id="user123",
            original_response=long_text,
            user_correction=long_text,
        )
        rows = feedback_mgr.get_recent_feedback(limit=1)
        assert len(rows[0]["original_action"]) <= 200
        assert len(rows[0]["correction"]) <= 200


# ==================================================================
# TestGetRelevantFeedback (4 tests)
# ==================================================================

class TestGetRelevantFeedback:
    """Test feedback retrieval (semantic + fallback)."""

    def test_semantic_search(self, feedback_mgr):
        feedback_mgr.save_correction("s1", "Wrong answer about MoS2", "MoS2 밴드갭은 1.8eV")
        feedback_mgr.save_correction("s1", "Wrong about WSe2", "WSe2는 다른 물질이야")

        results = feedback_mgr.get_relevant_feedback("MoS2 밴드갭", top_k=2)
        assert len(results) <= 2
        assert all("correction" in r for r in results)

    def test_top_k(self, feedback_mgr):
        for i in range(5):
            feedback_mgr.save_correction("s1", f"orig {i}", f"correction {i}")

        results = feedback_mgr.get_relevant_feedback("test", top_k=3)
        assert len(results) == 3

    def test_fallback_no_embedder(self, feedback_mgr_no_embed):
        feedback_mgr_no_embed.save_correction("s1", "orig", "correction A")
        feedback_mgr_no_embed.save_correction("s1", "orig2", "correction B")

        results = feedback_mgr_no_embed.get_relevant_feedback("test", top_k=5)
        assert len(results) == 2

    def test_empty_db(self, feedback_mgr):
        results = feedback_mgr.get_relevant_feedback("anything")
        assert results == []


# ==================================================================
# TestFormatAsCaution (4 tests)
# ==================================================================

class TestFormatAsCaution:
    """Test formatting feedback as caution block."""

    def test_format_basic(self):
        feedbacks = [
            {"original_action": "MoS2 gap is 2.0eV", "correction": "실제로는 1.8eV"},
        ]
        result = FeedbackManager.format_as_caution(feedbacks)
        assert "[주의: 과거 실수 기록]" in result
        assert "1.8eV" in result

    def test_format_empty(self):
        assert FeedbackManager.format_as_caution([]) == ""

    def test_format_max_three(self):
        feedbacks = [
            {"original_action": f"orig{i}", "correction": f"corr{i}"}
            for i in range(5)
        ]
        result = FeedbackManager.format_as_caution(feedbacks)
        assert result.count("- 잘못:") == 3

    def test_format_truncates_long(self):
        feedbacks = [
            {"original_action": "A" * 100, "correction": "B" * 100},
        ]
        result = FeedbackManager.format_as_caution(feedbacks)
        assert "..." in result


# ==================================================================
# TestGetCorrectionCount (3 tests)
# ==================================================================

class TestGetCorrectionCount:
    """Test correction count queries."""

    def test_count_all(self, feedback_mgr):
        feedback_mgr.save_correction("s1", "o1", "c1")
        feedback_mgr.save_correction("s1", "o2", "c2")
        assert feedback_mgr.get_correction_count() == 2

    def test_count_by_category(self, feedback_mgr):
        feedback_mgr.save_correction("s1", "o1", "c1", category="factual")
        feedback_mgr.save_correction("s1", "o2", "c2", category="tone")
        feedback_mgr.save_correction("s1", "o3", "c3", category="factual")
        assert feedback_mgr.get_correction_count(category="factual") == 2
        assert feedback_mgr.get_correction_count(category="tone") == 1

    def test_count_empty(self, feedback_mgr):
        assert feedback_mgr.get_correction_count() == 0


# ==================================================================
# TestSchemaMigration (2 tests)
# ==================================================================

class TestSchemaMigration:
    """Test schema migration (ALTER TABLE)."""

    def test_columns_added(self, memory_db):
        """New columns should exist after FeedbackManager init."""
        fm = FeedbackManager(memory_db)
        cursor = memory_db.conn.execute("PRAGMA table_info(feedback)")
        col_names = {row[1] for row in cursor.fetchall()}
        assert "embedding" in col_names
        assert "session_id" in col_names
        assert "category" in col_names

    def test_idempotent(self, memory_db):
        """Running migration twice should not raise."""
        fm1 = FeedbackManager(memory_db)
        fm2 = FeedbackManager(memory_db)  # should not raise
        assert fm2 is not None


# ==================================================================
# TestRouterIntegration (3 tests)
# ==================================================================

class TestRouterIntegration:
    """Test FeedbackManager integration with PolarisRouter."""

    @patch("polaris.router.PolarisRouter._init_ollama")
    @patch("polaris.router.PolarisRouter._load_tools")
    @patch("polaris.router.PolarisRouter._init_skills")
    @patch("polaris.router.PolarisRouter._init_feedback")
    @patch("polaris.router.PolarisRouter._init_memory")
    def test_prompt_injection(self, mock_mem, mock_fb, mock_skills, mock_tools, mock_ollama, tmp_path):
        """Feedback caution block should appear in system prompt."""
        db_path = str(tmp_path / "router_test.db")

        from polaris.router import PolarisRouter
        router = PolarisRouter(backend="ollama")

        # Manually set up memory and feedback manager
        router.memory = PolarisMemory(db_path=db_path, embedder=FakeEmbedder())
        router.feedback_manager = FeedbackManager(router.memory, embedder=FakeEmbedder())

        # Save a correction
        router.feedback_manager.save_correction("s1", "Wrong MoS2 answer", "MoS2는 1.8eV야")

        # Build system prompt
        prompt = router._build_system_prompt("MoS2 밴드갭 알려줘")
        assert "[주의: 과거 실수 기록]" in prompt

    @patch("polaris.router.PolarisRouter._init_ollama")
    @patch("polaris.router.PolarisRouter._load_tools")
    @patch("polaris.router.PolarisRouter._init_skills")
    @patch("polaris.router.PolarisRouter._init_feedback")
    @patch("polaris.router.PolarisRouter._init_memory")
    def test_correction_detection_in_route(self, mock_mem, mock_fb, mock_skills, mock_tools, mock_ollama, tmp_path):
        """Correction should be saved when detected during route()."""
        db_path = str(tmp_path / "router_test2.db")

        from polaris.router import PolarisRouter
        router = PolarisRouter(backend="ollama")

        router.memory = PolarisMemory(db_path=db_path, embedder=FakeEmbedder())
        router.feedback_manager = FeedbackManager(router.memory, embedder=FakeEmbedder())

        # Mock the actual LLM call
        router._route_ollama = MagicMock(
            return_value={"response": "알겠어!", "tools_used": []}
        )

        history = [
            {"role": "user", "content": "MoS2 밴드갭이 뭐야?"},
            {"role": "assistant", "content": "MoS2 밴드갭은 2.0eV야"},
        ]

        router.route(
            "틀렸어, 실제로는 1.8eV야",
            conversation_history=history,
            session_id="test_session",
        )

        # Verify correction was saved
        count = router.feedback_manager.get_correction_count()
        assert count == 1

    @patch("polaris.router.PolarisRouter._init_ollama")
    @patch("polaris.router.PolarisRouter._load_tools")
    @patch("polaris.router.PolarisRouter._init_skills")
    @patch("polaris.router.PolarisRouter._init_feedback")
    @patch("polaris.router.PolarisRouter._init_memory")
    def test_graceful_degradation(self, mock_mem, mock_fb, mock_skills, mock_tools, mock_ollama):
        """Router should work fine even without feedback manager."""
        from polaris.router import PolarisRouter
        router = PolarisRouter(backend="ollama")
        router.memory = None
        router.feedback_manager = None

        # Should not raise
        prompt = router._build_system_prompt("안녕?")
        assert "[주의" not in prompt
