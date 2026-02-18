"""
Polaris Fact Extractor — Rule-based knowledge extraction from conversations.

Extracts new facts about the user from conversation messages using
regex pattern matching. No LLM calls — fast and deterministic.

Extracted facts are saved to the knowledge table and optionally
reflected in master_prompt.md 99_CURRENT_CONTEXT.
"""

import logging
import re
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Extraction patterns
# ------------------------------------------------------------------
# Each pattern is (compiled_regex, category, title_template, content_group_index)
# title_template may contain {0}, {1}, ... for regex groups.

_RAW_PATTERNS = [
    # New tools / technologies
    (r"나\s+(.+?)\s*(시작했어|쓰게\s*됐어|배우고\s*있어|쓰기\s*시작|써보고\s*있어|도\s*쓰게|도\s*써)",
     "research", "{0} 도구/기술 사용 시작"),
    (r"(.+?)\s*(설치했어|깔았어|세팅했어|설정했어|셋업했어)",
     "research", "{0} 환경 설정"),

    # Status changes (pass/fail)
    (r"(.+?)\s*(에\s*)?합격했어",
     "career", "{0} 합격"),
    (r"(.+?)\s*(에\s*)?불합격했어",
     "career", "{0} 불합격"),
    (r"(.+?)\s*(에\s*)?(붙었어|떨어졌어|통과했어)",
     "career", "{0} 결과"),

    # Purchases / changes
    (r"나\s+(.+?)\s*(샀어|바꿨어|구매했어|질렀어|주문했어)",
     "life", "{0} 구매/변경"),

    # Cat-related (시루, 설기)
    (r"(시루|설기)\s*[가이은는]\s*(.+)",
     "life", "{0} 관련 정보"),
    (r"(시루|설기)\s+(.+)",
     "life", "{0} 관련 정보"),

    # Semester / academic
    (r"이번\s*학기\s*(.+)",
     "academic", "이번 학기 {0}"),
    (r"다음\s*학기\s*(.+)",
     "academic", "다음 학기 {0}"),

    # Research findings
    (r"연구에서\s+(.+?)\s*(발견했어|확인했어|알아냈어|밝혀졌어)",
     "research", "연구 발견: {0}"),
    (r"(시뮬레이션|계산|DFT|VASP|ONETEP)\s*(결과|에서)\s*(.+)",
     "research", "{0} 결과"),
    (r"(밴드갭|band\s*gap)\s*[이가은는]\s*(.+?(?:\d+\.?\d*\s*(?:eV|meV|eV야|eV어)).*)",
     "research", "밴드갭 정보: {1}"),

    # Internship / career
    (r"인턴십\s+(.+)",
     "career", "인턴십 {0}"),
    (r"인턴\s+(.+)",
     "career", "인턴 {0}"),
    (r"(직장|회사|취직)\s*(.+)",
     "career", "커리어: {1}"),

    # Vehicle / mileage
    (r"(\d[\d,]*)\s*(km|마일|mile)\s*.*(교체|갈았어|했어|체크)",
     "vehicle", "차량 주행거리 {0}{1}"),
    (r"(엔진오일|타이어|브레이크|배터리)\s*(.+?)(?:교체|갈았어|했어|체크)",
     "vehicle", "{0} 정비"),

    # Moving / address
    (r"(이사|이사했어|이사\s*가|이사\s*갈\s*거)",
     "life", "이사 관련"),

    # Health
    (r"(병원|아파서|감기|코로나|독감)\s*(.+)",
     "life", "건강: {0}"),
]

# Compile patterns
FACT_PATTERNS = []
for raw_pattern, category, title_tpl in _RAW_PATTERNS:
    FACT_PATTERNS.append((re.compile(raw_pattern, re.IGNORECASE), category, title_tpl))


# Section mapping for master_prompt.md
CATEGORY_TO_SECTION = {
    "research": "02_RESEARCH",
    "dev": "02_DEV",
    "academic": "99_CURRENT_CONTEXT",
    "career": "99_CURRENT_CONTEXT",
    "life": "99_CURRENT_CONTEXT",
    "vehicle": "99_CURRENT_CONTEXT",
}

# Categories considered "high importance" for master_prompt update
HIGH_IMPORTANCE_CATEGORIES = {"career", "research", "academic"}

# Minimum message length to consider extraction
MIN_MESSAGE_LENGTH = 10

# Simple messages that should never trigger extraction
_SKIP_PATTERNS = re.compile(
    r"^(ㅋ+|ㅎ+|ㅠ+|ㅜ+|안녕|고마워|감사|ㅇㅋ|ㅇㅇ|응|아니|네|오키|잘\s*자|굿나잇|"
    r"good\s*night|thanks|thank\s*you|ok|okay|hi|hello|hey|bye|gn)[\s!?.]*$",
    re.IGNORECASE,
)


class FactExtractor:
    """Rule-based fact extractor from conversation messages."""

    def __init__(self, memory=None, obsidian_writer=None):
        """
        Args:
            memory: PolarisMemory instance for save_knowledge().
            obsidian_writer: ObsidianWriter instance for master_prompt updates.
        """
        self.memory = memory
        self.obsidian_writer = obsidian_writer

    # ------------------------------------------------------------------
    # Pre-filter
    # ------------------------------------------------------------------

    @staticmethod
    def should_extract(user_message: str) -> bool:
        """Check if a message is worth attempting fact extraction.

        Returns False for short messages, simple greetings, etc.
        """
        if not user_message or len(user_message) < MIN_MESSAGE_LENGTH:
            return False
        if _SKIP_PATTERNS.match(user_message.strip()):
            return False
        return True

    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------

    def extract_facts(
        self,
        user_message: str,
        bot_response: str = "",
        session_id: str = "",
    ) -> List[Dict]:
        """Extract facts from a conversation turn using regex patterns.

        Returns a list of fact dicts:
            [{category, title, content, source}]
        """
        facts = []
        seen_titles = set()

        for pattern, category, title_tpl in FACT_PATTERNS:
            match = pattern.search(user_message)
            if not match:
                continue

            # Build title from template + captured groups
            groups = match.groups()
            try:
                title = title_tpl.format(*groups)
            except (IndexError, KeyError):
                title = title_tpl

            # Deduplicate within same extraction
            if title in seen_titles:
                continue
            seen_titles.add(title)

            content = user_message.strip()

            facts.append({
                "category": category,
                "title": title,
                "content": content,
                "source": "conversation",
            })

        return facts

    # ------------------------------------------------------------------
    # Categorization (for master_prompt section mapping)
    # ------------------------------------------------------------------

    @staticmethod
    def categorize_fact(fact: Dict) -> str:
        """Map a fact's category to the appropriate master_prompt.md section."""
        return CATEGORY_TO_SECTION.get(fact.get("category", ""), "99_CURRENT_CONTEXT")

    # ------------------------------------------------------------------
    # Save and update
    # ------------------------------------------------------------------

    def save_and_update(self, facts: List[Dict]) -> int:
        """Save extracted facts to knowledge table and update master_prompt.

        Returns the number of facts saved.
        """
        if not facts:
            return 0

        saved = 0
        high_importance_facts = []

        for fact in facts:
            # Save to knowledge table
            if self.memory:
                try:
                    self.memory.save_knowledge(
                        category=fact["category"],
                        title=fact["title"],
                        content=fact["content"],
                        source=fact.get("source", "conversation"),
                        tags=[fact["category"]],
                    )
                    saved += 1
                    logger.info("Saved fact: %s", fact["title"])
                except Exception as e:
                    logger.warning("Failed to save fact '%s': %s", fact["title"], e)

            # Collect high-importance facts for master_prompt update
            if fact.get("category") in HIGH_IMPORTANCE_CATEGORIES:
                high_importance_facts.append(fact)

        # Update master_prompt.md 99_CURRENT_CONTEXT for important facts
        if high_importance_facts and self.obsidian_writer:
            try:
                self._update_current_context(high_importance_facts)
            except Exception as e:
                logger.warning("Failed to update master_prompt: %s", e)

        return saved

    def _update_current_context(self, facts: List[Dict]):
        """Append high-importance facts to 99_CURRENT_CONTEXT section."""
        if not self.obsidian_writer:
            return

        # Read existing context
        existing = self.obsidian_writer.read_master_prompt_section("99_CURRENT_CONTEXT")

        # Build new entries
        today = datetime.now().strftime("%Y-%m-%d")
        new_lines = []
        for fact in facts:
            entry = f"- [{today}] {fact['title']}: {fact['content'][:100]}"
            # Skip if already present (dedup by title)
            if fact["title"] in existing:
                logger.debug("Fact '%s' already in 99_CURRENT_CONTEXT, skipping", fact["title"])
                continue
            new_lines.append(entry)

        if not new_lines:
            return

        # Append to existing content
        if existing:
            # Strip the section header, keep body
            body = existing
            # Remove the "## 99_CURRENT_CONTEXT" header line if present
            lines = body.split("\n")
            if lines and lines[0].startswith("## 99_CURRENT_CONTEXT"):
                body = "\n".join(lines[1:])
            new_content = body.strip() + "\n" + "\n".join(new_lines)
        else:
            new_content = "\n".join(new_lines)

        self.obsidian_writer.update_master_prompt(new_content)
        logger.info("Updated 99_CURRENT_CONTEXT with %d new facts", len(new_lines))
