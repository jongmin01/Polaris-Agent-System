---
name: mail_digest
description: "통합 메일 요약 조회(Outlook UIC + Gmail KR/US). Use when 사용자가 오늘 메일 요약, 메일 확인, inbox digest 관련 질문을 할 때. 필요 도구: fetch_mail_digest, fetch_urgent_mails."
category: system
requires_tool: true
strict_mode: true
tool_chain: [fetch_mail_digest, fetch_urgent_mails]
---

## Prompt
사용자가 메일 요약을 요청하면 다음 순서로 진행해:

1. `fetch_mail_digest`를 먼저 호출해서 최신 메일 요약을 가져와.
2. `fetch_urgent_mails`를 호출해서 긴급 메일을 분리해.
3. 아래 순서로 출력해:
   - 긴급(urgent)
   - 액션(action)
   - 정보(info)
   - 프로모션(promo)
4. 도구 결과가 없으면 추정해서 답하지 말고, 동기화/권한 문제를 명확히 안내해.
