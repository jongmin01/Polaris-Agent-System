#!/bin/bash
# Obsidian 폴더 정리 스크립트
# 잘못 생성된 "00. Inbox" 폴더를 올바른 "00_Inbox"로 이동

OBSIDIAN_BASE="/Users/jongmin/Library/Mobile Documents/iCloud~md~obsidian/Documents/My Second Brain"
OLD_FOLDER="$OBSIDIAN_BASE/00. Inbox"
NEW_FOLDER="$OBSIDIAN_BASE/00_Inbox"

echo "🔍 Obsidian 폴더 정리 시작..."
echo ""

# Check if old folder exists
if [ -d "$OLD_FOLDER" ]; then
    echo "✅ 발견: $OLD_FOLDER"

    # Create new folder if it doesn't exist
    if [ ! -d "$NEW_FOLDER" ]; then
        echo "📁 생성: $NEW_FOLDER"
        mkdir -p "$NEW_FOLDER"
    fi

    # Move emails from old to new
    if [ -d "$OLD_FOLDER/Emails" ]; then
        echo "📧 이동: Emails 폴더"

        # Create Emails folder in new location
        mkdir -p "$NEW_FOLDER/Emails"

        # Move all files
        if ls "$OLD_FOLDER/Emails/"*.md 1> /dev/null 2>&1; then
            mv "$OLD_FOLDER/Emails/"*.md "$NEW_FOLDER/Emails/"
            echo "   ✅ $(ls "$NEW_FOLDER/Emails/"*.md | wc -l | xargs) 개 파일 이동 완료"
        else
            echo "   ℹ️  이동할 파일 없음"
        fi

        # Remove old Emails folder
        rmdir "$OLD_FOLDER/Emails" 2>/dev/null
    fi

    # Remove old parent folder if empty
    rmdir "$OLD_FOLDER" 2>/dev/null && echo "🗑️  삭제: $OLD_FOLDER" || echo "⚠️  $OLD_FOLDER 는 비어있지 않아 삭제하지 않았습니다"
else
    echo "ℹ️  $OLD_FOLDER 폴더가 없습니다 (이미 정리됨)"
fi

echo ""
echo "✅ 정리 완료!"
echo ""
echo "📂 최종 구조:"
ls -la "$NEW_FOLDER" 2>/dev/null || echo "   $NEW_FOLDER 생성 대기 중"
if [ -d "$NEW_FOLDER/Emails" ]; then
    echo "   └── Emails/ ($(ls "$NEW_FOLDER/Emails/"*.md 2>/dev/null | wc -l | xargs) files)"
fi
