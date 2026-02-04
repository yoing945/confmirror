"""
差异对比功能模块 - 支持单文件级别的源文件与备份文件比较
"""
import filecmp
import difflib
import glob
import fnmatch
import os
from pathlib import Path
from typing import Optional, Tuple, List
from datetime import datetime

import click

from .config import ConfigKeys
from .utils import find_matching_module_with_path, should_exclude_path

def compare_files(source: Path, backup: Path, logger, show_content_diff: bool = True) -> bool:
    """
    比较两个文件

    Args:
        source: 源文件路径
        backup: 备份文件路径
        logger: 日志记录器
        show_content_diff: 是否显示详细内容差异

    Returns:
        bool: 文件相同返回True，不同返回False
    """
    # 首先进行shallow比较（文件大小和修改时间）
    shallow_same = filecmp.cmp(source, backup, shallow=True)

    # 然后进行deep比较（内容）
    deep_same = filecmp.cmp(source, backup, shallow=False)

    source_stat = source.stat()
    backup_stat = backup.stat()

    logger.info(f"文件: {source.name}")
    logger.info(f"  源文件: {source}")
    logger.info(f"  备份文件: {backup}")
    logger.info(f"  基本信息:")
    logger.info(f"  - 源大小: {source_stat.st_size} bytes")
    logger.info(f"  - 备份大小: {backup_stat.st_size} bytes")
    logger.info(f"  - 源修改时间: {datetime.fromtimestamp(source_stat.st_mtime)}")
    logger.info(f"  - 备份修改时间: {datetime.fromtimestamp(backup_stat.st_mtime)}")

    if deep_same:
        logger.info(f"  ✅ 状态: 文件内容完全一致")
        return True
    else:
        logger.info(f"  ⚠️  状态: 文件存在差异")
        if not shallow_same:
            logger.info(f"  - 元数据不同（大小或修改时间）")

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
            click.echo("   " + "-" * 50)
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
            click.echo("   " + "-" * 50)
        else:
            click.echo(f"\n   📝 文件文本内容相同（但可能存在编码或换行符差异）")

    except Exception as e:
        click.echo(f"\n   ⚠️  无法读取文件内容进行差异对比: {e}")


def compare_files_set(source_files_set: set, backup_files_set: set, logger, backup_root: Path) -> None:
    # 计算新增、删除和修改的文件
    added_files = source_files_set - backup_files_set  # 源中有但备份中没有
    deleted_files = backup_files_set - source_files_set  # 备份中有但源中没有
    common_files = source_files_set & backup_files_set  # 两者都有

    for added_file in added_files:
        logger.info(f"[新增源文件]: /{added_file}")

    for deleted_file in deleted_files:
        logger.info(f"[缺失源文件]: /{deleted_file}")

    # 比较共同存在的文件
    total_common_files = len(common_files)
    diff_files = 0

    for common_file in common_files:
        source_file = Path('/') / common_file
        backup_file = backup_root / str(common_file).lstrip('/')

        if source_file.exists() and backup_file.exists():
            if not filecmp.cmp(source_file, backup_file, shallow=False):
                diff_files += 1
                compare_files(source_file, backup_file, logger)

    logger.info(f"对比完成: 共{total_common_files}个共同文件, {diff_files}个存在差异, "
                f"{len(added_files)}个新增, {len(deleted_files)}个缺失")
    

def diff_paths(config: dict, logger, target_paths: List[str]) -> None:
    """
    对比指定路径下的所有文件与备份目录中的差异

    Args:
        config: 配置字典
        logger: 日志记录器
        target_path: 目标路径（原始系统路径）
    """
    settings = config[ConfigKeys.SECTION_SETTINGS]
    backup_root = Path(settings[ConfigKeys.BACKUP_ROOT])

    # 收集所有源文件路径
    source_files_set = set()
    # 收集该模块在备份目录中的所有文件
    backup_files_set = set()
    for target_path in target_paths:
        module = find_matching_module_with_path(config.get(ConfigKeys.SECTION_MODULES, []), Path(target_path))
        if not module:
            logger.error(f"❌ 路径 '{target_path}' 不属于任何模块")
            return
        # 获取排除路径模式和父路径
        all_exclude_patterns = module.get(ConfigKeys.MOD_EXCLUDE_PATHS, [])
        parent_path = module.get(ConfigKeys.MOD_PARENT_PATH, "")
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

    compare_files_set(source_files_set, backup_files_set, logger, backup_root)


def diff_module(config: dict, logger, module_name: str) -> None:
    """
    对比整个模块的所有文件

    Args:
        config: 配置字典
        logger: 日志记录器
        module_name: 模块名称
    """
    settings = config[ConfigKeys.SECTION_SETTINGS]
    backup_root = Path(settings[ConfigKeys.BACKUP_ROOT])

    modules = config.get(ConfigKeys.SECTION_MODULES, [])
    target_module = next((m for m in modules if m[ConfigKeys.MOD_NAME] == module_name), None)

    if not target_module:
        logger.error(f"未找到模块: {module_name}")
        return

    logger.info(f"开始对比模块: {module_name}")

    if ConfigKeys.MOD_SCRIPT in target_module:
        logger.info("脚本模块不支持差异对比")
        return

    parent_path = target_module.get(ConfigKeys.MOD_PARENT_PATH, "")
    include_paths = target_module.get(ConfigKeys.MOD_INCLUDE_PATHS, [])

    # 获取排除路径模式
    exclude_patterns = target_module.get(ConfigKeys.MOD_EXCLUDE_PATHS, [])

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
                logger.info(f"[路径被排除] 跳过差异对比: {source_path}")
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

    compare_files_set(source_files_set, backup_files_set, logger, backup_root)
    
