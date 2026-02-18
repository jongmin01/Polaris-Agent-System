# Polaris Agent System

## Architecture
- `polaris/bot_v2.py` — Telegram bot (entry point: `python -m polaris.bot_v2`), handler 등록 + 오케스트레이션만 담당
- `polaris/router.py` — LLM ReAct loop (Ollama default, Anthropic optional) + memory context injection
- `polaris/tools/` — 13 tools in 5 modules + auto-discovery registry
- `polaris/approval_gate.py` — Risk-based gate (AUTO/CONFIRM/CRITICAL)
- `polaris/trace_logger.py` — SQLite audit trail at data/trace.db
- `polaris/memory/` — Second Brain (conversations, knowledge, feedback, semantic search)
- `polaris/skills/` — Markdown 기반 스킬 시스템 (9+ skills, trigger matching, router injection)
- `polaris/mailops/` — Apple Mail 통합 (MailOpsService + MailOpsPoller)
- `polaris/services/` — 독립 서비스 모듈
  - `hot_reload.py`: HotReloader (파일 감시, 런타임 리로드)
  - (추후 확장용)

## Key Rules
- 기존 루트 .py 파일 수정 금지 (orchestrator.py, polaris_bot.py 등)
  - **예외**: deprecation 경고 주석/로그 추가만 허용 (2026-03-31 까지 read-only)
  - **삭제 일정**: 2026-04-15 — 삭제 조건: README/운영 스크립트 레거시 경로 참조 0건 + bot_v2.py 기능 검증 완료
- 테스트는 API 키 없이 실행 가능해야 함
- POLARIS_LLM_BACKEND=ollama 가 기본값 (무료)
- 유료 API 호출 시 반드시 사용자 승인 필요
- 임베딩은 Ollama nomic-embed-text만 사용 (무료 로컬)
- SSH 인증(비밀번호/MFA/OTP)은 반드시 사용자가 직접 수행 (Polaris 대리 입력 금지)
- Telegram 채팅으로 OTP를 받아 SSH 프롬프트에 입력하는 방식은 기술적으로 가능해도 보안/정책 준수 목적상 폐기
- Polaris의 SSH 역할은 접속 상태 점검/실패 감지/재인증 필요 알림으로 제한

## Structural DoD (구조 부채 해소 기준)

3개 모두 충족 시 "구조 부채 해소" 완료로 판정:
- [ ] `bot_v2.py` 350줄 이하
- [ ] 레거시 runtime import 0개 (`MailReader`/`EmailAnalyzer`/`PhDAgent`/`ScheduleAgent` import in `bot_v2.py`)
- [ ] `./check_legacy_refs.sh` 통과 (운영 스크립트 레거시 경로 참조 0건)

## Running Tests
```bash
python -m pytest tests/ -v
```

## Progress

### Phase 3.7: HPC 운영 UX 전환 + 멀티클러스터 설정화 ✅ (2026-02-18)

**운영 정책/UX 변경:**
- [x] `/physics*` 등록-의존 흐름 폐기, `/hpc` 단일 명령 중심으로 전환
- [x] `/hpc [status|jobs] [cluster]` 지원
  - `status`: SSH 연결 상태 확인
  - `jobs`: 현재 큐 작업 즉시 조회 (`jobid-state` 요약)
- [x] 연결 안내 문구 정리
  - profile/host 중복 시 단일 표기 (예: `polaris`)
  - 추천 명령(`/hpc jobs`)은 별도 줄로 출력

**코드/구조 변경:**
- [x] `physics_monitor.py` → `hpc_monitor.py` 리네임
- [x] 모니터 클래스 `HPCMonitor` 도입 (`PhysicsMonitor` 별칭으로 호환 유지)
- [x] `hpc_monitor.py`에 `list_jobs()` 추가 (PBS/Slurm 파서 포함)
- [x] `polaris/bot_v2.py`에서 `hpc_monitor` import로 전환
- [x] `polaris/tools/hpc_tools.py`, `polaris_bot.py` import 경로 동기화

**설정 체계 일반화:**
- [x] 메일 계정 선택: `MAIL_ACCOUNT_KEYWORDS` (콤마 구분) 지원
- [x] HPC 단일/다중 프로파일 동시 지원
  - `HPC_HOST`, `HPC_USERNAME`, `HPC_SCHEDULER`
  - `HPC_REMOTE_PATH` (비대화식 SSH PATH 보강)
  - `HPC_ACTIVE_PROFILE`, `HPC_PROFILES_JSON`

**문서 반영:**
- [x] `README.md` 명령/설정 예시를 `/hpc` 중심으로 갱신
- [x] `.env.example`에 `MAIL_ACCOUNT_KEYWORDS`, 멀티클러스터 설정 예시 및 Apple Mail 계정명 확인 명령 주석 추가

### Phase 1: Core 리팩토링 ✅ (2026-02-08 완료)
- [x] polaris/router.py — LLM 기반 ReAct 루프 (Ollama default + Anthropic opt-in)
- [x] polaris/tools/ — 6 파일, 13 도구 등록 (auto-discovery registry)
- [x] polaris/approval_gate.py — AUTO/CONFIRM/CRITICAL 3단계 (201줄)
- [x] polaris/trace_logger.py — SQLite 판단 기록 (116줄)
- [x] polaris/bot_v2.py — Telegram 연동 (PolarisRouter 사용)
- [x] router.py Ollama 전환 — llama3.3:70b 로컬 (완전 무료)
- [x] 유료 API 안전장치 — POLARIS_ALLOW_PAID_API=false 기본

환경 설정 기록:
- Ollama: llama3.3:70b (Modelfile: llama70b-lite, num_ctx=32768)
- Mac Mini M4 Pro 64GB, 메모리 ~48GB 사용
- Telegram 자연어 대화 + 도구 호출 (arxiv 검색) 동작 확인
- 응답 시간: 단순 대화 ~1분, 도구 호출 ~3분

### Phase 2: Memory + Second Brain ✅ (2026-02-08 완료)
- [x] polaris/memory/schema.sql — 4 테이블 (conversations, traces, knowledge, feedback)
- [x] polaris/memory/embedder.py — Ollama nomic-embed-text 로컬 임베딩 + batch_embed
- [x] polaris/memory/memory.py — PolarisMemory (시맨틱 검색 + 키워드 fallback + user profile)
- [x] polaris/memory/obsidian_writer.py — Obsidian vault 직접 쓰기 (save_note, save_paper_note, save_daily_log)
- [x] master_prompt.md 연동 — 00_CORE → 시스템 프롬프트 주입, 99_CURRENT_CONTEXT만 업데이트
- [x] router.py 메모리 연결 — user profile + relevant memories 시스템 프롬프트 주입
- [x] bot_v2.py session_id 연결 — Telegram 대화 → SQLite 자동 저장
- [x] corrections.jsonl → feedback 테이블 마이그레이션
- [x] Obsidian vault 경로 수정 — ~/Library/Mobile Documents/iCloud~md~obsidian/Documents
- [x] obsidian_writer.py 섹션 추출 regex 버그 수정
- [x] tests — 전체 93개 통과 (기존 50 + 메모리 43)

동작 확인 기록:
- Telegram 대화 → data/polaris_memory.db conversations 테이블 저장 확인
- master_prompt.md 00_CORE 섹션 추출 + 시스템 프롬프트 주입 확인
- 99_CURRENT_CONTEXT 업데이트 시 다른 섹션 보존 확인
- MASTER_PROMPT_PATH=data/master_prompt.md (프로젝트 내 관리)

### Phase 2.5: 속도 최적화 + 프롬프트 재구조화 ✅ (2026-02-09 완료)

**속도 최적화 (완료):**
- [x] Embedding 후순위 — LLM 응답 후에 memory 저장 (모델 스왑 방지)
- [x] Smart tool selection — 키워드 매칭으로 관련 도구만 전송 (13→0~4개)
- [x] 듀얼 모델 라우팅 — llama3.1:8b (일반대화 ~14초) + llama70b-lite (도구 호출)
- [x] OLLAMA_MAX_LOADED_MODELS=3 (8B + 70B + nomic 동시 로드)
- [x] bot_v2.py Markdown fallback — 깨진 마크다운 시 plain text 전환

**프롬프트 재구조화 (완료):**
- [x] Step 1: 시스템 프롬프트 재설계 — 언어 제약 + 정체성만, 포맷 지침 제거
- [x] Step 2: 도구 description 축약 — 13개 도구 한국어 축약 + "NOT for" 가이드 추가
- [x] Step 3: 70B용 few-shot 4개 — _build_system_prompt에 도구 선택 예시 포함
- [x] Step 4: Modelfile SYSTEM 프롬프트 제거 — router.py에서 통합 관리 (모델 재생성 완료)
- [x] Step 5: pytest 93개 통과 확인

### Phase 2.6: 페르소나 + 말투 개선 ✅ (2026-02-09 완료)

**진단 1차 (v3.0)**: "연구 보조 AI" 정체성 → 모든 대화를 연구로 유도, "간결하게 답변" → 대화 톤 사망
**진단 2차 (v3.1)**: "도구 불필요 시 바로 답변" → 모델이 "답변할 것 없다 → Bye" 로 해석 (Bye 버그)
**진단 3차 (v3.2)**: 공감만 하고 follow-up 질문 없음 → "그렇라구요! 잘 자요!" 식 종료

**변경 사항:**
- [x] SYSTEM_PROMPT [TONE] — Tiki-Taka + Never End First + 반말 종결어미 명시
- [x] master_prompt.md v3.2 (MIT Framework) — 대화 로직, 반말 검증, Few-shot 7개, 금지 패턴 6개
- [x] _build_system_prompt — 00_PERSONA + 99_SYSTEM 동시 주입 (~1080 토큰)
- [x] pytest 93개 통과
- [x] Telegram 테스트 — 속도 개선 확인, 한자 제거 확인, 말투 개선 확인 (8B 모델 한계 내)

잔여 이슈: 8B 모델 특성상 미세한 어색함 존재 — 프롬프트로 해결 불가, Phase 3 Self-Learning으로 점진 개선 예정

### Phase 2.7: 스킬 시스템 ✅ (2026-02-10 완료)

**구조:**
- `polaris/skills/__init__.py` — SkillLoader, SkillRegistry export
- `polaris/skills/skill_loader.py` — Markdown + YAML frontmatter 파싱, 트리거 매칭, 프롬프트 추출
- `polaris/skills/registry.py` — 스킬 인덱싱 + 검색 인터페이스
- `skills/` — 6개 스킬 마크다운 파일 + README.md

**6개 스킬:**
- `vasp_convergence.md` — VASP 수렴 확인 (OSZICAR, Janus TMDC)
- `arxiv_analysis.md` — 논문 분석 (5가지 관점)
- `paper_to_obsidian.md` — 논문 → Obsidian 노트 변환
- `email_triage.md` — 이메일 URGENT/NORMAL/FYI 분류
- `hpc_monitor.md` — HPC 작업 모니터링 + VASP 에러 진단
- `daily_briefing.md` — 일일 브리핑 (일정/HPC/메일/논문)

**완료 항목:**
- [x] Task 1: polaris/skills/ 모듈 (skill_loader.py + registry.py)
- [x] Task 2: skills/README.md (스킬 형식 가이드)
- [x] Task 3: 6개 스킬 파일 작성
- [x] Task 4: router.py 연동 — _init_skills() + _build_system_prompt에 스킬 주입 (max 2)
- [x] Task 5: bot_v2.py 연동 — /skills 커맨드 + 핸들러 등록 + help 텍스트 + BotCommand
- [x] Task 6: tests/test_skills.py — 24개 테스트 (Loader 12 + Registry 6 + Router 4 + Integration 2)
- [x] 전체 pytest 117개 통과 (기존 93 + 스킬 24)

### Phase 3 Step 1: Aha! Memory (피드백 루프) ✅ (2026-02-11 완료)

**구조:**
- `polaris/memory/feedback_manager.py` — FeedbackManager (교정 감지, 저장, 검색, 포맷)
- `polaris/memory/schema.sql` — feedback 테이블 확장 (embedding, session_id, category)

**기능:**
- `detect_correction()` — 30+ regex 패턴 (Korean + English) 자동 감지
- `save_correction()` — 교정 내용 + 임베딩 저장 (시맨틱 검색용)
- `get_relevant_feedback()` — 시맨틱 검색 (fallback: 최신순)
- `format_as_caution()` — "[주의: 과거 실수 기록]" 블록 생성 (max 3개, 각 60자)
- `/wrong` — Telegram 커맨드: 직전 응답 교정
- `/feedback` — Telegram 커맨드: 최근 피드백 목록

**완료 항목:**
- [x] schema.sql — feedback 테이블에 embedding, session_id, category 컬럼 추가
- [x] feedback_manager.py — FeedbackManager (detect, save, search, format) + ALTER TABLE 마이그레이션
- [x] memory/__init__.py — FeedbackManager export
- [x] router.py — _init_feedback() + _build_system_prompt Layer 6 + route() 교정 감지
- [x] bot_v2.py — /wrong, /feedback 커맨드 + awaiting_correction 상태 관리
- [x] tests/test_feedback.py — 30개 테스트 (Detection 10 + Save 4 + Search 4 + Format 4 + Count 3 + Migration 2 + Router 3)
- [x] 전체 pytest 147개 통과 (기존 117 + 피드백 30)

### Phase 3 Step 2: Fact Extractor (대화 → 지식 추출) ✅ (2026-02-11 완료)

**구조:**
- `polaris/memory/fact_extractor.py` — FactExtractor (규칙 기반 패턴 매칭, LLM 호출 없음)

**기능:**
- `should_extract()` — 메시지 사전 필터링 (단순 인사/감탄 제외)
- `extract_facts()` — 20+ regex 패턴으로 사실 추출 (연구/커리어/생활/차량/학사)
- `categorize_fact()` — 사실 → master_prompt.md 섹션 매핑
- `save_and_update()` — knowledge 테이블 저장 + 99_CURRENT_CONTEXT 자동 업데이트
  - 높은 중요도 (career/research/academic)만 master_prompt 반영
  - 중복 감지 (제목 기반)

**패턴 카테고리:**
- research: 새 도구/기술 사용, 환경 설정, 연구 발견, 시뮬레이션 결과, 밴드갭 정보
- career: 합격/불합격, 인턴십, 직장
- life: 구매/변경, 고양이(시루/설기), 건강, 이사
- academic: 학기 정보
- vehicle: 주행거리, 정비

**완료 항목:**
- [x] fact_extractor.py — FactExtractor (should_extract, extract_facts, save_and_update)
- [x] memory/__init__.py — FactExtractor export
- [x] router.py — _init_fact_extractor() + route() 후처리에서 자동 추출
- [x] tests/test_fact_extractor.py — 43개 테스트 (Filter 10 + Extract 18 + Categorize 5 + SaveUpdate 7 + Router 3)
- [x] 전체 pytest 190개 통과 (기존 147 + 팩트 추출 43)

### Phase 3 Step 2.5: Obsidian Vault Reader (지식 인덱싱) ✅ (2026-02-11 완료)

**구조:**
- `polaris/memory/vault_reader.py` — VaultReader (읽기 전용 Obsidian vault 인덱서)

**기능:**
- `scan_vault()` — vault 내 .md 파일 스캔 (.obsidian, .trash, 99_System, 1KB 미만 제외)
- `parse_note()` — YAML frontmatter + 본문 + [[링크]] + #태그 추출
- `infer_category()` — 폴더 경로 기반 카테고리 자동 추론 (30_Resources→research, 20_Areas→reference 등)
- `index_note()` — 파싱된 노트를 knowledge 테이블에 저장 (source="obsidian", 임베딩 포함)
- `index_vault()` — 전체 vault 인덱싱 (incremental: vault_index.json으로 변경분만 업데이트)
- `search_vault_knowledge()` — source="obsidian" 필터 시맨틱 검색 (키워드 fallback)
- `get_index_stats()` — 인덱싱 상태 통계

**완료 항목:**
- [x] vault_reader.py — VaultReader (scan, parse, index, search, incremental tracking)
- [x] memory/__init__.py — VaultReader export
- [x] router.py — _init_vault_reader() + _build_system_prompt Layer 6 vault knowledge 주입
- [x] bot_v2.py — /index (vault 인덱싱), /vault (상태/검색) 커맨드 + BotCommand 등록
- [x] tests/test_vault_reader.py — 52개 테스트 (Scan 8 + Parse 8 + Category 5 + Index 2 + IndexVault 5 + IndexFile 4 + Search 6 + YAML 5 + Router 2 + EdgeCases)
- [x] 전체 pytest 235개 통과 (기존 190 + vault reader 45 추가분)

### Phase 3.5 Task 1: 스킬 호환 어댑터 + AgentSkills 전환 ✅ (2026-02-17 완료)

**목표:**
- 내부 6개 스킬을 AgentSkills 스타일(name + description 중심)로 전환
- 레거시 frontmatter(trigger_patterns/tools_required)와 신규 description 기반 메타데이터를 동시 지원
- 외부 스킬(OpenClaw/Claude 등) 자동 로드 어댑터 추가

**완료 항목:**
- [x] `skills/*.md` 6개 파일 frontmatter 마이그레이션
  - `trigger_patterns`/`tools_required`/`version`/`author` 제거
  - `description`에 Use when + 필요 도구 메타데이터 통합
  - `category` 유지, 본문(body) 변경 없음
- [x] `polaris/skills/skill_loader.py`
  - `extract_trigger_keywords(description)` 추가 (Use when / e.g.(예:) / fallback)
  - `extract_tools_from_description(description)` 추가 (필요 도구/Required tools 파싱)
  - `load_external_skill(skill_dir)` 추가 (`SKILL.md` 로드, `source=\"external\"`)
  - `scan_external_skills(search_paths)` 추가 (없는 경로 무시)
  - `list_skills()` 레거시 + 신규 형식 동시 호환
- [x] `polaris/skills/registry.py`
  - `_scan()` 내부 스킬에 `source=\"internal\"` 추가
  - `register_external_skills(search_paths)` 추가
  - `match()`를 registry 인덱스 기반으로 동작하도록 보강 (내부+외부 통합 매칭)
  - `get_prompt()`에서 external skill prompt 지원
- [x] `polaris/router.py`
  - `_init_skills()`에서 외부 스킬 자동 로드 추가
  - `POLARIS_EXTERNAL_SKILLS`(콜론 구분) + 기본 경로(`~/.openclaw/skills`, `~/.claude/skills`) 스캔
- [x] `polaris/bot_v2.py`
  - `/skills` 출력에서 외부 스킬에 `[외부]` 태그 표시
- [x] `tests/test_skill_adapter.py` 신규 18개 테스트 추가
  - 트리거 추출 6, 도구 추출 3, 외부 로딩 4, 마이그레이션 3, 통합 2

**검증:**
- [x] `python3 -m pytest tests/test_skill_adapter.py -q` → 18 passed
- [x] `python3 -m pytest tests/test_skills.py -q` → 24 passed
- [x] `python3 -m pytest tests/ -q` → 253 passed

### Phase 3.6 Task 3: 스킬 도구 호출 강제 + 체이닝 ✅ (2026-02-17 완료)

**목표:**
- Known Issues의 핵심 문제(스킬 매칭 후 도구 미호출 할루시네이션)를 코드 레벨에서 차단
- 스킬에 도구 강제 정책(`requires_tool`)과 체인(`tool_chain`)을 정의하고 router에서 집행

**완료 항목:**
- [x] `skills/*.md` 6개 스킬에 실행 정책 추가
  - `requires_tool: true`
  - `strict_mode: true`
  - `tool_chain: [...]`
- [x] `polaris/skills/skill_loader.py`
  - `requires_tool`, `strict_mode`, `tool_chain` 파싱/노출 추가
  - 외부 스킬(`SKILL.md`)도 동일 정책 필드 로드
- [x] `polaris/router.py`
  - `_resolve_skill_enforcement()` 추가 (매칭 스킬 정책 집계)
  - `_execute_preflight_tools()` 추가 (무인자 도구 체인 선실행)
  - `requires_tool` 스킬 매칭 시 도구 집합 제한(정책 기반)
  - 도구 성공 결과가 없으면 최종 답변 차단(추정 답변 금지)
  - 강제 정책 지시 블록을 시스템 프롬프트에 주입
- [x] `polaris/bot_v2.py`
  - `/skills` 출력에 `[강제도구]`, `[체인:n]` 태그 추가
- [x] `tests/test_skill_enforcement.py` 신규 3개 테스트
  - 무도구 응답 차단
  - preflight(무인자 체인) 성공 시 정상 응답
  - 강제 스킬 시 모델에 전달되는 도구 집합 제한

**검증:**
- [x] `python3 -m pytest tests/test_skill_enforcement.py -q` → 3 passed
- [x] `python3 -m pytest tests/test_skill_adapter.py tests/test_skills.py tests/test_router.py tests/test_skill_enforcement.py -q` → 56 passed
- [x] `python3 -m pytest tests/ -q` → 256 passed

### Phase 3.6 Task 4: Bot 런타임 핫리로드 + 선택적 자동 재시작 ✅ (2026-02-17 완료)

**목표:**
- `python -m polaris.bot_v2` 수동 재실행 의존도를 줄이고, 변경사항을 런타임에 빠르게 반영
- 스킬/프롬프트 마크다운 변경은 무중단 반영, 코드(.py) 변경은 정책 기반 자동 재시작 옵션 제공

**완료 항목:**
- [x] `polaris/bot_v2.py`
  - 파일 변경 감지 기반 핫리로드 루프 추가 (`_check_and_apply_hot_reload`)
  - 런타임 리로드 함수 추가 (`_reload_runtime_components`) — 스킬/외부 스킬 재초기화
  - 수동 리로드 커맨드 `/reload` 추가 (`reload_command`)
  - help/Telegram BotCommand 목록에 `/reload` 등록
  - 메시지 처리 시작 시 자동 변경 감지 실행 (`handle_message` 진입부)
- [x] 환경변수 기반 동작 제어 추가
  - `POLARIS_AUTO_RELOAD` (기본 `true`)
  - `POLARIS_AUTO_RESTART_ON_CODE_CHANGE` (기본 `false`)
  - `POLARIS_RELOAD_CHECK_INTERVAL` (기본 `2.0`초)

**동작 정책:**
- `skills/*.md`, `data/master_prompt.md` 변경:
  - 자동 감지 시 런타임 반영(재시작 불필요)
  - 즉시 반영이 필요하면 `/reload` 수동 실행 가능
- `.py` 코드 변경:
  - 기본값은 로그 경고만 출력(수동 재시작 필요)
  - `POLARIS_AUTO_RESTART_ON_CODE_CHANGE=true` 설정 시 프로세스 자동 재시작

**검증:**
- [x] `python3 -m pytest tests/ -q` → 256 passed

### Phase 4: MailOps R1 (Apple Mail 통합) ✅ (2026-02-17 완료)

**목표:**
- Apple Mail을 단일 수집 소스로 사용해 Outlook UIC + Gmail KR + Gmail US 메일을 통합 관리
- 메일 이력/요약은 로컬 SQLite 기반으로 빠르게 조회하고, urgent 메일은 Telegram으로 별도 알림
- 카테고리 복잡도를 줄이기 위해 `urgent/action/info/promo` 4개만 사용

**완료 항목:**
- [x] `polaris/mailops/` 신규 모듈 추가
  - `store.py` — `data/mailops.db` 스키마/저장소 (`mail_messages`, `mail_classification`, `mail_alerts`, `mail_actions_log`)
  - `classifier.py` — 규칙 기반 4카테고리 분류기
  - `ingest.py` — Apple Mail 다중 계정 키워드 수집기 (`POLARIS_MAILOPS_ACCOUNT_KEYWORDS`)
  - `service.py` — sync/digest/urgent/promo/actions 오케스트레이션
  - `__init__.py` — `MailOpsService` export
- [x] `polaris/tools/mailops_tools.py` 신규 도구 5개 추가
  - `fetch_mail_digest`
  - `fetch_urgent_mails`
  - `fetch_promo_deals`
  - `propose_mail_actions`
  - `execute_mail_actions` (R1 안전모드: archive/label/mark_read, delete 미지원)
- [x] `polaris/router.py`
  - MailOps 도구 키워드 라우팅 맵 추가
- [x] `polaris/bot_v2.py`
  - MailOps 초기화 + 주기적 urgent 폴링 (`POLARIS_MAILOPS_POLL_INTERVAL`, 기본 300초)
  - 신규 명령어 추가: `/mail_digest`, `/mail_urgent`, `/mail_promo`, `/mail_actions`
  - urgent 미통지 건 Telegram push 알림 추가
- [x] `skills/` 신규 스킬 3개 추가
  - `mail_digest.md`
  - `mail_triage.md`
  - `promo_tracker.md`
  - 모두 `requires_tool: true`, `strict_mode: true` 적용
- [x] 테스트 추가/보강
  - `tests/test_mailops.py` 신규 4개 (분류/동기화/urgent 알림 상태/도구 핸들러)
  - `polaris/memory/obsidian_writer.py` 경로 해석 우선순위 수정 (vault 경로 우선)로 테스트 안정화

**검증:**
- [x] `python3 -m pytest tests/test_mailops.py -q` → 4 passed
- [x] `python3 -m pytest tests/ -q` → 260 passed

**후속 패치 (2026-02-17): Apple Mail 계정명 불일치 대응**
- [x] `read_mail.scpt` 개선
  - `account_keyword="*"` 또는 `ALL`일 때 모든 계정을 순회해 unread 메일 수집
  - 단일 계정 모드와 전체 계정 모드 동작 분리
- [x] `polaris/mailops/service.py`
  - 기본 계정 키워드를 `"*"`로 변경 (환경설정 누락 시에도 전체 계정 수집)
- [x] `mail_reader.py`
  - `list_accounts()` 추가 (Apple Mail 계정명 조회)
- [x] `polaris/bot_v2.py`
  - `/mail_accounts` 명령 추가 (실제 계정명 확인용)
- [x] 회귀 테스트
  - `python3 -m pytest tests/ -q` → 260 passed

### Known Issues (미해결)
- [ ] **할루시네이션 잔여 이슈(부분)**: `requires_tool=false` 스킬/일반 대화 경로에서는 모델의 추정 답변 가능성 남아있음
- 상태: Phase 3.6 Task 3에서 `requires_tool=true` 경로는 코드 레벨 차단 완료
- 잔여 과제:
  - 필수 인자 부족 시 추가 질문 자동화(현재는 차단 응답 중심)
  - 도구 실패 재시도/대체 경로 정책 강화
  - 일반 대화와 도구 필요 대화의 경계 판단 개선

---

### Phase 3: 자기학습 (Self-Learning) — Blueprint

> **목표**: Polaris가 대화에서 스스로 학습하고 master_prompt.md를 자동 업데이트하여 점점 똑똑해지는 시스템
> **영감**: email_analyzer의 다중 에이전트 합의 루프 (신뢰도 기반 정답 평가)

#### 기존 인프라 (이미 있는 것)
- `polaris_memory.db` — conversations, knowledge, feedback 테이블
- `obsidian_writer.py` — master_prompt 섹션별 읽기/쓰기 API
- `master_prompt.md` v3.2 — 00_PERSONA, 01_USER, 02_RESEARCH, 03_DEV, 99_SYSTEM

#### Step 1: Fact Extractor (대화 → 지식 추출)
```
[대화 발생] → [LLM이 새 사실 감지] → [master_prompt 해당 섹션 자동 업데이트]
```
- router.route() 완료 후, 8B 모델로 간단한 2차 호출 (백그라운드)
- 프롬프트: "이 대화에서 사용자에 대한 새로운 사실이 있나? JSON으로 답변"
- 새 사실 발견 시: obsidian_writer로 01_USER 또는 02_RESEARCH 섹션 업데이트
- 예: "나 ONETEP도 써야 해" → 02_RESEARCH에 ONETEP 추가
- **비용**: 8B 모델 2차 호출 ~3-5초 (백그라운드, 사용자 체감 없음)

#### Step 2: Correction Loop (교정 → 학습)
```
[사용자 교정] → [feedback 테이블 저장] → [다음 대화에 반영]
```
- 패턴 감지: "아니", "그게 아니라", "틀렸어", "그건 잘못된 정보야"
- 교정 내용을 feedback 테이블에 저장 (원본 응답 + 교정 내용)
- _build_system_prompt에서 관련 feedback을 주입하여 같은 실수 방지
- 누적 교정이 3회 이상이면 master_prompt 자체를 업데이트

#### Step 3: Prompt Self-Improvement (자기 프롬프트 개선)
```
[N회 대화 축적] → [Judge LLM이 Few-shot 품질 평가] → [99_SYSTEM 자동 갱신]
```
- 실제 성공/실패 대화를 분석하여 Few-shot 예시 자동 교체
- 금지 패턴도 실제 실패 사례에서 자동 추가
- email_analyzer 패턴 적용: 여러 후보 응답 생성 → 신뢰도 평가 → 최선 선택
- **주의**: 이 단계는 70B 또는 외부 API(Claude) 필요 — Phase 3 후반부

#### Step 4: Knowledge Graph (장기 기억)
```
[대화 기록] → [주제별 지식 정리] → [knowledge 테이블] → [시맨틱 검색으로 주입]
```
- 연구 토론 내용을 knowledge 테이블에 구조화 저장
- "지난번에 MoS2 밴드갭 얘기했잖아" → 시맨틱 검색으로 과거 맥락 복원
- 기존 embedder.py + memory.py 인프라 활용

#### 구현 우선순위
| Step | 난이도 | 임팩트 | 의존성 |
|------|--------|--------|--------|
| Step 1: Fact Extractor | 중 | 높음 | 없음 (바로 시작 가능) |
| Step 2: Correction Loop | 낮 | 높음 | 없음 (바로 시작 가능) |
| Step 3: Self-Improvement | 높 | 중간 | Step 1, 2 완료 후 |
| Step 4: Knowledge Graph | 중 | 중간 | Step 1 완료 후 |

#### 아키텍처 다이어그램
```
User Message
    │
    ▼
┌─────────────────────────────────────┐
│          PolarisRouter              │
│  ┌─────────┐  ┌──────────────────┐  │
│  │ 8B/70B  │  │ _build_system    │  │
│  │ ReAct   │◄─┤ _prompt()        │  │
│  │ Loop    │  │  ├ SYSTEM_PROMPT  │  │
│  └────┬────┘  │  ├ 00_PERSONA    │  │
│       │       │  ├ 99_SYSTEM     │  │
│       │       │  ├ recent convos │  │
│       │       │  └ feedback (NEW)│  │
│       ▼       └──────────────────┘  │
│  [Response]                          │
└───────┬─────────────────────────────┘
        │
        ▼ (Background, async)
┌───────────────────────────────┐
│  Self-Learning Pipeline (NEW) │
│                               │
│  1. Fact Extractor            │
│     대화 → 새 사실? → master_ │
│     prompt.md 업데이트         │
│                               │
│  2. Correction Detector       │
│     "아니, 그게 아니라..."     │
│     → feedback 테이블 저장     │
│                               │
│  3. Prompt Judge (주기적)     │
│     Few-shot 품질 평가        │
│     → 99_SYSTEM 자동 갱신     │
└───────────────────────────────┘
```
