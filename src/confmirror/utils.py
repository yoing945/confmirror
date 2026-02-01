
import fnmatch
from pathlib import Path
from typing import Dict

from confmirror.config import ConfigKeys


def should_exclude_path(path: Path, exclude_patterns: list, parent_path: str = "") -> bool:
    """
    检查路径是否应该被排除

    Args:
        path: 要检查的路径
        exclude_patterns: 排除模式列表
        parent_path: 父路径，用于相对于 parent_path 的排除模式

    Returns:
        bool: 如果应该排除则返回True，否则返回False
    """
    path_str = str(path)

    for pattern in exclude_patterns:
        # 如果设置了 parent_path，将排除模式视为相对于 parent_path
        if parent_path:
            # 构造相对于 parent_path 的完整模式
            relative_pattern = str(Path(parent_path) / pattern)
            # 检查路径是否匹配相对于 parent_path 的模式
            if (fnmatch.fnmatch(path_str, relative_pattern) or
                path.match(relative_pattern)):
                return True
        else:
            # 如果没有 parent_path，只检查原始排除模式
            if (fnmatch.fnmatch(path_str, pattern) or
                fnmatch.fnmatch(path.name, pattern) or
                path.match(pattern)):
                return True

    return False


def get_backup_path_str(config:Dict, full_path)->str:
    """
    获取用于显示的备份文件路径字符串

    Args:
        config: 配置文件
        full_path: 备份文件的完整路径
    """
    settings = config[ConfigKeys.SECTION_SETTINGS]
    backup_root = settings[ConfigKeys.BACKUP_ROOT]
    # 将绝对路径转换为相对备份路径
    # 将path转换为相对于备份根目录的路径
    try:
        rel_path = Path(full_path).relative_to(backup_root)
        display_path = f"(bak) /{rel_path}"
    except ValueError:
        # 如果path不在backup_root下，则使用原始路径
        display_path = full_path
    return display_path