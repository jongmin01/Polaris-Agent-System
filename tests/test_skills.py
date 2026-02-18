"""Tests for polaris.skills — SkillLoader, SkillRegistry, and router integration."""

import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# ---------- fixtures ----------

SAMPLE_SKILL = """\
---
name: test_skill
description: "테스트 스킬"
version: "1.0"
author: "test"
tools_required: [search_arxiv]
trigger_patterns: ["테스트", "test", "검색"]
category: research
---

## Prompt
사용자가 테스트를 요청했어. 다음 절차를 따라:
1. 검색 실행
2. 결과 요약

## Few-shot Examples
### Example 1
**Input**: 테스트 해줘
**Output**: 테스트 결과야.

## Validation
- 결과가 정확한가

## Changelog
- v1.0: 초기 생성
"""

SAMPLE_SKILL_NO_TRIGGERS = """\
---
name: no_triggers
description: "트리거 없는 스킬"
version: "1.0"
category: system
---

## Prompt
특별한 스킬이야.
"""


@pytest.fixture
def skills_dir(tmp_path):
    """Create a temp skills directory with sample skill files."""
    # Write sample skills
    (tmp_path / "test_skill.md").write_text(SAMPLE_SKILL, encoding="utf-8")
    (tmp_path / "no_triggers.md").write_text(SAMPLE_SKILL_NO_TRIGGERS, encoding="utf-8")
    # README should be skipped
    (tmp_path / "README.md").write_text("# Skills\nThis is the index.", encoding="utf-8")
    return tmp_path


@pytest.fixture
def empty_dir(tmp_path):
    """An empty directory with no skill files."""
    return tmp_path / "empty"


# ================================================================
# SkillLoader tests
# ================================================================

class TestSkillLoader:
    """Tests for SkillLoader."""

    def test_load_skill(self, skills_dir):
        from polaris.skills.skill_loader import SkillLoader
        loader = SkillLoader(str(skills_dir))
        skill = loader.load_skill("test_skill")

        assert skill is not None
        assert skill["name"] == "test_skill"
        assert skill["header"]["description"] == "테스트 스킬"
        assert skill["header"]["trigger_patterns"] == ["테스트", "test", "검색"]
        assert "## Prompt" in skill["body"]

    def test_load_skill_not_found(self, skills_dir):
        from polaris.skills.skill_loader import SkillLoader
        loader = SkillLoader(str(skills_dir))
        result = loader.load_skill("nonexistent")
        assert result is None

    def test_list_skills(self, skills_dir):
        from polaris.skills.skill_loader import SkillLoader
        loader = SkillLoader(str(skills_dir))
        skills = loader.list_skills()

        assert len(skills) == 2
        names = {s["name"] for s in skills}
        assert "test_skill" in names
        assert "no_triggers" in names
        # README should NOT be in the list
        assert "README" not in names

    def test_list_skills_empty_dir(self, empty_dir):
        from polaris.skills.skill_loader import SkillLoader
        loader = SkillLoader(str(empty_dir))
        assert loader.list_skills() == []

    def test_match_skills(self, skills_dir):
        from polaris.skills.skill_loader import SkillLoader
        loader = SkillLoader(str(skills_dir))

        # Should match test_skill (has "테스트" trigger)
        matched = loader.match_skills("테스트 해줘")
        assert len(matched) == 1
        assert matched[0]["name"] == "test_skill"

    def test_match_skills_case_insensitive(self, skills_dir):
        from polaris.skills.skill_loader import SkillLoader
        loader = SkillLoader(str(skills_dir))

        matched = loader.match_skills("TEST something")
        assert len(matched) == 1
        assert matched[0]["name"] == "test_skill"

    def test_match_skills_no_match(self, skills_dir):
        from polaris.skills.skill_loader import SkillLoader
        loader = SkillLoader(str(skills_dir))

        matched = loader.match_skills("안녕하세요")
        assert len(matched) == 0

    def test_get_skill_prompt(self, skills_dir):
        from polaris.skills.skill_loader import SkillLoader
        loader = SkillLoader(str(skills_dir))

        prompt = loader.get_skill_prompt("test_skill")
        assert prompt is not None
        # Should include Prompt and Few-shot sections
        assert "검색 실행" in prompt
        assert "Few-shot Examples" in prompt
        # Should NOT include Validation or Changelog
        assert "Validation" not in prompt
        assert "Changelog" not in prompt

    def test_get_skill_prompt_not_found(self, skills_dir):
        from polaris.skills.skill_loader import SkillLoader
        loader = SkillLoader(str(skills_dir))

        result = loader.get_skill_prompt("nonexistent")
        assert result is None

    def test_parse_frontmatter(self, skills_dir):
        from polaris.skills.skill_loader import SkillLoader
        loader = SkillLoader(str(skills_dir))

        header, body = loader._parse_frontmatter(SAMPLE_SKILL)
        assert header["name"] == "test_skill"
        assert header["version"] == "1.0"
        assert isinstance(header["tools_required"], list)
        assert "search_arxiv" in header["tools_required"]

    def test_parse_frontmatter_no_yaml(self, skills_dir):
        from polaris.skills.skill_loader import SkillLoader
        loader = SkillLoader(str(skills_dir))

        header, body = loader._parse_frontmatter("No frontmatter here")
        assert header == {}
        assert body == "No frontmatter here"

    def test_simple_parse_fallback(self, skills_dir):
        from polaris.skills.skill_loader import SkillLoader
        loader = SkillLoader(str(skills_dir))

        text = 'name: test\ndescription: "hello"\ntrigger_patterns: ["a", "b"]'
        result = loader._simple_parse(text)
        assert result["name"] == "test"
        assert result["description"] == "hello"
        assert result["trigger_patterns"] == ["a", "b"]


# ================================================================
# SkillRegistry tests
# ================================================================

class TestSkillRegistry:
    """Tests for SkillRegistry."""

    def test_registry_indexes_skills(self, skills_dir):
        from polaris.skills.registry import SkillRegistry
        registry = SkillRegistry(str(skills_dir))

        all_skills = registry.list_all()
        assert len(all_skills) == 2

    def test_registry_get(self, skills_dir):
        from polaris.skills.registry import SkillRegistry
        registry = SkillRegistry(str(skills_dir))

        skill = registry.get("test_skill")
        assert skill is not None
        assert skill["name"] == "test_skill"

    def test_registry_get_not_found(self, skills_dir):
        from polaris.skills.registry import SkillRegistry
        registry = SkillRegistry(str(skills_dir))

        assert registry.get("nonexistent") is None

    def test_registry_match(self, skills_dir):
        from polaris.skills.registry import SkillRegistry
        registry = SkillRegistry(str(skills_dir))

        matched = registry.match("검색해줘")
        assert len(matched) == 1
        assert matched[0]["name"] == "test_skill"

    def test_registry_get_prompt(self, skills_dir):
        from polaris.skills.registry import SkillRegistry
        registry = SkillRegistry(str(skills_dir))

        prompt = registry.get_prompt("test_skill")
        assert prompt is not None
        assert "검색 실행" in prompt

    def test_registry_refresh(self, skills_dir):
        from polaris.skills.registry import SkillRegistry
        registry = SkillRegistry(str(skills_dir))

        assert len(registry.list_all()) == 2

        # Add a new skill file
        new_skill = """\
---
name: new_skill
description: "새 스킬"
trigger_patterns: ["new"]
category: test
---

## Prompt
새 스킬이야.
"""
        (skills_dir / "new_skill.md").write_text(new_skill, encoding="utf-8")
        registry.refresh()
        assert len(registry.list_all()) == 3


# ================================================================
# Router skill injection tests
# ================================================================

class TestRouterSkillInjection:
    """Test that PolarisRouter injects skills into system prompt."""

    @patch("polaris.router.PolarisRouter._init_memory")
    @patch("polaris.router.PolarisRouter._load_tools")
    @patch("polaris.router.PolarisRouter._init_ollama")
    def test_router_loads_skills(self, mock_ollama, mock_tools, mock_mem, skills_dir):
        """Router should initialise skill_registry on __init__."""
        with patch("polaris.skills.SkillRegistry") as MockReg:
            MockReg.return_value.list_all.return_value = [{"name": "a"}]
            from polaris.router import PolarisRouter
            router = PolarisRouter()
            assert router.skill_registry is not None

    @patch("polaris.router.PolarisRouter._init_memory")
    @patch("polaris.router.PolarisRouter._load_tools")
    @patch("polaris.router.PolarisRouter._init_ollama")
    def test_router_skills_graceful_fail(self, mock_ollama, mock_tools, mock_mem):
        """Router should handle missing skills system gracefully."""
        with patch("polaris.skills.SkillRegistry", side_effect=ImportError("no skills")):
            from polaris.router import PolarisRouter
            router = PolarisRouter()
            assert router.skill_registry is None

    @patch("polaris.router.PolarisRouter._init_memory")
    @patch("polaris.router.PolarisRouter._load_tools")
    @patch("polaris.router.PolarisRouter._init_ollama")
    def test_skill_injection_in_system_prompt(self, mock_ollama, mock_tools, mock_mem, skills_dir):
        """Matched skills should appear in _build_system_prompt output."""
        from polaris.router import PolarisRouter

        with patch("polaris.router.PolarisRouter._init_skills"):
            router = PolarisRouter()
            router.tools = []
            router.memory = None

            # Set up a real skill registry pointing to temp dir
            from polaris.skills import SkillRegistry
            router.skill_registry = SkillRegistry(str(skills_dir))

            prompt = router._build_system_prompt("테스트 해줘", has_tools=False)
            assert "[SKILL: test_skill]" in prompt
            assert "검색 실행" in prompt

    @patch("polaris.router.PolarisRouter._init_memory")
    @patch("polaris.router.PolarisRouter._load_tools")
    @patch("polaris.router.PolarisRouter._init_ollama")
    def test_no_skill_injection_for_unmatched(self, mock_ollama, mock_tools, mock_mem, skills_dir):
        """Unmatched messages should not inject skills."""
        from polaris.router import PolarisRouter

        with patch("polaris.router.PolarisRouter._init_skills"):
            router = PolarisRouter()
            router.tools = []
            router.memory = None

            from polaris.skills import SkillRegistry
            router.skill_registry = SkillRegistry(str(skills_dir))

            prompt = router._build_system_prompt("안녕?", has_tools=False)
            assert "[SKILL:" not in prompt


# ================================================================
# Integration: actual skills directory
# ================================================================

class TestActualSkills:
    """Test that the real skills/ directory has valid skill files."""

    def test_actual_skills_load(self):
        """All .md files in skills/ should parse without errors."""
        from polaris.skills.skill_loader import SkillLoader
        loader = SkillLoader()  # uses default skills/ dir

        skills = loader.list_skills()
        # We should have at least the 6 skills created in Phase 2.7
        assert len(skills) >= 6

        for skill in skills:
            assert "name" in skill
            assert "description" in skill
            assert isinstance(skill.get("triggers", []), list)

    def test_actual_skills_have_prompts(self):
        """Each actual skill should have extractable prompt content."""
        from polaris.skills.skill_loader import SkillLoader
        loader = SkillLoader()

        for skill_info in loader.list_skills():
            prompt = loader.get_skill_prompt(skill_info["name"])
            assert prompt is not None, f"Skill {skill_info['name']} has no prompt"
            assert len(prompt) > 10, f"Skill {skill_info['name']} prompt too short"
