"""Tests for polaris.memory (PolarisMemory + OllamaEmbedder + ObsidianWriter).

All tests use a temporary SQLite DB, temp directories, and mock embedders
so they run without Ollama or any external service.
"""

import json
import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock

from polaris.memory.embedder import OllamaEmbedder
from polaris.memory.memory import PolarisMemory
from polaris.memory.obsidian_writer import ObsidianWriter


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

class FakeEmbedder:
    """Deterministic embedder for tests. Returns the hash-based vector."""

    available = True

    def embed(self, text):
        # Simple deterministic vector based on text length and first char
        seed = len(text) + ord(text[0]) if text else 0
        return [float(seed % (i + 1)) / (i + 1) for i in range(8)]

    def batch_embed(self, texts):
        return [self.embed(t) for t in texts]

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
def tmp_db(tmp_path):
    """Return a temp DB path."""
    return str(tmp_path / "test_memory.db")


@pytest.fixture
def memory(tmp_db):
    """PolarisMemory with a fake embedder."""
    return PolarisMemory(db_path=tmp_db, embedder=FakeEmbedder())


@pytest.fixture
def memory_no_embed(tmp_db):
    """PolarisMemory with no embedding support."""
    return PolarisMemory(db_path=tmp_db, embedder=NoEmbedder())


# ================================================================
# Conversation tests
# ================================================================

class TestConversations:
    def test_save_and_retrieve(self, memory):
        memory.save_conversation("s1", "user", "Hello Polaris")
        memory.save_conversation("s1", "assistant", "Hi! How can I help?")
        memory.save_conversation("s1", "user", "Search MoS2 papers")

        rows = memory.get_recent_conversations("s1", limit=10)
        assert len(rows) == 3
        assert rows[0]["role"] == "user"
        assert rows[0]["content"] == "Hello Polaris"
        assert rows[2]["content"] == "Search MoS2 papers"

    def test_session_isolation(self, memory):
        memory.save_conversation("s1", "user", "Session 1 message")
        memory.save_conversation("s2", "user", "Session 2 message")

        rows_s1 = memory.get_recent_conversations("s1")
        rows_s2 = memory.get_recent_conversations("s2")
        assert len(rows_s1) == 1
        assert len(rows_s2) == 1
        assert rows_s1[0]["content"] == "Session 1 message"

    def test_limit_respected(self, memory):
        for i in range(10):
            memory.save_conversation("s1", "user", f"Message {i}")

        rows = memory.get_recent_conversations("s1", limit=3)
        assert len(rows) == 3
        # Should be the 3 most recent, oldest first
        assert rows[0]["content"] == "Message 7"
        assert rows[2]["content"] == "Message 9"

    def test_save_returns_row_id(self, memory):
        rid1 = memory.save_conversation("s1", "user", "First")
        rid2 = memory.save_conversation("s1", "user", "Second")
        assert rid1 == 1
        assert rid2 == 2


# ================================================================
# Knowledge tests
# ================================================================

class TestKnowledge:
    def test_save_knowledge(self, memory):
        rid = memory.save_knowledge(
            category="research",
            title="MoS2 Band Structure",
            content="DFT calculations show MoS2 has a direct bandgap of 1.8 eV.",
            source="arxiv",
            tags=["DFT", "MoS2"],
        )
        assert rid >= 1

    def test_semantic_search(self, memory):
        memory.save_knowledge("research", "MoS2 bandgap", "MoS2 has 1.8 eV bandgap", source="arxiv")
        memory.save_knowledge("daily", "Gym schedule", "Workout at 6pm every Tuesday", source="manual")
        memory.save_knowledge("research", "Graphene properties", "Graphene is a 2D material", source="arxiv")

        results = memory.search_memory("MoS2 research", top_k=2)
        assert len(results) <= 2
        # All results should have a score
        for r in results:
            assert "score" in r

    def test_search_returns_knowledge_and_conversations(self, memory):
        memory.save_conversation("s1", "user", "Tell me about DFT calculations")
        memory.save_knowledge("research", "DFT intro", "Density functional theory basics", source="manual")

        results = memory.search_memory("DFT", top_k=5)
        sources = {r["source_table"] for r in results}
        assert "conversation" in sources
        assert "knowledge" in sources


# ================================================================
# Keyword fallback search tests
# ================================================================

class TestKeywordFallback:
    def test_keyword_search_without_embeddings(self, memory_no_embed):
        memory_no_embed.save_conversation("s1", "user", "DFT calculation for MoS2")
        memory_no_embed.save_knowledge("research", "VASP tutorial", "How to run VASP DFT", source="manual")

        results = memory_no_embed.search_memory("DFT", top_k=5)
        assert len(results) >= 1
        # Should find at least the conversation with DFT
        contents = [r["content"] for r in results]
        assert any("DFT" in c for c in contents)

    def test_keyword_search_no_results(self, memory_no_embed):
        memory_no_embed.save_conversation("s1", "user", "Hello world")
        results = memory_no_embed.search_memory("quantum_xyz_nonexistent", top_k=5)
        assert len(results) == 0


# ================================================================
# Feedback tests
# ================================================================

class TestFeedback:
    def test_save_feedback(self, memory):
        rid = memory.save_feedback("classified email as FYI", "should be ACTION")
        assert rid >= 1

    def test_get_pending_feedback(self, memory):
        memory.save_feedback("action1", "correction1")
        memory.save_feedback("action2", "correction2")

        pending = memory.get_pending_feedback()
        assert len(pending) == 2
        assert pending[0]["original_action"] == "action1"
        assert pending[0]["applied"] == 0

    def test_feedback_applied_flag(self, memory):
        memory.save_feedback("action1", "correction1")
        # Mark as applied
        memory.conn.execute("UPDATE feedback SET applied = 1 WHERE id = 1")
        memory.conn.commit()

        pending = memory.get_pending_feedback()
        assert len(pending) == 0


# ================================================================
# Migration tests
# ================================================================

class TestMigration:
    def test_migrate_corrections(self, memory, tmp_path):
        # Create a mock corrections.jsonl
        jsonl_path = str(tmp_path / "corrections.jsonl")
        entries = [
            {"timestamp": "2026-01-15 10:00:00", "hash": "a3f2", "file_path": "test.md",
             "original_label": "FYI", "corrected_label": "ACTION", "subject": "TA question"},
            {"timestamp": "2026-01-16 11:00:00", "hash": "b4c1", "file_path": "test2.md",
             "original_label": "ACTION", "corrected_label": "FYI", "subject": "Newsletter"},
        ]
        with open(jsonl_path, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

        count = memory.migrate_corrections(jsonl_path)
        assert count == 2

        # Verify data in feedback table
        cursor = memory.conn.execute("SELECT * FROM feedback ORDER BY id ASC")
        rows = [dict(r) for r in cursor.fetchall()]
        assert len(rows) == 2
        assert "a3f2" in rows[0]["original_action"]
        assert rows[0]["correction"] == "ACTION"
        assert rows[0]["applied"] == 1

    def test_migrate_missing_file(self, memory, tmp_path):
        count = memory.migrate_corrections(str(tmp_path / "nonexistent.jsonl"))
        assert count == 0

    def test_migrate_malformed_lines(self, memory, tmp_path):
        jsonl_path = str(tmp_path / "bad.jsonl")
        with open(jsonl_path, "w") as f:
            f.write('{"timestamp":"2026-01-15","hash":"ok","original_label":"FYI","corrected_label":"ACTION","subject":"Test"}\n')
            f.write("not valid json\n")
            f.write("\n")  # empty line

        count = memory.migrate_corrections(jsonl_path)
        assert count == 1  # only the valid line


# ================================================================
# Embedder unit tests
# ================================================================

class TestEmbedder:
    def test_to_from_bytes_roundtrip(self):
        vec = [1.0, 2.5, -3.14, 0.0, 99.99]
        blob = OllamaEmbedder.to_bytes(vec)
        restored = OllamaEmbedder.from_bytes(blob)
        assert len(restored) == len(vec)
        for a, b in zip(vec, restored):
            assert abs(a - b) < 1e-5

    def test_cosine_similarity_identical(self):
        vec = [1.0, 2.0, 3.0]
        sim = OllamaEmbedder.cosine_similarity(vec, vec)
        assert abs(sim - 1.0) < 1e-6

    def test_cosine_similarity_orthogonal(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        sim = OllamaEmbedder.cosine_similarity(a, b)
        assert abs(sim) < 1e-6

    def test_cosine_similarity_zero_vector(self):
        a = [0.0, 0.0]
        b = [1.0, 2.0]
        sim = OllamaEmbedder.cosine_similarity(a, b)
        assert sim == 0.0

    def test_cosine_similarity_different_lengths(self):
        a = [1.0, 2.0]
        b = [1.0, 2.0, 3.0]
        sim = OllamaEmbedder.cosine_similarity(a, b)
        assert sim == 0.0

    @patch("polaris.memory.embedder.requests.post")
    def test_embed_ollama_unavailable(self, mock_post):
        mock_post.side_effect = Exception("Connection refused")
        embedder = OllamaEmbedder()
        assert embedder.available is False
        assert embedder.embed("test") is None


# ================================================================
# get_relevant_context tests
# ================================================================

class TestRelevantContext:
    def test_returns_formatted_string(self, memory):
        memory.save_conversation("s1", "user", "MoS2 DFT calculation results")
        memory.save_knowledge("research", "MoS2", "MoS2 bandgap is 1.8 eV", source="arxiv")

        ctx = memory.get_relevant_context("MoS2", top_k=3)
        assert isinstance(ctx, str)
        assert len(ctx) > 0

    def test_empty_when_no_data(self, memory):
        ctx = memory.get_relevant_context("anything", top_k=3)
        assert ctx == ""


# ================================================================
# ObsidianWriter tests
# ================================================================

class TestObsidianWriter:
    @pytest.fixture
    def vault(self, tmp_path):
        """Return an ObsidianWriter pointed at a temp vault directory."""
        return ObsidianWriter(vault_path=str(tmp_path))

    def test_save_note(self, vault, tmp_path):
        path = vault.save_note(
            title="Test Note",
            content="Hello from Polaris",
            folder="Polaris/Research",
            tags=["test", "polaris"],
            source="polaris",
        )
        assert os.path.exists(path)
        text = open(path, encoding="utf-8").read()
        assert "# Test Note" in text
        assert "Hello from Polaris" in text
        assert "source: polaris" in text
        assert "  - test" in text

    def test_save_note_creates_subdirectories(self, vault, tmp_path):
        path = vault.save_note(
            title="Deep Note",
            content="Deep content",
            folder="Polaris/A/B/C",
        )
        assert os.path.exists(path)
        assert "Polaris/A/B/C" in path

    def test_save_paper_note(self, vault, tmp_path):
        paper_info = {
            "title": "MoS2 Band Structure Study",
            "authors": "Kim, Lee",
            "abstract": "We study MoS2 bandgap using DFT.",
            "arxiv_id": "2401.12345",
            "year": 2024,
        }
        path = vault.save_paper_note(paper_info, "Interesting paper on MoS2")
        assert os.path.exists(path)
        text = open(path, encoding="utf-8").read()
        assert "MoS2 Band Structure Study" in text
        assert "Kim, Lee" in text
        assert "2401.12345" in text
        assert "Interesting paper on MoS2" in text
        assert "source: arxiv" in text

    def test_save_daily_log(self, vault, tmp_path):
        path = vault.save_daily_log(
            date="2026-02-08",
            entries=["Searched MoS2 papers", "Sent email to advisor"],
        )
        assert os.path.exists(path)
        text = open(path, encoding="utf-8").read()
        assert "Daily Log 2026-02-08" in text
        assert "- Searched MoS2 papers" in text
        assert "- Sent email to advisor" in text

    def test_save_daily_log_default_date(self, vault, tmp_path):
        path = vault.save_daily_log(entries=["Test entry"])
        assert os.path.exists(path)
        assert "Daily Log" in open(path, encoding="utf-8").read()

    def test_filename_sanitisation(self, vault, tmp_path):
        path = vault.save_note(
            title='Bad/File:Name*"Test"',
            content="Safe content",
        )
        assert os.path.exists(path)
        # No illegal characters in path basename
        basename = os.path.basename(path)
        for ch in ['/', ':', '*', '"', '<', '>', '|']:
            assert ch not in basename


# ================================================================
# master_prompt.md tests
# ================================================================

class TestMasterPrompt:
    @pytest.fixture
    def vault_with_mp(self, tmp_path):
        """Create a vault with a master_prompt.md file."""
        mp_content = (
            "## 00_CORE_IDENTITY\n"
            "Name: Polaris\n"
            "Role: Research assistant\n\n"
            "## 01_RESEARCH_CONTEXT\n"
            "Field: Condensed matter physics\n"
            "Focus: 2D materials\n\n"
            "## 99_CURRENT_CONTEXT\n"
            "Last session: 2026-02-07\n"
            "Working on MoS2 calculations\n"
        )
        mp_path = tmp_path / "master_prompt.md"
        mp_path.write_text(mp_content, encoding="utf-8")
        return ObsidianWriter(vault_path=str(tmp_path))

    def test_read_master_prompt(self, vault_with_mp, tmp_path):
        content = vault_with_mp.read_master_prompt()
        assert "00_CORE_IDENTITY" in content
        assert "01_RESEARCH_CONTEXT" in content
        assert "99_CURRENT_CONTEXT" in content

    def test_read_master_prompt_missing(self, tmp_path):
        writer = ObsidianWriter(vault_path=str(tmp_path / "nonexistent"))
        # Pass an explicit nonexistent path to bypass fallback to data/master_prompt.md
        result = writer.read_master_prompt(path=str(tmp_path / "nonexistent" / "master_prompt.md"))
        assert result == ""

    def test_read_section_core(self, vault_with_mp):
        section = vault_with_mp.read_master_prompt_section("00_CORE")
        assert "Name: Polaris" in section
        assert "Role: Research assistant" in section
        # Should NOT include other sections
        assert "99_CURRENT_CONTEXT" not in section

    def test_read_section_research(self, vault_with_mp):
        section = vault_with_mp.read_master_prompt_section("01_RESEARCH")
        assert "Condensed matter physics" in section
        assert "00_CORE" not in section

    def test_read_section_nonexistent(self, vault_with_mp):
        section = vault_with_mp.read_master_prompt_section("50_NONEXISTENT")
        assert section == ""

    def test_update_current_context(self, vault_with_mp, tmp_path):
        success = vault_with_mp.update_master_prompt("New context: testing Phase 2")
        assert success is True

        # Re-read and verify
        content = vault_with_mp.read_master_prompt()
        assert "New context: testing Phase 2" in content
        # Other sections must be preserved exactly
        assert "## 00_CORE_IDENTITY" in content
        assert "Name: Polaris" in content
        assert "## 01_RESEARCH_CONTEXT" in content
        assert "Condensed matter physics" in content
        # Old context replaced
        assert "Working on MoS2 calculations" not in content

    def test_update_preserves_all_sections(self, vault_with_mp, tmp_path):
        vault_with_mp.update_master_prompt("Updated context")

        content = vault_with_mp.read_master_prompt()
        # Count section headers — should still be exactly 3
        headers = [line for line in content.split("\n") if line.startswith("## ")]
        assert len(headers) == 3

    def test_update_creates_section_if_missing(self, tmp_path):
        # Create a master_prompt without 99_CURRENT_CONTEXT
        mp_content = (
            "## 00_CORE_IDENTITY\n"
            "Name: Polaris\n"
        )
        mp_path = tmp_path / "master_prompt.md"
        mp_path.write_text(mp_content, encoding="utf-8")

        writer = ObsidianWriter(vault_path=str(tmp_path))
        success = writer.update_master_prompt("Brand new context")
        assert success is True

        content = mp_path.read_text(encoding="utf-8")
        assert "## 99_CURRENT_CONTEXT" in content
        assert "Brand new context" in content
        assert "## 00_CORE_IDENTITY" in content


# ================================================================
# batch_embed tests
# ================================================================

class TestBatchEmbed:
    @patch("polaris.memory.embedder.requests.post")
    def test_batch_embed_calls_embed_for_each(self, mock_post):
        # Make availability check fail so available=False
        mock_post.side_effect = Exception("Connection refused")
        embedder = OllamaEmbedder()
        results = embedder.batch_embed(["text1", "text2", "text3"])
        assert len(results) == 3
        # All None because embedder is unavailable
        assert all(r is None for r in results)

    def test_batch_embed_with_fake_embedder(self):
        embedder = FakeEmbedder()
        results = embedder.batch_embed(["hello", "world"])
        assert len(results) == 2
        assert results[0] is not None
        assert results[1] is not None
        # Different texts should produce different vectors
        assert results[0] != results[1]


# ================================================================
# User profile tests (PolarisMemory + ObsidianWriter integration)
# ================================================================

class TestUserProfile:
    @pytest.fixture
    def memory_with_vault(self, tmp_db, tmp_path):
        """PolarisMemory + vault with master_prompt.md."""
        mp_content = (
            "## 00_CORE_IDENTITY\n"
            "Name: Polaris\n"
            "User: 종민\n\n"
            "## 01_RESEARCH\n"
            "Field: Physics\n"
        )
        mp_path = tmp_path / "master_prompt.md"
        mp_path.write_text(mp_content, encoding="utf-8")

        mem = PolarisMemory(db_path=tmp_db, embedder=FakeEmbedder())
        return mem, str(mp_path)

    def test_get_user_profile(self, memory_with_vault):
        mem, mp_path = memory_with_vault
        profile = mem.get_user_profile(master_prompt_path=mp_path)
        assert "00_CORE_IDENTITY" in profile
        assert "Name: Polaris" in profile

    def test_get_user_profile_missing_file(self, memory):
        profile = memory.get_user_profile(master_prompt_path="/nonexistent/path.md")
        assert profile == ""

    def test_get_user_profile_sections_default(self, memory_with_vault):
        mem, mp_path = memory_with_vault
        result = mem.get_user_profile_sections(master_prompt_path=mp_path)
        # Default extracts 00_CORE
        assert "Name: Polaris" in result
        assert "User: 종민" in result

    def test_get_user_profile_sections_custom(self, memory_with_vault):
        mem, mp_path = memory_with_vault
        result = mem.get_user_profile_sections(
            sections=["01_RESEARCH"], master_prompt_path=mp_path
        )
        assert "Field: Physics" in result
        assert "00_CORE" not in result
