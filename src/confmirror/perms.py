"""
权限查看功能模块
"""
import logging
import glob
from pathlib import Path
from typing import Dict, List, Optional

from confmirror.utils import (
    find_matching_module_with_path,
    get_src_path_from_backup_full_path,
    should_exclude_path,
)

from .config import Config, ModuleConfig, Settings
from .meta import read_meta
from .logger import ModuleLog

logger = logging.getLogger(__name__)
_log = ModuleLog("perms", logger)


def execute_perms(config: Config, target_module_name: Optional[str] = None, target_path: Optional[str] = None) -> None:
    """
    执行权限查看操作

    Args:
        config: 配置对象
        target_module_name: 指定要查看权限的模块名称
        target_path: 指定要查看权限的路径
    """
    if target_module_name:
        # 查看指定模块的权限信息
        perms_info = get_perms_for_module(target_module_name, config)
        display_perms_info(perms_info, config)
    elif target_path:
        module = find_matching_module_with_path(config.modules, Path(target_path))
        if not module:
            _log.error(f"路径 '{target_path}' 不属于任何模块")
            return
        # 获取排除路径模式和父路径
        all_exclude_patterns = module.exclude_paths or []
        parent_path = module.parent_path or ""
        if should_exclude_path(Path(target_path), all_exclude_patterns, parent_path):
            return
        perms_info = get_perms_for_path(config, target_path)
        display_perms_info(perms_info, config)


def get_perms_for_module(module_name: str, config: Config) -> List[Dict]:
    """
    获取指定模块的所有权限信息

    Args:
        module_name: 模块名称
        config: 配置对象

    Returns:
        包含文件路径和权限信息的列表
    """

    settings = config.settings
    backup_root = settings.backup_root

    # 找到指定模块
    target_module = next((m for m in config.modules if m.name == module_name), None)
    if not target_module:
        _log.error(f"配置中不存在模块 '{module_name}'")
        return []

    perms_info = []

    if target_module.script is not None:
        # 模块使用脚本备份，暂时不处理
        _log.error(f"脚本钩子模块 '{module_name}'不支持查看权限 ")
        return []

    elif target_module.include_paths is not None:
        parent_path_str = target_module.parent_path or ""
        backup_parent_path = str(backup_root / parent_path_str.lstrip('/'))

        for path_str in target_module.include_paths:
            full_path_pattern = str(Path(backup_parent_path) / path_str)
            matched_paths = glob.glob(full_path_pattern, recursive=True)
            temp_info = matched_paths_to_perms_info(matched_paths)
            perms_info.extend(temp_info)

    return perms_info


def get_perms_for_path(config: Config, target_path: str) -> List[Dict]:
    """
    获取指定路径的权限信息

    Args:
        config: 配置对象
        target_path: 目标路径

    Returns:
        包含文件路径和权限信息的列表
    """
    settings = config.settings
    backup_root = settings.backup_root

    # 将用户输入的路径转换为备份根目录下的路径模式
    backup_target_path_str = str(backup_root / target_path.lstrip('/'))
    # 使用 glob 查找所有匹配的文件
    matched_files = glob.glob(backup_target_path_str, recursive=True)
    return matched_paths_to_perms_info(matched_files)

def matched_paths_to_perms_info(matched_paths: List[str]) -> List[Dict]:
    """
    将匹配的路径转换为权限信息列表

    Args:
        matched_paths: 匹配的路径列表
        config: 配置字典

    Returns:
        包含文件路径和权限信息的列表
    """
    perms_info = []
    for path_str in matched_paths:
        # 跳过 .meta 文件本身，根据备份文件路径统一获取元数据
        if path_str.endswith('.meta'):
            continue
        path = Path(path_str)
        meta_data = read_meta(path)
        if meta_data:
            perms_info.append({
                'path': path_str,
                'meta': meta_data
            })
    return perms_info


def display_perms_info(perms_list: List[Dict], config: Config):
    """
    显示权限信息

    Args:
        perms_list: 权限信息列表
        config: 配置对象
    """
    if not perms_list:
        _log.warn("未找到任何权限信息, 请检查路径或是否备份")
        return

    for info in perms_list:
        
        path = info['path']
        source_path = get_src_path_from_backup_full_path(config, path)
        _log.info(f"路径: {source_path}")
        # 检查源文件是否存在并显示其权限
        if source_path.exists():
            source_stat = source_path.stat()
            source_mode = oct(source_stat.st_mode)[-3:]
            source_uid = source_stat.st_uid
            source_gid = source_stat.st_gid
            _log.info(f"  (src) 类型: {'dir' if source_path.is_dir() else 'file'}, 权限: {source_mode}, 所有者: {source_uid}:{source_gid}")
        else:
            _log.warn(f"源文件: {source_path} (不存在)")

        meta = info['meta']
        type_str = meta.get('type', 'unknown')
        mode = meta.get('mode', 'unknown')
        uid = meta.get('uid', 'unknown')
        gid = meta.get('gid', 'unknown')

        _log.info(f"  (bak) 类型: {type_str}, 权限: {mode}, 所有者: {uid}:{gid}")
