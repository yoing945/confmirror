import logging
import glob
import os
import shutil
from pathlib import Path
from typing import Optional, Dict, Any

from .config import Config, ModuleConfig, Settings
from .meta import read_meta
from .utils import find_matching_module_with_path, run_shell_script, should_exclude_path
from .logger import ModuleLog

logger = logging.getLogger(__name__)
_log = ModuleLog("restore", logger)


def execute_restore(config: Config, target_module_name: Optional[str] = None, target_path: Optional[str] = None, force: bool = False) -> None:
    """
    执行还原操作

    Args:
        config: 配置对象
        target_module_name: 指定要还原的模块名称
        target_path: 指定要还原的路径
        force: 是否强制覆盖还原（默认为False，即差异还原）
    """
    if os.name != 'nt' and os.getuid() != 0:
        _log.warn("当前未以 root 身份运行，restore 操作可能因权限不足而失败。建议：sudo confmirror restore ...")

    if target_module_name:
        # 还原指定模块
        target_module = next((m for m in config.modules if m.name == target_module_name), None)
        if not target_module:
            _log.error(f"配置中不存在模块 '{target_module_name}'")
            return
        restore_module(target_module, config, force)
    elif target_path:
        # 还原指定路径
        restore_single_path(target_path, config, force)
    else:
        # 全量还原
        for module in config.modules:
            restore_module(module, config, force)


def restore_module(module: ModuleConfig, config: Config, force: bool = False) -> None:
    """
    还原单个模块

    Args:
        module: 模块配置对象
        config: 配置对象
        force: 是否强制覆盖还原
    """
    settings = config.settings
    backup_root = settings.backup_root

    module_name = module.name
    _log.info(f"开始还原模块: {module_name}")

    if module.script is not None:
        script_rel = module.script
        run_shell_script(script_rel, settings, "restore")

    elif module.include_paths is not None:
        parent_path_str = module.parent_path or ""
        backup_parent_path = backup_root / parent_path_str.lstrip('/')

        # 获取排除路径模式
        all_exclude_patterns = module.exclude_paths or []

        for path_str in module.include_paths:
            full_path_pattern = str(backup_parent_path / path_str.lstrip('/'))
            matched_paths = glob.glob(full_path_pattern, recursive=True)

            for path_str in matched_paths:
                # 跳过 .meta 文件本身
                if path_str.endswith('.meta'):
                    continue

                path = Path(path_str)

                # 检查是否应该排除此路径
                if should_exclude_path(path, all_exclude_patterns, str(backup_parent_path)):
                    _log.skip(f"路径 '{path}' 被排除")
                    continue

                # 获取相对于备份根目录的路径，这是原始路径
                try:
                    rel_path = path.relative_to(backup_root)
                    original_path = Path('/') / rel_path
                    restore_file_or_dir(original_path, backup_root, force)
                except ValueError:
                    _log.warn(f"路径不在备份根目录下 → {path}")


def restore_single_path(target_path: str, config: Config, force: bool = False) -> None:
    """
    还原单个路径

    Args:
        target_path: 目标路径
        config: 配置对象
        force: 是否强制覆盖还原
    """
    settings = config.settings
    backup_root = settings.backup_root

    # 检查路径是否属于某个模块
    module = find_matching_module_with_path(config.modules, Path(target_path))
    if not module:
        _log.error(f"路径 '{target_path}' 不属于任何模块，无法还原")
        return

    # 获取排除路径模式和父路径
    all_exclude_patterns = module.exclude_paths or []
    parent_path = module.parent_path or ""
    if should_exclude_path(Path(target_path), all_exclude_patterns, parent_path):
        _log.skip(f"路径 '{target_path}' 被排除")
        return

    # 将用户输入的路径转换为备份根目录下的路径
    backup_target_path = backup_root / target_path.lstrip('/')

    # 使用 glob 查找所有匹配的文件
    matched_files = glob.glob(str(backup_target_path), recursive=True)

    for file_path in matched_files:
        if file_path.endswith('.meta'):
            continue

        # 获取相对于备份根目录的路径，这是原始路径
        try:
            rel_path = Path(file_path).relative_to(backup_root)
            original_path = Path('/') / rel_path
            restore_file_or_dir(original_path, backup_root, force)
        except ValueError:
            _log.warn(f"路径不在备份根目录下 → {file_path}")

def restore_file_or_dir(original: Path, backup_root: Path, force: bool = False):
    """
    还原单个文件或目录

    Args:
        original: 原始路径
        backup_root: 备份根目录
        logger: 日志记录器
        force: 是否强制覆盖还原
    """
    # 获取备份路径
    backup = backup_root / str(original).lstrip("/")
    meta = read_meta(backup)

    if not meta:
        _log.warn(f"缺少 .meta → {original}")
        return

    if not backup.exists():
        _log.warn(f"备份内容不存在 → {original}")
        return

    # 检查是否需要跳过（差异还原模式）
    if not force and original.exists():
        # 导入差异比较函数
        from .diff import same_file
        if same_file(original, backup):
            _log.skip(f"文件信息无变化: {original}")
            return

    # 创建父目录
    original.parent.mkdir(parents=True, exist_ok=True)

    mode = meta["mode"]
    uid = int(meta["uid"])
    gid = int(meta["gid"])
    ftype = meta["type"]

    try:
        if ftype == "file":
            shutil.copy2(backup, original)
            os.chmod(original, int(mode, 8))
            os.chown(original, uid, gid)
            _log.ok(f"{original}")
        elif ftype == "dir":
            original.mkdir(exist_ok=True)
            # 类似rsync的复制 (shutil.copytree 不覆盖，用 walk)
            for src_dir, dirs, files in os.walk(backup):
                dst_dir = original / Path(src_dir).relative_to(backup)
                dst_dir.mkdir(exist_ok=True)
                for file_ in files:
                    if not file_.endswith(".meta"):
                        src_file = Path(src_dir) / file_
                        dst_file = dst_dir / file_
                        shutil.copy2(src_file, dst_file)
            os.chmod(original, int(mode, 8))
            os.chown(original, uid, gid)
            _log.ok(f"{original}")
    except PermissionError as e:
        _log.error(f"无法还原 {e}")
        _log.error("提示: 此文件可能需要 root 权限才能还原，请尝试使用 sudo 运行此命令")
    except Exception as e:
        _log.error(f"{original}: {str(e)}")