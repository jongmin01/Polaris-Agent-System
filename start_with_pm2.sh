#!/bin/bash
#
# Polaris Bot pm2 시작 스크립트
# launchd 대신 pm2를 사용한 간편한 프로세스 관리
#

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  🌟 Polaris Bot pm2 시작${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 프로젝트 디렉토리
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo -e "${YELLOW}[1/5] 환경 확인...${NC}"

# pm2 설치 확인
if ! command -v pm2 &> /dev/null; then
    echo -e "${RED}❌ pm2가 설치되지 않았습니다.${NC}"
    echo ""
    echo -e "${YELLOW}설치 방법:${NC}"
    echo "  brew install node"
    echo "  npm install -g pm2"
    exit 1
fi
echo -e "${GREEN}✅ pm2 설치 확인${NC}"

# Python 확인
PYTHON_PATH=$(which python3)
if [ -z "$PYTHON_PATH" ]; then
    echo -e "${RED}❌ Python3를 찾을 수 없습니다.${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Python: $PYTHON_PATH${NC}"

# bot_v2.py 확인
if [ ! -f "$PROJECT_DIR/polaris/bot_v2.py" ]; then
    echo -e "${RED}❌ polaris/bot_v2.py를 찾을 수 없습니다.${NC}"
    exit 1
fi
echo -e "${GREEN}✅ polaris/bot_v2.py 발견${NC}"

echo ""
echo -e "${YELLOW}[2/5] 기존 프로세스 확인...${NC}"

# 기존 프로세스가 있으면 중지
if pm2 list | grep -q "polaris-bot"; then
    echo -e "${YELLOW}⚠️  기존 프로세스 중지 중...${NC}"
    pm2 delete polaris-bot 2>/dev/null || true
    sleep 2
fi
echo -e "${GREEN}✅ 준비 완료${NC}"

echo ""
echo -e "${YELLOW}[3/5] Polaris Bot 시작...${NC}"

# pm2로 실행
pm2 start "$PROJECT_DIR/polaris/bot_v2.py" \
    --name "polaris-bot" \
    --interpreter "$PYTHON_PATH" \
    --cwd "$PROJECT_DIR" \
    --log "$PROJECT_DIR/logs/pm2.log" \
    --error "$PROJECT_DIR/logs/pm2_error.log" \
    --time

sleep 2
echo -e "${GREEN}✅ Polaris Bot 시작 완료${NC}"

echo ""
echo -e "${YELLOW}[4/5] 부팅 시 자동 시작 설정...${NC}"

# pm2 startup 설정 (macOS)
pm2 startup launchd -u $USER --hp $HOME > /dev/null 2>&1 || true

# 현재 프로세스 목록 저장
pm2 save

echo -e "${GREEN}✅ 자동 시작 설정 완료${NC}"

echo ""
echo -e "${YELLOW}[5/5] 상태 확인...${NC}"

# 프로세스 상태 확인
sleep 2
pm2 list

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  ✅ Polaris Bot 실행 완료!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}📊 유용한 명령어:${NC}"
echo ""
echo -e "  ${YELLOW}# 상태 확인${NC}"
echo "    pm2 list"
echo "    pm2 show polaris-bot"
echo ""
echo -e "  ${YELLOW}# 로그 보기${NC}"
echo "    pm2 logs polaris-bot"
echo "    pm2 logs polaris-bot --lines 100"
echo ""
echo -e "  ${YELLOW}# 모니터링${NC}"
echo "    pm2 monit"
echo ""
echo -e "  ${YELLOW}# 재시작${NC}"
echo "    pm2 restart polaris-bot"
echo ""
echo -e "  ${YELLOW}# 중지${NC}"
echo "    pm2 stop polaris-bot"
echo ""
echo -e "  ${YELLOW}# 삭제${NC}"
echo "    pm2 delete polaris-bot"
echo ""
echo -e "  ${YELLOW}# 전체 pm2 상태 초기화${NC}"
echo "    pm2 kill"
echo ""
echo -e "${GREEN}🌟 Polaris는 이제 pm2로 관리됩니다!${NC}"
echo ""
