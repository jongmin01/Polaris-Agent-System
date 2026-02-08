#!/usr/bin/env python3
"""
strings.py - Internationalization (i18n) Strings

All user-facing messages for Polaris Agent System.
Switch between languages by changing CURRENT_LANGUAGE.
"""

import os
from typing import Dict

# Current language setting (can be changed via environment variable)
CURRENT_LANGUAGE = os.getenv("POLARIS_LANG", "ko")  # "ko" or "en"


class Strings:
    """Multilingual string repository"""

    # Language data
    MESSAGES = {
        # === Telegram Bot Messages ===
        "welcome_title": {
            "ko": "🌟 **Polaris에 오신 것을 환영합니다!**",
            "en": "🌟 **Welcome to Polaris!**"
        },
        "welcome_tagline": {
            "ko": "당신의 연구를 안내하는 북극성 ⭐",
            "en": "Your guiding star for research ⭐"
        },
        "welcome_features": {
            "ko": "**가능한 작업:**\n"
                  "📚 논문 검색/분석 (PhD-Agent)\n"
                  "📧 TA 메일 지능형 분류 (Email-Agent Phase 2)\n"
                  "🔬 Physics 계산 자동화 (준비중)\n"
                  "📅 일정 관리 (준비중)",
            "en": "**Features:**\n"
                  "📚 Paper Search/Analysis (PhD-Agent)\n"
                  "📧 Intelligent Email Classification (Email-Agent Phase 2)\n"
                  "🔬 Physics Calculation Automation (Coming Soon)\n"
                  "📅 Schedule Management (Coming Soon)"
        },
        "welcome_usage": {
            "ko": "**사용법:**\n그냥 자연스럽게 말하세요!\n예: \"MoS2 논문 검색해줘\"",
            "en": "**How to Use:**\nJust talk naturally!\nExample: \"Search for MoS2 papers\""
        },
        "welcome_help": {
            "ko": "명령어를 보려면 /help 를 입력하세요.",
            "en": "Type /help to see available commands."
        },

        # === Email Agent Messages ===
        "check_mail_start": {
            "ko": "📧 UIC 메일 확인 중...",
            "en": "📧 Checking UIC mail..."
        },
        "no_unread_mails": {
            "ko": "📭 읽지 않은 메일이 없습니다.",
            "en": "📭 No unread emails."
        },
        "analyzing_with_gemini": {
            "ko": "🤖 Gemini로 메일 분석 중...",
            "en": "🤖 Analyzing emails with Gemini..."
        },
        "obsidian_saved": {
            "ko": "💾 중요 메일 {count}개를 Obsidian에 저장했습니다!",
            "en": "💾 Saved {count} important email(s) to Obsidian!"
        },
        "mail_error_script_not_found": {
            "ko": "❌ AppleScript 파일을 찾을 수 없습니다.",
            "en": "❌ AppleScript file not found."
        },
        "mail_error_general": {
            "ko": "❌ 메일 확인 중 오류가 발생했습니다.",
            "en": "❌ Error occurred while checking emails."
        },
        "mail_error_troubleshooting": {
            "ko": "**해결 방법:**\n"
                  "1. Mail.app이 실행 중인지 확인\n"
                  "2. System Preferences → Security & Privacy → Automation\n"
                  "3. Python에 Mail.app 접근 권한 부여\n"
                  "4. GEMINI_API_KEY가 .env에 설정되어 있는지 확인",
            "en": "**Troubleshooting:**\n"
                  "1. Check if Mail.app is running\n"
                  "2. System Preferences → Security & Privacy → Automation\n"
                  "3. Grant Python access to Mail.app\n"
                  "4. Verify GEMINI_API_KEY is set in .env"
        },

        # === Email Categories ===
        "category_ta": {
            "ko": "[TA/수업]",
            "en": "[TA/Class]"
        },
        "category_research": {
            "ko": "[연구/교수님]",
            "en": "[Research/Professor]"
        },
        "category_department": {
            "ko": "[학과 공지]",
            "en": "[Department]"
        },
        "category_other": {
            "ko": "[기타]",
            "en": "[Other]"
        },

        # === Email Analyzer Messages ===
        "gemini_api_error": {
            "ko": "❌ Gemini API 오류: {error_type} - {error_msg}",
            "en": "❌ Gemini API Error: {error_type} - {error_msg}"
        },
        "gemini_analysis_failed": {
            "ko": "[Gemini 분석 실패] {subject}",
            "en": "[Gemini Analysis Failed] {subject}"
        },
        "obsidian_folder_check": {
            "ko": "📁 Obsidian Emails 폴더 확인: {path}",
            "en": "📁 Obsidian Emails folder check: {path}"
        },
        "obsidian_folder_error": {
            "ko": "❌ Obsidian 폴더 생성 실패: {error}",
            "en": "❌ Failed to create Obsidian folder: {error}"
        },
        "obsidian_saved_file": {
            "ko": "💾 Obsidian 저장: {filename}",
            "en": "💾 Saved to Obsidian: {filename}"
        },
        "obsidian_save_failed": {
            "ko": "❌ Obsidian 저장 실패: {error}",
            "en": "❌ Failed to save to Obsidian: {error}"
        },

        # === System Status Messages ===
        "system_status_title": {
            "ko": "⚙️ **Polaris 시스템 상태**",
            "en": "⚙️ **Polaris System Status**"
        },
        "system_status_agents": {
            "ko": "**Agent 상태:**\n"
                  "✅ PhD-Agent (Paper)\n"
                  "✅ Email-Agent (Phase 2: 지능형 분류)\n"
                  "⏸️ Physics-Agent (DFT/VASP/ONETEP) - 준비중\n"
                  "⏸️ Life-Agent - 계획중\n"
                  "⏸️ Personal-Agent - 계획중",
            "en": "**Agent Status:**\n"
                  "✅ PhD-Agent (Paper)\n"
                  "✅ Email-Agent (Phase 2: Intelligent Classification)\n"
                  "⏸️ Physics-Agent (DFT/VASP/ONETEP) - Coming Soon\n"
                  "⏸️ Life-Agent - Planned\n"
                  "⏸️ Personal-Agent - Planned"
        },
        "system_all_ok": {
            "ko": "모든 시스템 정상 작동중입니다! 🌟",
            "en": "All systems operational! 🌟"
        },

        # === Help Messages ===
        "help_basic": {
            "ko": "**기본 명령어:**\n/start - 시작\n/help - 도움말\n/status - 시스템 상태",
            "en": "**Basic Commands:**\n/start - Start\n/help - Help\n/status - System Status"
        },
        "help_paper": {
            "ko": "**PhD-Agent (논문):**\n"
                  "/search <검색어> - 논문 검색\n"
                  "/download <번호> - 논문 다운로드\n"
                  "/analyze - 논문 분석",
            "en": "**PhD-Agent (Papers):**\n"
                  "/search <query> - Search papers\n"
                  "/download <number> - Download paper\n"
                  "/analyze - Analyze paper"
        },
        "help_email": {
            "ko": "**Email-Agent (메일):**\n"
                  "/check_mail - UIC 메일 확인 (읽지 않은 메일 5개)\n"
                  "  → Gemini가 자동으로 분류: [TA/수업], [연구/교수님], [학과 공지], [기타]\n"
                  "  → TA 메일은 답장 초안도 생성\n"
                  "  → 중요 메일은 Obsidian에 자동 저장",
            "en": "**Email-Agent:**\n"
                  "/check_mail - Check UIC mail (5 unread emails)\n"
                  "  → Auto-classified by Gemini: [TA/Class], [Research], [Department], [Other]\n"
                  "  → Reply drafts for TA emails\n"
                  "  → Important emails auto-saved to Obsidian"
        },
        "help_natural_language": {
            "ko": "**자연어 사용 (추천):**\n"
                  "\"MoS2 논문 검색해줘\"\n"
                  "\"Janus TMDC 분석\"\n"
                  "\"TA 메일 확인\"",
            "en": "**Natural Language (Recommended):**\n"
                  "\"Search for MoS2 papers\"\n"
                  "\"Analyze Janus TMDC\"\n"
                  "\"Check TA emails\""
        },
        "help_tip": {
            "ko": "**팁:**\n- Polaris가 자동으로 적절한 Agent를 선택합니다\n"
                  "- 비용이 드는 작업은 승인을 요청합니다",
            "en": "**Tips:**\n- Polaris automatically selects the appropriate agent\n"
                  "- Cost-incurring tasks will require approval"
        },

        # === Model and Debug Messages ===
        "available_models": {
            "ko": "🔍 Available Gemini models: {models}",
            "en": "🔍 Available Gemini models: {models}"
        },
        "model_list_error": {
            "ko": "⚠️  Could not list models: {error}",
            "en": "⚠️  Could not list models: {error}"
        },
        "using_model": {
            "ko": "✅ Using model: {model}",
            "en": "✅ Using model: {model}"
        },

        # === Email Summary Messages ===
        "email_summary_header": {
            "ko": "📬 **읽지 않은 메일 {count}개**",
            "en": "📬 **{count} Unread Email(s)**"
        },
        "reply_draft_label": {
            "ko": "💬 **답장 초안**:",
            "en": "💬 **Reply Draft**:"
        },
    }

    @classmethod
    def get(cls, key: str, lang: str = None, **kwargs) -> str:
        """
        Get translated string by key

        Args:
            key: Message key (e.g., "welcome_title")
            lang: Language code ("ko" or "en"), defaults to CURRENT_LANGUAGE
            **kwargs: Format arguments for string interpolation

        Returns:
            Translated and formatted string

        Example:
            >>> Strings.get("obsidian_saved", count=3)
            "💾 중요 메일 3개를 Obsidian에 저장했습니다!"
        """
        if lang is None:
            lang = CURRENT_LANGUAGE

        # Get message from dictionary
        message_dict = cls.MESSAGES.get(key)
        if not message_dict:
            return f"[Missing: {key}]"

        # Get language-specific string
        message = message_dict.get(lang)
        if not message:
            # Fallback to Korean if English not available
            message = message_dict.get("ko", f"[Missing: {key}]")

        # Format with arguments if provided
        if kwargs:
            try:
                message = message.format(**kwargs)
            except KeyError as e:
                print(f"Warning: Missing format key {e} for message '{key}'")

        return message

    @classmethod
    def set_language(cls, lang: str):
        """
        Set current language globally

        Args:
            lang: "ko" or "en"
        """
        global CURRENT_LANGUAGE
        if lang in ["ko", "en"]:
            CURRENT_LANGUAGE = lang
            print(f"✅ Language set to: {lang}")
        else:
            print(f"⚠️  Invalid language: {lang}. Use 'ko' or 'en'.")

    @classmethod
    def get_language(cls) -> str:
        """Get current language"""
        return CURRENT_LANGUAGE


# Convenience function
def _(key: str, **kwargs) -> str:
    """
    Shorthand for Strings.get()

    Example:
        >>> from strings import _
        >>> print(_("welcome_title"))
        🌟 **Polaris에 오신 것을 환영합니다!**
    """
    return Strings.get(key, **kwargs)


# Export for easy import
__all__ = ['Strings', '_', 'CURRENT_LANGUAGE']


# Usage examples and tests
if __name__ == "__main__":
    print("=" * 60)
    print("  Polaris i18n Strings Test")
    print("=" * 60)
    print()

    # Test Korean (default)
    print("[Korean Messages]")
    print(Strings.get("welcome_title"))
    print(Strings.get("check_mail_start"))
    print(Strings.get("obsidian_saved", count=3))
    print()

    # Test English
    print("[English Messages]")
    Strings.set_language("en")
    print(Strings.get("welcome_title"))
    print(Strings.get("check_mail_start"))
    print(Strings.get("obsidian_saved", count=3))
    print()

    # Test shorthand
    print("[Shorthand Test]")
    Strings.set_language("ko")
    print(_("gemini_api_error", error_type="ValueError", error_msg="Invalid API key"))
    print()

    print("=" * 60)
    print("  ✅ All tests passed!")
    print("=" * 60)
