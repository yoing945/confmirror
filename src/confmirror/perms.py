"""
权限查看功能模块
"""
from pathlib import Path
import glob
from typing import Dict, List, Optional

import click

from confmirror.utils import find_matching_module_with_path, get_backup_path_str, should_exclude_path

from .config import ConfigKeys
from .meta import read_meta


def execute_perms(config: Dict, logger, target_module_name: Optional[str] = None, target_path: Optional[str] = None) -> None:
    """
    执行权限查看操作

    Args:
        config: 配置字典
        logger: 日志记录器
        target_module_name: 指定要查看权限的模块名称
        target_paths: 指定要查看权限的路径列表
    """
    if target_module_name:
        # 查看指定模块的权限信息
        perms_info = get_perms_for_module(target_module_name, config)
        display_perms_info(perms_info, config)
    elif target_path:
        module = find_matching_module_with_path(config.get(ConfigKeys.SECTION_MODULES, []), Path(target_path))
        if not module:
            logger.error(f"❌ 路径 '{target_path}' 不属于任何模块")
            return
        # 获取排除路径模式和父路径
        all_exclude_patterns = module.get(ConfigKeys.MOD_EXCLUDE_PATHS, [])
        parent_path = module.get(ConfigKeys.MOD_PARENT_PATH, "")
        if should_exclude_path(Path(target_path), all_exclude_patterns, parent_path):
            return
        perms_info = get_perms_for_path(config, target_path)
        display_perms_info(perms_info, config)


def get_perms_for_module(module_name: str, config: Dict) -> List[Dict]:
    """
    获取指定模块的所有权限信息

    Args:
        module_name: 模块名称
        config: 配置字典

    Returns:
        包含文件路径和权限信息的列表
    """

    settings = config[ConfigKeys.SECTION_SETTINGS]
    backup_root = Path(settings[ConfigKeys.BACKUP_ROOT])

    # 找到指定模块
    modules = config.get(ConfigKeys.SECTION_MODULES, [])
    target_module = next((m for m in modules if m[ConfigKeys.MOD_NAME] == module_name), None)
    if not target_module:
        click.echo(f"❌ 配置中不存在模块 '{module_name}'")
        return []

    perms_info = []

    if ConfigKeys.MOD_SCRIPT in target_module:
        # 模块使用脚本备份，暂时不处理
        click.echo(f"❌ 脚本钩子模块 '{module_name}'不支持查看权限 ")
        return []

    elif ConfigKeys.MOD_INCLUDE_PATHS in target_module:
        parent_path_str = target_module.get(ConfigKeys.MOD_PARENT_PATH, "")
        backup_parent_path = str(backup_root / parent_path_str.lstrip('/'))

        for path_str in target_module[ConfigKeys.MOD_INCLUDE_PATHS]:
            full_path_pattern = str(Path(backup_parent_path) / path_str)
            matched_paths = glob.glob(full_path_pattern, recursive=True)
            temp_info = matched_paths_to_perms_info(matched_paths)
            perms_info.extend(temp_info)

    return perms_info


def get_perms_for_path(config: Dict, target_path: str) -> List[Dict]:
    """
    获取指定路径的权限信息

    Args:
        config: 配置字典
        target_path: 目标路径
        recursive: 是否递归查找

    Returns:
        包含文件路径和权限信息的列表
    """
    settings = config[ConfigKeys.SECTION_SETTINGS]
    backup_root = Path(settings[ConfigKeys.BACKUP_ROOT])

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


def display_perms_info(perms_list: List[Dict], config: Dict):
    """
    显示权限信息

    Args:
        perms_list: 权限信息列表
        config: 配置字典
    """
    if not perms_list:
        click.echo("未找到任何权限信息, 请检查路径或是否备份")
        return

    for info in perms_list:
        path = info['path']
        meta = info['meta']

        display_path = get_backup_path_str(config, path)
        type_str = meta.get('type', 'unknown')
        mode = meta.get('mode', 'unknown')
        uid = meta.get('uid', 'unknown')
        gid = meta.get('gid', 'unknown')

        click.echo(f"{display_path}")
        click.echo(f"  Type: {type_str}, Mode: {mode}, Owner: {uid}:{gid}")
