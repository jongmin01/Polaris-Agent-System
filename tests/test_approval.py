"""Tests for polaris.approval_gate.ApprovalGate."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from polaris.approval_gate import ApprovalGate, RiskLevel, TOOL_RISK_MAP


@pytest.fixture
def gate():
    return ApprovalGate()


@pytest.fixture
def mock_bot():
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    return bot


@pytest.fixture
def sync_executor():
    """A simple synchronous tool executor."""
    def execute(**kwargs):
        return f"executed with {kwargs}"
    return execute


@pytest.fixture
def async_executor():
    """An async tool executor."""
    async def execute(**kwargs):
        return f"async executed with {kwargs}"
    return execute


class TestAutoLevel:
    @pytest.mark.asyncio
    async def test_auto_executes_immediately(self, gate, sync_executor):
        # "arxiv_search" is mapped to AUTO in TOOL_RISK_MAP
        result = await gate.execute_with_approval(
            tool_name="arxiv_search",
            tool_args={"query": "MoS2"},
            execute_fn=sync_executor,
        )
        assert result["approved"] is True
        assert result["approval_level"] == "AUTO"
        assert "MoS2" in result["result"]

    @pytest.mark.asyncio
    async def test_auto_no_bot_needed(self, gate, sync_executor):
        # AUTO level should work without bot/chat_id
        result = await gate.execute_with_approval(
            tool_name="arxiv_search",
            tool_args={"query": "test"},
            execute_fn=sync_executor,
            bot=None,
            chat_id=None,
        )
        assert result["approved"] is True

    @pytest.mark.asyncio
    async def test_auto_with_async_executor(self, gate, async_executor):
        result = await gate.execute_with_approval(
            tool_name="arxiv_search",
            tool_args={"query": "test"},
            execute_fn=async_executor,
        )
        assert result["approved"] is True
        assert "test" in result["result"]


class TestConfirmLevel:
    @pytest.mark.asyncio
    async def test_confirm_denied_without_bot(self, gate, sync_executor):
        # CONFIRM level without bot/chat_id should deny
        result = await gate.execute_with_approval(
            tool_name="download_pdf",
            tool_args={"url": "http://example.com"},
            execute_fn=sync_executor,
            bot=None,
            chat_id=None,
        )
        assert result["approved"] is False
        assert result["result"] is None
        assert result["approval_level"] == "CONFIRM"

    @pytest.mark.asyncio
    async def test_confirm_sends_approval_request(self, gate, mock_bot, sync_executor):
        # Simulate user approving immediately
        original_request = gate._request_approval

        async def auto_approve(bot, chat_id, tool_name, tool_args, risk):
            # Simulate immediate approval
            return True

        gate._request_approval = auto_approve

        result = await gate.execute_with_approval(
            tool_name="download_pdf",
            tool_args={"url": "http://example.com"},
            execute_fn=sync_executor,
            bot=mock_bot,
            chat_id=12345,
        )
        assert result["approved"] is True
        assert result["result"] is not None

    @pytest.mark.asyncio
    async def test_confirm_denied_by_user(self, gate, mock_bot, sync_executor):
        async def auto_deny(bot, chat_id, tool_name, tool_args, risk):
            return False

        gate._request_approval = auto_deny

        result = await gate.execute_with_approval(
            tool_name="download_pdf",
            tool_args={"url": "http://example.com"},
            execute_fn=sync_executor,
            bot=mock_bot,
            chat_id=12345,
        )
        assert result["approved"] is False
        assert result["result"] is None


class TestCriticalLevel:
    @pytest.mark.asyncio
    async def test_critical_denied_without_bot(self, gate, sync_executor):
        result = await gate.execute_with_approval(
            tool_name="submit_physics_job",
            tool_args={"job": "test"},
            execute_fn=sync_executor,
            bot=None,
            chat_id=None,
        )
        assert result["approved"] is False
        assert result["approval_level"] == "CRITICAL"

    @pytest.mark.asyncio
    async def test_critical_approved(self, gate, mock_bot, sync_executor):
        async def auto_approve(bot, chat_id, tool_name, tool_args, risk):
            return True

        gate._request_approval = auto_approve

        result = await gate.execute_with_approval(
            tool_name="submit_physics_job",
            tool_args={"job": "test"},
            execute_fn=sync_executor,
            bot=mock_bot,
            chat_id=12345,
        )
        assert result["approved"] is True
        assert result["approval_level"] == "CRITICAL"


class TestTimeout:
    @pytest.mark.asyncio
    async def test_timeout_denies(self, gate, mock_bot, sync_executor):
        """Simulate a timeout by replacing _request_approval with one that times out."""
        async def timeout_approval(bot, chat_id, tool_name, tool_args, risk):
            # Simulate timeout returning False
            return False

        gate._request_approval = timeout_approval

        result = await gate.execute_with_approval(
            tool_name="analyze_emails",
            tool_args={"emails": []},
            execute_fn=sync_executor,
            bot=mock_bot,
            chat_id=12345,
        )
        assert result["approved"] is False
        assert result["result"] is None


class TestUnknownTool:
    @pytest.mark.asyncio
    async def test_unknown_tool_defaults_to_confirm(self, gate, sync_executor):
        # An unknown tool should default to CONFIRM (requires bot)
        result = await gate.execute_with_approval(
            tool_name="totally_unknown_tool",
            tool_args={},
            execute_fn=sync_executor,
            bot=None,
            chat_id=None,
        )
        # Without bot, CONFIRM level denies
        assert result["approved"] is False
        assert result["approval_level"] == "CONFIRM"

    def test_risk_map_lookup(self):
        # Verify unknown tools get CONFIRM from the gate logic
        risk = TOOL_RISK_MAP.get("totally_unknown_tool", RiskLevel.CONFIRM)
        assert risk == RiskLevel.CONFIRM


class TestCallbackHandling:
    @pytest.mark.asyncio
    async def test_handle_approve_callback(self, gate):
        # Set up a pending future
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        gate._pending["test123"] = future

        callback_query = AsyncMock()
        callback_query.data = "approve:test123"
        callback_query.message = MagicMock()
        callback_query.message.text = "Approve?"

        await gate.handle_callback(callback_query)

        assert future.result() is True
        callback_query.answer.assert_called_with("Approved")

    @pytest.mark.asyncio
    async def test_handle_deny_callback(self, gate):
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        gate._pending["test456"] = future

        callback_query = AsyncMock()
        callback_query.data = "deny:test456"
        callback_query.message = MagicMock()
        callback_query.message.text = "Approve?"

        await gate.handle_callback(callback_query)

        assert future.result() is False
        callback_query.answer.assert_called_with("Denied")

    @pytest.mark.asyncio
    async def test_handle_expired_callback(self, gate):
        callback_query = AsyncMock()
        callback_query.data = "approve:expired_id"

        await gate.handle_callback(callback_query)
        callback_query.answer.assert_called_with("This request has expired.")
