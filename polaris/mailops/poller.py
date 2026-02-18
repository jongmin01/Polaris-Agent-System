"""Periodic urgent mail polling and Telegram push alert management."""

import asyncio
import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .service import MailOpsService

logger = logging.getLogger(__name__)


class MailOpsPoller:
    """Manages periodic urgent mail polling and Telegram push alerts."""

    def __init__(self, mailops: "MailOpsService", poll_interval: int = 300):
        self.mailops = mailops
        self.poll_interval = poll_interval
        self._last_poll = 0.0

    def maybe_trigger(self, chat_id: int, bot_app) -> bool:
        """Check interval; if due, create background polling task. Returns True if triggered."""
        now = time.time()
        if now - self._last_poll >= self.poll_interval:
            self._last_poll = now
            asyncio.create_task(self.poll_and_alert(chat_id, bot_app))
            return True
        return False

    async def poll_and_alert(self, chat_id: int, bot_app):
        """Sync unread, find unalerted urgent mails, send Telegram alerts."""
        try:
            await asyncio.to_thread(self.mailops.sync_unread, 20)
            urgent = await asyncio.to_thread(self.mailops.list_unalerted_urgent, 5)
            if not urgent:
                return

            lines = ["**Urgent Mail Alert**", ""]
            for row in urgent:
                lines.append(f"- {row.get('subject', '')} / {row.get('sender', '')}")
                await asyncio.to_thread(self.mailops.mark_urgent_alerted, row["ext_id"])

            try:
                await bot_app.bot.send_message(
                    chat_id=chat_id,
                    text="\n".join(lines),
                    parse_mode="Markdown",
                )
            except Exception:
                await bot_app.bot.send_message(chat_id=chat_id, text="\n".join(lines))
        except Exception as e:
            logger.warning("MailOps poll failed: %s", e)
