---
name: arxiv_analysis
description: "arXiv 논문 심층 분석 및 연구 관련성 평가. Use when 사용자가 논문 분석, paper review, 리뷰해줘 관련 질문을 할 때. 필요 도구: search_arxiv, analyze_paper_gemini."
category: research
requires_tool: true
strict_mode: true
tool_chain: [search_arxiv, analyze_paper_gemini]
---

## Prompt
사용자가 논문 분석을 요청했어. 다음 구조로 분석해:

1. **검색**: search_arxiv로 논문을 찾아.
2. **분석**: analyze_paper_gemini으로 논문 전문 분석.
3. **결과 정리** (5개 항목 필수):
   - **핵심 기여**: 이 논문이 해결한 문제와 주요 발견
   - **방법론**: DFT functional, basis set, 실험 조건 등
   - **주요 결과**: 수치 결과 중심
   - **한계점**: 저자가 인정한 한계 + 내가 보는 한계
   - **내 연구 관련성**: Janus TMDC (MoSSe/WSSe), valley polarization, DFT/VASP 관점에서 평가
4. **후속 행동 제안**: 후속 연구나 계산 제안.

## Few-shot Examples
### Example 1
**Input**: MoSSe valley polarization 최신 논문 분석해줘
**Output**: MoSSe valley polarization 논문 찾아볼게. [search_arxiv 호출]

(결과 확인 후)
"Valley-dependent transport in Janus MoSSe monolayer" (2025) 분석이야:

**핵심 기여**: Janus MoSSe에서 intrinsic electric field가 valley polarization을 ~15% 향상시킨다는 걸 first-principles로 보여줌.
**방법론**: PBE+SOC, PAW pseudopotential, 500 eV cutoff, 12x12x1 k-mesh. Berry curvature 포함.
**주요 결과**: Valley splitting 148 meV (MoS2 대비 ~2배). Rashba splitting도 관측 (alpha_R = 0.85 eV*A).
**한계점**: GW 보정 없이 PBE만 사용 — band gap 과소평가 가능. 온도 효과 미포함.
**내 연구 관련성**: 우리 MoSSe 계산에서도 같은 valley splitting 경향 확인 필요. SOC 포함 band structure 비교하면 좋겠어.

더 자세히 볼 논문 있어? Obsidian 노트로 정리해줄까?

## Validation
- 5개 분석 항목이 모두 포함되었는가
- 내 연구(Janus TMDC)와의 관련성이 구체적인가
- 후속 행동 제안이 있는가

## Changelog
- v1.0: 초기 생성
