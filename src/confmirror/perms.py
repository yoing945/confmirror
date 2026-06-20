"""
权限查看功能模块
"""

import glob
import logging
from pathlib import Path
from typing import Dict, List, Optional

from confmirror.utils import (
    find_matching_module_with_path,
    get_src_path_from_backup_full_path,
    should_exclude_path,
)

from .config import Config, ModuleConfig, Settings
from .logger import ModuleLog
from .meta import read_meta

logger = logging.getLogger(__name__)
_log = ModuleLog("perms", logger)


def get_perms_data(
    config: Config,
    target_module_name: Optional[str] = None,
    target_path: Optional[str] = None,
) -> List[Dict]:
    """
    获取权限结构化数据（查询与展示分离后的核心接口）。

    返回每个条目的完整信息，包括 backup 元数据和源路径当前状态。
    """
    if target_module_name:
        entries = get_perms_for_module(target_module_name, config)
    elif target_path:
        module = find_matching_module_with_path(config.modules, Path(target_path))
        if not module:
            _log.error(f"路径 '{target_path}' 不属于任何模块")
            return []
        all_exclude_patterns = module.exclude_paths or []
        parent_path = module.base_path or ""
        if should_exclude_path(
            Path(target_path),
            exclude_patterns=all_exclude_patterns,
            parent_path=parent_path,
        ):
            return []
        entries = get_perms_for_path(config, target_path)
    else:
        entries = []

    # 补充源路径当前状态
    for entry in entries:
        backup_path = Path(entry["path"])
        source_path = get_src_path_from_backup_full_path(config, str(backup_path))
        entry["source_path"] = str(source_path)
        if source_path.exists():
            source_stat = source_path.stat()
            entry["source"] = {
                "type": "dir" if source_path.is_dir() else "file",
                "mode": oct(source_stat.st_mode)[-3:],
                "uid": source_stat.st_uid,
                "gid": source_stat.st_gid,
            }
        else:
            entry["source"] = None

    return entries


def execute_perms(
    config: Config,
    target_module_name: Optional[str] = None,
    target_path: Optional[str] = None,
) -> List[Dict]:
    """
    执行权限查看操作（兼容接口：获取数据并直接显示）。

    Args:
        config: 配置对象
        target_module_name: 指定要查看权限的模块名称
        target_path: 指定要查看权限的路径

    Returns:
        权限结构化数据列表
    """
    entries = get_perms_data(config, target_module_name, target_path)
    display_perms_info(entries)
    return entries


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

    if target_module.hook is not None:
        # 模块使用脚本备份，暂时不处理
        _log.error(f"脚本钩子模块 '{module_name}'不支持查看权限 ")
        return []

    elif target_module.paths is not None:
        parent_path_str = target_module.base_path or ""
        backup_parent_path = str(backup_root / parent_path_str.lstrip("/"))

        for path_str in target_module.paths:
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
    backup_target_path_str = str(backup_root / target_path.lstrip("/"))
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
        if path_str.endswith(".meta"):
            continue
        path = Path(path_str)
        meta_data = read_meta(path)
        if meta_data:
            perms_info.append({"path": path_str, "meta": meta_data})
    return perms_info


def display_perms_info(perms_list: List[Dict]) -> None:
    """
    显示权限信息（纯展示，不查询文件系统）。

    Args:
        perms_list: 权限信息列表，每个条目应包含 source_path / source / meta
    """
    if not perms_list:
        _log.warn("未找到任何权限信息, 请检查路径或是否备份")
        return

    for entry in perms_list:
        path = entry.get("source_path", entry["path"])
        _log.info(f"路径: {path}")

        source = entry.get("source")
        if source:
            _log.info(
                f"  (src) 类型: {source['type']}, 权限: {source['mode']}, 所有者: {source['uid']}:{source['gid']}"
            )
        else:
            _log.warn(f"源文件: {path} (不存在)")

        meta = entry["meta"]
        _log.info(
            f"  (bak) 类型: {meta.get('type', 'unknown')}, 权限: {meta.get('mode', 'unknown')}, 所有者: {meta.get('uid', 'unknown')}:{meta.get('gid', 'unknown')}"
        )
