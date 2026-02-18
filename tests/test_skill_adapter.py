"""Tests for AgentSkills adapter + external skills compatibility."""

from unittest.mock import patch

import pytest

from polaris.skills.registry import SkillRegistry
from polaris.skills.skill_loader import SkillLoader


class TestTriggerExtraction:
    def test_extract_triggers_korean_use_when(self):
        loader = SkillLoader()
        desc = "설명. Use when 사용자가 수렴, VASP, 계산 확인, convergence 관련 질문을 할 때. 필요 도구: monitor_hpc_job."
        assert loader.extract_trigger_keywords(desc) == ["수렴", "VASP", "계산 확인", "convergence"]

    def test_extract_triggers_english_use_when(self):
        loader = SkillLoader()
        desc = "Paper analysis helper. Use when user asks about paper review, arxiv search, methodology."
        assert loader.extract_trigger_keywords(desc) == ["paper review", "arxiv search", "methodology"]

    def test_extract_triggers_eg_pattern(self):
        loader = SkillLoader()
        desc = "Research helper (e.g., VASP, DFT, convergence)."
        assert loader.extract_trigger_keywords(desc) == ["VASP", "DFT", "convergence"]

    def test_extract_triggers_korean_eg_pattern(self):
        loader = SkillLoader()
        desc = "연구 도우미 (예: 수렴, VASP, 계산 상태)."
        assert loader.extract_trigger_keywords(desc) == ["수렴", "VASP", "계산 상태"]

    def test_extract_triggers_fallback(self):
        loader = SkillLoader()
        desc = "VASP convergence diagnostics for HPC troubleshooting"
        keywords = loader.extract_trigger_keywords(desc)
        assert "VASP" in keywords
        assert "convergence" in keywords

    def test_extract_triggers_empty_description(self):
        loader = SkillLoader()
        assert loader.extract_trigger_keywords("") == []


class TestToolExtraction:
    def test_extract_tools_korean(self):
        loader = SkillLoader()
        desc = "설명. 필요 도구: monitor_hpc_job, check_hpc_connection."
        assert loader.extract_tools_from_description(desc) == ["monitor_hpc_job", "check_hpc_connection"]

    def test_extract_tools_english(self):
        loader = SkillLoader()
        desc = "Research helper. Required tools: search_arxiv, analyze_paper_gemini."
        assert loader.extract_tools_from_description(desc) == ["search_arxiv", "analyze_paper_gemini"]

    def test_extract_tools_none(self):
        loader = SkillLoader()
        assert loader.extract_tools_from_description("no tool metadata") == []


class TestExternalSkillLoading:
    def test_load_external_agentskill(self, tmp_path):
        loader = SkillLoader()
        ext_dir = tmp_path / "skill_a"
        ext_dir.mkdir()
        (ext_dir / "SKILL.md").write_text(
            """---\nname: ext_agent\ndescription: \"desc. Use when 사용자가 외부, 테스트 관련 질문을 할 때. 필요 도구: search_arxiv.\"\ncategory: research\n---\n\n## Prompt\n외부 스킬 프롬프트\n""",
            encoding="utf-8",
        )

        skill = loader.load_external_skill(ext_dir)
        assert skill is not None
        assert skill["name"] == "ext_agent"
        assert skill["source"] == "external"
        assert skill["triggers"] == ["외부", "테스트"]

    def test_load_external_openclaw_legacy_metadata(self, tmp_path):
        loader = SkillLoader()
        ext_dir = tmp_path / "skill_legacy"
        ext_dir.mkdir()
        (ext_dir / "SKILL.md").write_text(
            """---\nname: openclaw_style\ndescription: \"legacy format\"\ntrigger_patterns: [\"job\", \"hpc\"]\ntools_required: [monitor_hpc_job]\ncategory: research\n---\n\n## Prompt\nlegacy prompt\n""",
            encoding="utf-8",
        )

        skill = loader.load_external_skill(ext_dir)
        assert skill is not None
        assert skill["triggers"] == ["job", "hpc"]
        assert skill["tools_required"] == ["monitor_hpc_job"]

    def test_load_external_missing_skill_md(self, tmp_path):
        loader = SkillLoader()
        ext_dir = tmp_path / "missing"
        ext_dir.mkdir()
        assert loader.load_external_skill(ext_dir) is None

    def test_scan_external_skills_skips_missing_paths(self, tmp_path):
        loader = SkillLoader()
        valid = tmp_path / "valid"
        valid.mkdir()
        (valid / "SKILL.md").write_text(
            """---\nname: valid_ext\ndescription: \"Use when 사용자가 valid 관련 질문을 할 때.\"\n---\n\n## Prompt\nhi\n""",
            encoding="utf-8",
        )

        missing = tmp_path / "not_exists"
        loaded = loader.scan_external_skills([str(missing), str(valid)])
        assert len(loaded) == 1
        assert loaded[0]["name"] == "valid_ext"


class TestMigrationCompatibility:
    def test_migrated_skills_have_no_trigger_patterns_field(self):
        loader = SkillLoader()
        for name in [
            "vasp_convergence",
            "arxiv_analysis",
            "paper_to_obsidian",
            "email_triage",
            "hpc_monitor",
            "daily_briefing",
        ]:
            skill = loader.load_skill(name)
            assert skill is not None
            assert "trigger_patterns" not in skill["header"]

    def test_migrated_skill_list_still_has_triggers(self):
        loader = SkillLoader()
        skills = {s["name"]: s for s in loader.list_skills()}
        assert "vasp_convergence" in skills
        assert "VASP" in skills["vasp_convergence"]["triggers"]

    def test_migrated_trigger_matching_works(self):
        loader = SkillLoader()
        matched = loader.match_skills("VASP 수렴 확인해줘")
        names = {s["name"] for s in matched}
        assert "vasp_convergence" in names


class TestIntegration:
    def test_registry_internal_external_mix(self, tmp_path):
        ext_root = tmp_path / "external"
        ext_skill = ext_root / "my_ext"
        ext_skill.mkdir(parents=True)
        (ext_skill / "SKILL.md").write_text(
            """---\nname: ext_mix\ndescription: \"Use when 사용자가 external mix 관련 질문을 할 때.\"\n---\n\n## Prompt\nexternal prompt\n""",
            encoding="utf-8",
        )

        registry = SkillRegistry()
        count = registry.register_external_skills([str(ext_root)])
        all_skills = registry.list_all()

        assert count >= 1
        assert any(s["source"] == "internal" for s in all_skills)
        assert any(s["name"] == "ext_mix" and s["source"] == "external" for s in all_skills)

    @patch("polaris.router.PolarisRouter._init_memory")
    @patch("polaris.router.PolarisRouter._load_tools")
    @patch("polaris.router.PolarisRouter._init_ollama")
    def test_router_system_prompt_includes_external_skill(self, mock_ollama, mock_tools, mock_mem, tmp_path):
        from polaris.router import PolarisRouter

        ext_root = tmp_path / "external"
        ext_skill = ext_root / "router_ext"
        ext_skill.mkdir(parents=True)
        (ext_skill / "SKILL.md").write_text(
            """---\nname: ext_router\ndescription: \"Use when 사용자가 router_ext 관련 질문을 할 때.\"\n---\n\n## Prompt\n외부 라우터 스킬\n""",
            encoding="utf-8",
        )

        with patch("polaris.router.PolarisRouter._init_skills"):
            router = PolarisRouter()
            router.tools = []
            router.memory = None
            router.skill_registry = SkillRegistry()
            router.skill_registry.register_external_skills([str(ext_root)])

            prompt = router._build_system_prompt("router_ext 알려줘", has_tools=False)
            assert "[SKILL: ext_router]" in prompt
            assert "외부 라우터 스킬" in prompt
