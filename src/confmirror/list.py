"""处理列出模块的功能"""

import logging
from typing import Dict

from .config import Config, ModuleConfig
from .logger import ModuleLog

logger = logging.getLogger(__name__)
_log = ModuleLog("list", logger)


def execute_list(config: Config, module_name=None, detail=False):
    """
    列出所有可用模块

    Args:
        config: 配置对象
        module_name: 指定要列出的模块名称，如果为None则列出所有模块
        detail: 是否输出详细信息
    """
    modules = config.modules

    if not modules:
        _log.warn("配置中没有定义任何模块")
        return

    if module_name:
        # 查找指定模块
        target_module = next((m for m in modules if m.name == module_name), None)

        if not target_module:
            _log.error(f"未找到模块: {module_name}")
            return

        if detail:
            _log.info("-" * 50)
            _print_module_details(target_module)
        else:
            _log.info(f"模块: {module_name}")
    else:
        # 列出所有模块
        _log.info(f"共 {len(modules)} 个模块:")
        if detail:
            _log.info("-" * 50)
            for module in modules:
                _print_module_details(module)
        else:
            for i, module in enumerate(modules, 1):
                _log.info(f"  - {module.name}")


def _print_module_details(module: ModuleConfig):
    """打印模块详细信息"""
    _log.info(f"模块: {module.name}")

    # 检查是否有脚本类型的模块
    if module.script is not None:
        _log.info(f"  类型: 脚本模块")
        _log.info(f"  脚本路径: {module.script}")
    else:
        # 输出路径相关配置
        if module.parent_path is not None:
            _log.info(f"  父目录: {module.parent_path}")

        if module.include_paths is not None:
            _log.info(f"  包含路径: {module.include_paths}")

        if module.exclude_paths is not None:
            _log.info(f"  排除路径: {module.exclude_paths}")

    _log.info("-" * 50)
