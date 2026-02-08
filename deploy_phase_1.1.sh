#!/bin/bash
#
# Phase 1.1 Deployment Script
# Deploy Feedback Loop v2.1 to Polaris Bot
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  🚀 Phase 1.1 Deployment${NC}"
echo -e "${BLUE}  Feedback Loop v2.1${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo -e "${YELLOW}[1/4] Pre-deployment verification...${NC}"

# Check files exist
if [ ! -f "email_analyzer.py" ]; then
    echo -e "${RED}❌ email_analyzer.py not found${NC}"
    exit 1
fi

if [ ! -f "polaris_bot.py" ]; then
    echo -e "${RED}❌ polaris_bot.py not found${NC}"
    exit 1
fi

if [ ! -f "prompts/email_classify.txt" ]; then
    echo -e "${RED}❌ prompts/email_classify.txt not found${NC}"
    exit 1
fi

if [ ! -d "data/feedback" ]; then
    echo -e "${RED}❌ data/feedback/ directory not found${NC}"
    exit 1
fi

echo -e "${GREEN}✅ All files verified${NC}"

# Syntax check
echo ""
echo -e "${YELLOW}[2/4] Syntax validation...${NC}"
python3 -m py_compile email_analyzer.py
echo -e "${GREEN}✅ email_analyzer.py syntax OK${NC}"

python3 -m py_compile polaris_bot.py
echo -e "${GREEN}✅ polaris_bot.py syntax OK${NC}"

echo ""
echo -e "${YELLOW}[3/4] Restarting PM2...${NC}"

# Check if pm2 is installed
if ! command -v pm2 &> /dev/null; then
    echo -e "${RED}❌ pm2 not found${NC}"
    echo -e "${YELLOW}Install with: npm install -g pm2${NC}"
    exit 1
fi

# Restart polaris-bot
pm2 restart polaris-bot

echo -e "${GREEN}✅ PM2 restarted${NC}"

echo ""
echo -e "${YELLOW}[4/4] Post-deployment verification...${NC}"
sleep 3

# Check PM2 status
pm2 list | grep polaris-bot

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  ✅ Phase 1.1 Deployed Successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}📊 Next Steps:${NC}"
echo ""
echo -e "  ${YELLOW}1. View logs:${NC}"
echo "     pm2 logs polaris-bot --lines 30"
echo ""
echo -e "  ${YELLOW}2. Test in Telegram:${NC}"
echo "     /mail"
echo "     → Verify [#xxxx] hashes appear"
echo ""
echo -e "  ${YELLOW}3. Test feedback:${NC}"
echo "     /wrong <hash> ACTION"
echo "     → Verify success message"
echo ""
echo -e "  ${YELLOW}4. Check corrections log:${NC}"
echo "     cat data/feedback/corrections.jsonl"
echo ""
echo -e "${GREEN}🌟 Phase 1.1 is now live!${NC}"
echo ""
