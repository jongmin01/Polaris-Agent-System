#!/usr/bin/env python3
"""
Physics-Agent
포괄적인 물리 시뮬레이션 에이전트 (VASP, ONETEP 등)
"""

import os
import re
from typing import Dict, Optional, List
from enum import Enum


class CalculationType(Enum):
    """계산 유형"""
    BAND_STRUCTURE = "band_structure"
    DOS = "dos"
    RELAXATION = "relaxation"
    SINGLE_POINT = "single_point"
    PHONON = "phonon"
    UNKNOWN = "unknown"


class SimulationTool(Enum):
    """시뮬레이션 툴"""
    VASP = "vasp"
    ONETEP = "onetep"
    AUTO = "auto"


class PhysicsAgent:
    """
    Physics Agent - VASP, ONETEP 등 DFT 계산 자동화

    역할:
    1. 자연어 요청 → 계산 유형 파악
    2. 시스템 크기/복잡도 분석 → 최적 툴 선택
    3. 입력 파일 생성 (POSCAR, INCAR, etc.)
    4. HPC 제출 및 모니터링
    5. 결과 분석 및 Obsidian 문서화
    """

    def __init__(self, hpc_config: Optional[Dict] = None):
        """
        Args:
            hpc_config: HPC 설정 (Polaris 클러스터 정보)
        """
        self.hpc_config = hpc_config or self._load_default_hpc_config()

        # Handler 초기화
        self.handlers = {
            SimulationTool.VASP: VASPHandler(self.hpc_config),
            SimulationTool.ONETEP: ONETEPHandler(self.hpc_config)
        }

        # 계산 유형별 키워드
        self.calc_keywords = {
            CalculationType.BAND_STRUCTURE: ["밴드", "band", "structure", "band structure"],
            CalculationType.DOS: ["DOS", "density of states", "상태밀도"],
            CalculationType.RELAXATION: ["relaxation", "optimization", "최적화", "구조최적화"],
            CalculationType.SINGLE_POINT: ["single point", "scf", "에너지"],
            CalculationType.PHONON: ["phonon", "진동", "포논"]
        }

    def _load_default_hpc_config(self) -> Dict:
        """기본 HPC 설정 로드"""
        return {
            'host': os.getenv('POLARIS_HOST', 'polaris.alcf.anl.gov'),
            'user': os.getenv('POLARIS_USER', ''),
            'work_dir': '/lus/eagle/projects/your_project',
            'queue': 'debug',  # or 'prod'
            'nodes': 1,
            'walltime': '01:00:00'
        }

    def handle(self, user_message: str) -> Dict:
        """
        사용자 요청 처리

        Args:
            user_message: "MoS2 밴드 구조 계산해줘"

        Returns:
            결과 딕셔너리
        """
        # 1. 계산 유형 파악
        calc_type = self._identify_calculation_type(user_message)

        if calc_type == CalculationType.UNKNOWN:
            return {
                'status': 'clarification_needed',
                'message': '어떤 계산을 수행할까요?\n\n1️⃣ 밴드 구조\n2️⃣ DOS (상태밀도)\n3️⃣ 구조 최적화\n4️⃣ 단일점 에너지'
            }

        # 2. 시스템 정보 추출
        system_info = self._extract_system_info(user_message)

        # 3. 툴 선택 (VASP vs ONETEP)
        tool = self._select_tool(system_info, calc_type)

        # 4. Handler로 위임
        handler = self.handlers[tool]

        return {
            'status': 'preparing',
            'message': f'🔬 {tool.value.upper()} 사용\n📊 계산 유형: {calc_type.value}\n⚙️ 입력 파일 생성 중...',
            'calculation_type': calc_type.value,
            'tool': tool.value,
            'system': system_info,
            'next_step': 'generate_input_files'
        }

    def _identify_calculation_type(self, message: str) -> CalculationType:
        """메시지에서 계산 유형 파악"""
        msg_lower = message.lower()

        for calc_type, keywords in self.calc_keywords.items():
            if any(kw in msg_lower for kw in keywords):
                return calc_type

        return CalculationType.UNKNOWN

    def _extract_system_info(self, message: str) -> Dict:
        """
        시스템 정보 추출 (재료, 크기 등)

        예: "MoS2 밴드 구조" → {'material': 'MoS2', 'type': '2D'}
        """
        msg_lower = message.lower()

        # 간단한 재료 추출 (정규식)
        materials = re.findall(r'([A-Z][a-z]?[0-9]?)+', message)

        system_info = {
            'material': materials[0] if materials else 'Unknown',
            'dimension': '2D' if any(kw in msg_lower for kw in ['2d', 'monolayer', '단층']) else '3D',
            'estimated_atoms': 50  # 기본값 (나중에 개선)
        }

        return system_info

    def _select_tool(self, system_info: Dict, calc_type: CalculationType) -> SimulationTool:
        """
        시스템 크기와 계산 유형에 따라 최적 툴 선택

        선택 기준:
        - VASP: 원자 수 < 200, 일반적인 DFT 계산
        - ONETEP: 원자 수 > 200, 선형 스케일링 필요
        """
        n_atoms = system_info.get('estimated_atoms', 50)

        # 대규모 시스템 → ONETEP
        if n_atoms > 200:
            return SimulationTool.ONETEP

        # 소규모 시스템 → VASP (더 빠름)
        return SimulationTool.VASP

    def generate_input_files(self, calc_type: CalculationType, system_info: Dict, tool: SimulationTool) -> Dict:
        """
        입력 파일 생성

        Returns:
            생성된 파일 경로들
        """
        handler = self.handlers[tool]
        return handler.generate_input(calc_type, system_info)

    def submit_job(self, tool: SimulationTool, job_dir: str) -> Dict:
        """
        HPC에 작업 제출

        Returns:
            Job ID 및 상태
        """
        handler = self.handlers[tool]
        return handler.submit(job_dir)


class VASPHandler:
    """VASP 계산 핸들러"""

    def __init__(self, hpc_config: Dict):
        self.hpc_config = hpc_config

    def generate_input(self, calc_type: CalculationType, system_info: Dict) -> Dict:
        """
        VASP 입력 파일 생성

        파일:
        - POSCAR (구조)
        - INCAR (계산 파라미터)
        - KPOINTS (k-point 샘플링)
        - POTCAR (pseudopotential)
        """
        # TODO: 실제 구현
        return {
            'status': 'not_implemented',
            'message': '🚧 VASP 입력 파일 생성 기능 개발 중...\n\n현재 수동으로 POSCAR를 생성해주세요.'
        }

    def submit(self, job_dir: str) -> Dict:
        """VASP 작업 제출"""
        # TODO: SSH를 통한 HPC 제출
        return {
            'status': 'not_implemented',
            'message': '🚧 HPC 제출 기능 개발 중...'
        }


class ONETEPHandler:
    """ONETEP 계산 핸들러"""

    def __init__(self, hpc_config: Dict):
        self.hpc_config = hpc_config

    def generate_input(self, calc_type: CalculationType, system_info: Dict) -> Dict:
        """
        ONETEP 입력 파일 생성

        파일:
        - .dat (ONETEP 입력 파일)
        """
        # TODO: 실제 구현
        return {
            'status': 'not_implemented',
            'message': '🚧 ONETEP 입력 파일 생성 기능 개발 중...'
        }

    def submit(self, job_dir: str) -> Dict:
        """ONETEP 작업 제출"""
        # TODO: SSH를 통한 HPC 제출
        return {
            'status': 'not_implemented',
            'message': '🚧 HPC 제출 기능 개발 중...'
        }


# ========================================
# 유틸리티 함수
# ========================================

def estimate_computational_cost(calc_type: CalculationType, n_atoms: int, tool: SimulationTool) -> Dict:
    """
    계산 비용 추정

    Returns:
        node-hours, 예상 시간 등
    """
    # 간단한 추정 (실제로는 더 복잡함)
    base_cost = {
        CalculationType.SINGLE_POINT: 0.1,
        CalculationType.RELAXATION: 0.5,
        CalculationType.BAND_STRUCTURE: 0.3,
        CalculationType.DOS: 0.2,
        CalculationType.PHONON: 2.0
    }

    cost = base_cost.get(calc_type, 0.5)
    cost *= (n_atoms / 50) ** 1.5  # 원자 수에 따른 스케일링

    return {
        'node_hours': round(cost, 2),
        'estimated_time': f'{int(cost * 60)} minutes',
        'nodes_recommended': 1 if n_atoms < 100 else 2
    }


if __name__ == "__main__":
    # 테스트
    agent = PhysicsAgent()

    test_messages = [
        "MoS2 밴드 구조 계산해줘",
        "WS2/MoS2 이종구조 구조 최적화",
        "그래핀 DOS 계산"
    ]

    for msg in test_messages:
        print(f"\n📝 입력: {msg}")
        result = agent.handle(msg)
        print(f"✅ 결과: {result}")
