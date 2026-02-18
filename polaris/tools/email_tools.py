"""
Email Tools - Anthropic tool wrappers for email_analyzer.py
"""

import sys
import json
from pathlib import Path

# Add project root to path for imports
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Graceful imports
_EmailAnalyzer = None
_import_error = None

try:
    from email_analyzer import EmailAnalyzer
    _EmailAnalyzer = EmailAnalyzer
except Exception as e:
    _import_error = str(e)


# ---------------------------------------------------------------------------
# Tool definitions (Anthropic schema)
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "analyze_emails",
        "description": "이메일 일괄 분석. ACTION/FYI 분류, 중요도(1-5), 한국어 요약. NOT for: 논문, 일정.",
        "input_schema": {
            "type": "object",
            "properties": {
                "emails": {
                    "type": "array",
                    "description": "List of email objects to analyze",
                    "items": {
                        "type": "object",
                        "properties": {
                            "subject": {"type": "string", "description": "Email subject line"},
                            "sender": {"type": "string", "description": "Sender email address or name"},
                            "content": {"type": "string", "description": "Email body text"},
                            "date": {"type": "string", "description": "Email date string"},
                            "account": {"type": "string", "description": "Email account (e.g. 'UIC', 'Gmail')"}
                        },
                        "required": ["subject", "sender", "content", "date", "account"]
                    }
                }
            },
            "required": ["emails"]
        }
    },
    {
        "name": "analyze_single_email",
        "description": "단일 이메일 분석. ACTION/FYI 분류, 중요도, 한국어 요약.",
        "input_schema": {
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "Email subject line"},
                "sender": {"type": "string", "description": "Sender email address or name"},
                "content": {"type": "string", "description": "Email body text"},
                "date": {"type": "string", "description": "Email date string"},
                "account": {"type": "string", "description": "Email account (e.g. 'UIC', 'Gmail')"}
            },
            "required": ["subject", "sender", "content", "date", "account"]
        }
    }
]


# ---------------------------------------------------------------------------
# Helper to serialize analysis results
# ---------------------------------------------------------------------------

def _serialize_analysis(analysis: dict) -> dict:
    """Convert EmailCategory enums to strings for JSON serialization."""
    result = dict(analysis)
    if "category" in result and hasattr(result["category"], "value"):
        result["category"] = result["category"].value
    return result


# ---------------------------------------------------------------------------
# Handler functions
# ---------------------------------------------------------------------------

def handle_analyze_emails(emails: list) -> str:
    """Analyze a batch of emails."""
    if _EmailAnalyzer is None:
        return json.dumps({"error": f"EmailAnalyzer unavailable: {_import_error}"})
    try:
        analyzer = _EmailAnalyzer()
        results = analyzer.analyze_batch(emails)
        serialized = []
        for item in results:
            serialized.append({
                "mail": item["mail"],
                "analysis": _serialize_analysis(item["analysis"])
            })
        return json.dumps({"results": serialized, "count": len(serialized)}, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


def handle_analyze_single_email(subject: str, sender: str, content: str, date: str, account: str) -> str:
    """Analyze a single email."""
    if _EmailAnalyzer is None:
        return json.dumps({"error": f"EmailAnalyzer unavailable: {_import_error}"})
    try:
        analyzer = _EmailAnalyzer()
        mail = {
            "subject": subject,
            "sender": sender,
            "content": content,
            "date": date,
            "account": account
        }
        analysis = analyzer.analyze_email(mail)
        return json.dumps(_serialize_analysis(analysis), default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


# Map tool names to handlers
HANDLERS = {
    "analyze_emails": handle_analyze_emails,
    "analyze_single_email": handle_analyze_single_email,
}
