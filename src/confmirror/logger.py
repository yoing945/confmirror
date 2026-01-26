# src/confmirror/logger.py

import logging
from pathlib import Path


def setup_logger(log_dir: Path, config_name: str = None) -> logging.Logger:
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

    logger = logging.getLogger("confmirror")
    logger.setLevel(logging.DEBUG)

    # 清除旧 handler（避免重复）
    logger.handlers.clear()

    # 文件 handler
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
    console.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(console)

    return logger