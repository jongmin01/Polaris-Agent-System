"""Tests for polaris.memory.fact_extractor (FactExtractor).

All tests use temporary SQLite DB and temp directories.
No LLM or external service needed.
"""

import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock

from polaris.memory.embedder import OllamaEmbedder
from polaris.memory.memory import PolarisMemory
from polaris.memory.obsidian_writer import ObsidianWriter
from polaris.memory.fact_extractor import FactExtractor


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


@pytest.fixture
def memory_db(tmp_path):
    """Create a PolarisMemory with temp DB."""
    db_path = str(tmp_path / "test_facts.db")
    return PolarisMemory(db_path=db_path, embedder=FakeEmbedder())


@pytest.fixture
def obsidian_writer(tmp_path):
    """Create an ObsidianWriter with temp vault."""
    vault = str(tmp_path / "vault")
    os.makedirs(vault, exist_ok=True)
    return ObsidianWriter(vault_path=vault)


@pytest.fixture
def extractor(memory_db, obsidian_writer):
    """Create a FactExtractor with memory and obsidian writer."""
    return FactExtractor(memory=memory_db, obsidian_writer=obsidian_writer)


@pytest.fixture
def extractor_no_deps():
    """Create a FactExtractor without memory or writer."""
    return FactExtractor()


# ==================================================================
# TestShouldExtract
# ==================================================================

class TestShouldExtract:
    """Test message pre-filtering."""

    def test_short_message_rejected(self):
        assert FactExtractor.should_extract("ㅋㅋ") is False

    def test_greeting_rejected(self):
        assert FactExtractor.should_extract("안녕") is False

    def test_thanks_rejected(self):
        assert FactExtractor.should_extract("고마워!") is False

    def test_goodnight_rejected(self):
        assert FactExtractor.should_extract("잘 자!") is False

    def test_english_greeting_rejected(self):
        assert FactExtractor.should_extract("hello!") is False

    def test_ok_rejected(self):
        assert FactExtractor.should_extract("ㅇㅋ") is False

    def test_empty_rejected(self):
        assert FactExtractor.should_extract("") is False

    def test_none_rejected(self):
        assert FactExtractor.should_extract(None) is False

    def test_meaningful_message_accepted(self):
        assert FactExtractor.should_extract("나 ONETEP도 쓰게 됐어") is True

    def test_long_message_accepted(self):
        assert FactExtractor.should_extract("오늘 연구에서 재미있는 결과가 나왔어") is True


# ==================================================================
# TestExtractFacts — Pattern Matching
# ==================================================================

class TestExtractFacts:
    """Test regex-based fact extraction patterns."""

    def test_new_tool(self, extractor):
        facts = extractor.extract_facts("나 ONETEP도 쓰게 됐어")
        assert len(facts) >= 1
        assert facts[0]["category"] == "research"
        assert "ONETEP" in facts[0]["title"]

    def test_started_learning(self, extractor):
        facts = extractor.extract_facts("나 Julia 배우고 있어")
        assert len(facts) >= 1
        assert facts[0]["category"] == "research"
        assert "Julia" in facts[0]["title"]

    def test_passed_exam(self, extractor):
        facts = extractor.extract_facts("Applied Materials 합격했어")
        assert len(facts) >= 1
        assert facts[0]["category"] == "career"
        assert "Applied Materials" in facts[0]["title"]
        assert "합격" in facts[0]["title"]

    def test_failed(self, extractor):
        facts = extractor.extract_facts("Google 인턴십에 불합격했어")
        assert len(facts) >= 1
        assert any(f["category"] == "career" for f in facts)

    def test_cat_info(self, extractor):
        facts = extractor.extract_facts("시루가 4.5kg이야")
        assert len(facts) >= 1
        assert facts[0]["category"] == "life"
        assert "시루" in facts[0]["title"]

    def test_cat_info_seolgi(self, extractor):
        facts = extractor.extract_facts("설기는 요즘 많이 자")
        assert len(facts) >= 1
        assert "설기" in facts[0]["title"]

    def test_semester_info(self, extractor):
        facts = extractor.extract_facts("이번 학기 양자역학 TA 맡았어")
        assert len(facts) >= 1
        assert facts[0]["category"] == "academic"
        assert "이번 학기" in facts[0]["title"]

    def test_research_finding(self, extractor):
        facts = extractor.extract_facts("연구에서 새로운 상전이를 발견했어")
        assert len(facts) >= 1
        assert facts[0]["category"] == "research"

    def test_vehicle_mileage(self, extractor):
        facts = extractor.extract_facts("엔진오일 70000km에 교체했어")
        assert len(facts) >= 1
        assert facts[0]["category"] == "vehicle"

    def test_vehicle_maintenance(self, extractor):
        facts = extractor.extract_facts("타이어 교체했어")
        assert len(facts) >= 1
        assert facts[0]["category"] == "vehicle"

    def test_purchase(self, extractor):
        facts = extractor.extract_facts("나 맥북 프로 샀어")
        assert len(facts) >= 1
        assert facts[0]["category"] == "life"
        assert "구매" in facts[0]["title"] or "변경" in facts[0]["title"]

    def test_internship(self, extractor):
        facts = extractor.extract_facts("인턴십 시작했어")
        assert len(facts) >= 1
        assert facts[0]["category"] == "career"

    def test_installation(self, extractor):
        facts = extractor.extract_facts("Quantum ESPRESSO 설치했어")
        assert len(facts) >= 1
        assert facts[0]["category"] == "research"
        assert "Quantum ESPRESSO" in facts[0]["title"]

    def test_simulation_result(self, extractor):
        facts = extractor.extract_facts("VASP 결과 수렴했어")
        assert len(facts) >= 1
        assert facts[0]["category"] == "research"

    def test_no_match_greeting(self, extractor):
        facts = extractor.extract_facts("안녕? 오늘 뭐 했어?")
        assert len(facts) == 0

    def test_no_match_question(self, extractor):
        facts = extractor.extract_facts("MoS2 밴드갭이 얼마야?")
        assert len(facts) == 0

    def test_dedup_within_extraction(self, extractor):
        """Same pattern shouldn't produce duplicate titles."""
        facts = extractor.extract_facts("나 ONETEP도 쓰게 됐어 그리고 나 ONETEP도 써")
        titles = [f["title"] for f in facts]
        # No exact duplicate titles
        assert len(titles) == len(set(titles))

    def test_band_gap_info(self, extractor):
        facts = extractor.extract_facts("밴드갭이 1.8eV야")
        assert len(facts) >= 1
        assert facts[0]["category"] == "research"


# ==================================================================
# TestCategorizeFact
# ==================================================================

class TestCategorizeFact:
    """Test fact → master_prompt section mapping."""

    def test_research_maps_to_02(self):
        assert FactExtractor.categorize_fact({"category": "research"}) == "02_RESEARCH"

    def test_career_maps_to_99(self):
        assert FactExtractor.categorize_fact({"category": "career"}) == "99_CURRENT_CONTEXT"

    def test_life_maps_to_99(self):
        assert FactExtractor.categorize_fact({"category": "life"}) == "99_CURRENT_CONTEXT"

    def test_unknown_maps_to_99(self):
        assert FactExtractor.categorize_fact({"category": "unknown"}) == "99_CURRENT_CONTEXT"

    def test_dev_maps_to_02(self):
        assert FactExtractor.categorize_fact({"category": "dev"}) == "02_DEV"


# ==================================================================
# TestSaveAndUpdate
# ==================================================================

class TestSaveAndUpdate:
    """Test knowledge saving and master_prompt update."""

    def test_save_to_knowledge_table(self, extractor, memory_db):
        facts = [
            {"category": "research", "title": "ONETEP 사용", "content": "나 ONETEP도 쓰게 됐어", "source": "conversation"},
        ]
        saved = extractor.save_and_update(facts)
        assert saved == 1

        # Verify in knowledge table
        cursor = memory_db.conn.execute(
            "SELECT title, category FROM knowledge WHERE title = ?", ("ONETEP 사용",)
        )
        row = cursor.fetchone()
        assert row is not None
        assert row["category"] == "research"

    def test_save_multiple_facts(self, extractor, memory_db):
        facts = [
            {"category": "research", "title": "Fact 1", "content": "Content 1", "source": "conversation"},
            {"category": "life", "title": "Fact 2", "content": "Content 2", "source": "conversation"},
        ]
        saved = extractor.save_and_update(facts)
        assert saved == 2

    def test_save_empty_list(self, extractor):
        saved = extractor.save_and_update([])
        assert saved == 0

    def test_no_memory_no_crash(self, extractor_no_deps):
        facts = [{"category": "research", "title": "Test", "content": "Test", "source": "conversation"}]
        saved = extractor_no_deps.save_and_update(facts)
        assert saved == 0  # nothing saved, but no crash

    def test_high_importance_updates_master_prompt(self, extractor, obsidian_writer, tmp_path):
        """Career/research facts should update 99_CURRENT_CONTEXT."""
        # Create a master_prompt.md with an existing section
        mp_path = str(tmp_path / "vault" / "master_prompt.md")
        with open(mp_path, "w") as f:
            f.write("## 00_CORE\nSome core content\n\n## 99_CURRENT_CONTEXT\nExisting context\n")

        # Point writer to the file
        with patch.object(obsidian_writer, '_resolve_master_prompt_path', return_value=mp_path):
            facts = [
                {"category": "career", "title": "Applied Materials 합격", "content": "Applied Materials 합격했어", "source": "conversation"},
            ]
            extractor.save_and_update(facts)

            # Read back
            content = open(mp_path).read()
            assert "Applied Materials 합격" in content

    def test_low_importance_skips_master_prompt(self, extractor, obsidian_writer, tmp_path):
        """Life category facts should NOT update master_prompt."""
        mp_path = str(tmp_path / "vault" / "master_prompt.md")
        with open(mp_path, "w") as f:
            f.write("## 99_CURRENT_CONTEXT\nOriginal\n")

        with patch.object(obsidian_writer, '_resolve_master_prompt_path', return_value=mp_path):
            facts = [
                {"category": "life", "title": "맥북 구매", "content": "나 맥북 샀어", "source": "conversation"},
            ]
            extractor.save_and_update(facts)

            content = open(mp_path).read()
            # Life facts are NOT high importance, so master_prompt should be unchanged
            assert "맥북 구매" not in content

    def test_dedup_in_master_prompt(self, extractor, obsidian_writer, tmp_path):
        """Same fact title should not be duplicated in 99_CURRENT_CONTEXT."""
        mp_path = str(tmp_path / "vault" / "master_prompt.md")
        with open(mp_path, "w") as f:
            f.write("## 99_CURRENT_CONTEXT\nApplied Materials 합격 already noted\n")

        with patch.object(obsidian_writer, '_resolve_master_prompt_path', return_value=mp_path):
            facts = [
                {"category": "career", "title": "Applied Materials 합격", "content": "합격했어!", "source": "conversation"},
            ]
            extractor.save_and_update(facts)

            content = open(mp_path).read()
            # Should not have a new entry since the title is already present
            assert content.count("Applied Materials 합격") == 1


# ==================================================================
# TestRouterIntegration
# ==================================================================

class TestRouterIntegration:
    """Test FactExtractor integration with PolarisRouter."""

    @patch("polaris.router.PolarisRouter._init_ollama")
    @patch("polaris.router.PolarisRouter._load_tools")
    @patch("polaris.router.PolarisRouter._init_skills")
    @patch("polaris.router.PolarisRouter._init_feedback")
    @patch("polaris.router.PolarisRouter._init_memory")
    @patch("polaris.router.PolarisRouter._init_fact_extractor")
    def test_fact_extraction_in_route(self, mock_fe, mock_mem, mock_fb, mock_skills, mock_tools, mock_ollama, tmp_path):
        """Facts should be extracted and saved during route()."""
        db_path = str(tmp_path / "router_fact_test.db")

        from polaris.router import PolarisRouter
        router = PolarisRouter(backend="ollama")

        router.memory = PolarisMemory(db_path=db_path, embedder=FakeEmbedder())
        router.fact_extractor = FactExtractor(memory=router.memory)
        router.feedback_manager = None

        # Mock the LLM call
        router._route_ollama = MagicMock(
            return_value={"response": "오 ONETEP 쓰기 시작했구나!", "tools_used": []}
        )

        router.route(
            "나 ONETEP도 쓰게 됐어",
            conversation_history=[],
            session_id="test_session",
        )

        # Verify fact was saved to knowledge table
        cursor = router.memory.conn.execute(
            "SELECT title FROM knowledge WHERE title LIKE '%ONETEP%'"
        )
        rows = cursor.fetchall()
        assert len(rows) >= 1

    @patch("polaris.router.PolarisRouter._init_ollama")
    @patch("polaris.router.PolarisRouter._load_tools")
    @patch("polaris.router.PolarisRouter._init_skills")
    @patch("polaris.router.PolarisRouter._init_feedback")
    @patch("polaris.router.PolarisRouter._init_memory")
    @patch("polaris.router.PolarisRouter._init_fact_extractor")
    def test_no_extraction_for_greeting(self, mock_fe, mock_mem, mock_fb, mock_skills, mock_tools, mock_ollama, tmp_path):
        """Greetings should not trigger fact extraction."""
        db_path = str(tmp_path / "router_fact_test2.db")

        from polaris.router import PolarisRouter
        router = PolarisRouter(backend="ollama")

        router.memory = PolarisMemory(db_path=db_path, embedder=FakeEmbedder())
        router.fact_extractor = FactExtractor(memory=router.memory)
        router.feedback_manager = None

        router._route_ollama = MagicMock(
            return_value={"response": "안녕!", "tools_used": []}
        )

        router.route(
            "안녕? 잘 지내?",
            conversation_history=[],
            session_id="test_session",
        )

        # No knowledge should be saved
        cursor = router.memory.conn.execute("SELECT COUNT(*) FROM knowledge")
        assert cursor.fetchone()[0] == 0

    @patch("polaris.router.PolarisRouter._init_ollama")
    @patch("polaris.router.PolarisRouter._load_tools")
    @patch("polaris.router.PolarisRouter._init_skills")
    @patch("polaris.router.PolarisRouter._init_feedback")
    @patch("polaris.router.PolarisRouter._init_memory")
    @patch("polaris.router.PolarisRouter._init_fact_extractor")
    def test_graceful_without_extractor(self, mock_fe, mock_mem, mock_fb, mock_skills, mock_tools, mock_ollama):
        """Router should work fine without fact extractor."""
        from polaris.router import PolarisRouter
        router = PolarisRouter(backend="ollama")
        router.memory = None
        router.fact_extractor = None
        router.feedback_manager = None

        router._route_ollama = MagicMock(
            return_value={"response": "응답", "tools_used": []}
        )

        result = router.route("나 ONETEP도 쓰게 됐어", session_id="test")
        assert result["response"] == "응답"
