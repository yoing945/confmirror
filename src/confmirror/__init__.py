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
    __version__ = "1.1.0"

_LAZY_IMPORTS = {
    "load_config": (".config", "load_config"),
    "Config": (".config", "Config"),
    "Settings": (".config", "Settings"),
    "ModuleConfig": (".config", "ModuleConfig"),
    "execute_backup": (".backup", "execute_backup"),
    "execute_restore": (".restore", "execute_restore"),
    "setup_logger": (".logger", "setup_logger"),
}

__all__ = list(_LAZY_IMPORTS.keys())


def __getattr__(name):
    """延迟导入，减少 import confmirror 时的启动开销"""
    if name in _LAZY_IMPORTS:
        import importlib

        module_path, attr_name = _LAZY_IMPORTS[name]
        module = importlib.import_module(module_path, package=__package__)
        return getattr(module, attr_name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    """确保 dir(confmirror) 和 IDE 补全能看到延迟导入的符号"""
    return list(__all__)
