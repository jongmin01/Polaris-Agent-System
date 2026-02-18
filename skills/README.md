# Polaris Skills

스킬 = LLM이 작업 전에 읽고 따라하는 마크다운 매뉴얼. 코드 실행 없음.

## 스킬 파일 포맷

```markdown
---
name: skill_name
description: "한 줄 설명"
version: "1.0"
author: "jongmin"
tools_required: [tool_a, tool_b]
trigger_patterns: ["키워드1", "keyword2"]
category: research  # research / dev / life / system
---

## Prompt
(LLM이 따라야 할 구체적 지시사항)

## Few-shot Examples
### Example 1
**Input**: (사용자 입력 예시)
**Output**: (기대 출력 예시)

## Validation
- (출력 검증 기준)

## Changelog
- v1.0: 초기 생성
```

## 스킬 추가 방법

1. 위 포맷으로 `skills/` 디렉토리에 `.md` 파일 생성
2. Telegram에서 `/skills` 명령으로 등록 확인
3. trigger_patterns에 포함된 키워드로 메시지 보내면 자동 매칭

## 등록된 스킬

| 스킬 | 카테고리 | 트리거 |
|------|----------|--------|
| vasp_convergence | research | 수렴, VASP, convergence |
| arxiv_analysis | research | 논문 분석, paper review |
| paper_to_obsidian | research | 노트 만들어, obsidian |
| email_triage | life | 메일, 이메일, inbox |
| hpc_monitor | research | 계산 상태, job, HPC |
| daily_briefing | system | 브리핑, morning |
