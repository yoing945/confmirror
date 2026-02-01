
import fnmatch
from pathlib import Path
import subprocess
from typing import Dict, Optional

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


def find_matching_module_with_path(modules: list, path: Path) -> Optional[dict]:
    """
    查找包含指定路径的模块

    Args:
        modules: 模块配置列表
        path: 要查找的路径

    Returns:
        包含该路径的模块配置字典，如果未找到则返回None
    """
    for module in modules:
        if ConfigKeys.MOD_INCLUDE_PATHS in module:
            parent_path = module.get(ConfigKeys.MOD_PARENT_PATH, "")
            for path_str in module[ConfigKeys.MOD_INCLUDE_PATHS]:
                if parent_path:
                    module_path = Path(parent_path) / path_str
                else:
                    module_path = Path(path_str)
                if path.is_relative_to(module_path):
                    return module
    return None


def run_shell_script(script_rel: str, settings: dict, logger, action: str) -> bool:
    """
    执行shell脚本

    Args:
        script_rel: 脚本相对路径
        settings: 配置设置字典
        logger: 日志记录器

    Returns:
        bool: 脚本执行成功返回True，否则返回False
    """
    script_hooks_dir = Path(settings[ConfigKeys.SCRIPT_HOOKS_DIR])
    script = script_hooks_dir / script_rel
    if not script.exists():
        logger.error(f"脚本不存在 {script}")
        return False

    logger.info(f"执行脚本: {script}")
    try:
        # 不捕获输出，直接显示在终端
        result = subprocess.run(
            ['bash', str(script), action],
            cwd=script.parent,  # 使用脚本所在目录作为工作目录
            check=True
        )
        logger.info(f"脚本执行完成")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"脚本执行异常: {e}")
        return False
    except Exception as e:
        logger.error(f"脚本执行异常: {str(e)}")
        return False
