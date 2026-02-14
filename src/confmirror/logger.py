# src/confmirror/logger.py

import logging
from pathlib import Path

from confmirror.config import APP_NAME, ConfigKeys

DEFAULT_LOG_MAX_LINES = 1000

# 定义跳过行为的日志颜色
SKIPPED_COLOR = '\033[90m'  # 灰色

class ColoredFormatter(logging.Formatter):
    """自定义颜色格式化器"""

    # ANSI颜色代码
    COLORS = {
        'DEBUG': '\033[36m',    # 青色
        'INFO': '\033[32m',     # 绿色
        'WARNING': '\033[33m',  # 黄色
        'ERROR': '\033[31m',    # 红色
        'CRITICAL': '\033[35m', # 紫色
        'RESET': '\033[0m'      # 重置
    }

    def format(self, record):
        # 为日志级别添加颜色
        level_color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        record.levelname = f"{level_color}{record.levelname}{self.COLORS['RESET']}"

        if record.msg.startswith("[跳过]"):
            record.msg = f"{SKIPPED_COLOR}{record.msg}{self.COLORS['RESET']}"

        # 调用父类的format方法
        formatted = super().format(record)
        return formatted


def rotate_log_file(log_file: Path, max_lines: int):
    """
    轮转日志文件，保留最近 max_lines 行

    Args:
        log_file: 日志文件路径
        max_lines: 最大保留行数
    """
    if not log_file.exists():
        return

    # 读取所有行
    with open(log_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # 如果行数超过限制，进行轮转
    if len(lines) > max_lines:
        # 保留最近的 max_lines 行
        kept_lines = lines[-max_lines:]

        # 写入保留的行
        with open(log_file, 'w', encoding='utf-8') as f:
            f.writelines(kept_lines)


def setup_logger(config: dict) -> logging.Logger:
    settings = config[ConfigKeys.SECTION_SETTINGS]
    log_dir = settings[ConfigKeys.LOG_DIR]
    config_name = settings[ConfigKeys.NAME]
    max_lines = settings.get(ConfigKeys.LOG_MAX_LINES, DEFAULT_LOG_MAX_LINES)
    log_path = Path(log_dir)
    if log_path.suffix:  # 如果有后缀，说明指定了文件名
        log_file = log_path.resolve()
        # 确保父目录存在
        log_file.parent.mkdir(parents=True, exist_ok=True)
    else:  # 没有后缀，说明只指定了目录
        log_path = log_path.resolve()
        log_path.mkdir(parents=True, exist_ok=True)
        if config_name:
            # 使用配置名称作为日志文件名
            log_file = log_path / f"{config_name}.log"
        else:
            # 使用默认日志文件名
            log_file = log_path / "log.log"

    # 启动时进行日志轮转检查
    rotate_log_file(log_file, max_lines)

    logger = logging.getLogger(APP_NAME)
    logger.setLevel(logging.DEBUG)

    # 清除旧 handler（避免重复）
    logger.handlers.clear()

    # 文件 handler - 不使用颜色，便于日志分析
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # 控制台 handler（INFO+）
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console_formatter = ColoredFormatter("[%(levelname)s] %(message)s")
    console.setFormatter(console_formatter)
    logger.addHandler(console)

    return logger