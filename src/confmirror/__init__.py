"""
ConfMirror - 系统配置文件备份与还原工具

功能特性：
- 模块化备份与还原
- 元数据保留（权限、属主等）
- 增量备份/还原
- 差异对比功能
- 多脚本语言支持
"""

try:
    from importlib.metadata import version
    __version__ = version("confmirror")
except ImportError:
    __version__ = "0.1.0"

from .backup import execute_backup
from .config import ConfigKeys, load_config
from .logger import setup_logger
from .restore import execute_restore

__all__ = [
    'load_config',
    'ConfigKeys',
    'execute_backup',
    'execute_restore',
    'setup_logger',
]