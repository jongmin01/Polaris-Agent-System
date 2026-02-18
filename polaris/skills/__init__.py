"""
Polaris Skills System

Skills are markdown files that provide structured instructions for the LLM.
They are NOT executable code — they are manuals that guide how the LLM
approaches specific tasks.
"""

from polaris.skills.skill_loader import SkillLoader
from polaris.skills.registry import SkillRegistry

__all__ = ["SkillLoader", "SkillRegistry"]
