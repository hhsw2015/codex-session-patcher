"""Real-time session file monitoring with incremental scanning.

Uses OS-native file system events (FSEvents on macOS, inotify on Linux)
via the watchdog library. When a session file changes, performs an
incremental scan and pushes results to connected WebSocket clients.
"""

import asyncio
import logging
import os
import threading
from typing import Optional

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent

logger = logging.getLogger(__name__)

DEFAULT_CODEX_DIR = os.path.expanduser("~/.codex/sessions/")
DEFAULT_CLAUDE_DIR = os.path.expanduser("~/.claude/projects/")


class SessionFileHandler(FileSystemEventHandler):
    """Handles file system events for session JSONL files."""

    def __init__(self, callback, debounce_ms: int = 500):
        super().__init__()
        self._callback = callback
        self._debounce_ms = debounce_ms
        self._pending = {}
        self._lock = threading.Lock()
        self._timer = None

    def on_modified(self, event):
        if event.is_directory:
            return
        if not self._is_session_file(event.src_path):
            return
        self._schedule(event.src_path)

    def on_created(self, event):
        if event.is_directory:
            return
        if not self._is_session_file(event.src_path):
            return
        self._schedule(event.src_path)

    def _is_session_file(self, path: str) -> bool:
        if path.endswith('.bak') or path.endswith('.tmp'):
            return False
        return path.endswith('.jsonl')

    def _schedule(self, path: str):
        with self._lock:
            self._pending[path] = True
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(
                self._debounce_ms / 1000.0, self._flush
            )
            self._timer.daemon = True
            self._timer.start()

    def _flush(self):
        with self._lock:
            paths = list(self._pending.keys())
            self._pending.clear()
            self._timer = None
        for path in paths:
            try:
                self._callback(path)
            except Exception:
                logger.warning("File watcher callback failed for %s", path, exc_info=True)


class SessionWatcher:
    """Manages file watchers for session directories."""

    def __init__(self):
        self._observer: Optional[Observer] = None
        self._running = False
        self._on_change_callback = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def start(self, on_change_callback, loop: asyncio.AbstractEventLoop):
        """Start watching session directories.

        Args:
            on_change_callback: async function(path: str) called on file changes
            loop: asyncio event loop for scheduling async callbacks
        """
        if self._running:
            return

        self._on_change_callback = on_change_callback
        self._loop = loop
        self._observer = Observer()

        handler = SessionFileHandler(self._on_file_changed, debounce_ms=500)

        dirs_to_watch = []
        if os.path.exists(DEFAULT_CODEX_DIR):
            dirs_to_watch.append(DEFAULT_CODEX_DIR)
        if os.path.exists(DEFAULT_CLAUDE_DIR):
            dirs_to_watch.append(DEFAULT_CLAUDE_DIR)

        if not dirs_to_watch:
            logger.info("No session directories found, file watcher not started")
            return

        for d in dirs_to_watch:
            self._observer.schedule(handler, d, recursive=True)
            logger.info("Watching directory: %s", d)

        self._observer.daemon = True
        self._observer.start()
        self._running = True
        logger.info("Session file watcher started")

    def stop(self):
        if not self._running:
            return
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=2)
            self._observer = None
        self._running = False
        logger.info("Session file watcher stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    def _on_file_changed(self, path: str):
        """Called from watchdog thread. Schedules async callback on event loop."""
        if self._on_change_callback and self._loop:
            asyncio.run_coroutine_threadsafe(
                self._on_change_callback(path), self._loop
            )
