"""
Polaris Approval Gate — Risk-based execution control with Telegram approval flow.

Classifies every tool invocation into one of three risk levels and, for
non-trivial operations, requests user approval via Telegram inline keyboards
before executing.
"""

import asyncio
import logging
import uuid
from enum import Enum
from typing import Any, Callable, Dict, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    AUTO = "AUTO"          # Safe — execute immediately
    CONFIRM = "CONFIRM"    # Needs user approval, 5 min timeout
    CRITICAL = "CRITICAL"  # Needs explicit approval, 30 min timeout


# Tool name → risk level mapping
TOOL_RISK_MAP: Dict[str, RiskLevel] = {
    # AUTO — safe, execute immediately
    "arxiv_search": RiskLevel.AUTO,
    "get_schedule": RiskLevel.AUTO,
    "list_physics_jobs": RiskLevel.AUTO,
    "phd_handle": RiskLevel.AUTO,
    # CONFIRM — needs user approval (5 min timeout)
    "download_pdf": RiskLevel.CONFIRM,
    "analyze_paper": RiskLevel.CONFIRM,
    "check_physics_job": RiskLevel.CONFIRM,
    "analyze_emails": RiskLevel.CONFIRM,
    # CRITICAL — needs explicit approval (30 min timeout)
    "submit_physics_job": RiskLevel.CRITICAL,
    "send_email_reply": RiskLevel.CRITICAL,
}

# Timeout in seconds per risk level
_TIMEOUTS: Dict[RiskLevel, int] = {
    RiskLevel.CONFIRM: 300,    # 5 minutes
    RiskLevel.CRITICAL: 1800,  # 30 minutes
}


class ApprovalGate:
    """Gate that checks risk level and optionally asks the user before executing a tool."""

    def __init__(self):
        # callback_id → asyncio.Future mapping for pending approvals
        self._pending: Dict[str, asyncio.Future] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def execute_with_approval(
        self,
        tool_name: str,
        tool_args: dict,
        execute_fn: Callable,
        bot=None,
        chat_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Run *execute_fn* after obtaining the appropriate level of approval.

        Returns:
            {"approved": bool, "result": <tool result or None>, "approval_level": str}
        """
        risk = TOOL_RISK_MAP.get(tool_name, RiskLevel.CONFIRM)

        # AUTO — just run it
        if risk == RiskLevel.AUTO:
            result = await self._call(execute_fn, tool_args)
            return {"approved": True, "result": result, "approval_level": risk.value}

        # CONFIRM / CRITICAL — ask user via Telegram
        if bot is None or chat_id is None:
            logger.warning(
                "Approval required for %s but no bot/chat_id provided; denying.",
                tool_name,
            )
            return {"approved": False, "result": None, "approval_level": risk.value}

        approved = await self._request_approval(
            bot, chat_id, tool_name, tool_args, risk
        )

        if not approved:
            return {"approved": False, "result": None, "approval_level": risk.value}

        result = await self._call(execute_fn, tool_args)
        return {"approved": True, "result": result, "approval_level": risk.value}

    async def handle_callback(self, callback_query) -> None:
        """Process an incoming Telegram CallbackQuery for an approval button.

        Expected callback_data format: ``approve:<callback_id>`` or ``deny:<callback_id>``
        """
        data = callback_query.data or ""
        if ":" not in data:
            return

        action, callback_id = data.split(":", 1)

        future = self._pending.pop(callback_id, None)
        if future is None or future.done():
            await callback_query.answer("This request has expired.")
            return

        if action == "approve":
            future.set_result(True)
            await callback_query.answer("Approved")
            await callback_query.edit_message_text(
                callback_query.message.text + "\n\n-- Approved --"
            )
        else:
            future.set_result(False)
            await callback_query.answer("Denied")
            await callback_query.edit_message_text(
                callback_query.message.text + "\n\n-- Denied --"
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _request_approval(
        self,
        bot,
        chat_id: int,
        tool_name: str,
        tool_args: dict,
        risk: RiskLevel,
    ) -> bool:
        """Send an inline-keyboard message and wait for the user's response."""
        callback_id = uuid.uuid4().hex[:12]
        timeout = _TIMEOUTS[risk]

        # Build message text
        if risk == RiskLevel.CRITICAL:
            text = (
                f"[CRITICAL] Tool: {tool_name}\n"
                f"Args: {_format_args(tool_args)}\n\n"
                f"This action is classified as CRITICAL.\n"
                f"Please confirm within {timeout // 60} minutes."
            )
        else:
            text = (
                f"[CONFIRM] Tool: {tool_name}\n"
                f"Args: {_format_args(tool_args)}\n\n"
                f"Approve execution? (timeout: {timeout // 60} min)"
            )

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Yes", callback_data=f"approve:{callback_id}"),
                    InlineKeyboardButton("No", callback_data=f"deny:{callback_id}"),
                ]
            ]
        )

        await bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard)

        # Create a future and wait with timeout
        loop = asyncio.get_running_loop()
        future: asyncio.Future[bool] = loop.create_future()
        self._pending[callback_id] = future

        try:
            approved = await asyncio.wait_for(future, timeout=timeout)
            return approved
        except asyncio.TimeoutError:
            self._pending.pop(callback_id, None)
            await bot.send_message(
                chat_id=chat_id,
                text=f"Approval request for '{tool_name}' timed out. Action denied.",
            )
            return False

    @staticmethod
    async def _call(execute_fn: Callable, tool_args: dict) -> Any:
        """Invoke *execute_fn*. Supports both sync and async callables."""
        result = execute_fn(**tool_args)
        if asyncio.iscoroutine(result):
            result = await result
        return result


def _format_args(args: dict, max_len: int = 200) -> str:
    """Pretty-print tool args, truncating if too long."""
    text = ", ".join(f"{k}={v!r}" for k, v in args.items())
    if len(text) > max_len:
        text = text[:max_len] + "..."
    return text
