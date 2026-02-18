"""
Polaris Core Router - LLM-powered ReAct Loop

Supports two backends:
  - Ollama (default, free) via OpenAI-compatible API
  - Anthropic (optional, paid) via native SDK

Backend is selected by POLARIS_LLM_BACKEND env var (default: "ollama").
Paid API calls require POLARIS_ALLOW_PAID_API=true.
"""

import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Default system prompt for the router
SYSTEM_PROMPT = """\
[LANGUAGE]
한국어로만 답변. 한자(漢字), 중국어, 일본어 금지.
전문 용어는 한글(영어) 형식 허용. 예: 엔트로피(Entropy)

[IDENTITY]
너는 Polaris. 종민이의 AI 비서이자 대화 상대야.
종민: UIC 물리학 박사과정, 시카고 거주 한국인.
할 수 있는 것: 논문 검색, 이메일 관리, VASP 시뮬레이션, 일정 관리, 일상 대화.

[TONE]
- 반말 전용. "~해", "~어", "~지" 사용. "~요", "~세요", "~합니다" 금지.
- 자연스러운 한국어 구어체. 번역투 금지.
- 일상 대화엔 가볍게 응대. 모든 대화를 연구로 돌리지 마.
- Tiki-Taka: 공감 후 반드시 관련 질문을 던져서 대화를 이어가.
- 사용자가 "잘 자" 등 종료 신호를 보내기 전에 절대 먼저 작별 인사 금지.

[RULES]
- 도구 결과의 고유명사(이름, 제목)는 그대로 전달. 임의 생성 금지.
- 도구 필요 시 도구 호출. 불필요 시 자연스럽게 대화.
- YAML frontmatter, tags 등 메타데이터 응답에 포함 금지."""

MAX_ITERATIONS = 10

# Backend configuration
OLLAMA_BASE_URL = "http://localhost:11434/v1"
OLLAMA_MODEL_FAST = "llama3.1:8b"       # Simple conversations (~3-5 sec)
OLLAMA_MODEL_FULL = "llama70b-lite"     # Tool calls, complex reasoning (~25-30 sec)
ANTHROPIC_MODEL = "claude-sonnet-4-5-20250929"


def _convert_tools_to_openai_format(anthropic_tools: list) -> list:
    """Convert Anthropic tool schemas to OpenAI function calling format.

    Anthropic: {"name": ..., "description": ..., "input_schema": {...}}
    OpenAI:    {"type": "function", "function": {"name": ..., "description": ..., "parameters": {...}}}
    """
    openai_tools = []
    for tool in anthropic_tools:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("input_schema", {"type": "object", "properties": {}}),
            },
        })
    return openai_tools


class PolarisRouter:
    """
    LLM-powered router with ReAct loop.

    Default backend is Ollama (free, local). Anthropic is available
    but requires explicit opt-in via environment variables.
    """

    def __init__(
        self,
        backend: Optional[str] = None,
        model: Optional[str] = None,
        max_iterations: int = MAX_ITERATIONS,
    ):
        self.max_iterations = max_iterations
        self.backend = backend or os.getenv("POLARIS_LLM_BACKEND", "ollama")
        self.allow_paid = os.getenv("POLARIS_ALLOW_PAID_API", "false").lower() == "true"

        if self.backend == "anthropic":
            self.model = model or ANTHROPIC_MODEL
            self._init_anthropic()
        else:
            self.model_fast = OLLAMA_MODEL_FAST
            self.model_full = OLLAMA_MODEL_FULL
            self.model = model or self.model_fast  # default to fast
            self._init_ollama()

        self.tools = []
        self._load_tools()

        self.memory = None
        self._init_memory()

        self.feedback_manager = None
        self._init_feedback()

        self.fact_extractor = None
        self._init_fact_extractor()

        self.vault_reader = None
        self._init_vault_reader()

        self.skill_registry = None
        self._init_skills()

    # ------------------------------------------------------------------
    # Backend initialisation
    # ------------------------------------------------------------------

    def _init_ollama(self):
        """Initialise the Ollama (OpenAI-compatible) client."""
        from openai import OpenAI
        self.client = OpenAI(
            base_url=OLLAMA_BASE_URL,
            api_key="ollama",
        )
        logger.info("Using Ollama backend (%s) at %s", self.model, OLLAMA_BASE_URL)

    def _init_anthropic(self):
        """Initialise the Anthropic client (paid, requires opt-in)."""
        import anthropic
        self.client = anthropic.Anthropic()
        logger.info("Using Anthropic backend (%s)", self.model)

    # ------------------------------------------------------------------
    # Memory
    # ------------------------------------------------------------------

    def _init_memory(self):
        """Initialise the memory system (optional — degrades gracefully)."""
        try:
            from polaris.memory import PolarisMemory
            self.memory = PolarisMemory()
            logger.info("Memory system initialised")
        except Exception as e:
            logger.warning("Memory system unavailable: %s", e)
            self.memory = None

    # ------------------------------------------------------------------
    # Feedback
    # ------------------------------------------------------------------

    def _init_feedback(self):
        """Initialise the feedback manager (optional — degrades gracefully)."""
        if not self.memory:
            return
        try:
            from polaris.memory.feedback_manager import FeedbackManager
            self.feedback_manager = FeedbackManager(self.memory)
            logger.info("Feedback manager initialised")
        except Exception as e:
            logger.warning("Feedback manager unavailable: %s", e)
            self.feedback_manager = None

    # ------------------------------------------------------------------
    # Fact Extractor
    # ------------------------------------------------------------------

    def _init_fact_extractor(self):
        """Initialise the fact extractor (optional — degrades gracefully)."""
        if not self.memory:
            return
        try:
            from polaris.memory.fact_extractor import FactExtractor
            from polaris.memory.obsidian_writer import ObsidianWriter
            writer = ObsidianWriter()
            self.fact_extractor = FactExtractor(memory=self.memory, obsidian_writer=writer)
            logger.info("Fact extractor initialised")
        except Exception as e:
            logger.warning("Fact extractor unavailable: %s", e)
            self.fact_extractor = None

    # ------------------------------------------------------------------
    # Vault Reader
    # ------------------------------------------------------------------

    def _init_vault_reader(self):
        """Initialise the vault reader (optional — degrades gracefully)."""
        if not self.memory:
            return
        try:
            from polaris.memory.vault_reader import VaultReader
            self.vault_reader = VaultReader(memory=self.memory)
            logger.info("Vault reader initialised")
        except Exception as e:
            logger.warning("Vault reader unavailable: %s", e)
            self.vault_reader = None

    # ------------------------------------------------------------------
    # Skills
    # ------------------------------------------------------------------

    def _init_skills(self):
        """Initialise the skills system (optional — degrades gracefully)."""
        try:
            from polaris.skills import SkillRegistry
            self.skill_registry = SkillRegistry()

            external_paths = []
            env_paths = os.environ.get("POLARIS_EXTERNAL_SKILLS", "")
            if env_paths:
                external_paths.extend([p for p in env_paths.split(":") if p.strip()])
            external_paths.extend(["~/.openclaw/skills", "~/.claude/skills"])
            external_count = self.skill_registry.register_external_skills(external_paths)

            count = len(self.skill_registry.list_all())
            if count:
                logger.info(
                    "Skills system initialised (%d skills, %d external)",
                    count,
                    external_count,
                )
            else:
                logger.info("Skills system initialised (no skills found)")
        except Exception as e:
            logger.warning("Skills system unavailable: %s", e)
            self.skill_registry = None

    # ------------------------------------------------------------------
    # Tool loading
    # ------------------------------------------------------------------

    # Keyword map for smart tool selection.
    # Only tools whose keywords match the user message are sent to the LLM.
    # This dramatically reduces input tokens (13 tools = ~1700 tokens overhead).
    TOOL_KEYWORDS = {
        "search_arxiv": ["arxiv", "paper", "논문", "검색", "연구", "search"],
        "search_semantic_scholar": ["paper", "논문", "semantic", "scholar", "검색"],
        "download_paper_pdf": ["download", "pdf", "다운로드", "다운"],
        "analyze_paper_gemini": ["analyze", "분석", "paper", "논문"],
        "analyze_paper_claude": ["analyze", "분석", "paper", "논문"],
        "get_calendar_briefing": ["calendar", "schedule", "일정", "캘린더", "스케줄", "오늘 일정", "내일 일정"],
        "add_calendar_event": ["calendar", "event", "일정 추가", "약속 추가", "일정 등록"],
        "analyze_emails": ["email", "mail", "이메일", "메일"],
        "analyze_single_email": ["email", "mail", "이메일", "메일"],
        "fetch_mail_digest": ["메일", "이메일", "요약", "digest", "inbox"],
        "fetch_urgent_mails": ["긴급", "urgent", "메일", "이메일"],
        "fetch_promo_deals": ["딜", "프로모션", "할인", "coupon", "deal"],
        "propose_mail_actions": ["메일 정리", "정리", "archive", "라벨", "actions"],
        "execute_mail_actions": ["정리 실행", "archive", "라벨 적용", "mark read"],
        "monitor_hpc_job": ["hpc", "job", "vasp", "계산", "클러스터", "잡"],
        "check_hpc_connection": ["hpc", "connection", "ssh", "폴라리스", "서버"],
        "physics_agent_handle": ["physics", "물리", "vasp", "dft", "시뮬레이션"],
        "phd_agent_handle": ["phd", "박사", "연구 진행"],
    }

    def _load_tools(self):
        """Auto-load tool definitions from polaris.tools registry."""
        try:
            from polaris.tools import get_all_tools
            self.tools = get_all_tools()
            logger.info("Loaded %d tools from polaris.tools", len(self.tools))
        except ImportError:
            logger.warning("polaris.tools not available; running without tools")
            self.tools = []
        except Exception as e:
            logger.error("Failed to load tools: %s", e)
            self.tools = []

    def _select_relevant_tools(self, message: str) -> list:
        """Select only tools relevant to the user message.

        Reduces input tokens from ~3000 to ~200-500 for simple messages.
        A plain greeting sends zero tools; "arxiv 논문 검색" sends only 2-3.
        """
        if not self.tools:
            return []

        msg_lower = message.lower()
        relevant = []
        for tool in self.tools:
            keywords = self.TOOL_KEYWORDS.get(tool["name"], [])
            if any(kw in msg_lower for kw in keywords):
                relevant.append(tool)

        if relevant:
            logger.info(
                "Selected %d/%d tools for message: %s",
                len(relevant), len(self.tools),
                [t["name"] for t in relevant],
            )
        else:
            logger.info("No tools selected — pure conversation mode")
        return relevant

    def _get_tools_by_name(self, tool_names: list[str]) -> list:
        """Return registered tool definitions by exact name."""
        wanted = set(tool_names)
        return [tool for tool in self.tools if tool["name"] in wanted]

    def _resolve_skill_enforcement(self, matched_skills: list[dict]) -> dict:
        """Build enforcement policy from matched skills."""
        requires_tool = False
        strict_mode = False
        allowed_tools: list[str] = []
        chain_tools: list[str] = []
        preflight_tools: list[str] = []
        known_tools = {t["name"]: t for t in self.tools}

        for skill in matched_skills:
            if not skill.get("requires_tool", False):
                continue
            requires_tool = True
            strict_mode = strict_mode or skill.get("strict_mode", True)

            tool_chain = skill.get("tool_chain", []) or []
            tools_required = skill.get("tools_required", []) or []
            ordered = tool_chain if tool_chain else tools_required
            for name in ordered:
                if name not in allowed_tools:
                    allowed_tools.append(name)
                if name not in chain_tools:
                    chain_tools.append(name)
                tool_def = known_tools.get(name)
                if not tool_def:
                    continue
                required = tool_def.get("input_schema", {}).get("required", [])
                if not required and name not in preflight_tools:
                    preflight_tools.append(name)

        return {
            "requires_tool": requires_tool,
            "strict_mode": strict_mode,
            "allowed_tools": allowed_tools,
            "chain_tools": chain_tools,
            "preflight_tools": preflight_tools,
        }

    def _execute_preflight_tools(self, tool_names: list[str]) -> list[dict]:
        """Execute zero-argument tools before the main LLM turn."""
        results = []
        for name in tool_names:
            result_text = self._execute_tool(name, {})
            results.append({
                "name": name,
                "content": result_text,
                "ok": not self._looks_like_tool_error(result_text),
            })
        return results

    def _looks_like_tool_error(self, result_text: str) -> bool:
        """Best-effort check for tool failure payloads."""
        lower = (result_text or "").lower()
        return (
            "tool '" in lower and "failed" in lower
        ) or '"error"' in lower or "'error'" in lower

    # ------------------------------------------------------------------
    # Main routing
    # ------------------------------------------------------------------

    def route(
        self,
        message: str,
        conversation_history: Optional[list] = None,
        session_id: str = "",
    ) -> dict:
        """
        Route a user message through the ReAct loop.

        Args:
            message: The user's message.
            conversation_history: Prior messages as
                [{"role": "user"|"assistant", "content": "..."}].
            session_id: Optional session identifier for memory persistence.

        Returns:
            {"response": str, "tools_used": list[str]}
        """
        # NOTE: Memory save is deferred to AFTER the LLM response.
        # This prevents model swapping (nomic-embed-text ↔ llama70b)
        # which was causing ~60s load time per message on 42GB model.

        # Store session_id for _build_system_prompt to read recent conversations
        self._current_session_id = session_id

        if self.backend == "anthropic":
            if not self.allow_paid:
                return {
                    "response": (
                        "This request requires a paid API (Anthropic). "
                        "Set POLARIS_ALLOW_PAID_API=true to enable, "
                        "or use the default Ollama backend."
                    ),
                    "tools_used": [],
                }
            result = self._route_anthropic(message, conversation_history)
        else:
            result = self._route_ollama(message, conversation_history)

        # Detect and save corrections (before memory save, after LLM response)
        if self.feedback_manager and session_id:
            try:
                if self.feedback_manager.detect_correction(message):
                    # Extract last assistant response from conversation history
                    prev_response = ""
                    if conversation_history:
                        for msg in reversed(conversation_history):
                            if msg.get("role") == "assistant":
                                prev_response = msg.get("content", "")
                                break
                    self.feedback_manager.save_correction(
                        session_id=session_id,
                        original_response=prev_response,
                        user_correction=message,
                    )
                    logger.info("Correction detected and saved for session %s", session_id)
            except Exception as e:
                logger.debug("Correction detection failed: %s", e)

        # Save BOTH messages to memory AFTER the LLM response.
        # Embedding calls happen here, but llama70b is already done.
        if self.memory and session_id:
            try:
                self.memory.save_conversation(session_id, "user", message)
            except Exception as e:
                logger.warning("Failed to save user message to memory: %s", e)
            if result.get("response"):
                try:
                    self.memory.save_conversation(session_id, "assistant", result["response"])
                except Exception as e:
                    logger.warning("Failed to save assistant response to memory: %s", e)

        # Fact extraction (after memory save, synchronous — regex only, no LLM)
        if self.fact_extractor and session_id:
            try:
                if self.fact_extractor.should_extract(message):
                    facts = self.fact_extractor.extract_facts(
                        user_message=message,
                        bot_response=result.get("response", ""),
                        session_id=session_id,
                    )
                    if facts:
                        saved = self.fact_extractor.save_and_update(facts)
                        logger.info("Extracted and saved %d facts from session %s", saved, session_id)
            except Exception as e:
                logger.debug("Fact extraction failed: %s", e)

        return result

    # ------------------------------------------------------------------
    # Ollama (OpenAI-compatible) backend
    # ------------------------------------------------------------------

    def _build_system_prompt(self, message: str, has_tools: bool = False) -> str:
        """Build system prompt with persona + skills + tool examples + recent context.

        Layers:
        1. SYSTEM_PROMPT (always) — language, identity, tone, rules
        2. 00_PERSONA + 99_SYSTEM from master_prompt — personality & few-shot
        3. Matched skills (max 2) — task-specific guidance
        4. Few-shot tool examples (only when tools present)
        5. Recent conversation context (DB read, no embedding)
        """
        prompt = SYSTEM_PROMPT

        # Inject persona + few-shot tone examples from master_prompt
        try:
            from polaris.memory.obsidian_writer import ObsidianWriter
            writer = ObsidianWriter()
            persona = writer.read_master_prompt_section("00_PERSONA")
            if persona:
                prompt += f"\n\n{persona.strip()}"
            fewshot = writer.read_master_prompt_section("99_SYSTEM")
            if fewshot:
                prompt += f"\n\n{fewshot.strip()}"
        except Exception as e:
            logger.debug("Master prompt injection skipped: %s", e)

        # Inject matching skills (max 2 to control token budget)
        if self.skill_registry:
            try:
                matched_skills = self.skill_registry.match(message)
                for skill_info in matched_skills[:2]:
                    skill_prompt = self.skill_registry.get_prompt(skill_info["name"])
                    if skill_prompt:
                        prompt += f"\n\n[SKILL: {skill_info['name']}]\n{skill_prompt}"
                        logger.info("Injected skill: %s", skill_info["name"])
            except Exception as e:
                logger.debug("Skill injection skipped: %s", e)

        # Few-shot examples only when tools are available (helps 70B pick correctly)
        if has_tools:
            prompt += """

[FEW-SHOT EXAMPLES]
User: "오늘 일정 알려줘" -> Call: get_calendar_briefing
User: "MoS2 논문 찾아줘" -> Call: search_arxiv(query="MoS2")
User: "이메일 확인해줘" -> Call: analyze_emails
User: "안녕? 잘 지내?" -> No tool needed, respond directly."""

        if self.memory:
            # Inject recent conversation history (DB read, no embedding)
            try:
                recent = self.memory.get_recent_conversations(
                    session_id=getattr(self, '_current_session_id', ''),
                    limit=5,
                )
                if recent:
                    parts = [f"[{r['role']}] {r['content'][:200]}" for r in recent]
                    prompt += (
                        "\n\n--- Recent conversation ---\n"
                        + "\n".join(parts)
                        + "\n--- End conversation ---"
                    )
            except Exception as e:
                logger.warning("Failed to retrieve recent conversations: %s", e)

        # Layer 6: Vault knowledge (from indexed Obsidian notes)
        if self.vault_reader:
            try:
                vault_results = self.vault_reader.search_vault_knowledge(message, top_k=2)
                if vault_results:
                    parts = []
                    for vr in vault_results:
                        parts.append(f"- {vr['title']}: {vr['content'][:500]}")
                    prompt += (
                        "\n\n[참고: 내 노트에서]\n"
                        + "\n".join(parts)
                    )
            except Exception as e:
                logger.debug("Vault knowledge injection skipped: %s", e)

        # Layer 7: Feedback caution block (closest to user message)
        if self.feedback_manager:
            try:
                feedbacks = self.feedback_manager.get_relevant_feedback(message, top_k=3)
                caution = self.feedback_manager.format_as_caution(feedbacks)
                if caution:
                    prompt += f"\n\n{caution}"
            except Exception as e:
                logger.debug("Feedback injection skipped: %s", e)

        return prompt

    def _route_ollama(
        self,
        message: str,
        conversation_history: Optional[list] = None,
    ) -> dict:
        """ReAct loop using the OpenAI-compatible API (Ollama)."""
        from openai import OpenAI, APIError, AuthenticationError

        tools_used: list[str] = []
        successful_tools: list[str] = []
        matched_skills = self.skill_registry.match(message) if self.skill_registry else []
        enforcement = self._resolve_skill_enforcement(matched_skills)

        if enforcement["requires_tool"] and enforcement["allowed_tools"]:
            relevant_tools = self._get_tools_by_name(enforcement["allowed_tools"])
        else:
            relevant_tools = self._select_relevant_tools(message)

        if enforcement["requires_tool"] and not relevant_tools:
            return {
                "response": (
                    "이 요청은 도구 실행이 필수인데, 사용 가능한 스킬 도구를 찾지 못했어. "
                    "스킬 설정(tool_chain/tools_required)을 확인해줘."
                ),
                "tools_used": [],
            }

        openai_tools = _convert_tools_to_openai_format(relevant_tools) if relevant_tools else None

        system_prompt = self._build_system_prompt(message, has_tools=bool(relevant_tools))
        if enforcement["requires_tool"]:
            chain = ", ".join(enforcement["chain_tools"])
            system_prompt += (
                "\n\n[SKILL TOOL ENFORCEMENT]\n"
                "이 요청은 스킬 정책상 도구 호출이 필수야. "
                "도구 결과 없이 추정 답변을 만들면 안 돼. "
                "필수 체인(순서): "
                f"{chain if chain else '없음'}.\n"
                "필수 인자가 부족하면 임의로 채우지 말고 사용자에게 추가 정보를 요청해."
            )

        preflight_results = self._execute_preflight_tools(enforcement["preflight_tools"])
        if preflight_results:
            prompt_lines = ["[PREFLIGHT TOOL RESULTS]"]
            for item in preflight_results:
                tools_used.append(item["name"])
                if item["ok"]:
                    successful_tools.append(item["name"])
                prompt_lines.append(f"- {item['name']}: {item['content'][:500]}")
            system_prompt += "\n" + "\n".join(prompt_lines)

        messages = [{"role": "system", "content": system_prompt}]
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": message})

        # Dual-model: use fast 8B for chat, full 70B for tool calls
        active_model = self.model_full if relevant_tools else self.model_fast
        logger.info("Using model: %s (tools=%d)", active_model, len(relevant_tools))

        for iteration in range(self.max_iterations):
            logger.debug("ReAct iteration %d/%d (ollama)", iteration + 1, self.max_iterations)

            try:
                kwargs = {
                    "model": active_model,
                    "messages": messages,
                    "max_tokens": 4096,
                }
                if openai_tools:
                    kwargs["tools"] = openai_tools

                response = self.client.chat.completions.create(**kwargs)
            except AuthenticationError:
                logger.error("OpenAI-compatible auth failed")
                return {
                    "response": "Authentication error: please check the API configuration.",
                    "tools_used": tools_used,
                }
            except APIError as e:
                logger.error("OpenAI-compatible API error: %s", e)
                return {
                    "response": f"API error: {e}",
                    "tools_used": tools_used,
                }

            choice = response.choices[0]

            # Check for tool calls
            if choice.finish_reason == "tool_calls" or (
                choice.message.tool_calls and len(choice.message.tool_calls) > 0
            ):
                # Append assistant message with tool calls
                messages.append(choice.message)

                for tool_call in choice.message.tool_calls:
                    tool_name = tool_call.function.name
                    try:
                        tool_args = json.loads(tool_call.function.arguments)
                    except (json.JSONDecodeError, TypeError):
                        tool_args = {}

                    logger.info("Tool call: %s(%s)", tool_name, tool_args)
                    tools_used.append(tool_name)

                    result_text = self._execute_tool(tool_name, tool_args)
                    if not self._looks_like_tool_error(result_text):
                        successful_tools.append(tool_name)

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result_text,
                    })
                continue

            # No tool calls — final answer
            final_text = choice.message.content or ""
            if enforcement["requires_tool"] and not successful_tools:
                return {
                    "response": (
                        "이 요청은 도구 실행 결과가 있어야 답변할 수 있어. "
                        "현재 도구 호출이 없었거나 모두 실패해서 추정 답변은 제공하지 않을게."
                    ),
                    "tools_used": tools_used,
                }
            return {"response": final_text, "tools_used": tools_used}

        # Exhausted iterations
        logger.warning("ReAct loop hit max iterations (%d)", self.max_iterations)
        fallback = choice.message.content or (
            "I was unable to complete the request within the allowed steps."
        )
        return {"response": fallback, "tools_used": tools_used}

    # ------------------------------------------------------------------
    # Anthropic backend (paid, opt-in)
    # ------------------------------------------------------------------

    def _route_anthropic(
        self,
        message: str,
        conversation_history: Optional[list] = None,
    ) -> dict:
        """ReAct loop using the native Anthropic API."""
        import anthropic

        messages = list(conversation_history) if conversation_history else []
        messages.append({"role": "user", "content": message})

        tools_used: list[str] = []

        relevant_tools = self._select_relevant_tools(message)

        api_kwargs = {
            "model": self.model,
            "max_tokens": 4096,
            "system": self._build_system_prompt(message, has_tools=bool(relevant_tools)),
        }
        if relevant_tools:
            api_kwargs["tools"] = relevant_tools

        for iteration in range(self.max_iterations):
            logger.debug("ReAct iteration %d/%d (anthropic)", iteration + 1, self.max_iterations)

            try:
                response = self.client.messages.create(
                    messages=messages,
                    **api_kwargs,
                )
            except anthropic.AuthenticationError:
                logger.error("Anthropic authentication failed — check ANTHROPIC_API_KEY")
                return {
                    "response": "Authentication error: please check the API key configuration.",
                    "tools_used": tools_used,
                }
            except anthropic.APIError as e:
                logger.error("Anthropic API error: %s", e)
                return {
                    "response": f"API error: {e}",
                    "tools_used": tools_used,
                }

            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": response.content})

                tool_results = []
                for block in response.content:
                    if block.type != "tool_use":
                        continue

                    tool_name = block.name
                    tool_input = block.input
                    tool_use_id = block.id

                    logger.info("Tool call: %s(%s)", tool_name, tool_input)
                    tools_used.append(tool_name)

                    result_text = self._execute_tool(tool_name, tool_input)

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": result_text,
                    })

                messages.append({"role": "user", "content": tool_results})
                continue

            # Final answer
            text_parts = [
                block.text for block in response.content if block.type == "text"
            ]
            final_text = "\n".join(text_parts) if text_parts else ""
            return {"response": final_text, "tools_used": tools_used}

        # Exhausted iterations
        logger.warning("ReAct loop hit max iterations (%d)", self.max_iterations)
        text_parts = [
            block.text for block in response.content
            if block.type == "text"
        ]
        fallback = "\n".join(text_parts) if text_parts else (
            "I was unable to complete the request within the allowed steps."
        )
        return {"response": fallback, "tools_used": tools_used}

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------

    def _execute_tool(self, name: str, args: dict) -> str:
        """Execute a tool by name and return its result as a string.

        Errors are returned as text so the LLM can observe and recover.
        """
        try:
            from polaris.tools import execute_tool
            result = execute_tool(name, args)
            return str(result)
        except ImportError:
            msg = "Tool execution unavailable (polaris.tools not loaded)"
            logger.error(msg)
            return msg
        except Exception as e:
            msg = f"Tool '{name}' failed: {e}"
            logger.error(msg)
            return msg
