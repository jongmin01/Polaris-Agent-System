# 🚀 맥미니 이전 가이드

Polaris Agent System을 맥미니로 이전하는 완벽 가이드

---

## ✅ 이전 전 체크리스트

### 현재 컴퓨터에서 확인

- [ ] Polaris 시스템 테스트 완료
- [ ] .env 파일 준비됨 (API 키 포함)
- [ ] Obsidian 폴더 iCloud 동기화 완료
- [ ] PhD-Agent 코드 Git 커밋 (또는 압축)

---

## 📦 이전할 파일 목록

### 1. PhD-Agent 폴더 전체
```
PhD-Agent/
├── orchestrator.py          # ⭐ Polaris Orchestrator
├── phd_agent.py            # ⭐ PhD Agent
├── polaris_bot.py          # ⭐ Telegram Bot
├── paper_workflow.py       # 논문 검색/다운로드
├── analyze_paper_v2.py     # 논문 분석
├── test_polaris_system.py  # 테스트 스크립트
├── requirements.txt        # 패키지 목록
├── .env                    # 🔒 API 키 (중요!)
├── .env.example           # 템플릿
├── README.md              # 문서
├── MAC_MINI_MIGRATION.md  # 이 파일
└── TELEGRAM_SETUP.md      # Telegram 설정
```

### 2. Obsidian 폴더 (iCloud 자동 동기화)
```
Obsidian/
├── master_prompt.md
├── .agent_system/
├── My Second Brain/
├── Life/
└── Personal_Operations_V1/
```

---

## 🔄 이전 방법 (3가지)

### Method 1: Git (추천 ⭐)

#### 현재 컴퓨터
```bash
cd ~/PhD-Agent

# Git 초기화 (처음만)
git init
git add .
git commit -m "Polaris v0.2 - Initial complete system"

# GitHub에 업로드
gh repo create PhD-Agent --private --source=. --push

# 또는 기존 repo에 푸시
git remote add origin https://github.com/yourusername/PhD-Agent.git
git push -u origin main
```

#### 맥미니
```bash
# Clone
cd ~
git clone https://github.com/yourusername/PhD-Agent.git

# .env 파일 별도 복사 필요 (Git에 포함 안됨)
```

**장점**: 버전 관리, 나중에 업데이트 쉬움
**주의**: .env 파일은 Git에 올리지 말 것!

---

### Method 2: iCloud

#### 현재 컴퓨터
```bash
# PhD-Agent를 iCloud로 복사
cp -r ~/PhD-Agent ~/Library/Mobile\ Documents/com~apple~CloudDocs/
```

#### 맥미니
```bash
# iCloud 동기화 대기 (몇 분)
# 동기화 완료 후
cp -r ~/Library/Mobile\ Documents/com~apple~CloudDocs/PhD-Agent ~/
```

**장점**: 간단, .env 파일도 자동 이전
**단점**: 동기화 시간, 버전 관리 없음

---

### Method 3: AirDrop / USB

#### 현재 컴퓨터
```bash
# 폴더 압축
cd ~
tar -czf PhD-Agent.tar.gz PhD-Agent/
```

#### 전송
- AirDrop으로 맥미니로 전송, 또는
- USB 드라이브 사용

#### 맥미니
```bash
# 압축 해제
cd ~
tar -xzf PhD-Agent.tar.gz
```

**장점**: 빠름, 인터넷 불필요
**단점**: 수동 작업

---

## ⚙️ 맥미니 설정

### 1. Python 환경 확인
```bash
# Python 버전 (3.8+ 필요)
python3 --version

# pip 업데이트
python3 -m pip install --upgrade pip
```

### 2. Cowork 설치 확인
```bash
# Cowork이 설치되어 있는지 확인
claude --version

# 없으면 설치
# https://claude.ai/download
```

### 3. PhD-Agent 설정
```bash
cd ~/PhD-Agent

# 가상환경 생성 (선택적이지만 권장)
python3 -m venv venv
source venv/bin/activate

# 패키지 설치
pip install -r requirements.txt
```

### 4. .env 파일 설정
```bash
# .env 파일이 없으면 생성
cp .env.example .env

# API 키 입력
nano .env
```

`.env` 내용:
```bash
TELEGRAM_BOT_TOKEN=your_bot_token_here
GEMINI_API_KEY=your_gemini_key_here
ANTHROPIC_API_KEY=your_claude_key_here  # 선택적
OBSIDIAN_PATH=/Users/yourusername/Library/Mobile Documents/com~apple~CloudDocs/Obsidian
```

**중요**: OBSIDIAN_PATH를 맥미니의 실제 경로로 수정!

### 5. Obsidian 경로 확인
```bash
# Obsidian 폴더가 iCloud 동기화 완료되었는지 확인
ls -la ~/Library/Mobile\ Documents/com~apple~CloudDocs/Obsidian/

# 확인할 파일들
# - master_prompt.md
# - .agent_system/
# - My Second Brain/
```

### 6. 테스트
```bash
cd ~/PhD-Agent

# 전체 시스템 테스트
python test_polaris_system.py
```

모든 테스트가 ✅ 통과하면 성공!

---

## 🚀 24/7 운영 설정

### launchd로 자동 시작 (macOS)

#### 1. plist 파일 생성
```bash
nano ~/Library/LaunchAgents/com.polaris.bot.plist
```

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.polaris.bot</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/yourusername/PhD-Agent/venv/bin/python</string>
        <string>/Users/yourusername/PhD-Agent/polaris_bot.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/yourusername/PhD-Agent/polaris.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/yourusername/PhD-Agent/polaris.error.log</string>
</dict>
</plist>
```

#### 2. 서비스 등록
```bash
# 권한 설정
chmod 644 ~/Library/LaunchAgents/com.polaris.bot.plist

# 서비스 로드
launchctl load ~/Library/LaunchAgents/com.polaris.bot.plist

# 상태 확인
launchctl list | grep polaris
```

#### 3. 제어 명령어
```bash
# 시작
launchctl start com.polaris.bot

# 중지
launchctl stop com.polaris.bot

# 재시작
launchctl unload ~/Library/LaunchAgents/com.polaris.bot.plist
launchctl load ~/Library/LaunchAgents/com.polaris.bot.plist
```

---

## 📊 동작 확인

### 1. 로그 확인
```bash
# 실시간 로그 보기
tail -f ~/PhD-Agent/polaris.log

# 에러 로그
tail -f ~/PhD-Agent/polaris.error.log
```

### 2. Telegram 테스트
```
1. Telegram에서 봇 찾기: @polaris_jm_bot
2. /start 입력
3. "MoS2 논문 검색해줘" 테스트
```

### 3. 프로세스 확인
```bash
# Python 프로세스 확인
ps aux | grep polaris_bot
```

---

## 🔧 문제 해결

### "Permission denied" 에러
```bash
chmod +x polaris_bot.py
chmod +x orchestrator.py
chmod +x phd_agent.py
```

### "ModuleNotFoundError"
```bash
# 가상환경 활성화 확인
source ~/PhD-Agent/venv/bin/activate

# 패키지 재설치
pip install -r requirements.txt
```

### "OBSIDIAN_PATH not found"
```bash
# .env 파일 확인
cat ~/PhD-Agent/.env

# 경로 수정
nano ~/PhD-Agent/.env
```

### Telegram Bot 응답 없음
```bash
# Bot 프로세스 확인
ps aux | grep polaris

# 로그 확인
tail -50 ~/PhD-Agent/polaris.log

# 재시작
launchctl restart com.polaris.bot
```

---

## 🎯 이전 완료 체크리스트

- [ ] PhD-Agent 폴더 맥미니로 이전 완료
- [ ] .env 파일 설정 완료
- [ ] Obsidian iCloud 동기화 완료
- [ ] requirements.txt 패키지 설치 완료
- [ ] test_polaris_system.py 모든 테스트 통과
- [ ] Telegram Bot 정상 응답 확인
- [ ] launchd 자동 시작 설정 완료 (선택적)
- [ ] 현재 컴퓨터에서 최종 테스트 완료

---

## 🌟 다음 단계

맥미니에서 Polaris가 정상 작동하면:

1. **Life-Agent 개발** - 일정/메일 관리
2. **DFT-Agent 개발** - VASP 자동화
3. **HPC 연동** - Polaris 클러스터 SSH
4. **GNN 파이프라인** - 밴드 구조 예측

---

**이전 중 문제가 생기면**:
1. 로그 확인 (`polaris.log`, `polaris.error.log`)
2. 테스트 스크립트 실행 (`test_polaris_system.py`)
3. 현재 대화 요약 참고

**축하합니다! 🎉**
맥미니에서 24/7 Polaris 시스템을 운영할 준비가 되었습니다!
