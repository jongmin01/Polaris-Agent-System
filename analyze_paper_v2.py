#!/usr/bin/env python3
"""
논문 분석 스크립트 v2
Gemini 2.5 Flash / Claude Sonnet 4.5 지원
"""

import os
from dotenv import load_dotenv

load_dotenv()

# API 설정
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')

# LLM 초기화
gemini_model = None
claude_client = None

if GEMINI_API_KEY:
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel('gemini-2.5-flash')
    except Exception as e:
        print(f"⚠️  Gemini 초기화 실패: {e}")

if ANTHROPIC_API_KEY:
    try:
        import anthropic
        claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    except Exception as e:
        print(f"⚠️  Claude 초기화 실패: {e}")


ANALYSIS_PROMPT = """다음 논문을 분석해주세요:

{content}

다음 형식으로 분석해주세요:

## 핵심 요약 (3-5문장)
[논문의 핵심 내용을 간단히 요약]

## 주요 발견
- 발견 1
- 발견 2
- 발견 3

## 연구 방법론
[사용된 방법론 설명]

## 기술적 세부사항
[DFT 계산, 실험 조건 등]

## 나의 연구와의 연관성
[이 논문이 2D materials/Janus TMDC 연구에 어떻게 도움이 되는지]

## 참고할 만한 레퍼런스
[논문에서 인용된 중요한 참고문헌]
"""


def analyze_with_gemini(content: str) -> str:
    """
    Gemini로 논문 분석

    Args:
        content: 논문 텍스트 또는 PDF 경로

    Returns:
        분석 결과 텍스트
    """
    if not gemini_model:
        return "❌ Gemini API key가 설정되지 않았습니다."

    try:
        # PDF 파일인 경우
        if isinstance(content, str) and content.endswith('.pdf'):
            # PDF를 텍스트로 변환 (간단한 구현)
            content = extract_text_from_pdf(content)

        prompt = ANALYSIS_PROMPT.format(content=content[:30000])  # 토큰 제한
        response = gemini_model.generate_content(prompt)

        return response.text

    except Exception as e:
        return f"❌ Gemini 분석 실패: {str(e)}"


def analyze_with_claude(content: str) -> str:
    """
    Claude로 논문 분석

    Args:
        content: 논문 텍스트 또는 PDF 경로

    Returns:
        분석 결과 텍스트
    """
    if not claude_client:
        return "❌ Claude API key가 설정되지 않았습니다."

    try:
        # PDF 파일인 경우
        if isinstance(content, str) and content.endswith('.pdf'):
            content = extract_text_from_pdf(content)

        message = claude_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": ANALYSIS_PROMPT.format(content=content[:100000])
                }
            ]
        )

        return message.content[0].text

    except Exception as e:
        return f"❌ Claude 분석 실패: {str(e)}"


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    PDF에서 텍스트 추출

    Args:
        pdf_path: PDF 파일 경로

    Returns:
        추출된 텍스트
    """
    try:
        import PyPDF2

        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = ""
            for page in reader.pages[:10]:  # 첫 10페이지만
                text += page.extract_text()

        return text

    except ImportError:
        return "⚠️  PyPDF2가 설치되지 않았습니다. pip install PyPDF2"
    except Exception as e:
        return f"❌ PDF 읽기 실패: {str(e)}"


def create_analysis_file(citekey: str, analysis_text: str, llm_name: str, paper_path: str) -> str:
    """
    분석 결과를 파일로 저장

    Args:
        citekey: 논문 cite key
        analysis_text: 분석 결과
        llm_name: "gemini" 또는 "claude"
        paper_path: 논문 PDF 경로

    Returns:
        저장된 파일 경로
    """
    # 논문과 같은 폴더에 저장
    paper_dir = os.path.dirname(paper_path)
    filename = f"{citekey}_{llm_name.lower()}_analysis.md"
    filepath = os.path.join(paper_dir, filename)

    # Markdown 형식으로 저장
    content = f"""---
paper: {citekey}
analyzed_by: {llm_name.title()}
date: {import_date()}
---

# {citekey} - {llm_name.title()} 분석

{analysis_text}

---

**분석 도구**: {llm_name.title()}
**원본 논문**: [[{citekey}]]
"""

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    return filepath


def import_date():
    """현재 날짜 반환"""
    from datetime import datetime
    return datetime.now().strftime('%Y-%m-%d')


def interactive_analysis(paper_path: str):
    """
    대화형 논문 분석

    사용자에게 LLM 선택을 요청하고 분석 수행
    """
    print(f"\n📄 논문: {os.path.basename(paper_path)}")
    print("\n어떤 LLM으로 분석하시겠습니까?")
    print("1. Gemini 2.5 Flash (무료, 빠름)")
    print("2. Claude Sonnet 4.5 (유료 ~$0.25, 정확함)")

    choice = input("\n선택 (1 또는 2): ").strip()

    if choice == "1":
        print("\n🤖 Gemini로 분석 중...")
        result = analyze_with_gemini(paper_path)
        llm_name = "gemini"
    elif choice == "2":
        confirm = input("⚠️  Claude 사용 시 비용이 발생합니다. 계속하시겠습니까? (y/n): ")
        if confirm.lower() != 'y':
            print("❌ 취소되었습니다.")
            return

        print("\n🤖 Claude로 분석 중...")
        result = analyze_with_claude(paper_path)
        llm_name = "claude"
    else:
        print("❌ 잘못된 선택입니다.")
        return

    # 결과 출력
    print("\n" + "="*60)
    print("📊 분석 결과")
    print("="*60)
    print(result)
    print("="*60)

    # 저장 여부 확인
    save = input("\n💾 분석 결과를 저장하시겠습니까? (y/n): ")
    if save.lower() == 'y':
        # Citekey 추출 (파일명에서)
        citekey = os.path.basename(paper_path).replace('.pdf', '')
        filepath = create_analysis_file(citekey, result, llm_name, paper_path)
        print(f"✅ 저장 완료: {filepath}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("사용법: python analyze_paper_v2.py <pdf_path>")
        sys.exit(1)

    paper_path = sys.argv[1]

    if not os.path.exists(paper_path):
        print(f"❌ 파일을 찾을 수 없습니다: {paper_path}")
        sys.exit(1)

    interactive_analysis(paper_path)
