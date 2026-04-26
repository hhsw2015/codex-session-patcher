"""Persistent scan cache for incremental refusal detection.

Stores per-session scan results (refusal lines, last scanned line) in a JSON
file so subsequent scans only process newly appended content.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_CACHE_PATH = os.path.expanduser("~/.codex-patcher/scan_cache.json")


class ScanCache:
    def __init__(self, cache_path: str = DEFAULT_CACHE_PATH):
        self._path = Path(cache_path)
        self._data: Dict[str, Dict[str, Any]] = {}
        self._batch_mode = False
        self._dirty = False
        self.load()

    def load(self):
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._data = {}
        else:
            self._data = {}

    def save(self):
        if self._batch_mode:
            self._dirty = True
            return
        self._flush()

    def _flush(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self._path)
        self._dirty = False

    def begin_batch(self):
        """Start batch mode: defer saves until end_batch()."""
        self._batch_mode = True
        self._dirty = False

    def end_batch(self):
        """End batch mode: flush to disk if any changes were made."""
        self._batch_mode = False
        if self._dirty:
            self._flush()

    def is_fresh(self, path: str, mtime: float, size: int) -> bool:
        entry = self._data.get(path)
        if not entry:
            return False
        if entry.get("size") != size:
            return False
        cached_mtime = entry.get("mtime", 0)
        return abs(cached_mtime - mtime) < 0.01

    def get(self, path: str) -> Optional[Dict[str, Any]]:
        return self._data.get(path)

    def update(
        self,
        path: str,
        mtime: float,
        size: int,
        last_line: int,
        has_refusal: bool,
        refusal_count: int,
        refusal_lines: List[int],
    ):
        self._data[path] = {
            "mtime": mtime,
            "size": size,
            "last_line": last_line,
            "has_refusal": has_refusal,
            "refusal_count": refusal_count,
            "refusal_lines": refusal_lines,
        }
        self.save()

    def update_incremental(
        self,
        path: str,
        mtime: float,
        size: int,
        new_last_line: int,
        new_refusal_lines: List[int],
    ):
        entry = self._data.get(path, {})
        old_refusals = entry.get("refusal_lines", [])
        merged = sorted(set(old_refusals + new_refusal_lines))
        self._data[path] = {
            "mtime": mtime,
            "size": size,
            "last_line": new_last_line,
            "has_refusal": len(merged) > 0,
            "refusal_count": len(merged),
            "refusal_lines": merged,
        }
        self.save()

    def update_after_patch(self, path: str, patched_lines: List[int]):
        entry = self._data.get(path)
        if not entry:
            return
        patched_set = set(patched_lines)
        remaining = [n for n in entry.get("refusal_lines", []) if n not in patched_set]
        entry["refusal_lines"] = remaining
        entry["refusal_count"] = len(remaining)
        entry["has_refusal"] = len(remaining) > 0
        try:
            stat = os.stat(path)
            entry["mtime"] = stat.st_mtime
            entry["size"] = stat.st_size
        except OSError:
            pass
        self.save()

    def update_after_delete(self, path: str, deleted_lines: List[int]):
        entry = self._data.get(path)
        if not entry:
            return
        deleted_set = set(deleted_lines)
        deleted_sorted = sorted(deleted_lines)
        new_refusals = []
        for n in entry.get("refusal_lines", []):
            if n in deleted_set:
                continue
            shift = sum(1 for d in deleted_sorted if d < n)
            new_refusals.append(n - shift)
        entry["refusal_lines"] = new_refusals
        entry["refusal_count"] = len(new_refusals)
        entry["has_refusal"] = len(new_refusals) > 0
        entry["last_line"] = max(0, entry.get("last_line", 0) - len(deleted_lines))
        try:
            stat = os.stat(path)
            entry["mtime"] = stat.st_mtime
            entry["size"] = stat.st_size
        except OSError:
            pass
        self.save()

    def invalidate(self, path: str):
        if path in self._data:
            del self._data[path]
            self.save()

    def prune_missing(self):
        """Remove entries for files that no longer exist."""
        to_remove = [
            path for path in self._data
            if not path.startswith("opencode:") and not os.path.exists(path)
        ]
        if to_remove:
            for path in to_remove:
                del self._data[path]
            self.save()

    def clear(self):
        self._data = {}
        self.save()
