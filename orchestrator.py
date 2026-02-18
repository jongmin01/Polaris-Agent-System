#!/usr/bin/env python3
"""
Polaris Orchestrator - Intent Classification & Agent Routing

북극성처럼 당신의 요청을 올바른 Agent로 안내합니다.
"""

# =============================================================================
# DEPRECATED - Scheduled for removal: 2026-04-15
# Use: polaris/router.py  (PolarisRouter class via ReAct loop)
# This file: legacy keyword-based intent classifier, no longer maintained.
# =============================================================================

import os
import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

import datetime as _dt
_DELETION_DATE = _dt.date(2026, 4, 15)
if _dt.date.today() >= _DELETION_DATE and os.environ.get("POLARIS_ALLOW_LEGACY") != "1":
    raise RuntimeError(
        f"orchestrator.py was scheduled for deletion on {_DELETION_DATE} and is no longer supported.\n"
        "Use: polaris/router.py (PolarisRouter class)\n"
        "Emergency bypass: POLARIS_ALLOW_LEGACY=1"
    )


class AgentType(Enum):
    """Agent 타입 정의"""
    PHD = "phd"
    LIFE = "life"
    PERSONAL = "personal"
    SCHEDULE = "schedule"  # Phase 1.5: Schedule Agent
    UNKNOWN = "unknown"


@dataclass
class Intent:
    """사용자 의도 분석 결과"""
    agent: AgentType
    confidence: float  # 0.0 ~ 1.0
    keywords_matched: List[str]
    original_message: str


class PolarisOrchestrator:
    """
    Polaris Orchestrator

    역할:
    1. 사용자 메시지 분석
    2. Intent 분류 (어느 Agent로 보낼지)
    3. 적절한 Agent로 라우팅
    4. 비용 추정 및 승인 요청
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Args:
            config_path: .agent_system/ 폴더 경로 (기본: Obsidian 폴더)
        """
        self.system_name = "Polaris"
        self.version = "v0.2"

        # Agent 키워드 정의 (.agent_system/orchestrator_system.md 기반)
        self.agent_keywords = {
            AgentType.PHD: [
                # 연구 관련
                # Paper keywords
                "논문", "paper", "분석", "analyze", "analysis",
                "검색", "search", "찾아", "find", "arxiv",
                # Physics/DFT keywords
                "DFT", "VASP", "ONETEP", "계산", "calculation", "compute",
                "시뮬레이션", "simulation", "sim",
                "밴드", "band", "band structure", "DOS",
                "구조최적화", "relaxation", "optimization",
                "Polaris", "HPC", "submit", "job",
                "GNN", "neural network"
                # Phase 0: Email routing DISABLED - use /mail command explicitly
                # "메일", "email", "학생", "student", "TA", "채점", "grading",
                # "office hour", "오피스아워"
            ],
            AgentType.LIFE: [
                "운동", "workout", "헬스", "gym",
                "수면", "sleep",
                "친구", "friend", "가족", "family"
            ],
            AgentType.PERSONAL: [
                "구매", "purchase", "buy", "사다",
                "차", "car", "정비", "maintenance", "니로", "niro",
                "고양이", "cat", "시루", "설기",
                "지출", "spending", "돈", "money",
                "결정", "decision"
            ],
            AgentType.SCHEDULE: [
                # Phase 1.5: Schedule keywords
                "일정", "schedule", "calendar", "캘린더",
                "오늘", "today", "내일", "tomorrow",
                "이번주", "this week", "다음주", "next week",
                "회의", "meeting", "약속", "appointment",
                "등록", "추가", "add", "register"
            ]
        }

        # 멀티 키워드 패턴 (더 높은 신뢰도)
        self.multi_keyword_patterns = {
            AgentType.PHD: [
                # Paper patterns
                ["논문", "검색"], ["paper", "search"],
                # Physics patterns
                ["DFT", "계산"], ["VASP", "계산"], ["ONETEP", "계산"],
                ["밴드", "구조"], ["band", "structure"],
                ["구조", "최적화"], ["relaxation", "계산"],
                ["Polaris", "submit"], ["HPC", "job"],
                # Phase 0: Email patterns DISABLED - use /mail command
                # ["메일", "학생"], ["email", "TA"]
            ],
            AgentType.LIFE: [
                ["운동", "기록"], ["workout", "log"]
            ],
            AgentType.SCHEDULE: [
                # Phase 1.5: Schedule patterns
                ["일정", "확인"], ["일정", "알려"], ["schedule", "today"],
                ["내일", "일정"], ["tomorrow", "schedule"],
                ["오늘", "일정"], ["today", "schedule"],
                ["회의", "등록"], ["meeting", "add"]
            ]
        }

        # Agent 우선순위 (애매할 때 기본값)
        self.default_agent = AgentType.PHD  # PhD 연구가 메인 작업

    def classify_intent(self, user_message: str) -> Intent:
        """
        사용자 메시지에서 Intent 분류

        Args:
            user_message: 사용자 입력 메시지

        Returns:
            Intent 객체 (agent, confidence, keywords_matched)
        """
        msg_lower = user_message.lower()

        # 1. 멀티 키워드 패턴 체크 (높은 신뢰도)
        for agent_type, patterns in self.multi_keyword_patterns.items():
            for pattern in patterns:
                if all(kw in msg_lower for kw in pattern):
                    return Intent(
                        agent=agent_type,
                        confidence=0.9,
                        keywords_matched=pattern,
                        original_message=user_message
                    )

        # 2. 단일 키워드 매칭
        agent_scores = {agent: [] for agent in AgentType}

        for agent_type, keywords in self.agent_keywords.items():
            for keyword in keywords:
                if keyword.lower() in msg_lower:
                    agent_scores[agent_type].append(keyword)

        # 3. 점수 계산
        max_score = 0
        best_agent = AgentType.UNKNOWN
        best_keywords = []

        for agent_type, matched_keywords in agent_scores.items():
            score = len(matched_keywords)
            if score > max_score:
                max_score = score
                best_agent = agent_type
                best_keywords = matched_keywords

        # 4. 신뢰도 계산
        if max_score == 0:
            confidence = 0.0
        elif max_score == 1:
            confidence = 0.6  # 단일 키워드만 매칭
        elif max_score == 2:
            confidence = 0.8
        else:
            confidence = 0.95  # 3개 이상 키워드 매칭

        return Intent(
            agent=best_agent,
            confidence=confidence,
            keywords_matched=best_keywords,
            original_message=user_message
        )

    def route_to_agent(self, intent: Intent) -> Dict:
        """
        Intent에 따라 적절한 Agent로 라우팅

        Args:
            intent: classify_intent()의 결과

        Returns:
            라우팅 결과 딕셔너리
        """
        result = {
            "agent": intent.agent.value,
            "confidence": intent.confidence,
            "keywords": intent.keywords_matched,
            "status": "routed"
        }

        # 신뢰도가 낮으면 사용자에게 확인 요청
        if intent.confidence < 0.5:
            result["status"] = "clarification_needed"
            result["message"] = self._generate_clarification_message(intent)
            return result

        # Agent별 라우팅
        if intent.agent == AgentType.PHD:
            result["handler"] = "phd_agent"
            result["module"] = "phd_agent.py"
        elif intent.agent == AgentType.SCHEDULE:
            # Phase 1.5: Schedule Agent
            result["handler"] = "schedule_agent"
            result["module"] = "schedule_agent.py"
        elif intent.agent == AgentType.LIFE:
            result["handler"] = "life_agent"
            result["status"] = "not_implemented"
            result["message"] = "Life-Agent는 아직 개발중입니다."
        elif intent.agent == AgentType.PERSONAL:
            result["handler"] = "personal_agent"
            result["status"] = "not_implemented"
            result["message"] = "Personal-Agent는 아직 개발중입니다."
        else:
            result["status"] = "unknown_intent"
            result["message"] = "어떤 작업을 도와드릴까요?\n\n가능한 작업:\n📚 논문 검색/분석\n📧 TA 메일 관리\n📅 일정 확인\n💰 지출 관리 (개발중)"

        return result

    def _generate_clarification_message(self, intent: Intent) -> str:
        """
        명확하지 않은 Intent에 대해 사용자에게 확인 메시지 생성
        """
        return f"""🤔 요청이 명확하지 않습니다.

다음 중 어떤 작업인가요?

1️⃣ 논문 검색/분석 (PhD-Agent)
2️⃣ 일정 확인 (Life-Agent)
3️⃣ 개인 작업 (Personal-Agent)

또는 더 구체적으로 말씀해주세요!
예: "MoS2 논문 검색해줘" """

    def estimate_cost(self, intent: Intent, use_claude: bool = False) -> Dict:
        """
        API 비용 추정

        Args:
            intent: 분류된 Intent
            use_claude: Claude API 사용 여부 (기본 Gemini 무료)

        Returns:
            비용 추정 결과
        """
        cost_estimate = {
            "api": "Gemini 2.5 Flash" if not use_claude else "Claude Sonnet 4.5",
            "estimated_cost": 0.0 if not use_claude else 0.15,  # Claude: ~$0.15/request
            "requires_approval": use_claude,
            "free_alternative": "Gemini" if use_claude else None
        }

        # Agent별 예상 비용 추가
        if intent.agent == AgentType.PHD:
            if "분석" in intent.original_message or "analyze" in intent.original_message.lower():
                cost_estimate["estimated_tokens"] = 5000  # 논문 분석 시
                if use_claude:
                    cost_estimate["estimated_cost"] = 0.25

        return cost_estimate

    def log_decision(self, intent: Intent, routing_result: Dict):
        """
        Orchestrator 결정 로그 (디버깅용)
        """
        log_entry = f"""
[Polaris Orchestrator Decision]
Message: {intent.original_message}
Agent: {intent.agent.value}
Confidence: {intent.confidence:.2f}
Keywords: {', '.join(intent.keywords_matched)}
Status: {routing_result['status']}
---
"""
        # TODO: 나중에 파일로 저장하거나 Obsidian에 기록
        print(log_entry)


# 테스트용 함수
def test_orchestrator():
    """Orchestrator 테스트"""
    orchestrator = PolarisOrchestrator()

    test_messages = [
        "MoS2 논문 검색해줘",
        "내일 일정 알려줘",
        "차 정비 언제 하지?",
        "TA 학생 메일 확인",
        "저녁 뭐먹지?",
        "DFT 계산 제출하고 싶어",
        "운동 기록 저장"
    ]

    print("🌟 Polaris Orchestrator Test\n")

    for msg in test_messages:
        print(f"📨 입력: {msg}")
        intent = orchestrator.classify_intent(msg)
        result = orchestrator.route_to_agent(intent)

        print(f"   → Agent: {result['agent']}")
        print(f"   → Confidence: {intent.confidence:.2f}")
        print(f"   → Status: {result['status']}")
        if 'message' in result:
            print(f"   → Message: {result['message'][:50]}...")
        print()


if __name__ == "__main__":
    test_orchestrator()
