import logging
import fnmatch
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

import pathspec

from confmirror.config import Config, ModuleConfig, Settings
from confmirror.logger import ModuleLog

logger = logging.getLogger(__name__)
_log = ModuleLog("script", logger)


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
    if not exclude_patterns:
        return False
    
    # 使用 pathspec 创建一个 gitignore 风格的路径规范
    spec = pathspec.GitIgnoreSpec.from_lines(exclude_patterns)
    if spec is None:
        return False
    
    # 获取相对于 parent_path 的路径
    if parent_path:
        try:
            rel_path = path.relative_to(parent_path)
            path_str = str(rel_path.as_posix())  # 使用 posix 格式以匹配 git 规范
        except ValueError:
            # 如果路径不在 parent_path 下，则使用原始路径
            path_str = str(path.as_posix())
    else:
        path_str = str(path.as_posix())
    
    # 使用 pathspec 检查路径是否匹配排除模式
    return spec.match_file(path_str)


def get_src_path_from_backup_full_path(config: Config, full_path_str: str) -> Path:
    """
    通过备份文件的完整路径获取对应的源文件路径字符串

    Args:
        config: 配置对象
        full_path_str: 备份文件的完整路径
    """
    backup_root = config.settings.backup_root
    # 将绝对路径转换为相对备份路径
    # 将path转换为相对于备份根目录的路径
    try:
        src_path = Path('/') / Path(full_path_str).relative_to(backup_root)
    except ValueError:
        # 如果path不在backup_root下，则使用原始路径
        src_path = Path(full_path_str)
    return src_path


def find_matching_module_with_path(modules: List[ModuleConfig], path: Path) -> Optional[ModuleConfig]:
    """
    查找包含指定路径的模块

    Args:
        modules: 模块配置列表
        path: 要查找的路径

    Returns:
        包含该路径的模块配置对象，如果未找到则返回None
    """
    for module in modules:
        if module.include_paths is not None:
            parent_path = module.parent_path or ""
            for path_str in module.include_paths:
                if parent_path:
                    module_path = Path(parent_path) / path_str
                else:
                    module_path = Path(path_str)
                if path.is_relative_to(module_path):
                    return module
    return None


def run_shell_script(script_rel: str, settings: Settings, action: str) -> bool:
    """
    执行shell脚本（向后兼容）

    Args:
        script_rel: 脚本相对路径
        settings: 配置设置对象
        action: 操作类型（backup/restore）

    Returns:
        bool: 脚本执行成功返回True，否则返回False
    """
    return run_script(script_rel, settings, action, script_lang="bash")


def run_script(script_rel: str, settings: Settings, action: str, script_lang: str = "bash") -> bool:
    """
    执行脚本，支持多种脚本语言

    Args:
        script_rel: 脚本相对路径
        settings: 配置设置对象
        action: 操作类型（backup/restore）
        script_lang: 脚本语言（bash/python/python3/ruby/node等）

    Returns:
        bool: 脚本执行成功返回True，否则返回False
    """
    script_hooks_dir = settings.script_hooks_dir
    script = script_hooks_dir / script_rel
    if not script.exists():
        _log.error(f"脚本不存在 {script}")
        return False

    # 根据脚本语言确定解释器和执行方式
    interpreters = {
        "bash": ["bash"],
        "sh": ["sh"],
        "python": [sys.executable],  # 使用当前Python解释器
        "python3": ["python3"],
        "python2": ["python2"],
        "ruby": ["ruby"],
        "node": ["node"],
        "nodejs": ["node"],
        "perl": ["perl"],
        "php": ["php"],
    }

    # 如果script_lang是路径（如/usr/bin/python3），直接使用
    if Path(script_lang).exists() or "/" in script_lang:
        cmd = [script_lang]
    elif script_lang.lower() in interpreters:
        cmd = interpreters[script_lang.lower()]
    else:
        # 尝试作为命令直接使用
        cmd = [script_lang]

    cmd.append(str(script))
    cmd.append(action)

    _log.info(f"执行脚本 [{script_lang}]: {script}")
    try:
        result = subprocess.run(
            cmd,
            # 指定脚本所在目录为工作目录
            cwd=script.parent,
            check=True,
            # 直接输出到终端
            capture_output=False,  
            text=True
        )
        _log.info("脚本执行完成")
        return True
    except subprocess.CalledProcessError as e:
        _log.error(f"脚本执行异常，返回码: {e.returncode}")
        return False
    except FileNotFoundError:
        _log.error(f"找不到解释器 '{script_lang}'，请确保已安装")
        return False
    except Exception as e:
        _log.error(f"脚本执行异常: {str(e)}")
        return False


def get_script_shebang(script_path: Path) -> Optional[str]:
    """
    读取脚本的shebang行来自动检测脚本语言

    Args:
        script_path: 脚本路径

    Returns:
        str: 检测到的语言或None
    """
    try:
        with open(script_path, 'r', encoding='utf-8', errors='ignore') as f:
            first_line = f.readline().strip()
            if first_line.startswith('#!'):
                # 解析shebang
                shebang = first_line[2:].strip()
                # 提取解释器名称
                if 'python3' in shebang:
                    return 'python3'
                elif 'python' in shebang:
                    return 'python'
                elif 'bash' in shebang:
                    return 'bash'
                elif 'sh' in shebang:
                    return 'sh'
                elif 'ruby' in shebang:
                    return 'ruby'
                elif 'node' in shebang:
                    return 'node'
                elif 'perl' in shebang:
                    return 'perl'
                else:
                    # 返回完整路径
                    return shebang.split()[-1]
    except (OSError, UnicodeDecodeError):
        pass
    return None