"""差异对比终端展示层 — 人类可读输出。"""
from datetime import datetime
from pathlib import Path
from typing import List

import click

from confmirror.diff.core import FileDiffResult, DiffResult


def _get_diff_prefix(is_same: bool) -> str:
    """获取差异前缀。"""
    return "" if is_same else "⚠️  "


def show_file_diff_lines(diff_lines: List[str]) -> None:
    """显示 unified diff 行（带 ANSI 颜色）。"""
    click.echo(f"\n   📝 内容差异 (Unified Diff):")
    for line in diff_lines:
        line = line.rstrip()
        if line.startswith('+'):
            click.echo(f"   \033[32m{line}\033[0m")
        elif line.startswith('-'):
            click.echo(f"   \033[31m{line}\033[0m")
        elif line.startswith('@@'):
            click.echo(f"   \033[36m{line}\033[0m")
        else:
            click.echo(f"   {line}")


def display_file_diff(result: FileDiffResult, show_content_diff: bool = True) -> None:
    """显示单个文件的差异（人类可读）。"""
    click.echo(f"源文件: {result.source}")
    click.echo(f"备份文件: {result.backup}")
    click.echo(f"基本信息:")
    is_dir = result.source.is_dir() and result.backup.is_dir()
    click.echo(f"  - 类型: {'dir' if is_dir else 'file'}")
    click.echo(f"  - 源修改时间: {datetime.fromtimestamp(result.source_mtime)}")
    click.echo(f"  - 备份修改时间: {datetime.fromtimestamp(result.backup_mtime)}")
    diff_size_prefix = _get_diff_prefix(result.source_size == result.backup_size)
    click.echo(f"  - {diff_size_prefix}源大小: {result.source_size} bytes")
    click.echo(f"  - {diff_size_prefix}备份大小: {result.backup_size} bytes")

    if is_dir:
        diff_meta_prefix = _get_diff_prefix(result.meta_same)
        click.echo(f"  - {diff_meta_prefix}源目录权限: {result.source_mode} (uid:{result.source_uid}, gid:{result.source_gid})")
        click.echo(f"  - {diff_meta_prefix}备份目录权限: {result.backup_mode} (uid:{result.backup_uid}, gid:{result.backup_gid})")
        if result.meta_same:
            click.echo(f"  ✅ 状态一致")
        else:
            click.echo(f"  ⚠️  状态存在差异")
    else:
        click.echo(f"  - 源文件权限: {result.source_mode} (uid:{result.source_uid}, gid:{result.source_gid})")
        click.echo(f"  - 备份文件权限: {result.backup_mode} (uid:{result.backup_uid}, gid:{result.backup_gid})")
        files_identical = result.content_same and result.meta_same
        if files_identical:
            click.echo(f"  ✅ 状态一致")
        else:
            click.echo(f"  ⚠️  状态存在差异")
            if show_content_diff and result.unified_diff:
                show_file_diff_lines(result.unified_diff)
            elif show_content_diff and not result.unified_diff:
                click.echo(f"\n   📝 文件文本内容相同（但可能存在编码或换行符差异）")


def print_line(count: int = 100) -> None:
    """打印分隔线。"""
    click.echo(f"{'-' * count}")


def display_diff_result(result: DiffResult, backup_root: Path, detail: bool = False) -> None:
    """显示模块/路径的差异结果（人类可读）。"""
    if result.module_name:
        click.echo(f"开始对比模块: {result.module_name}")

    for added_file in result.added:
        click.echo(f"\033[32m+ 源文件: {added_file}\033[0m")
        print_line()

    for deleted_file in result.deleted:
        click.echo(f"\033[31m- 源文件: {deleted_file}\033[0m")
        print_line()

    for file_result in result.changed:
        display_file_diff(file_result, show_content_diff=detail)
        print_line()

    for _ in result.unchanged:
        # unchanged 文件在人类可读模式下默认不显示详情，只显示统计
        pass

    total_common = len(result.changed) + len(result.unchanged)
    summary = f"共{total_common}个共同文件, {len(result.changed)}个存在差异, {len(result.added)}个新增, {len(result.deleted)}个缺失"
    click.echo(f"对比完成: {summary}")
