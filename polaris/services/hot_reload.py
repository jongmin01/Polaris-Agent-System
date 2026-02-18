"""Hot-reload watcher for Polaris runtime components."""

import os
import sys
import logging
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class HotReloader:
    """File-change watcher and runtime component reloader."""

    def __init__(
        self,
        watch_root: Path,
        on_runtime_reload: Optional[Callable] = None,
        auto_reload: bool = True,
        auto_restart_on_code_change: bool = False,
        check_interval: float = 2.0,
    ):
        self.watch_root = watch_root
        self.on_runtime_reload = on_runtime_reload  # callback e.g. router._init_skills
        self.auto_reload = auto_reload
        self.auto_restart_on_code_change = auto_restart_on_code_change
        self.check_interval = check_interval
        self._last_check = 0.0
        self._watch_mtimes: Dict[str, float] = {}
        self.refresh_snapshot()

    def _iter_watch_files(self):
        """Yield files that should trigger runtime refresh/restart."""
        # Runtime data files
        runtime_patterns = [
            "skills/**/*.md",
            "data/master_prompt.md",
        ]
        for pattern in runtime_patterns:
            yield from self.watch_root.glob(pattern)

        # Code files (optional auto-restart path)
        code_patterns = [
            "polaris/**/*.py",
            "mail_reader.py",
            "email_analyzer.py",
            "schedule_agent.py",
            "hpc_monitor.py",
            "physics_agent.py",
            "phd_agent.py",
            "paper_workflow.py",
            "analyze_paper_v2.py",
        ]
        for pattern in code_patterns:
            yield from self.watch_root.glob(pattern)

    def refresh_snapshot(self):
        """Capture latest file mtimes for watched files."""
        snapshot: Dict[str, float] = {}
        for path in self._iter_watch_files():
            if not path.exists() or not path.is_file():
                continue
            try:
                snapshot[str(path)] = path.stat().st_mtime
            except OSError:
                continue
        self._watch_mtimes = snapshot

    def _detect_changed_files(self) -> List[Path]:
        """Return watched files whose mtime changed since last snapshot."""
        changed: List[Path] = []
        current: Dict[str, float] = {}
        for path in self._iter_watch_files():
            if not path.exists() or not path.is_file():
                continue
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            key = str(path)
            current[key] = mtime
            prev = self._watch_mtimes.get(key)
            if prev is None or mtime > prev:
                changed.append(path)
        self._watch_mtimes = current
        return changed

    def reload_runtime(self):
        """Reload components that can be safely refreshed in-process."""
        if self.on_runtime_reload is not None:
            self.on_runtime_reload()

    def check_and_apply(self):
        """Auto-refresh runtime files and optionally restart on code changes."""
        if not self.auto_reload:
            return
        now = time.time()
        if now - self._last_check < self.check_interval:
            return
        self._last_check = now

        changed = self._detect_changed_files()
        if not changed:
            return

        runtime_changed = [p for p in changed if p.suffix.lower() in {".md", ".json", ".yaml", ".yml"}]
        code_changed = [p for p in changed if p.suffix.lower() == ".py"]

        if runtime_changed:
            self.reload_runtime()
            logger.info(
                "Runtime hot-reload applied: %s",
                [str(p.relative_to(self.watch_root)) for p in runtime_changed],
            )

        if code_changed:
            logger.info(
                "Code changes detected: %s",
                [str(p.relative_to(self.watch_root)) for p in code_changed],
            )
            if self.auto_restart_on_code_change:
                logger.warning("Auto-restarting Polaris bot to apply code changes")
                os.execv(sys.executable, [sys.executable] + sys.argv)
            else:
                logger.warning(
                    "Code changed but auto-restart is disabled. "
                    "Set POLARIS_AUTO_RESTART_ON_CODE_CHANGE=true for zero-manual restart."
                )
