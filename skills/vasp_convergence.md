---
name: vasp_convergence
description: "VASP DFT 계산 수렴 여부 확인 및 조언. Use when 사용자가 수렴, VASP, 계산 확인, convergence 관련 질문을 할 때. 필요 도구: monitor_hpc_job."
category: research
requires_tool: true
strict_mode: true
tool_chain: [check_hpc_connection, monitor_hpc_job]
---

## Prompt
사용자가 VASP 계산의 수렴 여부를 확인하고 싶어 해. 다음 절차를 따라:

1. **OSZICAR 확인**: E0 값의 변화를 봐. 마지막 3개 ionic step의 에너지 차이가 1 meV/atom 이하면 수렴.
2. **EDIFF 기준**: electronic step이 EDIFF (기본 1E-4 eV) 이내로 수렴해야 함.
3. **Force 수렴**: 잔여 힘(forces)이 EDIFFG 이하인지 확인.
4. **판단 후 조언**:
   - 수렴됨 → 결과 요약 + 다음 단계 제안 (band structure, DOS 등)
   - 수렴 안 됨 → 원인 분석 (ENCUT 부족, k-point 부족, 초기 구조 문제) + 해결책
5. **2D 시스템 주의**: Janus TMDC (MoSSe, WSSe) 등 2D 물질은 vacuum layer 충분한지 + IDIPOL=3 설정 확인.

## Few-shot Examples
### Example 1: 수렴된 경우
**Input**: VASP relaxation 수렴했는지 봐줘. Job 45231, /eagle/projects/catalysis/jongmin/MoSSe/relax
**Output**: 확인해볼게. [monitor_hpc_job 호출]

(결과 확인 후)
계산 수렴됐어! E0 변화가 마지막 3 step에서 0.3 meV/atom이야. Force도 0.01 eV/A 이하로 잘 수렴됐어.
다음으로 band structure 계산 돌릴 거야? KPOINTS 경로 잡아줄까?

### Example 2: 수렴 안 된 경우
**Input**: MoSSe relaxation이 200 step 넘게 돌았는데 아직 안 끝났어
**Output**: 200 step이면 뭔가 문제 있을 수 있어. 확인해보자:
1. ENCUT이 충분해? MoSSe면 최소 500 eV 권장
2. KPOINTS가 너무 dense하진 않아? relaxation엔 Gamma-centered 4x4x1이면 충분
3. 초기 구조 원자 간 거리가 너무 가까운 건 아닌지 POSCAR 확인
4. ISIF=3이면 cell shape도 변하는데, 2D라서 z-축 vacuum이 줄어들 수 있어. ISIF=2로 바꿔봐

## Validation
- 수렴 판단 기준이 명확하게 제시되었는가
- 2D 물질 특성을 고려한 조언 포함
- 다음 단계 제안이 있는가

## Changelog
- v1.0: 초기 생성
