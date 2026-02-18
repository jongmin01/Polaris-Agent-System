"""
PhD Tools - Anthropic tool wrappers for phd_agent.py
"""

import sys
import json
import os
from pathlib import Path

# Add project root to path for imports
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Graceful imports
_PhDAgent = None
_import_error = None

try:
    from phd_agent import PhDAgent
    _PhDAgent = PhDAgent
except Exception as e:
    _import_error = str(e)


# ---------------------------------------------------------------------------
# Tool definitions (Anthropic schema)
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "phd_agent_handle",
        "description": "PhD 연구 에이전트. 논문 검색/분석, 물리 계산, TA 이메일 라우팅.",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_message": {
                    "type": "string",
                    "description": "Natural language request (e.g. 'MoS2 논문 검색해줘', 'DFT band structure calculation')"
                }
            },
            "required": ["user_message"]
        }
    }
]


# ---------------------------------------------------------------------------
# Handler functions
# ---------------------------------------------------------------------------

def handle_phd_agent_handle(user_message: str) -> str:
    """Handle a PhD agent request."""
    if _PhDAgent is None:
        return json.dumps({"error": f"PhDAgent unavailable: {_import_error}"})
    try:
        obsidian_path = os.getenv("OBSIDIAN_PATH", "")
        agent = _PhDAgent(obsidian_path)
        result = agent.handle(user_message)
        return json.dumps(result, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


# Map tool names to handlers
HANDLERS = {
    "phd_agent_handle": handle_phd_agent_handle,
}
