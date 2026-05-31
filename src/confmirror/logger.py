# src/confmirror/logger.py

import logging
from collections import deque
from pathlib import Path
from typing import Optional

APP_NAME = "confmirror"
DEFAULT_LOG_MAX_LINES = 1000
SKIPPED_COLOR = '\033[90m'  # 灰色


class ModuleLog:
    """模块级日志工具

    默认绑定模块 category，同时支持显式覆盖。
    统一格式: [category:status] description
    示例: [backup:ok] → /etc/ssh/sshd_config
    """

    def __init__(self, default_category: str, logger: logging.Logger):
        self._default = default_category
        self._logger = logger
        # 显式设置级别，避免传播链上的不确定性
        if logger.level == logging.NOTSET:
            logger.setLevel(logging.DEBUG)

    def _fmt(self, msg: str, category: Optional[str] = None, status: Optional[str] = None) -> str:
        cat = category or self._default
        if status:
            return f"[{cat}:{status}] {msg}"
        return f"[{cat}] {msg}"

    def ok(self, msg: str, category: Optional[str] = None):
        self._logger.info(self._fmt(msg, category))

    def skip(self, msg: str, category: Optional[str] = None):
        self._logger.info(self._fmt(msg, category, status="skip"))

    def info(self, msg: str, category: Optional[str] = None):
        self._logger.info(self._fmt(msg, category))

    def warn(self, msg: str, category: Optional[str] = None):
        self._logger.warning(self._fmt(msg, category))

    def error(self, msg: str, category: Optional[str] = None):
        self._logger.error(self._fmt(msg, category))


class ColoredFormatter(logging.Formatter):
    """自定义颜色格式化器"""

    COLORS = {
        'DEBUG': '\033[36m',    # 青色
        'INFO': '\033[32m',     # 绿色
        'WARNING': '\033[33m',  # 黄色
        'ERROR': '\033[31m',    # 红色
        'CRITICAL': '\033[35m', # 紫色
        'RESET': '\033[0m'      # 重置
    }

    def format(self, record):
        original_levelname = record.levelname
        original_msg = record.msg

        level_color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        record.levelname = f"{level_color}{record.levelname}{self.COLORS['RESET']}"

        # 检测 skip 消息（统一格式 :skip]）
        if ":skip]" in record.msg:
            record.msg = f"{SKIPPED_COLOR}{record.msg}{self.COLORS['RESET']}"

        formatted = super().format(record)

        record.levelname = original_levelname
        record.msg = original_msg
        return formatted


def rotate_log_file(log_file: Path, max_lines: int):
    """轮转日志文件，保留最近 max_lines 行"""
    if not log_file.exists():
        return

    with open(log_file, 'r', encoding='utf-8') as f:
        kept = deque(f, maxlen=max_lines)

    with open(log_file, 'w', encoding='utf-8') as f:
        f.writelines(kept)


def resolve_log_path(log_dir: str | Path, config_name: str = "") -> Path:
    """根据配置解析日志文件路径

    Args:
        log_dir: 日志目录或日志文件路径
        config_name: 配置名称，用于生成默认日志文件名

    Returns:
        解析后的日志文件路径
    """
    log_path = Path(log_dir)
    if log_path.suffix:
        log_file = log_path.resolve()
        log_file.parent.mkdir(parents=True, exist_ok=True)
        return log_file
    else:
        log_path = log_path.resolve()
        log_path.mkdir(parents=True, exist_ok=True)
        return log_path / f"{config_name}.log" if config_name else log_path / "log.log"


def setup_logger(log_file: Path, max_lines: int = DEFAULT_LOG_MAX_LINES) -> logging.Logger:
    """配置并返回应用日志记录器

    首次调用会轮转日志并配置 handler；重复调用直接返回已配置的 logger，
    避免 handler 被重复添加或清除。
    """
    logger = logging.getLogger(APP_NAME)

    # 已配置则直接返回，避免重复添加 handler
    if logger.handlers:
        return logger

    rotate_log_file(log_file, max_lines)
    logger.setLevel(logging.DEBUG)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console_formatter = ColoredFormatter("[%(levelname)s] %(message)s")
    console.setFormatter(console_formatter)
    logger.addHandler(console)

    return logger
