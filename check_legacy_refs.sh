#!/bin/bash
#
# check_legacy_refs.sh
# 운영 스크립트(.sh)에서 레거시 진입점 참조 여부를 검사합니다.
# polaris_bot.py 또는 orchestrator.py가 운영 파일에 남아 있으면 실패(exit 1) 처리.
#
# 사용법:
#   ./check_legacy_refs.sh              # 검사만 실행
#   ./check_legacy_refs.sh --verbose    # 참조 줄 내용까지 출력
#
# 2026-04-15 파일 삭제 전, 재유입 차단용 게이트로 사용하세요.
#

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

VERBOSE=false
if [[ "$1" == "--verbose" ]]; then
    VERBOSE=true
fi

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 감지할 레거시 패턴 (진입점으로 사용되는 경우)
LEGACY_PATTERN='polaris_bot\.py|orchestrator\.py'

# 검사 대상에서 제외할 파일 (레거시 파일 자체, 이 스크립트, 과거 단계별 배포 스크립트)
EXCLUDE_PATTERN='check_legacy_refs\.sh|/polaris_bot\.py$|/orchestrator\.py$|deploy_phase_'

echo "================================================"
echo "  Polaris Legacy Reference Check"
echo "================================================"
echo ""

FAIL=false

# ── 1. 쉘 스크립트 (.sh) 검사 ──────────────────────
echo "Checking .sh files..."
FOUND_SH=$(grep -rl --include="*.sh" -E "$LEGACY_PATTERN" "$PROJECT_DIR" 2>/dev/null \
    | grep -vE "$EXCLUDE_PATTERN" || true)

if [ -n "$FOUND_SH" ]; then
    echo -e "${RED}❌ Legacy references in shell scripts:${NC}"
    echo "$FOUND_SH"
    if $VERBOSE; then
        echo ""
        grep -rn --include="*.sh" -E "$LEGACY_PATTERN" "$PROJECT_DIR" \
            | grep -vE "$EXCLUDE_PATTERN" || true
    fi
    FAIL=true
else
    echo -e "${GREEN}✅ Shell scripts: clean${NC}"
fi

echo ""

# ── 결과 ───────────────────────────────────────────
if $FAIL; then
    echo -e "${RED}================================================${NC}"
    echo -e "${RED}  FAIL: 레거시 참조가 운영 파일에 남아 있습니다.${NC}"
    echo -e "${RED}  삭제 일정: 2026-04-15${NC}"
    echo -e "${RED}================================================${NC}"
    echo ""
    echo -e "${YELLOW}수정 방법: 위 파일에서 polaris_bot.py / orchestrator.py 참조를${NC}"
    echo -e "${YELLOW}python -m polaris.bot_v2 (또는 polaris/bot_v2.py) 로 교체하세요.${NC}"
    exit 1
else
    echo -e "${GREEN}================================================${NC}"
    echo -e "${GREEN}  PASS: 레거시 참조 없음 — 삭제 준비 완료${NC}"
    echo -e "${GREEN}================================================${NC}"
    exit 0
fi
