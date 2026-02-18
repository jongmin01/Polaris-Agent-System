"""
Polaris Skills Registry — Indexes and provides access to all skills.
"""

import logging
from typing import Optional

from polaris.skills.skill_loader import SkillLoader

logger = logging.getLogger(__name__)


class SkillRegistry:
    """Registry that indexes all skills and provides lookup interface for router."""

    def __init__(self, skills_dir: Optional[str] = None):
        self.loader = SkillLoader(skills_dir)
        self._index: dict = {}
        self._scan()

    def _scan(self):
        """Scan skills directory and index all skills."""
        self._index = {}
        for skill_info in self.loader.list_skills():
            name = skill_info["name"]
            skill_info["source"] = "internal"
            self._index[name] = skill_info

        if self._index:
            logger.info("Skills registry: %d skills indexed", len(self._index))
        else:
            logger.info("Skills registry: no skills found")

    def refresh(self):
        """Re-scan skills directory (call when skills are added/removed)."""
        self._scan()

    def match(self, message: str) -> list:
        """Match skills for a user message.

        Args:
            message: User message text.

        Returns:
            List of matching skill info dicts.
        """
        if not message:
            return []
        msg_lower = message.lower()
        matched = []
        for skill_info in self._index.values():
            triggers = skill_info.get("triggers", [])
            if any(trigger.lower() in msg_lower for trigger in triggers):
                matched.append(skill_info)
        return matched

    def get_prompt(self, name: str) -> Optional[str]:
        """Get the prompt content for a skill.

        Args:
            name: Skill name.

        Returns:
            Prompt string or None.
        """
        skill = self._index.get(name)
        if skill and skill.get("source") == "external":
            return skill.get("prompt", "")
        return self.loader.get_skill_prompt(name)

    def get(self, name: str) -> Optional[dict]:
        """Get skill info by name."""
        return self._index.get(name)

    def list_all(self) -> list:
        """List all indexed skills."""
        return list(self._index.values())

    def register_external_skills(self, search_paths: list) -> int:
        """Scan external skill paths and register discovered skills."""
        registered = 0
        skills = self.loader.scan_external_skills(search_paths)
        for skill in skills:
            name = skill["name"]
            self._index[name] = skill
            registered += 1

        if registered:
            logger.info("Registered %d external skills", registered)
        return registered
