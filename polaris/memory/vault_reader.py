"""
Polaris Vault Reader — Read-only indexer for Obsidian vault notes.

Scans markdown files in an Obsidian vault, parses frontmatter/content,
indexes them into the knowledge table with embeddings for semantic search.
Supports incremental indexing via a vault_index.json tracking file.
"""

import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Default vault path (iCloud Obsidian on Mac)
_DEFAULT_VAULT = os.path.expanduser(
    "~/Library/Mobile Documents/iCloud~md~obsidian/Documents"
)

# Directories to skip during vault scan
SKIP_DIRS = {".obsidian", ".trash", "node_modules", ".git", "99_System"}

# Minimum file size (bytes) to index — skip empty/stub notes
MIN_FILE_SIZE = 1024  # 1KB

# Max content length stored per note (for embedding efficiency)
MAX_CONTENT_LENGTH = 2000

# Folder path → category mapping
FOLDER_CATEGORY_MAP = [
    ("30_Resources/Foundations/Physics", "research"),
    ("30_Resources/Foundations", "research"),
    ("30_Resources", "reference"),
    ("20_Areas", "reference"),
    ("10_Projects", "research"),
    ("40_Archives", "reference"),
    ("Polaris/Papers", "research"),
    ("Polaris/Research", "research"),
]

# Default index file path
_DEFAULT_INDEX_PATH = str(
    Path(__file__).parent.parent.parent / "data" / "vault_index.json"
)


class VaultReader:
    """Read-only indexer for Obsidian vault notes."""

    def __init__(
        self,
        vault_path: Optional[str] = None,
        memory=None,
        index_path: Optional[str] = None,
    ):
        """
        Args:
            vault_path: Root path to Obsidian vaults directory.
            memory: PolarisMemory instance for save_knowledge().
            index_path: Path to vault_index.json for incremental tracking.
        """
        self.vault_path = vault_path or os.getenv("OBSIDIAN_VAULT_PATH", _DEFAULT_VAULT)
        self.memory = memory
        self.index_path = index_path or _DEFAULT_INDEX_PATH

    # ------------------------------------------------------------------
    # Scanning
    # ------------------------------------------------------------------

    def scan_vault(self, vault_name: str = "My Second Brain") -> List[Dict]:
        """Scan a vault for all indexable .md files.

        Returns list of dicts: {path, title, modified_time, size}
        """
        vault_dir = Path(self.vault_path) / vault_name
        if not vault_dir.exists():
            logger.warning("Vault not found: %s", vault_dir)
            return []

        results = []
        for md_file in vault_dir.rglob("*.md"):
            # Skip hidden/excluded directories
            rel_parts = md_file.relative_to(vault_dir).parts
            if any(part in SKIP_DIRS for part in rel_parts):
                continue

            stat = md_file.stat()

            # Skip small files
            if stat.st_size < MIN_FILE_SIZE:
                continue

            results.append({
                "path": str(md_file),
                "title": md_file.stem,
                "modified_time": stat.st_mtime,
                "size": stat.st_size,
            })

        logger.info("Scanned vault '%s': %d indexable notes", vault_name, len(results))
        return results

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def parse_note(self, filepath: str) -> Dict:
        """Parse a markdown note into structured data.

        Returns: {title, frontmatter, content, links, tags, path}
        """
        path = Path(filepath)
        title = path.stem

        try:
            raw = path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning("Failed to read %s: %s", filepath, e)
            return {
                "title": title,
                "frontmatter": {},
                "content": "",
                "links": [],
                "tags": [],
                "path": filepath,
            }

        # Parse YAML frontmatter
        frontmatter = {}
        content = raw
        fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", raw, re.DOTALL)
        if fm_match:
            frontmatter = self._parse_yaml_simple(fm_match.group(1))
            content = raw[fm_match.end():]

        # Extract [[wikilinks]]
        links = re.findall(r"\[\[([^\]|]+?)(?:\|[^\]]+)?\]\]", content)

        # Extract #tags (inline + frontmatter)
        inline_tags = re.findall(r"(?:^|\s)#([a-zA-Z가-힣][\w가-힣/-]*)", content)
        fm_tags = frontmatter.get("tags", [])
        if isinstance(fm_tags, str):
            fm_tags = [fm_tags]
        all_tags = list(set(inline_tags + fm_tags))

        # Strip markdown formatting for cleaner content
        clean_content = self._strip_markdown(content)

        return {
            "title": title,
            "frontmatter": frontmatter,
            "content": clean_content[:MAX_CONTENT_LENGTH],
            "links": links,
            "tags": all_tags,
            "path": filepath,
        }

    @staticmethod
    def _parse_yaml_simple(yaml_text: str) -> Dict:
        """Simple key-value YAML parser (no dependency on PyYAML).

        Handles: key: value, key: [list], tags lists.
        """
        result = {}
        current_key = None
        current_list = None

        for line in yaml_text.split("\n"):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            # List item under a key
            if stripped.startswith("- ") and current_key:
                if current_list is None:
                    current_list = []
                current_list.append(stripped[2:].strip())
                result[current_key] = current_list
                continue

            # Key: value pair
            if ":" in stripped:
                current_list = None
                key, _, value = stripped.partition(":")
                key = key.strip()
                value = value.strip()
                current_key = key

                if value.startswith("[") and value.endswith("]"):
                    # Inline list: [a, b, c]
                    items = [v.strip().strip("'\"") for v in value[1:-1].split(",") if v.strip()]
                    result[key] = items
                elif value:
                    result[key] = value.strip("'\"")
                else:
                    result[key] = ""

        return result

    @staticmethod
    def _strip_markdown(text: str) -> str:
        """Remove markdown formatting for cleaner embedding content."""
        # Remove headings markers
        text = re.sub(r"^#+\s+", "", text, flags=re.MULTILINE)
        # Remove bold/italic
        text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
        # Remove wikilinks, keep text
        text = re.sub(r"\[\[([^\]|]+?)(?:\|([^\]]+))?\]\]", lambda m: m.group(2) or m.group(1), text)
        # Remove regular links, keep text
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        # Remove images
        text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", "", text)
        # Remove HTML tags
        text = re.sub(r"<[^>]+>", "", text)
        # Collapse whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    # ------------------------------------------------------------------
    # Category inference
    # ------------------------------------------------------------------

    def infer_category(self, filepath: str, frontmatter: Dict) -> str:
        """Infer knowledge category from frontmatter or folder path."""
        # Check frontmatter first
        fm_cat = frontmatter.get("category", "")
        if fm_cat:
            return fm_cat

        # Infer from folder path
        for folder_prefix, category in FOLDER_CATEGORY_MAP:
            if folder_prefix in filepath:
                return category

        return "reference"

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def index_note(self, parsed_note: Dict) -> int:
        """Index a single parsed note into the knowledge table.

        Returns the knowledge row id, or 0 on failure.
        """
        if not self.memory:
            logger.warning("No memory instance — cannot index note")
            return 0

        category = self.infer_category(
            parsed_note["path"], parsed_note.get("frontmatter", {})
        )

        try:
            row_id = self.memory.save_knowledge(
                category=category,
                title=parsed_note["title"],
                content=parsed_note["content"],
                source="obsidian",
                tags=parsed_note.get("tags", []),
            )
            return row_id
        except Exception as e:
            logger.warning("Failed to index note '%s': %s", parsed_note["title"], e)
            return 0

    def index_vault(
        self,
        vault_name: str = "My Second Brain",
        force: bool = False,
        progress_callback=None,
    ) -> Dict:
        """Index all notes in a vault.

        Args:
            vault_name: Name of the vault subfolder.
            force: If True, re-index all notes. If False, only changed notes.
            progress_callback: Optional callable(current, total) for progress updates.

        Returns: {total, new, updated, skipped, errors}
        """
        notes = self.scan_vault(vault_name)
        index = self._load_index() if not force else {}

        stats = {"total": len(notes), "new": 0, "updated": 0, "skipped": 0, "errors": 0}

        for i, note_info in enumerate(notes):
            filepath = note_info["path"]
            modified = note_info["modified_time"]

            # Progress callback
            if progress_callback and (i % 10 == 0 or i == len(notes) - 1):
                progress_callback(i + 1, len(notes))

            # Check if already indexed and unchanged
            if not force and filepath in index:
                last_indexed = index[filepath].get("indexed_time", 0)
                if modified <= last_indexed:
                    stats["skipped"] += 1
                    continue

            # Parse and index
            parsed = self.parse_note(filepath)
            if not parsed["content"]:
                stats["skipped"] += 1
                continue

            row_id = self.index_note(parsed)
            if row_id > 0:
                if filepath in index:
                    stats["updated"] += 1
                else:
                    stats["new"] += 1

                index[filepath] = {
                    "indexed_time": time.time(),
                    "title": parsed["title"],
                    "knowledge_id": row_id,
                }
            else:
                stats["errors"] += 1

        self._save_index(index)
        logger.info(
            "Vault indexing complete: %d total, %d new, %d updated, %d skipped, %d errors",
            stats["total"], stats["new"], stats["updated"], stats["skipped"], stats["errors"],
        )
        return stats

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search_vault_knowledge(self, query: str, top_k: int = 3) -> List[Dict]:
        """Search only vault-indexed knowledge (source='obsidian').

        Uses the memory's semantic search with a source filter.
        """
        if not self.memory:
            return []

        # Use memory's embedder for query vector
        query_vec = self.memory.embedder.embed(query)

        if query_vec is not None:
            return self._semantic_vault_search(query_vec, top_k)
        return self._keyword_vault_search(query, top_k)

    def _semantic_vault_search(self, query_vec: list, top_k: int) -> List[Dict]:
        """Semantic search filtered to obsidian-sourced knowledge."""
        cursor = self.memory.conn.execute(
            """SELECT id, title, content, category, embedding, tags
               FROM knowledge
               WHERE source = 'obsidian' AND embedding IS NOT NULL"""
        )

        candidates = []
        for row in cursor:
            vec = self.memory.embedder.from_bytes(row["embedding"])
            sim = self.memory.embedder.cosine_similarity(query_vec, vec)
            candidates.append({
                "source_table": "knowledge",
                "source": "obsidian",
                "id": row["id"],
                "title": row["title"],
                "content": row["content"],
                "category": row["category"],
                "score": sim,
            })

        candidates.sort(key=lambda c: c["score"], reverse=True)
        return candidates[:top_k]

    def _keyword_vault_search(self, query: str, top_k: int) -> List[Dict]:
        """Keyword fallback filtered to obsidian-sourced knowledge."""
        pattern = f"%{query}%"
        cursor = self.memory.conn.execute(
            """SELECT id, title, content, category
               FROM knowledge
               WHERE source = 'obsidian' AND (content LIKE ? OR title LIKE ?)
               ORDER BY id DESC LIMIT ?""",
            (pattern, pattern, top_k),
        )
        return [
            {
                "source_table": "knowledge",
                "source": "obsidian",
                "id": row["id"],
                "title": row["title"],
                "content": row["content"],
                "category": row["category"],
                "score": 0.0,
            }
            for row in cursor
        ]

    # ------------------------------------------------------------------
    # Index file management
    # ------------------------------------------------------------------

    def _load_index(self) -> Dict:
        """Load vault_index.json tracking file."""
        if not os.path.exists(self.index_path):
            return {}
        try:
            with open(self.index_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning("Failed to load vault index: %s", e)
            return {}

    def _save_index(self, index: Dict):
        """Save vault_index.json tracking file."""
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
        try:
            with open(self.index_path, "w", encoding="utf-8") as f:
                json.dump(index, f, ensure_ascii=False, indent=2)
        except IOError as e:
            logger.error("Failed to save vault index: %s", e)

    def get_index_stats(self) -> Dict:
        """Get indexing statistics from vault_index.json."""
        index = self._load_index()
        if not index:
            return {"indexed_notes": 0, "last_indexed": None}

        times = [v.get("indexed_time", 0) for v in index.values()]
        last = max(times) if times else 0

        return {
            "indexed_notes": len(index),
            "last_indexed": datetime.fromtimestamp(last).strftime("%Y-%m-%d %H:%M") if last else None,
        }
