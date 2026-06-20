"""差异对比功能模块。

支持单文件级别的源文件与备份文件比较，提供人类可读和 JSON 结构化两种输出格式。
"""

import glob as _glob_module

# Backward compatibility: tests patch these module-level names
from pathlib import Path

# Expose glob module so tests can patch confmirror.diff.glob.glob
glob = _glob_module

import click

from confmirror.config import Config, ModuleConfig
from confmirror.diff.core import (
    DiffResult,
    FileDiffResult,
    _compare_files_by_hash,
    compare_content,
    compare_files_core,
    compare_meta,
    diff_module_core,
    diff_paths_core,
    same_file,
)
from confmirror.diff.display import display_diff_result
from confmirror.meta import read_meta
from confmirror.output import emit_json
from confmirror.utils import find_matching_module_with_path, should_exclude_path

# ---------------------------------------------------------------------------
# Backward compatibility wrapper (old tests patch this)
# ---------------------------------------------------------------------------


def compare_files_set(source_files_set, backup_files_set, backup_root, detail=False):
    """对比两组文件集合（人类可读输出）。

    这是旧版接口的兼容包装，内部使用新的 core/display 分层实现。
    """
    added_files = source_files_set - backup_files_set
    deleted_files = backup_files_set - source_files_set
    common_files = source_files_set & backup_files_set

    for added_file in added_files:
        click.echo(f"\033[32m+ 源文件: {added_file}\033[0m")
        click.echo("-" * 100)

    for deleted_file in deleted_files:
        click.echo(f"\033[31m- 源文件: {deleted_file}\033[0m")
        click.echo("-" * 100)

    diff_files = 0
    total_common_files = len(common_files)

    for common_file in common_files:
        source_file = Path("/") / common_file
        backup_file = backup_root / str(common_file).lstrip("/")

        if source_file.exists() and backup_file.exists():
            from confmirror.diff.display import display_file_diff

            result = compare_files_core(source_file, backup_file)
            if not result.content_same or not result.meta_same:
                diff_files += 1
            display_file_diff(result, show_content_diff=detail)
            click.echo("-" * 100)

    summary = f"共{total_common_files}个共同文件, {diff_files}个存在差异, {len(added_files)}个新增, {len(deleted_files)}个缺失"
    click.echo(f"对比完成: {summary}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def diff_module(config, module_name, detail=False, output_format="human"):
    """对比整个模块的所有文件。

    Args:
        config: 配置对象
        module_name: 模块名称
        detail: 是否显示详细内容差异
        output_format: 输出格式，"human" 或 "json"
    """
    if output_format == "json":
        result = diff_module_core(config, module_name, detail)
        emit_json(
            {
                "status": "success",
                "command": "diff",
                "module": module_name,
                "added": result.added,
                "deleted": result.deleted,
                "changed": result.changed,
                "unchanged": result.unchanged,
            }
        )
        return

    # Human mode: backward-compatible path using compare_files_set
    settings = config.settings
    backup_root = settings.backup_root
    target_module = next((m for m in config.modules if m.name == module_name), None)

    if not target_module:
        click.echo(f"❌ 未找到模块: {module_name}")
        return

    if target_module.hook is not None:
        click.echo("脚本模块不支持差异对比")
        return

    parent_path = target_module.base_path or ""
    include_paths = target_module.paths or []
    exclude_patterns = target_module.exclude_paths or []

    source_files_set = set()
    for path_pattern in include_paths:
        if parent_path:
            source_pattern = Path(parent_path) / path_pattern
        else:
            source_pattern = Path(path_pattern)
        source_files = glob.glob(str(source_pattern), recursive=True)
        for source_str in source_files:
            source_path = Path(source_str)
            if not source_path.exists():
                continue
            if should_exclude_path(
                source_path, exclude_patterns=exclude_patterns, parent_path=parent_path
            ):
                continue
            source_files_set.add(source_path.resolve())

    backup_files_set = set()
    for path_pattern in include_paths:
        rel_pattern = path_pattern.lstrip("/")
        if parent_path:
            rel_parent = parent_path.lstrip("/")
            backup_pattern = backup_root / rel_parent / rel_pattern
        else:
            backup_pattern = backup_root / rel_pattern
        backup_files = glob.glob(str(backup_pattern), recursive=True)
        for backup_str in backup_files:
            backup_path = Path(backup_str)
            if backup_path.suffix == ".meta":
                continue
            if not backup_path.exists():
                continue
            rel_path = backup_path.relative_to(backup_root)
            source_equivalent = Path("/") / rel_path
            backup_files_set.add(source_equivalent)

    compare_files_set(source_files_set, backup_files_set, backup_root, detail)


def diff_paths(config, target_paths, detail=False, output_format="human"):
    """对比指定路径下的所有文件与备份目录中的差异。

    Args:
        config: 配置对象
        target_paths: 目标路径列表
        detail: 是否显示详细内容差异
        output_format: 输出格式，"human" 或 "json"
    """
    if output_format == "json":
        result = diff_paths_core(config, target_paths, detail)
        emit_json(
            {
                "status": "success",
                "command": "diff",
                "added": result.added,
                "deleted": result.deleted,
                "changed": result.changed,
                "unchanged": result.unchanged,
            }
        )
        return

    # Human mode: backward-compatible path
    settings = config.settings
    backup_root = settings.backup_root
    source_files_set = set()
    backup_files_set = set()

    for target_path in target_paths:
        module = find_matching_module_with_path(config.modules, Path(target_path))
        if not module:
            return
        all_exclude_patterns = module.exclude_paths or []
        parent_path = module.base_path or ""
        if should_exclude_path(
            Path(target_path),
            exclude_patterns=all_exclude_patterns,
            parent_path=parent_path,
        ):
            continue

        source_files = glob.glob(target_path, recursive=True)
        for source_str in source_files:
            source_path = Path(source_str)
            if not source_path.exists():
                continue
            source_files_set.add(source_path.resolve())

        target_path_obj = Path(target_path)
        if target_path_obj.is_absolute():
            rel_to_root = target_path_obj.relative_to(Path("/"))
        else:
            rel_to_root = target_path_obj
        target_backup_path = backup_root / rel_to_root

        backup_files = glob.glob(str(target_backup_path), recursive=True)
        for backup_str in backup_files:
            backup_path = Path(backup_str)
            if backup_path.suffix == ".meta":
                continue
            if not backup_path.exists():
                continue
            rel_path = backup_path.relative_to(backup_root)
            source_equivalent = Path("/") / rel_path
            backup_files_set.add(source_equivalent)

    compare_files_set(source_files_set, backup_files_set, backup_root, detail)
