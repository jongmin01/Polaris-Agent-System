---
name: mail_triage
description: "메일 정리 액션 제안 및 실행(안전 모드). Use when 사용자가 메일 정리, 아카이브, 라벨링, mark read 관련 질문을 할 때. 필요 도구: propose_mail_actions, execute_mail_actions."
category: system
requires_tool: true
strict_mode: true
tool_chain: [propose_mail_actions, execute_mail_actions]
---

## Prompt
사용자가 메일 정리를 요청하면 다음 순서를 지켜:

1. `propose_mail_actions`로 먼저 제안 목록을 만들고 사용자에게 확인을 받아.
2. 사용자가 승인한 경우에만 `execute_mail_actions`를 호출해.
3. 삭제(delete)는 R1에서 지원하지 않으므로 실행하지 말고 제한사항을 안내해.
4. 실행 결과는 개수와 상태를 명확히 요약해.
