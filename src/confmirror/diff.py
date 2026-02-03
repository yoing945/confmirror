"""
差异对比功能模块 - 支持单文件级别的源文件与备份文件比较
"""
import filecmp
import difflib
import glob
from pathlib import Path
from typing import Optional, Tuple, List
from datetime import datetime

import click

from .config import ConfigKeys
from .utils import find_matching_module_with_path, should_exclude_path


def execute_diff(config: dict, logger, target_path: str) -> None:
    """
    执行差异对比操作

    Args:
        config: 配置字典
        logger: 日志记录器
        target_path: 目标路径（原始系统路径）
    """
    settings = config[ConfigKeys.SECTION_SETTINGS]
    backup_root = Path(settings[ConfigKeys.BACKUP_ROOT])

    # 使用 glob 查找所有匹配的文件（包括目录中的文件）
    matched_files = glob.glob(str(target_path), recursive=True)

    for matched_file in matched_files:
        matched_path = Path(matched_file)

        # 检查文件是否存在
        if not matched_path.exists():
            logger.warning(f"[源文件不存在] 跳过差异对比: {matched_path}")
            continue

        # 只处理文件，跳过目录
        if matched_path.is_file():
            # 确定备份文件路径
            rel_path = matched_path.relative_to(Path('/'))
            backup_file_path = backup_root / rel_path

            if not backup_file_path.exists():
                logger.warning(f"[备份文件不存在] 跳过差异对比: {backup_file_path}")
                continue

            # 执行对比
            logger.info(f"正在对比: {matched_path} vs {backup_file_path}")
            compare_files(matched_path, backup_file_path, logger)


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


def batch_diff_module(config: dict, logger, module_name: str) -> None:
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

    total_files = 0
    diff_files = 0

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
            if not source_path.exists() or source_path.is_dir():
                continue

            # 检查路径是否在排除列表中
            if should_exclude_path(source_path, exclude_patterns, parent_path):
                logger.info(f"[路径被排除] 跳过差异对比: {source_path}")
                continue

            # 计算备份路径
            rel_path = source_path.relative_to(Path(parent_path) if parent_path else Path('/'))
            backup_path = backup_root / str(rel_path).lstrip('/')

            if backup_path.exists():
                total_files += 1
                if not filecmp.cmp(source_path, backup_path, shallow=False):
                    diff_files += 1
                    compare_files(source_path, backup_path, logger)

    logger.info(f"模块对比完成: 共{total_files}个文件, {diff_files}个存在差异")


def quick_diff_check(source: Path, backup: Path) -> bool:
    """
    快速检查两个路径是否相同（用于增量备份判断）

    Args:
        source: 源路径
        backup: 备份路径

    Returns:
        bool: 相同返回True，不同返回False
    """
    if not backup.exists():
        return False

    if source.is_file() and backup.is_file():
        # 使用shallow比较（检查大小和修改时间）作为快速判断
        return filecmp.cmp(source, backup, shallow=True)
    elif source.is_dir() and backup.is_dir():
        return filecmp.cmp(source, backup, shallow=True)

    return False