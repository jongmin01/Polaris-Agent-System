#!/bin/bash
# Archive documentation to Obsidian PARA structure
# 문서를 Obsidian의 04_Archives 폴더로 정리

OBSIDIAN_BASE="/Users/jongmin/Library/Mobile Documents/iCloud~md~obsidian/Documents/My Second Brain"
ARCHIVE_FOLDER="$OBSIDIAN_BASE/40_Archives/2026_Polaris_Agent_System"
PROJECT_DIR="$HOME/Desktop/Polaris_Agent_System"

echo "📦 Polaris 문서 아카이브 시작..."
echo ""

# Create archive folder
if [ ! -d "$ARCHIVE_FOLDER" ]; then
    echo "📁 생성: $ARCHIVE_FOLDER"
    mkdir -p "$ARCHIVE_FOLDER"
else
    echo "✅ 폴더 존재: $ARCHIVE_FOLDER"
fi

# Copy Polaris_System_Architecture.md
if [ -f "$PROJECT_DIR/docs/Polaris_System_Architecture.md" ]; then
    cp "$PROJECT_DIR/docs/Polaris_System_Architecture.md" "$ARCHIVE_FOLDER/"
    echo "✅ 복사: Polaris_System_Architecture.md"
else
    echo "⚠️  파일 없음: Polaris_System_Architecture.md"
fi

# Move HANDOFF_TO_MACMINI.md if exists
if [ -f "$PROJECT_DIR/HANDOFF_TO_MACMINI.md" ]; then
    mv "$PROJECT_DIR/HANDOFF_TO_MACMINI.md" "$ARCHIVE_FOLDER/"
    echo "✅ 이동: HANDOFF_TO_MACMINI.md"
else
    echo "ℹ️  파일 없음: HANDOFF_TO_MACMINI.md (이미 이동됨?)"
fi

# Copy other documentation
for doc in EMAIL_AGENT_ROADMAP.md PM2_MIGRATION.md; do
    if [ -f "$PROJECT_DIR/$doc" ]; then
        cp "$PROJECT_DIR/$doc" "$ARCHIVE_FOLDER/"
        echo "✅ 복사: $doc"
    fi
done

echo ""
echo "📂 아카이브 내용:"
ls -lh "$ARCHIVE_FOLDER" 2>/dev/null | tail -n +2

echo ""
echo "✅ 아카이브 완료!"
echo "📍 위치: $ARCHIVE_FOLDER"
