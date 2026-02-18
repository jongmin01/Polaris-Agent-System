---
name: promo_tracker
description: "프로모션/딜 메일 추적. Use when 사용자가 할인, 딜, 프로모션, coupon 관련 질문을 할 때. 필요 도구: fetch_promo_deals."
category: life
requires_tool: true
strict_mode: true
tool_chain: [fetch_promo_deals]
---

## Prompt
사용자가 딜/프로모션 메일을 요청하면:

1. `fetch_promo_deals`를 호출해서 promo 카테고리 메일을 조회해.
2. 발신자, 제목, 시각 중심으로 상위 항목을 요약해.
3. 과장된 추천을 하지 말고 도구 결과에 있는 정보만 전달해.
