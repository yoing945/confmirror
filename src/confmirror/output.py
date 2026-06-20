"""CLI 输出格式化与 Agent 友好基础设施。

提供 JSON 输出、标准化退出码、以及终端日志抑制等功能，
使 ConfMirror 对 AI Agent 友好。
"""

import json
import logging
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Dict, Optional


class ExitCode:
    """标准化退出码"""

    SUCCESS = 0
    CONFIG_ERROR = 1
    PERMISSION_ERROR = 2
    PARTIAL_FAILURE = 3


def _serialize(obj: Any) -> Any:
    """将对象递归序列化为 JSON 可序列化的类型。"""
    if isinstance(obj, Path):
        return str(obj)
    if is_dataclass(obj) and not isinstance(obj, type):
        return _serialize(asdict(obj))
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize(v) for v in obj]
    return obj


def emit_json(data: Dict[str, Any]) -> None:
    """将结构化数据以 JSON 格式输出到 stdout。"""
    print(json.dumps(_serialize(data), ensure_ascii=False, indent=2))


def suppress_console_log() -> None:
    """抑制日志输出到终端（stdout/stderr），避免污染 JSON 输出。

    抑制所有 StreamHandler（无论输出到 stdout 还是 stderr），
    FileHandler 不受影响，日志仍然写入文件。
    """
    for logger_name in (
        "",
        "confmirror",
        "confmirror.backup",
        "confmirror.restore",
        "confmirror.cli",
        "confmirror.diff",
        "confmirror.gitops",
        "confmirror.init",
    ):
        logger = logging.getLogger(logger_name)
        for handler in logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                handler.setLevel(logging.CRITICAL + 1)
