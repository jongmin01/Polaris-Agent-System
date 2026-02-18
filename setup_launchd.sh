#!/bin/bash
#
# Polaris Bot launchd 자동 설정 스크립트
# 24/7 상시 운영을 위한 자동 시작 설정
#

set -e  # 에러 시 즉시 종료

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Polaris Bot launchd 자동 설정${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# ========================================
# 1. 환경 확인
# ========================================

echo -e "${YELLOW}[1/6] 환경 확인 중...${NC}"

# Python 경로 확인
PYTHON_PATH=$(which python3)
if [ -z "$PYTHON_PATH" ]; then
    echo -e "${RED}❌ Python3를 찾을 수 없습니다.${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Python: $PYTHON_PATH${NC}"

# 현재 사용자
CURRENT_USER=$(whoami)
echo -e "${GREEN}✅ 사용자: $CURRENT_USER${NC}"

# 프로젝트 경로 (스크립트가 있는 디렉토리)
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo -e "${GREEN}✅ 프로젝트: $PROJECT_DIR${NC}"

# bot_v2.py 확인
if [ ! -f "$PROJECT_DIR/polaris/bot_v2.py" ]; then
    echo -e "${RED}❌ polaris/bot_v2.py를 찾을 수 없습니다.${NC}"
    exit 1
fi
echo -e "${GREEN}✅ polaris/bot_v2.py 발견${NC}"

echo ""

# ========================================
# 2. 가상환경 확인 (선택적)
# ========================================

echo -e "${YELLOW}[2/6] 가상환경 확인...${NC}"

VENV_PATH=""
if [ -d "$PROJECT_DIR/venv" ]; then
    VENV_PATH="$PROJECT_DIR/venv/bin/python"
    echo -e "${GREEN}✅ 가상환경 발견: $VENV_PATH${NC}"
    PYTHON_PATH=$VENV_PATH
elif [ -d "$PROJECT_DIR/.venv" ]; then
    VENV_PATH="$PROJECT_DIR/.venv/bin/python"
    echo -e "${GREEN}✅ 가상환경 발견: $VENV_PATH${NC}"
    PYTHON_PATH=$VENV_PATH
else
    echo -e "${YELLOW}⚠️  가상환경 없음 (시스템 Python 사용)${NC}"
fi

echo ""

# ========================================
# 3. plist 파일 생성
# ========================================

echo -e "${YELLOW}[3/6] plist 파일 생성 중...${NC}"

PLIST_DIR="$HOME/Library/LaunchAgents"
PLIST_FILE="$PLIST_DIR/com.polaris.bot.plist"
LOG_DIR="$PROJECT_DIR/logs"

# logs 디렉토리 생성
mkdir -p "$LOG_DIR"
echo -e "${GREEN}✅ 로그 디렉토리: $LOG_DIR${NC}"

# plist 내용 생성
cat > "$PLIST_FILE" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.polaris.bot</string>

    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON_PATH</string>
        <string>$PROJECT_DIR/polaris/bot_v2.py</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>

    <key>StandardOutPath</key>
    <string>$LOG_DIR/polaris.log</string>

    <key>StandardErrorPath</key>
    <string>$LOG_DIR/polaris.error.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>

    <key>ThrottleInterval</key>
    <integer>10</integer>
</dict>
</plist>
EOF

echo -e "${GREEN}✅ plist 생성 완료: $PLIST_FILE${NC}"
echo ""

# ========================================
# 4. 권한 설정
# ========================================

echo -e "${YELLOW}[4/6] 권한 설정 중...${NC}"

chmod 644 "$PLIST_FILE"
echo -e "${GREEN}✅ plist 권한 설정 완료${NC}"

echo ""

# ========================================
# 5. launchd 등록
# ========================================

echo -e "${YELLOW}[5/6] launchd 등록 중...${NC}"

# 기존 서비스가 있으면 제거
if launchctl list | grep -q "com.polaris.bot"; then
    echo -e "${YELLOW}⚠️  기존 서비스 제거 중...${NC}"
    launchctl unload "$PLIST_FILE" 2>/dev/null || true
    sleep 2
fi

# 새 서비스 등록
launchctl load "$PLIST_FILE"
sleep 2

# 시작
launchctl start com.polaris.bot
sleep 2

echo -e "${GREEN}✅ launchd 등록 완료${NC}"
echo ""

# ========================================
# 6. 동작 확인
# ========================================

echo -e "${YELLOW}[6/6] 동작 확인 중...${NC}"

# 프로세스 확인
if launchctl list | grep -q "com.polaris.bot"; then
    echo -e "${GREEN}✅ 서비스 등록 확인${NC}"

    # 프로세스 확인
    if pgrep -f "bot_v2.py" > /dev/null; then
        echo -e "${GREEN}✅ Polaris Bot 실행 중${NC}"
    else
        echo -e "${YELLOW}⚠️  Bot이 아직 시작 안됨 (로그 확인 필요)${NC}"
    fi
else
    echo -e "${RED}❌ 서비스 등록 실패${NC}"
    exit 1
fi

echo ""

# ========================================
# 완료 메시지
# ========================================

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  ✅ Polaris Bot 24/7 설정 완료!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}📊 상태 확인:${NC}"
echo -e "   launchctl list | grep polaris"
echo ""
echo -e "${BLUE}📝 로그 확인:${NC}"
echo -e "   tail -f $LOG_DIR/polaris.log"
echo -e "   tail -f $LOG_DIR/polaris.error.log"
echo ""
echo -e "${BLUE}🛑 서비스 중지:${NC}"
echo -e "   launchctl stop com.polaris.bot"
echo ""
echo -e "${BLUE}🔄 서비스 재시작:${NC}"
echo -e "   launchctl stop com.polaris.bot"
echo -e "   launchctl start com.polaris.bot"
echo ""
echo -e "${BLUE}❌ 서비스 제거:${NC}"
echo -e "   launchctl unload $PLIST_FILE"
echo -e "   rm $PLIST_FILE"
echo ""
echo -e "${GREEN}🌟 Polaris는 이제 Mac 시작 시 자동으로 실행됩니다!${NC}"
echo ""
