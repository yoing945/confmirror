"""差异对比核心逻辑 — 纯函数，无终端输出。"""

import difflib
import filecmp
import glob
import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from confmirror.config import Config, ModuleConfig, Settings
from confmirror.meta import read_meta
from confmirror.utils import find_matching_module_with_path, should_exclude_path


@dataclass
class FileDiffResult:
    """单个文件的差异结果。"""

    source: Path
    backup: Path
    content_same: bool
    meta_same: bool
    source_size: int
    backup_size: int
    source_mtime: float
    backup_mtime: float
    source_mode: str
    backup_mode: str
    source_uid: int
    backup_uid: int
    source_gid: int
    backup_gid: int
    unified_diff: Optional[List[str]] = None


@dataclass
class DiffResult:
    """模块/路径的差异结果。"""

    module_name: Optional[str]
    added: List[Path]  # 源中有但备份中没有
    deleted: List[Path]  # 备份中有但源中没有
    changed: List[FileDiffResult]
    unchanged: List[FileDiffResult]


def same_file(src: Path, dest: Path) -> bool:
    """比较源文件与备份文件是否相同（内容和元数据）。"""
    return compare_content(src, dest) and compare_meta(src, dest)


def compare_content(src: Path, dest: Path) -> bool:
    """比较两个文件的内容是否相同。"""
    if not dest.exists():
        return False
    try:
        if src.is_dir() != dest.is_dir():
            return False
        if src.is_dir():
            return True
        return filecmp.cmp(src, dest, shallow=False)
    except (OSError, ValueError):
        return _compare_files_by_hash(src, dest)


def compare_meta(src: Path, dest: Path) -> bool:
    """检查源文件的当前元数据是否与上次备份时记录的原始元数据相同。"""
    meta_data = read_meta(dest)
    if not meta_data:
        return False
    src_stat = src.stat()
    src_mode = oct(src_stat.st_mode)[-3:]
    src_uid = src_stat.st_uid
    src_gid = src_stat.st_gid
    return (
        src_mode == meta_data.get("mode", "")
        and src_uid == int(meta_data.get("uid", -1))
        and src_gid == int(meta_data.get("gid", -1))
    )


def _compare_files_by_hash(src: Path, dest: Path) -> bool:
    """通过哈希值比较两个文件的内容是否相同。"""
    try:

        def get_file_hash(file_path):
            hash_obj = hashlib.blake2b()
            with open(file_path, "rb") as f:
                while chunk := f.read(8192):
                    hash_obj.update(chunk)
            return hash_obj.hexdigest()

        return get_file_hash(src) == get_file_hash(dest)
    except (OSError, TypeError):
        return False


def _get_file_diff_lines(
    source: Path, backup: Path, context_lines: int = 3
) -> Optional[List[str]]:
    """生成两个文件的 unified diff 行列表。"""
    try:
        with open(source, "r", encoding="utf-8", errors="ignore") as f:
            source_lines = f.readlines()
        with open(backup, "r", encoding="utf-8", errors="ignore") as f:
            backup_lines = f.readlines()
        diff = list(
            difflib.unified_diff(
                backup_lines,
                source_lines,
                fromfile=f"backup: {backup.name}",
                tofile=f"source: {source.name}",
                n=context_lines,
            )
        )
        return diff if diff else None
    except Exception:
        return None


def compare_files_core(source: Path, backup: Path) -> FileDiffResult:
    """比较两个文件，返回结构化差异结果。"""
    source_stat = source.stat()
    backup_stat = backup.stat()
    is_dir = source.is_dir() and backup.is_dir()

    meta_data = read_meta(backup)
    meta_same = compare_meta(source, backup)

    if is_dir:
        return FileDiffResult(
            source=source,
            backup=backup,
            content_same=True,
            meta_same=meta_same,
            source_size=source_stat.st_size,
            backup_size=backup_stat.st_size,
            source_mtime=source_stat.st_mtime,
            backup_mtime=backup_stat.st_mtime,
            source_mode=oct(source_stat.st_mode)[-3:],
            backup_mode=meta_data.get("mode", "N/A") if meta_data else "N/A",
            source_uid=source_stat.st_uid,
            backup_uid=int(meta_data.get("uid", -1)) if meta_data else -1,
            source_gid=source_stat.st_gid,
            backup_gid=int(meta_data.get("gid", -1)) if meta_data else -1,
        )

    content_same = compare_content(source, backup)
    return FileDiffResult(
        source=source,
        backup=backup,
        content_same=content_same,
        meta_same=meta_same,
        source_size=source_stat.st_size,
        backup_size=backup_stat.st_size,
        source_mtime=source_stat.st_mtime,
        backup_mtime=backup_stat.st_mtime,
        source_mode=oct(source_stat.st_mode)[-3:],
        backup_mode=meta_data.get("mode", "N/A") if meta_data else "N/A",
        source_uid=source_stat.st_uid,
        backup_uid=int(meta_data.get("uid", -1)) if meta_data else -1,
        source_gid=source_stat.st_gid,
        backup_gid=int(meta_data.get("gid", -1)) if meta_data else -1,
        unified_diff=_get_file_diff_lines(source, backup) if not content_same else None,
    )


def _collect_files_for_paths(
    config: Config, target_paths: List[str]
) -> tuple[set, set]:
    """为指定路径收集源文件集合和备份文件集合。"""
    settings = config.settings
    backup_root = settings.backup_root
    source_files_set = set()
    backup_files_set = set()

    for target_path in target_paths:
        module = find_matching_module_with_path(config.modules, Path(target_path))
        if not module:
            continue
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

    return source_files_set, backup_files_set


def _collect_files_for_module(config: Config, module: ModuleConfig) -> tuple[set, set]:
    """为模块收集源文件集合和备份文件集合。"""
    settings = config.settings
    backup_root = settings.backup_root
    parent_path = module.base_path or ""
    include_paths = module.paths or []
    exclude_patterns = module.exclude_paths or []

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

    return source_files_set, backup_files_set


def diff_module_core(
    config: Config, module_name: str, detail: bool = False
) -> DiffResult:
    """对比整个模块，返回结构化结果。"""
    settings = config.settings
    backup_root = settings.backup_root
    target_module = next((m for m in config.modules if m.name == module_name), None)

    if not target_module or target_module.hook is not None:
        return DiffResult(
            module_name=module_name, added=[], deleted=[], changed=[], unchanged=[]
        )

    source_files_set, backup_files_set = _collect_files_for_module(
        config, target_module
    )

    added_files = source_files_set - backup_files_set
    deleted_files = backup_files_set - source_files_set
    common_files = source_files_set & backup_files_set

    changed = []
    unchanged = []
    for common_file in common_files:
        source_file = Path("/") / common_file
        backup_file = backup_root / str(common_file).lstrip("/")
        if source_file.exists() and backup_file.exists():
            result = compare_files_core(source_file, backup_file)
            if not result.content_same or not result.meta_same:
                changed.append(result)
            else:
                unchanged.append(result)

    return DiffResult(
        module_name=module_name,
        added=list(added_files),
        deleted=list(deleted_files),
        changed=changed,
        unchanged=unchanged,
    )


def diff_paths_core(
    config: Config, target_paths: List[str], detail: bool = False
) -> DiffResult:
    """对比指定路径，返回结构化结果。"""
    settings = config.settings
    backup_root = settings.backup_root
    source_files_set, backup_files_set = _collect_files_for_paths(config, target_paths)

    added_files = source_files_set - backup_files_set
    deleted_files = backup_files_set - source_files_set
    common_files = source_files_set & backup_files_set

    changed = []
    unchanged = []
    for common_file in common_files:
        source_file = Path("/") / common_file
        backup_file = backup_root / str(common_file).lstrip("/")
        if source_file.exists() and backup_file.exists():
            result = compare_files_core(source_file, backup_file)
            if not result.content_same or not result.meta_same:
                changed.append(result)
            else:
                unchanged.append(result)

    return DiffResult(
        module_name=None,
        added=list(added_files),
        deleted=list(deleted_files),
        changed=changed,
        unchanged=unchanged,
    )
