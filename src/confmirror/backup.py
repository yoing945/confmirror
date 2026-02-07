import os
import shutil
import subprocess
import glob
import fnmatch
from pathlib import Path
from typing import Optional

from confmirror.config import ConfigKeys
from confmirror.diff import compare_meta, same_file
from confmirror.utils import run_script, should_exclude_path, find_matching_module_with_path
from confmirror.meta import write_meta
import hashlib


def execute_backup(config: dict, logger, target_module_name: Optional[str] = None,
                   target_path: Optional[str] = None, force: bool = False) -> None:
    """
    执行备份操作

    Args:
        config: 配置字典
        logger: 日志记录器
        target_module_name: 指定要备份的模块名称
        target_path: 指定要备份的路径
        force: 是否强制覆盖备份（默认为False，即差异备份）
    """
    settings = config[ConfigKeys.SECTION_SETTINGS]
    backup_root = Path(settings[ConfigKeys.BACKUP_ROOT])

    # 确保备份根目录存在
    backup_root.mkdir(parents=True, exist_ok=True)

    if target_module_name:
        # 分模块备份
        modules = config.get(ConfigKeys.SECTION_MODULES, [])
        found_module = next((mod for mod in modules if mod[ConfigKeys.MOD_NAME] == target_module_name), None)
        if not found_module:
            logger.error(f"找不到模块: '{target_module_name}' ")
            return
        backup_module(found_module, backup_root, settings, logger, force)

    elif target_path:
        module = find_matching_module_with_path(config.get(ConfigKeys.SECTION_MODULES, []), Path(target_path))
        if not module:
            logger.error(f"路径 '{target_path}' 不属于任何模块，无法备份")
            return
        # 获取排除路径模式和父路径
        all_exclude_patterns = module.get(ConfigKeys.MOD_EXCLUDE_PATHS, [])
        parent_path = module.get(ConfigKeys.MOD_PARENT_PATH, "")
        if should_exclude_path(Path(target_path), all_exclude_patterns, parent_path):
            logger.info(f"[跳过] 路径 '{target_path}' 被排除")
            return
        # 展开可能的通配符路径，并应用排除规则
        expanded_paths = expand_path_patterns(target_path, "", all_exclude_patterns)

        if not expanded_paths:
            logger.warning(f"路径模式未匹配到任何文件: {target_path}")
            return

        # 对每个匹配的路径进行备份
        for path in expanded_paths:
            # 检查路径是否在当前模块的排除列表中
            if should_exclude_path(path, all_exclude_patterns, parent_path):
                logger.info(f"[跳过] 路径 '{path}' 被排除")
                continue
            backup_single_path(path, backup_root, logger, force)
    else:
        # 全量备份
        for module in config.get(ConfigKeys.SECTION_MODULES, []):
            backup_module(module, backup_root, settings, logger, force)


def _backup_directory(src_dir: Path, dest_dir: Path, logger, force: bool = False):
    """
    备份目录及其内容

    Args:
        src_dir: 源目录
        dest_dir: 目标目录
        logger: 日志记录器
        force: 是否强制覆盖
    """
    # 检查是否跳过（差异备份）
    if not force and dest_dir.exists() and compare_meta(src_dir, dest_dir):
        logger.info(f"[跳过] 目录信息无变化: {src_dir}")
        return

    # 创建目标目录
    dest_dir.mkdir(parents=True, exist_ok=True)

    # 获取源目录的统计信息并写入目录的元数据
    src_stat = src_dir.stat()
    dir_mode = oct(src_stat.st_mode)[-3:]
    write_meta(dest_dir, dir_mode, src_stat.st_uid, src_stat.st_gid, "dir")

    # 确保备份目录可读写（关键：修改权限以确保用户可以读写和Git可以管理）
    # 设置目录权限为用户可读写执行，组和其他用户只读执行
    dest_dir.chmod(0o755)

    # 记录目录元数据写入成功的日志
    logger.info(f"[目录信息备份成功] → {src_dir} (权限:{dir_mode} 用户:{src_stat.st_uid}:{src_stat.st_gid})")


def _backup_file(src: Path, dest: Path, logger, force: bool = False, use_hash: bool = False):
    """
    备份单个文件

    Args:
        src: 源文件路径
        dest: 目标文件路径
        logger: 日志记录器
        force: 是否强制覆盖
        use_hash: 是否使用哈希比对（增量备份时）
    """
    # 检查是否跳过（差异备份）
    if not force and same_file(src, dest):
        logger.info(f"[跳过] 文件信息无变化: {src}")
        return

    try:
        # 确保目标父目录存在
        dest.parent.mkdir(parents=True, exist_ok=True)

        # 复制文件内容
        shutil.copy2(src, dest)

        # 获取文件统计信息
        stat = src.stat()
        mode = oct(stat.st_mode)[-3:]  # 获取最后3位权限数字

        # 写入元数据（重要：在修改权限之前保存原始权限信息）
        write_meta(dest, mode, stat.st_uid, stat.st_gid, "file")

        # 设置备份文件权限为用户可读写，组和其他用户只读
        dest.chmod(0o644)

        logger.info(f"[文件备份成功] → {src} (权限:{mode} 用户:{stat.st_uid}:{stat.st_gid})")

    except PermissionError:
        logger.error(f"[权限错误] 无法备份文件 {src}，可能需要更高权限")
    except Exception as e:
        logger.error(f"[备份失败] {src}: {str(e)}")


def backup_single_path(src: Path, mirror_root: Path, logger, force: bool = False):
    """
    备份单个路径（文件或目录）到镜像目录

    Args:
        src: 源路径
        mirror_root: 镜像根目录
        logger: 日志记录器
        force: 是否强制覆盖
    """
    if not src.exists():
        logger.warning(f"路径不存在: {src}")
        return

    # 检查是否为支持的文件类型
    if not (src.is_file() or src.is_dir()):
        logger.warning(f"不支持的文件类型: {src}")
        return

    # 检查源路径是否在备份根目录内，避免递归备份
    try:
        src.resolve().relative_to(mirror_root.resolve())
        logger.error(f"源路径 '{src}' 是备份目录或其子目录，不能备份备份目录自身")
        return
    except ValueError:
        # 源路径不在备份根目录内，继续备份
        pass

    # 直接使用源路径的绝对路径作为备份路径
    dest = mirror_root / str(src).lstrip('/')

    if src.is_file():
        _backup_file(src, dest, logger, force)
    elif src.is_dir():
        # 对于目录，只备份目录本身（不递归内容）
        _backup_directory(src, dest, logger, force)


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


def backup_module(module: dict, backup_root: Path, settings: dict, logger,
                  force: bool = False):
    """
    备份模块配置中指定的路径或脚本

    Args:
        module: 模块配置字典
        backup_root: 镜像根目录
        settings: 配置设置字典
        logger: 日志记录器
        force: 是否强制覆盖备份（默认为False，即差异备份）
    """
    module_name = module[ConfigKeys.MOD_NAME]
    logger.info(f"正在备份模块: {module_name}")

    if ConfigKeys.MOD_SCRIPT in module:
        # 使用脚本备份
        script_rel = module[ConfigKeys.MOD_SCRIPT]
        script_lang = module.get(ConfigKeys.MOD_SCRIPT_LANG, "bash")

        # 如果未指定语言，尝试自动检测
        if script_lang == "auto":
            from confmirror.utils import get_script_shebang
            script_path = Path(settings[ConfigKeys.SCRIPT_HOOKS_DIR]) / script_rel
            detected = get_script_shebang(script_path)
            script_lang = detected if detected else "bash"
            logger.info(f"自动检测到脚本语言: {script_lang}")

        run_script(script_rel, settings, logger, "backup", script_lang)

    elif ConfigKeys.MOD_INCLUDE_PATHS in module:
        # 使用路径备份
        parent_path = module.get(ConfigKeys.MOD_PARENT_PATH, "")

        # 获取排除路径模式
        exclude_patterns = module.get(ConfigKeys.MOD_EXCLUDE_PATHS, [])

        for path_str in module[ConfigKeys.MOD_INCLUDE_PATHS]:
            # 展开可能的通配符路径，同时应用排除规则
            expanded_paths = expand_path_patterns(path_str, parent_path, exclude_patterns)

            if not expanded_paths:
                logger.warning(f"该路径未到任何文件: {path_str}")
                continue

            for path in expanded_paths:
                # 检查路径是否在备份根目录内，避免递归备份
                try:
                    path.resolve().relative_to(backup_root.resolve())
                    logger.error(f"源路径 '{path}' 是备份目录或其子目录，不能备份备份目录自身")
                    continue
                except ValueError:
                    # 源路径不在备份根目录内，继续备份
                    pass
                
                # 直接处理glob结果，根据文件类型执行相应备份
                if path.is_file():
                    _backup_file(path, backup_root / str(path).lstrip('/'), logger, force)
                elif path.is_dir():
                    _backup_directory(path, backup_root / str(path).lstrip('/'), logger, force)
                else:
                    logger.warning(f"[跳过] 不支持的文件类型: {path}")
    else:
        logger.warning(f"模块 {module_name} 既没有配置路径也没有配置脚本")