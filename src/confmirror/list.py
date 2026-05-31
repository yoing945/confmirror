"""处理列出模块的功能"""

import logging
from typing import Any, Dict, List, Optional

from .config import Config, ModuleConfig
from .logger import ModuleLog

logger = logging.getLogger(__name__)
_log = ModuleLog("list", logger)


def _module_to_dict(module: ModuleConfig) -> Dict[str, Any]:
    """将模块配置转换为结构化字典"""
    return {
        "name": module.name,
        "type": "script" if module.script is not None else "path",
        "script": module.script,
        "script_lang": module.script_lang,
        "parent_path": module.parent_path,
        "include_paths": module.include_paths,
        "exclude_paths": module.exclude_paths,
    }


def get_modules_data(config: Config, module_name: Optional[str] = None,
                     detail: bool = False) -> Optional[List[Dict[str, Any]]]:
    """
    获取模块列表结构化数据（查询与展示分离后的核心接口）。

    Returns:
        模块数据列表；若指定了 module_name 但未找到，返回 None
    """
    modules = config.modules

    if not modules:
        return []

    if module_name:
        target_module = next((m for m in modules if m.name == module_name), None)
        if not target_module:
            return None
        return [_module_to_dict(target_module)]

    return [_module_to_dict(m) for m in modules]


def display_modules(entries: List[Dict[str, Any]], detail: bool = False) -> None:
    """显示模块信息（纯展示，不访问配置对象）"""
    if not entries:
        _log.warn("配置中没有定义任何模块")
        return

    if len(entries) == 1 and detail:
        _log.info("-" * 50)
        _print_module_detail(entries[0])
    elif len(entries) == 1:
        _log.info(f"模块: {entries[0]['name']}")
    else:
        _log.info(f"共 {len(entries)} 个模块:")
        if detail:
            _log.info("-" * 50)
            for entry in entries:
                _print_module_detail(entry)
        else:
            for i, entry in enumerate(entries, 1):
                _log.info(f"  - {entry['name']}")


def _print_module_detail(entry: Dict[str, Any]) -> None:
    """打印单个模块详细信息"""
    _log.info(f"模块: {entry['name']}")

    if entry['type'] == 'script':
        _log.info(f"  类型: 脚本模块")
        _log.info(f"  脚本路径: {entry['script']}")
    else:
        if entry.get('parent_path') is not None:
            _log.info(f"  父目录: {entry['parent_path']}")
        if entry.get('include_paths') is not None:
            _log.info(f"  包含路径: {entry['include_paths']}")
        if entry.get('exclude_paths') is not None:
            _log.info(f"  排除路径: {entry['exclude_paths']}")

    _log.info("-" * 50)


def execute_list(config: Config, module_name: Optional[str] = None,
                 detail: bool = False) -> Optional[List[Dict[str, Any]]]:
    """
    列出所有可用模块（兼容接口：获取数据并直接显示）。

    Returns:
        模块数据列表；若指定了 module_name 但未找到，返回 None
    """
    entries = get_modules_data(config, module_name, detail)
    if entries is None:
        _log.error(f"未找到模块: {module_name}")
        return None
    display_modules(entries, detail)
    return entries
