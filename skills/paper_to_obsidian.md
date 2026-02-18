---
name: paper_to_obsidian
description: "논문 정보를 Obsidian 노트로 변환. Use when 사용자가 노트 만들어, 정리해줘, obsidian, 노트로 관련 질문을 할 때. 필요 도구: search_arxiv."
category: research
requires_tool: true
strict_mode: true
tool_chain: [search_arxiv]
---

## Prompt
사용자가 논문을 Obsidian 노트로 정리하고 싶어 해. 다음 절차를 따라:

1. **논문 검색**: search_arxiv로 정확한 정보 확보
2. **노트 생성**: 아래 템플릿에 맞춰 마크다운 출력
3. **내부 링크**: 주요 개념은 [[개념]] 형태로 감싸서 Obsidian 지식 그래프 연결

### 노트 템플릿
```
---
category: paper
tags: [주제태그, DFT]
status: to-read
created: YYYY-MM-DD
arxiv: "arXiv ID"
---

# 논문 제목

## 기본 정보
- **저자**: 이름 나열
- **저널**: 저널명 또는 arXiv
- **연도**: YYYY

## 요약
한국어 3-5줄 요약

## 핵심 결과
- 결과 1
- 결과 2

## 방법론
사용된 계산/실험 방법

## 내 연구 관련성
[[Janus TMDC]], [[Valley Polarization]] 등과의 연결점

## 관련 노트
- [[관련 논문]]
- [[관련 개념]]
```

## Few-shot Examples
### Example 1
**Input**: 이 논문 Obsidian 노트로 만들어줘: Valley polarization in MoSSe
**Output**: 논문 정보 찾아볼게. [search_arxiv 호출]

노트 만들었어:

---
category: paper
tags: [MoSSe, valley-polarization, Janus-TMDC, DFT]
status: to-read
created: 2026-02-10
arxiv: "2025.12345"
---

# Valley-dependent transport in Janus MoSSe monolayer

## 기본 정보
- **저자**: Zhang et al.
- **저널**: Physical Review B
- **연도**: 2025

## 요약
Janus MoSSe 단층에서 내재 전기장에 의한 valley polarization 향상을 first-principles 계산으로 보여줌. Valley splitting이 MoS2 대비 약 2배.

## 핵심 결과
- Valley splitting: 148 meV
- Rashba parameter: 0.85 eV*A

## 방법론
[[VASP]] + [[PBE]] + SOC, PAW, 500 eV cutoff

## 내 연구 관련성
[[Janus TMDC]] 프로젝트에서 동일한 valley splitting 경향 확인 필요

## 관련 노트
- [[MoS2 Band Structure]]
- [[Valley Polarization]]
- [[Spin-Orbit Coupling]]

Obsidian vault에 저장할까?

## Validation
- YAML frontmatter 형식이 올바른가
- 내부 링크([[ ]])가 적절히 사용되었는가
- 내 연구 관련성이 구체적인가

## Changelog
- v1.0: 초기 생성
