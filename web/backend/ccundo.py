"""ccundo CLI 集成: 调用 ccundo 命令查询/执行 undo/redo。

ccundo 是独立的 npm 工具，做 Claude Code 文件操作的级联撤销。
官方仓库: https://github.com/RonitSachdev/ccundo

本模块提供:
- is_available(): 检测 ccundo 是否可用
- list_operations(cwd, session_id): 解析 ccundo list 输出 -> {op_id: 'active'|'undone'}
- run_action(cwd, op_id, action, session_id): 执行 undo/redo
"""
from __future__ import annotations

import re
import shutil
import subprocess
from typing import Dict, Optional


_CCUNDO_CMD: Optional[list] = None  # 缓存完整命令前缀


def _find_ccundo() -> Optional[list]:
    """返回调用 ccundo 的命令前缀, 找不到返回 None"""
    global _CCUNDO_CMD
    if _CCUNDO_CMD is not None:
        return list(_CCUNDO_CMD) if _CCUNDO_CMD else None
    # 优先全局 ccundo
    path = shutil.which("ccundo")
    if path:
        _CCUNDO_CMD = [path]
        return list(_CCUNDO_CMD)
    # fallback: npx ccundo (需要 node + npm)
    npx = shutil.which("npx")
    if npx:
        _CCUNDO_CMD = [npx, "ccundo"]
        return list(_CCUNDO_CMD)
    _CCUNDO_CMD = []
    return None


def is_available() -> bool:
    return _find_ccundo() is not None


# ccundo list 输出格式:
# 1. [ACTIVE] bash_command - 11d ago
#    ID: toolu_bdrk_xxx
#    Command: ...
_LINE_RX = re.compile(
    r"^\s*\d+\.\s+\[(ACTIVE|UNDONE)\]\s+(\w+)\s+-\s+",
    re.MULTILINE,
)
_ID_RX = re.compile(r"^\s+ID:\s+(\S+)", re.MULTILINE)


def list_operations(cwd: str, session_id: Optional[str] = None) -> Dict[str, str]:
    """返回 {op_id: 'active' | 'undone'} 映射."""
    cmd = _find_ccundo()
    if cmd is None:
        return {}
    args = list(cmd) + ["list", "--all"]
    if session_id:
        args += ["--session", session_id]
    try:
        r = subprocess.run(
            args, cwd=cwd, capture_output=True, text=True, timeout=15
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return {}
    if r.returncode != 0:
        return {}

    out = r.stdout
    # 按行扫描: 找 [STATE] xxx 后紧跟 ID: yyy
    state_map: Dict[str, str] = {}
    lines = out.splitlines()
    pending_state: Optional[str] = None
    for ln in lines:
        m = _LINE_RX.match(ln)
        if m:
            pending_state = m.group(1).lower()
            continue
        if pending_state:
            mid = _ID_RX.match(ln)
            if mid:
                state_map[mid.group(1)] = pending_state
                pending_state = None
    return state_map


def run_action(
    cwd: str,
    op_id: str,
    action: str,
    session_id: Optional[str] = None,
) -> dict:
    """执行 undo 或 redo。返回 {ok, stdout, stderr}."""
    if action not in ("undo", "redo"):
        return {"ok": False, "stdout": "", "stderr": f"invalid action: {action}"}
    cmd = _find_ccundo()
    if cmd is None:
        return {"ok": False, "stdout": "", "stderr": "ccundo not installed"}
    args = list(cmd) + [action, op_id, "--yes"]
    if session_id:
        args += ["--session", session_id]
    try:
        r = subprocess.run(
            args, cwd=cwd, capture_output=True, text=True, timeout=60
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return {"ok": False, "stdout": "", "stderr": str(e)}
    return {
        "ok": r.returncode == 0,
        "stdout": r.stdout,
        "stderr": r.stderr,
    }
