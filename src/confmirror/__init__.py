"""
ConfMirror - 系统配置文件备份与还原工具

功能特性：
- 模块化备份与还原
- 元数据保留（权限、属主等）
- Git版本控制集成
- 增量备份支持
- 差异对比功能
- 多脚本语言支持
"""

__version__ = "1.0"
__author__ = "yoing945"

from .config import load_config, ConfigKeys
from .backup import execute_backup
from .restore import execute_restore
from .logger import setup_logger

__all__ = [
    'load_config',
    'ConfigKeys',
    'execute_backup',
    'execute_restore',
    'setup_logger',
]