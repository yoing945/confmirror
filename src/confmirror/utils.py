
from pathlib import Path
from typing import Dict

from confmirror.config import ConfigKeys


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