# 📧 Email-Agent Mail.app 연동 로드맵

## 문제 상황
- UIC 학교 메일(Outlook): 외부 API 연동 및 포워딩 차단
- 하지만 맥미니 Mail.app에는 등록 가능

## 해결 방법
**Mail.app → AppleScript → Python → Email-Agent**

---

## 🎯 Phase 1: AppleScript로 메일 읽기 (1-2일)

### 1.1 AppleScript 프로토타입

```applescript
-- read_mail.scpt
tell application "Mail"
    set inbox_messages to messages of inbox

    set mail_data to {}
    repeat with msg in inbox_messages
        set mail_info to {¬
            subject:(subject of msg), ¬
            sender:(sender of msg), ¬
            content:(content of msg), ¬
            date_received:(date received of msg), ¬
            is_read:(read status of msg)}

        set end of mail_data to mail_info
    end repeat

    return mail_data
end tell
```

### 1.2 Python에서 AppleScript 실행

```python
# mail_reader.py
import subprocess
import json
from datetime import datetime

def read_mail_via_applescript():
    """AppleScript로 Mail.app 읽기"""
    script = '''
    tell application "Mail"
        set inbox_messages to messages of inbox
        set output to ""

        repeat with msg in inbox_messages
            set output to output & (subject of msg) & "|"
            set output to output & (sender of msg) & "|"
            set output to output & (content of msg) & "|"
            set output to output & (date received of msg as string) & "\\n"
        end repeat

        return output
    end tell
    '''

    result = subprocess.run(
        ['osascript', '-e', script],
        capture_output=True,
        text=True
    )

    return parse_mail_output(result.stdout)

def parse_mail_output(raw_output):
    """파싱"""
    mails = []
    for line in raw_output.strip().split('\n'):
        if not line:
            continue
        parts = line.split('|')
        if len(parts) >= 4:
            mails.append({
                'subject': parts[0],
                'sender': parts[1],
                'content': parts[2],
                'date': parts[3]
            })
    return mails
```

### 1.3 테스트

```bash
python3 mail_reader.py
```

**예상 출력:**
```
[
  {'subject': 'HW2 Question', 'sender': 'student@uic.edu', ...},
  {'subject': 'Office Hours', 'sender': 'another@uic.edu', ...}
]
```

---

## 🎯 Phase 2: TA 메일 분류 로직 (2-3일)

### 2.1 메일 분류기

```python
# email_classifier.py
from typing import List, Dict
import re

class TAEmailClassifier:
    """TA 학생 메일 자동 분류"""

    def __init__(self):
        self.categories = {
            'homework': ['hw', 'homework', '과제', 'assignment'],
            'grade': ['grade', '성적', 'score', 'point'],
            'office_hours': ['office hour', '오피스', 'meeting', '면담'],
            'technical': ['code', 'error', '에러', 'bug', 'compile'],
            'general': []  # 기타
        }

    def classify(self, mail: Dict) -> str:
        """메일 카테고리 분류"""
        subject = mail['subject'].lower()
        content = mail['content'].lower()

        text = subject + ' ' + content

        for category, keywords in self.categories.items():
            if any(kw in text for kw in keywords):
                return category

        return 'general'

    def extract_homework_number(self, mail: Dict) -> str:
        """HW 번호 추출 (예: HW2)"""
        text = mail['subject'] + ' ' + mail['content']
        match = re.search(r'hw\s*(\d+)', text, re.IGNORECASE)
        return f"HW{match.group(1)}" if match else "Unknown"

    def is_urgent(self, mail: Dict) -> bool:
        """긴급 메일 여부"""
        urgent_keywords = ['urgent', '긴급', 'asap', 'emergency']
        text = (mail['subject'] + ' ' + mail['content']).lower()
        return any(kw in text for kw in urgent_keywords)
```

### 2.2 Obsidian 로그 저장

```python
# email_logger.py
import os
from datetime import datetime

def log_to_obsidian(mail: Dict, category: str, obsidian_path: str):
    """Obsidian에 메일 로그 저장"""

    # 저장 경로: My Second Brain/03_TA/Emails/2026-02/
    date_str = datetime.now().strftime('%Y-%m')
    log_dir = os.path.join(
        obsidian_path,
        'My Second Brain/03_TA/Emails',
        date_str
    )
    os.makedirs(log_dir, exist_ok=True)

    # 파일명: 2026-02-04_HW2_student_name.md
    today = datetime.now().strftime('%Y-%m-%d')
    sender_name = mail['sender'].split('@')[0]
    filename = f"{today}_{category}_{sender_name}.md"

    # Markdown 생성
    content = f"""---
type: ta_email
category: {category}
sender: {mail['sender']}
date: {mail['date']}
status: pending
---

# {mail['subject']}

**보낸 사람**: {mail['sender']}
**날짜**: {mail['date']}
**카테고리**: {category}

## 내용

{mail['content']}

---

## 답장 (AI 생성)

[여기에 답장 템플릿 생성]

---

[[TA]], [[Emails]]
"""

    filepath = os.path.join(log_dir, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    return filepath
```

---

## 🎯 Phase 3: Email-Agent 통합 (3-4일)

### 3.1 email_agent.py

```python
# email_agent.py
from typing import Dict, List
import os
from mail_reader import read_mail_via_applescript
from email_classifier import TAEmailClassifier
from email_logger import log_to_obsidian

class EmailAgent:
    """Email Agent - TA 학생 메일 자동 관리"""

    def __init__(self, obsidian_path: str):
        self.obsidian_path = obsidian_path
        self.classifier = TAEmailClassifier()
        self.templates = self._load_templates()

    def _load_templates(self) -> Dict:
        """답장 템플릿 로드"""
        return {
            'homework': """안녕하세요,

과제 관련 질문 감사합니다.

{specific_answer}

추가 질문이 있으시면 언제든 연락 주세요.

감사합니다,
종민""",
            'office_hours': """안녕하세요,

오피스 아워는 매주 [요일] [시간]에 [장소]에서 진행됩니다.

참석을 원하시면 미리 알려주세요.

감사합니다,
종민""",
            'general': """안녕하세요,

메일 주셔서 감사합니다.

{specific_answer}

추가 도움이 필요하시면 연락 주세요.

감사합니다,
종민"""
        }

    def handle(self, user_message: str) -> Dict:
        """
        사용자 요청 처리

        예: "TA 메일 확인해줘"
        """
        if "확인" in user_message or "check" in user_message:
            return self._check_new_mails()
        elif "답장" in user_message or "reply" in user_message:
            return self._generate_reply()
        else:
            return {
                'status': 'unknown',
                'message': '무엇을 도와드릴까요?\n\n1️⃣ 새 메일 확인\n2️⃣ 답장 생성'
            }

    def _check_new_mails(self) -> Dict:
        """새 메일 확인"""
        # 1. Mail.app에서 읽기
        mails = read_mail_via_applescript()

        # 2. 읽지 않은 메일만 필터링
        unread_mails = [m for m in mails if not m.get('is_read', False)]

        if not unread_mails:
            return {
                'status': 'success',
                'message': '📭 새 메일이 없습니다.'
            }

        # 3. 분류 및 로깅
        categorized = []
        for mail in unread_mails:
            category = self.classifier.classify(mail)
            filepath = log_to_obsidian(mail, category, self.obsidian_path)

            categorized.append({
                'subject': mail['subject'],
                'sender': mail['sender'],
                'category': category,
                'file': filepath
            })

        # 4. 결과 포맷팅
        message = f"📬 새 메일 {len(unread_mails)}개\n\n"
        for i, mail in enumerate(categorized, 1):
            icon = {'homework': '📝', 'grade': '📊', 'office_hours': '🕐'}.get(mail['category'], '📧')
            message += f"{i}. {icon} {mail['subject']}\n"
            message += f"   보낸이: {mail['sender']}\n"
            message += f"   카테고리: {mail['category']}\n\n"

        return {
            'status': 'success',
            'message': message,
            'mails': categorized
        }

    def _generate_reply(self) -> Dict:
        """답장 생성 (LLM 사용)"""
        # TODO: Gemini/Claude로 답장 생성
        return {
            'status': 'not_implemented',
            'message': '🚧 답장 생성 기능 개발 중...'
        }
```

### 3.2 phd_agent.py에 통합

```python
# phd_agent.py 수정
from email_agent import EmailAgent

class PhDAgent:
    def __init__(self, obsidian_path: str):
        self.obsidian_path = obsidian_path
        self.papers_dir = ...

        # Sub-agents
        self.agents = {
            "paper": True,
            "email": EmailAgent(obsidian_path),  # ✅ 추가
            "physics": False  # 개발 중
        }

    def handle(self, user_message: str) -> Dict:
        # 메일 키워드
        if any(kw in user_message.lower() for kw in ['메일', 'email', 'ta', '학생']):
            return self.agents['email'].handle(user_message)

        # 기존 논문 로직
        ...
```

---

## 🎯 Phase 4: 자동화 (1-2일)

### 4.1 주기적 메일 체크 (cron 또는 launchd)

```bash
# ~/Library/LaunchAgents/com.polaris.mail.plist
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.polaris.mail</string>

    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/jongmin/PhD-Agent/check_mail.py</string>
    </array>

    <!-- 30분마다 실행 -->
    <key>StartInterval</key>
    <integer>1800</integer>

    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
```

### 4.2 check_mail.py

```python
#!/usr/bin/env python3
"""
주기적으로 메일 확인 및 Telegram 알림
"""
import os
from email_agent import EmailAgent
from dotenv import load_dotenv
import telegram

load_dotenv()

def main():
    obsidian_path = os.getenv('OBSIDIAN_PATH')
    agent = EmailAgent(obsidian_path)

    result = agent._check_new_mails()

    # 새 메일이 있으면 Telegram 알림
    if result['status'] == 'success' and 'mails' in result:
        bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        chat_id = os.getenv('YOUR_CHAT_ID')  # 본인 chat_id

        bot = telegram.Bot(token=bot_token)
        bot.send_message(chat_id=chat_id, text=result['message'])

if __name__ == "__main__":
    main()
```

---

## 📊 개발 일정

| Phase | 작업 | 기간 | 상태 |
|-------|------|------|------|
| 1 | AppleScript 메일 읽기 | 1-2일 | 🔜 |
| 2 | TA 메일 분류 로직 | 2-3일 | 📅 |
| 3 | Email-Agent 통합 | 3-4일 | 📅 |
| 4 | 자동화 (cron/launchd) | 1-2일 | 📅 |

**총 예상 기간**: 1-2주

---

## ✅ 성공 기준

1. **Mail.app에서 메일 읽기**: AppleScript로 UIC 메일 접근 ✅
2. **자동 분류**: HW, 성적, 오피스아워 등 카테고리화 ✅
3. **Obsidian 로그**: 모든 메일이 Obsidian에 저장 ✅
4. **답장 생성**: Gemini/Claude로 답장 템플릿 생성 ✅
5. **Telegram 알림**: 새 메일 도착 시 실시간 알림 ✅

---

## 🚀 즉시 시작 가능

지금 바로 Phase 1을 시작할 수 있습니다:

```bash
# 1. AppleScript 테스트
osascript -e 'tell application "Mail" to get subject of messages of inbox'

# 2. mail_reader.py 생성 및 테스트
python3 mail_reader.py
```

다음 세션에서 본격 개발하시겠습니까?
