# src/confmirror/logger.py

import logging
from pathlib import Path

from confmirror.config import APP_NAME


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

        # 为消息添加颜色（根据级别）
        msg_color = self.COLORS.get(record.levelname
                                    .replace('\033[31mERROR\033[0m', 'ERROR')
                                    .replace('\033[33mWARNING\033[0m', 'WARNING')
                                    #.replace('\033[32mINFO\033[0m', 'INFO')
                                    #.replace('\033[36mDEBUG\033[0m', 'DEBUG')
                                    .replace('\033[35mCRITICAL\033[0m', 'CRITICAL'), self.COLORS['RESET'])
        original_msg = record.msg
        record.msg = f"{msg_color}{original_msg}{self.COLORS['RESET']}"

        # 调用父类的format方法
        formatted = super().format(record)

        # 恢复原始消息
        record.msg = original_msg

        return formatted


def setup_logger(log_dir: Path, config_name: str) -> logging.Logger:
    # 检查 log_dir 是否包含文件名还是只是目录
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