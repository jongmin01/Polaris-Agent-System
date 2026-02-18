---
name: daily_briefing
description: "일일 브리핑: 일정 + HPC 상태 + 이메일 + 새 논문. Use when 사용자가 브리핑, briefing, 오늘 요약, morning, 오늘 상황 관련 질문을 할 때. 필요 도구: get_calendar_briefing, monitor_hpc_job, analyze_emails, search_arxiv."
category: system
requires_tool: true
strict_mode: true
tool_chain: [get_calendar_briefing, monitor_hpc_job, analyze_emails, search_arxiv]
---

## Prompt
사용자가 일일 브리핑을 요청했어. 다음 4가지를 순서대로 확인해서 정리해:

### 1. 오늘 일정
get_calendar_briefing으로 오늘/내일 일정 확인.

### 2. HPC 작업 상태
monitor_hpc_job으로 돌아가고 있는 계산 확인. 상태 요약.

### 3. 새 이메일
analyze_emails로 새 이메일 확인. URGENT만 요약, 나머지는 개수만.

### 4. 관심 분야 새 논문
search_arxiv로 "Janus TMDC" 또는 "MoSSe" 최신 논문 확인. 상위 3개만.

### 출력 형식
```
오늘의 브리핑

[일정]
- 10:00 Lab meeting
- 14:00 Office hours

[HPC]
- MoSSe relax: RUNNING (step 45, ~3시간 남음)
- WSSe band: COMPLETED

[메일]
- URGENT 1건: Prof. Chen 미팅 변경
- 전체 5건 (URGENT 1 / NORMAL 2 / FYI 2)

[새 논문]
- "Valley polarization in Janus MoSSe..." (2025)
- "Strain effects on WSSe..." (2025)
```

## Few-shot Examples
### Example 1
**Input**: 오늘 브리핑해줘
**Output**: 오늘 상황 정리해볼게. 일정부터 확인할게. [get_calendar_briefing 호출]

(순차적으로 각 도구 호출 후)

오늘의 브리핑이야:

[일정]
- 10:00 Lab meeting (SES 238)
- 14:00-16:00 PHYS 132 Office Hours
- 내일: Prof. Chen 1:1 미팅 (시간 변경됨, 메일 확인 필요)

[HPC]
- MoSSe relaxation (Job 45231): RUNNING, step 67/200, 에너지 수렴 중
- WSSe band structure (Job 45198): COMPLETED, 정상 종료

[메일]
- URGENT: Prof. Chen 미팅 시간 변경 요청 (답장 필요)
- 전체 8건 (URGENT 1 / NORMAL 3 / FYI 4)

[새 논문]
- "Anomalous valley Hall effect in Janus MoSSe" — 우리 연구랑 직접 관련!
- "Strain-tunable band gap in WSSe monolayer"

Prof. Chen 메일 먼저 답장하는 게 좋겠어. 답장 초안 써줄까?

## Validation
- 4개 카테고리가 모두 포함되었는가
- URGENT 항목이 눈에 띄게 표시되었는가
- 후속 행동 제안이 있는가

## Changelog
- v1.0: 초기 생성
