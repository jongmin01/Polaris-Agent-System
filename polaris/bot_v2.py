#!/usr/bin/env python3
"""
Polaris Bot v2 - Telegram Interface with LLM-powered Router

Uses PolarisRouter (ReAct loop) instead of keyword-based PolarisOrchestrator.
Integrates ApprovalGate for tool execution control and TraceLogger for audit trail.
"""

import os
import logging
import asyncio
from typing import Dict, List
from pathlib import Path

from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from dotenv import load_dotenv

from polaris.router import PolarisRouter
from polaris.approval_gate import ApprovalGate
from polaris.trace_logger import TraceLogger
from polaris.tools import get_all_tools
from polaris.mailops import MailOpsService, MailOpsPoller
from polaris.services import HotReloader

# Legacy agent imports for explicit command handlers
from mail_reader import MailReader
from email_analyzer import EmailAnalyzer
from phd_agent import PhDAgent
from hpc_monitor import HPCMonitor, JobStatus
from schedule_agent import ScheduleAgent

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


class PolarisBotV2:
    """Polaris Telegram Bot v2 with LLM-powered routing."""

    def __init__(self):
        self.router = PolarisRouter()
        self.approval_gate = ApprovalGate()
        self.trace_logger = TraceLogger()

        self.obsidian_path = os.getenv("OBSIDIAN_PATH", os.path.expanduser("~/Documents"))
        self.phd_agent = PhDAgent(self.obsidian_path)
        self.mail_reader = MailReader()
        self.email_analyzer = EmailAnalyzer()
        self.hpc_monitor = HPCMonitor()
        self.schedule_agent = ScheduleAgent()
        self.mailops = None
        self.mailops_poll_interval = int(os.getenv("POLARIS_MAILOPS_POLL_INTERVAL", "300"))
        try:
            self.mailops = MailOpsService()
        except Exception as e:
            logger.warning("MailOps unavailable: %s", e)
            self.mailops = None

        self._mailops_poller = (
            MailOpsPoller(self.mailops, self.mailops_poll_interval) if self.mailops else None
        )

        # Per-user conversation history
        self.conversations: Dict[int, List[dict]] = {}

        # Hot-reload settings
        self.auto_reload = os.getenv("POLARIS_AUTO_RELOAD", "true").lower() == "true"
        self.auto_restart_on_code_change = os.getenv(
            "POLARIS_AUTO_RESTART_ON_CODE_CHANGE",
            "false",
        ).lower() == "true"
        self.reload_check_interval = float(os.getenv("POLARIS_RELOAD_CHECK_INTERVAL", "2.0"))
        self._hot_reloader = HotReloader(
            watch_root=Path(__file__).resolve().parent.parent,
            on_runtime_reload=self.router._init_skills,
            auto_reload=self.auto_reload,
            auto_restart_on_code_change=self.auto_restart_on_code_change,
            check_interval=self.reload_check_interval,
        )

        logger.info("Polaris Bot v2 initialized")

    # ------------------------------------------------------------------
    # Basic commands
    # ------------------------------------------------------------------

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        welcome = (
            "**Polaris v2**\n\n"
            "Your research north star.\n\n"
            "**Features:**\n"
            "- Paper search/analysis (arXiv, Semantic Scholar)\n"
            "- TA email classification\n"
            "- HPC job monitoring\n"
            "- iCloud Calendar\n"
            "- LLM-powered natural language routing\n\n"
            "Type /help for commands, or just ask me anything."
        )
        await update.message.reply_text(welcome, parse_mode="Markdown")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = (
            "**Polaris v2 Commands**\n\n"
            "/start - Welcome\n"
            "/help - This message\n"
            "/status - System status\n"
            "/mail - Check primary mail account\n"
            "/search <query> - Search papers\n"
            "/schedule - Today/tomorrow calendar\n"
            "/hpc [status|jobs] [cluster] - HPC status and queue\n"
            "/trace - Show recent action traces\n"
            "/tools - List registered tools\n"
            "/skills - List registered skills\n"
            "/wrong - Mark last response as wrong\n"
            "/feedback - Show recent feedback\n"
            "/index - Index Obsidian vault\n"
            "/vault - Vault status / search\n"
            "/mail\\_digest - Unified mail digest\n"
            "/mail\\_accounts - Apple Mail account names\n"
            "/mail\\_urgent - Urgent mails only\n"
            "/mail\\_promo - Promotion/deal mails\n"
            "/mail\\_actions - Propose safe mail actions\n"
            "/reload - Reload runtime components\n\n"
            "Or just type naturally and Polaris will route your request."
        )
        await update.message.reply_text(help_text, parse_mode="Markdown")

    async def mail_accounts_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List Apple Mail account names to validate account keyword config."""
        try:
            reader = MailReader(account_keyword="*")
            accounts = await asyncio.to_thread(reader.list_accounts)
            if not accounts:
                await update.message.reply_text("Apple Mail 계정을 찾지 못했어.")
                return
            lines = ["**Apple Mail Accounts**", ""] + [f"- {name}" for name in accounts]
            await update.message.reply_text("\n".join(lines))
        except Exception as e:
            await update.message.reply_text(f"계정 조회 실패: {e}")

    async def mail_digest_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Sync and show unified mail digest."""
        if not self.mailops:
            await update.message.reply_text("MailOps가 초기화되지 않았어.")
            return

        await update.message.reply_text("메일 동기화 및 요약 중...")
        data = await asyncio.to_thread(self.mailops.sync_unread, 20)
        rows = await asyncio.to_thread(self.mailops.get_digest, 20)
        if not rows:
            await update.message.reply_text("새로 분류된 메일이 없어.")
            return

        lines = [
            "**Mail Digest**",
            f"sync: fetched={data['fetched']}, new={data['inserted']}, urgent_new={data['urgent_new']}",
            "",
        ]
        for row in rows[:10]:
            cat = row.get("category", "info")
            lines.append(f"- [{cat}] {row.get('subject', '')} ({row.get('account_id', 'unknown')})")
        await update.message.reply_text("\n".join(lines))

    async def mail_urgent_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show urgent mails."""
        if not self.mailops:
            await update.message.reply_text("MailOps가 초기화되지 않았어.")
            return

        await asyncio.to_thread(self.mailops.sync_unread, 20)
        rows = await asyncio.to_thread(self.mailops.get_urgent, 20)
        if not rows:
            await update.message.reply_text("긴급 메일이 없어.")
            return
        lines = ["**Urgent Mails**", ""]
        for row in rows[:10]:
            lines.append(f"- {row.get('subject', '')} / {row.get('sender', '')}")
        await update.message.reply_text("\n".join(lines))

    async def mail_promo_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show promo/deal mails."""
        if not self.mailops:
            await update.message.reply_text("MailOps가 초기화되지 않았어.")
            return

        await asyncio.to_thread(self.mailops.sync_unread, 20)
        rows = await asyncio.to_thread(self.mailops.get_promo, 20)
        if not rows:
            await update.message.reply_text("프로모션 메일이 없어.")
            return
        lines = ["**Promo/Deal Mails**", ""]
        for row in rows[:15]:
            lines.append(f"- {row.get('subject', '')} / {row.get('sender', '')}")
        await update.message.reply_text("\n".join(lines))

    async def mail_actions_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Propose safe action queue for promo mails."""
        if not self.mailops:
            await update.message.reply_text("MailOps가 초기화되지 않았어.")
            return

        target = context.args[0] if context.args else "promo"
        proposals = await asyncio.to_thread(self.mailops.propose_actions, target, 20)
        if not proposals:
            await update.message.reply_text("제안할 액션이 없어.")
            return
        lines = [f"**Mail Actions Proposal ({target})**", ""]
        for item in proposals[:10]:
            lines.append(
                f"- {item['proposed_action']} | {item.get('subject', '')} | {item.get('category', '')}"
            )
        lines.append("")
        lines.append("R1 정책: archive/label/mark_read만 지원, delete는 미지원.")
        await update.message.reply_text("\n".join(lines))

    async def reload_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manual runtime reload command."""
        try:
            self._hot_reloader.reload_runtime()
            self._hot_reloader.refresh_snapshot()
            await update.message.reply_text("런타임 리로드 완료: skills/외부 스킬을 다시 불러왔어.")
        except Exception as e:
            await update.message.reply_text(f"리로드 실패: {e}")

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        tools = get_all_tools()
        status = (
            "**Polaris v2 Status**\n\n"
            f"**Router:** PolarisRouter (ReAct loop)\n"
            f"**Model:** {self.router.model}\n"
            f"**Tools:** {len(tools)} registered\n"
            f"**Approval Gate:** Active\n"
            f"**Trace Logger:** Active\n"
        )
        await update.message.reply_text(status, parse_mode="Markdown")

    # ------------------------------------------------------------------
    # New v2 commands
    # ------------------------------------------------------------------

    async def trace_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show recent action traces."""
        recent = self.trace_logger.get_recent(limit=10)
        if not recent:
            await update.message.reply_text("No traces recorded yet.")
            return

        lines = ["**Recent Traces (last 10)**\n"]
        for entry in recent:
            ts = entry.get("timestamp", "?")[:19]
            tool = entry.get("tool", "?")
            level = entry.get("approval_level", "?")
            lines.append(f"`{ts}` | {tool} | {level}")

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def tools_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List all registered tools."""
        tools = get_all_tools()
        if not tools:
            await update.message.reply_text("No tools registered.")
            return

        lines = [f"**Registered Tools ({len(tools)})**\n"]
        for t in tools:
            name = t["name"]
            desc = t["description"][:80]
            lines.append(f"- `{name}`: {desc}")

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def skills_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List all registered skills."""
        try:
            from polaris.skills import SkillRegistry
            registry = SkillRegistry()
            skills = registry.list_all()
            if not skills:
                await update.message.reply_text("등록된 스킬이 없어.")
                return

            lines = [f"**등록된 스킬 ({len(skills)}개)**\n"]
            for s in skills:
                triggers = ", ".join(s.get("triggers", []))
                tags = []
                if s.get("source") == "external":
                    tags.append("외부")
                if s.get("requires_tool"):
                    tags.append("강제도구")
                chain = s.get("tool_chain", [])
                if chain:
                    tags.append(f"체인:{len(chain)}")
                tag_text = f" [{' | '.join(tags)}]" if tags else ""
                lines.append(f"- `{s['name']}`{tag_text}: {s.get('description', '')} [{triggers}]")

            try:
                await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
            except Exception:
                await update.message.reply_text("\n".join(lines))
        except Exception as e:
            await update.message.reply_text(f"스킬 시스템 에러: {e}")

    # ------------------------------------------------------------------
    # Legacy explicit commands (kept for backward compatibility)
    # ------------------------------------------------------------------

    async def mail_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Processing emails...\nResults will arrive in 10-20 seconds.")
        chat_id = update.effective_chat.id
        asyncio.create_task(self._process_mail_background(chat_id))

    async def _process_mail_background(self, chat_id: int):
        try:
            mails = self.mail_reader.get_unread_mails(limit=5)
            if not mails:
                await self.application.bot.send_message(chat_id=chat_id, text="No unread emails.")
                return

            analyzed = await asyncio.to_thread(self.email_analyzer.analyze_batch, mails)
            if not analyzed:
                await self.application.bot.send_message(chat_id=chat_id, text="Email analysis returned no results.")
                return

            message = self.email_analyzer.format_categorized_summary(analyzed)
            await self.application.bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")
        except Exception as e:
            logger.error("Mail processing error: %s", e)
            await self.application.bot.send_message(chat_id=chat_id, text=f"Email error: {e}")

    async def search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.args:
            await update.message.reply_text("Usage: /search <query>")
            return
        query = " ".join(context.args)
        await update.message.reply_text(f"Searching '{query}'...")
        result = self.phd_agent._handle_paper_search(f"search {query}")
        if result["status"] == "success":
            await update.message.reply_text(result["formatted_message"], parse_mode="Markdown")
        else:
            await update.message.reply_text(result["message"])

    async def schedule_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Checking schedule...")
        chat_id = update.effective_chat.id
        asyncio.create_task(self._get_schedule_background(chat_id))

    async def _get_schedule_background(self, chat_id: int):
        try:
            briefing = await asyncio.to_thread(self.schedule_agent.get_daily_briefing)
            if briefing.get("status") == "error":
                await self.application.bot.send_message(chat_id=chat_id, text=f"Schedule error: {briefing.get('message')}")
                return
            message = self.schedule_agent.format_daily_briefing(briefing)
            await self.application.bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")
        except Exception as e:
            logger.error("Schedule error: %s", e)
            await self.application.bot.send_message(chat_id=chat_id, text=f"Schedule error: {e}")

    # ------------------------------------------------------------------
    # HPC commands
    # ------------------------------------------------------------------

    async def hpc_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        def _target_label(profile: str, host: str) -> str:
            return profile if profile == host else f"{profile} ({host})"

        args = context.args or []
        actions = {"status", "jobs"}
        action = "status"
        cluster = None

        if len(args) == 1:
            if args[0].lower() in actions:
                action = args[0].lower()
            else:
                cluster = args[0]
        elif len(args) >= 2:
            if args[0].lower() in actions:
                action = args[0].lower()
                cluster = args[1]
            elif args[1].lower() in actions:
                cluster = args[0]
                action = args[1].lower()
            else:
                await update.message.reply_text("Usage: /hpc [status|jobs] [cluster]")
                return

        try:
            if action == "jobs":
                result = await asyncio.to_thread(self.hpc_monitor.list_jobs, cluster, 30)
                target = _target_label(result.get("cluster", "default"), result.get("host", "unknown"))
                if not result.get("ok"):
                    await update.message.reply_text(
                        f"HPC queue check failed ({target}): "
                        f"{result.get('error', 'unknown error')}"
                    )
                    return

                jobs = result.get("jobs", [])
                if not jobs:
                    await update.message.reply_text(
                        f"{target}: 현재 큐에 잡이 없어."
                    )
                    return

                compact = " ".join([f"{j['job_id']}-{j['state']}" for j in jobs[:10]])
                await update.message.reply_text(
                    f"{target} 현재 작업:\n{compact}"
                )
                return

            if cluster:
                self.hpc_monitor.set_profile(cluster)
            alive = await asyncio.to_thread(self.hpc_monitor.zombie_guard)
            target = _target_label(self.hpc_monitor.profile_name, self.hpc_monitor.hpc_host)
            if alive:
                await update.message.reply_text(
                    f"{target} 연결됨.\n"
                    "현재 진행중인 job 상태를 확인해드릴까요?\n"
                    "`/hpc jobs`",
                    parse_mode="Markdown",
                )
            else:
                await update.message.reply_text(
                    f"{target} 연결 실패.\n"
                    "SSH 인증 세션 또는 네트워크 상태를 확인해줘."
                )
        except ValueError as e:
            await update.message.reply_text(str(e))
        except Exception as e:
            await update.message.reply_text(f"HPC check error: {e}")

    # ------------------------------------------------------------------
    # Vault commands (/index, /vault)
    # ------------------------------------------------------------------

    async def index_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start vault indexing."""
        if not self.router.vault_reader:
            await update.message.reply_text("Vault reader가 초기화되지 않았어.")
            return

        chat_id = update.effective_chat.id
        await update.message.reply_text("Vault 인덱싱 시작...")
        asyncio.create_task(self._index_vault_background(chat_id))

    async def _index_vault_background(self, chat_id: int):
        """Run vault indexing in background and report completion."""
        try:
            # Step 2: Run indexing (no progress callback)
            stats = await asyncio.to_thread(
                self.router.vault_reader.index_vault,
                vault_name="My Second Brain",
                force=False,
            )

            # Step 3: Send completion message
            msg = (
                f"**Vault 인덱싱 완료!**\n\n"
                f"총 노트: {stats['total']}개\n"
                f"신규: {stats['new']}개\n"
                f"업데이트: {stats['updated']}개\n"
                f"스킵: {stats['skipped']}개\n"
                f"에러: {stats['errors']}개"
            )
            try:
                await self.application.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")
            except Exception:
                await self.application.bot.send_message(chat_id=chat_id, text=msg)
        except Exception as e:
            logger.error("Vault indexing error: %s", e)
            await self.application.bot.send_message(chat_id=chat_id, text=f"인덱싱 에러: {e}")

    async def vault_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show vault indexing status or search vault knowledge."""
        if not self.router.vault_reader:
            await update.message.reply_text("Vault reader가 초기화되지 않았어.")
            return

        # /vault search <query>
        if context.args and context.args[0] == "search" and len(context.args) > 1:
            query = " ".join(context.args[1:])
            results = self.router.vault_reader.search_vault_knowledge(query, top_k=5)
            if not results:
                await update.message.reply_text(f"'{query}'에 대한 vault 검색 결과가 없어.")
                return

            lines = [f"**Vault 검색: '{query}'**\n"]
            for r in results:
                score = f"{r.get('score', 0):.3f}" if r.get("score") else "-"
                lines.append(f"- `{r['title']}` ({r['category']}) [score: {score}]")
                lines.append(f"  {r['content'][:100]}...")

            text = "\n".join(lines)
            try:
                await update.message.reply_text(text, parse_mode="Markdown")
            except Exception:
                await update.message.reply_text(text)
            return

        # /vault (status)
        stats = self.router.vault_reader.get_index_stats()
        msg = (
            f"**Vault 인덱싱 상태**\n\n"
            f"인덱싱된 노트: {stats['indexed_notes']}개\n"
            f"마지막 인덱싱: {stats['last_indexed'] or '없음'}"
        )
        try:
            await update.message.reply_text(msg, parse_mode="Markdown")
        except Exception:
            await update.message.reply_text(msg)

    # ------------------------------------------------------------------
    # Feedback commands (/wrong, /feedback)
    # ------------------------------------------------------------------

    async def wrong_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Mark the last response as wrong. User provides correction in next message."""
        user_id = update.effective_user.id
        history = self.conversations.get(user_id, [])

        # Find last assistant response
        last_response = ""
        for msg in reversed(history):
            if msg.get("role") == "assistant":
                last_response = msg.get("content", "")
                break

        if not last_response:
            await update.message.reply_text("교정할 이전 응답이 없어.")
            return

        # Store state for next message
        context.user_data["awaiting_correction"] = True
        context.user_data["wrong_original"] = last_response

        await update.message.reply_text(
            "어떻게 고쳐야 하는지 알려줘. (다음 메시지에 교정 내용을 적어줘)"
        )

    async def feedback_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show recent feedback entries."""
        if not self.router.feedback_manager:
            await update.message.reply_text("피드백 시스템이 초기화되지 않았어.")
            return

        feedbacks = self.router.feedback_manager.get_recent_feedback(limit=10)
        if not feedbacks:
            await update.message.reply_text("저장된 피드백이 없어.")
            return

        lines = [f"**최근 피드백 ({len(feedbacks)}개)**\n"]
        for fb in feedbacks:
            ts = fb.get("timestamp", "?")[:10]
            correction = fb.get("correction", "")[:60]
            cat = fb.get("category", "") or ""
            cat_label = f" [{cat}]" if cat else ""
            lines.append(f"- `{ts}`{cat_label} {correction}")

        text = "\n".join(lines)
        try:
            await update.message.reply_text(text, parse_mode="Markdown")
        except Exception:
            await update.message.reply_text(text)

    # ------------------------------------------------------------------
    # Natural language handler (LLM router)
    # ------------------------------------------------------------------

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self._hot_reloader.check_and_apply()
        user_message = update.message.text
        user_id = update.effective_user.id

        # Trigger periodic background urgent-mail polling.
        if self._mailops_poller:
            self._mailops_poller.maybe_trigger(update.effective_chat.id, self.application)

        # Defensive: skip /commands that slip past filters.COMMAND
        if user_message and user_message.startswith("/"):
            logger.warning("Command leaked to handle_message: %s", user_message)
            await update.message.reply_text(
                f"알 수 없는 명령어야: {user_message.split()[0]}\n/help 로 사용 가능한 명령어를 확인해봐."
            )
            return

        logger.info("User %d: %s", user_id, user_message)

        # Handle /wrong follow-up (awaiting correction)
        if context.user_data.get("awaiting_correction"):
            context.user_data["awaiting_correction"] = False
            original = context.user_data.pop("wrong_original", "")

            if self.router.feedback_manager:
                self.router.feedback_manager.save_correction(
                    session_id=str(user_id),
                    original_response=original,
                    user_correction=user_message,
                    category="manual",
                )
                await update.message.reply_text("교정 내용을 저장했어! 다음부터 반영할게.")
            else:
                await update.message.reply_text("피드백 시스템이 초기화되지 않았어.")
            return

        # Get or create conversation history
        history = self.conversations.get(user_id, [])

        # Route through LLM (session_id enables memory persistence)
        result = await asyncio.to_thread(
            self.router.route, user_message, history, session_id=str(user_id)
        )

        response_text = result["response"]
        tools_used = result["tools_used"]

        # Log tool usage to trace
        for tool_name in tools_used:
            self.trace_logger.log(
                thought="LLM routed request",
                tool=tool_name,
                args={"user_message": user_message},
                result=response_text[:200],
                approval_level="AUTO",
                session_id=str(user_id),
            )

        # Update conversation history (keep last 20 messages)
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": response_text})
        self.conversations[user_id] = history[-20:]

        # Send response (try Markdown, fallback to plain text)
        if response_text:
            try:
                await update.message.reply_text(response_text, parse_mode="Markdown")
            except Exception:
                # LLM response may contain broken markdown — send as plain text
                await update.message.reply_text(response_text)
        else:
            await update.message.reply_text("I could not generate a response. Please try again.")

    # ------------------------------------------------------------------
    # Callback handler for approval gate
    # ------------------------------------------------------------------

    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.approval_gate.handle_callback(update.callback_query)

    # ------------------------------------------------------------------
    # Error handler
    # ------------------------------------------------------------------

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.error("Update %s caused error %s", update, context.error)
        if update and update.message:
            await update.message.reply_text("An error occurred. Please try again.")


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not found in .env")

    app = Application.builder().token(token).build()
    bot = PolarisBotV2()
    bot.application = app

    # Command handlers
    app.add_handler(CommandHandler("start", bot.start))
    app.add_handler(CommandHandler("help", bot.help_command))
    app.add_handler(CommandHandler("status", bot.status_command))
    app.add_handler(CommandHandler("mail", bot.mail_command))
    app.add_handler(CommandHandler("search", bot.search_command))
    app.add_handler(CommandHandler("schedule", bot.schedule_command))
    app.add_handler(CommandHandler("hpc", bot.hpc_command))
    app.add_handler(CommandHandler("trace", bot.trace_command))
    app.add_handler(CommandHandler("tools", bot.tools_command))
    app.add_handler(CommandHandler("skills", bot.skills_command))
    app.add_handler(CommandHandler("wrong", bot.wrong_command))
    app.add_handler(CommandHandler("feedback", bot.feedback_command))
    app.add_handler(CommandHandler("index", bot.index_command))
    app.add_handler(CommandHandler("vault", bot.vault_command))
    app.add_handler(CommandHandler("mail_digest", bot.mail_digest_command))
    app.add_handler(CommandHandler("mail_accounts", bot.mail_accounts_command))
    app.add_handler(CommandHandler("mail_urgent", bot.mail_urgent_command))
    app.add_handler(CommandHandler("mail_promo", bot.mail_promo_command))
    app.add_handler(CommandHandler("mail_actions", bot.mail_actions_command))
    app.add_handler(CommandHandler("reload", bot.reload_command))

    # Callback query handler for approval gate
    app.add_handler(CallbackQueryHandler(bot.handle_callback_query))

    # Natural language handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))

    # Error handler
    app.add_error_handler(bot.error_handler)

    # Post-init: set command list
    async def post_init(application):
        commands = [
            BotCommand("start", "Welcome"),
            BotCommand("help", "Help"),
            BotCommand("status", "System status"),
            BotCommand("mail", "Check emails"),
            BotCommand("search", "Search papers"),
            BotCommand("schedule", "Calendar briefing"),
            BotCommand("hpc", "HPC status and jobs"),
            BotCommand("trace", "Show recent traces"),
            BotCommand("tools", "List registered tools"),
            BotCommand("skills", "List skills"),
            BotCommand("wrong", "Mark last response wrong"),
            BotCommand("feedback", "Show feedback history"),
            BotCommand("index", "Index Obsidian vault"),
            BotCommand("vault", "Vault status/search"),
            BotCommand("mail_digest", "Unified mail digest"),
            BotCommand("mail_accounts", "Apple Mail account names"),
            BotCommand("mail_urgent", "Urgent mail list"),
            BotCommand("mail_promo", "Promotion/deal mails"),
            BotCommand("mail_actions", "Propose mail actions"),
            BotCommand("reload", "Reload runtime components"),
        ]
        await application.bot.set_my_commands(commands)
        logger.info("Polaris Bot v2 started")

    app.post_init = post_init

    logger.info("Polaris Bot v2 starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
