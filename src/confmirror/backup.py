import logging
import glob
import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any

import pathspec

from confmirror.config import Config, ModuleConfig, Settings
from confmirror.diff import compare_meta, same_file
from confmirror.meta import write_meta
from confmirror.utils import (
    find_matching_module_with_path,
    run_script,
    should_exclude_path,
)
from confmirror.logger import ModuleLog

logger = logging.getLogger(__name__)
_log = ModuleLog("backup", logger)


def execute_backup(config: Config, target_module_name: Optional[str] = None,
                   target_path: Optional[str] = None, force: bool = False,
                   dry_run: bool = False) -> None:
    """
    执行备份操作

    Args:
        config: 配置对象
        target_module_name: 指定要备份的模块名称
        target_path: 指定要备份的路径
        force: 是否强制覆盖备份（默认为False，即差异备份）
        dry_run: 是否为预览模式（不实际执行）
    """
    settings = config.settings
    backup_root = settings.backup_root

    if dry_run:
        _log.info("[DRY-RUN] 预览模式，不实际执行备份操作")
    else:
        # 确保备份根目录存在
        backup_root.mkdir(parents=True, exist_ok=True)

    if target_module_name:
        # 分模块备份
        modules = config.modules
        found_module = next((mod for mod in modules if mod.name == target_module_name), None)
        if not found_module:
            _log.error(f"找不到模块: '{target_module_name}'")
            return
        backup_module(found_module, backup_root, settings, force, dry_run=dry_run)

    elif target_path:
        module = find_matching_module_with_path(config.modules, Path(target_path))
        if not module:
            _log.error(f"路径 '{target_path}' 不属于任何模块，无法备份")
            return
        # 获取排除路径模式和父路径
        all_exclude_patterns = module.exclude_paths or []
        parent_path = module.base_path or ""
        if should_exclude_path(Path(target_path), exclude_patterns=all_exclude_patterns, parent_path=parent_path):
            _log.skip(f"路径 '{target_path}' 被排除")
            return
        # 展开可能的通配符路径，并应用排除规则
        expanded_paths = expand_path_patterns(target_path, "", all_exclude_patterns)

        if not expanded_paths:
            _log.warn(f"路径模式未匹配到任何文件: {target_path}")
            return

        # 预编译排除规则，避免循环内重复构建
        spec = pathspec.GitIgnoreSpec.from_lines(all_exclude_patterns) if all_exclude_patterns else None
        # 对每个匹配的路径进行备份
        for path in expanded_paths:
            # 检查路径是否在当前模块的排除列表中
            if should_exclude_path(path, spec=spec, parent_path=parent_path):
                _log.skip(f"路径 '{path}' 被排除")
                continue
            backup_single_path(path, backup_root, settings, force, spec=spec, parent_path=parent_path)
    else:
        # 全量备份
        for module in config.modules:
            backup_module(module, backup_root, settings, force, dry_run=dry_run)


def _backup_directory(src_dir: Path, dest_dir: Path, settings: Settings, force: bool = False,
                      spec: Optional[pathspec.GitIgnoreSpec] = None, parent_path: str = "",
                      dry_run: bool = False):
    """
    备份目录及其内容（递归）

    Args:
        src_dir: 源目录
        dest_dir: 目标目录
        settings: 配置设置对象
        force: 是否强制覆盖
        spec: 预编译的 pathspec 对象，用于排除规则
        parent_path: 模块的父路径，用于排除规则匹配
        dry_run: 是否为预览模式
    """
    if dry_run:
        _log.info(f"[DRY-RUN] 将备份目录: {src_dir} -> {dest_dir}")
    else:
        # 创建目标目录
        dest_dir.mkdir(parents=True, exist_ok=True)

        # 获取源目录的统计信息并写入目录的元数据
        src_stat = src_dir.stat()
        dir_mode = oct(src_stat.st_mode)[-3:]
        if not write_meta(dest_dir, dir_mode, src_stat.st_uid, src_stat.st_gid, "dir"):
            _log.warn(f"目录元数据写入失败，继续备份子内容: {src_dir}")

        # 确保备份目录可读写
        backup_dir_mode = int(settings.mirror_dir_mode, 8)
        dest_dir.chmod(backup_dir_mode)

        _log.ok(f"→ {src_dir} (权限:{dir_mode} 用户:{src_stat.st_uid}:{src_stat.st_gid})")

    # 递归处理子文件和子目录
    for child in src_dir.iterdir():
        # 应用排除规则
        if spec and should_exclude_path(child, spec=spec, parent_path=parent_path):
            _log.skip(f"路径 '{child}' 被排除")
            continue

        child_dest = dest_dir / child.name
        if child.is_file():
            _backup_file(child, child_dest, settings, force, dry_run=dry_run)
        elif child.is_dir():
            _backup_directory(child, child_dest, settings, force, spec=spec, parent_path=parent_path, dry_run=dry_run)
        else:
            _log.skip(f"不支持的文件类型: {child}")


def _backup_file(src: Path, dest: Path, settings: Settings, force: bool = False,
                  use_hash: bool = False, dry_run: bool = False):
    """
    备份单个文件

    Args:
        src: 源文件路径
        dest: 目标文件路径
        settings: 配置设置对象
        force: 是否强制覆盖
        use_hash: 是否使用哈希比对（增量备份时）
        dry_run: 是否为预览模式
    """
    # 检查是否跳过（差异备份）
    if not force and same_file(src, dest):
        _log.skip(f"文件信息无变化: {src}")
        return

    if dry_run:
        _log.info(f"[DRY-RUN] 将备份文件: {src} -> {dest}")
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
        if not write_meta(dest, mode, stat.st_uid, stat.st_gid, "file"):
            _log.warn(f"文件元数据写入失败: {src}")

        # 设置备份文件权限，确保当前用户和 Git 可读写
        backup_file_mode = int(settings.mirror_file_mode, 8)
        dest.chmod(backup_file_mode)

        _log.ok(f"→ {src} (权限:{mode} 用户:{stat.st_uid}:{stat.st_gid})")

    except PermissionError:
        _log.error(f"无法备份文件 {src}，可能需要更高权限")
    except Exception as e:
        _log.error(f"{src}: {str(e)}")


def backup_single_path(src: Path, mirror_root: Path, settings: Settings, force: bool = False,
                       spec: Optional[pathspec.GitIgnoreSpec] = None, parent_path: str = "",
                       dry_run: bool = False):
    """
    备份单个路径（文件或目录）到镜像目录

    Args:
        src: 源路径
        mirror_root: 镜像根目录
        settings: 配置设置对象
        force: 是否强制覆盖
        spec: 预编译的 pathspec 对象，用于排除规则
        parent_path: 模块的父路径，用于排除规则匹配
        dry_run: 是否为预览模式
    """
    if not src.exists():
        _log.warn(f"路径不存在: {src}")
        return

    # 检查是否为支持的文件类型
    if not (src.is_file() or src.is_dir()):
        _log.warn(f"不支持的文件类型: {src}")
        return

    # 检查源路径是否在备份根目录内，避免递归备份
    if src.resolve().is_relative_to(mirror_root.resolve()):
        _log.error(f"源路径 '{src}' 是备份目录或其子目录，不能备份备份目录自身")
        return

    # 直接使用源路径的绝对路径作为备份路径
    dest = mirror_root / str(src).lstrip('/')

    if src.is_file():
        _backup_file(src, dest, settings, force, dry_run=dry_run)
    elif src.is_dir():
        _backup_directory(src, dest, settings, force, spec=spec, parent_path=parent_path, dry_run=dry_run)


def expand_path_patterns(
    path_pattern: str,
    parent_path: str = "",
    exclude_patterns: Optional[list] = None,
    spec: Optional[pathspec.GitIgnoreSpec] = None,
) -> List[Path]:
    """
    展开通配符路径模式为实际路径列表

    Args:
        path_pattern: 路径模式，可能包含通配符
        parent_path: 父路径
        exclude_patterns: 排除模式列表（仅在 spec 为 None 时使用）
        spec: 预编译的 pathspec 对象（推荐在循环外预编译后传入）

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
        if not should_exclude_path(path, spec=spec, parent_path=parent_path)
    ]

    return filtered_paths


def backup_module(module: ModuleConfig, backup_root: Path, settings: Settings,
                  force: bool = False, dry_run: bool = False):
    """
    备份模块配置中指定的路径或脚本

    Args:
        module: 模块配置对象
        backup_root: 镜像根目录
        settings: 配置设置对象
        force: 是否强制覆盖备份（默认为False，即差异备份）
        dry_run: 是否为预览模式
    """
    module_name = module.name
    _log.info(f"正在备份模块: {module_name}")

    if dry_run:
        _log.info(f"[DRY-RUN] 预览模块 '{module_name}' 的备份内容")

    if module.hook is not None:
        if dry_run:
            _log.info(f"[DRY-RUN] 将执行脚本: {module.hook}")
        else:
            # 使用脚本备份
            script_rel = module.hook
            hook_lang = module.hook_lang

            # 如果未指定语言，尝试自动检测
            if hook_lang == "auto":
                from confmirror.utils import get_script_shebang
                script_path = settings.script_hooks_dir / script_rel
                detected = get_script_shebang(script_path)
                hook_lang = detected if detected else "bash"
                _log.info(f"自动检测到脚本语言: {hook_lang}")

            run_script(script_rel, settings, "backup", hook_lang)

    elif module.paths is not None:
        # 使用路径备份
        parent_path = module.base_path or ""

        # 获取排除路径模式
        exclude_patterns = module.exclude_paths or []

        # 预编译排除规则，避免循环内重复构建
        spec = pathspec.GitIgnoreSpec.from_lines(exclude_patterns) if exclude_patterns else None
        for path_str in module.paths:
            # 展开可能的通配符路径，同时应用排除规则
            expanded_paths = expand_path_patterns(path_str, parent_path, exclude_patterns, spec=spec)

            if not expanded_paths:
                _log.warn(f"该路径未到任何文件: {path_str}")
                continue

            for path in expanded_paths:
                # 检查路径是否在备份根目录内，避免递归备份
                if path.resolve().is_relative_to(backup_root.resolve()):
                    _log.error(f"源路径 '{path}' 是备份目录或其子目录，不能备份备份目录自身")
                    continue

                # 直接处理glob结果，根据文件类型执行相应备份
                if path.is_file():
                    _backup_file(path, backup_root / str(path).lstrip('/'), settings, force, dry_run=dry_run)
                elif path.is_dir():
                    _backup_directory(path, backup_root / str(path).lstrip('/'), settings, force,
                                      spec=spec, parent_path=parent_path, dry_run=dry_run)
                else:
                    _log.skip(f"不支持的文件类型: {path}")
    else:
        _log.warn(f"模块 {module_name} 既没有配置路径也没有配置脚本")