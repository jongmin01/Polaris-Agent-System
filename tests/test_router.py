"""Tests for polaris.router.PolarisRouter (ReAct loop).

Default backend is Ollama (OpenAI-compatible). Tests mock the OpenAI client.
"""

import json
import pytest
from unittest.mock import patch, MagicMock


# ---------- helpers for building mock OpenAI responses ----------

def _make_tool_call(call_id, name, arguments):
    """Create a mock OpenAI tool call object."""
    tc = MagicMock()
    tc.id = call_id
    tc.function.name = name
    tc.function.arguments = json.dumps(arguments)
    return tc


def _make_choice(finish_reason, content=None, tool_calls=None):
    """Create a mock OpenAI Choice."""
    choice = MagicMock()
    choice.finish_reason = finish_reason
    choice.message.content = content
    choice.message.tool_calls = tool_calls
    return choice


def _make_response(choices):
    """Create a mock OpenAI ChatCompletion response."""
    resp = MagicMock()
    resp.choices = choices
    return resp


# ---------- helpers for building mock Anthropic responses ----------

def _make_text_block(text):
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def _make_tool_use_block(tool_id, name, input_args):
    block = MagicMock()
    block.type = "tool_use"
    block.id = tool_id
    block.name = name
    block.input = input_args
    return block


def _make_anthropic_response(stop_reason, content_blocks):
    resp = MagicMock()
    resp.stop_reason = stop_reason
    resp.content = content_blocks
    return resp


# ================================================================
# Tests — Ollama (default) backend
# ================================================================

class TestRouteSimpleText:
    @patch("polaris.router.PolarisRouter._init_ollama")
    @patch("polaris.router.PolarisRouter._load_tools")
    def test_text_only_response(self, mock_load, mock_init):
        from polaris.router import PolarisRouter

        router = PolarisRouter()
        mock_client = MagicMock()
        router.client = mock_client

        resp = _make_response([_make_choice("stop", content="Hello!")])
        mock_client.chat.completions.create.return_value = resp

        result = router.route("Hi there")
        assert result["response"] == "Hello!"
        assert result["tools_used"] == []

    @patch("polaris.router.PolarisRouter._init_ollama")
    @patch("polaris.router.PolarisRouter._load_tools")
    def test_empty_text_response(self, mock_load, mock_init):
        from polaris.router import PolarisRouter

        router = PolarisRouter()
        mock_client = MagicMock()
        router.client = mock_client

        resp = _make_response([_make_choice("stop", content="")])
        mock_client.chat.completions.create.return_value = resp

        result = router.route("Hi")
        assert result["response"] == ""
        assert result["tools_used"] == []


class TestRouteWithToolUse:
    @patch("polaris.router.PolarisRouter._init_ollama")
    @patch("polaris.router.PolarisRouter._load_tools")
    def test_tool_use_then_text(self, mock_load, mock_init):
        from polaris.router import PolarisRouter

        router = PolarisRouter()
        mock_client = MagicMock()
        router.client = mock_client

        # First call: model wants to call a tool
        tool_resp = _make_response([_make_choice(
            "tool_calls",
            tool_calls=[_make_tool_call("tc_1", "search_arxiv", {"query": "MoS2"})],
        )])
        # Second call: model returns final text
        final_resp = _make_response([_make_choice("stop", content="Found 3 papers about MoS2.")])
        mock_client.chat.completions.create.side_effect = [tool_resp, final_resp]

        with patch.object(router, "_execute_tool", return_value='{"papers": []}'):
            result = router.route("Search MoS2 papers")

        assert result["response"] == "Found 3 papers about MoS2."
        assert "search_arxiv" in result["tools_used"]

    @patch("polaris.router.PolarisRouter._init_ollama")
    @patch("polaris.router.PolarisRouter._load_tools")
    def test_multiple_tool_calls(self, mock_load, mock_init):
        from polaris.router import PolarisRouter

        router = PolarisRouter()
        mock_client = MagicMock()
        router.client = mock_client

        # First call: two tool calls
        tool_resp = _make_response([_make_choice(
            "tool_calls",
            tool_calls=[
                _make_tool_call("tc_1", "search_arxiv", {"query": "MoS2"}),
                _make_tool_call("tc_2", "get_calendar_briefing", {}),
            ],
        )])
        final_resp = _make_response([_make_choice("stop", content="Here are results.")])
        mock_client.chat.completions.create.side_effect = [tool_resp, final_resp]

        with patch.object(router, "_execute_tool", return_value='{"ok": true}'):
            result = router.route("Search papers and check schedule")

        assert "search_arxiv" in result["tools_used"]
        assert "get_calendar_briefing" in result["tools_used"]
        assert len(result["tools_used"]) == 2


class TestMaxIterations:
    @patch("polaris.router.PolarisRouter._init_ollama")
    @patch("polaris.router.PolarisRouter._load_tools")
    def test_stops_at_max_iterations(self, mock_load, mock_init):
        from polaris.router import PolarisRouter

        router = PolarisRouter(max_iterations=3)
        mock_client = MagicMock()
        router.client = mock_client

        # Every call returns tool_calls — should stop at 3
        tool_resp = _make_response([_make_choice(
            "tool_calls",
            content="Thinking...",
            tool_calls=[_make_tool_call("tc_x", "search_arxiv", {"query": "loop"})],
        )])
        mock_client.chat.completions.create.return_value = tool_resp

        with patch.object(router, "_execute_tool", return_value='{"ok": true}'):
            result = router.route("Keep searching")

        assert len(result["tools_used"]) == 3
        assert result["response"] is not None


class TestConversationHistory:
    @patch("polaris.router.PolarisRouter._init_ollama")
    @patch("polaris.router.PolarisRouter._load_tools")
    def test_history_passed_to_api(self, mock_load, mock_init):
        from polaris.router import PolarisRouter

        router = PolarisRouter()
        mock_client = MagicMock()
        router.client = mock_client

        resp = _make_response([_make_choice("stop", content="OK")])
        mock_client.chat.completions.create.return_value = resp

        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        router.route("Follow up question", conversation_history=history)

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        messages = call_kwargs["messages"]
        # system + history(2) + user(1) = 4
        assert len(messages) == 4
        assert messages[0]["role"] == "system"
        assert messages[1]["content"] == "Hello"
        assert messages[2]["content"] == "Hi there!"
        assert messages[3]["content"] == "Follow up question"

    @patch("polaris.router.PolarisRouter._init_ollama")
    @patch("polaris.router.PolarisRouter._load_tools")
    def test_no_history(self, mock_load, mock_init):
        from polaris.router import PolarisRouter

        router = PolarisRouter()
        mock_client = MagicMock()
        router.client = mock_client

        resp = _make_response([_make_choice("stop", content="OK")])
        mock_client.chat.completions.create.return_value = resp

        router.route("Just a message")

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        messages = call_kwargs["messages"]
        # system + user = 2
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"


class TestErrorHandling:
    @patch("polaris.router.PolarisRouter._init_ollama")
    @patch("polaris.router.PolarisRouter._load_tools")
    def test_api_error(self, mock_load, mock_init):
        from openai import APIError
        from polaris.router import PolarisRouter

        router = PolarisRouter()
        mock_client = MagicMock()
        router.client = mock_client

        mock_client.chat.completions.create.side_effect = APIError(
            message="Server error",
            request=MagicMock(),
            body=None,
        )

        result = router.route("Test message")
        assert "error" in result["response"].lower() or "API error" in result["response"]

    @patch("polaris.router.PolarisRouter._init_ollama")
    @patch("polaris.router.PolarisRouter._load_tools")
    def test_auth_error(self, mock_load, mock_init):
        from openai import AuthenticationError
        from polaris.router import PolarisRouter

        router = PolarisRouter()
        mock_client = MagicMock()
        router.client = mock_client

        mock_client.chat.completions.create.side_effect = AuthenticationError(
            message="Invalid API key",
            response=MagicMock(status_code=401, headers={}),
            body=None,
        )

        result = router.route("Test message")
        assert "authentication" in result["response"].lower() or "API" in result["response"]

    @patch("polaris.router.PolarisRouter._init_ollama")
    @patch("polaris.router.PolarisRouter._load_tools")
    def test_tool_execution_error(self, mock_load, mock_init):
        from polaris.router import PolarisRouter

        router = PolarisRouter()
        mock_client = MagicMock()
        router.client = mock_client

        tool_resp = _make_response([_make_choice(
            "tool_calls",
            tool_calls=[_make_tool_call("tc_1", "bad_tool", {})],
        )])
        final_resp = _make_response([_make_choice(
            "stop", content="The tool failed but I can help anyway."
        )])
        mock_client.chat.completions.create.side_effect = [tool_resp, final_resp]

        with patch.object(router, "_execute_tool", return_value="Tool 'bad_tool' failed: connection error"):
            result = router.route("Do something")

        assert "bad_tool" in result["tools_used"]
        assert len(result["response"]) > 0


# ================================================================
# Tests — Anthropic backend (paid, opt-in)
# ================================================================

class TestAnthropicBackendBlocked:
    @patch("polaris.router.PolarisRouter._init_anthropic")
    @patch("polaris.router.PolarisRouter._load_tools")
    @patch.dict("os.environ", {"POLARIS_LLM_BACKEND": "anthropic", "POLARIS_ALLOW_PAID_API": "false"})
    def test_paid_api_blocked_by_default(self, mock_load, mock_init):
        from polaris.router import PolarisRouter

        router = PolarisRouter()
        result = router.route("Test")

        assert "paid API" in result["response"]
        assert result["tools_used"] == []
