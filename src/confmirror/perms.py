"""
权限查看功能模块
"""
from pathlib import Path
from typing import Dict, List, Optional

import click

from confmirror.utils import get_backup_path_str

from .config import APP_NAME, ConfigKeys, load_config
from .meta import read_meta


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
        click.echo(f"配置中不存在模块 '{module_name}'")
        return []

    perms_info = []

    if ConfigKeys.MOD_SCRIPT in target_module:
        # 模块使用脚本备份，暂时不处理
        click.echo(f"脚本钩子模块 '{module_name}'不支持查看权限 ")
        return []

    elif ConfigKeys.MOD_PATHS in target_module:
        parent_path = target_module.get(ConfigKeys.MOD_PARENT_PATH, "")

        for path_str in target_module[ConfigKeys.MOD_PATHS]:
            if parent_path:
                path = Path(parent_path) / path_str
            else:
                path = Path(path_str)

            # 查找对应的元数据文件
            perms_info.extend(_get_perms_for_path_recursive(backup_root / str(path).lstrip('/')))

    return perms_info


def get_perms_for_path(config: Dict, target_path: str, recursive: bool = False) -> List[Dict]:
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

    full_path = backup_root / target_path.lstrip('/')

    if recursive:
        return _get_perms_for_path_recursive(full_path)
    else:
        return _get_single_path_perms(full_path)


def _get_single_path_perms(path: Path) -> List[Dict]:
    """
    获取单个路径的权限信息

    Args:
        path: 路径对象

    Returns:
        包含文件路径和权限信息的列表
    """
    perms_info = []

    # 检查文件或目录的元数据
    meta_data = read_meta(path)
    if meta_data:
        perms_info.append({
            'path': str(path),
            'meta': meta_data
        })

    return perms_info


def _get_perms_for_path_recursive(path: Path) -> List[Dict]:
    """
    递归获取路径及其子文件的权限信息

    Args:
        path: 路径对象

    Returns:
        包含文件路径和权限信息的列表
    """
    perms_info = []

    def scan_path(current_path: Path):
        # 检查当前路径的元数据
        meta_data = read_meta(current_path)
        if meta_data:
            perms_info.append({
                'path': str(current_path),
                'meta': meta_data
            })

        # 如果是目录，递归扫描子文件
        if current_path.is_dir():
            for item in current_path.iterdir():
                scan_path(item)

    scan_path(path)
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
        click.echo()
            