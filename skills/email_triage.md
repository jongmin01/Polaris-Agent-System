---
name: email_triage
description: "이메일 분류 및 우선순위 결정. Use when 사용자가 메일, 이메일, inbox, 메일함 관련 질문을 할 때. 필요 도구: analyze_emails."
category: life
requires_tool: true
strict_mode: true
tool_chain: [analyze_emails]
---

## Prompt
사용자가 이메일 확인/분류를 요청했어. 다음 절차를 따라:

1. **이메일 분석**: analyze_emails 도구로 이메일 분석
2. **분류** (3단계):
   - **URGENT**: 24시간 내 답장 필요 (TA 학생 질문, 교수님 메일, 마감 임박)
   - **NORMAL**: 답장 필요하지만 급하지 않음 (세미나 안내, 공동연구자)
   - **FYI**: 읽기만 하면 됨 (뉴스레터, 학교 공지)
3. **TA 메일 특별 처리**: PHYS 132 학생 메일은 영어 답장 초안 작성
4. **요약**: URGENT → NORMAL → FYI 순서로 정리

## Few-shot Examples
### Example 1
**Input**: 이메일 확인해줘
**Output**: 메일함 확인해볼게. [analyze_emails 호출]

5개 새 메일 있어:

**URGENT (2)**
1. [학생] Sarah Kim — "Lab report extension request"
   → PHYS 132 리포트 마감 연장 요청. 내일까지 답장 필요.
   → 답장 초안: "Hi Sarah, I understand. You can submit by Friday 5 PM. Let me know if you need further help."

2. [교수] Prof. Chen — "Meeting reschedule"
   → 내일 미팅 시간 변경 요청. 확인 답장 필요.

**NORMAL (1)**
3. [동료] Mike — "VASP input files"
   → MoSSe relaxation INCAR 파일 공유 요청.

**FYI (2)**
4. UIC Graduate College — 장학금 공지
5. APS Newsletter — March Meeting 등록 안내

먼저 처리할 거 있어?

## Validation
- URGENT/NORMAL/FYI 분류가 되었는가
- TA 메일에 답장 초안이 포함되었는가
- 우선순위 순서로 정리되었는가

## Changelog
- v1.0: 초기 생성
