#!/usr/bin/env python3
"""
mail_test.py - Mail.app 연동 프로토타입

UIC 학교 메일(Outlook)을 Mac Mail 앱에서 읽어오는 테스트 스크립트
AppleScript 인터페이스를 사용하여 로컬에서만 작동
"""

import subprocess
import json
from datetime import datetime
from typing import List, Dict, Optional


class MailReader:
    """
    Mac Mail.app에서 메일 읽기

    보안:
    - 모든 작업은 로컬에서만 실행
    - 계정 정보 유출 없음
    - AppleScript를 통한 안전한 접근
    """

    def __init__(self):
        """초기화"""
        self.app_name = "Mail"

    def test_mail_access(self) -> bool:
        """
        Mail.app 접근 가능 여부 테스트

        Returns:
            접근 가능 여부
        """
        script = f'''
        tell application "{self.app_name}"
            return name
        end tell
        '''

        try:
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                print(f"✅ {self.app_name} 앱 접근 가능")
                return True
            else:
                print(f"❌ {self.app_name} 접근 실패: {result.stderr}")
                return False

        except Exception as e:
            print(f"❌ 오류: {e}")
            return False

    def get_mailboxes(self) -> List[str]:
        """
        메일함 목록 가져오기

        Returns:
            메일함 이름 리스트
        """
        script = f'''
        tell application "{self.app_name}"
            set mailbox_list to {{}}
            repeat with mb in mailboxes
                set end of mailbox_list to name of mb
            end repeat
            return mailbox_list
        end tell
        '''

        try:
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                # AppleScript 출력 파싱
                output = result.stdout.strip()
                mailboxes = [mb.strip() for mb in output.split(',')]
                return mailboxes
            else:
                print(f"❌ 메일함 목록 가져오기 실패: {result.stderr}")
                return []

        except Exception as e:
            print(f"❌ 오류: {e}")
            return []

    def get_recent_mails(self, mailbox_name: str = "INBOX", limit: int = 5) -> List[Dict]:
        """
        최근 메일 가져오기

        Args:
            mailbox_name: 메일함 이름 (기본값: INBOX)
            limit: 가져올 메일 개수 (기본값: 5)

        Returns:
            메일 정보 리스트
        """
        # AppleScript로 메일 정보 추출
        # 출력 형식: subject|sender|date_received|was_read
        script = f'''
        tell application "{self.app_name}"
            set mail_list to {{}}
            set msg_count to 0

            try
                set target_mailbox to mailbox "{mailbox_name}"
                set all_messages to messages of target_mailbox

                repeat with msg in all_messages
                    if msg_count >= {limit} then
                        exit repeat
                    end if

                    set mail_subject to subject of msg
                    set mail_sender to sender of msg
                    set mail_date to date received of msg as string
                    set mail_read to read status of msg

                    set mail_info to mail_subject & "|" & mail_sender & "|" & mail_date & "|" & mail_read
                    set end of mail_list to mail_info

                    set msg_count to msg_count + 1
                end repeat

                return mail_list

            on error errMsg
                return "ERROR: " & errMsg
            end try
        end tell
        '''

        try:
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                print(f"❌ AppleScript 실행 실패: {result.stderr}")
                return []

            output = result.stdout.strip()

            # 에러 체크
            if output.startswith("ERROR:"):
                print(f"❌ {output}")
                return []

            # 파싱
            mails = []
            if output:
                # AppleScript의 출력을 줄바꿈으로 분리
                lines = output.split(', ')

                for line in lines:
                    if not line.strip():
                        continue

                    parts = line.split('|')
                    if len(parts) >= 4:
                        mails.append({
                            'subject': parts[0].strip(),
                            'sender': parts[1].strip(),
                            'date': parts[2].strip(),
                            'is_read': parts[3].strip().lower() == 'true'
                        })

            return mails

        except subprocess.TimeoutExpired:
            print("❌ 시간 초과 (30초)")
            return []
        except Exception as e:
            print(f"❌ 오류: {e}")
            return []

    def get_unread_count(self, mailbox_name: str = "INBOX") -> int:
        """
        읽지 않은 메일 개수

        Args:
            mailbox_name: 메일함 이름

        Returns:
            읽지 않은 메일 개수
        """
        script = f'''
        tell application "{self.app_name}"
            try
                set target_mailbox to mailbox "{mailbox_name}"
                return unread count of target_mailbox
            on error
                return 0
            end try
        end tell
        '''

        try:
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                return int(result.stdout.strip())
            else:
                return 0

        except Exception as e:
            print(f"❌ 오류: {e}")
            return 0


def format_mails(mails: List[Dict]) -> str:
    """메일 리스트를 읽기 쉬운 형식으로 포맷팅"""
    if not mails:
        return "📭 메일 없음"

    output = f"📬 총 {len(mails)}개 메일\n"
    output += "=" * 60 + "\n\n"

    for i, mail in enumerate(mails, 1):
        read_icon = "✅" if mail['is_read'] else "🆕"
        output += f"{i}. {read_icon} **{mail['subject']}**\n"
        output += f"   👤 {mail['sender']}\n"
        output += f"   📅 {mail['date']}\n"
        output += "\n"

    return output


def main():
    """메인 함수 - 테스트 실행"""
    print("=" * 60)
    print("  📧 Mail.app 연동 테스트")
    print("=" * 60)
    print()

    reader = MailReader()

    # 1. Mail.app 접근 테스트
    print("[1/4] Mail.app 접근 테스트...")
    if not reader.test_mail_access():
        print("\n❌ Mail.app에 접근할 수 없습니다.")
        print("\n해결 방법:")
        print("1. Mail.app이 실행 중인지 확인")
        print("2. System Preferences → Security & Privacy → Automation")
        print("3. Terminal에 Mail.app 접근 권한 부여")
        return

    print()

    # 2. 메일함 목록 가져오기
    print("[2/4] 메일함 목록 가져오기...")
    mailboxes = reader.get_mailboxes()
    if mailboxes:
        print(f"✅ 발견된 메일함: {', '.join(mailboxes[:5])}")
        if len(mailboxes) > 5:
            print(f"   ... 외 {len(mailboxes) - 5}개")
    else:
        print("⚠️  메일함을 찾을 수 없습니다.")

    print()

    # 3. 읽지 않은 메일 개수
    print("[3/4] 읽지 않은 메일 개수...")
    unread_count = reader.get_unread_count("INBOX")
    print(f"📬 읽지 않은 메일: {unread_count}개")

    print()

    # 4. 최근 메일 5개 가져오기
    print("[4/4] 최근 메일 5개 가져오기...")
    mails = reader.get_recent_mails("INBOX", limit=5)

    if mails:
        print(f"✅ {len(mails)}개 메일 가져오기 성공!\n")
        print(format_mails(mails))

        # JSON 저장 (선택적)
        save = input("\n💾 결과를 JSON으로 저장하시겠습니까? (y/n): ")
        if save.lower() == 'y':
            output_file = f"mail_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(mails, f, ensure_ascii=False, indent=2)
            print(f"✅ 저장 완료: {output_file}")

    else:
        print("❌ 메일을 가져올 수 없습니다.")
        print("\n문제 해결:")
        print("1. Mail.app에서 INBOX에 메일이 있는지 확인")
        print("2. UIC 계정이 제대로 동기화되었는지 확인")

    print()
    print("=" * 60)
    print("  ✅ 테스트 완료!")
    print("=" * 60)
    print()
    print("다음 단계:")
    print("- email_classifier.py 작성 (TA 메일 자동 분류)")
    print("- email_agent.py 통합 (Polaris Agent 연결)")


if __name__ == "__main__":
    main()
