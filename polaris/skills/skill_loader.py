"""
Polaris Skills — Markdown-based skill loader

Skills are markdown files with YAML frontmatter that provide
structured instructions for the LLM.
"""

import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False


class SkillLoader:
    """Load and parse skill markdown files."""

    def __init__(self, skills_dir: Optional[str] = None):
        if skills_dir:
            self.skills_dir = Path(skills_dir)
        else:
            self.skills_dir = Path(__file__).resolve().parent.parent.parent / "skills"

    def load_skill(self, name: str) -> Optional[dict]:
        """Load a skill by name.

        Args:
            name: Skill name (without .md extension).

        Returns:
            Dict with 'name', 'header' (parsed YAML), 'body' (markdown),
            or None if not found.
        """
        path = self.skills_dir / f"{name}.md"
        if not path.exists():
            logger.warning("Skill not found: %s", name)
            return None

        try:
            content = path.read_text(encoding="utf-8")
            header, body = self._parse_frontmatter(content)
            return {
                "name": header.get("name", name),
                "header": header,
                "body": body,
            }
        except Exception as e:
            logger.error("Failed to load skill %s: %s", name, e)
            return None

    def list_skills(self) -> list:
        """List all available skills.

        Returns:
            List of dicts with name, description, triggers, category.
        """
        if not self.skills_dir.exists():
            return []

        skills = []
        for path in sorted(self.skills_dir.glob("*.md")):
            if path.name == "README.md":
                continue
            try:
                content = path.read_text(encoding="utf-8")
                header, _ = self._parse_frontmatter(content)
                if not header:
                    continue
                triggers = header.get("trigger_patterns", [])
                if not triggers:
                    triggers = self.extract_trigger_keywords(header.get("description", ""))

                tools_req = header.get("tools_required", [])
                if not tools_req:
                    tools_req = self.extract_tools_from_description(header.get("description", ""))

                tool_chain = header.get("tool_chain", [])
                if isinstance(tool_chain, str):
                    tool_chain = self._split_items(tool_chain)

                requires_tool = self._as_bool(header.get("requires_tool", False))
                strict_mode = self._as_bool(header.get("strict_mode", requires_tool))

                skills.append({
                    "name": header.get("name", path.stem),
                    "description": header.get("description", ""),
                    "triggers": triggers,
                    "category": header.get("category", ""),
                    "version": header.get("version", ""),
                    "tools_required": tools_req,
                    "tool_chain": tool_chain,
                    "requires_tool": requires_tool,
                    "strict_mode": strict_mode,
                })
            except Exception as e:
                logger.warning("Failed to parse skill %s: %s", path.name, e)

        return skills

    def match_skills(self, user_message: str) -> list:
        """Match skills whose trigger patterns appear in user message.

        Args:
            user_message: The user's message text.

        Returns:
            List of matching skill info dicts.
        """
        if not self.skills_dir.exists():
            return []

        msg_lower = user_message.lower()
        matched = []

        for skill_info in self.list_skills():
            triggers = skill_info.get("triggers", [])
            if any(trigger.lower() in msg_lower for trigger in triggers):
                matched.append(skill_info)

        return matched

    def extract_trigger_keywords(self, description: str) -> list:
        """Extract trigger keywords from a skill description."""
        if not description:
            return []

        patterns = [
            r"Use when\s*사용자가\s*(.+?)\s*관련 질문을 할 때",
            r"Use when\s*(?:the\s+)?user(?:s)?\s*(?:asks?|ask)\s*(?:about|for|regarding)\s*(.+?)(?:\.|$)",
        ]
        for pattern in patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                return self._split_items(match.group(1))

        match = re.search(r"\((?:e\.g\.,?|예:)\s*([^)]+)\)", description, re.IGNORECASE)
        if match:
            return self._split_items(match.group(1))

        stopwords = {
            "use", "when", "user", "users", "asks", "ask", "about", "for",
            "related", "question", "questions", "the", "and", "or",
            "사용자가", "관련", "질문", "할", "때", "도구", "필요",
        }
        words = re.findall(r"[A-Za-z0-9_+\-\.#가-힣]{2,}", description)
        deduped = []
        seen = set()
        for word in words:
            token = word.strip()
            if not token:
                continue
            if token.lower() in stopwords:
                continue
            key = token.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(token)
        return deduped[:10]

    def extract_tools_from_description(self, description: str) -> list:
        """Extract required tools from description text."""
        if not description:
            return []

        patterns = [
            r"필요 도구:\s*([^.\n]+)",
            r"Required tools:\s*([^.\n]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                return self._split_items(match.group(1))
        return []

    def load_external_skill(self, skill_dir: Path) -> Optional[dict]:
        """Load an external skill from a directory containing SKILL.md."""
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            return None

        try:
            content = skill_md.read_text(encoding="utf-8")
            header, body = self._parse_frontmatter(content)
            description = header.get("description", "")
            triggers = header.get("trigger_patterns", [])
            if not triggers:
                triggers = self.extract_trigger_keywords(description)

            tools_req = header.get("tools_required", [])
            if not tools_req:
                tools_req = self.extract_tools_from_description(description)

            tool_chain = header.get("tool_chain", [])
            if isinstance(tool_chain, str):
                tool_chain = self._split_items(tool_chain)

            requires_tool = self._as_bool(header.get("requires_tool", False))
            strict_mode = self._as_bool(header.get("strict_mode", requires_tool))

            name = header.get("name") or skill_dir.name
            prompt = self._extract_prompt_sections(body if header else content)
            return {
                "name": name,
                "description": description,
                "triggers": triggers,
                "category": header.get("category", ""),
                "version": header.get("version", ""),
                "tools_required": tools_req,
                "tool_chain": tool_chain,
                "requires_tool": requires_tool,
                "strict_mode": strict_mode,
                "source": "external",
                "path": str(skill_md),
                "prompt": prompt,
            }
        except Exception as e:
            logger.warning("Failed to load external skill %s: %s", skill_md, e)
            return None

    def scan_external_skills(self, search_paths: list) -> list:
        """Scan external paths and load SKILL.md files."""
        loaded = []
        seen_paths = set()

        for raw_path in search_paths:
            base = Path(raw_path).expanduser()
            if not base.exists():
                continue

            candidates = []
            if (base / "SKILL.md").exists():
                candidates.append(base)
            else:
                for skill_file in base.rglob("SKILL.md"):
                    candidates.append(skill_file.parent)

            for candidate in candidates:
                skill_md = str((candidate / "SKILL.md").resolve())
                if skill_md in seen_paths:
                    continue
                seen_paths.add(skill_md)
                skill = self.load_external_skill(candidate)
                if skill:
                    loaded.append(skill)

        return loaded

    def get_skill_prompt(self, name: str) -> Optional[str]:
        """Extract Prompt and Few-shot sections from a skill.

        Skips Validation and Changelog sections to save tokens.

        Args:
            name: Skill name.

        Returns:
            Prompt content string, or None if skill not found.
        """
        skill = self.load_skill(name)
        if not skill:
            return None

        body = skill["body"]
        return self._extract_prompt_sections(body)

    def _extract_prompt_sections(self, body: str) -> str:
        """Extract Prompt/Few-shot sections from markdown body."""
        include_sections = {"prompt", "few-shot examples"}

        sections = []
        current_section = None
        current_lines: list = []

        for line in body.split("\n"):
            if line.startswith("## "):
                if current_section and current_section.lower() in include_sections:
                    sections.append("\n".join(current_lines))
                current_section = line[3:].strip()
                current_lines = [line]
            else:
                current_lines.append(line)

        # Last section
        if current_section and current_section.lower() in include_sections:
            sections.append("\n".join(current_lines))

        return "\n\n".join(sections) if sections else body

    def _split_items(self, text: str) -> list:
        """Split comma-separated text into cleaned items."""
        if not text:
            return []
        normalized = text.replace("및", ",").replace(" and ", ",").replace("/", ",")
        parts = [p.strip(" .:;\"'") for p in normalized.split(",")]
        cleaned = []
        seen = set()
        for part in parts:
            if not part:
                continue
            key = part.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(part)
        return cleaned

    def _as_bool(self, value) -> bool:
        """Coerce YAML/frontmatter values into bool."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"true", "1", "yes", "y", "on"}
        return bool(value)

    # ------------------------------------------------------------------
    # Frontmatter parsing
    # ------------------------------------------------------------------

    def _parse_frontmatter(self, content: str) -> tuple:
        """Parse YAML frontmatter from markdown content.

        Returns:
            (header_dict, body_string)
        """
        if not content.startswith("---"):
            return {}, content

        end_idx = content.find("---", 3)
        if end_idx == -1:
            return {}, content

        frontmatter = content[3:end_idx].strip()
        body = content[end_idx + 3:].strip()

        if _HAS_YAML:
            try:
                header = yaml.safe_load(frontmatter)
                return header or {}, body
            except Exception as e:
                logger.warning("YAML parse error: %s", e)
                return self._simple_parse(frontmatter), body
        else:
            return self._simple_parse(frontmatter), body

    def _simple_parse(self, text: str) -> dict:
        """Fallback YAML parser when PyYAML is unavailable."""
        result = {}
        for line in text.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                key, _, value = line.partition(":")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if value.startswith("[") and value.endswith("]"):
                    items = value[1:-1].split(",")
                    result[key] = [
                        item.strip().strip('"').strip("'")
                        for item in items if item.strip()
                    ]
                else:
                    result[key] = value
        return result
