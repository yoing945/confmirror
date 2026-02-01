import os
import shutil
import subprocess
import glob
import fnmatch
from pathlib import Path

from confmirror.config import ConfigKeys
from confmirror.utils import should_exclude_path

from .meta import write_meta

def _backup_directory(src_dir: Path, dest_dir: Path, logger):
    """
    备份目录及其内容

    Args:
        src_dir: 源目录
        dest_dir: 目标目录
        logger: 日志记录器
    """
    # 创建目标目录
    dest_dir.mkdir(parents=True, exist_ok=True)

    # 获取源目录的统计信息并写入目录的元数据
    src_stat = src_dir.stat()
    dir_mode = oct(src_stat.st_mode)[-3:]
    write_meta(dest_dir, dir_mode, src_stat.st_uid, src_stat.st_gid, "dir")

    # 记录目录元数据写入成功的日志
    logger.info(f"[目录信息备份成功] → {src_dir} (权限:{dir_mode} 用户:{src_stat.st_uid}:{src_stat.st_gid})")

def _backup_file(src: Path, dest: Path, logger):
    """
    备份单个文件

    Args:
        src: 源文件路径
        dest: 目标文件路径
        logger: 日志记录器
    """
    try:
        # 确保目标父目录存在
        dest.parent.mkdir(parents=True, exist_ok=True)

        # 复制文件
        shutil.copy2(src, dest)

        # 获取文件统计信息
        stat = src.stat()
        mode = oct(stat.st_mode)[-3:]  # 获取最后3位权限数字

        # 写入元数据
        write_meta(dest, mode, stat.st_uid, stat.st_gid, "file")

        logger.info(f"[文件备份成功] → {src} (权限:{mode} 用户:{stat.st_uid}:{stat.st_gid})")
    except PermissionError:
        logger.error(f"[权限错误] 无法备份文件 {src}，可能需要更高权限")
    except Exception as e:
        logger.error(f"[备份失败] {src}: {str(e)}")


def backup_single_path(src: Path, mirror_root: Path, logger):
    """
    备份单个路径（文件或目录）到镜像目录

    Args:
        src: 源路径
        mirror_root: 镜像根目录
        logger: 日志记录器
    """
    if not src.exists():
        logger.warning(f"[路径不存在] 跳过备份: {src}")
        return

    # 检查是否为支持的文件类型
    if not (src.is_file() or src.is_dir()):
        logger.warning(f"[跳过] 不支持的文件类型: {src}")
        return

    # 直接使用源路径的绝对路径作为备份路径
    dest = mirror_root / str(src).lstrip('/')

    if src.is_file():
        _backup_file(src, dest, logger)
    elif src.is_dir():
        # 对于目录，只备份目录本身（不递归内容）
        _backup_directory(src, dest, logger)

def run_backup_script(script_rel: str, settings: dict, logger):
    """
    执行备份脚本

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
        logger.error(f"[脚本备份失败] → 脚本不存在 {script}")
        return False

    try:
        # 确保脚本有执行权限
        script.chmod(0o755)
        logger.info(f"[脚本备份执行] → 运行脚本 {script}")

        # 执行脚本，传入"backup"参数
        result = subprocess.run(
            [str(script), "backup"],
            check=True,
            cwd=Path(settings[ConfigKeys.SCRIPT_HOOKS_DIR]).parent,  # 使用备份根目录作为工作目录
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        logger.info(f"[脚本备份成功] → 脚本执行完成")
        if result.stdout:
            logger.debug(f"[脚本输出] {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"[脚本备份失败] → 脚本执行异常: {e}")
        if e.stderr:
            logger.error(f"[脚本错误输出] {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"[脚本执行异常] → : {str(e)}")
        return False

def expand_path_patterns(path_pattern: str, parent_path: str = "", exclude_patterns: list = []) -> list:
    """
    展开通配符路径模式为实际路径列表

    Args:
        path_pattern: 路径模式，可能包含通配符
        parent_path: 父路径
        exclude_patterns: 排除模式列表

    Returns:
        匹配的路径列表
    """
    if exclude_patterns is None:
        exclude_patterns = []

    # 如果提供了父路径，则将模式附加到父路径
    if parent_path:
        full_pattern = str(Path(parent_path) / path_pattern)
    else:
        full_pattern = path_pattern

    # 使用 glob 模块匹配所有路径
    # recursive=True 使 glob.glob 支持 ** 模式
    matched_strs = glob.glob(full_pattern, recursive=True)

    # 将匹配的字符串路径转为 Path 对象
    matched_paths = [Path(p) for p in matched_strs]

    # 应用排除模式过滤结果
    filtered_paths = [
        path for path in matched_paths
        if not should_exclude_path(path, exclude_patterns, parent_path)
    ]

    return filtered_paths


def backup_module(module: dict, backup_root: Path, settings: dict, logger):
    """
    备份模块配置中指定的路径或脚本

    Args:
        module: 模块配置字典
        backup_root: 镜像根目录
        settings: 配置设置字典
        logger: 日志记录器
    """
    module_name = module[ConfigKeys.MOD_NAME]
    logger.info(f"正在备份模块: {module_name}")
    if ConfigKeys.MOD_SCRIPT in module:
        # 使用脚本备份
        script_rel = module[ConfigKeys.MOD_SCRIPT]
        run_backup_script(script_rel, settings, logger)
    elif ConfigKeys.MOD_INCLUDE_PATHS in module:
        # 使用路径备份
        parent_path = module.get(ConfigKeys.MOD_PARENT_PATH, "")

        # 获取排除路径模式
        exclude_patterns = module.get(ConfigKeys.MOD_EXCLUDE_PATHS, [])

        for path_str in module[ConfigKeys.MOD_INCLUDE_PATHS]:
            # 展开可能的通配符路径，同时应用排除规则
            expanded_paths = expand_path_patterns(path_str, parent_path, exclude_patterns)

            if not expanded_paths:
                logger.warning(f"[路径模式无匹配] 路径模式未匹配到任何文件: {path_str}")
                continue

            for path in expanded_paths:
                # 直接处理glob结果，根据文件类型执行相应备份
                if path.is_file():
                    _backup_file(path, backup_root / str(path).lstrip('/'), logger)
                elif path.is_dir():
                    _backup_directory(path, backup_root / str(path).lstrip('/'), logger)
                else:
                    logger.warning(f"[跳过] 不支持的文件类型: {path}")
    else:
        logger.warning(f"模块 {module_name} 既没有配置路径也没有配置脚本")