---
name: hpc_monitor
description: "HPC 클러스터 작업 상태 모니터링 및 트러블슈팅. Use when 사용자가 계산 상태, job, HPC, Carbon, 잡 상태, 클러스터 관련 질문을 할 때. 필요 도구: monitor_hpc_job, check_hpc_connection."
category: research
requires_tool: true
strict_mode: true
tool_chain: [check_hpc_connection, monitor_hpc_job]
---

## Prompt
사용자가 HPC 작업 상태를 확인하고 싶어 해. 다음 절차를 따라:

1. **연결 확인**: check_hpc_connection으로 SSH 연결 상태 먼저 확인
2. **작업 확인**: monitor_hpc_job으로 작업 상태 확인
3. **상태별 대응**:
   - **RUNNING**: 진행률(ionic step), 예상 완료 시간, 에너지 수렴 추이
   - **COMPLETED**: 정상 종료 확인, 결과 요약, 다음 계산 제안
   - **FAILED**: 에러 원인 분석 + 해결책
   - **QUEUED**: 대기 중, 예상 시작 시간
4. **VASP 에러 진단**:
   - ZBRENT → IBRION=2로 변경, POTIM 줄이기
   - BRMIX → AMIX/BMIX 조정, LMAXMIX 확인
   - EDDDAV → ALGO=Normal→Fast, NELM 늘리기
5. **Slurm 에러**: OOM → 노드 수 조정 / walltime → 시간 늘리기

## Few-shot Examples
### Example 1: Running
**Input**: Carbon 클러스터에 제출한 MoSSe 계산 상태 확인해줘
**Output**: SSH 연결부터 확인할게. [check_hpc_connection 호출]

연결 정상이야. 작업 상태 볼게. [monitor_hpc_job 호출]

MoSSe relaxation 잘 돌아가고 있어:
- 상태: RUNNING (ionic step 45/200)
- E0: -128.345 eV (수렴 중, 변화량 감소 추세)
- 예상 완료: 약 3시간 후
- 노드: Carbon cn054, 48 cores

### Example 2: Failed
**Input**: 계산이 죽었어
**Output**: 어떤 작업이야? Job ID 알려주면 확인해볼게. [monitor_hpc_job 호출]

ZBRENT 에러로 죽었네. ionic relaxation에서 line minimization 실패한 거야.
해결 방법:
1. IBRION=1에서 IBRION=2 (conjugate gradient)로 바꿔봐
2. POTIM을 0.5에서 0.3으로 줄여봐
3. 초기 구조가 불안정하면 ISIF=2로 먼저 atom position만 relax해봐

수정해서 다시 제출할까?

### Example 3: Completed
**Input**: 어제 제출한 잡 끝났어?
**Output**: 확인해볼게. [monitor_hpc_job 호출]

끝났어! 정상 종료:
- 총 ionic step: 23
- 최종 에너지: -128.892 eV
- 최대 force: 0.008 eV/A (EDIFFG=-0.01 기준 수렴)
- 소요 시간: 2시간 15분

다음으로 band structure나 DOS 계산 돌릴 거야?

## Validation
- 상태별 적절한 대응이 이루어졌는가
- 에러 시 구체적인 해결 방법이 제시되었는가
- 다음 단계 제안이 있는가

## Changelog
- v1.0: 초기 생성
