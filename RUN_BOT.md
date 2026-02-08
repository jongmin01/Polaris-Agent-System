# 🌟 Polaris Bot 실행 가이드

## 📦 1단계: 패키지 재설치

python-telegram-bot을 v20.8로 다운그레이드해야 합니다:

```bash
# 현재 디렉토리로 이동
cd ~/Desktop/Polaris_Agent_System

# 기존 패키지 삭제 (중요!)
pip3 uninstall -y python-telegram-bot

# 모든 패키지 재설치
pip3 install -r requirements.txt --break-system-packages
```

**예상 시간**: 1-2분

---

## 🚀 2단계: Bot 실행

```bash
python3 polaris_bot.py
```

**성공 메시지**:
```
2026-02-04 XX:XX:XX - __main__ - INFO - 🌟 Polaris Bot initialized
2026-02-04 XX:XX:XX - __main__ - INFO - 📁 Obsidian path: /Users/jongmin/...
2026-02-04 XX:XX:XX - __main__ - INFO - 🌟 Polaris Bot starting...
```

---

## 💬 3단계: Telegram에서 테스트

1. Telegram 앱 열기
2. `@MyPolaris_bot` 검색
3. `/start` 입력
4. "MoS2 논문 검색해줘" 테스트

---

## ⚠️ 문제 해결

### 에러: "No module named 'telegram'"
```bash
pip3 install python-telegram-bot==20.8 --break-system-packages
```

### 에러: "TELEGRAM_BOT_TOKEN not found"
`.env` 파일에 토큰이 제대로 설정되었는지 확인:
```bash
cat .env | grep TELEGRAM
```

### 경고 메시지들 (무시 가능)
- `FutureWarning: Python 3.9` → 작동에는 문제 없음
- `NotOpenSSLWarning` → 작동에는 문제 없음
- `google.generativeai package deprecated` → 나중에 업데이트 예정

---

## 🎉 성공 확인

Telegram에서 봇이 응답하면 성공입니다!

```
🌟 Polaris에 오신 것을 환영합니다!
당신의 연구를 안내하는 북극성 ⭐
```

---

## 📝 다음 단계

1. **24/7 운영**: launchd 설정 (MAC_MINI_MIGRATION.md 참조)
2. **Email-Agent 개발**: TA 메일 자동 관리
3. **DFT-Agent 개발**: VASP 계산 자동화
