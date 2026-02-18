"""
Calendar Tools - Anthropic tool wrappers for schedule_agent.py
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# Add project root to path for imports
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Graceful imports
_ScheduleAgent = None
_import_error = None

try:
    from schedule_agent import ScheduleAgent
    _ScheduleAgent = ScheduleAgent
except Exception as e:
    _import_error = str(e)


# ---------------------------------------------------------------------------
# Tool definitions (Anthropic schema)
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "get_calendar_briefing",
        "description": "오늘/내일 iCloud 캘린더 일정 조회. NOT for: 날씨, 뉴스, 논문 검색.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "add_calendar_event",
        "description": "iCloud 캘린더에 새 일정 추가.",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "Event title"
                },
                "start_time": {
                    "type": "string",
                    "description": "Start time in ISO 8601 format (e.g. '2026-02-08T14:00:00')"
                },
                "end_time": {
                    "type": "string",
                    "description": "End time in ISO 8601 format. If omitted, defaults to start_time + 1 hour."
                },
                "location": {
                    "type": "string",
                    "description": "Event location (optional)"
                },
                "description": {
                    "type": "string",
                    "description": "Event description (optional)"
                },
                "all_day": {
                    "type": "boolean",
                    "description": "Whether this is an all-day event (default: false)"
                }
            },
            "required": ["summary", "start_time"]
        }
    }
]


# ---------------------------------------------------------------------------
# Handler functions
# ---------------------------------------------------------------------------

def handle_get_calendar_briefing() -> str:
    """Get daily calendar briefing."""
    if _ScheduleAgent is None:
        return json.dumps({"error": f"ScheduleAgent unavailable: {_import_error}"})
    try:
        agent = _ScheduleAgent()
        briefing = agent.get_daily_briefing()
        formatted = agent.format_daily_briefing(briefing)
        return json.dumps({
            "today": [_serialize_event(e) for e in briefing.get("today", [])],
            "tomorrow": [_serialize_event(e) for e in briefing.get("tomorrow", [])],
            "status": briefing.get("status"),
            "message": briefing.get("message"),
            "formatted": formatted
        }, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


def handle_add_calendar_event(
    summary: str,
    start_time: str,
    end_time: str = None,
    location: str = "",
    description: str = "",
    all_day: bool = False
) -> str:
    """Add a calendar event."""
    if _ScheduleAgent is None:
        return json.dumps({"error": f"ScheduleAgent unavailable: {_import_error}"})
    try:
        agent = _ScheduleAgent()
        start_dt = datetime.fromisoformat(start_time)
        end_dt = datetime.fromisoformat(end_time) if end_time else None
        result = agent.add_event(
            summary=summary,
            start_time=start_dt,
            end_time=end_dt,
            location=location,
            description=description,
            all_day=all_day
        )
        return json.dumps(result, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


def _serialize_event(event: dict) -> dict:
    """Convert datetime objects in event dict to ISO strings."""
    result = dict(event)
    for key in ("start", "end"):
        if key in result and hasattr(result[key], "isoformat"):
            result[key] = result[key].isoformat()
    return result


# Map tool names to handlers
HANDLERS = {
    "get_calendar_briefing": handle_get_calendar_briefing,
    "add_calendar_event": handle_add_calendar_event,
}
