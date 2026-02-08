#!/usr/bin/env python3
"""
PhD-Agent - 연구 자동화 Agent

기존 코드 통합:
- paper_workflow.py (논문 검색/다운로드)
- analyze_paper_v2.py (논문 분석)
"""

import os
import re
from typing import Dict, List, Optional
from paper_workflow import search_arxiv, search_semantic_scholar, download_pdf, create_paper_note, generate_citekey
from analyze_paper_v2 import analyze_with_gemini, analyze_with_claude, create_analysis_file
from physics_agent import PhysicsAgent


class PhDAgent:
    """
    PhD-Agent: 연구 업무 자동화

    Sub-agents:
    - Paper-Agent: 논문 검색/다운로드/분석 ✅
    - Email-Agent: TA 메일 관리 (개발중)
    - Physics-Agent: VASP/ONETEP 계산 자동화 ✅
    """

    def __init__(self, obsidian_path: str):
        """
        Args:
            obsidian_path: Obsidian 폴더 경로
        """
        self.obsidian_path = obsidian_path
        self.papers_dir = os.path.join(obsidian_path, "My Second Brain/01_PhD_Research/02_Resources/Papers/zotero")

        # Sub-agent 상태
        self.agents = {
            "paper": True,          # ✅ 구현됨
            "email": False,         # 🚧 개발중
            "physics": PhysicsAgent()  # ✅ 구현됨
        }

    def handle(self, user_message: str) -> Dict:
        """
        사용자 메시지 처리

        Args:
            user_message: 사용자 입력

        Returns:
            처리 결과 딕셔너리
        """
        msg_lower = user_message.lower()

        # 논문 검색
        if any(kw in msg_lower for kw in ["검색", "search", "찾아", "find"]):
            return self._handle_paper_search(user_message)

        # 논문 분석
        elif any(kw in msg_lower for kw in ["분석", "analyze", "요약", "summary"]):
            return self._handle_paper_analysis(user_message)

        # TA 메일
        elif any(kw in msg_lower for kw in ["메일", "email", "학생", "student"]):
            return {
                "status": "not_implemented",
                "message": "📧 Email-Agent는 아직 개발중입니다.\n\n구현 예정 기능:\n- TA 학생 메일 자동 분류\n- 템플릿 기반 답장 제안\n- 메일 로그 Obsidian 저장"
            }

        # Physics 계산 (DFT, VASP, ONETEP 등)
        elif self._is_physics_request(msg_lower):
            return self.agents['physics'].handle(user_message)

        # 일반 PhD 질문
        else:
            return {
                "status": "unclear",
                "message": "PhD-Agent가 도울 수 있는 작업:\n\n📚 논문 검색/분석\n📧 TA 메일 관리 (개발중)\n🔬 DFT 계산 (개발중)\n\n더 구체적으로 말씀해주세요!"
            }

    def _handle_paper_search(self, user_message: str) -> Dict:
        """논문 검색 처리"""
        # 검색어 추출
        query = self._extract_search_query(user_message)

        if not query:
            return {
                "status": "error",
                "message": "검색어를 찾을 수 없습니다. 예: 'MoS2 논문 검색해줘'"
            }

        try:
            # arXiv 검색 (무료 API)
            results = search_arxiv(query, max_results=5)

            if not results:
                # Semantic Scholar로 폴백
                results = search_semantic_scholar(query, max_results=5)

            if not results:
                return {
                    "status": "no_results",
                    "message": f"'{query}'에 대한 검색 결과가 없습니다."
                }

            # 결과 포맷팅
            formatted_results = self._format_search_results(results)

            return {
                "status": "success",
                "query": query,
                "count": len(results),
                "results": results,
                "formatted_message": formatted_results
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"검색 중 오류 발생: {str(e)}"
            }

    def _handle_paper_analysis(self, user_message: str) -> Dict:
        """논문 분석 처리"""
        return {
            "status": "needs_paper",
            "message": "분석할 논문을 먼저 검색하거나 업로드해주세요.\n\n예: '/search MoS2' 후 논문 선택"
        }

    def _extract_search_query(self, message: str) -> Optional[str]:
        """
        메시지에서 검색어 추출

        예:
        "MoS2 논문 검색해줘" → "MoS2"
        "Janus TMDC heterostructure 찾아줘" → "Janus TMDC heterostructure"
        """
        # 불필요한 단어 제거
        stopwords = [
            "논문", "paper", "검색", "search", "찾아", "find",
            "해줘", "해주세요", "주세요", "please",
            "알려", "줘", "좀"
        ]

        words = message.split()
        query_words = [w for w in words if w.lower() not in stopwords]

        return " ".join(query_words).strip() if query_words else None

    def _is_physics_request(self, msg_lower: str) -> bool:
        """
        Physics-Agent 요청 여부를 지능적으로 판단

        명시적 키워드:
        - 툴 이름: VASP, ONETEP
        - 계산 유형: DFT, 밴드, DOS, relaxation

        맥락 기반 키워드:
        - 대규모 시스템: "대규모", "큰", "large", "many atoms"
        - 물질 구조: "구조 최적화", "relaxation", "optimization"
        - 계산 요청: "계산", "simulation", "compute"
        - HPC 관련: "Polaris", "HPC", "submit", "job"
        """
        # 1. 명시적 Physics 키워드
        explicit_keywords = [
            "dft", "vasp", "onetep",
            "밴드", "band", "band structure",
            "dos", "density of states", "상태밀도",
            "relaxation", "optimization", "최적화", "구조최적화",
            "phonon", "포논", "진동"
        ]

        if any(kw in msg_lower for kw in explicit_keywords):
            return True

        # 2. 맥락 기반 판단 (계산 + 재료)
        calculation_keywords = ["계산", "simulation", "sim", "compute", "run"]
        material_keywords = ["mos2", "ws2", "graphene", "그래핀", "tmdc", "이종구조", "heterostructure"]

        has_calculation = any(kw in msg_lower for kw in calculation_keywords)
        has_material = any(kw in msg_lower for kw in material_keywords)

        if has_calculation and has_material:
            return True

        # 3. 대규모 시스템 키워드
        large_system_keywords = ["대규모", "큰", "large", "many atoms", "수백", "hundreds"]
        if any(kw in msg_lower for kw in large_system_keywords):
            return True

        # 4. HPC 관련
        hpc_keywords = ["polaris", "hpc", "submit", "job", "클러스터", "cluster"]
        if any(kw in msg_lower for kw in hpc_keywords):
            return True

        return False

    def _format_search_results(self, results: List[Dict]) -> str:
        """검색 결과를 읽기 쉬운 형식으로 변환"""
        if not results:
            return "검색 결과 없음"

        formatted = f"📚 검색 결과 ({len(results)}개)\n\n"

        for i, paper in enumerate(results, 1):
            title = paper.get('title', 'No title')
            authors = paper.get('authors', 'Unknown')
            year = paper.get('year', 'N/A')
            journal = paper.get('journal', '')

            # authors가 리스트인 경우 처리
            if isinstance(authors, list):
                authors_str = ", ".join(authors[:3])  # 첫 3명만
                if len(authors) > 3:
                    authors_str += " et al."
            else:
                authors_str = authors

            formatted += f"{i}. **{title}**\n"
            formatted += f"   👤 {authors_str}\n"
            formatted += f"   📅 {year}"
            if journal:
                formatted += f" | 📖 {journal}"
            formatted += "\n\n"

        formatted += "💡 다운로드하려면 번호를 선택하세요 (예: /download 1)"

        return formatted

    def download_and_save(self, paper: Dict, llm_choice: str = "gemini") -> Dict:
        """
        논문 다운로드 및 Obsidian 저장

        Args:
            paper: 논문 메타데이터
            llm_choice: "gemini" 또는 "claude"

        Returns:
            처리 결과
        """
        try:
            # Citekey 생성
            authors = paper.get('authors', ['Unknown'])
            year = paper.get('year', '2024')
            citekey = generate_citekey(authors, year)

            # 폴더 생성
            paper_dir = os.path.join(self.papers_dir, citekey)
            os.makedirs(paper_dir, exist_ok=True)

            # PDF 다운로드
            pdf_url = paper.get('pdf_url')
            if pdf_url:
                pdf_path = os.path.join(paper_dir, f"{citekey}.pdf")
                download_pdf(pdf_url, pdf_path)
            else:
                pdf_path = None

            # 메타데이터 노트 생성
            note_path = create_paper_note(paper, paper_dir)

            # 분석 (선택적)
            analysis_path = None
            if pdf_path and os.path.exists(pdf_path):
                if llm_choice == "gemini":
                    analysis = analyze_with_gemini(pdf_path)
                else:
                    analysis = analyze_with_claude(pdf_path)

                if analysis and not analysis.startswith("❌"):
                    analysis_path = create_analysis_file(citekey, analysis, llm_choice, pdf_path)

            return {
                "status": "success",
                "citekey": citekey,
                "pdf_path": pdf_path,
                "note_path": note_path,
                "analysis_path": analysis_path,
                "message": f"✅ 논문 저장 완료!\n\n📁 {citekey}\n📄 Papers_Zotero_v3 노트 생성\n🤖 {llm_choice.title()} 분석 완료"
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"논문 저장 중 오류: {str(e)}"
            }


# 테스트용
def test_phd_agent():
    """PhD-Agent 테스트"""
    # 실제 경로는 환경에 맞게 수정
    obsidian_path = "/path/to/Obsidian"
    agent = PhDAgent(obsidian_path)

    test_messages = [
        "MoS2 논문 검색해줘",
        "Janus TMDC 분석",
        "TA 학생 메일 확인",
        "DFT 계산 제출"
    ]

    print("🎓 PhD-Agent Test\n")

    for msg in test_messages:
        print(f"📨 입력: {msg}")
        result = agent.handle(msg)
        print(f"   → Status: {result['status']}")
        print(f"   → Message: {result['message'][:80]}...")
        print()


if __name__ == "__main__":
    test_phd_agent()
