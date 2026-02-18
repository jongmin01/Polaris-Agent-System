"""Tests for polaris.memory.vault_reader (VaultReader).

All tests use temporary directories and mock embedders.
No Ollama or external service needed.
"""

import json
import os
import time
import pytest

from polaris.memory.embedder import OllamaEmbedder
from polaris.memory.memory import PolarisMemory
from polaris.memory.vault_reader import VaultReader


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


def _create_note(vault_dir, rel_path, content, size_pad=True):
    """Helper to create a note file in the fake vault."""
    full_path = vault_dir / rel_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    # Pad content to meet min size (1KB) if needed
    if size_pad and len(content.encode("utf-8")) < 1024:
        content += "\n" + "x" * (1024 - len(content.encode("utf-8")))
    full_path.write_text(content, encoding="utf-8")
    return full_path


@pytest.fixture
def memory_db(tmp_path):
    """PolarisMemory with temp DB and fake embedder."""
    db_path = str(tmp_path / "test_vault.db")
    return PolarisMemory(db_path=db_path, embedder=FakeEmbedder())


@pytest.fixture
def vault_dir(tmp_path):
    """Create a fake vault directory structure."""
    vault = tmp_path / "vaults" / "My Second Brain"
    vault.mkdir(parents=True)
    return vault


@pytest.fixture
def reader(tmp_path, memory_db, vault_dir):
    """VaultReader with fake vault and memory."""
    index_path = str(tmp_path / "vault_index.json")
    return VaultReader(
        vault_path=str(tmp_path / "vaults"),
        memory=memory_db,
        index_path=index_path,
    )


@pytest.fixture
def reader_no_embed(tmp_path, vault_dir):
    """VaultReader without embedder."""
    db_path = str(tmp_path / "test_vault_no_embed.db")
    mem = PolarisMemory(db_path=db_path, embedder=NoEmbedder())
    index_path = str(tmp_path / "vault_index_ne.json")
    return VaultReader(
        vault_path=str(tmp_path / "vaults"),
        memory=mem,
        index_path=index_path,
    )


# ==================================================================
# TestScanVault
# ==================================================================

class TestScanVault:
    """Test vault directory scanning."""

    def test_scan_finds_md_files(self, reader, vault_dir):
        _create_note(vault_dir, "note1.md", "# Test Note\nSome content here.")
        _create_note(vault_dir, "subfolder/note2.md", "# Sub Note\nMore content.")

        results = reader.scan_vault()
        assert len(results) == 2
        titles = {r["title"] for r in results}
        assert "note1" in titles
        assert "note2" in titles

    def test_scan_skips_obsidian_dir(self, reader, vault_dir):
        _create_note(vault_dir, ".obsidian/config.md", "obsidian config")
        _create_note(vault_dir, "real_note.md", "# Real\nActual content.")

        results = reader.scan_vault()
        assert len(results) == 1
        assert results[0]["title"] == "real_note"

    def test_scan_skips_trash(self, reader, vault_dir):
        _create_note(vault_dir, ".trash/deleted.md", "deleted content")
        _create_note(vault_dir, "kept.md", "# Kept\nThis is kept.")

        results = reader.scan_vault()
        assert len(results) == 1

    def test_scan_skips_99_system(self, reader, vault_dir):
        _create_note(vault_dir, "99_System/internal.md", "system stuff")
        _create_note(vault_dir, "normal.md", "# Normal\nNormal content.")

        results = reader.scan_vault()
        assert len(results) == 1

    def test_scan_skips_small_files(self, reader, vault_dir):
        # Create small file (no padding)
        _create_note(vault_dir, "tiny.md", "# Tiny", size_pad=False)
        _create_note(vault_dir, "big.md", "# Big\nLots of content here.")

        results = reader.scan_vault()
        assert len(results) == 1
        assert results[0]["title"] == "big"

    def test_scan_empty_vault(self, reader):
        results = reader.scan_vault()
        assert results == []

    def test_scan_missing_vault(self, reader):
        results = reader.scan_vault(vault_name="NonExistent")
        assert results == []

    def test_scan_returns_metadata(self, reader, vault_dir):
        _create_note(vault_dir, "meta.md", "# Meta\nContent for metadata test.")

        results = reader.scan_vault()
        assert len(results) == 1
        assert "path" in results[0]
        assert "modified_time" in results[0]
        assert "size" in results[0]
        assert results[0]["size"] >= 1024


# ==================================================================
# TestParseNote
# ==================================================================

class TestParseNote:
    """Test markdown note parsing."""

    def test_parse_with_frontmatter(self, reader, vault_dir):
        content = (
            "---\n"
            "date: 2024-01-15\n"
            "tags: [physics, DFT]\n"
            "category: research\n"
            "---\n\n"
            "# Valley Polarization\n\n"
            "Valley polarization is a quantum property..."
        )
        path = _create_note(vault_dir, "valley.md", content)
        parsed = reader.parse_note(str(path))

        assert parsed["title"] == "valley"
        assert parsed["frontmatter"]["date"] == "2024-01-15"
        assert "physics" in parsed["frontmatter"]["tags"]
        assert "Valley polarization" in parsed["content"]

    def test_parse_without_frontmatter(self, reader, vault_dir):
        content = "# Simple Note\n\nJust some text content."
        path = _create_note(vault_dir, "simple.md", content)
        parsed = reader.parse_note(str(path))

        assert parsed["title"] == "simple"
        assert parsed["frontmatter"] == {}
        assert "Just some text" in parsed["content"]

    def test_parse_extracts_wikilinks(self, reader, vault_dir):
        content = "# Note\n\nSee [[Valley Polarization]] and [[MoS2|Molybdenite]]."
        path = _create_note(vault_dir, "links.md", content)
        parsed = reader.parse_note(str(path))

        assert "Valley Polarization" in parsed["links"]
        assert "MoS2" in parsed["links"]

    def test_parse_extracts_inline_tags(self, reader, vault_dir):
        content = "# Note\n\nThis is about #physics and #DFT calculations."
        path = _create_note(vault_dir, "tagged.md", content)
        parsed = reader.parse_note(str(path))

        assert "physics" in parsed["tags"]
        assert "DFT" in parsed["tags"]

    def test_parse_combines_fm_and_inline_tags(self, reader, vault_dir):
        content = (
            "---\n"
            "tags:\n"
            "  - research\n"
            "---\n\n"
            "# Note\n\n#physics content"
        )
        path = _create_note(vault_dir, "combined.md", content)
        parsed = reader.parse_note(str(path))

        assert "research" in parsed["tags"]
        assert "physics" in parsed["tags"]

    def test_parse_truncates_long_content(self, reader, vault_dir):
        content = "# Long\n\n" + "A" * 5000
        path = _create_note(vault_dir, "long.md", content)
        parsed = reader.parse_note(str(path))

        assert len(parsed["content"]) <= 2000

    def test_parse_strips_markdown(self, reader, vault_dir):
        content = "# Heading\n\n**bold** and *italic* and [[link|display]]"
        path = _create_note(vault_dir, "formatted.md", content)
        parsed = reader.parse_note(str(path))

        assert "**" not in parsed["content"]
        assert "[[" not in parsed["content"]
        assert "display" in parsed["content"]

    def test_parse_nonexistent_file(self, reader):
        parsed = reader.parse_note("/nonexistent/file.md")
        assert parsed["content"] == ""
        assert parsed["frontmatter"] == {}


# ==================================================================
# TestCategoryInference
# ==================================================================

class TestCategoryInference:
    """Test folder-path based category inference."""

    def test_physics_foundations(self, reader):
        cat = reader.infer_category(
            "/vault/30_Resources/Foundations/Physics/QM.md", {}
        )
        assert cat == "research"

    def test_areas(self, reader):
        cat = reader.infer_category("/vault/20_Areas/Teaching/TA.md", {})
        assert cat == "reference"

    def test_projects(self, reader):
        cat = reader.infer_category("/vault/10_Projects/MoS2/note.md", {})
        assert cat == "research"

    def test_frontmatter_overrides(self, reader):
        cat = reader.infer_category(
            "/vault/20_Areas/random.md", {"category": "research"}
        )
        assert cat == "research"

    def test_unknown_folder(self, reader):
        cat = reader.infer_category("/vault/misc/note.md", {})
        assert cat == "reference"


# ==================================================================
# TestIndexNote
# ==================================================================

class TestIndexNote:
    """Test single note indexing."""

    def test_index_saves_to_knowledge(self, reader, memory_db, vault_dir):
        content = "# Valley\n\nValley polarization in TMDCs..."
        path = _create_note(vault_dir, "30_Resources/Foundations/Physics/valley.md", content)
        parsed = reader.parse_note(str(path))
        row_id = reader.index_note(parsed)

        assert row_id > 0

        cursor = memory_db.conn.execute(
            "SELECT title, source, category FROM knowledge WHERE id = ?", (row_id,)
        )
        row = cursor.fetchone()
        assert row["title"] == "valley"
        assert row["source"] == "obsidian"
        assert row["category"] == "research"

    def test_index_without_memory(self, tmp_path):
        reader = VaultReader(memory=None)
        parsed = {"title": "test", "content": "content", "path": "/x", "tags": [], "frontmatter": {}}
        assert reader.index_note(parsed) == 0


# ==================================================================
# TestIndexVault
# ==================================================================

class TestIndexVault:
    """Test full vault indexing."""

    def test_index_all_notes(self, reader, vault_dir):
        _create_note(vault_dir, "note1.md", "# Note 1\nPhysics content.")
        _create_note(vault_dir, "note2.md", "# Note 2\nMath content.")

        stats = reader.index_vault()
        assert stats["total"] == 2
        assert stats["new"] == 2
        assert stats["errors"] == 0

    def test_incremental_skips_unchanged(self, reader, vault_dir):
        _create_note(vault_dir, "note1.md", "# Note 1\nPhysics content.")

        # First index
        stats1 = reader.index_vault()
        assert stats1["new"] == 1

        # Second index (no changes)
        stats2 = reader.index_vault()
        assert stats2["skipped"] == 1
        assert stats2["new"] == 0

    def test_force_reindexes_all(self, reader, vault_dir):
        _create_note(vault_dir, "note1.md", "# Note 1\nPhysics content.")

        reader.index_vault()
        stats = reader.index_vault(force=True)
        # When forced, it indexes again (new or updated)
        assert stats["skipped"] == 0
        assert stats["new"] + stats["updated"] >= 1

    def test_empty_vault_indexing(self, reader):
        stats = reader.index_vault()
        assert stats["total"] == 0

    def test_progress_callback(self, reader, vault_dir):
        _create_note(vault_dir, "note1.md", "# Note 1\nContent here.")

        calls = []
        def callback(current, total):
            calls.append((current, total))

        reader.index_vault(progress_callback=callback)
        assert len(calls) >= 1
        assert calls[-1][0] == calls[-1][1]  # last call should be total == total


# ==================================================================
# TestIndexFile
# ==================================================================

class TestIndexFile:
    """Test vault_index.json management."""

    def test_index_file_created(self, reader, vault_dir, tmp_path):
        _create_note(vault_dir, "note1.md", "# Note\nContent.")
        reader.index_vault()

        assert os.path.exists(reader.index_path)
        with open(reader.index_path) as f:
            data = json.load(f)
        assert len(data) == 1

    def test_index_file_tracks_time(self, reader, vault_dir):
        _create_note(vault_dir, "note1.md", "# Note\nContent.")
        reader.index_vault()

        with open(reader.index_path) as f:
            data = json.load(f)

        entry = list(data.values())[0]
        assert "indexed_time" in entry
        assert "title" in entry
        assert "knowledge_id" in entry

    def test_get_index_stats_empty(self, reader):
        stats = reader.get_index_stats()
        assert stats["indexed_notes"] == 0
        assert stats["last_indexed"] is None

    def test_get_index_stats_after_indexing(self, reader, vault_dir):
        _create_note(vault_dir, "note1.md", "# Note\nContent here.")
        reader.index_vault()

        stats = reader.get_index_stats()
        assert stats["indexed_notes"] == 1
        assert stats["last_indexed"] is not None


# ==================================================================
# TestSearchVaultKnowledge
# ==================================================================

class TestSearchVaultKnowledge:
    """Test vault-specific knowledge search."""

    def test_search_finds_indexed_notes(self, reader, vault_dir, memory_db):
        content = "# Valley Polarization\n\nValley polarization in MoS2 monolayer TMDC materials."
        _create_note(vault_dir, "valley.md", content)
        reader.index_vault()

        results = reader.search_vault_knowledge("valley polarization MoS2")
        assert len(results) >= 1
        assert results[0]["source"] == "obsidian"
        assert "valley" in results[0]["title"].lower() or "Valley" in results[0]["content"]

    def test_search_excludes_non_obsidian(self, reader, memory_db, vault_dir):
        # Add a non-obsidian knowledge entry
        memory_db.save_knowledge("research", "Manual Entry", "Some manual content", source="manual")

        # Add an obsidian entry
        _create_note(vault_dir, "obsidian_note.md", "# Obsidian\nSpecific vault content.")
        reader.index_vault()

        results = reader.search_vault_knowledge("content")
        sources = {r.get("source") for r in results}
        assert sources == {"obsidian"}

    def test_search_empty_vault(self, reader):
        results = reader.search_vault_knowledge("anything")
        assert results == []

    def test_search_keyword_fallback(self, reader_no_embed, vault_dir):
        _create_note(vault_dir, "physics_note.md", "# Physics\nQuantum mechanics fundamentals.")
        reader_no_embed.index_vault()

        results = reader_no_embed.search_vault_knowledge("Quantum")
        assert len(results) >= 1

    def test_search_no_memory(self, tmp_path):
        reader = VaultReader(memory=None)
        results = reader.search_vault_knowledge("test")
        assert results == []

    def test_search_respects_top_k(self, reader, vault_dir):
        for i in range(5):
            _create_note(vault_dir, f"note{i}.md", f"# Note {i}\nContent about physics topic {i}.")
        reader.index_vault()

        results = reader.search_vault_knowledge("physics", top_k=2)
        assert len(results) <= 2


# ==================================================================
# TestYamlParser
# ==================================================================

class TestYamlParser:
    """Test the simple YAML frontmatter parser."""

    def test_simple_key_value(self):
        result = VaultReader._parse_yaml_simple("key: value\ndate: 2024-01-15")
        assert result["key"] == "value"
        assert result["date"] == "2024-01-15"

    def test_inline_list(self):
        result = VaultReader._parse_yaml_simple("tags: [physics, DFT, VASP]")
        assert result["tags"] == ["physics", "DFT", "VASP"]

    def test_multiline_list(self):
        result = VaultReader._parse_yaml_simple("tags:\n  - physics\n  - DFT")
        assert result["tags"] == ["physics", "DFT"]

    def test_empty_value(self):
        result = VaultReader._parse_yaml_simple("key:")
        assert result["key"] == ""

    def test_quoted_values(self):
        result = VaultReader._parse_yaml_simple("title: 'My Title'\nauthor: \"John\"")
        assert result["title"] == "My Title"
        assert result["author"] == "John"


# ==================================================================
# TestRouterIntegration
# ==================================================================

class TestRouterIntegration:
    """Test VaultReader integration with PolarisRouter."""

    def test_vault_knowledge_in_prompt(self, tmp_path):
        from unittest.mock import patch, MagicMock

        db_path = str(tmp_path / "router_vault.db")
        vault_dir = tmp_path / "vaults" / "My Second Brain"
        vault_dir.mkdir(parents=True)
        _create_note(vault_dir, "valley.md", "# Valley\nValley polarization in MoS2...", size_pad=True)

        with patch("polaris.router.PolarisRouter._init_ollama"), \
             patch("polaris.router.PolarisRouter._load_tools"), \
             patch("polaris.router.PolarisRouter._init_skills"), \
             patch("polaris.router.PolarisRouter._init_feedback"), \
             patch("polaris.router.PolarisRouter._init_memory"), \
             patch("polaris.router.PolarisRouter._init_fact_extractor"), \
             patch("polaris.router.PolarisRouter._init_vault_reader"):

            from polaris.router import PolarisRouter
            router = PolarisRouter(backend="ollama")

            router.memory = PolarisMemory(db_path=db_path, embedder=FakeEmbedder())
            router.feedback_manager = None
            router.fact_extractor = None

            index_path = str(tmp_path / "vi.json")
            router.vault_reader = VaultReader(
                vault_path=str(tmp_path / "vaults"),
                memory=router.memory,
                index_path=index_path,
            )
            router.vault_reader.index_vault()

            prompt = router._build_system_prompt("valley polarization이 뭐야?")
            assert "[참고: 내 노트에서]" in prompt
            assert "valley" in prompt.lower() or "Valley" in prompt

    def test_graceful_without_vault_reader(self, tmp_path):
        from unittest.mock import patch

        with patch("polaris.router.PolarisRouter._init_ollama"), \
             patch("polaris.router.PolarisRouter._load_tools"), \
             patch("polaris.router.PolarisRouter._init_skills"), \
             patch("polaris.router.PolarisRouter._init_feedback"), \
             patch("polaris.router.PolarisRouter._init_memory"), \
             patch("polaris.router.PolarisRouter._init_fact_extractor"), \
             patch("polaris.router.PolarisRouter._init_vault_reader"):

            from polaris.router import PolarisRouter
            router = PolarisRouter(backend="ollama")
            router.memory = None
            router.feedback_manager = None
            router.fact_extractor = None
            router.vault_reader = None

            prompt = router._build_system_prompt("안녕?")
            assert "[참고: 내 노트에서]" not in prompt
