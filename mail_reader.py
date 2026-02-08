#!/usr/bin/env python3
"""
mail_reader.py - Mail.app 읽기 모듈

AppleScript를 사용하여 Mac Mail.app에서 메일 읽기
UIC 계정 (jbaek27@uic.edu) 전용
"""

import subprocess
import os
import time
from typing import List, Dict, Optional
from pathlib import Path


class MailReader:
    """
    Mac Mail.app에서 메일 읽기

    Features:
    - 특정 계정의 읽지 않은 메일 읽기
    - AppleScript 기반 안전한 접근
    - 제목, 발신자, 본문 추출
    """

    def __init__(self, account_keyword: str = "UIC"):
        """
        Args:
            account_keyword: 대상 메일 계정 키워드 (기본값: UIC)
                           계정 이름 또는 이메일 주소의 일부
        """
        print("📧 Mail.app fetch initialized")

        self.account_keyword = account_keyword
        self.script_path = Path(__file__).parent / "read_mail.scpt"

        if not self.script_path.exists():
            raise FileNotFoundError(f"AppleScript 파일을 찾을 수 없습니다: {self.script_path}")

        # Preflight check: Ensure Mail.app is accessible
        self._preflight_check()

    def _preflight_check(self):
        """
        Mail.app 접근 가능 여부 사전 체크

        1. Mail.app 실행
        2. 기본 AppleScript 명령 테스트
        """
        print("🔍 Mail.app preflight check...")

        # Step 1: Launch Mail.app explicitly
        try:
            launch_result = subprocess.run(
                ['open', '-a', 'Mail'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if launch_result.returncode != 0:
                print(f"⚠️  Mail.app 실행 경고: {launch_result.stderr}")
            else:
                print("✅ Mail.app 실행됨")

            # Wait for Mail.app to fully launch
            time.sleep(2)

        except Exception as e:
            print(f"⚠️  Mail.app 실행 실패: {e}")

        # Step 2: Test basic Mail.app access
        try:
            test_result = subprocess.run(
                ['osascript', '-e', 'tell application "Mail" to count of messages in inbox'],
                capture_output=True,
                text=True,
                timeout=10
            )

            if test_result.returncode != 0:
                error_msg = f"MAIL_APP_PERMISSION_FAILURE: {test_result.stderr.strip()}"
                print(f"❌ {error_msg}")
                raise Exception(error_msg)

            print(f"✅ Mail.app 접근 성공 (inbox count: {test_result.stdout.strip()})")

        except subprocess.TimeoutExpired:
            raise Exception("MAIL_APP_TIMEOUT: Preflight check timed out")
        except Exception as e:
            if "MAIL_APP" in str(e):
                raise
            raise Exception(f"MAIL_APP_ACCESS_FAILURE: {str(e)}")

    def get_unread_mails(self, limit: int = 5) -> List[Dict]:
        """
        읽지 않은 메일 가져오기

        Args:
            limit: 가져올 메일 개수 (기본값: 5)

        Returns:
            메일 정보 리스트
            [
                {
                    'subject': '제목',
                    'sender': '발신자',
                    'content': '본문 (최대 500자)',
                    'date': '날짜'
                },
                ...
            ]
        """
        try:
            # AppleScript 실행 (explicit stderr/stdout capture)
            result = subprocess.run(
                ['osascript', str(self.script_path), self.account_keyword, str(limit)],
                capture_output=True,
                text=True,
                timeout=30
            )

            # Log execution details
            print(f"📊 AppleScript execution:")
            print(f"   Return code: {result.returncode}")
            print(f"   stdout length: {len(result.stdout)} chars")
            if result.stderr:
                print(f"   stderr: {result.stderr[:200]}")

            if result.returncode != 0:
                # DETAILED ERROR LOGGING
                print(f"❌ AppleScript 실행 실패 (exit code: {result.returncode})")
                print(f"   Script: {self.script_path}")
                print(f"   Args: {self.account_keyword}, {limit}")
                print(f"   stderr: {result.stderr}")
                print(f"   stdout: {result.stdout}")

                # Raise specific exception instead of returning empty list
                raise Exception(f"MAIL_FETCH_FAILED: exit_code={result.returncode}, stderr={result.stderr.strip()}")

            output = result.stdout.strip()

            # 에러 체크
            if output.startswith("ERROR:"):
                error_detail = output.replace("ERROR:", "").strip()
                print(f"❌ AppleScript reported error: {error_detail}")
                raise Exception(f"MAIL_FETCH_FAILED: {error_detail}")

            # 읽지 않은 메일 없음
            if output == "NO_UNREAD_MAILS":
                print("📭 No unread mails")
                return []

            # 파싱
            mails = self._parse_mail_output(output)
            print(f"✅ Successfully parsed {len(mails)} emails")
            return mails

        except subprocess.TimeoutExpired:
            error_msg = "MAIL_FETCH_TIMEOUT: AppleScript execution timed out after 30s"
            print(f"❌ {error_msg}")
            raise Exception(error_msg)
        except Exception as e:
            # Re-raise if already a MAIL_FETCH error
            if "MAIL_FETCH" in str(e):
                raise
            # Otherwise wrap in generic MAIL_FETCH_FAILED
            print(f"❌ Unexpected error in mail fetch: {e}")
            raise Exception(f"MAIL_FETCH_FAILED: {str(e)}")

    def _parse_mail_output(self, output: str) -> List[Dict]:
        """
        AppleScript 출력 파싱

        형식: mail1:::mail2:::mail3
        각 메일: subject|||sender|||content|||date
        """
        mails = []

        # 메일 구분 (:::)
        mail_entries = output.split(':::')

        for entry in mail_entries:
            if not entry.strip():
                continue

            # 필드 분리 (|||)
            parts = entry.split('|||')

            if len(parts) >= 5:
                mails.append({
                    'subject': parts[0].strip(),
                    'sender': parts[1].strip(),
                    'content': parts[2].strip(),
                    'date': parts[3].strip(),
                    'account': parts[4].strip()  # 계정 이름 추가
                })

        return mails

    def format_mails_for_telegram(self, mails: List[Dict]) -> str:
        """
        Telegram용 메시지 포맷팅

        Args:
            mails: 메일 리스트

        Returns:
            포맷팅된 메시지
        """
        if not mails:
            return "📭 읽지 않은 메일이 없습니다."

        message = f"📬 **읽지 않은 메일 {len(mails)}개**\n"
        # 계정 정보 (첫 메일의 계정 표시)
        if mails:
            message += f"📧 계정: {mails[0].get('account', 'Unknown')}\n\n"
        message += "=" * 50 + "\n\n"

        for i, mail in enumerate(mails, 1):
            message += f"**{i}. {mail['subject']}**\n"
            message += f"👤 {mail['sender']}\n"
            message += f"📅 {mail['date']}\n\n"

            # 본문 미리보기 (첫 100자)
            preview = mail['content'][:100]
            if len(mail['content']) > 100:
                preview += "..."
            message += f"💬 {preview}\n\n"
            message += "-" * 50 + "\n\n"

        return message

    def get_unread_count(self) -> int:
        """
        읽지 않은 메일 개수만 가져오기

        Returns:
            읽지 않은 메일 개수
        """
        mails = self.get_unread_mails(limit=100)  # 많이 가져와서 카운트
        return len(mails)


# 테스트용
def test_mail_reader():
    """mail_reader.py 테스트"""
    print("=" * 60)
    print("  📧 Mail Reader 테스트")
    print("=" * 60)
    print()

    reader = MailReader(account_keyword="UIC")

    print("[1/2] 읽지 않은 메일 가져오기...")
    mails = reader.get_unread_mails(limit=5)

    if mails:
        print(f"✅ {len(mails)}개 메일 발견\n")

        # Telegram 포맷 테스트
        telegram_msg = reader.format_mails_for_telegram(mails)
        print(telegram_msg)
    else:
        print("📭 읽지 않은 메일 없음")

    print()
    print("[2/2] 읽지 않은 메일 개수...")
    count = reader.get_unread_count()
    print(f"📬 총 {count}개")

    print()
    print("=" * 60)
    print("  ✅ 테스트 완료!")
    print("=" * 60)


if __name__ == "__main__":
    test_mail_reader()
