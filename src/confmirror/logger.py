# src/confmirror/logger.py

import logging
from pathlib import Path


def setup_logger(log_dir: Path) -> logging.Logger:
    log_dir = Path(log_dir).resolve()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "log.log"  # ← 固定文件名

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