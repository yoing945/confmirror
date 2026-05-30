"""
差异对比功能模块 - 支持单文件级别的源文件与备份文件比较
"""
import logging
import difflib
import filecmp
import glob
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any

import click

from .config import Config, ModuleConfig, Settings
from .meta import read_meta
from .utils import find_matching_module_with_path, should_exclude_path
from .logger import ModuleLog

logger = logging.getLogger(__name__)
_log = ModuleLog("diff", logger)


def same_file(src:Path, dest:Path) -> bool:
    """
    比较源文件与备份文件是否相同（内容和元数据）

    Args:
        src: 源文件路径
        dest: 目标文件路径（备份文件）

    Returns:
        bool: 文件内容和元数据均未发生变化返回True，否则返回False
    """
    return compare_content(src, dest) and compare_meta(src, dest)

def compare_content(src: Path, dest: Path) -> bool:
    """
    比较两个文件的内容是否相同

    Args:
        src: 源文件路径
        dest: 目标文件路径

    Returns:
        bool: 内容相同返回True，不同返回False
    """
    if not dest.exists():
        # 目标文件不存在，认为内容不同
        return False

    try:
        # 文件类型不同
        if src.is_dir() != dest.is_dir():
            return False
        if src.is_dir():
            # 目录比较直接返回True
            return True
        return filecmp.cmp(src, dest, shallow=False)
    except (OSError, ValueError):
        # 如果文件比较失败，使用哈希比较
        return _compare_files_by_hash(src, dest)


def compare_meta(src: Path, dest: Path) -> bool:
    """
    检查源文件的当前元数据（权限、UID、GID）是否与上次备份时记录的原始元数据相同

    Args:
        src: 源文件路径
        dest: 目标文件路径（备份文件）

    Returns:
        bool: 元数据未发生变化返回True，否则返回False
    """
    from confmirror.meta import read_meta

    # 读取备份文件的元数据（包含上次备份时的原始权限信息）
    meta_data = read_meta(dest)

    if not meta_data:
        return False  # 没有元数据，认为元数据已变化（首次备份）

    # 获取源文件的当前统计信息
    src_stat = src.stat()
    src_mode = oct(src_stat.st_mode)[-3:]
    src_uid = src_stat.st_uid
    src_gid = src_stat.st_gid

    # 比较所有元数据项：权限、UID、GID
    return (
        src_mode == meta_data.get('mode', '') and
        src_uid == int(meta_data.get('uid', -1)) and
        src_gid == int(meta_data.get('gid', -1))
    )


def _compare_files_by_hash(src: Path, dest: Path) -> bool:
    """
    通过哈希值比较两个文件的内容是否相同

    Args:
        src: 源文件路径
        dest: 目标文件路径

    Returns:
        bool: 内容相同返回True，不同返回False
    """
    try:
        def get_file_hash(file_path):
            hash_obj = hashlib.blake2b()
            with open(file_path, 'rb') as f:
                while chunk := f.read(8192):
                    hash_obj.update(chunk)
            return hash_obj.hexdigest()

        return get_file_hash(src) == get_file_hash(dest)
    except (OSError, TypeError):
        # 如果哈希计算失败，认为文件不同
        return False


def _get_diff_prefix(is_same: bool) -> str:
    """获取差异前缀"""
    return "" if is_same else "⚠️  "

def compare_files(source: Path, backup: Path, show_content_diff: bool = True) -> bool:
    """
    比较两个文件

    Args:
        source: 源文件路径
        backup: 备份文件路径
        show_content_diff: 是否显示详细内容差异

    Returns:
        bool: 文件相同返回True，不同返回False
    """
    source_stat = source.stat()
    backup_stat = backup.stat()
    is_dir = source.is_dir() and backup.is_dir()

    click.echo(f"源文件: {source}")
    click.echo(f"备份文件: {backup}")
    click.echo(f"基本信息:")
    click.echo(f"  - 类型: {'dir' if is_dir else 'file'}")
    click.echo(f"  - 源修改时间: {datetime.fromtimestamp(source_stat.st_mtime)}")
    click.echo(f"  - 备份修改时间: {datetime.fromtimestamp(backup_stat.st_mtime)}")
    diff_size_prefix = _get_diff_prefix(source_stat.st_size == backup_stat.st_size)
    click.echo(f"  - {diff_size_prefix}源大小: {source_stat.st_size} bytes")
    click.echo(f"  - {diff_size_prefix}备份大小: {backup_stat.st_size} bytes")

    # 检查是否是目录
    if is_dir:

        # 对于目录，只比较元数据
        meta_same = compare_meta(source, backup)

        # 读取备份文件的元数据
        meta_data = read_meta(backup)
        if meta_data:
            diff_meta_prefix = _get_diff_prefix(meta_same)
            click.echo(f"  - {diff_meta_prefix}源目录权限: {oct(source_stat.st_mode)[-3:]} (uid:{source_stat.st_uid}, gid:{source_stat.st_gid})")
            click.echo(f"  - {diff_meta_prefix}备份目录权限: {meta_data.get('mode', 'N/A')} (uid:{meta_data.get('uid', 'N/A')}, gid:{meta_data.get('gid', 'N/A')})")

        if meta_same:
            click.echo(f"  ✅ 状态一致")
            return True
        else:
            click.echo(f"  ⚠️  状态存在差异")
            return False
    else:
        content_same = compare_content(source, backup)
        meta_same = compare_meta(source, backup)

        # 读取备份文件的元数据
        meta_data = read_meta(backup)
        if meta_data:
            click.echo(f"  - 源文件权限: {oct(source_stat.st_mode)[-3:]} (uid:{source_stat.st_uid}, gid:{source_stat.st_gid})")
            click.echo(f"  - 备份文件权限: {meta_data.get('mode', 'N/A')} (uid:{meta_data.get('uid', 'N/A')}, gid:{meta_data.get('gid', 'N/A')})")

        # 判断是否完全相同
        files_identical = content_same and meta_same

        if files_identical:
            click.echo(f"  ✅ 状态一致")
            return True
        else:
            click.echo(f"  ⚠️  状态存在差异")

            if show_content_diff:
                show_file_diff(source, backup)
            return False


def show_file_diff(source: Path, backup: Path, context_lines: int = 3) -> None:
    """
    显示两个文件的详细内容差异（Unified Diff格式）

    Args:
        source: 源文件路径
        backup: 备份文件路径
        context_lines: 上下文行数
    """
    try:
        with open(source, 'r', encoding='utf-8', errors='ignore') as f:
            source_lines = f.readlines()
        with open(backup, 'r', encoding='utf-8', errors='ignore') as f:
            backup_lines = f.readlines()

        # 生成 unified diff
        diff = list(difflib.unified_diff(
            backup_lines,  # from (备份)
            source_lines,  # to (源文件)
            fromfile=f"backup: {backup.name}",
            tofile=f"source: {source.name}",
            n=context_lines
        ))

        if diff:
            click.echo(f"\n   📝 内容差异 (Unified Diff):")
            for line in diff:
                # 根据差异类型着色
                line = line.rstrip()
                if line.startswith('+'):
                    click.echo(f"   \033[32m{line}\033[0m")  # 绿色 - 新增
                elif line.startswith('-'):
                    click.echo(f"   \033[31m{line}\033[0m")  # 红色 - 删除
                elif line.startswith('@@'):
                    click.echo(f"   \033[36m{line}\033[0m")  # 青色 - 位置信息
                else:
                    click.echo(f"   {line}")
        else:
            click.echo(f"\n   📝 文件文本内容相同（但可能存在编码或换行符差异）")

    except Exception as e:
        click.echo(f"\n   ⚠️  无法读取文件内容进行差异对比: {e}")

def print_line(count: int = 100) -> None:
    """
    打印一条分隔线
    """
    click.echo(f"{'-' * count}")

def compare_files_set(source_files_set: set, backup_files_set: set, backup_root: Path, detail: bool = False) -> None:
    # 计算新增、删除和修改的文件
    added_files = source_files_set - backup_files_set  # 源中有但备份中没有
    deleted_files = backup_files_set - source_files_set  # 备份中有但源中没有
    common_files = source_files_set & backup_files_set  # 两者都有

    for added_file in added_files:
        click.echo(f"\033[32m+ 源文件: {added_file}\033[0m")
        print_line()

    for deleted_file in deleted_files:
        click.echo(f"\033[31m- 源文件: {deleted_file}\033[0m")
        print_line()

    # 比较共同存在的文件
    total_common_files = len(common_files)
    diff_files = 0

    for common_file in common_files:
        source_file = Path('/') / common_file
        backup_file = backup_root / str(common_file).lstrip('/')

        if source_file.exists() and backup_file.exists():
            # 调用改进后的compare_files函数，该函数会检查内容和元数据
            if not compare_files(source_file, backup_file, show_content_diff=detail):
                diff_files += 1
            print_line()

    summary = f"共{total_common_files}个共同文件, {diff_files}个存在差异, {len(added_files)}个新增, {len(deleted_files)}个缺失"
    click.echo(f"对比完成: {summary}")
    _log.info(f"对比完成: {summary}")


def diff_paths(config: Config, target_paths: List[str], detail: bool = False) -> None:
    """
    对比指定路径下的所有文件与备份目录中的差异

    Args:
        config: 配置对象
        target_paths: 目标路径列表（原始系统路径）
        detail: 是否显示详细内容差异
    """
    settings = config.settings
    backup_root = settings.backup_root

    # 收集所有源文件路径
    source_files_set = set()
    # 收集该模块在备份目录中的所有文件
    backup_files_set = set()
    for target_path in target_paths:
        module = find_matching_module_with_path(config.modules, Path(target_path))
        if not module:
            click.echo(f"❌ 路径 '{target_path}' 不属于任何模块")
            return
        # 获取排除路径模式和父路径
        all_exclude_patterns = module.exclude_paths or []
        parent_path = module.parent_path or ""
        if should_exclude_path(Path(target_path), all_exclude_patterns, parent_path):
            continue

        # 展开通配符
        source_files = glob.glob(target_path, recursive=True)
        for source_str in source_files:
            source_path = Path(source_str)
            # 检查是否为支持的文件类型
            if not source_path.exists():
                continue
            # 将相对路径添加到集合中（相对于根目录）
            source_files_set.add(source_path)

        target_backup_path = backup_root / Path(target_path).relative_to(Path('/'))
        backup_files = glob.glob(str(target_backup_path), recursive=True)
        for backup_str in backup_files:
            backup_path = Path(backup_str)
            # 跳过.meta文件
            if backup_path.suffix == '.meta':
                continue
            if not backup_path.exists():
                continue
            # 将相对路径添加到集合中（相对于根目录）
            backup_files_set.add(Path('/') / backup_path.relative_to(backup_root))

    compare_files_set(source_files_set, backup_files_set, backup_root, detail)
    _log.info(f"路径对比完成: {target_paths}")


def diff_module(config: Config, module_name: str, detail: bool = False) -> None:
    """
    对比整个模块的所有文件

    Args:
        config: 配置对象
        module_name: 模块名称
        detail: 是否显示详细内容差异
    """
    settings = config.settings
    backup_root = settings.backup_root

    target_module = next((m for m in config.modules if m.name == module_name), None)

    if not target_module:
        click.echo(f"❌ 未找到模块: {module_name}")
        return

    _log.info(f"开始对比模块: {module_name}")
    click.echo(f"开始对比模块: {module_name}")

    if target_module.script is not None:
        click.echo("脚本模块不支持差异对比")
        return

    parent_path = target_module.parent_path or ""
    include_paths = target_module.include_paths or []

    # 获取排除路径模式
    exclude_patterns = target_module.exclude_paths or []

    # 收集所有源文件路径
    source_files_set = set()
    for path_pattern in include_paths:
        # 构造完整路径
        if parent_path:
            source_pattern = Path(parent_path) / path_pattern
        else:
            source_pattern = Path(path_pattern)

        # 展开通配符
        source_files = glob.glob(str(source_pattern), recursive=True)

        for source_str in source_files:
            source_path = Path(source_str)

            # 检查是否为支持的文件类型
            if not source_path.exists():
                continue

            # 检查路径是否在排除列表中
            if should_exclude_path(source_path, exclude_patterns, parent_path):
                continue

            # 将相对路径添加到集合中（相对于根目录）
            source_files_set.add(source_path)

    # 收集该模块在备份目录中的所有文件
    backup_files_set = set()
    for path_pattern in include_paths:
        # 构造备份路径模式
        if parent_path:
            source_pattern = Path(parent_path) / path_pattern
        else:
            source_pattern = Path(path_pattern)

        # 展开通配符
        backup_files = glob.glob(str(source_pattern), recursive=True)

        for backup_str in backup_files:
            backup_path = Path(backup_str)

            # 跳过.meta文件
            if backup_path.suffix == '.meta':
                continue

            if backup_path.exists():
                backup_files_set.add(backup_path)

    compare_files_set(source_files_set, backup_files_set, backup_root, detail)

