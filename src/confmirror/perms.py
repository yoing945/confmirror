"""
权限查看功能模块
"""
import logging
from pathlib import Path
from typing import Dict, List, Optional

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
    logger = logging.getLogger(APP_NAME)
    if not target_module:
        print(f"配置中不存在模块 '{module_name}'")
        return []

    perms_info = []

    if ConfigKeys.MOD_SCRIPT in target_module:
        # 模块使用脚本备份，暂时不处理
        logger.warning(f"脚本钩子模块 '{module_name}'不支持查看权限 ")
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
    else:
        print(f"No metadata found for: {path}")

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


def display_perms_info(perms_list: List[Dict], config: Dict, show_paths_only: bool = False):
    """
    显示权限信息

    Args:
        perms_list: 权限信息列表
        config: 配置字典
        show_paths_only: 是否只显示路径（不显示详细权限信息）
    """
    if not perms_list:
        print("No permissions information found.")
        return

    # 检查配置是否加载成功
    if not config:
        print("Configuration could not be loaded. Cannot display permissions properly.")
        return

    # 从配置中获取备份根目录
    settings = config[ConfigKeys.SECTION_SETTINGS]
    backup_root = settings[ConfigKeys.BACKUP_ROOT]

    for info in perms_list:
        path = info['path']
        meta = info['meta']

        # 将绝对路径转换为相对备份路径
        # 将path转换为相对于备份根目录的路径
        try:
            rel_path = Path(path).relative_to(backup_root)
            display_path = f"(bak) /{rel_path}"
        except ValueError:
            # 如果path不在backup_root下，则使用原始路径
            display_path = f"(bak) {path}"

        if show_paths_only:
            print(display_path)
        else:
            type_str = meta.get('type', 'unknown')
            mode = meta.get('mode', 'unknown')
            uid = meta.get('uid', 'unknown')
            gid = meta.get('gid', 'unknown')

            print(f"{display_path}")
            print(f"  Type: {type_str}, Mode: {mode}, Owner: {uid}:{gid}")
            print()