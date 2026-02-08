#!/usr/bin/env python3
"""
email_analyzer.py - Email Intelligence with Gemini 2.5 Flash

Features:
- 4-category email classification
- TA reply draft generation (Korean/English)
- Importance scoring for Obsidian integration
"""

import os
from typing import Dict, List, Optional
from enum import Enum
from datetime import datetime
from pathlib import Path
import google.generativeai as genai
from dotenv import load_dotenv
import asyncio
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
import json
import uuid
import hashlib  # Phase 1.1: Hash ID generation
import logging  # Phase 1.3: RLM logging

# Load environment
load_dotenv()

# Phase 1.3: RLM (Optional)
RLM_ENABLED = os.getenv('RLM_ENABLED', 'false').lower() == 'true'
if RLM_ENABLED:
    try:
        from rlm_wrapper import create_rlm_wrapper
        print("🔬 RLM (Recursive Learning Monitor) enabled")
    except ImportError:
        print("⚠️ RLM module not found, falling back to standard classification")
        RLM_ENABLED = False

logger = logging.getLogger(__name__)


class EmailCategory(Enum):
    """Email categories for Phase 0 Reflex System (Phase 1.3: + UNCERTAIN)"""
    ACTION = "ACTION"  # Requires reply, has deadline, or TA/professor request
    FYI = "FYI"        # Everything else - informational only
    UNCERTAIN = "UNCERTAIN"  # Phase 1.3: Low confidence, requires manual review


class EmailAnalyzer:
    """
    Gemini-powered email analyzer

    Features:
    - Smart categorization (TA, Research, Department, Other)
    - TA reply draft generation
    - Importance detection for Obsidian saving
    """

    def __init__(self):
        """Initialize Gemini API"""
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in .env")

        genai.configure(api_key=api_key)

        # Debug: List available models
        try:
            available_models = [m.name for m in genai.list_models()]
            print(f"🔍 Available Gemini models: {available_models[:5]}")  # Show first 5
        except Exception as e:
            print(f"⚠️  Could not list models: {e}")

        # Use latest stable model: Gemini 2.5 Flash
        self.model = genai.GenerativeModel('gemini-2.5-flash')
        print(f"✅ Using model: gemini-2.5-flash")

        # Phase 0: Local storage (NOT Obsidian/iCloud)
        # Store emails in project directory first
        project_dir = Path(__file__).parent
        self.emails_folder = project_dir / "data" / "emails"

        # Create local emails folder if not exists
        self.emails_folder.mkdir(parents=True, exist_ok=True)
        print(f"📁 Local Emails 폴더: {self.emails_folder}")

        # PATCH 2: Gemini consecutive failure counter
        self.gemini_fail_count = 0

        # Phase 1.1: Load classification prompt from file
        self.prompt_template = self._load_classification_prompt()

        # Phase 1.3: RLM wrapper (optional)
        self.rlm_wrapper = None
        if RLM_ENABLED:
            try:
                self.rlm_wrapper = create_rlm_wrapper()
                print("✅ RLM wrapper initialized (ensemble voting active)")
            except Exception as e:
                print(f"⚠️ RLM initialization failed: {e}")
                self.rlm_wrapper = None

        # Obsidian path (DISABLED for Phase 0 - not critical path)
        # obsidian_base = os.getenv("OBSIDIAN_PATH", "")
        # self.obsidian_path = Path(obsidian_base) / "My Second Brain"
        # self.obsidian_backup_folder = self.obsidian_path / "00_Inbox" / "Emails"

    def _load_classification_prompt(self) -> str:
        """
        Phase 1.1: Load classification prompt from file

        Returns:
            Prompt template string with {subject}, {sender}, {content} placeholders
        """
        project_dir = Path(__file__).parent
        prompt_file = project_dir / "prompts" / "email_classify.txt"

        try:
            if prompt_file.exists():
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    template = f.read()
                    print(f"✅ Loaded classification prompt from: {prompt_file}")
                    return template
            else:
                print(f"⚠️ Prompt file not found: {prompt_file}, using fallback")
                return self._fallback_classification_prompt()
        except Exception as e:
            print(f"❌ Failed to load prompt file: {e}, using fallback")
            return self._fallback_classification_prompt()

    def _fallback_classification_prompt(self) -> str:
        """Fallback classification prompt (hardcoded)"""
        return """You are an email classifier for 종민 (Jongmin Baek), a Physics PhD student and TA at UIC.

**Phase 0 Reflex System: ACTION vs FYI**

Classify this email into EXACTLY ONE of these two categories:

**1. ACTION** - Requires immediate attention or response
   - Needs a reply (student questions, professor requests, collaborator queries)
   - Has a deadline (assignment due, meeting RSVP, registration deadline)
   - Explicit request from TA supervisor, professor, or advisor
   - Grade disputes, homework clarifications, office hour requests
   - Research task assignments, calculation requests
   - Examples:
     * "Can you help me with problem 2?"
     * "Please submit grades by Friday"
     * "Could you review this draft?"
     * "RSVP for colloquium this week"

**2. FYI** - Informational only, no immediate action required
   - General announcements (seminars you can optionally attend)
   - Newsletters, department updates
   - Automated notifications (Gradescope submissions, system messages)
   - Commercial advertisements, promotions
   - FYI-style updates from professors or department
   - Examples:
     * "Weekly physics colloquium schedule"
     * "Student submitted assignment on Gradescope"
     * "Department newsletter: recent publications"
     * "Physics lab equipment sale"

**Decision Logic:**
- If email asks a question → ACTION
- If email requires you to do something → ACTION
- If email has a deadline/RSVP → ACTION
- If email is purely informational with no ask → FYI
- When in doubt, prefer ACTION (better to over-triage than miss something)

**Email Details:**
Subject: {subject}
From: {sender}
Body: {content}

**Response Format (strictly follow):**
CATEGORY: ACTION or FYI
IMPORTANCE: [1-5, where 5=urgent/deadline, 1=low priority]
SUMMARY: [one sentence summary in Korean]

Respond in the exact format above."""

    def generate_email_hash(self, mail: Dict) -> str:
        """
        Phase 1.1: Generate 4-char hash ID for email

        Logic:
        1. Try MD5(message-id) if available
        2. Fallback to MD5(subject + date)

        Args:
            mail: Email dict with message_id, subject, date

        Returns:
            4-character hash string (e.g., 'a3f2')
        """
        message_id = mail.get('message_id', '')

        if message_id:
            # Use message-id if available
            hash_input = message_id
        else:
            # Fallback: subject + date
            subject = mail.get('subject', '')
            date = mail.get('date', '')
            hash_input = f"{subject}{date}"

        # Generate MD5 hash and take first 4 chars
        md5_hash = hashlib.md5(hash_input.encode('utf-8')).hexdigest()
        return md5_hash[:4]

    def _extract_gemini_text(self, response) -> Optional[str]:
        """
        Robust Gemini response text extraction with multiple fallback attempts

        Returns:
            Extracted text or None if all methods fail
        """
        # Method 1: Try structured access (most reliable)
        try:
            text = response.candidates[0].content.parts[0].text
            if text:
                return text
        except (AttributeError, IndexError, KeyError) as e:
            print(f"⚠️ Gemini extraction method 1 failed: {type(e).__name__}")

        # Method 2: Try direct .text property
        try:
            text = response.text
            if text:
                return text
        except (AttributeError, KeyError) as e:
            print(f"⚠️ Gemini extraction method 2 failed: {type(e).__name__}")

        # Both methods failed - log full response for debugging
        print("❌ All Gemini text extraction methods failed!")
        print(f"📊 Gemini raw response: {repr(response)}")
        return None

    def _call_gemini_with_timeout(self, prompt: str, timeout_seconds: int = 15) -> Optional[str]:
        """
        Call Gemini with timeout protection

        Args:
            prompt: Prompt to send
            timeout_seconds: Timeout in seconds (default 15s)

        Returns:
            Response text or None if timeout/error
        """
        def _generate():
            try:
                response = self.model.generate_content(prompt)
                return self._extract_gemini_text(response)
            except Exception as e:
                print(f"❌ Gemini API error: {type(e).__name__} - {str(e)}")
                return None

        # Run with timeout
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_generate)
            try:
                result = future.result(timeout=timeout_seconds)
                return result
            except FuturesTimeoutError:
                print(f"⏱️ Gemini timeout after {timeout_seconds}s")
                return None
            except Exception as e:
                print(f"❌ Unexpected error in Gemini call: {type(e).__name__} - {str(e)}")
                return None

    def _classify_single(self, mail: Dict) -> str:
        """
        Phase 1.3: Single classification inference (ACTION or FYI only).
        Used for RLM ensemble voting.

        Args:
            mail: Email dictionary

        Returns:
            "ACTION" or "FYI" string
        """
        subject = mail.get('subject', '')
        sender = mail.get('sender', '')
        content = mail.get('content', '')

        # Build prompt and call Gemini
        prompt = self._build_analysis_prompt(subject, sender, content)
        response_text = self._call_gemini_with_timeout(prompt, timeout_seconds=15)

        if not response_text:
            return "FYI"  # Fallback

        # Parse category only
        try:
            result = self._parse_gemini_response(response_text)
            return result['category'].value  # "ACTION" or "FYI"
        except Exception:
            return "FYI"  # Fallback

    def analyze_email(self, mail: Dict) -> Dict:
        """
        Analyze email with Gemini (Phase 1.3: with optional RLM ensemble voting)

        Args:
            mail: Dict with keys: subject, sender, content, date, account

        Returns:
            {
                'category': EmailCategory,
                'importance': int (1-5),
                'summary': str,
                'reply_draft': str (optional, for TA emails),
                'should_save': bool,
                'rlm_metadata': dict (optional, if RLM used)
            }
        """
        subject = mail.get('subject', '')
        sender = mail.get('sender', '')
        content = mail.get('content', '')

        # Phase 1.3: RLM ensemble voting (if enabled)
        voted_category = None
        rlm_metadata = None
        if self.rlm_wrapper:
            try:
                # Run ensemble voting asynchronously
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                voted_category_str, confidence, metadata = loop.run_until_complete(
                    self.rlm_wrapper.classify_with_ensemble(self._classify_single, mail)
                )
                loop.close()

                # Convert string to EmailCategory
                if voted_category_str == "ACTION":
                    voted_category = EmailCategory.ACTION
                elif voted_category_str == "FYI":
                    voted_category = EmailCategory.FYI
                elif voted_category_str == "UNCERTAIN":
                    voted_category = None  # Will trigger manual review path

                rlm_metadata = {
                    "confidence": confidence,
                    "votes": metadata.get("votes", []),
                    "ensemble_used": True
                }

                logger.info(f"✅ RLM vote: {voted_category_str} (conf={confidence:.2f})")

            except Exception as e:
                logger.error(f"⚠️ RLM voting failed, falling back to single inference: {e}")
                voted_category = None

        # Build prompt for Gemini (used for importance, summary if needed)
        prompt = self._build_analysis_prompt(subject, sender, content)

        # Call Gemini with timeout protection (for full analysis)
        response_text = self._call_gemini_with_timeout(prompt, timeout_seconds=15)

        if not response_text:
            # Timeout or extraction failed - return FYI fallback
            print(f"⚠️ Gemini analysis failed for: {subject[:50]}")
            return {
                'category': EmailCategory.FYI,
                'importance': 1,
                'summary': f"[Gemini 분석 실패] {subject[:50]}",
                'reply_draft': None,
                'should_save': True  # Save for manual review
            }

        # Parse Gemini response
        try:
            result = self._parse_gemini_response(response_text)
        except Exception as e:
            print(f"❌ Response parsing failed: {type(e).__name__} - {str(e)}")
            print(f"   Response text: {response_text[:200]}")
            return {
                'category': EmailCategory.FYI,
                'importance': 1,
                'summary': f"[파싱 실패] {subject[:50]}",
                'reply_draft': None,
                'should_save': True
            }

        # Phase 1.3: Override category with RLM vote if available
        if voted_category is not None:
            result['category'] = voted_category
            result['rlm_metadata'] = rlm_metadata
            logger.info(f"📊 Using RLM voted category: {voted_category.value}")
        elif voted_category is None and rlm_metadata:
            # UNCERTAIN case - mark for manual review
            result['category'] = EmailCategory.UNCERTAIN  # Phase 1.3: Use UNCERTAIN category
            result['summary'] = f"[⚠️ UNCERTAIN] {result.get('summary', subject[:50])}"
            result['rlm_metadata'] = rlm_metadata
            logger.warning(f"⚠️ RLM returned UNCERTAIN for: {subject}")

        # Phase 1.3: Add reply draft for ACTION emails only (skip UNCERTAIN)
        if result['category'] == EmailCategory.ACTION:
            reply_prompt = self._build_reply_prompt(subject, sender, content)
            reply_text = self._call_gemini_with_timeout(reply_prompt, timeout_seconds=10)
            result['reply_draft'] = reply_text.strip() if reply_text else "[Reply generation failed]"
        else:
            result['reply_draft'] = None

        return result

    def _build_analysis_prompt(self, subject: str, sender: str, content: str) -> str:
        """
        Build classification prompt for Gemini - Phase 0 Reflex System
        Phase 1.1: Uses prompt template loaded from file
        """
        # Truncate content to 500 chars for prompt
        content_preview = content[:500] if len(content) > 500 else content
        if len(content) > 500:
            content_preview += "..."

        # Use loaded template and format with email details
        return self.prompt_template.format(
            subject=subject,
            sender=sender,
            content=content_preview
        )

    def _build_reply_prompt(self, subject: str, sender: str, content: str) -> str:
        """Build TA reply draft prompt"""
        return f"""You are 종민 (Jongmin Baek), a friendly Physics PhD TA at UIC.

Write a **polite and helpful reply** to this student email.

Guidelines:
- Detect language: If student wrote in Korean, reply in Korean. If English, reply in English.
- Be warm and encouraging (e.g., "좋은 질문이에요!", "Great question!")
- Keep it concise but helpful
- If you don't have enough info, ask clarifying questions
- Include your name at the end: "종민" (Korean) or "Jongmin" (English)

**Student Email:**
Subject: {subject}
From: {sender}
Body: {content[:500]}

**Write the reply draft below:**"""

    def _parse_gemini_response(self, response_text: str) -> Dict:
        """Parse Gemini's structured response"""
        lines = response_text.strip().split('\n')
        result = {
            'category': EmailCategory.FYI,
            'importance': 1,
            'summary': '',
            'should_save': True  # 테스트 기간: 모든 메일 저장
        }

        for line in lines:
            line = line.strip()

            if line.startswith('CATEGORY:'):
                category_str = line.replace('CATEGORY:', '').strip().upper()
                if 'ACTION' in category_str:
                    result['category'] = EmailCategory.ACTION
                elif 'FYI' in category_str:
                    result['category'] = EmailCategory.FYI
                else:
                    # Default to FYI if unclear
                    result['category'] = EmailCategory.FYI

            elif line.startswith('IMPORTANCE:'):
                try:
                    importance = int(line.replace('IMPORTANCE:', '').strip()[0])
                    result['importance'] = max(1, min(5, importance))
                except:
                    result['importance'] = 1

            elif line.startswith('SUMMARY:'):
                result['summary'] = line.replace('SUMMARY:', '').strip()

            elif line.startswith('SHOULD_SAVE:'):
                should_save_str = line.replace('SHOULD_SAVE:', '').strip().upper()
                result['should_save'] = 'YES' in should_save_str

        return result

    def save_to_obsidian(self, mail: Dict, analysis: Dict) -> Optional[Path]:
        """
        Save important email to Obsidian

        Args:
            mail: Original email dict
            analysis: Analysis result from analyze_email()

        Returns:
            Path to saved file, or None if not saved
        """
        if not analysis['should_save']:
            return None

        # Create folder if it doesn't exist
        try:
            self.emails_folder.mkdir(parents=True, exist_ok=True)
            print(f"📁 Obsidian Emails 폴더 확인: {self.emails_folder}")
        except Exception as e:
            print(f"❌ Obsidian 폴더 생성 실패: {e}")
            print(f"   경로: {self.emails_folder}")
            return None

        try:
            # PATCH 1: Generate filename with time to prevent collision
            # Format: YYMMDD_HHMM_subject.md
            try:
                datetime_str = datetime.now().strftime("%y%m%d_%H%M")
            except:
                # Fallback: use short hash if time unavailable
                datetime_str = datetime.now().strftime("%y%m%d") + "_" + str(uuid.uuid4())[:4]

            # Clean subject for filename - remove ALL filesystem-forbidden characters
            # Forbidden: : / \ ? * < > |
            subject = mail['subject'][:30]
            forbidden_chars = [':', '/', '\\', '?', '*', '<', '>', '|', '"', "'"]
            for char in forbidden_chars:
                subject = subject.replace(char, '_')
            # Remove leading/trailing spaces and dots
            subject = subject.strip('. ')

            # Phase 0: Filename format with time (prevents same-day collision)
            filename = f"{datetime_str}_{subject}.md"
            filepath = self.emails_folder / filename

            # Create markdown content
            content = self._format_email_markdown(mail, analysis)

            # Write file
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)

            print(f"💾 로컬 저장: {filename}")
            return filepath

        except Exception as e:
            print(f"❌ 로컬 저장 실패: {e}")
            print(f"   경로: {filepath}")
            return None

    def _format_email_markdown(self, mail: Dict, analysis: Dict) -> str:
        """
        Format email as markdown with Phase 0 metadata
        Phase 1.1: Added hash field to frontmatter
        """
        category = analysis['category'].value
        importance = "⭐" * analysis['importance']

        # Phase 1.1: Generate hash for this email
        email_hash = self.generate_email_hash(mail)

        md_content = f"""---
category: {category}
hash: {email_hash}
user_corrected: false
importance: {analysis['importance']}
sender: {mail['sender']}
date: {mail['date']}
account: {mail['account']}
tags: [email, {category.lower()}]
---

# {mail['subject']}

**Category**: {category}
**Importance**: {importance}
**From**: {mail['sender']}
**Date**: {mail['date']}
**Account**: {mail['account']}

---

## 📧 Email Content

{mail['content']}

---

## 🤖 AI Analysis

**Summary**: {analysis['summary']}

"""

        # Add reply draft if exists
        if analysis.get('reply_draft'):
            md_content += f"""---

## ✍️ Reply Draft (TA)

{analysis['reply_draft']}

"""

        return md_content

    def _build_batch_prompt(self, mails: List[Dict]) -> str:
        """Build a single prompt for batch email classification"""
        email_list = []
        for idx, mail in enumerate(mails):
            email_list.append(f"""
Email #{idx}:
Subject: {mail.get('subject', 'No subject')}
Sender: {mail.get('sender', 'Unknown')}
Content: {mail.get('content', '')[:500]}...
""")

        batch_prompt = f"""You are an email classifier for 종민 (Jongmin Baek), a Physics PhD student and TA at UIC.

**Phase 0 Reflex System: Batch Classification**

Classify each email below into ACTION or FYI:

**ACTION**: Needs reply, has deadline, or TA/professor request
**FYI**: Informational only, no action required

**Emails to classify:**
{''.join(email_list)}

**Output format (JSON):**
{{
  "classifications": [
    {{"email_index": 0, "category": "ACTION", "importance": 4, "summary": "Student needs help with homework problem 2"}},
    {{"email_index": 1, "category": "FYI", "importance": 2, "summary": "Department newsletter about upcoming seminar"}}
  ]
}}

Respond ONLY with valid JSON. No additional text."""

        return batch_prompt

    def analyze_batch(self, mails: List[Dict]) -> List[Dict]:
        """
        Analyze multiple emails in a SINGLE Gemini API call (batch processing)

        Args:
            mails: List of email dicts

        Returns:
            List of dicts with 'mail' and 'analysis' keys
        """
        if not mails:
            return []

        print(f"📊 Batch processing {len(mails)} emails in single API call...")

        # Build batch prompt
        batch_prompt = self._build_batch_prompt(mails)

        # Single Gemini call for all emails
        response_text = self._call_gemini_with_timeout(batch_prompt, timeout_seconds=20)

        if not response_text:
            print("❌ Batch Gemini call failed - falling back to FYI for all")
            # PATCH 2: Increment failure counter
            self.gemini_fail_count += 1
            print(f"⚠️ Gemini fail count: {self.gemini_fail_count}")
            # Fallback: treat all as FYI
            return self._fallback_batch_analysis(mails)

        # Parse JSON response
        try:
            # Extract JSON from response (handle markdown code blocks)
            json_text = response_text.strip()
            if json_text.startswith('```'):
                # Remove markdown code block markers
                json_text = json_text.split('```')[1]
                if json_text.startswith('json'):
                    json_text = json_text[4:]
                json_text = json_text.strip()

            batch_result = json.loads(json_text)
            classifications = batch_result.get('classifications', [])

            print(f"✅ Batch classification successful: {len(classifications)} results")
            # PATCH 2: Reset failure counter on success
            self.gemini_fail_count = 0

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"❌ Batch JSON parsing failed: {type(e).__name__} - {str(e)}")
            print(f"   Response: {response_text[:300]}")
            # PATCH 2: Increment failure counter
            self.gemini_fail_count += 1
            print(f"⚠️ Gemini fail count: {self.gemini_fail_count}")
            return self._fallback_batch_analysis(mails)

        # Map classifications back to emails
        results = []
        for idx, mail in enumerate(mails):
            # Find classification for this email
            classification = next(
                (c for c in classifications if c.get('email_index') == idx),
                None
            )

            if classification:
                category_str = classification.get('category', 'FYI').upper()
                category = EmailCategory.ACTION if category_str == 'ACTION' else EmailCategory.FYI

                analysis = {
                    'category': category,
                    'importance': classification.get('importance', 3),
                    'summary': classification.get('summary', mail['subject'][:50]),
                    'reply_draft': None,
                    'should_save': True
                }

                # Generate reply draft for ACTION emails
                if category == EmailCategory.ACTION:
                    reply_prompt = self._build_reply_prompt(
                        mail['subject'], mail['sender'], mail['content']
                    )
                    reply_text = self._call_gemini_with_timeout(reply_prompt, timeout_seconds=10)
                    analysis['reply_draft'] = reply_text.strip() if reply_text else None

            else:
                # No classification found - fallback to FYI
                analysis = {
                    'category': EmailCategory.FYI,
                    'importance': 2,
                    'summary': f"[분류 누락] {mail['subject'][:50]}",
                    'reply_draft': None,
                    'should_save': True
                }

            results.append({
                'mail': mail,
                'analysis': analysis
            })

            # Save to local storage
            self.save_to_obsidian(mail, analysis)

        return results

    def _fallback_batch_analysis(self, mails: List[Dict]) -> List[Dict]:
        """Fallback analysis when batch processing fails"""
        print("⚠️ Using fallback analysis (all → FYI)")
        results = []
        for mail in mails:
            analysis = {
                'category': EmailCategory.FYI,
                'importance': 1,
                'summary': f"[Batch 실패] {mail['subject'][:50]}",
                'reply_draft': None,
                'should_save': True
            }
            results.append({
                'mail': mail,
                'analysis': analysis
            })
            self.save_to_obsidian(mail, analysis)
        return results

    def should_alert_gemini_failure(self) -> bool:
        """
        PATCH 2: Check if Gemini consecutive failure alert should be sent

        Returns:
            True if gemini_fail_count >= 3
        """
        return self.gemini_fail_count >= 3

    def format_categorized_summary(self, analyzed_mails: List[Dict]) -> str:
        """
        Format analyzed emails as Telegram message with categories

        Args:
            analyzed_mails: Output from analyze_batch()

        Returns:
            Formatted message string
        """
        if not analyzed_mails:
            return "📭 읽지 않은 메일이 없습니다."

        # Group by category (Phase 1.3: ACTION/FYI/UNCERTAIN)
        by_category = {
            EmailCategory.ACTION: [],
            EmailCategory.FYI: [],
            EmailCategory.UNCERTAIN: []  # Phase 1.3: RLM low-confidence
        }

        for item in analyzed_mails:
            category = item['analysis']['category']
            by_category[category].append(item)

        # Build message
        action_count = len(by_category[EmailCategory.ACTION])
        fyi_count = len(by_category[EmailCategory.FYI])
        uncertain_count = len(by_category[EmailCategory.UNCERTAIN])

        message = f"📬 **읽지 않은 메일 {len(analyzed_mails)}개**\n"
        message += f"🔴 ACTION: {action_count} | ℹ️ FYI: {fyi_count}"

        # Phase 1.3: Show UNCERTAIN count if RLM is active
        if uncertain_count > 0:
            message += f" | ❓ UNCERTAIN: {uncertain_count}"

        message += "\n\n"

        for category in EmailCategory:
            mails = by_category.get(category, [])
            if not mails:
                continue

            # Phase 1.3: Special icon for UNCERTAIN
            category_icon = "❓" if category == EmailCategory.UNCERTAIN else ""
            message += f"\n### {category_icon}{category.value} ({len(mails)}개)\n"
            message += "=" * 40 + "\n"

            # Phase 1.3: Add explanation for UNCERTAIN
            if category == EmailCategory.UNCERTAIN:
                message += "❓ **Classification is ambiguous. RLM consistency check failed.**\n"
                message += "Please review manually to determine ACTION vs FYI.\n"

            message += "\n"

            for item in mails:
                mail = item['mail']
                analysis = item['analysis']
                importance = "⭐" * analysis['importance']

                # Phase 1.1: Generate and display hash
                email_hash = self.generate_email_hash(mail)

                message += f"**[#{email_hash}] {mail['subject']}**\n"
                message += f"👤 {mail['sender']}\n"
                message += f"📅 {mail['date']}\n"
                message += f"{importance} {analysis['summary']}\n"

                # Phase 1.3: Show RLM metadata if available
                if analysis.get('rlm_metadata'):
                    metadata = analysis['rlm_metadata']
                    confidence = metadata.get('confidence', 0)
                    votes = metadata.get('votes', [])
                    message += f"🔬 RLM: confidence={confidence:.2f}, votes={votes}\n"

                # Show reply draft for ACTION emails (skip for UNCERTAIN)
                if category == EmailCategory.ACTION and analysis.get('reply_draft'):
                    message += f"\n💬 **답장 초안**:\n{analysis['reply_draft'][:200]}...\n"

                message += "\n" + "-" * 40 + "\n\n"

        return message


# Test function
def test_email_analyzer():
    """Test email_analyzer.py"""
    print("=" * 60)
    print("  🧠 Email Analyzer 테스트")
    print("=" * 60)
    print()

    analyzer = EmailAnalyzer()

    # Test email
    test_mail = {
        'subject': '[PHYS 142] Homework 3 Question',
        'sender': 'student@uic.edu',
        'content': 'Hi, I have a question about problem 2 in homework 3. Can you help?',
        'date': 'Wed, 4 Feb 2026 10:30:00',
        'account': 'UIC'
    }

    print("[1/3] 메일 분석 중...")
    analysis = analyzer.analyze_email(test_mail)

    print(f"✅ 카테고리: {analysis['category'].value}")
    print(f"✅ 중요도: {'⭐' * analysis['importance']}")
    print(f"✅ 요약: {analysis['summary']}")
    print(f"✅ Obsidian 저장: {'Yes' if analysis['should_save'] else 'No'}")

    if analysis.get('reply_draft'):
        print(f"\n[2/3] TA 답장 초안:")
        print(analysis['reply_draft'])

    print(f"\n[3/3] Obsidian 저장 테스트...")
    saved_path = analyzer.save_to_obsidian(test_mail, analysis)
    if saved_path:
        print(f"✅ 저장 완료: {saved_path}")

    print()
    print("=" * 60)
    print("  ✅ 테스트 완료!")
    print("=" * 60)


if __name__ == "__main__":
    test_email_analyzer()
