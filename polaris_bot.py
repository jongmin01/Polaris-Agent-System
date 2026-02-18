#!/usr/bin/env python3
"""
Polaris Bot - Telegram Interface

당신의 연구를 안내하는 북극성
"""

# =============================================================================
# DEPRECATED - Scheduled for removal: 2026-04-15
# Use: python -m polaris.bot_v2  (bot_v2.py via PolarisRouter)
# This file: legacy keyword-based orchestrator, no longer maintained.
# =============================================================================

import os
import logging
import asyncio
from typing import Dict, List
from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)
from dotenv import load_dotenv
import time  # Phase 1.1: For race condition guards
import json  # Phase 1.1: For corrections.jsonl
import re  # Phase 1.1: For YAML parsing
from pathlib import Path  # Phase 1.1: For file operations

from orchestrator import PolarisOrchestrator, AgentType
from phd_agent import PhDAgent
from mail_reader import MailReader
from email_analyzer import EmailAnalyzer
from hpc_monitor import PhysicsMonitor, JobStatus  # Phase 1.2: Physics-Agent
from schedule_agent import ScheduleAgent  # Phase 1.5: Schedule-Agent

import warnings
warnings.warn(
    "polaris_bot.py is deprecated and will be removed on 2026-04-15. "
    "Use: python -m polaris.bot_v2",
    DeprecationWarning,
    stacklevel=1,
)

import datetime as _dt
_DELETION_DATE = _dt.date(2026, 4, 15)
if _dt.date.today() >= _DELETION_DATE and os.environ.get("POLARIS_ALLOW_LEGACY") != "1":
    raise RuntimeError(
        f"polaris_bot.py was scheduled for deletion on {_DELETION_DATE} and is no longer supported.\n"
        "Use: python -m polaris.bot_v2\n"
        "Emergency bypass: POLARIS_ALLOW_LEGACY=1 python polaris_bot.py"
    )

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
SEARCH_RESULTS, DOWNLOAD_CONFIRM, LLM_SELECT = range(3)


class PolarisBot:
    """Polaris Telegram Bot"""

    def __init__(self):
        self.orchestrator = PolarisOrchestrator()
        self.obsidian_path = os.getenv('OBSIDIAN_PATH', os.path.expanduser('~/Documents'))
        self.phd_agent = PhDAgent(self.obsidian_path)

        # Mail Reader 초기화 (UIC 계정)
        self.mail_reader = MailReader(account_keyword="UIC")

        # Email Analyzer 초기화 (Gemini)
        self.email_analyzer = EmailAnalyzer()

        # Phase 1.2: Physics Monitor 초기화
        self.physics_monitor = PhysicsMonitor()
        self.physics_jobs_file = Path(__file__).parent / "data" / "physics" / "active_jobs.json"

        # Phase 1.5: Schedule Agent 초기화
        self.schedule_agent = ScheduleAgent()

        # 검색 결과 임시 저장
        self.current_search_results = {}

        logger.info(f"🌟 Polaris Bot initialized")
        logger.info(f"📁 Obsidian path: {self.obsidian_path}")
        logger.info(f"🔬 Physics Monitor active")
        logger.info(f"📅 Schedule Agent active")

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """시작 명령"""
        welcome_msg = """🌟 **Polaris에 오신 것을 환영합니다!**

당신의 연구를 안내하는 북극성 ⭐

**가능한 작업:**
📚 논문 검색/분석 (PhD-Agent)
📧 TA 메일 지능형 분류 (Email-Agent Phase 1.1)
🔬 VASP 작업 모니터링 (Physics-Agent Phase 1.2)
📅 일정 확인 (Schedule-Agent Phase 1.5)

**사용법:**
그냥 자연스럽게 말하세요!
예: "MoS2 논문 검색해줘", "내일 일정 알려줘"

명령어를 보려면 /help 를 입력하세요.
"""
        await update.message.reply_text(welcome_msg, parse_mode='Markdown')

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """도움말"""
        help_msg = """📖 **Polaris 명령어**

**기본 명령어:**
/start - 시작
/help - 도움말
/status - 시스템 상태

**PhD-Agent (논문):**
/search <검색어> - 논문 검색
/download <번호> - 논문 다운로드
/analyze - 논문 분석

**Email-Agent (메일):**
/mail - UIC 메일 확인 (Phase 0-1.3)
  → Gemini가 자동으로 분류: ACTION (조치 필요) / FYI (참고용)
  → Phase 1.3: RLM 앙상블 투표[VER-0.5.1-NEW] (신뢰도 낮으면 UNCERTAIN)
  → ACTION 메일은 답장 초안도 생성
  → 로컬 폴더에 자동 저장 (data/emails/)
/wrong <hash> [ACTION|FYI] - 이메일 분류 수정 (Phase 1.1 Feedback Loop)
  → 예: /wrong a3f2 ACTION
  → 카테고리 생략 시 자동 반전 (FYI ↔ ACTION)

**Physics-Agent (VASP):**
/physics <job\_id> <path> - VASP 작업 등록 (Phase 1.2)
  → 예: /physics 12345 /lus/eagle/projects/run001
  → 1시간마다 자동 상태 확인
/physics\_check <job\_id> - 수동 상태 확인
/physics\_list - 등록된 작업 목록

**Schedule-Agent (일정):**
/schedule - 오늘/내일 일정 확인 (Phase 1.5)
  → iCloud Calendar와 동기화
  → 모든 텍스트는 언더바 이스케이프 적용

**자연어 사용:**
"MoS2 논문 검색해줘" (논문 검색)
"내일 일정 알려줘" (일정 확인)

**메일 확인 (명령어만 지원):**
/mail

**팁:**
- Polaris가 자동으로 적절한 Agent를 선택합니다
- 비용이 드는 작업은 승인을 요청합니다
"""
        await update.message.reply_text(help_msg, parse_mode='Markdown')

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """시스템 상태"""
        status_msg = f"""⚙️ **Polaris 시스템 상태**

**버전:** {self.orchestrator.version}
**Obsidian:** {self.obsidian_path}

**Agent 상태:**
✅ PhD-Agent (Paper)
✅ Email-Agent (Phase 1.3: RLM 앙상블 투표)
✅ Physics-Agent (Phase 1.2: VASP Monitoring)
✅ Schedule-Agent (Phase 1.5: iCloud Calendar)
⏸️ Life-Agent - 계획중
⏸️ Personal-Agent - 계획중

**API:**
✅ Gemini 2.5 Flash (무료)
⚪ Claude Sonnet 4.5 (선택적)

모든 시스템 정상 작동중입니다! 🌟
"""
        await update.message.reply_text(status_msg, parse_mode='Markdown')

    async def _process_mail_background(self, chat_id: int):
        """
        Background task for email processing (non-blocking)

        Args:
            chat_id: Telegram chat ID to send results to
        """
        try:
            logger.info("DEBUG: Background mail processing started")

            # Step 1: Mail.app에서 읽지 않은 메일 가져오기
            logger.info("DEBUG: Fetching mails from Mail.app...")
            mails = self.mail_reader.get_unread_mails(limit=5)
            logger.info(f"DEBUG: Fetched {len(mails) if mails else 0} mails")

            if not mails:
                logger.info("DEBUG: No mails found, sending empty message")
                await self.application.bot.send_message(
                    chat_id=chat_id,
                    text="📭 읽지 않은 메일이 없습니다."
                )
                return

            # Step 2: Gemini 배치 분류 (단일 API 호출로 모든 메일 처리)
            # CRITICAL: Run in thread pool to avoid blocking async event loop
            logger.info("DEBUG: Starting Gemini batch analysis...")
            analyzed_mails = await asyncio.to_thread(
                self.email_analyzer.analyze_batch, mails
            )
            logger.info(f"DEBUG: Gemini batch analysis done. Results: {len(analyzed_mails) if analyzed_mails else 0} emails")

            # PATCH 2: Check for Gemini consecutive failures
            if self.email_analyzer.should_alert_gemini_failure():
                logger.warning(f"DEBUG: Gemini fail count reached {self.email_analyzer.gemini_fail_count}")
                await self.application.bot.send_message(
                    chat_id=chat_id,
                    text="⚠️ Gemini 불안정: 3회 연속 실패 감지"
                )

            # Guard: Handle None or empty results
            if not analyzed_mails:
                logger.warning("DEBUG: analyzed_mails is None or empty!")
                await self.application.bot.send_message(
                    chat_id=chat_id,
                    text="⚠️ 메일 분석 결과가 없습니다. 다시 시도해주세요."
                )
                return

            # Step 3: ACTION/FYI 요약 메시지 생성
            logger.info("DEBUG: Formatting summary message...")
            message = self.email_analyzer.format_categorized_summary(analyzed_mails)
            logger.info(f"DEBUG: Summary message formatted (length: {len(message)} chars)")

            # Step 4: Telegram에 전송
            logger.info("DEBUG: Sending summary to Telegram...")
            await self.application.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode='Markdown'
            )
            logger.info("DEBUG: Summary sent successfully")

            # Step 5: 로컬 저장 알림
            saved_count = sum(1 for item in analyzed_mails if item and item.get('analysis', {}).get('should_save', False))
            logger.info(f"DEBUG: Saved count: {saved_count}")
            if saved_count > 0:
                await self.application.bot.send_message(
                    chat_id=chat_id,
                    text=f"💾 {saved_count}개 메일을 로컬에 저장했습니다! (data/emails/)"
                )
                logger.info("DEBUG: Save notification sent")

            logger.info("DEBUG: Background mail processing completed successfully")

        except FileNotFoundError as e:
            logger.error(f"DEBUG: FileNotFoundError in background task: {e}")
            await self.application.bot.send_message(
                chat_id=chat_id,
                text=f"❌ AppleScript 파일을 찾을 수 없습니다.\n\n{str(e)}"
            )
        except Exception as e:
            error_str = str(e)
            logger.error(f"DEBUG: Exception in background task: {type(e).__name__} - {e}")
            logger.error(f"메일 확인 중 오류: {e}")

            # PATCH 3: Detailed error message based on error type
            # AppleScript/Mail.app failures trigger Telegram alert
            if "MAIL_APP_PERMISSION" in error_str:
                error_detail = "❌ Mail.app 접근 불가 또는 AppleScript 실패"
                solution = (
                    "**해결 방법:**\n"
                    "1. System Preferences → Security & Privacy → Automation\n"
                    "2. Python 또는 Terminal에 Mail.app 접근 권한 부여\n"
                    "3. Mail.app 재시작"
                )
            elif "MAIL_FETCH_FAILED" in error_str:
                error_detail = f"❌ Mail.app 접근 불가 또는 AppleScript 실패\n상세: {error_str[:100]}"
                solution = (
                    "**해결 방법:**\n"
                    "1. Mail.app이 정상 작동하는지 확인\n"
                    "2. UIC 계정이 Mail.app에 추가되어 있는지 확인\n"
                    "3. pm2 logs polaris-bot 로그 확인"
                )
            elif "MAIL_FETCH_TIMEOUT" in error_str:
                error_detail = "❌ Mail.app 응답 시간 초과"
                solution = (
                    "**해결 방법:**\n"
                    "1. Mail.app을 재시작해주세요\n"
                    "2. 메일 동기화 완료 후 다시 시도"
                )
            else:
                error_detail = error_str
                solution = (
                    "**해결 방법:**\n"
                    "1. Mail.app이 실행 중인지 확인\n"
                    "2. GEMINI_API_KEY가 .env에 설정되어 있는지 확인"
                )

            await self.application.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"❌ 메일 확인 중 오류가 발생했습니다.\n\n"
                    f"**오류:** {error_detail}\n\n"
                    f"{solution}"
                )
            )

    async def mail_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /mail 명령어 (Phase 0 Reflex System) - NON-BLOCKING

        즉시 응답하고, 백그라운드에서 메일 처리 후 결과 전송
        """
        # Immediate response - Telegram handler returns immediately
        await update.message.reply_text("📧 메일 처리를 시작합니다...\n⏱️ 10-20초 내에 결과를 보내드립니다.")

        # Spawn background task (non-blocking)
        chat_id = update.effective_chat.id
        asyncio.create_task(self._process_mail_background(chat_id))

    async def wrong_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Phase 1.1: /wrong command - Feedback loop for misclassifications

        Usage:
            /wrong <hash> [ACTION|FYI]

        If category is omitted, flips the current label (FYI ↔ ACTION)
        """
        if not context.args:
            await update.message.reply_text(
                "사용법: `/wrong <hash> [ACTION|FYI]`\n\n"
                "예시:\n"
                "  `/wrong a3f2 ACTION` - 해시 a3f2 이메일을 ACTION으로 수정\n"
                "  `/wrong a3f2` - 해시 a3f2 이메일의 분류를 반대로 변경 (FYI ↔ ACTION)",
                parse_mode='Markdown'
            )
            return

        # Parse arguments
        hash_id = context.args[0].lower()
        new_category = context.args[1].upper() if len(context.args) > 1 else None

        # Validate new_category if provided
        if new_category and new_category not in ['ACTION', 'FYI']:
            await update.message.reply_text(
                f"❌ 잘못된 카테고리: `{new_category}`\n"
                "유효한 카테고리: ACTION, FYI",
                parse_mode='Markdown'
            )
            return

        logger.info(f"DEBUG: /wrong command - hash: {hash_id}, new_category: {new_category}")

        # Find email file with this hash
        emails_dir = Path(__file__).parent / "data" / "emails"
        matching_file = None

        try:
            for email_file in emails_dir.glob("*.md"):
                # Read YAML frontmatter to find hash
                with open(email_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Extract hash from frontmatter using regex
                hash_match = re.search(r'^hash:\s*(\w+)', content, re.MULTILINE)
                if hash_match and hash_match.group(1) == hash_id:
                    matching_file = email_file
                    break

            if not matching_file:
                await update.message.reply_text(
                    f"❌ 해시 `{hash_id}`를 찾을 수 없습니다.\n"
                    "이메일 목록에서 [#xxxx] 해시를 확인하세요.",
                    parse_mode='Markdown'
                )
                return

            logger.info(f"DEBUG: Found matching file: {matching_file}")

            # Safety Gate 3: Reject if file modified within last 5 seconds
            file_mtime = matching_file.stat().st_mtime
            time_since_modification = time.time() - file_mtime
            if time_since_modification < 5:
                await update.message.reply_text(
                    f"⏸️ 파일이 최근에 수정되었습니다 ({time_since_modification:.1f}초 전).\n"
                    "5초 후에 다시 시도하세요. (Race condition guard)"
                )
                return

            # Read current content
            with open(matching_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Extract current category and user_corrected
            category_match = re.search(r'^category:\s*(\w+)', content, re.MULTILINE)
            user_corrected_match = re.search(r'^user_corrected:\s*(\w+)', content, re.MULTILINE)

            if not category_match:
                await update.message.reply_text("❌ 파일에서 category를 찾을 수 없습니다.")
                return

            current_category = category_match.group(1)
            user_corrected_value = user_corrected_match.group(1) if user_corrected_match else 'false'

            logger.info(f"DEBUG: Current category: {current_category}, user_corrected: {user_corrected_value}")

            # Safety Gate 4: Reject if user_corrected was set within last 30 seconds
            if user_corrected_value.lower() == 'true':
                # Check if file was modified within last 30 seconds (approximate)
                if time_since_modification < 30:
                    await update.message.reply_text(
                        f"⏸️ 이 이메일은 이미 수정되었습니다 ({time_since_modification:.1f}초 전).\n"
                        "30초 후에 다시 시도하세요. (Double-logging guard)"
                    )
                    return

            # Determine final category
            if new_category is None:
                # Safety Gate 2: Flip current label
                final_category = 'FYI' if current_category == 'ACTION' else 'ACTION'
            else:
                final_category = new_category

            logger.info(f"DEBUG: Final category: {final_category}")

            # Extract subject for logging
            subject_match = re.search(r'^# (.+)$', content, re.MULTILINE)
            subject = subject_match.group(1) if subject_match else "Unknown"

            # Atomic Write Order - Step 1: Update .md file frontmatter FIRST
            updated_content = re.sub(
                r'^category:\s*\w+',
                f'category: {final_category}',
                content,
                count=1,
                flags=re.MULTILINE
            )
            updated_content = re.sub(
                r'^user_corrected:\s*\w+',
                'user_corrected: true',
                updated_content,
                count=1,
                flags=re.MULTILINE
            )

            # Write updated content
            with open(matching_file, 'w', encoding='utf-8') as f:
                f.write(updated_content)

            logger.info(f"DEBUG: Updated .md file: {matching_file}")

            # Atomic Write Order - Step 2: Append to corrections.jsonl (only if Step 1 succeeds)
            feedback_dir = Path(__file__).parent / "data" / "feedback"
            feedback_file = feedback_dir / "corrections.jsonl"

            correction_entry = {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "hash": hash_id,
                "file_path": str(matching_file.name),
                "original_label": current_category,
                "corrected_label": final_category,
                "subject": subject
            }

            with open(feedback_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(correction_entry, ensure_ascii=False) + '\n')
                # Atomic Write Order - Step 3: Flush buffer immediately
                f.flush()

            logger.info(f"DEBUG: Appended to corrections.jsonl: {correction_entry}")

            # User Response
            await update.message.reply_text(
                f"✅ [#{hash_id}] 분류가 **{final_category}**로 수정되었습니다.",
                parse_mode='Markdown'
            )

        except Exception as e:
            logger.error(f"DEBUG: Error in /wrong command: {type(e).__name__} - {e}")
            await update.message.reply_text(
                f"❌ 오류가 발생했습니다: {str(e)}\n\n"
                "pm2 logs polaris-bot을 확인하세요."
            )

    def _load_physics_jobs(self) -> List[Dict]:
        """Load active physics jobs from JSON"""
        try:
            with open(self.physics_jobs_file, 'r') as f:
                data = json.load(f)
                return data.get('jobs', [])
        except Exception as e:
            logger.error(f"Failed to load physics jobs: {e}")
            return []

    def _save_physics_jobs(self, jobs: List[Dict]):
        """Save active physics jobs to JSON"""
        try:
            data = {
                'jobs': jobs,
                'last_updated': time.strftime("%Y-%m-%d %H:%M:%S"),
                'schema_version': '1.0'
            }
            with open(self.physics_jobs_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save physics jobs: {e}")

    async def physics_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Phase 1.2: /physics command - Register VASP job for monitoring

        Usage:
            /physics <job_id> <path>

        Example:
            /physics 12345 /lus/eagle/projects/MyProject/run001
        """
        if len(context.args) < 2:
            await update.message.reply_text(
                "사용법: `/physics <job_id> <path>`\n\n"
                "예시:\n"
                "  `/physics 12345 /lus/eagle/projects/MyProject/run001`\n\n"
                "VASP 작업을 등록하면 1시간마다 자동으로 상태를 확인합니다.",
                parse_mode='Markdown'
            )
            return

        job_id = context.args[0]
        path = context.args[1]

        logger.info(f"DEBUG: /physics command - job_id: {job_id}, path: {path}")

        # Validate job_id (numeric)
        if not job_id.isdigit():
            await update.message.reply_text(
                f"❌ 잘못된 job_id: `{job_id}`\n"
                "job_id는 숫자여야 합니다.",
                parse_mode='Markdown'
            )
            return

        # Validate path (absolute path)
        if not path.startswith('/'):
            await update.message.reply_text(
                f"❌ 잘못된 경로: `{path}`\n"
                "절대 경로를 사용하세요 (예: /lus/eagle/...)",
                parse_mode='Markdown'
            )
            return

        # Load existing jobs
        jobs = self._load_physics_jobs()

        # Check if job already registered
        for job in jobs:
            if job['job_id'] == job_id:
                await update.message.reply_text(
                    f"⚠️ Job `{job_id}`는 이미 등록되어 있습니다.\n"
                    f"경로: `{job['path']}`",
                    parse_mode='Markdown'
                )
                return

        # Register new job
        new_job = {
            'job_id': job_id,
            'path': path,
            'registered_at': time.strftime("%Y-%m-%d %H:%M:%S"),
            'chat_id': update.effective_chat.id,
            'last_check': None,
            'last_status': None
        }

        jobs.append(new_job)
        self._save_physics_jobs(jobs)

        logger.info(f"Registered physics job: {job_id} at {path}")

        await update.message.reply_text(
            f"✅ VASP 작업 등록 완료!\n\n"
            f"**Job ID**: `{job_id}`\n"
            f"**경로**: `{path}`\n\n"
            f"1시간마다 자동으로 상태를 확인합니다.\n"
            f"수동 확인: `/physics_check {job_id}`",
            parse_mode='Markdown'
        )

    async def physics_check_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Phase 1.2: /physics_check command - Manual job status check

        Usage:
            /physics_check <job_id>
        """
        if not context.args:
            await update.message.reply_text(
                "사용법: `/physics_check <job_id>`\n\n"
                "예시: `/physics_check 12345`",
                parse_mode='Markdown'
            )
            return

        job_id = context.args[0]

        # Find job in registered jobs
        jobs = self._load_physics_jobs()
        target_job = None
        for job in jobs:
            if job['job_id'] == job_id:
                target_job = job
                break

        if not target_job:
            await update.message.reply_text(
                f"❌ Job `{job_id}`를 찾을 수 없습니다.\n"
                "등록된 작업 목록: `/physics_list`",
                parse_mode='Markdown'
            )
            return

        await update.message.reply_text("🔬 VASP 작업 상태 확인 중...")

        # Run monitoring in background to avoid blocking
        asyncio.create_task(
            self._check_physics_job_background(
                job_id,
                target_job['path'],
                update.effective_chat.id
            )
        )

    async def _check_physics_job_background(self, job_id: str, path: str, chat_id: int):
        """Background task to check physics job status"""
        try:
            # Run monitor in thread pool (blocking SSH calls)
            result = await asyncio.to_thread(
                self.physics_monitor.monitor_job,
                job_id,
                path
            )

            # Format result message
            status = result['status']
            message = result['message']

            if status == JobStatus.CONVERGED.value:
                emoji = "✅"
                alert_msg = f"{emoji} **작업 완료!**\n\n"
            elif status == JobStatus.RUNNING.value:
                emoji = "🔄"
                alert_msg = f"{emoji} **작업 진행 중**\n\n"
            elif status == JobStatus.MFA_EXPIRED.value:
                emoji = "🔐"
                alert_msg = f"{emoji} **MFA 세션 만료**\n\n"
            elif status == JobStatus.ZOMBIE.value:
                emoji = "💀"
                alert_msg = f"{emoji} **SSH 연결 실패**\n\n"
            else:
                emoji = "❌"
                alert_msg = f"{emoji} **오류**\n\n"

            alert_msg += f"**Job ID**: `{job_id}`\n"
            alert_msg += f"**상태**: {status}\n"
            alert_msg += f"**메시지**: {message}\n\n"

            # Add progress details if available
            if 'oszicar' in result['details']:
                oszicar = result['details']['oszicar']
                if oszicar.get('progress'):
                    prog = oszicar['progress']
                    alert_msg += f"**진행**: Step {prog['step']}, E={prog['energy']:.6f} eV\n\n"

            alert_msg += f"**시각**: {result['timestamp']}"

            await self.application.bot.send_message(
                chat_id=chat_id,
                text=alert_msg,
                parse_mode='Markdown'
            )

            # Update job status in JSON
            jobs = self._load_physics_jobs()
            for job in jobs:
                if job['job_id'] == job_id:
                    job['last_check'] = result['timestamp']
                    job['last_status'] = status
                    break
            self._save_physics_jobs(jobs)

        except Exception as e:
            logger.error(f"Physics job check error: {e}")
            await self.application.bot.send_message(
                chat_id=chat_id,
                text=f"❌ 작업 확인 중 오류 발생:\n{str(e)}"
            )

    async def physics_list_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Phase 1.2: /physics_list command - List all registered jobs
        """
        jobs = self._load_physics_jobs()

        if not jobs:
            await update.message.reply_text(
                "📭 등록된 VASP 작업이 없습니다.\n\n"
                "작업 등록: `/physics <job_id> <path>`",
                parse_mode='Markdown'
            )
            return

        msg = f"🔬 **등록된 VASP 작업 ({len(jobs)}개)**\n\n"

        for idx, job in enumerate(jobs, 1):
            msg += f"**{idx}. Job {job['job_id']}**\n"
            msg += f"경로: `{job['path']}`\n"
            msg += f"등록: {job['registered_at']}\n"

            if job.get('last_status'):
                msg += f"상태: {job['last_status']}\n"

            if job.get('last_check'):
                msg += f"마지막 확인: {job['last_check']}\n"

            msg += "\n"

        await update.message.reply_text(msg, parse_mode='Markdown')

    async def schedule_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Phase 1.5: /schedule command - Get daily briefing (today + tomorrow)

        Usage:
            /schedule
        """
        await update.message.reply_text("📅 일정을 확인하는 중...")

        # Run in background to avoid blocking
        chat_id = update.effective_chat.id
        asyncio.create_task(self._get_schedule_background(chat_id))

    async def _get_schedule_background(self, chat_id: int):
        """Background task for schedule retrieval"""
        try:
            # Run in thread pool (blocking iCloud CalDAV calls)
            briefing = await asyncio.to_thread(
                self.schedule_agent.get_daily_briefing
            )

            if briefing['status'] == 'error':
                await self.application.bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ 일정 확인 중 오류가 발생했습니다:\n{briefing.get('message', '알 수 없는 오류')}"
                )
                return

            # Format and send briefing
            message = self.schedule_agent.format_daily_briefing(briefing)

            await self.application.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode='Markdown'
            )

        except Exception as e:
            logger.error(f"Schedule retrieval error: {e}")
            await self.application.bot.send_message(
                chat_id=chat_id,
                text=f"❌ 일정 확인 중 오류 발생:\n{str(e)}"
            )

    async def _physics_monitoring_loop(self):
        """
        Phase 1.2: Background monitoring loop (every 1 hour)

        Checks all registered physics jobs periodically
        """
        logger.info("Physics monitoring loop started")

        while True:
            try:
                # Wait 1 hour
                await asyncio.sleep(3600)

                logger.info("Running physics monitoring cycle...")

                jobs = self._load_physics_jobs()

                if not jobs:
                    logger.debug("No physics jobs registered")
                    continue

                for job in jobs:
                    job_id = job['job_id']
                    path = job['path']
                    chat_id = job['chat_id']

                    logger.info(f"Checking job {job_id} at {path}")

                    # Check job status in background
                    asyncio.create_task(
                        self._check_physics_job_background(job_id, path, chat_id)
                    )

                    # Small delay between jobs to avoid overload
                    await asyncio.sleep(5)

            except Exception as e:
                logger.error(f"Physics monitoring loop error: {e}")
                # Continue loop even on error
                await asyncio.sleep(60)

    async def search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """논문 검색 명령"""
        if not context.args:
            await update.message.reply_text(
                "검색어를 입력하세요.\n예: /search MoS2"
            )
            return

        query = " ".join(context.args)
        await update.message.reply_text(f"🔍 '{query}' 검색 중...")

        # PhD-Agent로 검색
        result = self.phd_agent._handle_paper_search(f"search {query}")

        if result['status'] == 'success':
            # 검색 결과 저장
            user_id = update.effective_user.id
            self.current_search_results[user_id] = result['results']

            await update.message.reply_text(
                result['formatted_message'],
                parse_mode='Markdown'
            )
            return SEARCH_RESULTS
        else:
            await update.message.reply_text(result['message'])
            return ConversationHandler.END

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """자연어 메시지 처리"""
        user_message = update.message.text
        user_id = update.effective_user.id

        logger.info(f"User {user_id}: {user_message}")

        # Orchestrator로 Intent 분류
        intent = self.orchestrator.classify_intent(user_message)
        routing_result = self.orchestrator.route_to_agent(intent)

        logger.info(f"Intent: {intent.agent.value} (confidence: {intent.confidence:.2f})")

        # 명확하지 않은 경우
        if routing_result['status'] == 'clarification_needed':
            await update.message.reply_text(routing_result['message'])
            return

        # PhD-Agent 라우팅
        if intent.agent == AgentType.PHD and routing_result['status'] == 'routed':
            result = self.phd_agent.handle(user_message)

            if result['status'] == 'success':
                # 검색 결과인 경우
                if 'results' in result:
                    self.current_search_results[user_id] = result['results']
                    await update.message.reply_text(
                        result['formatted_message'],
                        parse_mode='Markdown'
                    )
                else:
                    await update.message.reply_text(result['message'])
            else:
                await update.message.reply_text(result['message'])

        # Schedule-Agent (Phase 1.5)
        elif intent.agent == AgentType.SCHEDULE and routing_result['status'] == 'routed':
            await update.message.reply_text("📅 일정을 확인하는 중...")
            # Run in background
            chat_id = update.effective_chat.id
            asyncio.create_task(self._get_schedule_background(chat_id))

        # Life-Agent (미구현)
        elif intent.agent == AgentType.LIFE:
            await update.message.reply_text(routing_result['message'])

        # Personal-Agent (미구현)
        elif intent.agent == AgentType.PERSONAL:
            await update.message.reply_text(routing_result['message'])

        # Unknown
        else:
            await update.message.reply_text(routing_result['message'])

    async def download_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """논문 다운로드 명령"""
        user_id = update.effective_user.id

        # 검색 결과 확인
        if user_id not in self.current_search_results:
            await update.message.reply_text(
                "먼저 /search 로 논문을 검색하세요."
            )
            return

        # 번호 확인
        if not context.args:
            await update.message.reply_text(
                "다운로드할 논문 번호를 입력하세요.\n예: /download 1"
            )
            return

        try:
            paper_idx = int(context.args[0]) - 1
            results = self.current_search_results[user_id]

            if paper_idx < 0 or paper_idx >= len(results):
                await update.message.reply_text(
                    f"유효하지 않은 번호입니다. (1-{len(results)})"
                )
                return

            selected_paper = results[paper_idx]

            # LLM 선택 요청
            await update.message.reply_text(
                f"📄 선택: {selected_paper['title']}\n\n분석에 사용할 LLM을 선택하세요:\n\n1️⃣ Gemini (무료, 빠름)\n2️⃣ Claude (유료, 정확)\n\n답장: 1 또는 2"
            )

            # 컨텍스트에 논문 저장
            context.user_data['selected_paper'] = selected_paper

            return LLM_SELECT

        except (ValueError, IndexError):
            await update.message.reply_text(
                "올바른 번호를 입력하세요.\n예: /download 1"
            )
            return

    async def llm_select(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """LLM 선택 처리"""
        choice = update.message.text.strip()
        selected_paper = context.user_data.get('selected_paper')

        if not selected_paper:
            await update.message.reply_text("세션이 만료되었습니다. 다시 검색해주세요.")
            return ConversationHandler.END

        if choice == "1":
            llm_choice = "gemini"
            await update.message.reply_text("🤖 Gemini로 분석합니다...")
        elif choice == "2":
            llm_choice = "claude"
            await update.message.reply_text("🤖 Claude로 분석합니다... (비용: ~$0.25)")
        else:
            await update.message.reply_text(
                "1 또는 2를 선택하세요.\n1️⃣ Gemini\n2️⃣ Claude"
            )
            return LLM_SELECT

        # 다운로드 및 분석
        result = self.phd_agent.download_and_save(selected_paper, llm_choice)

        if result['status'] == 'success':
            await update.message.reply_text(result['message'])
        else:
            await update.message.reply_text(f"❌ {result['message']}")

        return ConversationHandler.END

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """대화 취소"""
        await update.message.reply_text("작업을 취소했습니다.")
        return ConversationHandler.END

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """전역 에러 핸들러"""
        logger.error(f"Update {update} caused error {context.error}")
        if update and update.message:
            await update.message.reply_text(
                "❌ 오류가 발생했습니다. 다시 시도해주세요."
            )


def main():
    """봇 실행"""
    # Telegram 토큰 확인
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not found in .env")

    # Application 생성 (먼저 생성)
    app = Application.builder().token(token).build()

    # Bot 인스턴스 생성
    bot = PolarisBot()

    # Bot에 Application 연결
    bot.application = app

    # 명령어 핸들러
    app.add_handler(CommandHandler("start", bot.start))
    app.add_handler(CommandHandler("help", bot.help_command))
    app.add_handler(CommandHandler("status", bot.status_command))
    # Phase 0: Explicit /mail command only (no natural language routing)
    app.add_handler(CommandHandler("mail", bot.mail_command))
    # Phase 1.1: Feedback loop
    app.add_handler(CommandHandler("wrong", bot.wrong_command))
    # Phase 1.2: Physics-Agent
    app.add_handler(CommandHandler("physics", bot.physics_command))
    app.add_handler(CommandHandler("physics_check", bot.physics_check_command))
    app.add_handler(CommandHandler("physics_list", bot.physics_list_command))
    # Phase 1.5: Schedule-Agent
    app.add_handler(CommandHandler("schedule", bot.schedule_command))

    # Conversation Handler (논문 검색 → 다운로드 → LLM 선택)
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("search", bot.search_command),
            CommandHandler("download", bot.download_command)
        ],
        states={
            SEARCH_RESULTS: [
                CommandHandler("download", bot.download_command)
            ],
            LLM_SELECT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, bot.llm_select)
            ]
        },
        fallbacks=[CommandHandler("cancel", bot.cancel)]
    )
    app.add_handler(conv_handler)

    # 자연어 메시지 핸들러
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        bot.handle_message
    ))

    # 에러 핸들러
    app.add_error_handler(bot.error_handler)

    # Phase 1.2: Start physics monitoring loop after app initialization
    async def post_init(application):
        """Start background tasks after app initialization"""
        logger.info("🔬 Starting physics monitoring loop...")
        asyncio.create_task(bot._physics_monitoring_loop())

        # Set command list in Telegram's UI (autocomplete menu)
        commands = [
            BotCommand("start", "시작"),
            BotCommand("help", "도움말"),
            BotCommand("status", "시스템 상태"),
            BotCommand("mail", "메일 확인"),
            BotCommand("wrong", "메일 분류 수정 (예: /wrong a3f2 ACTION)"),
            BotCommand("search", "논문 검색"),
            BotCommand("download", "논문 다운로드"),
            BotCommand("analyze", "논문 분석"),
            BotCommand("physics", "VASP 작업 등록 (예: /physics 12345 /path)"),
            BotCommand("physics_check", "VASP 작업 상태 확인"),
            BotCommand("physics_list", "등록된 VASP 작업 목록"),
            BotCommand("schedule", "오늘/내일 일정 확인"),
        ]
        await application.bot.set_my_commands(commands)
        logger.info("✅ Telegram command list updated")

    app.post_init = post_init

    # 봇 시작
    logger.info("🌟 Polaris Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
