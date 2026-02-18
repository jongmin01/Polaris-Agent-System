"""
arXiv / Paper Tools - Anthropic tool wrappers for paper_workflow.py and analyze_paper_v2.py
"""

import sys
import json
from pathlib import Path

# Add project root to path for imports
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Graceful imports
_search_arxiv = None
_search_semantic_scholar = None
_download_pdf = None
_analyze_with_gemini = None
_analyze_with_claude = None
_import_errors = []

try:
    from paper_workflow import search_arxiv, search_semantic_scholar, download_pdf
    _search_arxiv = search_arxiv
    _search_semantic_scholar = search_semantic_scholar
    _download_pdf = download_pdf
except Exception as e:
    _import_errors.append(f"paper_workflow: {e}")

try:
    from analyze_paper_v2 import analyze_with_gemini, analyze_with_claude
    _analyze_with_gemini = analyze_with_gemini
    _analyze_with_claude = analyze_with_claude
except Exception as e:
    _import_errors.append(f"analyze_paper_v2: {e}")


# ---------------------------------------------------------------------------
# Tool definitions (Anthropic schema)
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "search_arxiv",
        "description": "arXiv 논문 검색. 키워드로 논문 목록 반환 (제목, 저자, abstract). NOT for: 일상 대화, 이메일, 일정.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (e.g. 'MoS2 band structure DFT')"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 10)"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "search_semantic_scholar",
        "description": "Semantic Scholar 논문 검색. 인용 데이터 포함. NOT for: 일상 대화, 이메일, 일정.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (e.g. 'Janus TMDC heterostructure')"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 10)"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "download_paper_pdf",
        "description": "논문 PDF 다운로드. URL → 로컬 저장.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pdf_url": {
                    "type": "string",
                    "description": "URL of the PDF to download"
                },
                "save_path": {
                    "type": "string",
                    "description": "Local file path to save the PDF to"
                }
            },
            "required": ["pdf_url", "save_path"]
        }
    },
    {
        "name": "analyze_paper_gemini",
        "description": "Gemini로 논문 분석. 텍스트/PDF → 요약, 핵심 결과, 방법론.",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "Paper text content or path to a PDF file"
                }
            },
            "required": ["content"]
        }
    },
    {
        "name": "analyze_paper_claude",
        "description": "Claude로 논문 분석. 텍스트/PDF → 요약, 핵심 결과, 방법론.",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "Paper text content or path to a PDF file"
                }
            },
            "required": ["content"]
        }
    }
]


# ---------------------------------------------------------------------------
# Handler functions
# ---------------------------------------------------------------------------

def handle_search_arxiv(query: str, max_results: int = 10) -> str:
    """Search arXiv for papers."""
    if _search_arxiv is None:
        return json.dumps({"error": f"paper_workflow unavailable: {_import_errors}"})
    try:
        results = _search_arxiv(query, max_results)
        return json.dumps({"papers": results, "count": len(results)}, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


def handle_search_semantic_scholar(query: str, max_results: int = 10) -> str:
    """Search Semantic Scholar for papers."""
    if _search_semantic_scholar is None:
        return json.dumps({"error": f"paper_workflow unavailable: {_import_errors}"})
    try:
        results = _search_semantic_scholar(query, max_results)
        return json.dumps({"papers": results, "count": len(results)}, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


def handle_download_paper_pdf(pdf_url: str, save_path: str) -> str:
    """Download a paper PDF."""
    if _download_pdf is None:
        return json.dumps({"error": f"paper_workflow unavailable: {_import_errors}"})
    try:
        success = _download_pdf(pdf_url, save_path)
        return json.dumps({"success": success, "save_path": save_path})
    except Exception as e:
        return json.dumps({"error": str(e)})


def handle_analyze_paper_gemini(content: str) -> str:
    """Analyze paper with Gemini."""
    if _analyze_with_gemini is None:
        return json.dumps({"error": f"analyze_paper_v2 unavailable: {_import_errors}"})
    try:
        result = _analyze_with_gemini(content)
        return json.dumps({"analysis": result})
    except Exception as e:
        return json.dumps({"error": str(e)})


def handle_analyze_paper_claude(content: str) -> str:
    """Analyze paper with Claude."""
    if _analyze_with_claude is None:
        return json.dumps({"error": f"analyze_paper_v2 unavailable: {_import_errors}"})
    try:
        result = _analyze_with_claude(content)
        return json.dumps({"analysis": result})
    except Exception as e:
        return json.dumps({"error": str(e)})


# Map tool names to handlers
HANDLERS = {
    "search_arxiv": handle_search_arxiv,
    "search_semantic_scholar": handle_search_semantic_scholar,
    "download_paper_pdf": handle_download_paper_pdf,
    "analyze_paper_gemini": handle_analyze_paper_gemini,
    "analyze_paper_claude": handle_analyze_paper_claude,
}
